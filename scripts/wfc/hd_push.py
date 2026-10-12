"""HD 'push harder' PILOT (user decision 2026-10-11 via Integration): detail that SHOWS at normal play distance at 1440p, beyond
faithful, still the same game (layout, motifs, palette, material identity; no redrawn logos or designs). One map (MP_IAC_Rust),
its ~36 most screen-visible textures (world-space area in the playable region: out/hd/rust_texture_area.json) + Bumblebee robot
and the Heavy Pistol. Nothing goes into ExtractedAssets or the M4 pack; each variant is its own pack (WFC_HD_ROOT).

Variants (4x):
  gen4x          colour: 4x-Textures-GTAV-rgt-s (generative game-texture model); masks / alpha: 4x-PBRify-RPLKSRd-V3; normals
                 (standalone and the TEXSET NormX / NormY alpha halves, recombined): 4x-Normal-RG0-BC1. Anchored to the original
                 only at low frequency (smoothed back-projection: palette and layout held, micro-detail free; no 40 dB lock)
  gen4x_mid      + local contrast in the original's mid band on colour (unsharp, sigma 3 original px): visible at distance
  gen4x_mid_nrm  + normal detail: base relief x1.25 plus micro relief from the colour texture's own luminance detail
Drift gate per texture and variant (at original size): luma SSIM >= 0.80, max channel mean shift <= 3 levels, colours outside
the original <= 3 %; a texture failing it stays original in that pack.

  python hd_push.py select | gen | build | sheet
"""
import glob, json, math, os, shutil, subprocess, sys, time
from collections import OrderedDict as OD, Counter
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if '--v2' not in sys.argv: sys.argv.append('--v2')
import hd_pilot as H  # noqa: E402
import hd_v4 as V4  # noqa: E402
REB = os.path.dirname(H.AT)
OUT = os.path.join(H.HD, 'push_pilot'); RAW = os.path.join(OUT, '_raw')
VARIANTS = ['gen4x', 'gen4x_mid', 'gen4x_mid_nrm']
COLOUR_MODEL, MASK_MODEL, NORMAL_MODEL = '4x-Textures-GTAV-rgt-s', '4x-PBRify-RPLKSRd-V3', '4x-Normal-RG0-BC1'
EXTRA = ['content/TR_BumbleBee_ROBO_p/RB_Bumblebee_GrngCLR.png', 'content/TR_BumbleBee_ROBO_p/RB_Bumblebee_Norm_XY_1024.png',
         'content/WEP_HeavyPistol_p/WEP_HeavyPistol_CLR.png', 'content/WEP_HeavyPistol_p/WEP_HeavyPistol_NORM.png']
N_MAP = 36
MAX_SIDE = 4096   # Integration: VRAM (sRGB colour decodes to 4-8 B/px): 4x up to 1024, 2x for 2048
SSIM_MIN, SHIFT_MAX, NEWCOL_MAX = 0.80, 3.0, 0.03
MID_SIGMA_ORIG, MID_GAIN = 3.0, 0.6
NRM_BASE, NRM_MICRO = 1.25, 0.15

def kind(png):
    b = os.path.basename(png)
    if b.endswith('_Color_NormX.png'): return 'texset_color'
    if b.endswith('_Masks_NormY.png'): return 'texset_masks'
    if any(t in b for t in ('NORM', 'Norm', 'NRM')): return 'normal'
    return 'colour'

