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
# WFC_HD_PUSH_SET=full: the HD full pass (docs/HD_FULL_PASS_PLAN.md) on out/hd/full/selection.json instead of the Rust pilot
FULL = os.environ.get('WFC_HD_PUSH_SET') == 'full'
OUT = os.path.join(H.HD, 'push_full' if FULL else 'push_pilot'); RAW = os.path.join(OUT, '_raw')
VARIANTS = ['gen4x', 'gen4x_mid', 'gen4x_mid_nrm', 'gen4x_d']   # D (Integration 2026-10-11, user 'the most amount of details'): stronger than C
COLOUR_MODEL, MASK_MODEL, NORMAL_MODEL = '4x-Textures-GTAV-rgt-s', '4x-PBRify-RPLKSRd-V3', '4x-Normal-RG0-BC1'
EXTRA = ['content/TR_BumbleBee_ROBO_p/RB_Bumblebee_GrngCLR.png', 'content/TR_BumbleBee_ROBO_p/RB_Bumblebee_Norm_XY_1024.png',
         'content/WEP_HeavyPistol_p/WEP_HeavyPistol_CLR.png', 'content/WEP_HeavyPistol_p/WEP_HeavyPistol_NORM.png']
N_MAP = 36
MAX_SIDE = 4096   # Integration: VRAM (sRGB colour decodes to 4-8 B/px): 4x up to 1024, 2x for 2048
SSIM_MIN, SHIFT_MAX, NEWCOL_MAX = 0.80, 3.0, 0.03
MID_SIGMA_ORIG, MID_GAIN = 3.0, 0.6
NRM_BASE, NRM_MICRO = 1.25, 0.15
# D: luminance-only mid + fine band (chroma kept, so the palette holds), stronger relief
D_MID_GAIN, D_FINE_SIGMA_ORIG, D_FINE_GAIN, D_NRM_BASE, D_NRM_MICRO = 1.0, 1.0, 0.5, 1.6, 0.30

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

def select_full():
    """the full pass: every texture of the M4 selection except KEEP verdicts and tiny (<= 64 px) ones (Lanczos / kept, plan).
    Kind from the selection class (data = masks / spec / glow: mask model), TEXSET halves by name; i = the selection key k"""
    sel = json.load(open(os.path.join(H.HD, 'full', 'selection.json'), encoding='utf-8'))
    ver = json.load(open(os.path.join(H.HD, 'full', 'verdicts.json'), encoding='utf-8'))
    rows = []
    for x in sel:
        if ver.get(str(x['k']), {}).get('verdict') == 'KEEP' or max(x['size']) <= 64: continue
        k = kind(x['png']); k = k if k.startswith('texset') else x['cls']
        rows.append(OD([('i', x['k']), ('png', x['png']), ('dds', x['dds']), ('object_path', x['object_path']), ('format', x['format']),
                        ('size', x['size']), ('kind', k), ('verdict', ver.get(str(x['k']), {}).get('verdict'))]))
    os.makedirs(OUT, exist_ok=True)
    json.dump(rows, open(os.path.join(OUT, 'select.json'), 'w', encoding='utf-8'), indent=1)
    print(len(rows), Counter(r['kind'] for r in rows), Counter(r['verdict'] for r in rows))

def rows(): return json.load(open(os.path.join(OUT, 'select.json'), encoding='utf-8'))
def orig(r): return np.asarray(Image.open(os.path.join(H.DDS, r['dds'])).convert('RGBA'))
def partner(r, R):
    """the other TEXSET half, by dds path (8 selection rows share a png path with a same-named texture in another package)"""
    if r['kind'] == 'texset_color': p = r['dds'].replace('_Color_NormX.dds', '_Masks_NormY.dds')
    elif r['kind'] == 'texset_masks': p = r['dds'].replace('_Masks_NormY.dds', '_Color_NormX.dds')
    else: return None
    return next((x for x in R if x['dds'] == p), None)
def free_commit_gb():
    """system commit still available (GlobalMemoryStatusEx ullAvailPageFile), GB"""
    import ctypes
    class M(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in
                    ('tp', 'ap', 'tpf', 'apf', 'tv', 'av', 'aev')]
    m = M(); m.dwLength = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.apf / 2 ** 30
