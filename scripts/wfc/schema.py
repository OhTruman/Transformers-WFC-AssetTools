"""Authoritative UnrealScript type registry recovered from the cooked script packages.

Every UProperty export's serialized data ends with its type reference (CONFIRMED by
inspection, file ver 511 / licensee 144):
  ObjectProperty/ComponentProperty/InterfaceProperty : last int32 = PropertyClass
  ClassProperty  : last two int32 = PropertyClass, MetaClass
  StructProperty : last int32 = Struct (ScriptStruct)
  ByteProperty   : last int32 = Enum (0 = plain byte)
  ArrayProperty  : last int32 = Inner property (also a child export of the ArrayProperty)
Class/ScriptStruct inheritance = export-table SuperIndex.  Enum value names are the
Enum export's FName array (int32 count + FNames) at the end of its data.

Output: AssetTools/manifests/schema.json
  {"types": {"Engine.Actor": {"kind": "Class", "super": "Core.Object", "props": {...}}, ...},
   "enums": {"Engine.Actor.ENetRole": ["ROLE_None", ...]}}
Each property: {"type": "FloatProperty", "struct"|"class"|"enum"|"inner": ...}
"""
import json, os, sqlite3, struct, sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, extract  # noqa: E402

PROP = ('ByteProperty', 'IntProperty', 'BoolProperty', 'FloatProperty', 'ObjectProperty', 'NameProperty',
        'StrProperty', 'StructProperty', 'ArrayProperty', 'ClassProperty', 'ComponentProperty',
        'InterfaceProperty', 'DelegateProperty', 'MapProperty', 'ScriptMapProperty', 'StringRefProperty')

def scan(pkgname):
    p = ue3pkg.Package(os.path.join(extract.COOKED, pkgname + '.xxx'))
    types, enums = {}, {}
    def path(i): return p.object_path(i) if i > 0 else (p.full_path(i) if i < 0 else None)
    def last(e, n=1):
        d = p.data[e['serial_offset']:e['serial_offset'] + e['serial_size']]
        if len(d) < 4 * n: return [0] * n
        return list(struct.unpack('>%di' % n, d[-4 * n:]))
    def prop_desc(i):
        e = p.exports[i - 1]; c = p.class_name(e); d = {'type': c}
        if c in ('ObjectProperty', 'ComponentProperty', 'InterfaceProperty'):
            d['class'] = path(last(e)[0])
        elif c == 'ClassProperty':
            a, b = last(e, 2); d['class'] = path(a); d['meta_class'] = path(b)
        elif c == 'StructProperty':
            d['struct'] = path(last(e)[0])
        elif c == 'ByteProperty':
            en = last(e)[0]; d['enum'] = path(en) if en else None
        elif c == 'ArrayProperty':
            inner = last(e)[0]
            if inner > 0 and p.class_name(p.exports[inner - 1]) in PROP:
                d['inner'] = prop_desc(inner)
        return d
    owners = {}
    for i, e in enumerate(p.exports):
        c = p.class_name(e)
        if c in ('Class', 'ScriptStruct', 'State', 'Function') and c != 'Function':
            sup = e['super_index']
            types[path(i + 1)] = {'kind': c, 'super': path(sup) if sup else None, 'props': {}, 'source_package': pkgname}
            owners[i + 1] = path(i + 1)
        elif c == 'Enum':
            d = p.data[e['serial_offset']:e['serial_offset'] + e['serial_size']]
            # find the trailing FName array: try count positions from the start
            vals = None
            for off in range(0, min(len(d), 64), 4):
                try:
                    n = struct.unpack_from('>i', d, off)[0]
                    if 0 < n < 512 and off + 4 + 8 * n == len(d):
                        r = ue3pkg.Reader(d, off + 4)
                        vals = [p.fname(r) for _ in range(n)]
                        break
                except Exception:
                    pass
            enums[path(i + 1)] = vals
    for i, e in enumerate(p.exports):
        c = p.class_name(e)
        if c in PROP and e['outer'] in owners:
            types[owners[e['outer']]]['props'][e['name']] = prop_desc(i + 1)
    return types, enums

def main():
    con = sqlite3.connect(os.path.join(extract.MANI, 'inventory.db'))
    # every package holding property definitions; prefer the package owning most of them
    rows = con.execute("SELECT package, COUNT(*) FROM exports WHERE class LIKE '%Property' GROUP BY package").fetchall()
    pkgs = [r[0] for r in sorted(rows, key=lambda r: -r[1])]
    types, enums = {}, {}
    with ProcessPoolExecutor() as ex:
        for t, en in ex.map(scan, pkgs, chunksize=2):
            for k, v in t.items():
                if k not in types or len(v['props']) > len(types[k]['props']): types[k] = v
            for k, v in en.items():
                if v and k not in enums: enums[k] = v
    out = {'types': types, 'enums': enums,
           'provenance': 'CONFIRMED: recovered from cooked UProperty/Class/ScriptStruct/Enum exports (schema.py)'}
    json.dump(out, open(os.path.join(extract.MANI, 'schema.json'), 'w'), indent=0)
    k = defaultdict(int)
    for v in types.values(): k[v['kind']] += 1
    print('types', dict(k), 'props', sum(len(v['props']) for v in types.values()), 'enums', len(enums), 'packages', len(pkgs))

if __name__ == '__main__':
    main()