def select():
    area = json.load(open(os.path.join(H.HD, 'rust_texture_area.json'), encoding='utf-8'))
    man = {}
    for l in open(os.path.join(H.AT, 'manifests', 'extracted', 'textures_dds.jsonl'), encoding='utf-8'):
        r = json.loads(l)
        if r.get('status') == 'ok' and r.get('png') and not r.get('png_is_other_object'): man[r['png'].lower()] = r
    files = [a['file'] for a in area if not a['file'].startswith('content/FX_')][:N_MAP] + EXTRA
    for f in list(files):                                      # complete TEXSET pairs (the normal is split over both)
        k = kind(f)
        if k == 'texset_color': p = f.replace('_Color_NormX.png', '_Masks_NormY.png')
        elif k == 'texset_masks': p = f.replace('_Masks_NormY.png', '_Color_NormX.png')
        else: continue
        if p not in files: files.append(p)
    rows = []
    for i, f in enumerate(files):
        r = man.get(f.lower())
        if not r: print('no DDS row for', f); continue
        rows.append(OD([('i', i), ('png', r['png']), ('dds', r['dds']), ('object_path', r['object_path']), ('format', r['format']),
                        ('size', r['size']), ('kind', kind(r['png'])), ('area_m2', next((a['area_m2'] for a in area if a['file'] == f), None))]))
    os.makedirs(OUT, exist_ok=True)
    json.dump(rows, open(os.path.join(OUT, 'select.json'), 'w', encoding='utf-8'), indent=1)
    from collections import Counter
    print(len(rows), Counter(r['kind'] for r in rows))

def rows(): return json.load(open(os.path.join(OUT, 'select.json'), encoding='utf-8'))
def orig(r): return np.asarray(Image.open(os.path.join(H.DDS, r['dds'])).convert('RGBA'))
def partner(r, R):
    if r['kind'] == 'texset_color': p = r['png'].replace('_Color_NormX.png', '_Masks_NormY.png')
    elif r['kind'] == 'texset_masks': p = r['png'].replace('_Masks_NormY.png', '_Color_NormX.png')
    else: return None
    return next((x for x in R if x['png'] == p), None)
def held():
    """a performance hold, or a game / fidelity run sharing the GPU (the pilot runs in gaps only)"""
    h = glob.glob(os.path.join(REB, '*', 'work', 'PERF_HOLD'))
    t = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, errors='replace').stdout.lower()
    return h + [e for e in ('wfc_rebuild.exe', 'wfc_fidelity.exe') if '"%s"' % e in t]
