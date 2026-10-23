"""Per-sublevel gap list of campaign render data (out/campaign_render/<CH>): world.glb materials not in materials_glsl.json, compile errors,
texture files missing, lights / fogs / fog volumes, and the 'materials missing from this map' line of the materials step log."""
import json, os, re, struct, sys
AT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
def glbj(p):
    with open(p, 'rb') as f: f.read(12); n, _ = struct.unpack('<II', f.read(8)); return json.loads(f.read(n))
ch = sys.argv[1]; R = os.path.join(AT, 'out', 'campaign_render', ch); out = {}
for sub in sorted(d for d in os.listdir(R) if os.path.isdir(os.path.join(R, d)) and not d.startswith('_')):
    od = os.path.join(R, sub); g = {}
    w = {(m.get('extras') or {}).get('wfc_material') for m in glbj(os.path.join(od, 'world.glb')).get('materials') or []} - {None}
    m = json.load(open(os.path.join(od, 'materials_glsl.json'), encoding='utf-8')) if os.path.exists(os.path.join(od, 'materials_glsl.json')) else {}
    g['world_materials'] = len(w); g['compiled'] = len(m)
    g['world_not_compiled'] = sorted(w - set(m)); g['compile_errors'] = sorted(k for k, v in m.items() if (v or {}).get('error'))
    g['texture_files_missing'] = sorted({t.get('object') for v in m.values() for t in ((v or {}).get('info') or {}).get('textures') or [] if t.get('file') and not os.path.exists(t['file'])} - {None})
    lg = open(os.path.join(od, '_status', 'materials.log'), encoding='utf-8', errors='replace').read() if os.path.exists(os.path.join(od, '_status', 'materials.log')) else ''
    mm = re.findall(r'materials missing from this map: (\d+)', lg); g['missing_line'] = int(mm[-1]) if mm else None
    if os.path.exists(os.path.join(od, 'lighting.json')):
        l = json.load(open(os.path.join(od, 'lighting.json'), encoding='utf-8'))
        g.update(lights=len(l.get('lights') or []), fogs=len(l.get('fogs') or []), component_flags=len(l.get('component_flags') or {}))
    fv = os.path.join(od, 'fog_volumes.json')
    g['fog_volumes'] = len((json.load(open(fv, encoding='utf-8')) or {}).get('volumes') or []) if os.path.exists(fv) and os.path.getsize(fv) > 2 else 0
    out[sub] = g
json.dump(out, open(os.path.join(R, 'gaps.json'), 'w', encoding='utf-8'), indent=1)
for s, g in out.items():
    print('%-28s world mats %4d compiled %4d not-compiled %3d errors %d tex-missing %d missing-line %s lights %s fogs %s fogvol %s' % (
        s, g['world_materials'], g['compiled'], len(g['world_not_compiled']), len(g['compile_errors']), len(g['texture_files_missing']), g['missing_line'], g.get('lights'), g.get('fogs'), g['fog_volumes']))
print('errors', sorted({e for g in out.values() for e in g['compile_errors']}))
print('not compiled sample', sorted({e for g in out.values() for e in g['world_not_compiled']})[:8])
