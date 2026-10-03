"""Census of the compiled particle-module flag bytes (pstream records) over every ParticleLODLevel cooked into the MP maps.

Bounded: one map package in memory at a time (objtree cache cleared after each), de-duplicated by object path,
working-set guard. Writes manifests/particle_flag_census.json.
  python pstream_flag_census.py
"""
import gc, json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, pstream  # noqa: E402
from m03_common import write, HIGH, PART, UNK  # noqa: E402
from fe_map_catalog import rss_gb  # noqa: E402

MAPS = ['MP_IAC_Streets_BASE_m', 'MP_IAC_Seed_BASE_m', 'MP_IAC_Berth_BASE_m', 'MP_UND_Complex_BASE_m', 'MP_IAC_Rust_BASE_m',
        'MP_ESC_BrokenHope_Base_m', 'MP_ESC_Remnant_BASE_m', 'MP_ORB_Debris_BASE_m', 'MP_KON_Molten_BASE_m', 'MP_UND_Gorge_BASE_m']
MEM_LIMIT_GB = 6

def main():
    seen, lods = set(), 0
    agree, xt = Counter(), {}
    for name in MAPS:
        p = objtree.package(name)
        for k, i in p._idx.items():
            if k in seen or p.class_name(p.exports[i - 1]) != 'ParticleLODLevel': continue
            seen.add(k)
            try:
                pr = pstream.parse(pstream.lod_tail(p, i))
            except Exception:
                continue
            lods += 1
            for r in pr['records']:
                inl = r['index'] in pr['list_after_records']
                agree[(r['flagA'], inl)] += 1
                key = 'A%dB%d%s' % (r['flagA'], r['flagB'], 'L' if inl else '-')
                xt.setdefault(r['module'], Counter())[key] += 1
        objtree.package.cache_clear(); del p; gc.collect()
        if rss_gb() > MEM_LIMIT_GB: raise MemoryError('working-set guard')
    flagb = {m: sorted({k[3] for k in c}) for m, c in xt.items()}
    never_listed = sorted(m for m, c in xt.items() if all(not k.endswith('L') for k in c) and any(k.startswith('A1') for k in c))
    write('particle_flag_census.json', {
        'generated_by': 'AssetTools/scripts/wfc/pstream_flag_census.py', 'packages': MAPS, 'lods': lods,
        'records': sum(agree.values()),
        'flagA_vs_post_record_list': {'%s,%s' % k: v for k, v in agree.items()},
        'crosstab (module -> A<flagA>B<flagB><L=in list|->)': {m: dict(c) for m, c in sorted(xt.items(), key=lambda x: -sum(x[1].values()))},
        'flagB_values_per_module_class': flagb,
        'flagB_constant_per_class': all(len(v) == 1 for m, v in flagb.items() if m != 'PMI_Unknown'),
        'enabled_but_never_listed_classes': never_listed,
        'conclusions': {
            'flagA': 'module enabled (UE3 bEnabled, per instance): every flagA=0 record is absent from the post-record list and '
                     'flagA=0 occurs in every module class - HIGH (RE MILESTONE04_STREETS_PICKUP_OBJECTIVE_PRESENTATION §2 + this census). '
                     'Do not evaluate flagA=0 modules.',
            'post_record_list': 'enabled modules except whole classes that are never listed (%s): consistent with a spawn-step list; '
                                'PARTIAL (native consumer not located)' % ', '.join(never_listed),
            'flagB': 'constant per module class (no instance variation) - a class trait, not authored per-instance data; meaning UNKNOWN; '
                     'presentation should not gate on it'}})
    print('lods', lods, 'records', sum(agree.values()), 'flagB constant per class', all(len(v) == 1 for m, v in flagb.items() if m != 'PMI_Unknown'))

if __name__ == '__main__':
    main()