def factor(r): return max(1, min(4, MAX_SIDE // max(r['size'])))
def raw4(path, f, size, mode='RGB'):
    im = Image.open(path).convert(mode)
    return np.asarray(im if f == 4 else im.resize(size, Image.BOX))
def raw_path(r, part): return os.path.join(RAW, '%03d_%s.png' % (r['i'], part))
def resize(a, size, m=Image.LANCZOS):
    return H.resize_straight(a, size, m) if a.ndim == 3 else np.asarray(Image.fromarray(a, 'L').resize(size, m))

# eye review of texture_sheet_*.png (2026-10-11): rejected textures keep the original in every variant
EYE_REJECT = {'content/ENV_AllShader_p/Textures/Metal_01_TiledNORM.png'}   # diagonal grain turns into crumpled foil (motif change)
CPU_MODELS = {COLOUR_MODEL}   # rgt-s on DirectML returns garbage for interior (160 px) tiles; CPU output is correct (2026-10-11)

def gen():
    """the model outputs (resumable; exits 75 when a performance hold appears, the cmd runner waits and restarts).
    --cpu-only: only the CPU_MODELS outputs (no GPU use; these yield to PERF_HOLD files only, not to a running game)"""
    import torch
    import hd_torch as T
    cpu_only = '--cpu-only' in sys.argv
    dev, name = (torch.device('cpu'), 'cpu') if cpu_only else T.device(); print('device', name, flush=True)
    torch.set_num_threads(int(os.environ.get('WFC_HD_CPU_THREADS', '6')))
    os.makedirs(RAW, exist_ok=True); R = rows(); models = {}
    def run(model, img, path):
        if os.path.exists(path) or cpu_only != (model in CPU_MODELS): return
        d = torch.device('cpu') if model in CPU_MODELS else dev
        stop = glob.glob(os.path.join(REB, '*', 'work', 'PERF_HOLD')) if model in CPU_MODELS else held()
        if stop: print('PERF_HOLD present: stopping', stop, flush=True); sys.exit(75)
        if model not in models: models[model] = T.load(model, d)
        t0 = time.time(); out = T.upscale(models[model], d, img); Image.fromarray(out).save(path)
        print(os.path.basename(path), img.shape, '%.0fs' % (time.time() - t0), flush=True)
    for r in R:
        o = orig(r); w, h = r['size']; g3 = lambda c: np.dstack([c, c, c])
        if r['kind'] in ('colour', 'texset_color'): run(COLOUR_MODEL, o[..., :3], raw_path(r, 'rgb'))
        if r['kind'] == 'texset_masks': run(MASK_MODEL, o[..., :3], raw_path(r, 'rgb'))
        if r['kind'] == 'normal':
            n = o[..., :3].copy(); n[..., 2] = 0; run(NORMAL_MODEL, n, raw_path(r, 'nrm'))     # RG0 convention (M4)
        if r['kind'] == 'colour' and r['format'] == 'PF_DXT5': run(MASK_MODEL, g3(o[..., 3]), raw_path(r, 'alpha'))
        if r['kind'] == 'texset_color':                         # NormX (this alpha) + NormY (the masks' alpha) at this size
            p = partner(r, R)
            if p is None: continue
            y = resize(orig(p)[..., 3], (w, h))
            run(NORMAL_MODEL, np.dstack([o[..., 3], y, np.zeros_like(y)]), raw_path(r, 'texnrm'))
    print('gen done', flush=True)

# ---- CPU build ---------------------------------------------------------------------------------------------------------------
def gblur(a, sigma):
    """separable gaussian blur (float32, edge padding), per channel"""
    if sigma <= 0: return a
    r = int(math.ceil(3 * sigma)); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2).astype(np.float32); k /= k.sum()
    x = a.astype(np.float32)
    for ax in (0, 1):
        p = np.pad(x, [(r, r) if i == ax else (0, 0) for i in range(x.ndim)], mode='edge')
        x = sum(k[i] * np.take(p, range(i, i + x.shape[ax]), axis=ax) for i in range(2 * r + 1))
    return x

def box_down(a, f):
    h, w = a.shape[0] // f, a.shape[1] // f
    return a[:f * h, :f * w].reshape(h, f, w, f, *a.shape[2:]).mean((1, 3))

def up(a, f):
    h, w = a.shape[:2]
    if a.ndim == 2: return np.asarray(Image.fromarray(a.astype(np.float32), 'F').resize((w * f, h * f), Image.BILINEAR))
    return np.stack([up(a[..., c], f) for c in range(a.shape[2])], -1)

def anchor(o, x, f=4, sigma=1.5, iters=3):
    """low-frequency anchoring: the smoothed residual between the original and the area-downsample is put back (palette /
    layout held), the band above sigma original px stays the model's (micro-detail free)"""
    o = o.astype(np.float32); x = x.astype(np.float32)
    for _ in range(iters): x = np.clip(x + up(gblur(o - box_down(x, f), sigma), f), 0, 255)
    return x

def mid_boost(x, f=4):
    s = MID_SIGMA_ORIG * f
    return np.clip(x + MID_GAIN * (x - gblur(x, s)), 0, 255)

def nrm_from_xy(x, y):
    X = x / 127.5 - 1; Y = y / 127.5 - 1; Z = np.sqrt(np.clip(1 - X * X - Y * Y, 0, 1)); return np.stack([X, Y, Z], -1)

def nrm_boost(n, lum):
    """n: HxWx3 unit normals; base relief x NRM_BASE, then whiteout blend with micro relief from the colour's own detail"""
    n = n.copy(); n[..., :2] *= NRM_BASE
    if lum is not None:
        d = lum - gblur(lum, 3.0); d = d / (d.std() + 1e-6)
        gy, gx = np.gradient(d)
        m = np.stack([-gx * NRM_MICRO, -gy * NRM_MICRO, np.ones_like(d)], -1)
        n = np.stack([n[..., 0] + m[..., 0], n[..., 1] + m[..., 1], n[..., 2] * m[..., 2]], -1)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)

