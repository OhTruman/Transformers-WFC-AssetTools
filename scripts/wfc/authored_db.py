"""Global authored-data database: every unique cooked object with its full typed properties.

AssetTools/manifests/authored.db (SQLite)
  objects(key PK = class|opath, opath, class, class_path, outer_path, archetype, package,
          serial_size, tag_bytes, native_bytes, props JSON)
      one row per unique (original object path, class); the copy with the largest
      serialized size wins (cooked copies can be stripped stubs).
  refs(src, prop, dst, dst_class)   object references found anywhere in props
  types(path, kind, super, props JSON)   copy of schema.json for SQL joins

Query examples:
  SELECT props FROM objects WHERE opath='TransGame.Default__TnPlayerPawn';
  SELECT src, prop FROM refs WHERE dst LIKE 'BL_WPN_GUN_ION_BLASTER.%';
"""
import json, os, sqlite3, sys, time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, typed_props as tp, extract  # noqa: E402

SKIP = {'Class', 'Function', 'State', 'ScriptStruct', 'Enum', 'Const', 'Package'}
# UProperty field types (script metadata, not authored objects). Exact names: a suffix test ('...Property') also dropped real
# objects - TnPhysicalMaterialProperty / HmPhysicalMaterialProperty (surface decals, impact FX, footsteps), SeqAct_GetProperty,
# InterpTrackInstProperty, HmGoapReadableWorldStateProperty (RE 2026-10-06).
UPROPERTY = {'ObjectProperty', 'StructProperty', 'FloatProperty', 'BoolProperty', 'IntProperty', 'ByteProperty', 'StrProperty',
             'ArrayProperty', 'NameProperty', 'ClassProperty', 'DelegateProperty', 'ComponentProperty', 'InterfaceProperty',
             'ScriptMapProperty', 'MapProperty'}

def skipped(c):
    return c in SKIP or c in UPROPERTY
DB = os.path.join(extract.MANI, 'authored.db')

def walk_refs(v, prop, out):
    if isinstance(v, dict):
        if 'ref' in v and 'class' in v:
            out.append((prop, v['ref'], v['class'])); return
        for k, x in v.items(): walk_refs(x, prop if prop else k, out)
    elif isinstance(v, list):
        for x in v: walk_refs(x, prop, out)

OWN = None

def init_owner(path):
    global OWN
    OWN = path

def owned_keys(name):
    con = sqlite3.connect(OWN)
    return {r[0] for r in con.execute('SELECT key FROM owner WHERE package=?', (name,))}

def do_pkg(name):
    keys = owned_keys(name)
    if not keys: return name, [], 0
    p = ue3pkg.Package(os.path.join(extract.COOKED, name + '.xxx'))
    r = tp.TypedReader(p)
    rows, errs = [], 0
    for i, e in enumerate(p.exports):
        c = p.class_name(e)
        if skipped(c): continue
        if c + '|' + p.object_path(i + 1) not in keys: continue
        try:
            tags, used = r.read_object(i + 1)
        except Exception:
            errs += 1; tags, used = None, 0
        op = p.object_path(i + 1)
        d = tp.to_dict(tags) if tags is not None else None
        refs = []
        if d:
            for k, v in d.items(): walk_refs(v, k, refs)
        outer = p.object_path(e['outer']) if e['outer'] > 0 else None
        arch = e['archetype']
        arch_p = (p.object_path(arch) if arch > 0 else p.full_path(arch)) if arch else None
        rows.append((c + '|' + op, op, c, r.class_path(i + 1), outer, arch_p, name, e['serial_size'], used,
                     max(0, e['serial_size'] - used),
                     json.dumps(tp.simplify(d), separators=(',', ':'), default=str) if d is not None else None,
                     refs))
    return name, rows, errs

def build_owner():
    """owner package per (class|opath) = largest serialized copy (CONFIRMED rule: stripped
    stubs are smaller)."""
    path = os.path.join(extract.MANI, '_owner.db')
    if os.path.exists(path): os.remove(path)
    inv = sqlite3.connect(os.path.join(extract.MANI, 'inventory.db'))
    o = sqlite3.connect(path); o.execute('CREATE TABLE owner(key TEXT PRIMARY KEY, package TEXT, size INT)')
    best = {}
    for pkg, cls, op, sz in inv.execute('SELECT package, class, opath, serial_size FROM exports'):
        if skipped(cls): continue
        k = cls + '|' + op
        b = best.get(k)
        if b is None or sz > b[1] or (sz == b[1] and pkg < b[0]): best[k] = (pkg, sz)
    o.executemany('INSERT INTO owner VALUES(?,?,?)', ((k, v[0], v[1]) for k, v in best.items()))
    o.execute('CREATE INDEX ix_own_pkg ON owner(package)'); o.commit()
    return path, len(best)

SHARDS = os.path.join(extract.MANI, 'authored_shards')

def shard_pkg(name):
    """Resumable unit of work: one package -> one gzip JSONL shard."""
    import gzip
    out = os.path.join(SHARDS, name + '.jsonl.gz')
    if os.path.exists(out): return name, -1, 0
    _, rows, e = do_pkg(name)
    tmp = out + '.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(list(r[:11]) + [r[11]], separators=(',', ':'), default=str) + chr(10))
    os.replace(tmp, out)
    return name, len(rows), e

