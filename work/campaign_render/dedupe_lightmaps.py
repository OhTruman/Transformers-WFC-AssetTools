"""One lightmap set per chapter (Systems / Integration 2026-10-23): Rendering's build_lighting copies every LightMapTexture2D PNG of the
chapter-wide umodel export into EACH unit's lightmaps/ (A1: 48 units x 1,050 identical files = 2.2 GB). This post-pass writes the distinct
files once to out/campaign_render/<CH>/lightmaps/ (+ index.json: per unit the atlases its lighting.json uses, and per file its sha256),
after checking that a name never has two contents across units (if one did, that unit keeps its own copy, reported).
  python dedupe_lightmaps.py <CH>                       write <CH>/lightmaps/ + index.json (additive, unit copies untouched)
  python dedupe_lightmaps.py <CH> --remove-unit-copies  then delete each unit's lightmaps/ files that are byte-identical to the chapter copy
                                                        (only once the loader reads <chapter>/lightmaps/; Integration's go)
"""
import hashlib, json, os, shutil, sys
from collections import OrderedDict as OD, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import campaign_render as CR  # noqa: E402

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def main(ch, remove=False):
    R = os.path.join(CR.OUTR, ch); C = os.path.join(R, 'lightmaps'); os.makedirs(C, exist_ok=True)
    units = [u for u in sorted(os.listdir(R)) if os.path.isdir(os.path.join(R, u, 'lightmaps')) and u != 'lightmaps']
    seen, conflicts, per_unit, nfiles, nbytes = {}, defaultdict(set), OD(), 0, 0
    for u in units:
        d = os.path.join(R, u, 'lightmaps')
        for n in sorted(os.listdir(d)):
            p = os.path.join(d, n)
            if not os.path.isfile(p): continue
            h = sha(p); nfiles += 1; nbytes += os.path.getsize(p)
            if n not in seen:
                seen[n] = h
                if not (os.path.exists(os.path.join(C, n)) and sha(os.path.join(C, n)) == h): shutil.copyfile(p, os.path.join(C, n))
            elif seen[n] != h: conflicts[n].add(u)
        lj = os.path.join(R, u, 'lighting.json')
        atl = (json.load(open(lj, encoding='utf-8')).get('lightmaps') or {}).get('atlases') if os.path.exists(lj) else None
        per_unit[u] = OD([('atlases', atl), ('atlases_missing_in_chapter_set', sorted(a for a in atl or [] if a + '.png' not in seen))])
    removed = 0
    if remove:
        for u in units:
            d = os.path.join(R, u, 'lightmaps')
            for n in sorted(os.listdir(d)):
                p = os.path.join(d, n)
                if n in conflicts and u in conflicts[n]: continue
                if os.path.isfile(p) and seen.get(n) and sha(p) == seen[n]: os.remove(p); removed += 1
            if not os.listdir(d): os.rmdir(d)
    idx = OD([('chapter', ch), ('generated_by', 'AssetTools/work/campaign_render/dedupe_lightmaps.py'),
              ('rule', 'one copy per chapter at <chapter>/lightmaps/<name>.png; a unit\'s lighting.json lightmaps.atlases names the files it samples'),
              ('counts', OD([('units', len(units)), ('unit_files_scanned', nfiles), ('unit_bytes_scanned', nbytes), ('chapter_files', len(seen)),
                             ('chapter_bytes', sum(os.path.getsize(os.path.join(C, n)) for n in seen)), ('name_conflicts', len(conflicts)),
                             ('unit_copies_removed', removed)])),
              ('conflicts (unit keeps its own copy)', {n: sorted(u) for n, u in conflicts.items()}),
              ('units', per_unit), ('files', OD((n, seen[n]) for n in sorted(seen)))])
    json.dump(idx, open(os.path.join(C, 'index.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(idx['counts']))

if __name__ == '__main__':
    main(sys.argv[1], '--remove-unit-copies' in sys.argv[2:])