def ssim_luma(a, b):
    a = V4.luma(a); b = V4.luma(b); C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    ma, mb = V4.box_blur(a, 3), V4.box_blur(b, 3)
    va = V4.box_blur(a * a, 3) - ma * ma; vb = V4.box_blur(b * b, 3) - mb * mb; cv = V4.box_blur(a * b, 3) - ma * mb
    return float((((2 * ma * mb + C1) * (2 * cv + C2)) / ((ma * ma + mb * mb + C1) * (va + vb + C2))).mean())

def drift(o, hd, k):
    w, h = o.shape[1], o.shape[0]
    d = H.resize_straight(np.clip(np.round(hd), 0, 255).astype(np.uint8), (w, h), Image.BOX).astype(np.float64)
    of = o.astype(np.float64)
    if k in ('normal',):
        lit = lambda a: H._lit(a.astype(np.uint8), True).astype(np.float64)
        s = ssim_luma(lit(of), lit(d))
    else: s = ssim_luma(of[..., :3], d[..., :3])
    sh = float(np.abs(of[..., :3].reshape(-1, 3).mean(0) - d[..., :3].reshape(-1, 3).mean(0)).max())
    q = lambda a: (a[..., :3].astype(np.int32) >> 3) + 1
    pal = np.zeros((34, 34, 34), bool); qo = q(o)
    for dz in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1): pal[qo[..., 0] + dz, qo[..., 1] + dy, qo[..., 2] + dx] = True
    qh = q(d.astype(np.uint8)); newc = float((~pal[qh[..., 0], qh[..., 1], qh[..., 2]]).mean()) if k != 'normal' else 0.0
    loc = lambda x: np.sqrt(np.maximum(V4.box_blur(x ** 2, 4) - V4.box_blur(x, 4) ** 2, 0)).mean()
    lc = float(loc(V4.luma(d)) / max(loc(V4.luma(of)), 1e-6))
    hd8 = np.clip(np.round(hd), 0, 255).astype(np.uint8)
    bb = broken_blocks(H._lit(o, True), H._lit(hd8, True)) if k == 'normal' else broken_blocks(o[..., :3], hd8[..., :3])
    ok = bool(s >= SSIM_MIN and sh <= SHIFT_MAX and newc <= NEWCOL_MAX and bb == 0)
    return OD([('ssim', round(s, 3)), ('mean_shift', round(sh, 2)), ('new_colours', round(newc, 4)), ('local_contrast_ratio', round(lc, 3)),
               ('broken_blocks', bb), ('ok', ok)])

def broken_blocks(o, hd, B=128):
    """full-resolution check (the box-downsampled gate averages tile noise away): HD blocks whose blurred luma departs from a
    Lanczos upscale of the original, or whose fine detail is > 6x / < 1/12 of it (garbage / flat model tiles)"""
    W, Hh = hd.shape[1], hd.shape[0]
    lz = V4.luma(H.resize_straight(o, (W, Hh), Image.LANCZOS)).astype(np.float32); hl = V4.luma(np.clip(np.round(hd), 0, 255).astype(np.uint8)).astype(np.float32)
    bl = lambda a: V4.box_blur(a, 6)
    hf = lambda a: np.abs(np.diff(a, axis=1))[:-1] + np.abs(np.diff(a, axis=0))[:, :-1]
    dl, fl, fh = np.abs(bl(lz) - bl(hl)), hf(lz), hf(hl); n = 0
    for y in range(0, Hh - B + 1, B):
        for x in range(0, W - B + 1, B):
            d = dl[y:y + B, x:x + B].mean(); a = fl[y:y + B - 1, x:x + B - 1].mean() + 0.5; b = fh[y:y + B - 1, x:x + B - 1].mean() + 0.5
            if d > 24 or b / a > 6 or b / a < 1 / 12: n += 1
    return n

