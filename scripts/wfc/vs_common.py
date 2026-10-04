"""Shared helpers for the vertical-slice builders.

Coordinate convention (identical to umodel's glTF mesh export, so extracted meshes,
animations and maps line up):  glTF = Y-up, metres;  v_gltf = 0.01 * (x, z, y)_UE.
UE transforms are row-vector (p' = p*M); converted with G = C * M^T * C^-1,
C = diag(0.01*S, 1), S = swap(Y,Z).
"""
import json, math, os, struct, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract  # noqa: E402

ROOT = os.path.dirname(extract.OUT)                 # ExtractedAssets
VS = os.path.join(ROOT, 'VerticalSlice')
URU = 2 * math.pi / 65536.0

S3 = np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], dtype='f8')
C4 = np.eye(4); C4[:3, :3] = 0.01 * S3
C4i = np.linalg.inv(C4)

def ue_rot(pitch, yaw, roll):
    """UE3 FRotationMatrix (row-vector, rows = axes)."""
    sp, cp = math.sin(pitch * URU), math.cos(pitch * URU)
    sy, cy = math.sin(yaw * URU), math.cos(yaw * URU)
    sr, cr = math.sin(roll * URU), math.cos(roll * URU)
    M = np.eye(4)
    M[0, :3] = [cp * cy, cp * sy, sp]
    M[1, :3] = [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp]
    M[2, :3] = [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp]
    return M

def ue_scale(s3):
    M = np.eye(4); M[0, 0], M[1, 1], M[2, 2] = s3; return M

def ue_trans(t):
    M = np.eye(4); M[3, :3] = t; return M

def ue_actor_matrix(loc=(0, 0, 0), rot=(0, 0, 0), draw_scale=1.0, scale3=(1, 1, 1), prepivot=(0, 0, 0)):
    s = [draw_scale * x for x in scale3]
    return ue_trans([-p for p in prepivot]) @ ue_scale(s) @ ue_rot(*rot) @ ue_trans(loc)

def ue_to_gltf_matrix(M):
    """UE row-vector matrix -> glTF column-major 16-list."""
    G = C4 @ M.T @ C4i
    return [float(x) for x in G.T.reshape(-1)]

def ue_points_to_gltf(P):
    P = np.asarray(P, dtype='f8')
    return np.stack([P[:, 0], P[:, 2], P[:, 1]], 1) * 0.01

def rel(path, start):
    return os.path.relpath(path, start).replace('\\', '/')

# ------------------------------------------------------------------ glTF reading
CT = {5126: 'f4', 5125: 'u4', 5123: 'u2', 5121: 'u1', 5122: 'i2', 5120: 'i1'}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

def load_gltf(path):
    g = json.load(open(path, encoding='utf-8'))
    bins = [open(os.path.join(os.path.dirname(path), b['uri']), 'rb').read() for b in g.get('buffers', [])]
    return g, bins

def accessor(g, bins, i):
    a = g['accessors'][i]; v = g['bufferViews'][a['bufferView']]
    n = NC[a['type']]; dt = np.dtype('<' + CT[a['componentType']])
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = v.get('byteStride')
    buf = bins[v['buffer']]
    if stride and stride != dt.itemsize * n:
        rows = [np.frombuffer(buf, dt, n, off + k * stride) for k in range(a['count'])]
        return np.array(rows)
    return np.frombuffer(buf, dt, a['count'] * n, off).reshape(a['count'], n) if n > 1 else \
        np.frombuffer(buf, dt, a['count'], off)

