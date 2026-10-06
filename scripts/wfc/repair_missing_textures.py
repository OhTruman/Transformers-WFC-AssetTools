"""Export cooked Texture2D objects that map / character / weapon materials reference but the bulk extraction never produced,
and register them in the extraction indexes -> manifests/audit/repaired_textures.json

  python repair_missing_textures.py            (targets = every Texture2D with no file in any Maps/*/materials_authored.json)

Why: the bulk extraction exported each object once, from its asset-index owner package; a few small ENV_AllShader_p textures
(Pixel_4_NORM: 862 map-material references, Pixel_4_Mask, Pixel_4_NORM_DXT1, Crackle_1_NORM, ...) never produced a file, so
floors render without normal / mask maps. Each is exported with the same umodel invocation as extract.py (-uncook -groups
-nooverwrite -png) from a cooked package that contains it, into the canonical content/<pkg>/<group>/<name>.png path, then
appended to manifests/extracted/textures.jsonl and manifests/assets.json "extracted" (both local extraction indexes) so
materials.tex_file / vs_materials.tex_file resolve them. Nothing is duplicated; existing files are never overwritten.
"""
import glob, json, os, sys, time
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract, objtree  # noqa: E402
from vs_common import ROOT, VS  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MANI = os.path.join(AT, 'manifests')

def targets():
    c = Counter()
    for f in glob.glob(os.path.join(VS, 'Maps', '*', 'materials_authored.json')):
        for v in (json.load(open(f, encoding='utf-8')).get('materials') or {}).values():
            for x in (v.get('textures') or {}).values():
                if isinstance(x, dict) and x.get('class') == 'Texture2D' and not x.get('file') and x.get('texture'):
                    c[x['texture']] += 1
    return c

def main():
    tg = targets()
    inv = objtree.inv()
    by_pkg = {}
    for t in tg:
        r = inv.execute('SELECT package FROM exports WHERE opath = ? ORDER BY serial_size DESC, package', (t,)).fetchall()
        if r: by_pkg.setdefault(r[0][0], []).append(t)
    recs, results = [], OrderedDict()
    for pkg, ts in sorted(by_pkg.items()):
        r = extract.run_umodel('textures', pkg, [(t, 'Texture2D', t.rsplit('.', 1)[-1]) for t in ts])
        recs += [x for x in r['records'] if x.get('object_path')]
        for t in ts:
            out = next((x['output'] for x in r['records'] if x.get('object_path') == t), None)
            p = 'content/' + t.replace('.', '/') + '.png'
            results[t] = {'references': tg[t], 'package': pkg, 'output': out or (p if os.path.exists(os.path.join(ROOT, p)) else None)}
    # register in the local extraction indexes
    jl = os.path.join(MANI, 'extracted', 'textures.jsonl')
    have = set()
    for l in open(jl, encoding='utf-8'):
        try: have.add(json.loads(l)['object_path'])
        except Exception: pass
    with open(jl, 'a', encoding='utf-8') as f:
        for t, x in results.items():
            if x['output'] and t not in have:
                f.write(json.dumps({'phase': 'textures', 'source_package': x['package'], 'object_path': t, 'class': 'Texture2D',
                                    'name': t.rsplit('.', 1)[-1], 'output': x['output'], 'requested': True,
                                    'note': 'repair_missing_textures.py'}) + '\n')
    aj = os.path.join(MANI, 'assets.json')
    A = json.load(open(aj, encoding='utf-8'))
    n = 0
    for a in A['assets']:
        x = results.get(a['object_path'])
        if x and x['output'] and x['output'] not in (a.get('extracted') or []):
            a['extracted'] = (a.get('extracted') or []) + [x['output']]; n += 1
    if n: json.dump(A, open(aj, 'w', encoding='utf-8'))
    out = OrderedDict([('generated_by', 'AssetTools/scripts/wfc/repair_missing_textures.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
                       ('textures', results), ('assets_json_entries_updated', n)])
    json.dump(out, open(os.path.join(MANI, 'audit', 'repaired_textures.json'), 'w', encoding='utf-8'), indent=1)
    for t, x in results.items(): print(t, x)

if __name__ == '__main__':
    main()
