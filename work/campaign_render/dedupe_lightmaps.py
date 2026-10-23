"""One lightmap set per chapter (Systems / Integration 2026-10-23): Rendering's build_lighting copies every LightMapTexture2D PNG of the
chapter-wide umodel export into EACH unit's lightmaps/ (A1: 48 units x 1,050 identical files = 2.2 GB). This post-pass writes the files once
to out/campaign_render/<CH>/lightmaps/ (+ index.json: per unit the atlases its lighting.json uses, per file its sha256).
A NAME CONFLICT (one name, different bytes in different units: A2 has 30, LightMapTexture2D_<n> names collide across the chapter's sublevel
packages in the shared umodel dir) is never put in the chapter set: every unit keeps its own copy of that name, so the loader (chapter set
first, then the unit's) samples exactly what the unit sampled before. A name several level packages export with different bytes is
treated the same way, and each unit using it gets ITS OWN package's page (_umodel/<level>[_LM]): build_lighting copied by file name only,
so some units sampled another package's page (D5 1, A1 27 found 2026-10-23). Two passes: scan everything, then copy / remove.
  python dedupe_lightmaps.py <CH>                       write <CH>/lightmaps/ + index.json (additive, unit copies untouched)
  python dedupe_lightmaps.py <CH> --remove-unit-copies  also delete each unit's copies of conflict-free names (byte-identical to the chapter's)
  python dedupe_lightmaps.py <CH> --repair-conflicts    (A2 2026-10-23, after a first version that removed the first-seen copy of a
                                                        conflicting name): restore that version from the chapter set into every unit whose
                                                        lighting.json atlases use the name and that has no copy, then drop it from the set
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

def atlases(R, u):
    lj = os.path.join(R, u, 'lighting.json')
    return (json.load(open(lj, encoding='utf-8')).get('lightmaps') or {}).get('atlases') or [] if os.path.exists(lj) else []

def main(ch, remove=False, repair=False):
    R = os.path.join(CR.OUTR, ch); C = os.path.join(R, 'lightmaps'); os.makedirs(C, exist_ok=True)
    units = [u for u in sorted(os.listdir(R)) if os.path.isdir(os.path.join(R, u)) and not u.startswith('_') and u != 'lightmaps'
             and os.path.exists(os.path.join(R, u, 'lighting.json'))]
    old = json.load(open(os.path.join(C, 'index.json'), encoding='utf-8')) if os.path.exists(os.path.join(C, 'index.json')) else {}
    restored = []
    if repair:
        for n in (old.get('conflicts (unit keeps its own copy)') or {}):
            src = os.path.join(C, n)
            if not os.path.exists(src): continue
            for u in units:
                d = os.path.join(R, u, 'lightmaps'); p = os.path.join(d, n)
                if n[:-4] in atlases(R, u) and not os.path.exists(p):
                    os.makedirs(d, exist_ok=True); shutil.copyfile(src, p); restored.append((n, u))
    # package-correct pages: a name several packages export with DIFFERENT bytes (LightMapTexture2D_<n> collide across a chapter's levels;
    # build_lighting copies by file name, so the last-walked package's page reached every unit) -> each unit whose lighting.json uses it
    # gets ITS OWN level package's export (_umodel/<level>[_LM]/LightMapTexture2D/<name>) as a unit copy; the name stays out of the set
    UM = os.path.join(R, '_umodel'); pkgver = defaultdict(dict)
    for pk in sorted(os.listdir(UM)) if os.path.isdir(UM) else []:
        d = os.path.join(UM, pk, 'LightMapTexture2D')
        for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            pkgver[n].setdefault(pk[:-3] if pk.endswith('_LM') else pk, os.path.join(d, n))
    multi = {n: v for n, v in pkgver.items() if len({sha(p) for p in v.values()}) > 1}
    fixed = []
    for u in units:
        for a in atlases(R, u):
            n = a + '.png'; srcp = (multi.get(n) or {}).get(u + '_m')
            if not srcp: continue
            d = os.path.join(R, u, 'lightmaps'); p = os.path.join(d, n)
            if not (os.path.exists(p) and sha(p) == sha(srcp)):
                os.makedirs(d, exist_ok=True); shutil.copyfile(srcp, p); fixed.append((u, n))
    # pass 1: every unit file's hash
    hashes, nfiles, nbytes = defaultdict(dict), 0, 0
    for u in units:
        d = os.path.join(R, u, 'lightmaps')
        for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            p = os.path.join(d, n)
            if os.path.isfile(p): hashes[n][u] = sha(p); nfiles += 1; nbytes += os.path.getsize(p)
    # names only in the chapter set (unit copies already removed): their recorded hash
    for n, h in (old.get('files') or {}).items():
        if n not in hashes and os.path.exists(os.path.join(C, n)): hashes[n]['<chapter>'] = h
    conflicts = {n: sorted(hu) for n, hu in hashes.items() if len(set(hu.values())) > 1 or n in multi}
    # pass 2: chapter set = conflict-free names; conflicting names are removed from the set (units keep theirs)
    files = OD()
    for n in sorted(hashes):
        cp = os.path.join(C, n)
        if n in conflicts:
            if os.path.exists(cp): os.remove(cp)
            continue
        h = next(iter(hashes[n].values())); files[n] = h
        if not (os.path.exists(cp) and sha(cp) == h):
            u = next(x for x in hashes[n] if x != '<chapter>'); shutil.copyfile(os.path.join(R, u, 'lightmaps', n), cp)
    removed = 0
    if remove:
        for u in units:
            d = os.path.join(R, u, 'lightmaps')
            if not os.path.isdir(d): continue
            for n in sorted(os.listdir(d)):
                if n in files and hashes[n].get(u) == files[n]: os.remove(os.path.join(d, n)); removed += 1
            if not os.listdir(d): os.rmdir(d)
    per_unit = OD()
    for u in units:
        a = atlases(R, u); d = os.path.join(R, u, 'lightmaps')
        own = set(os.listdir(d)) if os.path.isdir(d) else set()
        per_unit[u] = OD([('atlases', a), ('own_copies', sorted(own)),
                          ('atlases_unresolved', sorted(x for x in a if x + '.png' not in files and x + '.png' not in own))])
    idx = OD([('chapter', ch), ('generated_by', 'AssetTools/work/campaign_render/dedupe_lightmaps.py'),
              ('rule', 'conflict-free pages once at <chapter>/lightmaps/<name>.png; a conflicting name stays only in the units (own_copies), '
                       'so chapter-first-then-unit loading samples what each unit sampled before'),
              ('counts', OD([('units', len(units)), ('unit_files_scanned', nfiles), ('unit_bytes_scanned', nbytes), ('chapter_files', len(files)),
                             ('chapter_bytes', sum(os.path.getsize(os.path.join(C, n)) for n in files)), ('name_conflicts', len(conflicts)),
                             ('unit_copies_removed', removed), ('restored_by_repair', len(restored)),
                             ('names_exported_by_several_packages_differently', len(multi)), ('unit_pages_set_to_own_package', len(fixed)),
                             ('atlases_unresolved', sum(len(v['atlases_unresolved']) for v in per_unit.values()))])),
              ('conflicts (unit keeps its own copy)', conflicts), ('repair_restored', restored), ('set_to_own_package', fixed), ('units', per_unit), ('files', files)])
    json.dump(idx, open(os.path.join(C, 'index.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(idx['counts']))

if __name__ == '__main__':
    main(sys.argv[1], '--remove-unit-copies' in sys.argv[2:], '--repair-conflicts' in sys.argv[2:])
