"""Re-parse authored.db rows that tag_parse_audit.py flags (property names foreign to the class schema) with the current typed_props
reader, and update those rows in place. Cause (2026-10-16): authored.db was built before typed_props' garbage-tag guard, so for some
objects the first header-skip candidate (4) "parsed" as garbage; the current reader rejects it and lands on the real tag start (8).

Only flagged rows change. A row is updated only when the new parse is clean (every name in the class schema); the old row and its
refs are saved to backups/authored_reparse_<stamp>.json (exact undo: python authored_reparse.py undo <file>).

  python authored_reparse.py dry <MAP> [...]      list what would change (recovered property names per object)
  python authored_reparse.py apply <MAP> [...]
"""
import json, os, sqlite3, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ue3pkg, typed_props as tp, extract, tag_parse_audit as T  # noqa: E402
from authored_db import DB, walk_refs  # noqa: E402

AT = os.path.dirname(os.path.dirname(HERE))
_PK = {}
def package(name):
    if name not in _PK: _PK[name] = ue3pkg.Package(os.path.join(extract.COOKED, name + '.xxx'))
    return _PK[name]

def flagged(maps):
    con = sqlite3.connect(DB); out = []
    for m in maps:
        for lv in T.levels_of(m):
            for key, opath, cls, cp, pkg, props in con.execute(
                    'SELECT key, opath, class, class_path, package, props FROM objects WHERE opath LIKE ?', (lv + '.TheWorld.PersistentLevel.%',)):
                sk = T.schema(cp)
                if sk and [k for k in json.loads(props or '{}') if k not in sk]: out.append((m, key, opath, cls, cp, pkg))
    return out

def reparse(opath, pkg_name):
    p = package(pkg_name); r = tp.TypedReader(p)
    i = p._idx[opath.lower()] if hasattr(p, '_idx') and opath.lower() in p._idx else \
        next(k + 1 for k in range(len(p.exports)) if p.object_path(k + 1) == opath)
    e = p.exports[i - 1]
    tags, used = r.read_object(i)
    d = tp.to_dict(tags); refs = []
    for k, v in d.items(): walk_refs(v, k, refs)
    return {'props': json.dumps(tp.simplify(d), separators=(',', ':'), default=str), 'tag_bytes': used,
            'native_bytes': max(0, e['serial_size'] - used), 'refs': refs}

def main(mode, maps):
    rows = flagged(maps); con = sqlite3.connect(DB); plan = []
    for m, key, opath, cls, cp, pkg in rows:
        try: n = reparse(opath, pkg)
        except Exception as ex: plan.append({'map': m, 'object': opath, 'error': str(ex)[:120]}); continue
        names = list(json.loads(n['props']))
        clean = all(k in T.schema(cp) for k in names)
        old = con.execute('SELECT props, tag_bytes, native_bytes FROM objects WHERE key=?', (key,)).fetchone()
        plan.append({'map': m, 'key': key, 'object': opath, 'class': cls, 'clean': clean, 'recovered_properties': names,
                     'old_names': list(json.loads(old[0] or '{}')), 'new': n, 'old': {'props': old[0], 'tag_bytes': old[1], 'native_bytes': old[2],
                     'refs': con.execute('SELECT src, prop, dst, dst_class FROM refs WHERE src=?', (opath,)).fetchall()}})
    ok = [x for x in plan if x.get('clean')]
    print('flagged %d, clean re-parse %d, not clean / error %d' % (len(plan), len(ok), len(plan) - len(ok)), flush=True)
    for x in plan[:6]: print(' ', x['object'].rsplit('.', 2)[-2:], x.get('recovered_properties', x.get('error')))
    if mode != 'apply': return plan
    os.makedirs(os.path.join(AT, 'backups'), exist_ok=True)
    bak = os.path.join(AT, 'backups', 'authored_reparse_%s.json' % time.strftime('%Y%m%d_%H%M%S'))
    json.dump([{k: x[k] for k in ('key', 'object', 'old')} for x in ok], open(bak, 'w', encoding='utf-8'))
    with con:
        for x in ok:
            n = x['new']
            con.execute('UPDATE objects SET props=?, tag_bytes=?, native_bytes=? WHERE key=?', (n['props'], n['tag_bytes'], n['native_bytes'], x['key']))
            con.execute('DELETE FROM refs WHERE src=?', (x['object'],))
            con.executemany('INSERT INTO refs (src, prop, dst, dst_class) VALUES (?,?,?,?)', [(x['object'], pr, d, c) for pr, d, c in n['refs']])
    print('applied %d rows; backup %s' % (len(ok), bak), flush=True)
    json.dump([{k: x.get(k) for k in ('map', 'object', 'class', 'old_names', 'recovered_properties', 'error')} for x in plan],
              open(os.path.join(AT, 'work', 'authored_reparse_report.json'), 'w', encoding='utf-8'), indent=1)
    return plan

def undo(path):
    con = sqlite3.connect(DB)
    with con:
        for x in json.load(open(path, encoding='utf-8')):
            o = x['old']
            con.execute('UPDATE objects SET props=?, tag_bytes=?, native_bytes=? WHERE key=?', (o['props'], o['tag_bytes'], o['native_bytes'], x['key']))
            con.execute('DELETE FROM refs WHERE src=?', (x['object'],))
            con.executemany('INSERT INTO refs (src, prop, dst, dst_class) VALUES (?,?,?,?)', [tuple(r) for r in o['refs']])
    print('undone', path)

if __name__ == '__main__':
    if sys.argv[1] == 'undo': undo(sys.argv[2])
    else: main(sys.argv[1], sys.argv[2:])
