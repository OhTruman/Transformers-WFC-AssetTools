"""Playtest 2026-10-23 #4: what HD content package 6 (Rebuild-Systems/work/playtest_slim) carries. Read-only."""
import json, os
HD = r'F:\Transformers Rebuild\Rebuild-Systems\work\playtest_slim\Transformers Rebuild\AssetTools\out\hd'

def paths(r):
    if isinstance(r, dict):
        for v in r.values(): yield from paths(v)
    elif isinstance(r, list):
        for x in r: yield from paths(x)
    elif isinstance(r, str) and r.lower().endswith(('.dds', '.png')): yield r

for name in ('hd_pbr_index.json', 'hd_index.json'):
    d = json.load(open(os.path.join(HD, name), encoding='utf-8'))
    top = list(d.keys())[:10] if isinstance(d, dict) else type(d).__name__
    refs = list(paths(d)); miss = []
    for p in refs:
        q = p.replace(chr(92), '/')
        rel = q.split('out/hd/')[-1]
        if not (os.path.exists(os.path.join(HD, rel)) or os.path.exists(os.path.join(HD, q))): miss.append(rel)
    print(name, 'top keys', top, '| file refs', len(refs), '| missing in package', len(miss), miss[:5])
