"""Query layer over manifests/authored.db (global authored-object database, authored_db.py).

  import authored as A
  A.get(opath)                -> {'opath','class','class_path','package','archetype','outer','props'} | None
  A.effective(opath)          -> {prop: {'value', 'from'}} through archetype / class-default chain
  A.values(opath)             -> {prop: value} (effective)
  A.children(outer, cls=None) -> [rows] whose outer_path == outer
  A.find(pattern, cls=None)   -> [rows] with opath LIKE pattern
  A.refs_to(dst)              -> [(src, prop)]
  A.cue(opath)                -> SoundCue graph: root params, category, node tree, flat wave list (with WAV paths)

Archetype rule (CONFIRMED, see FORMAT_NOTES): the stored archetype if any, else the class default object
'<ClassPkg>.Default__<Class>'; a CDO's parent is its super-class CDO (types table).
"""
import json, os, sqlite3, sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract  # noqa: E402

DB = os.path.join(extract.MANI, 'authored.db')
ROOT = os.path.dirname(extract.OUT)
_con = None

def con():
    global _con
    if _con is None: _con = sqlite3.connect('file:%s?mode=ro' % DB.replace('\\', '/'), uri=True)
    return _con

def _row(r):
    if not r: return None
    return {'opath': r[0], 'class': r[1], 'class_path': r[2], 'outer': r[3], 'archetype': r[4], 'package': r[5],
            'props': json.loads(r[6]) if r[6] else None}

COLS = 'opath, class, class_path, outer_path, archetype, package, props'

@lru_cache(maxsize=200000)
def _get(opath):
    rows = con().execute('SELECT %s FROM objects WHERE opath = ?' % COLS, (opath,)).fetchall()
    if not rows:
        rows = con().execute('SELECT %s FROM objects WHERE opath = ? COLLATE NOCASE' % COLS, (opath,)).fetchall()
    if not rows: return None
    # same opath can exist for several classes (rare): prefer the non-Package one with most props
    rows.sort(key=lambda r: (r[1] == 'Package', -len(r[6] or '')))
    return json.dumps(_row(rows[0]))

def _fix_matrices(type_path, props, depth=0):
    """authored.db shards were written before typed_props.fix_raw: reorder Matrix-typed values (W,X,Y,Z rows),
    recursing into nested structs and struct arrays by their declared schema types (e.g. KAggregateGeom.BoxElems[].TM)."""
    if not isinstance(props, dict) or not type_path or depth > 8: return props
    import typed_props as tp
    for k, v in list(props.items()):
        d = tp.find_prop(type_path, k)
        if not d: continue
        if d.get('type') == 'StructProperty':
            st = d.get('struct') or ''
            if st.endswith('.Matrix') and isinstance(v, list) and len(v) == 16:
                props[k] = tp.fix_raw('Matrix', v)
            elif isinstance(v, dict):
                _fix_matrices(st, v, depth + 1)
        elif d.get('type') == 'ArrayProperty' and (d.get('inner') or {}).get('type') == 'StructProperty' and isinstance(v, list):
            st = d['inner'].get('struct') or ''
            for i, x in enumerate(v):
                if st.endswith('.Matrix') and isinstance(x, list) and len(x) == 16: v[i] = tp.fix_raw('Matrix', x)
                elif isinstance(x, dict): _fix_matrices(st, x, depth + 1)
    return props

DB_MATRIX_FIXED = False   # set True once authored.db is rebuilt with the fixed reader

def get(opath):
    s = _get(opath) if opath else None
    if not s: return None
    o = json.loads(s)
    if not DB_MATRIX_FIXED: o['props'] = _fix_matrices(o.get('class_path'), o.get('props'))
    return o

@lru_cache(maxsize=4096)
def _super(class_path):
    r = con().execute('SELECT super FROM types WHERE path = ?', (class_path,)).fetchone()
    return r[0] if r else None

def chain(opath, max_len=24):
    out, seen, cur = [], set(), opath
    while cur and cur.lower() not in seen and len(out) < max_len:
        seen.add(cur.lower())
        o = get(cur)
        if not o:
            out.append({'opath': cur, 'missing': True}); break
        out.append(o)
        nxt = o.get('archetype')
        if not nxt:
            name = cur.rsplit('.', 1)[-1]; cp = o.get('class_path') or ''
            if name.startswith('Default__'):
                sup = _super(cp)
                nxt = sup.rsplit('.', 1)[0] + '.Default__' + sup.rsplit('.', 1)[1] if sup and '.' in sup else None
            elif '.' in cp:
                nxt = cp.rsplit('.', 1)[0] + '.Default__' + cp.rsplit('.', 1)[1]
        cur = nxt
    return out

