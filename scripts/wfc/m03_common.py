"""Shared helpers for the Milestone-03 targeted evidence manifests (AssetTools/manifests/*.json).

Provenance record per important field:
  {"value": ..., "source_package": ..., "object": ..., "class": ..., "property": ..., "confidence": ...,
   "origin": "authored" | "inherited:<object>" | "class default" | "absent" | "decoded native" | ...}
Confidence vocabulary (as requested for M03): CONFIRMED AUTHORED DATA, HIGH CONFIDENCE, PARTIAL, UNKNOWN.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MANI = os.path.join(AT, 'manifests')
CONF = 'CONFIRMED AUTHORED DATA'
HIGH = 'HIGH CONFIDENCE'
PART = 'PARTIAL'
UNK = 'UNKNOWN'

def pkg_of(opath):
    r = A.con().execute('SELECT package FROM objects WHERE opath = ?', (opath,)).fetchone()
    return r[0] if r else None

def cls_of(opath):
    r = A.get(opath)
    return r['class'] if r else None

def field(opath, prop, conf=CONF, default=None, note=None):
    """Value of prop on opath resolved through the archetype/CDO chain, with where it came from."""
    own = (A.get(opath) or {}).get('props') or {}
    if prop in own:
        v, origin, src = own[prop], 'authored on object', opath
    else:
        v, origin, src = None, 'absent (engine default)', None
        for c in A.chain(opath)[1:]:
            p = (A.get(c['opath']) or {}).get('props') or {}
            if prop in p:
                v, origin, src = p[prop], 'inherited from ' + c['opath'], c['opath']
                break
        if src is None and default is not None:
            v, origin = default, 'unset in whole chain -> property zero/None default'
    r = {'value': v, 'source_package': pkg_of(src or opath), 'object': src or opath, 'class': cls_of(src or opath),
         'property': prop, 'origin': origin, 'confidence': conf}
    if note: r['note'] = note
    return r

def lit(value, obj, prop, conf=CONF, note=None, origin='authored on object'):
    r = {'value': value, 'source_package': pkg_of(obj), 'object': obj, 'class': cls_of(obj), 'property': prop,
         'origin': origin, 'confidence': conf}
    if note: r['note'] = note
    return r

def write(name, data):
    path = os.path.join(MANI, name)
    json.dump(data, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print('->', path)
    return path
