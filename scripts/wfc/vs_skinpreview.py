"""Skinned + textured preview of a character GLB at an animation time (validation).

Evaluates glTF node TRS with the clip's channels (linear / nlerp), builds joint
matrices, applies inverseBindMatrices + JOINTS_0/WEIGHTS_0 skinning on the CPU,
samples base-colour textures at triangle UV centroids and rasterises front/side views.
  python vs_skinpreview.py robot.glb out.png [--clip NAME --t 0.5 (fraction)]
Prints pose statistics (bounding box, skinned extent) used by vs_validate.py.
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import read_glb, accessor  # noqa: E402
from vs_preview import raster  # noqa: E402

def quat_mat(q):
    x, y, z, w = q / (np.linalg.norm(q) or 1)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])

def node_local(n, over):
    t = np.array(over.get('translation', n.get('translation', [0, 0, 0])), 'f8')
    r = np.array(over.get('rotation', n.get('rotation', [0, 0, 0, 1])), 'f8')
    s = np.array(n.get('scale', [1, 1, 1]), 'f8')
    M = np.eye(4); M[:3, :3] = quat_mat(r) * s; M[:3, 3] = t
    if 'matrix' in n: M = np.array(n['matrix']).reshape(4, 4).T
    return M

def sample(j, bins, anim, frac):
    over = {}
    for ch in anim['channels']:
        s = anim['samplers'][ch['sampler']]
        T = accessor(j, bins, s['input']); V = accessor(j, bins, s['output'])
        t = T[0] + frac * (T[-1] - T[0])
        k = int(np.clip(np.searchsorted(T, t) - 1, 0, len(T) - 1)); k2 = min(k + 1, len(T) - 1)
        a = 0 if k2 == k else (t - T[k]) / (T[k2] - T[k])
        v = V[k] * (1 - a) + V[k2] * a
        over.setdefault(ch['target']['node'], {})[ch['target']['path']] = v
    return over

def pose(path, clip=None, frac=0.0, drop_translation=()):
    j, bins = read_glb(path)
    over = {}
    if clip:
        anim = next(a for a in j['animations'] if a['name'] == clip)
        over = sample(j, bins, anim, frac)
        names = {n.get('name'): i for i, n in enumerate(j['nodes'])}
        for b in drop_translation:
            over.get(names.get(b), {}).pop('translation', None)
    parent = {}
    for i, n in enumerate(j['nodes']):
        for c in n.get('children', []): parent[c] = i
    world = {}
    def W(i):
        if i not in world:
            L = node_local(j['nodes'][i], over.get(i, {}))
            world[i] = W(parent[i]) @ L if i in parent else L
        return world[i]
    skin = j['skins'][0]
    ibm = accessor(j, bins, skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
    J = np.array([W(jn) @ ibm[k] for k, jn in enumerate(skin['joints'])])
    tris, uvs, mats = [], [], []
    for n in j['nodes']:
        if 'mesh' not in n: continue
        for p in j['meshes'][n['mesh']]['primitives']:
            at = p['attributes']
            P = accessor(j, bins, at['POSITION']).astype('f8')
            if 'JOINTS_0' in at:
                ji = accessor(j, bins, at['JOINTS_0']).astype('i8'); wt = accessor(j, bins, at['WEIGHTS_0']).astype('f8')
                if wt.max() > 1.5: wt = wt / 255.0
                Ph = np.c_[P, np.ones(len(P))]
                out = np.zeros((len(P), 4))
                for k in range(4):
                    out += wt[:, k:k + 1] * np.einsum('nij,nj->ni', J[ji[:, k]], Ph)
                P = out[:, :3]
            I = accessor(j, bins, p['indices']).astype('i8').reshape(-1, 3)
            tris.append(P[I]); mats.append(np.full(len(I), p.get('material', 0)))
            uv = accessor(j, bins, at['TEXCOORD_0']).astype('f8') if 'TEXCOORD_0' in at else np.zeros((len(P), 2))
            uvs.append(uv[I].mean(1))
    return j, np.concatenate(tris), np.concatenate(uvs), np.concatenate(mats)

def colours(j, path, uvs, mats):
    base = os.path.dirname(path); cache = {}; C = np.full((len(uvs), 3), 0.6)
    for mi in np.unique(mats):
        m = j['materials'][mi]; t = m.get('pbrMetallicRoughness', {}).get('baseColorTexture')
        if t is None: continue
        uri = j['images'][j['textures'][t['index']]['source']]['uri']
        im = np.asarray(Image.open(os.path.join(base, uri)).convert('RGB'), 'f8') / 255
        sel = mats == mi; h, w = im.shape[:2]
        u = np.mod(uvs[sel, 0], 1) * (w - 1); v = np.mod(uvs[sel, 1], 1) * (h - 1)
        C[sel] = im[v.astype(int), u.astype(int)]
    return C

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('glb'); ap.add_argument('out')
    ap.add_argument('--clip'); ap.add_argument('--t', type=float, default=0.0); ap.add_argument('--size', type=int, default=600)
    a = ap.parse_args()
    j, T, uvs, mats = pose(a.glb, a.clip, a.t)
    C = colours(j, a.glb, uvs, mats)
    lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    span = (hi - lo).max() * 1.1; c = (lo + hi) / 2; size = a.size
    views = []
    for axis in ('front', 'side'):
        def proj(T, axis=axis):
            h = T[..., 0] if axis == 'front' else T[..., 2]
            d = T[..., 2] if axis == 'front' else -T[..., 0]
            hc = c[0] if axis == 'front' else c[2]
            return np.stack([(h - hc) / span * size + size / 2, (c[1] - T[..., 1]) / span * size + size / 2, 1e3 - d], -1)
        img, _ = raster(T, C, size, proj); views.append(img)
    Image.fromarray(np.concatenate(views, 1)).save(a.out)
    print(json.dumps({'clip': a.clip, 't': a.t, 'triangles': int(len(T)), 'bbox_min': lo.round(3).tolist(),
                      'bbox_max': hi.round(3).tolist(), 'height_m': round(float(hi[1] - lo[1]), 3)}))

if __name__ == '__main__':
    main()
