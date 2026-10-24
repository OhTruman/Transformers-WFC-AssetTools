"""Which cooked packages have a compressed block whose decoded size differs from its declared size (RE 2026-10-23: ue3pkg.decompress
now places blocks at their declared offset; a package WITHOUT such a block decompresses byte-identically to before). Read only.
    python scan_short_blocks.py <cooked dir> [<cooked dir> ...]   -> work/dlc/short_blocks.json
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
import ue3pkg  # noqa: E402
hits = {}; n = 0
for d in sys.argv[1:]:
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(('.xxx', '.u')): continue
        data = open(os.path.join(d, f), 'rb').read()
        try: s = ue3pkg.read_summary(data)
        except Exception: continue
        if not s.get('chunks'): continue
        del ue3pkg.SHORT_BLOCKS[:]
        try: ue3pkg.decompress(data, s)
        except Exception as x: hits[f] = {'error': repr(x)[:200]}; continue
        n += 1
        if ue3pkg.SHORT_BLOCKS: hits[os.path.join(os.path.basename(d.rstrip('/\\')), f)] = list(ue3pkg.SHORT_BLOCKS)
json.dump({'compressed_packages_scanned': n, 'packages_with_short_blocks': hits}, open(os.path.join(HERE, 'short_blocks.json'), 'w', encoding='utf-8'), indent=1)
print('compressed packages', n, '| with short / long blocks', len(hits), list(hits)[:10])
