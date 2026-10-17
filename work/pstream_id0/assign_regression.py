"""Regression for pstream.assign (base-index, 2026-10-18) vs pstream.assign_sequential over every distinct cooked ParticleLODLevel:
identical (owner record, module, property, distribution, confidence) wherever the sequential assignment was complete.
Read-only; prints counts and writes assign_regression.json here."""
import gc, json, os, sqlite3, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'wfc'))
import objtree, pstream  # noqa: E402

def key(a):
    return {g: [(x['module_index'], x['module'], x['property'], x['dist']['offset'], x['confidence']) for x in a[g]] for g in ('float', 'vector')}

inv = sqlite3.connect(os.path.join(ROOT, 'manifests', 'inventory.db'))
pkgs = [r[0] for r in inv.execute("select distinct package from exports where class='ParticleLODLevel' order by package")]
seen = set(); c = Counter(); other = []
for name in pkgs:
    try: p = objtree.package(name)
    except Exception: continue
    for k, i in p._idx.items():
        if k in seen or p.class_name(p.exports[i - 1]) != 'ParticleLODLevel': continue
        seen.add(k)
        try: pr = pstream.parse(pstream.lod_tail(p, i))
        except Exception: c['parse error'] += 1; continue
        old, new = pstream.assign_sequential(pr), pstream.assign(pr, p)
        oc = old['float_complete'] and old['vector_complete']; nc = new['float_complete'] and new['vector_complete']
        same = key(old) == key(new) and len(old['float_unassigned']) == len(new['float_unassigned']) \
            and len(old['vector_unassigned']) == len(new['vector_unassigned'])
        c['old %s -> new %s, %s' % ('complete' if oc else 'INCOMPLETE', 'complete' if nc else 'INCOMPLETE', 'identical' if same else 'DIFFERENT')] += 1
        if not same: other.append({'lod': k, 'old_complete': oc, 'new_complete': nc, 'new': key(new), 'old': key(old)})
    objtree.package.cache_clear(); del p; gc.collect()
json.dump({'lods': len(seen), 'counts': dict(c), 'different': other}, open(os.path.join(HERE, 'assign_regression.json'), 'w'), indent=1)
print(len(seen), dict(c)); [print('DIFF', o['lod'], o['old_complete'], '->', o['new_complete']) for o in other]
