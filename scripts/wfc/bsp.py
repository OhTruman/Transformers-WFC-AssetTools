"""UE3 BSP (class Model) reader for WFC 511/144 + polygon builder.

Native layout after the (empty) tagged-property block, established from the data:
  FBoxSphereBounds (28)
  Vectors  bulk: i32 elemsize(12), i32 count, FVector[]          (normals / texture axes)
  Points   bulk: elemsize 12                                      (vertex positions)
  Nodes    bulk: elemsize 64  FBspNode = Plane(4f) iVertPool iSurf iVertexIndex
                 u16 ComponentIndex u16 ComponentNodeIndex i32 ComponentElementIndex
                 iBack iFront iPlane iCollisionBound u8 iZone[2] u8 NumVertices u8 NodeFlags
                 i32 iLeaf[2]
  Surfs    i32 owner(obj ref) i32 count, FBspSurf(56) = Material(obj) PolyFlags pBase vNormal
                 vTextureU vTextureV iBrushPoly Actor(obj) Plane(4f) ShadowMapScale LightingChannels
  Verts    bulk: FVert = pVertex iSide [ShadowTexCoord ...]
UV convention as UE3 model rendering: u = ((P - Points[pBase]) . TextureU) / 128.
"""
import struct
import numpy as np
from ue3pkg import Reader
import props

PF_INVISIBLE = 0x00000001
PF_MASKED = 0x00000002
PF_TRANSLUCENT = 0x00000004
PF_NOTSOLID = 0x00000008
PF_TWOSIDED = 0x00000100
PF_PORTAL = 0x04000000

def _bulk(r, dtype_fields, expect=None):
    es = r.i32(); n = r.i32()
    if expect and es != expect:
        raise ValueError('unexpected element size %d (expected %d)' % (es, expect))
    raw = r.d[r.p:r.p + es * n]; r.p += es * n
    return es, n, raw

def read_model(pkg, index):
    e = pkg.exports[index - 1]
    pr = props.PropReader(pkg)
    _, used = pr.read_object(index)
    r = Reader(pkg.data, e['serial_offset'] + used)
    bounds = struct.unpack_from('>7f', pkg.data, r.p); r.p += 28
    _, nv, raw = _bulk(r, None, 12); vectors = np.frombuffer(raw, '>f4').reshape(nv, 3).astype('f8')
    _, npnt, raw = _bulk(r, None, 12); points = np.frombuffer(raw, '>f4').reshape(npnt, 3).astype('f8')
    es, nn, raw = _bulk(r, None, 64)
    ndt = np.dtype([('plane', '>f4', 4), ('iVertPool', '>i4'), ('iSurf', '>i4'), ('iVertexIndex', '>i4'),
                    ('comp', '>u2'), ('compnode', '>u2'), ('compelem', '>i4'), ('iBack', '>i4'), ('iFront', '>i4'),
                    ('iPlane', '>i4'), ('iCollisionBound', '>i4'), ('iZone', 'u1', 2), ('NumVertices', 'u1'),
                    ('NodeFlags', 'u1'), ('iLeaf', '>i4', 2)])
    nodes = np.frombuffer(raw, ndt)
    owner = r.i32(); ns = r.i32()
    sdt = np.dtype([('Material', '>i4'), ('PolyFlags', '>u4'), ('pBase', '>i4'), ('vNormal', '>i4'),
                    ('vTextureU', '>i4'), ('vTextureV', '>i4'), ('iBrushPoly', '>i4'), ('Actor', '>i4'),
                    ('Plane', '>f4', 4), ('ShadowMapScale', '>f4'), ('LightingChannels', '>u4')])
    surfs = np.frombuffer(pkg.data[r.p:r.p + 56 * ns], sdt); r.p += 56 * ns
    ves, nvt, raw = _bulk(r, None)
    vdt = np.dtype([('pVertex', '>i4'), ('iSide', '>i4'), ('rest', 'u1', ves - 8)]) if ves > 8 else \
        np.dtype([('pVertex', '>i4'), ('iSide', '>i4')])
    verts = np.frombuffer(raw, vdt)
    return {'bounds': bounds, 'vectors': vectors, 'points': points, 'nodes': nodes, 'surfs': surfs,
            'verts': verts, 'vert_elem_size': ves, 'end_offset': r.p - e['serial_offset'],
            'serial_size': e['serial_size']}

def validate(m):
    n, s, v, p = m['nodes'], m['surfs'], m['verts'], m['points']
    issues = []
    used = n[n['NumVertices'] > 0]
    if len(used) and (used['iVertPool'].max() + 0 >= len(v) or used['iVertPool'].min() < 0): issues.append('iVertPool out of range')
    if len(used) and (used['iSurf'].max() >= len(s) or used['iSurf'].min() < 0): issues.append('iSurf out of range')
    if len(v) and (v['pVertex'].max() >= len(p) or v['pVertex'].min() < 0): issues.append('pVertex out of range')
    return issues

def polygons(m):
    """Yield (surf_index, [point xyz...]) for every BSP node with vertices."""
    for node in m['nodes']:
        k = int(node['NumVertices'])
        if k < 3: continue
        vp = int(node['iVertPool'])
        idx = m['verts']['pVertex'][vp:vp + k]
        yield int(node['iSurf']), m['points'][idx], node
