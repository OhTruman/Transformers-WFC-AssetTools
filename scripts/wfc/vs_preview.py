"""Software preview renderer for validation (no GPU / external viewer needed).

Flattens a GLB (node matrices x mesh primitives) to world triangles, shades by
normal x material average texture colour, z-buffered rasterisation in numpy.
  python vs_preview.py world.glb out.png [--top] [--eye x y z --look x y z] [--size 1024]
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import read_glb, accessor  # noqa: E402

TEXTURED = '--textured' in sys.argv

def world_triangles(path):
    j, bins = read_glb(path)
    base = os.path.dirname(path)
    mcol = []
    for m in j.get('materials', []):
        c = np.array([0.6, 0.6, 0.6])
        t = m.get('pbrMetallicRoughness', {}).get('baseColorTexture')
        if t is not None:
            try:
                uri = j['images'][j['textures'][t['index']]['source']]['uri']
                im = Image.open(os.path.join(base, uri)).convert('RGB').resize((16, 16))
                c = np.asarray(im, 'f8').reshape(-1, 3).mean(0) / 255
            except Exception:
                pass
        elif 'baseColorFactor' in m.get('pbrMetallicRoughness', {}):
            c = np.array(m['pbrMetallicRoughness']['baseColorFactor'][:3])
        mcol.append(c)
    texc = {}
    def tex(mi):
        if mi in texc: return texc[mi]
        im = None
        t = j['materials'][mi].get('pbrMetallicRoughness', {}).get('baseColorTexture') if mi is not None else None
        if t is not None:
            try:
                uri = j['images'][j['textures'][t['index']]['source']]['uri']
                im = np.asarray(Image.open(os.path.join(base, uri)).convert('RGB').resize((256, 256)), 'f8') / 255
            except Exception: im = None
        texc[mi] = im; return im
    tris, cols = [], []
    for n in j['nodes']:
        if 'mesh' not in n: continue
        M = np.array(n['matrix']).reshape(4, 4).T if 'matrix' in n else np.eye(4)
        for p in j['meshes'][n['mesh']]['primitives']:
            P = accessor(j, bins, p['attributes']['POSITION']).astype('f8')
            I = accessor(j, bins, p['indices']).astype('i8') if 'indices' in p else np.arange(len(P))
            W = (np.c_[P, np.ones(len(P))] @ M.T)[:, :3]
            T = W[I.reshape(-1, 3)]
            tris.append(T)
            col = np.repeat(mcol[p['material']][None] if 'material' in p and mcol else np.array([[0.6, 0.6, 0.6]]), len(T), 0)
            im = tex(p.get('material')) if TEXTURED and 'TEXCOORD_0' in p['attributes'] else None
            if im is not None:
                uv = accessor(j, bins, p['attributes']['TEXCOORD_0']).astype('f8')[I.reshape(-1, 3)].mean(1)
                u = (np.mod(uv[:, 0], 1) * 255).astype(int); v = (np.mod(uv[:, 1], 1) * 255).astype(int)
                col = im[v, u]
            cols.append(col)
    return np.concatenate(tris), np.concatenate(cols)

def raster(T, C, size, proj):
    """proj: (N,3,3) world -> screen x,y,depth (smaller depth = nearer)."""
    S = proj(T)
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    light = np.array([0.4, 0.8, 0.3]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.abs(nrm @ light)
    img = np.zeros((size, size, 3)) + np.array([0.08, 0.09, 0.12])
    z = np.full((size, size), np.inf)
    ok = np.all(np.isfinite(S), axis=(1, 2)) & np.all(S[:, :, 2] > 0, axis=1)
    order = np.argsort(-S[ok][:, :, 2].mean(1))
    for t, col in zip(S[ok][order], (C[ok] * shade[ok][:, None])[order]):
        x0, x1 = int(max(0, np.floor(t[:, 0].min()))), int(min(size - 1, np.ceil(t[:, 0].max())))
        y0, y1 = int(max(0, np.floor(t[:, 1].min()))), int(min(size - 1, np.ceil(t[:, 1].max())))
        if x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9: continue
        w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
        w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any(): continue
        depth = w0 * az + w1 * bz + w2 * cz
        sub = z[y0:y1 + 1, x0:x1 + 1]
        upd = inside & (depth < sub)
        sub[upd] = depth[upd]
        img[y0:y1 + 1, x0:x1 + 1][upd] = np.clip(col, 0, 1)
    return (img * 255).astype('u1'), np.isfinite(z).mean()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('glb'); ap.add_argument('out')
    ap.add_argument('--size', type=int, default=1024)
    ap.add_argument('--textured', action='store_true')
    ap.add_argument('--top', action='store_true')
    ap.add_argument('--eye', nargs=3, type=float); ap.add_argument('--look', nargs=3, type=float)
    ap.add_argument('--fov', type=float, default=70)
    ap.add_argument('--bounds', nargs=4, type=float, help='xmin zmin xmax zmax for top view')
    ap.add_argument('--clip-y', type=float, help='drop triangles whose min y is above this')
    ap.add_argument('--points', help='json list of [x,y,z] to mark (top view)')
    a = ap.parse_args()
    T, C = world_triangles(a.glb)
    if a.clip_y is not None:
        keep = T[:, :, 1].min(1) < a.clip_y; T, C = T[keep], C[keep]
    size = a.size
    if a.top:
        if a.bounds: x0, z0, x1, z1 = a.bounds
        else:
            lo, hi = np.percentile(T.reshape(-1, 3), [1, 99], axis=0); x0, z0, x1, z1 = lo[0], lo[2], hi[0], hi[2]
        span = max(x1 - x0, z1 - z0)
        def proj(T):
            return np.stack([(T[..., 0] - x0) / span * size, (T[..., 2] - z0) / span * size, 1e4 - T[..., 1]], -1)
    else:
        eye = np.array(a.eye); look = np.array(a.look)
        f = look - eye; f /= np.linalg.norm(f); r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, f)
        k = (size / 2) / np.tan(np.radians(a.fov) / 2)
        def proj(T):
            D = T - eye; zc = D @ f
            with np.errstate(divide='ignore', invalid='ignore'):
                return np.stack([size / 2 + k * (D @ r) / zc, size / 2 - k * (D @ u) / zc, np.where(zc > 0.1, zc, -1)], -1)
    img, cov = raster(T, C, size, proj)
    im = Image.fromarray(img)
    if a.top and a.points:
        from PIL import ImageDraw
        dr = ImageDraw.Draw(im)
        for x, y, z, col in json.load(open(a.points)):
            px, py = (x - x0) / span * size, (z - z0) / span * size
            dr.ellipse([px - 4, py - 4, px + 4, py + 4], outline=col, width=2)
    im.save(a.out)
    print(json.dumps({'triangles': int(len(T)), 'pixel_coverage': round(float(cov), 4), 'out': a.out}))

if __name__ == '__main__':
    main()
