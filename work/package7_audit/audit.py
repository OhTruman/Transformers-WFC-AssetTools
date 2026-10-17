"""Package 7 slim-list audit (Integration 2026-10-18; read-only, the tsv is NOT regenerated: Systems owns the package step).

Inputs:
  AssetTools/out/package/slim_files.tsv (Oct 11; dest, source, bytes, action, reason)
  the newest WFC_FILELOG set: Rebuild-Systems/work/verify_af4d0731/{Streets,Gorge,Debris,hd_runtime/Streets}/filelog.txt
  ('r ok <abs path>' = a file the game opened)
Method:
  opened paths -> relative to F:/Transformers Rebuild; a verify run's private bin copy (.../verify_*/<map>/bin/X) -> the package bin
  tree. Paths naming one of the 3 logged maps are generalised to all 10 MP maps (the same loader reads the same per-map file names)
  and kept when the file exists. Reports: opened files absent from the tsv (or present but dropped), tsv rows whose source no longer
  exists, tsv rows whose size changed, and the explicit new loads Integration listed (checked on disk, as the logs predate them).
  python audit.py -> PACKAGE7_SLIM_AUDIT.json (+ the doc is written by hand from it)
"""
import json, os, re, glob
from collections import Counter, defaultdict

R = r'F:\Transformers Rebuild'; HERE = os.path.dirname(os.path.abspath(__file__))
TSV = os.path.join(R, 'AssetTools', 'out', 'package', 'slim_files.tsv')
LOGS = sorted(glob.glob(os.path.join(R, 'Rebuild-Systems', 'work', 'verify_af4d0731', '*', 'filelog.txt')) +
              glob.glob(os.path.join(R, 'Rebuild-Systems', 'work', 'verify_af4d0731', 'hd_runtime', '*', 'filelog.txt')))
MAPS = ['MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_IAC_Streets', 'MP_KON_Molten',
        'MP_ORB_Debris', 'MP_UND_Complex', 'MP_UND_Gorge']
LOGGED = {'MP_IAC_Streets', 'MP_UND_Gorge', 'MP_ORB_Debris'}

def norm(p): return p.replace('\\', '/')

rows = {}; header = None
for line in open(TSV, encoding='utf-8'):
    f = line.rstrip('\n').split('\t')
    if header is None: header = f; continue
    if len(f) < 4: continue
    rows[norm(f[1])] = {'dest': f[0], 'bytes': int(f[2]) if f[2].isdigit() else None, 'action': f[3], 'reason': f[4] if len(f) > 4 else ''}
bin_src = Counter(s.rsplit('/', 1)[0] for s in rows if '/bin/' in s and s.startswith('Rebuild/build/'))
BIN = bin_src.most_common(1)[0][0] if bin_src else 'Rebuild/build/release/bin'

opened = set(); runtime_artifacts = set()
pre = norm(R) + '/'
for lg in LOGS:
    for line in open(lg, encoding='utf-8', errors='replace'):
        if not line.startswith('r ok '): continue
        p = norm(line[5:].strip())
        mm = re.match(r'^[A-Za-z]:/Transformers Rebuild/(.*)$', p)      # runs map the tree to X: (Play.bat subst) or F:
        if not mm: continue
        rel = mm.group(1)
        if rel.endswith('.xpr'): rel = rel[:-4]          # the package stores tsv action 'xpr' rows compressed as <name>.xpr
        m = re.match(r'Rebuild-Systems/work/verify_[^/]+/(?:hd_runtime/)?[^/]+/(bin|cwd)/(.*)$', rel)
        if m:
            if m.group(1) == 'cwd': runtime_artifacts.add(m.group(2)); continue
            rel = BIN + '/' + m.group(2)
        opened.add(rel)
# generalise per-map paths to all 10 maps
expected = set()
for rel in opened:
    hit = next((mp for mp in LOGGED if mp in rel), None)
    if not hit: expected.add(rel); continue
    for mp in MAPS:
        q = rel.replace(hit, mp)
        if os.path.exists(os.path.join(R, q)): expected.add(q)