COMMIT_PAUSE_GB = float(os.environ.get('WFC_COMMIT_PAUSE_GB', '16'))   # Integration 2026-10-12: pause < 16 GB free commit, resume > 20 (C: tight; was 8 / 12, then 14 / 18)
def low_commit():
    f = free_commit_gb()
    return ['free commit %.1f GB < %.0f' % (f, COMMIT_PAUSE_GB)] if f < COMMIT_PAUSE_GB else []
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
    --cpu-only: only the CPU_MODELS outputs (no GPU use; these yield to PERF_HOLD files only, not to a running game)
    --shard i/n: only rows whose position % n == i (parallel CPU shards)"""
    import torch
    import hd_torch as T
    cpu_only = '--cpu-only' in sys.argv
    dev, name = (torch.device('cpu'), 'cpu') if cpu_only else T.device(); print('device', name, flush=True)
    torch.set_num_threads(int(os.environ.get('WFC_HD_CPU_THREADS', '6')))
    os.makedirs(RAW, exist_ok=True); R = rows(); models = {}
    sh = next((a.split('/') for a in sys.argv if '/' in a and a.replace('/', '').isdigit()), None)
    mine = (lambda j: j % int(sh[1]) == int(sh[0])) if sh else (lambda j: True)
    def run(model, img, path):
        if os.path.exists(path) or cpu_only != (model in CPU_MODELS): return
        d = torch.device('cpu') if model in CPU_MODELS else dev
        stop = (glob.glob(os.path.join(REB, '*', 'work', 'PERF_HOLD')) if model in CPU_MODELS else held()) + low_commit()
        if stop: print('PERF_HOLD present: stopping', stop, flush=True); sys.exit(75)
        if model not in models: models[model] = T.load(model, d)
        t0 = time.time(); out = T.upscale(models[model], d, img); Image.fromarray(out).save(path)
        print(os.path.basename(path), img.shape, '%.0fs' % (time.time() - t0), flush=True)
    for j, r in enumerate(R):
        if not mine(j) or (cpu_only and r['kind'] not in ('colour', 'texset_color')): continue
        o = orig(r); w, h = r['size']; g3 = lambda c: np.dstack([c, c, c])
        if r['kind'] in ('colour', 'texset_color'): run(COLOUR_MODEL, o[..., :3], raw_path(r, 'rgb'))
        if r['kind'] in ('texset_masks', 'data'): run(MASK_MODEL, o[..., :3], raw_path(r, 'rgb'))
        if r['kind'] == 'normal':
            n = o[..., :3].copy(); n[..., 2] = 0; run(NORMAL_MODEL, n, raw_path(r, 'nrm'))     # RG0 convention (M4)
        if r['kind'] in ('colour', 'data') and r['format'] == 'PF_DXT5': run(MASK_MODEL, g3(o[..., 3]), raw_path(r, 'alpha'))
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
    if os.environ.get('WFC_HD_TORCH_BLUR') == '1':    # same kernel and edge padding as a torch separable conv (full pass: ~10x faster)
        import torch
        import torch.nn.functional as TF
        t = torch.from_numpy(np.ascontiguousarray(a, np.float32)); hw = t.ndim == 2
        t = (t[None] if hw else t.permute(2, 0, 1))[:, None]                       # C x 1 x H x W
        kt = torch.from_numpy(k)
        with torch.no_grad():
            t = TF.conv2d(TF.pad(t, (0, 0, r, r), mode='replicate'), kt.view(1, 1, -1, 1))
            t = TF.conv2d(TF.pad(t, (r, r, 0, 0), mode='replicate'), kt.view(1, 1, 1, -1))
        t = t[:, 0]
        return (t[0] if hw else t.permute(1, 2, 0)).numpy()
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

def detail_boost_d(x, f=4):
    """D: mid band (MID_SIGMA_ORIG) at D_MID_GAIN plus a fine band (D_FINE_SIGMA_ORIG) at D_FINE_GAIN, on luminance only"""
    Y = V4.luma(x).astype(np.float32)
    Yb = Y + D_MID_GAIN * (Y - gblur(Y, MID_SIGMA_ORIG * f)) + D_FINE_GAIN * (Y - gblur(Y, D_FINE_SIGMA_ORIG * f))
    return np.clip(x + (Yb - Y)[..., None], 0, 255)

def nrm_from_xy(x, y):
    X = x / 127.5 - 1; Y = y / 127.5 - 1; Z = np.sqrt(np.clip(1 - X * X - Y * Y, 0, 1)); return np.stack([X, Y, Z], -1)

def nrm_boost(n, lum, base=None, micro=None):
    """n: HxWx3 unit normals; base relief x NRM_BASE, then whiteout blend with micro relief from the colour's own detail"""
    base = NRM_BASE if base is None else base; micro = NRM_MICRO if micro is None else micro
    n = n.copy(); n[..., :2] *= base
    if lum is not None:
        d = lum - gblur(lum, 3.0); d = d / (d.std() + 1e-6)
        gy, gx = np.gradient(d)
        m = np.stack([-gx * micro, -gy * micro, np.ones_like(d)], -1)
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
    bb = broken_blocks(H._lit(o, True), H._lit(hd8, True), noise=BB_NORMAL_NOISE) if k == 'normal' else broken_blocks(o[..., :3], hd8[..., :3])
    ok = bool(s >= SSIM_MIN and sh <= SHIFT_MAX and newc <= NEWCOL_MAX and bb == 0)
    return OD([('ssim', round(s, 3)), ('mean_shift', round(sh, 2)), ('new_colours', round(newc, 4)), ('local_contrast_ratio', round(lc, 3)),
               ('broken_blocks', bb), ('ok', ok)])