def merge():
    import gzip
    t0 = time.time()
    if os.path.exists(DB): os.remove(DB)
    db = sqlite3.connect(DB)
    db.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE objects(key TEXT PRIMARY KEY, opath TEXT, class TEXT, class_path TEXT, outer_path TEXT,
        archetype TEXT, package TEXT, serial_size INT, tag_bytes INT, native_bytes INT, props TEXT);
      CREATE TABLE refs(src TEXT, prop TEXT, dst TEXT, dst_class TEXT);
      CREATE TABLE types(path TEXT PRIMARY KEY, kind TEXT, super TEXT, props TEXT);''')
    for fn in sorted(os.listdir(SHARDS)):
        if not fn.endswith('.jsonl.gz'): continue
        rows = [json.loads(l) for l in gzip.open(os.path.join(SHARDS, fn), 'rt', encoding='utf-8')]
        db.executemany('INSERT OR IGNORE INTO objects VALUES(?,?,?,?,?,?,?,?,?,?,?)', [r[:11] for r in rows])
        db.executemany('INSERT INTO refs VALUES(?,?,?,?)', [(r[1], a, b, c) for r in rows for a, b, c in r[11]])
    s = json.load(open(os.path.join(extract.MANI, 'schema.json')))
    db.executemany('INSERT INTO types VALUES(?,?,?,?)', [(k, v['kind'], v['super'], json.dumps(v['props'])) for k, v in s['types'].items()])
    db.executescript('''CREATE INDEX ix_o_class ON objects(class); CREATE INDEX ix_o_opath ON objects(opath);
      CREATE INDEX ix_o_outer ON objects(outer_path); CREATE INDEX ix_r_src ON refs(src); CREATE INDEX ix_r_dst ON refs(dst);''')
    db.commit()
    n = db.execute('SELECT COUNT(*) FROM objects').fetchone()[0]
    nr = db.execute('SELECT COUNT(*) FROM refs').fetchone()[0]
    bad = db.execute('SELECT COUNT(*) FROM objects WHERE props IS NULL').fetchone()[0]
    print('MERGED unique objects %d, unparsed %d, refs %d, %.0fs' % (n, bad, nr, time.time() - t0), flush=True)

def add_missing():
    """Insert objects the old suffix filter dropped (class ends with 'Property' but is not a UProperty) into the existing
    authored.db, same row format and owner rule (largest serialized copy); existing rows untouched (INSERT OR IGNORE)."""
    inv = sqlite3.connect(os.path.join(extract.MANI, 'inventory.db'))
    best = {}
    for pkg, cls, op, sz in inv.execute("SELECT package, class, opath, serial_size FROM exports WHERE class LIKE '%Property'"):
        if skipped(cls): continue
        k = cls + '|' + op; b = best.get(k)
        if b is None or sz > b[1] or (sz == b[1] and pkg < b[0]): best[k] = (pkg, sz)
    by_pkg = {}
    for k, (pkg, _) in best.items(): by_pkg.setdefault(pkg, set()).add(k)
    db = sqlite3.connect(DB); n = nr = errs = 0
    for pkg, keys in sorted(by_pkg.items()):
        global owned_keys
        _ok = owned_keys
        owned_keys = lambda name, keys=keys: keys
        try:
            _, rows, e = do_pkg(pkg)
        finally:
            owned_keys = _ok
        errs += e
        for r in rows:
            c = db.execute('INSERT OR IGNORE INTO objects VALUES(?,?,?,?,?,?,?,?,?,?,?)', r[:11]).rowcount
            if c:
                n += 1; db.executemany('INSERT INTO refs VALUES(?,?,?,?)', [(r[1], a, b, cl) for a, b, cl in r[11]]); nr += len(r[11])
    db.commit()
    print('add_missing: %d objects inserted (%d candidates), %d refs, %d parse errors' % (n, len(best), nr, errs))

def main():
    if '--add-missing' in sys.argv:
        add_missing(); return
    t0 = time.time()
    os.makedirs(SHARDS, exist_ok=True)
    own = os.path.join(extract.MANI, '_owner.db')
    if not os.path.exists(own) or '--rebuild-owner' in sys.argv:
        own, nkeys = build_owner(); print('owners decided for %d objects' % nkeys, flush=True)
    pk = sorted(os.path.splitext(n)[0] for n in os.listdir(extract.COOKED) if n.endswith('.xxx'))
    done = skipped = 0
    # skip finished shards up front, report in completion order (ex.map reports in input order,
    # so one slow package used to hide all progress)
    todo = [n for n in pk if not os.path.exists(os.path.join(SHARDS, n + '.jsonl.gz'))]
    skipped = len(pk) - len(todo)
    print('%d packages, %d shards already done, %d to do' % (len(pk), skipped, len(todo)), flush=True)
    from concurrent.futures import as_completed
    # --jobs N (default 4): full-core runs (28 workers) coincided with two hard machine crashes
    # (Kernel-Power 41) on 2026-10-01; keep the load modest and below-normal priority.
    jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 4
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL, inherited
    except Exception:
        pass
    print('workers %d (below-normal priority)' % jobs, flush=True)
    with ProcessPoolExecutor(max(1, jobs), initializer=init_owner, initargs=(own,)) as ex:
        futs = [ex.submit(shard_pkg, n) for n in todo]
        for f in as_completed(futs):
            name, n, e = f.result()
            done += 1
            if done % 25 == 0 or done == len(todo):
                print('  %d/%d done (last %s: %d objects, %d unparsed), %.0fs' % (done, len(todo), name, n, e, time.time() - t0), flush=True)
    print('SHARDS COMPLETE %.0fs' % (time.time() - t0), flush=True)
    merge()

if __name__ == '__main__':
    main()
