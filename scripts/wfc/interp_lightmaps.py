"""Baked interpolated light maps of the 32 MP transforming world actors (Integration 2026-10-18; layout RE INTERPOLATED_LIGHTMAP_RE.md
d2ad301, decoded with RE-Workspace/tools/interp_lightmap.decode, imported read-only).

Per actor: its HmInterpolatedLightMappedSkeletalMeshComponent's two texture light-map captures (0 = untransformed, LightMapCapturePercentage
0; 1 = transformed, 1), each = 3 directional coefficient LightMapTexture2D (in <map>_LM) + 3 scale vectors + the atlas UV transform
(uv * coordScale + coordBias) + the capture's baked light GUIDs. Records use lighting.json's lightmap shape (coeffs / scales / coordScale /
coordBias) so build_lighting.py can read them. Coefficient textures point at Rendering's exported atlas PNGs
(Rebuild/work/render/<map>/lightmaps/<texture>.png, with the capture's pixel rectangle); any texture not there is decoded from the cooked
data into AssetTools/out/interp_lightmaps/<map>/.
Writes manifests/maps/transforming_actors/<map>_interp_lightmaps.json. Read-only on the dump and on every other lane.
"""
import json, os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(ROOT)
sys.path.insert(0, os.path.join(TR, 'RE-Workspace', 'tools'))
sys.path.insert(0, os.path.join(TR, 'Rebuild', 'tools', 'render'))
import ue3pkg  # noqa: E402
import interp_lightmap as RE  # noqa: E402
from PIL import Image  # noqa: E402

DUMP = os.path.join(TR, 'Game Dump', 'TransGame', 'CookedXenon')
OUT_DIR = os.path.join(ROOT, 'out', 'interp_lightmaps')
POSES = ['untransformed', 'transformed']           # LightMapCapturePercentages [0, 1] (class default; RE C)

def components(pkg_name):
    p = ue3pkg.Package(os.path.join(DUMP, pkg_name + '.xxx')); d = p.data; res = {}
    for i, e in enumerate(p.exports, 1):
        if p.class_name(e) != RE.CLS: continue
        b = d[e['serial_offset']:e['serial_offset'] + e['serial_size']]
        for k in range(len(b) - 21, -1, -1):        # same tail search as RE's __main__
            if b[k + 16] != 1: continue
            try: r, end = RE.decode(p, b[k:])
            except Exception: continue
            if k + end == len(b) and (r['captures'] or end == 21): res[p.object_path(i)] = r; break
    return res

_cooked = None
def decode_texture(mp, tex_name):
    """LightMapTexture2D -> PNG via Rendering's xbox_texture (same path as build_materials.native_decode), into out/"""
    global _cooked
    import xbox_texture
    from ue3obj import Repo, COOKED
    if _cooked is None: _cooked = {f.lower(): f for f in os.listdir(COOKED)}
    lm = _cooked.get((mp + '_LM.xxx').lower())
    R = Repo([lm]); path = next((k for k in R.index if k.endswith('.' + tex_name.lower())), None)
    if not path: return None, 'not found in %s' % lm
    o = R.obj(path) or {}; _, tail = R.native_tail(path)
    mips, _ = xbox_texture.read_mip_chain(tail, 0)
    sx, sy, data = next(m for m in mips if m[2])
    os.makedirs(os.path.join(OUT_DIR, mp), exist_ok=True)
    fn = os.path.join(OUT_DIR, mp, tex_name + '.png')
    Image.fromarray(xbox_texture.decode_mip(sx, sy, data, o.get('Format', 'PF_DXT1'))).save(fn)
    return fn, None