def encode(img, r, root):
    src = os.path.join(OUT, '_enc', os.path.basename(root), '%03d.png' % r['i']); os.makedirs(os.path.dirname(src), exist_ok=True)
    Image.fromarray(img, 'RGBA').save(src)
    out = os.path.join(root, os.path.dirname(r['dds'])); os.makedirs(out, exist_ok=True)
    fmt = {'PF_DXT1': 'BC1_UNORM', 'PF_DXT5': 'BC3_UNORM', 'PF_A8R8G8B8': 'B8G8R8A8_UNORM'}[r['format']]
    p = subprocess.run([H.TEXCONV, '-nologo', '-y', '-nogpu', '-m', '0', '-f', fmt, '-o', out, src], capture_output=True, text=True, errors='replace')
    tmp = os.path.join(out, '%03d.dds' % r['i']); dst = os.path.join(root, r['dds'])
    if p.returncode != 0 or not os.path.exists(tmp): raise RuntimeError('texconv: ' + p.stdout[-300:])
    os.replace(tmp, dst); return dst

def build():
    R = rows(); res = []; idx = {v: [] for v in VARIANTS}
    for r in R:
        o = orig(r); w, h = r['size']; f = factor(r); W, Hh = f * w, f * h; k = r['kind']
        A = np.zeros((Hh, W, 4), np.float32); A[..., 3] = resize(o[..., 3], (W, Hh)) if k != 'normal' else 255
        if k in ('colour', 'texset_color', 'texset_masks'):
            A[..., :3] = anchor(o[..., :3], raw4(raw_path(r, 'rgb'), f, (W, Hh)), f)
        if k == 'colour' and r['format'] == 'PF_DXT5' and os.path.exists(raw_path(r, 'alpha')):
            A[..., 3] = anchor(o[..., 3:4], raw4(raw_path(r, 'alpha'), f, (W, Hh))[..., :1], f)[..., 0]
        nrm = None                                                    # unit normals at 4x (gen4x) for the normal boost
        if k == 'normal':
            n = raw4(raw_path(r, 'nrm'), f, (W, Hh)).astype(np.float32)
            xy = anchor(o[..., :2], n[..., :2], f); nrm = nrm_from_xy(xy[..., 0], xy[..., 1])
            A[..., :3] = (nrm + 1) * 127.5
        texn = None
        if k in ('texset_color', 'texset_masks'):
            c = r if k == 'texset_color' else partner(r, R); m = partner(c, R) if c else None
            if c and m and os.path.exists(raw_path(c, 'texnrm')):
                cw, ch = c['size']; fc = factor(c); n = raw4(raw_path(c, 'texnrm'), fc, (fc * cw, fc * ch)).astype(np.float32)
                ox = orig(c)[..., 3].astype(np.float32); oy = resize(orig(m)[..., 3], (cw, ch)).astype(np.float32)
                xy = anchor(np.stack([ox, oy], -1), n[..., :2], fc); texn = (c, nrm_from_xy(xy[..., 0], xy[..., 1]))
                comp = 0 if k == 'texset_color' else 1
                A[..., 3] = resize(np.clip((texn[1][..., comp] + 1) * 127.5, 0, 255).astype(np.uint8), (W, Hh))
        # variants
        V = OD([('gen4x', A)])
        B = A.copy()
        if k in ('colour', 'texset_color'): B[..., :3] = mid_boost(A[..., :3], f)
        V['gen4x_mid'] = B
        C = B.copy()
        if k == 'normal':
            lumsrc = next((x for x in R if x['kind'] == 'colour' and os.path.dirname(x['png']) == os.path.dirname(r['png'])
                           and os.path.basename(x['png']).split('_')[0] == os.path.basename(r['png']).split('_')[0]), None)
            lum = None
            if lumsrc and os.path.exists(raw_path(lumsrc, 'rgb')):
                fl = factor(lumsrc); lw, lh = lumsrc['size']
                lum = V4.luma(mid_boost(anchor(orig(lumsrc)[..., :3], raw4(raw_path(lumsrc, 'rgb'), fl, (fl * lw, fl * lh)), fl), fl))
                if lum.shape != (Hh, W): lum = np.asarray(Image.fromarray(lum.astype(np.float32), 'F').resize((W, Hh), Image.BILINEAR))
            C[..., :3] = (nrm_boost(nrm, lum) + 1) * 127.5
        if texn is not None:
            c = texn[0]; fc = factor(c); cw, ch = c['size']
            lum = V4.luma(mid_boost(anchor(orig(c)[..., :3], raw4(raw_path(c, 'rgb'), fc, (fc * cw, fc * ch)), fc), fc))
            nb = nrm_boost(texn[1], lum); comp = 0 if k == 'texset_color' else 1
            C[..., 3] = resize(np.clip((nb[..., comp] + 1) * 127.5, 0, 255).astype(np.uint8), (W, Hh))
        V['gen4x_mid_nrm'] = C
        rec = OD([('i', r['i']), ('png', r['png']), ('kind', k), ('size', r['size']), ('area_m2', r['area_m2'])])
        for v, img in V.items():
            u8 = np.clip(np.round(img), 0, 255).astype(np.uint8); m = drift(o, u8, k); rec[v] = m
            if m['ok']:
                d = encode(u8, r, os.path.join(OUT, v))
                idx[v].append(OD([('key', r['png'].lower()), ('object_path', r['object_path']), ('dds', r['dds']), ('format', r['format']),
                                  ('size', [W, Hh]), ('bytes', os.path.getsize(d))]))
                Image.fromarray(u8, 'RGBA').save(os.path.join(OUT, '_enc', v, '%03d.png' % r['i']))
        res.append(rec); print(r['i'], k, {v: (rec[v]['ssim'], rec[v]['local_contrast_ratio'], rec[v]['ok']) for v in V}, flush=True)
    for v in VARIANTS:
        json.dump(OD([('version', 1), ('generator', 'AssetTools/scripts/wfc/hd_push.py (pilot: %s)' % v), ('generated', time.strftime('%Y-%m-%d %H:%M')),
                      ('map', 'MP_IAC_Rust'), ('textures', len(idx[v])), ('rows', idx[v])]),
                  open(os.path.join(OUT, v, 'hd_index.json'), 'w', encoding='utf-8'), indent=1)
    json.dump(OD([('generated', time.strftime('%Y-%m-%d %H:%M')), ('variants', VARIANTS),
                  ('drift_gate', OD([('ssim_min', SSIM_MIN), ('mean_shift_max', SHIFT_MAX), ('new_colours_max', NEWCOL_MAX)])),
                  ('params', OD([('mid_sigma_orig_px', MID_SIGMA_ORIG), ('mid_gain', MID_GAIN), ('normal_base', NRM_BASE), ('normal_micro', NRM_MICRO)])),
                  ('models', OD([('colour', COLOUR_MODEL), ('masks_alpha', MASK_MODEL), ('normal', NORMAL_MODEL)])), ('textures', res)]),
              open(os.path.join(OUT, 'push_pilot.json'), 'w', encoding='utf-8'), indent=1)
    print({v: len(idx[v]) for v in VARIANTS})
    pack()

