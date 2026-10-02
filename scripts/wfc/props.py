"""UE3 tagged-property reader for WFC (ver 511/144, big-endian).

RAW-STRUCT CAVEATS (CONFIRMED 2026-10-01; prefer typed_props.py, which decodes these correctly):
  * Color  -> list of the 4 bytes in on-disk order [B, G, R, A]  (Engine.Default__HUD.RedColor = [0,0,255,255]).
              Reading it as R,G,B swaps red and blue: HeightFog [234,91,116,0] is RGB (116,91,234).
  * Matrix -> 16 floats with each row stored (W, X, Y, Z); use typed_props.fix_raw('Matrix', v).

Object layout observed: int32 NetIndex, then tagged properties terminated by
FName 'None'.  Tag = Name(FName) Type(FName) Size(i32) ArrayIndex(i32)
[+ StructName FName for StructProperty]; BoolProperty value is 4 bytes here.
Values: Object/Class/Component -> resolved object path; Name -> string;
Str -> string; Array -> list of decoded elements when the element type can
be inferred, otherwise raw hex.  Unknown/native tails are left untouched.
"""
import struct
from ue3pkg import Reader

RAW_STRUCTS = {  # immutable/native structs serialized without tags
    'Vector': '>3f', 'Rotator': '>3i', 'Color': '4B', 'LinearColor': '>4f', 'Vector2D': '>2f',
    'Guid': '>4I', 'Quat': '>4f', 'Vector4': '>4f', 'IntPoint': '>2i', 'Plane': '>4f',
    'Box': '>6fB', 'Matrix': '>16f', 'TwoVectors': '>6f',
}

class PropReader:
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

    def read_object(self, export_index, max_props=4000):
        e = self.p.exports[export_index - 1]
        end = e['serial_offset'] + e['serial_size']
        # NetIndex (4); components additionally carry TemplateOwnerClass (4)
        # [+ TemplateName FName (8)] before their tags.
        err = None
        # objects with RF_HasStack: FStateFrame (26 bytes) precedes NetIndex
        for skip in (4, 8, 16, 30, 0):
            r = Reader(self.p.data, e['serial_offset'] + skip)
            try:
                props = self.read_tags(r, end, max_props)
                return props, r.p - e['serial_offset']
            except Exception as ex:
                err = ex
        raise err

    def read_tags(self, r, end, max_props=4000):
        out = []
        for _ in range(max_props):
            if r.p + 8 > end: break
            name = self.p.fname(r)
            if name == 'None': break
            ptype = self.p.fname(r)
            size = r.i32(); aidx = r.i32()
            sname = self.p.fname(r) if ptype == 'StructProperty' else None
            start = r.p
            if ptype == 'BoolProperty':
                val = bool(r.u32()); size = 0
            else:
                if size < 0 or start + size > end:
                    raise ValueError('bad property size %s %s %d' % (name, ptype, size))
                val = self.value(ptype, sname, self.p.data[start:start + size], name)
                r.p = start + size
            item = {'name': name, 'type': ptype, 'value': val}
            if aidx: item['index'] = aidx
            if sname: item['struct'] = sname
            out.append(item)
        return out

    def value(self, ptype, sname, raw, name):
        r = Reader(raw)
        try:
            if ptype in ('ObjectProperty', 'ClassProperty', 'ComponentProperty', 'InterfaceProperty'):
                return self.ref(r.i32())
            if ptype == 'IntProperty': return r.i32()
            if ptype == 'FloatProperty': return struct.unpack('>f', raw[:4])[0]
            if ptype == 'NameProperty': return self.p.fname(r)
            if ptype == 'ByteProperty':
                return raw[0] if len(raw) == 1 else self.p.fname(r)
            if ptype == 'StrProperty': return r.fstring()
            if ptype == 'StructProperty':
                if sname in RAW_STRUCTS and struct.calcsize(RAW_STRUCTS[sname]) == len(raw):
                    return list(struct.unpack(RAW_STRUCTS[sname], raw))
                return self.read_tags(Reader(self.p.data, 0), 0) if False else self._struct(raw)
            if ptype == 'ArrayProperty':
                return self._array(raw, name)
        except Exception as ex:
            return {'raw': raw[:64].hex(), 'error': str(ex)}
        return {'raw': raw[:64].hex(), 'len': len(raw)}

    def _struct(self, raw):
        sub = PropReaderSlice(self, raw)
        try:
            return sub.tags()
        except Exception:
            return {'raw': raw[:64].hex(), 'len': len(raw)}

    def _array(self, raw, name):
        r = Reader(raw)
        n = r.i32()
        if n == 0: return []
        body = len(raw) - 4
        # array of object refs (4 bytes each) -- most common for references
        if body == 4 * n:
            vals = [r.i32() for _ in range(n)]
            refs = [self.ref(v) for v in vals]
            if all(x is None or 'ref' in x for x in refs):
                return refs
            return vals
        # array of FNames (8 bytes each), e.g. AnimSet.TrackBoneNames
        if body == 8 * n:
            names = [self.p.fname(r) for _ in range(n)]
            if not any(x.startswith('?') for x in names):
                return names
            r = Reader(raw, 4)
        # array of tagged structs
        sub = PropReaderSlice(self, raw[4:])
        items = []
        try:
            for _ in range(n):
                items.append(sub.tags())
            if sub.r.p == len(raw) - 4:
                return items
        except Exception:
            pass
        return {'count': n, 'raw': raw[4:68].hex(), 'len': len(raw)}

class PropReaderSlice:
    """Read tagged properties from a detached byte slice (struct/array bodies)."""
    def __init__(self, parent, raw):
        self.parent = parent; self.raw = raw; self.r = Reader(raw)
    def tags(self):
        pr = self.parent
        saved = pr.p.data
        # temporarily point the package reader at the slice
        class _P: pass
        out = []
        r = self.r
        while r.p + 8 <= len(self.raw):
            name = pr.p.fname(r)
            if name == 'None': return out
            ptype = pr.p.fname(r); size = r.i32(); aidx = r.i32()
            sname = pr.p.fname(r) if ptype == 'StructProperty' else None
            if ptype == 'BoolProperty':
                val = bool(r.u32())
            else:
                if size < 0 or r.p + size > len(self.raw): raise ValueError('bad nested size')
                val = pr.value(ptype, sname, self.raw[r.p:r.p + size], name); r.p += size
            item = {'name': name, 'type': ptype, 'value': val}
            if aidx: item['index'] = aidx
            if sname: item['struct'] = sname
            out.append(item)
        raise ValueError('unterminated struct')

def props_dict(props):
    """Flatten a tag list to {name: value} (arrays of same name -> list)."""
    d = {}
    for p in props:
        if 'index' in p:
            d.setdefault(p['name'], {})
            if isinstance(d[p['name']], dict): d[p['name']][p['index']] = p['value']
        elif p['name'] in d:
            continue
        else:
            d[p['name']] = p['value']
    return d