# ------------------------------------------------------------------ GLB writing
class GLB:
    def __init__(self, generator='AssetTools vertical slice'):
        self.j = {'asset': {'version': '2.0', 'generator': generator}, 'scene': 0, 'scenes': [{'nodes': []}],
                  'nodes': [], 'meshes': [], 'materials': [], 'accessors': [], 'bufferViews': [],
                  'buffers': [{'byteLength': 0}], 'images': [], 'textures': [], 'samplers': [{}]}
        self.bin = bytearray(); self._img = {}; self._mat = {}

    def view(self, data, target=None):
        while len(self.bin) % 4: self.bin.append(0)
        v = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target: v['target'] = target
        self.bin.extend(data); self.j['bufferViews'].append(v)
        return len(self.j['bufferViews']) - 1

    def acc(self, arr, kind, minmax=False, target=None):
        arr = np.ascontiguousarray(arr)
        ct = {np.dtype('float32'): 5126, np.dtype('uint32'): 5125, np.dtype('uint16'): 5123,
              np.dtype('uint8'): 5121}[arr.dtype]
        a = {'bufferView': self.view(arr.astype(arr.dtype.newbyteorder('<')).tobytes(), target),
             'componentType': ct, 'count': int(arr.shape[0]), 'type': kind}
        if minmax:
            a['min'] = [float(x) for x in np.atleast_1d(arr.min(0))]
            a['max'] = [float(x) for x in np.atleast_1d(arr.max(0))]
        self.j['accessors'].append(a); return len(self.j['accessors']) - 1

    def texture(self, uri):
        if uri in self._img: return self._img[uri]
        self.j['images'].append({'uri': uri})
        self.j['textures'].append({'source': len(self.j['images']) - 1, 'sampler': 0})
        self._img[uri] = len(self.j['textures']) - 1
        return self._img[uri]

    def material(self, key, mat):
        if key in self._mat: return self._mat[key]
        self.j['materials'].append(mat); self._mat[key] = len(self.j['materials']) - 1
        return self._mat[key]

    def mesh(self, name, prims):
        self.j['meshes'].append({'name': name, 'primitives': prims}); return len(self.j['meshes']) - 1

    def node(self, n, root=True):
        self.j['nodes'].append(n); i = len(self.j['nodes']) - 1
        if root: self.j['scenes'][0]['nodes'].append(i)
        return i

    def write(self, path):
        j = {k: v for k, v in self.j.items() if v != [] and v != [{}]}
        if 'textures' in j: j['samplers'] = self.j['samplers']
        j['buffers'] = [{'byteLength': len(self.bin)}]
        js = json.dumps(j, separators=(',', ':')).encode()
        js += b' ' * ((4 - len(js) % 4) % 4)
        b = bytes(self.bin) + b'\0' * ((4 - len(self.bin) % 4) % 4)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(b)))
            f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
            f.write(struct.pack('<II', len(b), 0x004E4942)); f.write(b)

def read_glb(path):
    d = open(path, 'rb').read()
    magic, ver, length = struct.unpack_from('<III', d, 0)
    assert magic == 0x46546C67 and ver == 2 and length == len(d), 'bad GLB header'
    jl, jt = struct.unpack_from('<II', d, 12); j = json.loads(d[20:20 + jl])
    o = 20 + jl; bl, bt = struct.unpack_from('<II', d, o)
    return j, [d[o + 8:o + 8 + bl]]

def pbr_material(name, roles, glb_dir, extras=None, double_sided=False, blend='OPAQUE', base_override=None):
    """glTF PBR approximation of a resolved WFC material (texture URIs relative to the GLB)."""
    m = {'name': name, 'pbrMetallicRoughness': {'metallicFactor': 0.0, 'roughnessFactor': 0.6}}
    def uri(f): return rel(os.path.join(ROOT, f), glb_dir)
    bc = base_override or (roles.get('base_color') or {}).get('file')
    if bc: m['pbrMetallicRoughness']['baseColorTexture'] = {'index': None, '_uri': uri(bc) if not os.path.isabs(bc) else rel(bc, glb_dir)}
    else: m['pbrMetallicRoughness']['baseColorFactor'] = [0.5, 0.5, 0.5, 1.0]
    if (roles.get('normal') or {}).get('file'):
        m['normalTexture'] = {'index': None, '_uri': uri(roles['normal']['file'])}
    if (roles.get('emissive') or {}).get('file') and roles['emissive'].get('role_source') == 'graph':
        m['emissiveTexture'] = {'index': None, '_uri': uri(roles['emissive']['file'])}
        m['emissiveFactor'] = [1.0, 1.0, 1.0]
    if double_sided: m['doubleSided'] = True
    if blend != 'OPAQUE': m['alphaMode'] = blend
    if blend == 'MASK': m['alphaCutoff'] = 0.33
    if extras: m['extras'] = extras
    return m

def bind_textures(glb, m):
    for slot in (m.get('pbrMetallicRoughness', {}).get('baseColorTexture'), m.get('normalTexture'), m.get('emissiveTexture')):
        if slot and '_uri' in slot:
            slot['index'] = glb.texture(slot.pop('_uri'))
    return m

BLEND = {'BLEND_Opaque': 'OPAQUE', 'BLEND_Masked': 'MASK', 'BLEND_Translucent': 'BLEND',
         'BLEND_Additive': 'BLEND', 'BLEND_Modulate': 'BLEND'}


def map_sublevels(map_name, A):
    """every level of a map: name-prefix levels in authored.db + streamed sublevels vs_map exported (map.json; authored
    LevelStreaming - Seed MP_IAC_Global_Art_m, Debris MP_ORB_Art_m / MP_ORB_Audio_m, GLB_Audio_m). Sorted."""
    subs = {r['opath'].split('.')[0] for r in A.find(map_name + '_%.TheWorld', 'World')}
    mj = os.path.join(VS, 'Maps', map_name, 'map.json')
    if os.path.exists(mj):
        subs |= set(json.load(open(mj, encoding='utf-8')).get('sublevels') or [])
    return sorted(subs)
