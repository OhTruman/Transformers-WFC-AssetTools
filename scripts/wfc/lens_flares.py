"""MP lens flares (Integration 2026-10-18, with RE's LENS_FLARE_RE.md): every LensFlareSource placed in the 10 MP maps (one each in
BrokenHope / Remnant / Rust / Seed / Debris / Gorge), its LensFlareComponent and LensFlare template with every element.
All values are cooked tagged properties (CONFIRMED). Fields a template / element does not set fall back to the Engine class default
object (Default__LensFlare / Default__LensFlareComponent), marked per field. Element distributions are raw lookup tables (UE3
FRawDistribution): decoded with the layout pstream.DIST_LAYOUT documents (constant / constant curve: min, max, start, time scale, samples).
What each curve's input is (radial distance, occlusion, screen percentage) is RE's to state (LENS_FLARE_RE.md); not inferred here.
Textures of the element materials are copied from ExtractedAssets/content into AssetTools/out/lens_flares/.
Writes manifests/maps/lens_flares/<map>_lens_flares.json. Read-only on the dump and on other lanes.
"""
import json, os, shutil, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(ROOT)
CONTENT = os.path.join(TR, 'ExtractedAssets', 'content')
OUT = os.path.join(ROOT, 'out', 'lens_flares')
DB = sqlite3.connect(os.path.join(ROOT, 'manifests', 'authored.db'))
INV = sqlite3.connect(os.path.join(ROOT, 'manifests', 'inventory.db'))
MAPS = ['MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_IAC_Streets', 'MP_KON_Molten',
        'MP_ORB_Debris', 'MP_UND_Complex', 'MP_UND_Gorge']
PKG_PREFIX = {'MP_ORB_Debris': ('MP_ORB_',)}        # Debris' level packages are named MP_ORB_*_m

def props(o):
    r = DB.execute('select props from objects where opath=?', (o,)).fetchone()
    return json.loads(r[0]) if r and r[0] else {}

def dist(d):
    """raw distribution -> decoded form (constant / curve samples), raw table kept"""
    if not isinstance(d, dict) or 'LookupTable' not in d: return d
    t, lut, ch = d.get('Type'), d['LookupTable'], max(1, int(d.get('LookupTableChunkSize') or 1))
    out = {'type': t, 'op': d.get('Op'), 'raw': lut}
    if t is None and len(lut) > ch and len(lut) >= 4 + ch and (len(lut) - 4) % ch == 0:
        t = 2 if ch == 1 else 8          # Type not stored: header + whole samples = the curve layout
        out['type_inferred'] = 'Type not in the cooked struct; curve layout inferred from the table length (HIGH)'
    if t in (1, 7):
        out.update({'kind': 'constant', 'value': lut[0] if ch == 1 else lut[:ch]})
    elif t in (2, 8) and len(lut) >= 4:
        smp = lut[4:]; n = len(smp) // ch
        out.update({'kind': 'constant curve', 'range': lut[0:2], 'start': lut[2], 'time_scale': lut[3],
                    'samples': [smp[i * ch:(i + 1) * ch] if ch > 1 else smp[i] for i in range(n)],
                    'sample_inputs': [lut[2] + i / lut[3] for i in range(n)] if lut[3] else None})
    elif t in (3, 9):
        out.update({'kind': 'uniform', 'min': lut[:ch], 'max': lut[ch:2 * ch]})
    else:
        out['kind'] = 'other (raw only)'
    return out

def material_textures(mat, depth=0):
    out = []
    if not mat or depth > 8: return out
    for prop, dst, cls in DB.execute("select prop, dst, dst_class from refs where src like ? and dst_class like 'Texture%'", (mat + '%',)):
        if dst not in out: out.append(dst)
    par = props(mat).get('Parent')
    return out + [t for t in material_textures(par, depth + 1) if t not in out]

