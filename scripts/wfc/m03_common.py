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


# ------------------------------------------------------------------ map-agnostic helpers (generic map pipeline)
STREETS = 'MP_IAC_Streets'

def map_arg(default=STREETS):
    """first positional command-line argument (not a --flag or a flag's value), else default."""
    import sys
    args = sys.argv[1:]
    skip = False
    for a in args:
        if skip: skip = False; continue
        if a.startswith('--'):
            skip = '=' not in a and a not in ('--before',) and False
            continue
        return a
    return default

def map_out(map_name, name):
    """Streets keeps its canonical manifest names; other maps write manifests/next_map/<MAP>_<name without 'streets_'>."""
    if map_name == STREETS: return name
    os.makedirs(os.path.join(MANI, 'next_map'), exist_ok=True)
    return 'next_map/%s_%s' % (map_name, name.replace('streets_', ''))

def map_levels(map_name):
    """cooked level packages of a map, resolved case-insensitively: {'base', 'art', 'audio', 'all'}."""
    import extract as _x
    names = {os.path.splitext(n)[0].lower(): os.path.splitext(n)[0] for n in os.listdir(_x.COOKED)}
    pick = lambda suf: names.get((map_name + '_' + suf + '_m').lower())
    lv = {'base': pick('base'), 'art': pick('art'), 'audio': pick('audio')}
    lv['all'] = [x for x in (lv['base'], lv['art'], lv['audio']) if x]
    # + streamed sublevels exported by vs_map (authored LevelStreaming; Seed: MP_IAC_Global_Art_m, Debris: MP_ORB_Art_m)
    import json
    from vs_common import VS
    mj = os.path.join(VS, 'Maps', map_name, 'map.json')
    if os.path.exists(mj):
        have = {x.lower() for x in lv['all']}
        lv['all'] += [x for x in json.load(open(mj, encoding='utf-8')).get('sublevels') or [] if x.lower() not in have]
    return lv

def bsp_level(map_name, lv=None):
    """level holding the map's BSP: the ART level when cooked, else the level with the most exported BSP triangles (map.json;
    single-level maps such as MP_ORB_Debris keep their BSP in BASE)."""
    lv = lv or map_levels(map_name)
    if lv.get('art'): return lv['art']
    import json
    from vs_common import VS
    mj = os.path.join(VS, 'Maps', map_name, 'map.json')
    bsp = (json.load(open(mj, encoding='utf-8')).get('bsp') or {}) if os.path.exists(mj) else {}
    best = max(bsp.items(), key=lambda kv: (kv[1] or {}).get('render_triangles') or 0, default=(None, None))[0]
    return best or lv.get('base')
