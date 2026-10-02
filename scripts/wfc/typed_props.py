"""Schema-driven tagged-property reader (supersedes props.py guessing for arrays/structs).

Uses manifests/schema.json (schema.py) to know every property's declared type, so:
  * ArrayProperty elements decode by their Inner type (float/int/name/byte/enum/str/
    object/struct), instead of being guessed from the byte count
  * StructProperty / struct-array elements decode with their struct's own schema
  * immutable/native structs (Vector, Color, Rotator, Guid, Matrix, ...) decode raw
Tag layout (CONFIRMED for 511/144): Name, Type, Size, ArrayIndex [, StructName], value;
BoolProperty value = 4 bytes (ver < 673). Unknown pieces fall back to {'raw': hex}.

API:
  r = TypedReader(pkg); props, used = r.read_object(export_index)   # list of tags
  d = r.read_dict(export_index)                                    # flattened dict
  r.class_path(export_index)  -> 'Engine.AnimSequence'
"""
import json, os, struct, sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ue3pkg import Reader  # noqa: E402

RAW = {'Vector': ('>3f', ['X', 'Y', 'Z']), 'Rotator': ('>3i', ['Pitch', 'Yaw', 'Roll']),
       'Color': ('4B', ['B', 'G', 'R', 'A']), 'LinearColor': ('>4f', ['R', 'G', 'B', 'A']),
       'Vector2D': ('>2f', ['X', 'Y']), 'Guid': ('>4I', ['A', 'B', 'C', 'D']), 'Quat': ('>4f', ['X', 'Y', 'Z', 'W']),
       'Vector4': ('>4f', ['X', 'Y', 'Z', 'W']), 'IntPoint': ('>2i', ['X', 'Y']), 'Plane': ('>4f', ['X', 'Y', 'Z', 'W']),
       'Box': ('>6fB', None), 'Matrix': ('>16f', None), 'TwoVectors': ('>6f', None), 'Sphere': ('>4f', None),
       'BoxSphereBounds': ('>7f', None)}

def fix_raw(short, v):
    """Cooked (Xbox) tagged FMatrix rows are stored (W, X, Y, Z); return conventional row-major X,Y,Z,W.
    CONFIRMED 2026-10-01: StaticLightCollectionActor native LocalToWorld vs each light's CachedParentToWorld
    tag (268/268 lights), decal CachedParentToWorld = identity, OriginalParentRelativeTransform."""
    if short == 'Matrix' and isinstance(v, list) and len(v) == 16:
        return [x for r in range(4) for x in (v[4 * r + 1], v[4 * r + 2], v[4 * r + 3], v[4 * r])]
    return v

_schema = None
def schema():
    global _schema
    if _schema is None:
        s = json.load(open(os.path.join(HERE, '..', '..', 'manifests', 'schema.json'), encoding='utf-8'))
        by_name = {}
        for k in s['types']:
            by_name.setdefault(k.rsplit('.', 1)[-1].lower(), []).append(k)
        s['by_name'] = by_name
        _schema = s
    return _schema

def resolve_type(path):
    """Map an import/export path to a schema key (paths differ by package prefix)."""
    if not path: return None
    S = schema()
    if path in S['types']: return path
    c = S['by_name'].get(path.rsplit('.', 1)[-1].lower(), [])
    if len(c) == 1: return c[0]
    # prefer a candidate sharing the outer name (struct inside class)
    parts = path.split('.')
    for k in c:
        if len(parts) > 1 and k.split('.')[-2:-1] == parts[-2:-1]: return k
    return c[0] if c else None

@lru_cache(maxsize=20000)
def find_prop(type_path, name):
    S = schema(); t = resolve_type(type_path); seen = 0
    lname = name.lower()
    while t and seen < 40:
        info = S['types'].get(t)
        if not info: break
        for k, v in info['props'].items():
            if k.lower() == lname: return v
        t = resolve_type(info.get('super')); seen += 1
    return None

