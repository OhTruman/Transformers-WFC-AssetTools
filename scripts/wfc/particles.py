"""ParticleSystem summarizer (authored data, read-only).

For a ParticleSystem opath, emits per emitter / per LOD:
  * ParticleModuleRequired tagged props (material, local space, duration, loops,
    bursts, spawn rate, screen alignment, SubUV ...)             -> CONFIRMED (tagged)
  * TypeData module (Mesh / Trail2 / Beam2 ...) with its tagged props -> CONFIRMED
  * any other surviving *tagged* module exports under the LOD       -> CONFIRMED
  * WFC's compiled native per-LOD module stream: raw UE3 distribution tables
    found in the bytes after the LOD's tagged block.  Layout (from the Systems agent's
    lodscan.py, re-verified here): u8 type, u8 op, u8 n, u8 chunk, i32 count, count BE floats.
    type 1 float const, 2 float curve, 3 float uniform, 7 vector const, 8 vector curve,
    9 vector uniform, 10 vector uniform curve.  WHICH module each table belongs to is
    NOT encoded by name -> reported in stream order only            -> PARTIAL
  * the emitter material(s): BlendMode, LightingModel, TwoSided, textures sampled,
    parameter names/defaults                                       -> CONFIRMED (tagged)

CLI: python particles.py <ParticleSystem opath> [--pkg PACKAGE] [--out file.json]
"""
import argparse, json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, typed_props as tp  # noqa: E402

def scan_stream(d, start):
    out, i = [], start
    while i + 8 <= len(d):
        t, op, n, ch = d[i], d[i + 1], d[i + 2], d[i + 3]
        if 1 <= t <= 12 and op <= 3 and 1 <= n <= 64 and 1 <= ch <= 16:
            cnt = struct.unpack_from('>i', d, i + 4)[0]
            if 1 <= cnt <= 2048 and i + 8 + cnt * 4 <= len(d):
                fl = struct.unpack_from('>%df' % cnt, d, i + 8)
                if all(abs(x) < 1e7 for x in fl):
                    out.append({'offset': i - start, 'dist_type': t, 'op': op, 'n': n, 'chunk': ch,
                                'values': [round(x, 5) for x in fl][:64]})
                    i += 8 + cnt * 4; continue
        i += 1
    return out

def material_summary(p, opath, depth=0):
    i = p._idx.get((opath or '').lower())
    if not i: return {'material': opath, 'not_in_package': True}
    d = tp.simplify(p._tr.read_dict(i))
    cls = p.class_name(p.exports[i - 1])
    out = {'material': opath, 'class': cls}
    for k in ('BlendMode', 'LightingModel', 'TwoSided', 'bIsMasked', 'OpacityMaskClipValue', 'bUsedWithParticleSprites',
              'bUsedWithBeamTrails', 'bUsedWithMeshParticles', 'Wireframe', 'bDisableDepthTest'):
        if k in d: out[k] = d[k]
    if cls.startswith('MaterialInstance'):
        out['parent'] = d.get('Parent')
        for k in ('ScalarParameterValues', 'VectorParameterValues', 'TextureParameterValues', 'StaticParameters'):
            if k in d: out[k] = d[k]
        if d.get('Parent') and depth < 6: out['parent_summary'] = material_summary(p, d['Parent'], depth + 1)
        return out
    # base Material: walk its expressions for textures/parameters
    tex, params = set(), []
    pre = opath.lower() + '.'
    for k, j in p._idx.items():
        if not k.startswith(pre): continue
        c = p.class_name(p.exports[j - 1])
        if not c.startswith('MaterialExpression'): continue
        try: e = tp.simplify(p._tr.read_dict(j))
        except Exception: continue
        if e.get('Texture'): tex.add(e['Texture'])
        if 'ParameterName' in e:
            params.append({'class': c, 'name': e['ParameterName'],
                           'default': e.get('DefaultValue', e.get('Texture'))})
    out['textures'] = sorted(tex); out['parameters'] = params
    return out

def summarize(ps, pkg=None):
    pkg = pkg or objtree.owner(ps)
    p = objtree.package(pkg)
    i = p._idx.get(ps.lower())
    if not i: return {'particle_system': ps, 'missing_in': pkg}
    root = tp.simplify(p._tr.read_dict(i))
    out = {'particle_system': ps, 'package': pkg,
           'props': {k: v for k, v in root.items() if k != 'Emitters'}, 'emitters': [],
           'provenance': 'tagged props CONFIRMED; native_stream tables PARTIAL (module role by order only)'}
    mats = {}
    for em in root.get('Emitters') or []:
        if not em: continue
        j = p._idx.get(em.lower())
        if not j: continue
        ed = tp.simplify(p._tr.read_dict(j))
        e = {'emitter': em, 'class': p.class_name(p.exports[j - 1]), 'name': ed.get('EmitterName'),
             'props': {k: v for k, v in ed.items() if k not in ('LODLevels', 'EmitterName')}, 'lods': []}
        for lod in ed.get('LODLevels') or []:
            k = p._idx.get((lod or '').lower())
            if not k: continue
            tags, used = p._tr.read_object(k)
            ld = tp.simplify(tp.to_dict(tags))
            x = p.exports[k - 1]
            raw = p.data[x['serial_offset']:x['serial_offset'] + x['serial_size']]
            L = {'lod': lod, 'level': ld.get('Level', 0), 'props': {a: b for a, b in ld.items()
                 if a not in ('RequiredModule', 'TypeDataModule', 'Modules', 'SpawnModules', 'UpdateModules')}}
            for key in ('RequiredModule', 'TypeDataModule'):
                r = ld.get(key)
                if r and r.lower() in p._idx:
                    rd = tp.simplify(p._tr.read_dict(p._idx[r.lower()]))
                    L[key] = {'object': r, 'class': p.class_name(p.exports[p._idx[r.lower()] - 1]), 'props': rd}
                    if key == 'RequiredModule' and rd.get('Material'): mats[rd['Material']] = None
                    if key == 'TypeDataModule' and rd.get('Mesh'): L['mesh'] = rd['Mesh']
            mods = ld.get('Modules') or []
            if mods:
                L['tagged_modules'] = []
                for m in mods:
                    if m and m.lower() in p._idx:
                        mi = p._idx[m.lower()]
                        L['tagged_modules'].append({'object': m, 'class': p.class_name(p.exports[mi - 1]),
                                                    'props': tp.simplify(p._tr.read_dict(mi))})
            L['native_tail_bytes'] = len(raw) - used
            L['native_stream'] = scan_stream(raw, used)
            e['lods'].append(L)
        out['emitters'].append(e)
    out['materials'] = {m: material_summary(p, m) for m in mats}
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('ps'); ap.add_argument('--pkg'); ap.add_argument('--out')
    a = ap.parse_args()
    s = json.dumps(summarize(a.ps, a.pkg), indent=1, default=str)
    if a.out: open(a.out, 'w').write(s)
    else: print(s)
