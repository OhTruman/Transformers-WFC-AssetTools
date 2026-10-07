"""CPU skinned pose preview (QA only, no GPU): robot.glb + one animation frame -> PNG (front + side, flat-shaded)

  python pose_preview.py <glb> <out.png> <clip>[@t] [<clip>[@t] ...]

Linear-blend skinning with the glb's inverse bind matrices; animation sampled linearly (rotation slerp-free nlerp is fine for QA).
"""
import json, struct, sys
import numpy as np
from PIL import Image, ImageDraw

def read_glb(p):
    b = open(p, 'rb').read(); o = 12; j = None; bins = []
    while o < len(b):
        ln, ty = struct.unpack_from('<II', b, o); o += 8
        if ty == 0x4E4F534A: j = json.loads(b[o:o + ln])
        else: bins.append(b[o:o + ln])
        o += ln
    return j, bins

def acc(j, bins, i):
    a = j['accessors'][i]; v = j['bufferViews'][a['bufferView']]
    n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
    dt = {5126: '<f4', 5125: '<u4', 5123: '<u2', 5121: 'u1'}[a['componentType']]
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0); st = v.get('byteStride')
    buf = bins[v.get('buffer', 0)]; isz = np.dtype(dt).itemsize
    if st and st != isz * n:
        return np.array([np.frombuffer(buf, dt, n, off + k * st) for k in range(a['count'])])
    r = np.frombuffer(buf, dt, a['count'] * n, off)
    return r.reshape(a['count'], n) if n > 1 else r

def q2m(q):
    x, y, z, w = q / max(np.linalg.norm(q), 1e-12)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])

def sample(j, bins, anim, t):
    pose = {}
    for ch in anim['channels']:
        s = anim['samplers'][ch['sampler']]; tin = acc(j, bins, s['input']); out = acc(j, bins, s['output'])
        k = int(np.searchsorted(tin, t)); k = min(max(k, 1), len(tin) - 1)
        a = (t - tin[k - 1]) / max(tin[k] - tin[k - 1], 1e-9); a = min(max(a, 0), 1)
        v = out[k - 1] * (1 - a) + out[k] * a
        pose.setdefault(ch['target']['node'], {})[ch['target']['path']] = v
    return pose

def world_mats(j, pose):
    N = len(j['nodes']); W = [None] * N
    parent = {c: i for i, n in enumerate(j['nodes']) for c in n.get('children', [])}
    def local(i):
        n = j['nodes'][i]; p = pose.get(i, {})
        if 'matrix' in n and not p: return np.array(n['matrix']).reshape(4, 4).T
        t = p.get('translation', n.get('translation', [0, 0, 0])); r = p.get('rotation', n.get('rotation', [0, 0, 0, 1]))
        s = p.get('scale', n.get('scale', [1, 1, 1]))
        L = np.eye(4); L[:3, :3] = q2m(np.array(r)) @ np.diag(s); L[:3, 3] = t; return L
    def w(i):
        if W[i] is None: W[i] = (w(parent[i]) if i in parent else np.eye(4)) @ local(i)
        return W[i]
    for i in range(N): w(i)
    return W

def skin(j, bins, pose):
    W = world_mats(j, pose); sk = j['skins'][0]
    ib = acc(j, bins, sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
    JM = np.array([W[jt] @ ib[k] for k, jt in enumerate(sk['joints'])])
    tris = []
    for m in j['meshes']:
        for p in m['primitives']:
            P = acc(j, bins, p['attributes']['POSITION']).astype('f8')
            Jn = acc(j, bins, p['attributes']['JOINTS_0']).astype(int); Wt = acc(j, bins, p['attributes']['WEIGHTS_0']).astype('f8')
            Wt = Wt / np.maximum(Wt.sum(1, keepdims=True), 1e-9)
            Ph = np.c_[P, np.ones(len(P))]
            out = np.zeros((len(P), 3))
            for c in range(4): out += Wt[:, c:c + 1] * np.einsum('nij,nj->ni', JM[Jn[:, c]], Ph)[:, :3]
            I = acc(j, bins, p['indices']).astype(int).reshape(-1, 3)
            tris.append(out[I])
    return np.concatenate(tris)

def draw(T, view, size):
    ax = {'front': (0, 1, 2), 'side': (2, 1, 0)}[view]
    X = T[:, :, ax[0]]; Y = T[:, :, ax[1]]; Z = T[:, :, ax[2]]
    lo = np.array([X.min(), Y.min()]); hi = np.array([X.max(), Y.max()]); sc = (size - 20) / max(hi - lo)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    shade = np.abs(n[:, ax[2]]) * 0.8 + 0.2
    im = Image.new('RGB', (size, size), (24, 26, 30)); d = ImageDraw.Draw(im)
    for k in np.argsort(Z.mean(1) * (1 if view == 'front' else -1)):
        pts = [(10 + (X[k, i] - lo[0]) * sc, size - 10 - (Y[k, i] - lo[1]) * sc) for i in range(3)]
        c = int(60 + 180 * shade[k]); d.polygon(pts, fill=(c, int(c * 0.9), int(c * 0.75)))
    return im

def main():
    glb, out, clips = sys.argv[1], sys.argv[2], sys.argv[3:]
    j, bins = read_glb(glb)
    tiles = []
    for c in clips:
        name, _, t = c.partition('@')
        anim = next((a for a in j.get('animations', []) if a['name'] == name), None)
        if anim is None: print('no clip', name); continue
        dur = max(float(acc(j, bins, s['input']).max()) for s in anim['samplers'])
        tt = float(t) * dur if t else 0.5 * dur
        T = skin(j, bins, sample(j, bins, anim, tt))
        a = draw(T, 'front', 256); b = draw(T, 'side', 256)
        tile = Image.new('RGB', (512, 276), (10, 10, 12)); tile.paste(a, (0, 20)); tile.paste(b, (256, 20))
        ImageDraw.Draw(tile).text((4, 4), '%s @%.2fs  %s' % (name, tt, (anim.get('extras') or {}).get('retargeted_from', 'original')), fill=(255, 255, 255))
        tiles.append(tile)
    sheet = Image.new('RGB', (512 * 2, 276 * ((len(tiles) + 1) // 2)), (0, 0, 0))
    for i, t in enumerate(tiles): sheet.paste(t, ((i % 2) * 512, (i // 2) * 276))
    sheet.save(out); print('wrote', out)

if __name__ == '__main__':
    main()
