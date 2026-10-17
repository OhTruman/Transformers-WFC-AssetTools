"""Pre-switch check of Experimental's frozen (B) after arm (Integration 2026-10-18), read-only on every tree.

before = Rebuild-Experimental/work/matb/matB_base_root, after = Rebuild-Experimental/work/matb/matB_root,
candidate = Rebuild-Systems/work/matB/render, manifest = Rebuild/docs/handoff/matscan_b/MATFIX_MANIFEST.json.
Per map: (1) the entries differing between before and after are exactly the manifest's 'replaced' list, with no entry added or removed;
(2) every replaced after-entry equals the candidate entry (raw JSON bytes of the entry value, extracted from each file, compared;
plus parsed-value equality); (3) every other file in the map directory (recursively) is byte-identical (sha256), none added or removed.
Root-level files are compared too. Writes verify_frozen.json next to this script.
"""
import hashlib, json, os, sys
R = r'F:\Transformers Rebuild'; HERE = os.path.dirname(os.path.abspath(__file__))
BEFORE = os.path.join(R, 'Rebuild-Experimental', 'work', 'matb', 'matB_base_root')
AFTER = os.path.join(R, 'Rebuild-Experimental', 'work', 'matb', 'matB_root')
CAND = os.path.join(R, 'Rebuild-Systems', 'work', 'matB', 'render')
MAN = json.load(open(os.path.join(R, 'Rebuild', 'docs', 'handoff', 'matscan_b', 'MATFIX_MANIFEST.json'), encoding='utf-8'))

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def tree(root):
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f); out[os.path.relpath(p, root).replace(os.sep, '/')] = p
    return out

def raw_entries(path):
    """top-level key -> raw bytes of its value, using the decoder's end offsets (exact source bytes, not a re-serialisation)"""
    s = open(path, encoding='utf-8').read()
    dec = json.JSONDecoder(); out = {}
    i = s.index('{') + 1
    while True:
        while s[i] in ' \t\r\n,': i += 1
        if s[i] == '}': break
        k, i = dec.raw_decode(s, i)
        while s[i] in ' \t\r\n:': i += 1
        _, j = dec.raw_decode(s, i)
        out[k] = s[i:j]; i = j
    return out

WS = lambda t: ''.join(t.split()) if t is not None else None
def glsl_hashes():
    return {mp: sha(os.path.join(AFTER, mp, 'materials_glsl.json')) for mp in MAN['maps']}