BB_NORMAL_NOISE = True   # full pass sets False: on lit normals the > 6x test flags model grain in flat areas, not garbage tiles

def broken_blocks(o, hd, B=128, noise=True):
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
            if d > 24 or (noise and b / a > 6) or b / a < 1 / 12: n += 1
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

def variants(r, R):
    """the four ladder levels of one texture (float32 HxWx4, 4x or 2x): gen4x (anchored model output), + mid band, + normal detail,
    D. Kinds: colour / texset_color / texset_masks / normal, and data (full pass: masks, spec, glow; mask model, no boosts)"""
    o = orig(r); w, h = r['size']; f = factor(r); W, Hh = f * w, f * h; k = r['kind']
    A = np.zeros((Hh, W, 4), np.float32); A[..., 3] = resize(o[..., 3], (W, Hh)) if k != 'normal' else 255
    if k in ('colour', 'texset_color', 'texset_masks', 'data'):
        A[..., :3] = anchor(o[..., :3], raw4(raw_path(r, 'rgb'), f, (W, Hh)), f)
    if k in ('colour', 'data') and r['format'] == 'PF_DXT5' and os.path.exists(raw_path(r, 'alpha')):
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
        ls = lumsrc(r, R); lum = None
        if ls and os.path.exists(raw_path(ls, 'rgb')):
            fl = factor(ls); lw, lh = ls['size']
            lum = V4.luma(mid_boost(anchor(orig(ls)[..., :3], raw4(raw_path(ls, 'rgb'), fl, (fl * lw, fl * lh)), fl), fl))
            if lum.shape != (Hh, W): lum = np.asarray(Image.fromarray(lum.astype(np.float32), 'F').resize((W, Hh), Image.BILINEAR))
        C[..., :3] = (nrm_boost(nrm, lum) + 1) * 127.5
        D = C.copy(); D[..., :3] = (nrm_boost(nrm, lum, D_NRM_BASE, D_NRM_MICRO) + 1) * 127.5
    if texn is not None:
        c = texn[0]; fc = factor(c); cw, ch = c['size']
        lum = V4.luma(mid_boost(anchor(orig(c)[..., :3], raw4(raw_path(c, 'rgb'), fc, (fc * cw, fc * ch)), fc), fc))
        nb = nrm_boost(texn[1], lum); comp = 0 if k == 'texset_color' else 1
        C[..., 3] = resize(np.clip((nb[..., comp] + 1) * 127.5, 0, 255).astype(np.uint8), (W, Hh))
        nd = nrm_boost(texn[1], lum, D_NRM_BASE, D_NRM_MICRO)
        Dt = resize(np.clip((nd[..., comp] + 1) * 127.5, 0, 255).astype(np.uint8), (W, Hh))
    V['gen4x_mid_nrm'] = C
    if k != 'normal': D = C.copy()
    if k in ('colour', 'texset_color'): D[..., :3] = detail_boost_d(A[..., :3], f)
    if texn is not None: D[..., 3] = Dt
    V['gen4x_d'] = D
    return o, f, W, Hh, V

def lumsrc(r, R):
    """the colour texture a normal map's micro relief comes from (same package folder, same name prefix)"""
    return next((x for x in R if x['kind'] == 'colour' and os.path.dirname(x['png']) == os.path.dirname(r['png'])
                 and os.path.basename(x['png']).split('_')[0] == os.path.basename(r['png']).split('_')[0]), None)

