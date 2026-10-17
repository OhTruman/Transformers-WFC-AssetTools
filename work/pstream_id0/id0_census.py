"""Data test of RE's PowerCell rule (2026-10-18, HIGH): a compiled record with ModuleId 0 whose object is a ParticleModuleLocationPrimitive*
subclass contributes its LocationPrimitiveBase distributions (float VelocityScale + vector StartLocation) at its record position; id-0
records whose object is any other class contribute nothing.
Over every distinct ParticleLODLevel in every cooked package: leftovers under pstream's current rules vs with the rule applied, grouped
by the classes of the LOD's id-0 objects. Read-only; writes id0_census.json here.
"""
import gc, json, os, sqlite3, sys
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'wfc'))
import objtree, pstream  # noqa: E402

def assign_rule(pr, p):
    """pstream.assign with id-0 LocationPrimitive* records owning [VelocityScale] / [StartLocation]"""
    recs = []
    for r in pr['records']:
        r = dict(r)
        if r['module_id'] == 0 and 0 < r['object_ref'] <= len(p.exports):
            cls = p.class_name(p.exports[r['object_ref'] - 1])
            if cls.startswith('ParticleModuleLocationPrimitive'): r['module'] = 'ID0_LOCPRIM'
        recs.append(r)
    saved = pstream.MODULE_DISTS.get('ID0_LOCPRIM')
    pstream.MODULE_DISTS['ID0_LOCPRIM'] = (['VelocityScale'], ['StartLocation'])
    try:
        return pstream.assign(dict(pr, records=recs))
    finally:
        if saved is None: del pstream.MODULE_DISTS['ID0_LOCPRIM']

def main():
    inv = sqlite3.connect(os.path.join(ROOT, 'manifests', 'inventory.db'))
    pkgs = [r[0] for r in inv.execute("select distinct package from exports where class='ParticleLODLevel' order by package")]
    seen = set(); groups = defaultdict(lambda: Counter()); examples = defaultdict(list)
    for name in pkgs:
        try: p = objtree.package(name)
        except Exception: continue
        for k, i in p._idx.items():
            if k in seen or p.class_name(p.exports[i - 1]) != 'ParticleLODLevel': continue
            seen.add(k)
            try: pr = pstream.parse(pstream.lod_tail(p, i))
            except Exception: groups['(parse error)']['lods'] += 1; continue
            id0 = []
            for r in pr['records']:
                if r['module_id'] == 0:
                    ref = r['object_ref']
                    id0.append(p.class_name(p.exports[ref - 1]).replace('ParticleModule', '') if 0 < ref <= len(p.exports) else '(no object)')
            key = ' + '.join(sorted(id0)) or '(no id-0 record)'
            a = pstream.assign(pr)
            cur = (len(a['float_unassigned']), len(a['vector_unassigned']), a['float_complete'] and a['vector_complete'])
            g = groups[key]; g['lods'] += 1
            g['current: leftovers f%d v%d %s' % (cur[0], cur[1], 'complete' if cur[2] else 'incomplete')] += 1
            if any(c.startswith('LocationPrimitive') for c in id0):
                b = assign_rule(pr, p)
                new = (len(b['float_unassigned']), len(b['vector_unassigned']), b['float_complete'] and b['vector_complete'])
                g['rule: leftovers f%d v%d %s' % (new[0], new[1], 'complete' if new[2] else 'incomplete')] += 1
                if len(examples[key]) < 4: examples[key].append({'lod': k, 'package': name, 'modules': [r['module'] for r in pr['records']],
                                                                 'current_leftovers': cur[:2], 'rule_leftovers': new[:2]})
        objtree.package.cache_clear(); del p; gc.collect()
    out = {'generated_by': 'AssetTools/work/pstream_id0/id0_census.py', 'packages': len(pkgs), 'distinct_lods': len(seen),
           'groups': {k: dict(v) for k, v in sorted(groups.items(), key=lambda x: -x[1]['lods'])}, 'examples': examples}
    json.dump(out, open(os.path.join(HERE, 'id0_census.json'), 'w', encoding='utf-8'), indent=1)
    for k, v in out['groups'].items(): print(k, dict(v))

if __name__ == '__main__':
    main()
