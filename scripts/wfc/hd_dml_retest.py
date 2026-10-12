"""DirectML retest of the colour model (4x-Textures-GTAV-rgt-s) at 144 px tiles (Integration 2026-10-11, condition for the HD full pass).
At 160 px tiles DirectML returned garbage for interior tiles; the 144 px edge tiles were correct. Clean only if, on >= 20 colour
textures of mixed sizes, the DML 4x output has broken_blocks == 0 AND sampled interior tiles match a CPU run of the same input.

  WFC_HD_TILE=112 python hd_dml_retest.py      (112 + 2 x 16 pad = 144 px tiles; exits 75 on a performance hold / running game)
Writes out/hd/dml_retest/dml_retest.json (+ the DML outputs, resumable).
"""
import json, os, sys, time
from collections import OrderedDict as OD
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hd_push as P  # noqa: E402
import hd_torch as T  # noqa: E402
H = P.H
OUT = os.path.join(H.HD, 'dml_retest')
PER_SIZE = {256: 5, 512: 6, 1024: 6, 2048: 3}       # 20 textures, mixed sizes
TILES_PER_TEX = 3                                   # sampled interior tiles compared with CPU
TILE_DIFF_MAX = 1.0                                 # mean |DML - CPU| in 8-bit units per tile

def pick():
    sel = json.load(open(os.path.join(H.HD, 'full', 'selection.json'), encoding='utf-8'))
    out = []
    for size, n in PER_SIZE.items():
        c = [s for s in sel if s['cls'] == 'colour' and max(s['size']) == size and min(s['size']) >= size // 2]
        c.sort(key=lambda s: s['k']); step = max(1, len(c) // n)
        out += c[::step][:n]
    return out

def interior_tiles(h, w, rng):
    t = T.TILE; ys = list(range(t, h - t, t)); xs = list(range(t, w - t, t))
    if not ys or not xs: return []
    return [(int(rng.choice(ys)), int(rng.choice(xs))) for _ in range(TILES_PER_TEX)]

def main():
    import torch
    assert T.TILE == 112, 'run with WFC_HD_TILE=112 (144 px tiles)'
    os.makedirs(OUT, exist_ok=True)
    dml, how = T.device(); cpu = torch.device('cpu'); torch.set_num_threads(6); print('device', how, 'tile', T.TILE + 2 * T.PAD, flush=True)
    res_path = os.path.join(OUT, 'dml_retest.json')
    res = OD((r['k'], r) for r in json.load(open(res_path, encoding='utf-8'))['textures']) if os.path.exists(res_path) else OD()
    dg = dc = None; rng = np.random.default_rng(11)
    for s in pick():
        if s['k'] in res: continue
        stop = P.held()
        if stop: print('PERF_HOLD present: stopping', stop, flush=True); sys.exit(75)
        if dg is None: dg = T.load(P.COLOUR_MODEL, dml); dc = T.load(P.COLOUR_MODEL, cpu)
        o = np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGBA')); rgb = np.ascontiguousarray(o[..., :3])
        t0 = time.time(); hd = T.upscale(dg, dml, rgb); t_dml = time.time() - t0
        Image.fromarray(hd).save(os.path.join(OUT, '%05d_dml.png' % s['k']))
        bb = P.broken_blocks(rgb, hd)
        tiles = []
        for (y0, x0) in interior_tiles(*rgb.shape[:2], rng):
            ya, xa = y0 - T.PAD, x0 - T.PAD
            t = torch.from_numpy(np.ascontiguousarray(rgb[ya:y0 + T.TILE + T.PAD, xa:x0 + T.TILE + T.PAD])).permute(2, 0, 1).float().div(255)[None]
            with torch.no_grad(): c = dc.model(t).float().clamp(0, 1)[0].permute(1, 2, 0).numpy() * 255
            c = c[4 * T.PAD:4 * (T.PAD + T.TILE), 4 * T.PAD:4 * (T.PAD + T.TILE)]
            g = hd[4 * y0:4 * (y0 + T.TILE), 4 * x0:4 * (x0 + T.TILE)].astype(np.float32)
            tiles.append(OD([('y0', y0), ('x0', x0), ('mean_abs_diff', round(float(np.abs(np.round(c) - g).mean()), 3))]))
        clean = bool(bb == 0 and all(t['mean_abs_diff'] <= TILE_DIFF_MAX for t in tiles))
        res[s['k']] = OD([('k', s['k']), ('object_path', s['object_path']), ('size', s['size']), ('dml_seconds', round(t_dml, 1)),
                          ('broken_blocks', bb), ('interior_tiles', tiles), ('clean', clean)])
        print(s['k'], s['size'], 'bb', bb, [t['mean_abs_diff'] for t in tiles], 'CLEAN' if clean else 'NOT CLEAN', '%.0fs' % t_dml, flush=True)
        json.dump(OD([('textures', list(res.values()))]), open(res_path, 'w', encoding='utf-8'), indent=1)
    rows = list(res.values())
    verdict = bool(len(rows) >= 20 and all(r['clean'] for r in rows))
    json.dump(OD([('generated', time.strftime('%Y-%m-%d %H:%M')), ('model', P.COLOUR_MODEL), ('tile_px', T.TILE + 2 * T.PAD),
                  ('rule', 'clean = broken_blocks 0 and every sampled interior tile mean |DML - CPU| <= %.1f, on >= 20 textures' % TILE_DIFF_MAX),
                  ('verdict_clean', verdict), ('textures', rows)]), open(res_path, 'w', encoding='utf-8'), indent=1)
    print('VERDICT', 'CLEAN' if verdict else 'NOT CLEAN', len(rows), 'textures', flush=True)

if __name__ == '__main__':
    main()