def _deep(child, parent):
    """struct properties serialize only fields that differ from the archetype's struct value:
    merge dict over dict recursively (lists/arrays are whole values in UE3 deltas)."""
    if isinstance(child, dict) and isinstance(parent, dict):
        out = dict(parent)
        for k, v in child.items(): out[k] = _deep(v, parent.get(k))
        return out
    return child

def effective(opath):
    eff = {}
    for o in chain(opath):
        for k, v in (o.get('props') or {}).items():
            if k not in eff:
                eff[k] = {'value': v, 'from': o['opath']}
            elif isinstance(eff[k]['value'], dict) and isinstance(v, dict) and not ('ref' in v):
                eff[k] = {'value': _deep(eff[k]['value'], v), 'from': eff[k]['from'], 'struct_defaults_from': o['opath']}
    return eff

def values(opath):
    return {k: v['value'] for k, v in effective(opath).items()}

def children(outer, cls=None):
    q = 'SELECT %s FROM objects WHERE outer_path = ?' % COLS + (' AND class = ?' if cls else '')
    return [_row(r) for r in con().execute(q, (outer, cls) if cls else (outer,))]

def find(pattern, cls=None):
    q = 'SELECT %s FROM objects WHERE opath LIKE ?' % COLS + (' AND class = ?' if cls else '')
    return [_row(r) for r in con().execute(q, (pattern, cls) if cls else (pattern,))]

def refs_to(dst):
    return con().execute('SELECT src, prop FROM refs WHERE dst = ?', (dst,)).fetchall()

_wav = None
def wav_of(wave):
    global _wav
    if _wav is None:
        _wav = {}
        for fn in ('audio_native.jsonl', 'audio.jsonl'):
            p = os.path.join(extract.MANI, 'extracted', fn)
            if not os.path.exists(p): continue
            for l in open(p, encoding='utf-8'):
                r = json.loads(l); w = os.path.splitext(r.get('output') or '')[0] + '.wav'
                if os.path.exists(os.path.join(ROOT, w)): _wav.setdefault(r['object_path'], w)
    return _wav.get(wave)

WAVE_CLASSES = ('SoundNodeWave', 'SoundNodeWaveEx')

def cue(opath, depth=0):
    """SoundCue -> {'cue','root':{...},'category','tree','waves':[{wave,wav,duration,path:[node classes]}]}"""
    c = get(opath)
    if not c: return {'cue': opath, 'missing': True}
    out = {'cue': opath, 'class': c['class']}
    waves = []
    def node(np, path, d):
        o = get(np)
        if not o: return {'node': np, 'missing': True}
        p = o['props'] or {}
        t = {'node': np.rsplit('.', 1)[-1] if np.startswith(opath + '.') else np, 'class': o['class']}
        if o['class'] in WAVE_CLASSES:
            w = {'wave': np, 'wav': wav_of(np), 'duration': p.get('Duration'), 'path': path}
            waves.append(w); t.update({'wav': w['wav'], 'duration': w['duration']}); return t
        params = {k: v for k, v in p.items() if k not in ('ChildNodes', 'Category', 'SecondaryCategory', 'PlayMixerPreset')}
        for k in ('Category', 'SecondaryCategory'):
            if p.get(k):
                cn = (get(p[k]) or {}).get('props') or {}
                if cn.get('CategoryName'): params[k] = cn['CategoryName']
        if p.get('PlayMixerPreset'):
            pn = (get(p['PlayMixerPreset']) or {}).get('props') or {}
            if pn.get('PresetName'): params['PlayMixerPreset'] = pn['PresetName']
        if params: t['params'] = params
        if d < 24:
            kids = [k for k in (p.get('ChildNodes') or []) if k]
            if kids: t['children'] = [node(k, path + [o['class']], d + 1) for k in kids]
        return t
    fn = (c['props'] or {}).get('FirstNode')
    if fn:
        out['tree'] = node(fn, [], 0)
        r = get(fn)
        if r and r['class'] == 'SoundNodeRoot': out['root'] = out['tree'].get('params', {})
    out['waves'] = waves
    out['category'] = (out.get('root') or {}).get('Category')
    return out