def pack():
    """each variant pack = the strongest variant up to it that passed the drift gate (a cumulative ladder, so every variant
    covers what gen4x covers); a TEXSET Color / Masks pair (NormX / NormY halves of one normal) always takes the same level"""
    R = rows(); T = {t['i']: t for t in json.load(open(os.path.join(OUT, 'push_pilot.json'), encoding='utf-8'))['textures']}
    def level(r, p):
        if any(x['png'] in EYE_REJECT for x in (r, partner(r, R)) if x is not None): return None
        for q in range(p, -1, -1):
            if all(T[x['i']][VARIANTS[q]]['ok'] for x in (r, partner(r, R)) if x is not None): return q
        return None
    out = OD()
    for p, v in enumerate(VARIANTS):
        rows_v = []; lv = OD()
        for r in R:
            q = level(r, p); dst = os.path.join(OUT, v, r['dds']); lv[r['i']] = None if q is None else VARIANTS[q]
            if q is None:
                if os.path.exists(dst): os.remove(dst)
                continue
            if q != p: os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(os.path.join(OUT, VARIANTS[q], r['dds']), dst)
            f = factor(r)
            rows_v.append(OD([('key', r['png'].lower()), ('object_path', r['object_path']), ('dds', r['dds']), ('format', r['format']),
                              ('size', [f * r['size'][0], f * r['size'][1]]), ('bytes', os.path.getsize(dst)), ('level', VARIANTS[q])]))
        json.dump(OD([('version', 1), ('generator', 'AssetTools/scripts/wfc/hd_push.py (pilot: %s, cumulative fallback)' % v),
                      ('generated', time.strftime('%Y-%m-%d %H:%M')), ('map', 'MP_IAC_Rust'), ('textures', len(rows_v)), ('rows', rows_v)]),
                  open(os.path.join(OUT, v, 'hd_index.json'), 'w', encoding='utf-8'), indent=1)
        out[v] = OD([('textures', len(rows_v)), ('mb', round(sum(x['bytes'] for x in rows_v) / 2 ** 20, 1)),
                     ('levels', dict(Counter(x['level'] for x in rows_v)))])
    print(json.dumps(out))