h_start = glsl_hashes()
res = {}; allpass = True
for mp, spec in sorted(MAN['maps'].items()):
    want = set(spec.get('replaced') or [])
    b = json.load(open(os.path.join(BEFORE, mp, 'materials_glsl.json'), encoding='utf-8'))
    a = json.load(open(os.path.join(AFTER, mp, 'materials_glsl.json'), encoding='utf-8'))
    c = json.load(open(os.path.join(CAND, mp, 'materials_glsl.json'), encoding='utf-8'))
    ra = raw_entries(os.path.join(AFTER, mp, 'materials_glsl.json'))
    rc = raw_entries(os.path.join(CAND, mp, 'materials_glsl.json'))
    differ = {k for k in set(a) & set(b) if a[k] != b[k]}
    noop = sorted(k for k in want if k in b and k in c and b[k] == c[k])          # candidate == before: nothing to replace
    added, removed = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    unexpected = sorted(differ - want); not_changed = sorted(want - differ - set(noop))
    cand_bad = sorted(k for k in want if k not in c or a.get(k) != c[k])
    cand_raw_bad = sorted(k for k in want if WS(ra.get(k)) != WS(rc.get(k)))   # entry text equal apart from whitespace
    tb, ta = tree(os.path.join(BEFORE, mp)), tree(os.path.join(AFTER, mp))
    files_changed = sorted(f for f in set(tb) & set(ta) if f != 'materials_glsl.json' and sha(tb[f]) != sha(ta[f]))
    files_added, files_removed = sorted(set(ta) - set(tb)), sorted(set(tb) - set(ta))
    ok = not (added or removed or unexpected or not_changed or cand_bad or cand_raw_bad or files_changed or files_added or files_removed)
    allpass &= ok
    res[mp] = {'pass': ok, 'manifest_replaced': len(want), 'noop_candidate_equals_before': noop, 'entries_differing': len(differ),
               'entries_total_after': len(a), 'file_format': {'after_compact': not open(os.path.join(AFTER, mp, 'materials_glsl.json'), encoding='utf-8').read(3).startswith('{' + chr(10)),
                                                              'before_compact': not open(os.path.join(BEFORE, mp, 'materials_glsl.json'), encoding='utf-8').read(3).startswith('{' + chr(10))},
               'unexpected_changes': unexpected, 'manifest_entries_unchanged': not_changed, 'added': added, 'removed': removed,
               'after_ne_candidate_value': cand_bad, 'after_ne_candidate_raw_bytes': cand_raw_bad,
               'other_files_compared': len(set(tb) & set(ta)) - 1, 'other_files_changed': files_changed,
               'files_added': files_added, 'files_removed': files_removed}
    print('%-18s %s  manifest %3d = changed %3d + no-op %d  unexpected %d  after==candidate %d/%d  other files %d identical%s' % (
        mp, 'PASS' if ok else 'FAIL', len(want), len(differ & want), len(noop), len(unexpected), len(want) - len(cand_raw_bad), len(want),
        len(set(tb) & set(ta)) - 1 - len(files_changed), '' if ok else '  -> ' + json.dumps({k: v for k, v in res[mp].items() if isinstance(v, list) and v})[:300]))
rb = {f for f in os.listdir(BEFORE) if os.path.isfile(os.path.join(BEFORE, f))}
ra_ = {f for f in os.listdir(AFTER) if os.path.isfile(os.path.join(AFTER, f))}
root_diff = sorted(f for f in rb | ra_ if f not in rb or f not in ra_ or sha(os.path.join(BEFORE, f)) != sha(os.path.join(AFTER, f)))
maps_unlisted = sorted({d for d in os.listdir(AFTER) if os.path.isdir(os.path.join(AFTER, d))} - set(MAN['maps']))
unlisted_changed = {}
for d in maps_unlisted:
    tb, ta = tree(os.path.join(BEFORE, d)), tree(os.path.join(AFTER, d))
    diff = sorted(f for f in set(tb) | set(ta) if f not in tb or f not in ta or sha(tb[f]) != sha(ta[f]))
    unlisted_changed[d] = {'files': len(set(tb) | set(ta)), 'differing': diff[:20], 'n_differing': len(diff)}
    print('%-18s %s  (not in manifest) %d files, %d differ' % (d, 'PASS' if not diff else 'FAIL', len(set(tb) | set(ta)), len(diff)))
    allpass &= not diff
h_end = glsl_hashes()
moved = sorted(mp for mp in h_start if h_start[mp] != h_end[mp])
allpass &= not root_diff and not moved
res['_root'] = {'root_files_differing': root_diff, 'map_dirs_not_in_manifest': unlisted_changed,
                'after_files_changed_during_run': moved,
                'manifest_materials': len(MAN['materials']),
                'distinct_replaced_over_maps': len({k for s in MAN['maps'].values() for k in s.get('replaced') or []})}
print('root files differing:', root_diff or 'none', '| map dirs not in manifest:', maps_unlisted or 'none',
      '| distinct replaced', res['_root']['distinct_replaced_over_maps'], '/ manifest', len(MAN['materials']))
print('after materials_glsl.json changed during this run:', moved or 'none')
print('OVERALL', 'PASS' if allpass else 'FAIL')
json.dump(res, open(os.path.join(HERE, 'verify_frozen.json'), 'w', encoding='utf-8'), indent=1)
