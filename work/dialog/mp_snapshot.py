"""MP no-change gate for the dialog export: SHA-256 of the MP / top-level manifests, size + mtime of ExtractedAssets MP map files.
python mp_snapshot.py before|after   -> work/dialog/mp_snapshot_<tag>.json; 'after' also writes work/dialog/mp_gate.json"""
import os, hashlib, json, glob, sys
AT = r'F:\Transformers Rebuild\AssetTools'; EA = r'F:\Transformers Rebuild\ExtractedAssets\VerticalSlice\Maps'
snap = {'manifests': {}, 'extracted': {}}
for f in glob.glob(AT + r'\manifests\maps\MP_*\*') + glob.glob(AT + r'\manifests\next_map\MP_*') + glob.glob(AT + r'\manifests\*.json'):
    if os.path.isfile(f): snap['manifests'][os.path.relpath(f, AT)] = hashlib.sha256(open(f, 'rb').read()).hexdigest()
for d in glob.glob(EA + r'\MP_*'):
    for root, _, fs in os.walk(d):
        for x in fs:
            p = os.path.join(root, x); st = os.stat(p); snap['extracted'][os.path.relpath(p, EA)] = [st.st_size, int(st.st_mtime)]
tag = sys.argv[1]; json.dump(snap, open(AT + r'\work\dialog\mp_snapshot_%s.json' % tag, 'w'), indent=0)
if tag == 'after':
    b = json.load(open(AT + r'\work\dialog\mp_snapshot_before.json'))
    diff = {k: sorted(f for f in set(b[k]) | set(snap[k]) if b[k].get(f) != snap[k].get(f)) for k in b}
    res = {'identical': not any(diff.values()), 'files_compared': {k: len(snap[k]) for k in snap}, 'differences': diff}
    json.dump(res, open(AT + r'\work\dialog\mp_gate.json', 'w'), indent=1); print(res['identical'], res['files_compared'])
else: print('snapshot', {k: len(v) for k, v in snap.items()})