def sheet():
    """texture-space check (in-game shots are the verdict): original nearest | gen4x | gen4x_mid | gen4x_mid_nrm, 64 px spot at 4x"""
    J = json.load(open(os.path.join(OUT, 'push_pilot.json'), encoding='utf-8')); R = {r['i']: r for r in rows()}
    n, S = 64, 256; cols = 1 + len(VARIANTS); rws = J['textures']
    for part in range(0, len(rws), 10):
        grp = rws[part:part + 10]; im = Image.new('RGB', (cols * (S + 8), len(grp) * (S + 22)), (16, 16, 20)); d = ImageDraw.Draw(im)
        for j, t in enumerate(grp):
            r = R[t['i']]; o = orig(r)
            show = (lambda a: H._lit(a, True)) if t['kind'] == 'normal' else (lambda a: a[..., :3])
            O = show(o); gr = V4.luma(O); gr = np.abs(np.diff(gr, axis=0))[:, :-1] + np.abs(np.diff(gr, axis=1))[:-1, :]
            nn = min(n, *gr.shape)
            _, x, y = max(((gr[yy:yy + nn, xx:xx + nn].sum(), xx, yy) for yy in range(0, max(1, gr.shape[0] - nn), 16) for xx in range(0, max(1, gr.shape[1] - nn), 16)))
            Y = j * (S + 22); d.text((4, Y + 3), '%03d %s %s' % (t['i'], os.path.basename(t['png'])[:60], t['kind']), fill=(230, 230, 230))
            im.paste(Image.fromarray(np.ascontiguousarray(O[y:y + nn, x:x + nn])).resize((S, S), Image.NEAREST), (0, Y + 18))
            for c, v in enumerate(VARIANTS, 1):
                p = os.path.join(OUT, '_enc', v, '%03d.png' % t['i'])
                if not os.path.exists(p): d.text((c * (S + 8) + 60, Y + 18 + S // 2), 'drift: original', fill=(255, 150, 120)); continue
                a = show(np.asarray(Image.open(p).convert('RGBA')))
                fr = factor(r); im.paste(Image.fromarray(np.ascontiguousarray(a[fr * y:fr * y + fr * nn, fr * x:fr * x + fr * nn])).resize((S, S), Image.LANCZOS), (c * (S + 8), Y + 18))
        im.save(os.path.join(OUT, 'texture_sheet_%d.png' % (part // 10 + 1)))
    print('sheets', (len(rws) + 9) // 10)

if __name__ == '__main__':
    {'select': select, 'gen': gen, 'build': build, 'pack': pack, 'sheet': sheet}[sys.argv[1]]()
