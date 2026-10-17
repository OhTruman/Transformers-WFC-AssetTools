"""RE 2026-10-18 (CONFIRMED in both runners): each compiled module record carries its own float / vector distribution base index; the
runner reads distribution k of a module at base + k and never counts records. In the cooked LOD tail the 7 bytes before each 10-byte
record block are that record's prefix: u16 LE float base at +0, u16 LE vector base at +2 (record 0's prefix = tail[28:35]).

Regression over every distinct cooked ParticleLODLevel: assign by base index (owner = record, k = MODULE_DISTS order) and compare with
pstream's sequential assignment. Expect identical wherever the sequential one is complete; report every LOD where they differ and the
table entries no compiled record points at. Read-only; writes base_index_check.json here.
"""
import gc, json, os, sqlite3, struct, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'wfc'))
import objtree, pstream  # noqa: E402

def bases(t, pr):
    n = t[24]; i = 35; out = []
    for m in range(n):
        pre = t[i - 7:i]
        out.append((struct.unpack_from('<H', pre, 0)[0], struct.unpack_from('<H', pre, 2)[0]))
        i += 10 + (7 if m < n - 1 else 0)
    return out

def by_base(pr, bs):
    res = {}
    for g, key, gi in (('float', 'float_group', 0), ('vector', 'vector_group', 1)):
        tab = pr[key]; used = {}; bad = []
        for r, b in zip(pr['records'], bs):
            props = (pstream.MODULE_DISTS.get(r['module']) or pstream.ORDER_PROVISIONAL.get(r['module']) or ([], []))[gi]
            for k, prop in enumerate(props):
                j = b[gi] + k
                if j >= len(tab): bad.append((r['module'], prop, j)); continue
                used[j] = (r['index'], r['module'], prop)
        res[g] = {'owned': used, 'out_of_range': bad, 'unowned': [j for j in range(len(tab)) if j not in used]}
    return res

def main():
    inv = sqlite3.connect(os.path.join(ROOT, 'manifests', 'inventory.db'))
    pkgs = [r[0] for r in inv.execute("select distinct package from exports where class='ParticleLODLevel' order by package")]
    seen = set(); c = Counter(); diffs = []; unowned = []
    for name in pkgs:
        try: p = objtree.package(name)
        except Exception: continue
        for k, i in p._idx.items():
            if k in seen or p.class_name(p.exports[i - 1]) != 'ParticleLODLevel': continue
            seen.add(k)
            t = pstream.lod_tail(p, i)
            try: pr = pstream.parse(t)
            except Exception: c['parse error'] += 1; continue
            a = pstream.assign(pr); complete = a['float_complete'] and a['vector_complete']
            b = by_base(pr, bases(t, pr))
            seq = {}
            for g in ('float', 'vector'):
                for x in a[g]:
                    j = next(n for n, d in enumerate(pr[g + '_group']) if d is x['dist'])
                    seq[(g, j)] = (x['module_index'], x['module'], x['property'])
            bb = {(g, j): v for g in ('float', 'vector') for j, v in b[g]['owned'].items()}
            same = seq == bb
            oor = b['float']['out_of_range'] + b['vector']['out_of_range']
            c['%s / %s%s' % ('seq complete' if complete else 'seq INCOMPLETE', 'base == seq' if same else 'base != seq',
                             ' / out of range' if oor else '')] += 1
            un = {g: b[g]['unowned'] for g in ('float', 'vector') if b[g]['unowned']}
            if un: c['lods with unowned entries'] += 1
            if (not same or oor) and len(diffs) < 60:
                diffs.append({'lod': k, 'package': name, 'seq_complete': complete, 'modules': [r['module'] for r in pr['records']],
                              'bases': bases(t, pr), 'out_of_range': oor, 'unowned': un,
                              'base_assignment': {'%s[%d]' % kk: list(v) for kk, v in sorted(bb.items())},
                              'seq_assignment': {'%s[%d]' % kk: list(v) for kk, v in sorted(seq.items())}})
            if un and len(unowned) < 60:
                unowned.append({'lod': k, 'package': name, 'modules': [r['module'] for r in pr['records']], 'unowned': un,
                                'unowned_values': {g: [pr[g + '_group'][j]['values'][:6] for j in js] for g, js in un.items()}})
        objtree.package.cache_clear(); del p; gc.collect()
    out = {'generated_by': 'AssetTools/work/pstream_id0/base_index_check.py', 'distinct_lods': len(seen), 'counts': dict(c),
           'differences': diffs, 'unowned_examples': unowned}
    json.dump(out, open(os.path.join(HERE, 'base_index_check.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(out['counts'], indent=1))
    for d in diffs[:12]: print('DIFF', d['lod'], d['seq_complete'], d['modules'], d['bases'], d['out_of_range'], d['unowned'])
    for u in unowned[:8]: print('UNOWNED', u['lod'], u['modules'], u['unowned'])

if __name__ == '__main__':
    main()
