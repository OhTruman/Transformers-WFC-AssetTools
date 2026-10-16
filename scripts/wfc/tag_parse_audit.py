"""Mis-parsed tagged properties in authored.db (Integration 2026-10-16, after A1_IAC): an object whose parsed property names are not
properties of its class (the class chain in authored.db `types`) was read with a desynced name table / tag size. A1_IAC HGHWY2/3
components came out with names such as "Wave_Alpha_Pan_Speed_1407" / "_DialogEventManager_1430", so their StaticMesh did not
resolve. Checks every object under <level>.TheWorld.PersistentLevel of each of the map's levels.

  python tag_parse_audit.py <MAP> [<MAP> ...]     -> counts per map / level / class; exit 1 when any object is flagged
  check(map, levels) -> report dict                (used by vs_validate)
"""
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import authored as A  # noqa: E402

_SCHEMA = {}
def schema(class_path):
    if class_path not in _SCHEMA:
        keys, x, n = set(), class_path, 0
        while x and n < 40:
            r = A.con().execute('SELECT super, props FROM types WHERE path = ?', (x,)).fetchone()
            if not r: break
            keys |= set(json.loads(r[1] or '{}')); x = r[0]; n += 1
        _SCHEMA[class_path] = keys if n else None      # None: class not in the schema table (not checked)
    return _SCHEMA[class_path]

def check(map_name, levels):
    per_level, per_class, names, examples = Counter(), Counter(), Counter(), []
    checked = unknown_class = 0
    for lv in levels:
        for opath, cls, cp, props in A.con().execute('SELECT opath, class, class_path, props FROM objects WHERE opath LIKE ?',
                                                     (lv + '.TheWorld.PersistentLevel.%',)):
            sk = schema(cp)
            if sk is None: unknown_class += 1; continue
            checked += 1
            bad = [k for k in json.loads(props or '{}') if k not in sk]
            if bad:
                per_level[lv] += 1; per_class[cls] += 1; names.update(bad)
                if len(examples) < 10: examples.append({'object': opath, 'class': cls, 'foreign_names': bad[:6]})
    return {'map': map_name, 'objects_checked': checked, 'objects_without_class_schema': unknown_class,
            'flagged': sum(per_level.values()), 'by_level': dict(per_level), 'by_class': dict(per_class),
            'top_foreign_names': names.most_common(15), 'examples': examples}

def levels_of(map_name):
    from vs_common import VS
    from m03_common import map_levels
    mj = os.path.join(VS, 'Maps', map_name, 'map.json')
    if os.path.exists(mj): return json.load(open(mj, encoding='utf-8'))['sublevels']
    return map_levels(map_name)['all']

if __name__ == '__main__':
    bad = 0
    for m in sys.argv[1:]:
        r = check(m, levels_of(m)); bad += r['flagged']
        print('%-18s checked %7d  flagged %5d  %s' % (m, r['objects_checked'], r['flagged'], dict(Counter(r['by_class']).most_common(4))), flush=True)
    sys.exit(1 if bad else 0)