def build():
    R = rows(); res = []; idx = {v: [] for v in VARIANTS}
    for r in R:
        o, f, W, Hh, V = variants(r, R); k = r['kind']
        rec = OD([('i', r['i']), ('png', r['png']), ('kind', k), ('size', r['size']), ('area_m2', r.get('area_m2'))])
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
                  ('params', OD([('mid_sigma_orig_px', MID_SIGMA_ORIG), ('mid_gain', MID_GAIN), ('normal_base', NRM_BASE), ('normal_micro', NRM_MICRO),
                                  ('d', OD([('mid_gain', D_MID_GAIN), ('fine_sigma_orig_px', D_FINE_SIGMA_ORIG), ('fine_gain', D_FINE_GAIN),
                                            ('normal_base', D_NRM_BASE), ('normal_micro', D_NRM_MICRO)]))])),
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

INGAME = os.path.join(REB, 'Rebuild-Rendering', 'work', 'hdpush', 'runs')   # Rendering's captures (read in place)
SOURCES = [('off', 'original (HD off)', ''), ('gen4x', 'A  4x', ''), ('gen4x_mid', 'B  4x + mid-band', ''),
           ('gen4x_mid_nrm', 'C  4x + mid + normal', ''), ('m4', 'M4 shipped pack (reference)', '')]
# C vs D (user to choose): Rendering's '_cd' runs on the build with the compressed sRGB upload; the original is the earlier pilot run
SOURCES_CD = [('off', 'original (HD off; earlier build)', ''), ('gen4x_mid_nrm', 'C  4x + mid + normal', '_cd'),
              ('gen4x_d', 'D  4x + stronger mid/fine + relief', '_cd')]
SPOTS = ['ground_rust', 'wall_blockbldpanel', 'interior_wall', 'floor_panel', 'wall_archive']