class TypedReader:
    def __init__(self, pkg):
        self.p = pkg

    def ref(self, idx):
        if idx == 0: return None
        try:
            if idx > 0:
                e = self.p.exports[idx - 1]
                return {'ref': self.p.object_path(idx), 'class': self.p.class_name(e)}
            im = self.p.imports[-idx - 1]
            return {'ref': self.p.full_path(idx), 'class': im['class']}
        except IndexError:
            return {'ref_bad': idx}

    def class_path(self, i):
        ci = self.p.exports[i - 1]['class_index']
        if ci == 0: return 'Core.Class'
        return self.p.object_path(ci) if ci > 0 else self.p.full_path(ci)

    # ---------------------------------------------------------------- objects
    def read_object(self, i, max_props=5000):
        e = self.p.exports[i - 1]
        end = e['serial_offset'] + e['serial_size']
        cp = self.class_path(i)
        err = None
        for skip in (4, 8, 16, 30, 0):
            r = Reader(self.p.data, e['serial_offset'] + skip)
            try:
                tags = self.tags(r, end, cp, max_props)
                return tags, r.p - e['serial_offset']
            except Exception as ex:
                err = ex
        raise err

    def read_dict(self, i):
        return to_dict(self.read_object(i)[0])

    def tags(self, r, end, owner_type, max_props=5000):
        out = []
        for _ in range(max_props):
            if r.p + 8 > end: raise ValueError('ran off end')
            name = self.p.fname(r)
            if name == 'None': return out
            ptype = self.p.fname(r)
            size = r.i32(); aidx = r.i32()
            # garbage guard: a wrong header skip reads random bytes as tags (seen: name '?-1090438784_190',
            # ArrayIndex 1468456127 -> to_dict tried to allocate a 1.47e9-entry list, 8+ GB per worker)
            if name.startswith('?') or not ptype.endswith('Property') or not 0 <= aidx < 65536:
                raise ValueError('invalid tag %r %r idx %d' % (name, ptype, aidx))
            sname = self.p.fname(r) if ptype == 'StructProperty' else None
            if ptype == 'BoolProperty':
                val = bool(r.u32())
            else:
                if size < 0 or r.p + size > end: raise ValueError('bad size %s %d' % (name, size))
                decl = find_prop(owner_type, name) if owner_type else None
                val = self.value(ptype, sname, r.d[r.p:r.p + size], decl)
                r.p += size
            t = {'name': name, 'type': ptype, 'value': val}
            if aidx: t['index'] = aidx
            if sname: t['struct'] = sname
            out.append(t)
        raise ValueError('too many props')

    # ---------------------------------------------------------------- values
    def value(self, ptype, sname, raw, decl):
        r = Reader(raw)
        try:
            if ptype in ('ObjectProperty', 'ClassProperty', 'ComponentProperty', 'InterfaceProperty'):
                return self.ref(r.i32())
            if ptype == 'IntProperty': return r.i32()
            if ptype == 'FloatProperty': return struct.unpack('>f', raw[:4])[0]
            if ptype == 'NameProperty': return self.p.fname(r)
            if ptype == 'ByteProperty': return raw[0] if len(raw) == 1 else self.p.fname(r)
            if ptype == 'StrProperty': return r.fstring()
            if ptype == 'DelegateProperty': return {'object': self.ref(r.i32()), 'function': self.p.fname(r)}
            if ptype == 'StructProperty':
                return self.struct_value(sname, raw, (decl or {}).get('struct'))
            if ptype == 'ArrayProperty':
                return self.array_value(raw, (decl or {}).get('inner'))
        except Exception as ex:
            return {'raw': raw[:96].hex(), 'len': len(raw), 'error': str(ex)[:80]}
        return {'raw': raw[:96].hex(), 'len': len(raw)}

    def struct_value(self, sname, raw, struct_path=None):
        short = (sname or (struct_path or '').rsplit('.', 1)[-1])
        if short in RAW:
            fmt, names = RAW[short]
            if struct.calcsize(fmt) == len(raw):
                v = fix_raw(short, list(struct.unpack(fmt, raw)))
                return dict(zip(names, v)) if names else v
        tpath = resolve_type(struct_path or short)
        r = Reader(raw)
        return to_dict(self.tags(r, len(raw), tpath))

    def struct_size_raw(self, short):
        return struct.calcsize(RAW[short][0]) if short in RAW else None

    def array_value(self, raw, inner):
        r = Reader(raw); n = r.i32()
        if n < 0 or n > 10_000_000: raise ValueError('bad array count')
        if n == 0: return []
        body = raw[4:]
        it = (inner or {}).get('type')
        if it == 'FloatProperty' and len(body) == 4 * n:
            return list(struct.unpack('>%df' % n, body))
        if it == 'IntProperty' and len(body) == 4 * n:
            return list(struct.unpack('>%di' % n, body))
        if it in ('ObjectProperty', 'ComponentProperty', 'ClassProperty', 'InterfaceProperty') and len(body) == 4 * n:
            return [self.ref(x) for x in struct.unpack('>%di' % n, body)]
        if it == 'NameProperty' and len(body) == 8 * n:
            return [self.p.fname(r) for _ in range(n)]
        if it == 'ByteProperty':
            if len(body) == n: return list(body)
            if len(body) == 8 * n: return [self.p.fname(r) for _ in range(n)]
        if it == 'BoolProperty' and len(body) in (n, 4 * n):
            step = len(body) // n; return [bool(body[k * step]) for k in range(n)]
        if it == 'StrProperty':
            return [r.fstring() for _ in range(n)]
        if it == 'StructProperty':
            short = (inner.get('struct') or '').rsplit('.', 1)[-1]
            sz = self.struct_size_raw(short)
            if sz and len(body) == sz * n:
                fmt, names = RAW[short]
                vals = [fix_raw(short, list(struct.unpack_from(fmt, body, k * sz))) for k in range(n)]
                return [dict(zip(names, v)) if names else v for v in vals]
            tpath = resolve_type(inner.get('struct'))
            items = []
            for _ in range(n):
                items.append(to_dict(self.tags(r, len(raw), tpath)))
            return items
        # undeclared: keep the old heuristics' safest form
        if len(body) == 4 * n:
            return {'count': n, 'int32': list(struct.unpack('>%di' % n, body))[:4096], 'untyped': True}
        return {'count': n, 'raw': body[:96].hex(), 'len': len(raw), 'untyped': True}

def to_dict(tags):
    d = {}
    for t in tags:
        if 'index' in t or (t['name'] in d and not isinstance(d[t['name']], dict)):
            # static arrays: Name[k]
            cur = d.get(t['name'])
            if not isinstance(cur, dict) or not cur.get('__static__'):
                cur = {'__static__': True, 0: cur} if t['name'] in d else {'__static__': True}
            cur[t.get('index', 0)] = t['value']; d[t['name']] = cur
        else:
            d[t['name']] = t['value']
    for k, v in list(d.items()):
        if isinstance(v, dict) and v.get('__static__'):
            v.pop('__static__'); d[k] = [v.get(i) for i in range(max(v) + 1)] if max(v) < 65536 else v
    return d

def simplify(v):
    """refs -> path strings (for compact JSON output)."""
    if isinstance(v, dict):
        if 'ref' in v and set(v) <= {'ref', 'class'}: return v['ref']
        return {k: simplify(x) for k, x in v.items()}
    if isinstance(v, list): return [simplify(x) for x in v]
    return v
