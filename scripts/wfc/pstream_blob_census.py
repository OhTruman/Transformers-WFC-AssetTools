"""Census of the compiled parameter blob (pstream.param_blob) over every ParticleLODLevel cooked into the 10 MP maps: decoded / size
mismatch / unknown block sizes, the module ids still missing a block size, and those sizes solved from the LODs where they are the only
unknown (SIZE - sum of known blocks, divided by the count). Bounded like pstream_flag_census.py.
  python pstream_blob_census.py -> manifests/particle_blob_census.json
"""
import gc, json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import objtree, pstream  # noqa: E402
from m03_common import write  # noqa: E402
from fe_map_catalog import rss_gb  # noqa: E402
from pstream_flag_census import MAPS, MEM_LIMIT_GB  # noqa: E402

def main():
    seen = set(); status = Counter(); unknown = Counter(); solved = defaultdict(Counter); mismatch = []; decoded_fields = Counter()
    for name in MAPS:
        p = objtree.package(name)
        for k, i in p._idx.items():
            if k in seen or p.class_name(p.exports[i - 1]) != 'ParticleLODLevel': continue
            seen.add(k)
            try:
                pr = pstream.parse(pstream.lod_tail(p, i))
            except Exception:
                status['parse error'] += 1; continue
            pb = pstream.param_blob(pr, p); st = pb.get('status', '')
            status[st.split(':')[0] if not st.startswith('unknown') else 'unknown block size'] += 1
            if st == 'decoded':
                for r in pr['records']:
                    if r['index'] in pb['blocks']: decoded_fields[r['module']] += 1
            elif st.startswith('unknown'):
                unk = [r['module'] for r in pr['records'] if pstream.block_size(r['module']) is None]
                for m in set(unk): unknown[m] += 1
                if len(set(unk)) == 1:                     # one unknown module class: solve its block size from this LOD
                    known = sum(pstream.block_size(r['module']) for r in pr['records'] if pstream.block_size(r['module']) is not None)
                    rem = pb['size'] - known
                    solved[unk[0]][(rem / len(unk)) if rem % len(unk) == 0 else 'non-integer %d/%d' % (rem, len(unk))] += 1
            elif st.startswith('size mismatch'):
                if len(mismatch) < 40: mismatch.append({'lod': k, 'status': st, 'modules': [r['module'] for r in pr['records']]})
        objtree.package.cache_clear(); del p; gc.collect()
        if rss_gb() > MEM_LIMIT_GB: raise MemoryError('working-set guard')
    rep = {'generated_by': 'AssetTools/scripts/wfc/pstream_blob_census.py', 'packages': MAPS, 'lods': len(seen), 'status': dict(status),
           'decoded_records_by_module': dict(decoded_fields.most_common()), 'lods_with_unknown_module': dict(unknown.most_common()),
           'solved_block_sizes': {m: {str(k): v for k, v in c.items()} for m, c in solved.items()}, 'size_mismatches': mismatch}
    write('particle_blob_census.json', rep)
    print(json.dumps({k: rep[k] for k in ('lods', 'status', 'lods_with_unknown_module', 'solved_block_sizes')})[:1800])

if __name__ == '__main__':
    main()
