"""extras.wfc_material for skeletal-mesh glTFs (Integration 2026-10-14/16): the umodel exports name each glTF material only by its
object NAME (e.g. "WEP_Barrier_Defrag_MATINST"), so the game could not find the original material and drew the opaque glTF
fallback. This writes extras.wfc_material = the material's full object path into each material, resolved from the authored DB.

Output: AssetTools/work/gltf_wfcmat/<same relative path>.gltf, the .gltf JSON only (buffer uris unchanged: the file is meant to
replace the ExtractedAssets .gltf next to its existing .bin; ExtractedAssets is not written here, install goes through Integration).
Every output is checked: identical to the source except materials[i].extras.

Resolution (per glTF material name): authored objects of material classes with that name; one candidate -> it; several -> the
one in the mesh's own package, else the one flagged bUsedWithSkeletalMesh, else unresolved (listed, left without extras).

  python gltf_wfcmat.py run [prefixes]   default prefixes WEP_,PROP_ (top-level content folder)
  python gltf_wfcmat.py audit            weapon / prop mesh materials that no map's materials_glsl.json compiles -> report for Rendering
"""
import copy, glob, json, os, sys
from collections import OrderedDict as OD, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
AT = os.path.dirname(os.path.dirname(HERE)); REB = os.path.dirname(AT); EA = os.path.join(REB, 'ExtractedAssets')
OUT = os.path.join(AT, 'work', 'gltf_wfcmat')
MAT_CLASSES = ('Material', 'MaterialInstanceConstant', 'MaterialInstanceTimeVarying')

def mesh_rows(prefixes):
    seen = set()
    for l in open(os.path.join(AT, 'manifests', 'extracted', 'skeletal_meshes.jsonl'), encoding='utf-8'):
        r = json.loads(l)
        if not r.get('object_path') or not r['output'].endswith('.gltf') or r['output'] in seen: continue
        top = r['output'].split('/')[1]
        if prefixes and not top.upper().startswith(prefixes): continue
        seen.add(r['output']); yield r

def resolver():
    import authored as A
    by = defaultdict(list)
    for c in MAT_CLASSES:
        for o in A.find('%', c): by[o['opath'].rsplit('.', 1)[-1].lower()].append(o)
    def resolve(name, mesh_path):
        c = by.get((name or '').lower(), [])
        if len(c) == 1: return c[0]['opath'], 'unique'
        if not c: return None, 'unknown'
        pkg = mesh_path.split('.')[0].lower()
        same = [o for o in c if o['opath'].split('.')[0].lower() == pkg]
        if len(same) == 1: return same[0]['opath'], 'mesh package'
        sk = [o for o in c if any(b.get('PropertyName') == 'bUsedWithSkeletalMesh' and b.get('PropertyValue')
                                  for b in (o.get('props') or {}).get('BoolPropertyValues') or [])]
        if len(sk) == 1: return sk[0]['opath'], 'bUsedWithSkeletalMesh'
        return None, 'ambiguous: ' + ', '.join(sorted(o['opath'] for o in c)[:4])
    return resolve

def strip(g):
    g = copy.deepcopy(g)
    for m in g.get('materials', []):
        if 'extras' in m:
            m['extras'].pop('wfc_material', None)
            if not m['extras']: m.pop('extras')
    return g

def run(prefixes=('WEP_', 'PROP_')):
    resolve = resolver(); report = OD([('generated_by', 'scripts/wfc/gltf_wfcmat.py'), ('meshes', [])]); n = ok = unres = 0
    for r in mesh_rows(prefixes):
        src = os.path.join(EA, r['output'])
        if not os.path.exists(src): continue
        g = json.load(open(src, encoding='utf-8')); g0 = copy.deepcopy(g); mats = []
        for m in g.get('materials', []):
            op, how = resolve(m.get('name'), r['object_path']); n += 1
            if op: m.setdefault('extras', {})['wfc_material'] = op; ok += 1
            else: unres += 1
            mats.append(OD([('name', m.get('name')), ('wfc_material', op), ('how', how)]))
        assert strip(g) == strip(g0), r['output']               # only materials[i].extras changed
        dst = os.path.join(OUT, r['output']); os.makedirs(os.path.dirname(dst), exist_ok=True)
        json.dump(g, open(dst, 'w', encoding='utf-8'), indent=2)
        assert strip(json.load(open(dst, encoding='utf-8'))) == strip(g0), dst
        report['meshes'].append(OD([('gltf', r['output']), ('mesh', r['object_path']), ('materials', mats)]))
    report['totals'] = OD([('meshes', len(report['meshes'])), ('materials', n), ('resolved', ok), ('unresolved', unres)])
    json.dump(report, open(os.path.join(OUT, 'wfcmat_report.json'), 'w', encoding='utf-8'), indent=1)
    print(report['totals'], flush=True)

def audit():
    rep = json.load(open(os.path.join(OUT, 'wfcmat_report.json'), encoding='utf-8'))
    compiled = set()
    for f in glob.glob(os.path.join(REB, 'Rebuild-Rendering', '**', 'materials_glsl.json'), recursive=True):
        try:
            d = json.load(open(f, encoding='utf-8')); compiled |= {k.lower() for k in (d.get('materials') if isinstance(d.get('materials'), dict) else d)}
        except Exception: pass
    for f in glob.glob(os.path.join(EA, 'VerticalSlice', 'Maps', '*', 'materials.json')):
        compiled |= {k.lower() for k in json.load(open(f, encoding='utf-8'))}
    miss = OD()
    for m in rep['meshes']:
        for x in m['materials']:
            if x['wfc_material'] and x['wfc_material'].lower() not in compiled: miss.setdefault(x['wfc_material'], []).append(m['mesh'])
    out = OD([('generated_by', 'scripts/wfc/gltf_wfcmat.py audit'), ('compiled_sources', 'Rebuild-Rendering/**/materials_glsl.json + '
              'ExtractedAssets VerticalSlice map materials.json (%d material keys)' % len(compiled)),
              ('missing', [OD([('material', k), ('meshes', v)]) for k, v in sorted(miss.items())])])
    json.dump(out, open(os.path.join(OUT, 'missing_matinst_audit.json'), 'w', encoding='utf-8'), indent=1)
    print(len(miss), 'weapon / prop materials not compiled anywhere;', len(compiled), 'compiled keys seen', flush=True)

if __name__ == '__main__':
    a = sys.argv[1] if len(sys.argv) > 1 else 'run'
    if a == 'run': run(tuple(p.upper() for p in sys.argv[2].split(',')) if len(sys.argv) > 2 else ('WEP_', 'PROP_'))
    elif a == 'audit': audit()
