"""Recursive authored-object tree dumper (reusable for camera sets, particle systems,
SoundCue graphs, AnimTrees, weapons, pawn CDOs ...).

dump(opath) finds the largest cooked copy of the object (inventory.db), reads it with the
schema-driven TypedReader, then follows every object reference that resolves to an
export *in the same package* (cooked copies of sub-objects / referenced assets),
returning nested {"object","class","class_path","props","refs":{path: subtree}}.
References outside the package (or beyond max_depth) are kept as plain paths.

CLI: python objtree.py <opath> [--depth N] [--out file.json]
"""
import argparse, json, os, sqlite3, sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, typed_props as tp, extract  # noqa: E402

_inv = None
def inv():
    global _inv
    if _inv is None: _inv = sqlite3.connect(os.path.join(extract.MANI, 'inventory.db'))
    return _inv

def owner(opath):
    r = inv().execute('SELECT package FROM exports WHERE opath=? ORDER BY serial_size DESC, package LIMIT 1', (opath,)).fetchone()
    return r[0] if r else None

# WFC_PKG_CACHE: decompressed packages kept (default 16, unchanged). Own LRU instead of functools.lru_cache: a package and its
# TypedReader reference each other, so a package evicted from lru_cache stayed in memory until the cycle collector ran; a smaller
# cache then only multiplied dead copies (D3B_IAC vs_map hit 10 GB at 6). Eviction here runs gc.collect() so it is freed at once.
# Cache size / eviction only: outputs are identical
from collections import OrderedDict as _OD
_PKGS = _OD()
_PKG_MAX = int(os.environ.get('WFC_PKG_CACHE') or 16)
def package(name):
    if name in _PKGS:
        _PKGS.move_to_end(name); return _PKGS[name]
    p = ue3pkg.Package(os.path.join(extract.COOKED, name + '.xxx'))
    p._tr = tp.TypedReader(p)
    p._idx = {p.object_path(i + 1).lower(): i + 1 for i in range(len(p.exports))}
    _PKGS[name] = p
    if len(_PKGS) > _PKG_MAX:
        while len(_PKGS) > _PKG_MAX: _PKGS.popitem(last=False)
        import gc; gc.collect()             # free the evicted package <-> reader cycles now (still-held packages stay valid)
    return p

class _Info:
    def __init__(self): self.currsize = len(_PKGS); self.maxsize = _PKG_MAX
def _cache_clear():
    _PKGS.clear()
package.cache_clear = _cache_clear          # functools.lru_cache API kept for texture_dds / pstream_flag_census
package.cache_info = lambda: _Info()

def _refs(v, out):
    if isinstance(v, dict):
        if 'ref' in v and 'class' in v: out.append(v['ref']); return
        for x in v.values(): _refs(x, out)
    elif isinstance(v, list):
        for x in v: _refs(x, out)

def read(pkgname, opath):
    p = package(pkgname); i = p._idx.get(opath.lower())
    if not i: return None
    try: d = p._tr.read_dict(i)
    except Exception as ex: d = {'__error__': str(ex)}
    return {'object': opath, 'class': p.class_name(p.exports[i - 1]), 'class_path': p._tr.class_path(i),
            'archetype': (p.object_path(p.exports[i - 1]['archetype']) if p.exports[i - 1]['archetype'] > 0 else
                          p.full_path(p.exports[i - 1]['archetype']) if p.exports[i - 1]['archetype'] else None),
            'package': pkgname, 'raw': d}

def dump(opath, pkgname=None, max_depth=8, follow=None, _seen=None, _depth=0):
    pkgname = pkgname or owner(opath)
    if not pkgname: return {'object': opath, 'missing': True}
    _seen = set() if _seen is None else _seen
    node = read(pkgname, opath)
    if node is None: return {'object': opath, 'not_in_package': pkgname}
    raw = node.pop('raw'); node['props'] = tp.simplify(raw)
    if opath.lower() in _seen or _depth >= max_depth: return node
    _seen.add(opath.lower())
    refs = []; _refs(raw, refs)
    kids = {}
    p = package(pkgname)
    for r in refs:
        if r.lower() in _seen or r in kids: continue
        if r.lower() not in p._idx: continue
        if follow and not follow(r): continue
        kids[r] = dump(r, pkgname, max_depth, follow, _seen, _depth + 1)
    if kids: node['refs'] = kids
    return node

def flatten(tree, out=None):
    """tree -> {opath: {class, props}} (convenient for consumers)."""
    out = {} if out is None else out
    if 'props' in tree:
        out[tree['object']] = {'class': tree['class'], 'props': tree['props']}
    for k in tree.get('refs', {}).values(): flatten(k, out)
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('opath'); ap.add_argument('--depth', type=int, default=8)
    ap.add_argument('--out'); ap.add_argument('--flat', action='store_true')
    a = ap.parse_args()
    t = dump(a.opath, max_depth=a.depth)
    s = json.dumps(flatten(t) if a.flat else t, indent=1, default=str)
    if a.out: open(a.out, 'w').write(s)
    else: print(s)