def element(e, default):
    dec = {}
    for k, v in e.items():
        dec[k] = dist(v) if isinstance(v, dict) and 'LookupTable' in v else v
    unset = sorted(k for k in default if k not in e)
    for k in unset:
        v = default[k]; dec[k] = dist(v) if isinstance(v, dict) and 'LookupTable' in v else v
    dec['_from_class_default'] = unset
    mats = []
    for m in e.get('LFMaterials') or []:
        texs = []
        for t in material_textures(m):
            src = os.path.join(CONTENT, *t.split('.')) + '.png'
            rec = {'texture': t, 'extracted': os.path.exists(src)}
            if rec['extracted']:
                os.makedirs(OUT, exist_ok=True)
                dst = os.path.join(OUT, t.replace('.', '__') + '.png'); shutil.copy2(src, dst)
                from PIL import Image
                im = Image.open(dst); rec.update({'file': os.path.relpath(dst, TR).replace(os.sep, '/'), 'size': list(im.size), 'mode': im.mode})
            texs.append(rec)
        mats.append({'material': m, 'class': (DB.execute('select class from objects where opath=?', (m,)).fetchone() or [None])[0],
                     'textures': texs})
    dec['_materials'] = mats
    return dec

def main():
    dlf = props('Engine.Default__LensFlare'); dlc = props('Engine.Default__LensFlareComponent')
    el_default = dlf.get('SourceElement') or {}
    for mp in MAPS:
        pre = PKG_PREFIX.get(mp, (mp + '_',))
        rows = [r for r in INV.execute("select package, opath from exports where class='LensFlareSource' and opath not like '%Default__%'")
                if r[0].startswith(pre)]
        flares = []
        for pkg, src in rows:
            ap = props(src); comp = ap.get('LensFlareComp'); cp = props(comp)
            comp_v = {k: cp.get(k, dlc.get(k)) for k in sorted(set(cp) | set(dlc))}
            tpl = cp.get('Template'); tp = props(tpl)
            tpl_v = {k: tp.get(k, dlf.get(k)) for k in ('Radius', 'ConeFudgeFactor', 'InnerCone', 'OuterCone', 'SourceDPG', 'ReflectionsDPG',
                                                          'ScreenPercentageMap', 'bUseFixedRelativeBoundingBox', 'FixedRelativeBoundingBox',
                                                          'SourceMesh')}
            if isinstance(tpl_v.get('ScreenPercentageMap'), dict): tpl_v['ScreenPercentageMap'] = dist(tpl_v['ScreenPercentageMap'])
            flares.append({
                'actor': src, 'level_package': pkg, 'component': comp,
                'location_ue': ap.get('Location'), 'rotation_ue': ap.get('Rotation', {'Pitch': 0, 'Yaw': 0, 'Roll': 0}),
                'draw_scale': ap.get('DrawScale', 1.0), 'draw_scale3d': ap.get('DrawScale3D', {'X': 1.0, 'Y': 1.0, 'Z': 1.0}),
                'group': ap.get('Group'), 'tag': ap.get('Tag'),
                'component_props': comp_v, 'component_props_from_class_default': sorted(k for k in dlc if k not in cp),
                'template': tpl, 'template_props': tpl_v,
                'template_props_from_class_default': sorted(k for k in tpl_v if k not in tp),
                'source_element': element(tp.get('SourceElement') or {}, el_default),
                'reflections': [element(e, el_default) for e in tp.get('Reflections') or []]})
        if not flares: print(mp, 0); continue          # no LensFlareSource in this map: no file
        doc = {'map': mp, 'generated_by': 'AssetTools/scripts/wfc/lens_flares.py',
               'semantics': 'RE-Workspace/work/handoff/LENS_FLARE_RE.md (RE) for how the runtime uses each field / curve input',
               'distribution_layout': 'constant: value; constant curve: range = output min/max, start, time_scale, samples at start + i / '
                                      'time_scale (pstream DIST_LAYOUT); raw lookup table kept as "raw"',
               'count': len(flares), 'lens_flares': flares}
        os.makedirs(os.path.join(ROOT, 'manifests', 'maps', 'lens_flares'), exist_ok=True)
        json.dump(doc, open(os.path.join(ROOT, 'manifests', 'maps', 'lens_flares', mp + '_lens_flares.json'), 'w', encoding='utf-8'), indent=1)
        print(mp, len(flares), [(f['template'].split('.')[-1], len(f['reflections']),
                                 sum(len(m['textures']) for e in f['reflections'] for m in e['_materials'])) for f in flares])

if __name__ == '__main__':
    main()
