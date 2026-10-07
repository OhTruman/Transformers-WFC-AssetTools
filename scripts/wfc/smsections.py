"""StaticMesh section -> material binding, read from a specific cooked copy.

Why: umodel's glTF names materials by SHORT name only (e.g. 'SideSupport_MATINST'), and
several packages define materials with the same short name.  Resolving the short name
globally picked the wrong object (ENV_ORB_D1_Debris_p...SideSupport_MATINST for a Streets
column; the cooked Streets copy binds ENV_IAC_Deco_1_p.Material.SideSupport_MATINST).

The authoritative binding is the native FStaticMeshElement array in the StaticMesh export:
  Material (object index i32), EnableCollision (u32 bool), OldEnableCollision (u32 bool),
  bEnableShadowCasting (u32 bool), FirstIndex i32, NumTriangles i32, MinVertexIndex i32,
  MaxVertexIndex i32, MaterialIndex i32, Fragments TArray<(i32 BaseIndex, i32 NumPrimitives)>
(UE3 layout; CONFIRMED for WFC 511/144 by self-consistency: FirstIndex = 3 * sum of previous
NumTriangles, MaterialIndex = 0..n-1 in order, vertex ranges contiguous.)

API: sections(pkg_name, mesh_opath) -> [{'index','material','enable_collision','old_enable_collision',
                                         'cast_shadow','first_index','num_triangles','min_vertex','max_vertex'}]
     Returns the FIRST consistent run of elements (LOD 0).
CLI: python smsections.py <PACKAGE> <StaticMesh opath>
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree  # noqa: E402

def _is_mat(p, v):
    if v == 0: return True
    try:
        c = p.class_name(p.exports[v - 1]) if v > 0 else p.imports[-v - 1]['class']
    except IndexError:
        return False
    return 'Material' in c

def _elem(d, o, allow_empty=False):
    if o + 40 > len(d): return None
    v, a, b, c, fi, nt, mn, mx, mi, nfrag = struct.unpack_from('>10i', d, o)
    if a not in (0, 1) or b not in (0, 1) or c not in (0, 1): return None
    if not (0 <= fi < 10 ** 7 and (0 < nt or (allow_empty and nt == 0)) and nt < 10 ** 7 and 0 <= mn and (mn <= mx or nt == 0) and mx < 10 ** 6 and 0 <= mi < 64 and fi % 3 == 0): return None
    if not (0 <= nfrag < 4096): return None
    return {'material_index_ref': v, 'enable_collision': bool(a), 'old_enable_collision': bool(b), 'cast_shadow': bool(c),
            'first_index': fi, 'num_triangles': nt, 'min_vertex': mn, 'max_vertex': mx, 'index': mi,
            'size': 40 + 8 * nfrag}

def sections(pkg_name, mesh_opath):
    p = objtree.package(pkg_name)
    i = p._idx.get(mesh_opath.lower())
    if not i: return None
    e = p.exports[i - 1]
    d = p.data[e['serial_offset']:e['serial_offset'] + e['serial_size']]
    # the element array is preceded by its int32 count
    for o in range(4, len(d) - 44):
        n = struct.unpack_from('>i', d, o - 4)[0]
        if not 1 <= n <= 64: continue
        el = _elem(d, o, allow_empty=True)   # section 0 can be empty (null-material dummy: Bridge_1536, Corruptor_Body)
        if not el or el['index'] != 0 or el['first_index'] != 0 or not _is_mat(p, el['material_index_ref']): continue
        out, q, tri = [el], o + el['size'], el['num_triangles']
        ok = True
        for k in range(1, n):
            x = _elem(d, q, allow_empty=True)
            # empty sections (NumTriangles 0) store FirstIndex 0 instead of the running offset
            if not x or x['index'] != k or not _is_mat(p, x['material_index_ref']) or \
               x['first_index'] != (3 * tri if x['num_triangles'] else x['first_index']) or \
               (x['num_triangles'] == 0 and x['first_index'] not in (0, 3 * tri)):
                ok = False; break
            out.append(x); q += x['size']; tri += x['num_triangles']
        if not ok or tri == 0: continue         # an all-empty run is not a real element array
        for x in out:
            v = x.pop('material_index_ref'); x.pop('size')
            x['material'] = (p.object_path(v) if v > 0 else p.full_path(v)) if v else None
            x['offset'] = o
        return out
    return []

if __name__ == '__main__':
    import json
    print(json.dumps(sections(sys.argv[1], sys.argv[2]), indent=1))