def ingame():
    """in-game before / after for the user (Integration): per spot, the settled 2560x1440 frame (m00600) of each source; the 640x360
    region where the two compared sources differ most is shown 1:1 for every source, at AF 16 and AF 4.
    `ingame` = original vs C (A/B/C/M4 pilot); `ingame cd` = C vs D (crop where D departs most from C)"""
    import re
    cd = 'cd' in sys.argv[2:]
    srcs, (ra, rb), top = (SOURCES_CD, ('gen4x_mid_nrm', 'gen4x_d'), ('gen4x_mid_nrm', 'gen4x_d')) if cd else \
                          (SOURCES, ('off', 'gen4x_mid_nrm'), ('off', 'gen4x_mid_nrm'))
    suf = {s: x for s, _, x in srcs}; lab = {s: l for s, l, _ in srcs}
    dst = os.path.join(OUT, 'ingame_cd' if cd else 'ingame'); os.makedirs(dst, exist_ok=True)
    run = lambda s, af, sp: os.path.join(INGAME, '%s_af%d_%s%s' % (s, af, sp, suf[s]))
    shot = lambda s, af, sp: np.asarray(Image.open(os.path.join(run(s, af, sp), 'shots', 'm00600.bmp')).convert('RGB'))
    mem = OD()
    for s, _, _ in srcs:
        m = re.search(r'other textures \d+ = (\d+) MB.*?(\d+) HD\)', open(os.path.join(run(s, 16, SPOTS[0]), 'wfc.log'),
                                                                        encoding='utf-8', errors='replace').read())
        mem[s] = OD([('texture_mb', int(m.group(1))), ('hd_loaded', int(m.group(2)))])
    CW, CH, LBL = 640, 360, 26; summary = OD()
    for sp in SPOTS:
        a, c = shot(ra, 16, sp).astype(np.int16), shot(rb, 16, sp).astype(np.int16)
        dif = np.abs(a - c).sum(2).astype(np.float32); best = (-1, 0, 0)
        # HUD = equal in every source (same build) and at AF 4 and 16 (texture filtering changes every textured surface, not the HUD)
        hud = np.ones(dif.shape, bool)
        for s, _, x in srcs:
            if x != suf[ra]: continue
            for af in (4, 16): hud &= (shot(s, af, sp).astype(np.int16) == a).all(2)
        hud[:300] = True; hud[640:820, 120:900] = True; hud[400:560, 1200:1360] = True   # HUD blends with the scene: top bar, kill feed, crosshair
        if cd:   # C and D are equal over most of the scene, so the equality mask is meaningless here: fixed zones from the '_cd' frames
            hud = np.zeros(dif.shape, bool)
            hud[:300] = True; hud[1040:1300, 100:800] = True; hud[680:840, 1180:1380] = True   # top bar, kill feed (lower here), crosshair
        hud = hud.astype(np.float32)
        for lim in (0.01, 0.03, 0.1, 1.0):
            for y in range(0, a.shape[0] - CH + 1, 60):
                for x in range(0, a.shape[1] - CW + 1, 80):
                    if hud[y:y + CH, x:x + CW].mean() > lim: continue
                    v = dif[y:y + CH, x:x + CW].mean()
                    if v > best[0]: best = (v, x, y)
            if best[0] >= 0: break
        _, x0, y0 = best
        W = max(len(srcs), 2) * (CW + 8) if not cd else max(len(srcs) * (CW + 8), 2 * 1288)
        im = Image.new('RGB', (W, LBL + 720 + 3 * (CH + LBL) + 40), (16, 16, 20)); d = ImageDraw.Draw(im)
        d.text((6, 6), 'Rust / %s   2560x1440 in game, same camera, only textures differ.  Top: full frame %s | %s (yellow box = 1:1 region)'
               % (sp, lab[top[0]].split('(')[0].strip(), lab[top[1]].split('(')[0].strip()), fill=(235, 235, 235))
        for j, s in enumerate(top):
            f = Image.fromarray(shot(s, 16, sp).astype(np.uint8)).resize((1280, 720), Image.LANCZOS); fd = ImageDraw.Draw(f)
            fd.rectangle([x0 // 2, y0 // 2, (x0 + CW) // 2, (y0 + CH) // 2], outline=(255, 220, 0), width=2)
            im.paste(f, (j * 1288, LBL))
        Y = LBL + 728; diffs = OD()
        for af in (16, 4):
            d.text((6, Y + 4), 'AF %dx, 1:1 crop' % af, fill=(255, 220, 0))
            for j, (s, l, _) in enumerate(srcs):
                fr = shot(s, af, sp); cr = fr[y0:y0 + CH, x0:x0 + CW]
                im.paste(Image.fromarray(cr), (j * (CW + 8), Y + LBL)); d.text((j * (CW + 8) + 120, Y + 4), l, fill=(235, 235, 235))
                if af == 16: diffs[s] = round(float(np.abs(cr.astype(np.int16) - shot(ra, 16, sp)[y0:y0 + CH, x0:x0 + CW]).mean()), 2)
            Y += CH + LBL
        d.text((6, Y + 4), 'AF 16x, centre of the crop at 2x (nearest), BRIGHTENED 2x for visibility (not as seen in game)', fill=(255, 220, 0))
        for j, (s, l, _) in enumerate(srcs):
            cr = shot(s, 16, sp)[y0 + CH // 4:y0 + CH // 4 + CH // 2, x0 + CW // 4:x0 + CW // 4 + CW // 2]
            cr = np.clip(cr.astype(np.int16) * 2, 0, 255).astype(np.uint8)
            im.paste(Image.fromarray(cr).resize((CW, CH), Image.NEAREST), (j * (CW + 8), Y + LBL)); d.text((j * (CW + 8) + 120, Y + 4), l, fill=(235, 235, 235))
        Y += CH + LBL
        d.text((6, Y + 10), 'texture VRAM (MEMSTATS): ' + '   '.join('%s %d MB' % (lab[s].split('(')[0].strip(), mem[s]['texture_mb']) for s, _, _ in srcs),
               fill=(200, 200, 200))
        p = os.path.join(dst, 'ingame_%s.png' % sp); im.save(p)
        summary[sp] = OD([('crop_xywh', [x0, y0, CW, CH]), ('mean_abs_diff_vs_%s_af16' % ra, diffs)])
        print(sp, (x0, y0), diffs, flush=True)
    json.dump(OD([('generated', time.strftime('%Y-%m-%d %H:%M')), ('captures', 'Rendering, Rebuild-Rendering/work/hdpush/runs (m00600, 2560x1440)'
                   + (', C / D from the _cd runs (compressed sRGB upload build); original from the earlier pilot run' if cd else '')),
                  ('memstats', mem), ('spots', summary)]), open(os.path.join(dst, 'ingame.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(mem))

if __name__ == '__main__':
    {'select': select, 'select_full': select_full, 'gen': gen, 'build': build, 'pack': pack, 'sheet': sheet, 'ingame': ingame}[sys.argv[1]]()