def main():
    actors = json.load(open(os.path.join(ROOT, 'manifests', 'maps', 'mp_transforming_actors.json'), encoding='utf-8'))['actors']
    by_map = {}
    for a in actors: by_map.setdefault(a['map'], []).append(a)
    for mp, acts in sorted(by_map.items()):
        comps = {}
        for sub in sorted({a['sublevel'] for a in acts}): comps.update(components(sub))
        lmdir = os.path.join(TR, 'Rebuild', 'work', 'render', mp, 'lightmaps')
        out = {}; stats = {'actors': len(acts), 'captures': 0, 'textures_in_render_atlas': 0, 'textures_decoded_here': 0, 'problems': []}
        for a in acts:
            cand = {k: v for k, v in comps.items() if k.startswith(a['object'] + '.')}
            if len(cand) != 1:
                stats['problems'].append('%s: %d interpolated components' % (a['actor'], len(cand))); continue
            comp, r = next(iter(cand.items()))
            if r is None or not r['captures']:
                stats['problems'].append('%s: unbuilt' % a['actor']); continue
            caps = []
            for ci, c in enumerate(r['captures']):
                names = [t['texture'].split('.')[-1] for t in c['textures']]
                files, rects = [], []
                for n in names:
                    f = os.path.join(lmdir, n + '.png'); src = 'render_atlas'
                    if not os.path.exists(f):
                        f, err = decode_texture(mp, n); src = 'decoded_here'
                        if not f: stats['problems'].append('%s capture %d: %s %s' % (a['actor'], ci, n, err)); files.append(None); rects.append(None); continue
                    stats['textures_in_render_atlas' if src == 'render_atlas' else 'textures_decoded_here'] += 1
                    w, h = Image.open(f).size
                    sx, sy = c['coordinate_scale']; bx, by = c['coordinate_bias']
                    rects.append({'x': round(bx * w, 3), 'y': round(by * h, 3), 'w': round(sx * w, 3), 'h': round(sy * h, 3), 'atlas_size': [w, h]})
                    files.append({'file': os.path.relpath(f, TR).replace(os.sep, '/'), 'source': src})
                caps.append({'capture': ci, 'pose': POSES[ci] if ci < 2 else None, 'capture_percentage': float(ci) if ci < 2 else None,
                             'type': c['type'], 'coeffs': names,
                             'scales': [t['scale'][:3] for t in c['textures']], 'scales_w': [t['scale'][3] for t in c['textures']],
                             'coordScale': c['coordinate_scale'], 'coordBias': c['coordinate_bias'],
                             'texture_files': files, 'atlas_rects_px': rects, 'lights': c['lights']})
                stats['captures'] += 1
            out[a['object']] = {'actor': a['actor'], 'component': comp, 'skeletal_mesh': a['skeletal_mesh'],
                                'initial_state': a.get('initial_state'), 'anim_sequence': a.get('anim_sequence'),
                                'lighting_guid': r['lighting_guid'], 'baked_lights': r['baked_lights'],
                                'irrelevant_lights': r['irrelevant_lights'], 'captures': caps}
        doc = {'map': mp, 'generated_by': 'AssetTools/scripts/wfc/interp_lightmaps.py',
               'source': 'cooked HmInterpolatedLightMappedSkeletalMeshComponent native tails (RE INTERPOLATED_LIGHTMAP_RE.md d2ad301; '
                         'decoder RE-Workspace/tools/interp_lightmap.py, read-only)',
               'shader': 'L_i = A_i + LightMapLerpAmount * (B_i - A_i) with A_i / B_i = texture(capture 0 / 1 coeff i, uv * coordScale + coordBias) '
                         '* scale_i; then the stock directional light-map decode (RE §2, CONFIRMED)',
               'lerp_driver': 'LightMapLerpAmount = the actor AnimNodeSequence normalized position, set every component tick; '
                              'script sets 0 / 1 at setup (RE §3, CONFIRMED)',
               'record_shape': 'per capture: coeffs / scales (rgb) / coordScale / coordBias as in lighting.json lightmaps; scales_w = the '
                               '4th scale component (1 on all checked); atlas_rects_px = coordBias * size, coordScale * size',
               'stats': stats, 'interpolated_lightmaps': out}
        os.makedirs(os.path.join(ROOT, 'manifests', 'maps', 'transforming_actors'), exist_ok=True)
        json.dump(doc, open(os.path.join(ROOT, 'manifests', 'maps', 'transforming_actors', mp + '_interp_lightmaps.json'), 'w',
                            encoding='utf-8'), indent=1)
        print(mp, json.dumps(stats))

if __name__ == '__main__':
    main()