keep = {s for s, r in rows.items() if r['action'] in ('keep', 'xpr')}
# shipped beside the tsv by build_slim (Systems' build_slim.json): the HD pack (base D + M6 hd_pbr overlay) and the glTF overlay
SIDE = ('AssetTools/out/hd/',)
side = sorted(x for x in expected if x not in rows and x.startswith(SIDE))
missing = sorted(x for x in expected if x not in rows and not x.startswith(SIDE))
dropped_but_opened = sorted(x for x in expected if x in rows and rows[x]['action'] not in ('keep', 'xpr'))
stale, drift = [], []
for s, r in rows.items():
    if r['action'] not in ('keep', 'xpr'): continue
    fp = os.path.join(R, s)
    if not os.path.exists(fp): stale.append({'source': s, 'bytes': r['bytes']}); continue
    sz = os.path.getsize(fp)
    if r['bytes'] is not None and sz != r['bytes']: drift.append({'source': s, 'tsv_bytes': r['bytes'], 'now_bytes': sz})
# explicit new loads named by Integration (logs predate several of them)
EXPLICIT = ['AssetTools/manifests/maps/%s/collision_weapon_physmat.json' % m for m in MAPS] + \
           ['Rebuild/work/render/%s/%s' % (m, f) for m in MAPS for f in ('map_fx_runtime.json', 'materials_glsl.json', 'lighting.json')]
for pat in ('AssetTools/manifests/frontend*/**/*objectives*', 'AssetTools/manifests/**/pc_strings.int', 'AssetTools/manifests/**/mp_characters.json',
            'AssetTools/out/hd/**/hd_pbr_index.json', 'Rebuild/work/render/**/hd_pbr_index.json'):
    EXPLICIT += [norm(os.path.relpath(x, R)) for x in glob.glob(os.path.join(R, pat), recursive=True)]
explicit = [{'path': p, 'exists': os.path.exists(os.path.join(R, p)), 'in_tsv': p in rows,
             'tsv_action': (rows.get(p) or {}).get('action'), 'size_now': os.path.getsize(os.path.join(R, p)) if os.path.exists(os.path.join(R, p)) else None,
             'tsv_bytes': (rows.get(p) or {}).get('bytes')} for p in sorted(set(EXPLICIT))]
by_root = lambda xs: dict(Counter('/'.join(x.split('/')[:3]) for x in xs).most_common(20))
size = lambda xs: sum(os.path.getsize(os.path.join(R, x)) for x in xs if os.path.exists(os.path.join(R, x)))
rep = {'generated_by': 'AssetTools/work/package7_audit/audit.py', 'tsv': 'AssetTools/out/package/slim_files.tsv', 'tsv_rows': len(rows),
       'tsv_keep_rows': len(keep), 'tsv_keep_bytes': sum(r['bytes'] or 0 for s, r in rows.items() if s in keep),
       'filelogs': [norm(os.path.relpath(x, R)) for x in LOGS], 'bin_tree': BIN,
       'opened_files': len(opened), 'expected_after_10_map_generalisation': len(expected),
       'shipped_beside_tsv_hd_pack': {'count': len(side), 'note': 'HD pack D + M6 hd_pbr overlay, shipped by build_slim from its own sources'},
       'missing_from_tsv': {'count': len(missing), 'bytes': size(missing), 'by_root': by_root(missing), 'files': missing},
       'opened_but_dropped_in_tsv': {'count': len(dropped_but_opened), 'files': dropped_but_opened},
       'tsv_rows_source_gone': {'count': len(stale), 'bytes_in_tsv': sum(x['bytes'] or 0 for x in stale), 'by_root': by_root([x['source'] for x in stale]), 'files': stale},
       'tsv_rows_size_changed': {'count': len(drift), 'delta_bytes': sum(x['now_bytes'] - (x['tsv_bytes'] or 0) for x in drift),
                                 'by_root': by_root([x['source'] for x in drift]), 'files': drift},
       'explicit_new_loads': explicit}
json.dump(rep, open(os.path.join(HERE, 'PACKAGE7_SLIM_AUDIT.json'), 'w', encoding='utf-8'), indent=1)
print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'files'}) for k, v in rep.items() if k != 'explicit_new_loads'}, indent=1)[:3500])
print('explicit:', [(e['path'][-60:], e['exists'], e['in_tsv'], e['tsv_bytes'] == e['size_now']) for e in explicit if not e['in_tsv'] or e['tsv_bytes'] != e['size_now']][:40])
