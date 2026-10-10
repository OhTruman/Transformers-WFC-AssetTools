"""Optional faithful 2x HD texture pack - pilot (user decision 2026-10-09: "HD textures, true to the artists' originals";
originals stay the default; no remastering). Output only under AssetTools/out/hd, never ExtractedAssets.

  python hd_pilot.py prep      CPU: pick 50 textures across classes, decode the original top level (DDS export) to inputs
  python hd_pilot.py gpu       GPU (coordinated window): Real-ESRGAN ncnn-vulkan, two models
  python hd_pilot.py post      CPU: recombine channels, renormalise normals, faithfulness gate, BC7/BC5 + fresh mips (texconv),
                               contact sheets per class, size numbers -> manifests/hd/hd_pilot.json

Classes (authored LODGroup / SRGB from the DDS index, alpha-read flag from Rendering's texture_formats.json):
  colour   sRGB textures (Character, Weapon, environment); RGB upscaled as an image; alpha (if read) upscaled as its own channel
  normal   World/VehicleNormalMap: XYZ upscaled as an image, then every texel renormalised to unit length -> BC5 (XY)
  data     non-sRGB, non-normal (spec / masks / packed): every channel upscaled separately as greyscale (no cross-channel invention)
  excluded UI (TEXTUREGROUP_UI), lightmaps (LightAndShadowMap, baked lighting), skybox: kept original, not in the pack
Faithfulness gate (rule: no invented detail / colour / pattern; reject -> keep the original): the HD texture area-downsampled back
to the original size must reproduce the original: PSNR >= 38 dB and mean colour shift <= 1.0 / 255 per channel. Detail the
model adds above the original's resolution cannot change the downsample, so a texture fails when the model altered the image
content itself (colour shifts, moved / new patterns, halos).
Tools (AssetTools/bin, not shipped): Real-ESRGAN ncnn-vulkan v0.2.5.0 (BSD-3-Clause, github.com/xinntao/Real-ESRGAN, zip sha256
abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d); DirectXTex texconv 2026.5.8.1 (MIT, github.com/microsoft/DirectXTex,
sha256 dcfdec10244e02cf5037fba089c55fb7e1326b1c8181742d77d15fa5cb5eef06).
"""
import json, os, random, re, shutil, subprocess, sys, time
from collections import OrderedDict as OD, Counter
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
AT = os.path.normpath(os.path.join(HERE, '..', '..'))
REB = os.path.dirname(AT)
DDS = os.path.join(AT, 'out', 'dds')
HD = os.path.join(AT, 'out', 'hd')
# --v2 (Integration / user 2026-10-09 "faithful, but look better"): A) DXT deblocking of the original before upscaling and as the
# back-projection target (block artefacts are not the artists' intent); C) normal maps also via height: integrate the normals to a
# height field (Frankot-Chellappa), upscale the height, re-derive normals; output in the original block formats (Rendering:
# DXT1 / DXT5 / A8R8G8B8 at 2x, same loader path). Separate work / output roots so the first pilot stays comparable.
V2 = '--v2' in sys.argv
WORK = os.path.join(HD, '_work_v2' if V2 else '_work')
OUTV = os.path.join(HD, 'v2') if V2 else HD
ESR = os.path.join(AT, 'bin', 'realesrgan', 'realesrgan-ncnn-vulkan.exe')
TEXCONV = os.path.join(AT, 'bin', 'texconv', 'texconv.exe')
MODELS = OD([('animevideov3_x2', ('realesr-animevideov3', 2)), ('x4plus_down2', ('realesrgan-x4plus', 4))])
SEL = os.path.join(WORK, 'selection.json')

def classify(r, tf):
    g = r.get('lod_group') or ''
    if g in ('TEXTUREGROUP_UI', 'TEXTUREGROUP_LightAndShadowMap', 'TEXTUREGROUP_Skybox') or 'LightMapTexture2D' in r['object_path']:
        return 'excluded'
    name = r['object_path'].split('.')[-1].lower()
    if name == 'thumbnailtexture': return 'excluded'          # editor thumbnails, never used at runtime
    # normal maps: *_NORM / *_NRM in any group (character / weapon normals are grouped as Character / Weapon); TEXSET packs
    # (Color_NormX / Masks_NormY) are not normal maps
    if re.search(r'_(norm|nrm)$', name): return 'normal'
    # packed data / masks (authored sRGB or not; '_maks' is an authored typo of MASKS): every channel is data. Names win over the
    # LOD group (e.g. ENV_COR_RoutingPipeAGuts_MASK is grouped WorldNormalMap)
    if r.get('srgb') is False or re.search(r'mask|maks|spec|difflum|_lum$|rough|gloss|height|custab|auxglow', name): return 'data'
    if 'NormalMap' in g: return 'normal'
    return 'colour'

def load_rows():
    rows = [json.loads(l) for l in open(os.path.join(AT, 'manifests', 'extracted', 'textures_dds.jsonl'), encoding='utf-8')]
    tf = json.load(open(os.path.join(REB, 'Rebuild', 'work', 'render', 'texture_formats.json'), encoding='utf-8'))['textures']
    for r in rows:
        r['cls'] = classify(r, tf)
        r['alpha_read'] = bool((tf.get((r.get('png') or '').lower()) or {}).get('alpha')) and r['format'] in ('PF_DXT5', 'PF_A8R8G8B8') \
                          and not r.get('alpha_all_zero')
    return rows

def deblock(img, alpha=24.0, beta=6.0, tc=6.0):
    """H.264-style deblocking across the 4x4 DXT block edges (float HxWxC): a step across a block boundary is smoothed only when
    both sides are flat (|p1-p0|, |q1-q0| < beta) and the step is small (< alpha), so real edges in the art are untouched"""
    x = img.astype(np.float64).copy()
    for axis in (1, 0):
        a = np.moveaxis(x, axis, 0)
        for b in range(4, a.shape[0] - 1, 4):
            p1, p0, q0, q1 = a[b - 2], a[b - 1], a[b], a[b + 1]
            m = (np.abs(p0 - q0) < alpha) & (np.abs(p1 - p0) < beta) & (np.abs(q1 - q0) < beta)
            d = np.clip(((q0 - p0) * 4 + (p1 - q1)) / 8, -tc, tc) * m
            a[b - 1] = p0 + d; a[b] = q0 - d
        x = np.moveaxis(a, 0, axis)
    return x

def source(r_or_s):
    """the image the pack is built from: the original top level, deblocked in v2 (normals renormalised after deblocking)"""
    img = np.asarray(Image.open(os.path.join(DDS, r_or_s['dds'])).convert('RGBA'))
    if not V2: return img
    x = deblock(img)
    if r_or_s.get('cls') == 'normal':
        v = x[..., :3] / 255 * 2 - 1; v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6); x[..., :3] = (v + 1) / 2 * 255
    return np.clip(np.round(x), 0, 255).astype(np.uint8)

def normals_to_height(img):
    """Frankot-Chellappa: least-squares integrable height from the normal map (periodic, matches tiling textures);
    returns height in original-pixel units"""
    v = img[..., :3].astype(np.float64) / 255 * 2 - 1
    nz = np.maximum(v[..., 2], 0.05); p, q = -v[..., 0] / nz, -v[..., 1] / nz
    h, w = p.shape; wx = np.fft.fftfreq(w) * 2 * np.pi; wy = np.fft.fftfreq(h) * 2 * np.pi
    WX, WY = np.meshgrid(wx, wy); den = WX ** 2 + WY ** 2; den[0, 0] = 1
    Z = (-1j * WX * np.fft.fft2(p) - 1j * WY * np.fft.fft2(q)) / den; Z[0, 0] = 0
    return np.real(np.fft.ifft2(Z))

def height_to_normals(hgt, step):
    """normals from a height field sampled every `step` original pixels (central differences, periodic)"""
    gx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) / (2 * step); gy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) / (2 * step)
    v = np.dstack([-gx, -gy, np.ones_like(hgt)]); v /= np.linalg.norm(v, axis=-1, keepdims=True)
    return v

def prep():
    rows = [r for r in load_rows() if r['status'] == 'ok' and 64 <= min(r['size']) and max(r['size']) <= 1024 and r['format'] != 'PF_G8']
    random.seed(9)
    pick = []
    if V2:          # same 50 textures as the first pilot, for a like-for-like comparison
        keep = {s['object_path'] for s in json.load(open(os.path.join(HD, '_work', 'selection.json'), encoding='utf-8'))}
        rows = [r for r in rows if r['object_path'] in keep]
    want = [('colour', lambda r: r.get('lod_group') is None and not r['alpha_read'], 8), ('colour', lambda r: r.get('lod_group') == 'TEXTUREGROUP_Character', 6),
            ('colour', lambda r: r.get('lod_group') == 'TEXTUREGROUP_Weapon', 6), ('colour', lambda r: r['alpha_read'], 8),
            ('normal', lambda r: True, 12), ('data', lambda r: True, 10)]
    if V2:
        order = [s['object_path'] for s in json.load(open(os.path.join(HD, '_work', 'selection.json'), encoding='utf-8'))]
        pick = sorted(rows, key=lambda r: order.index(r['object_path']))
    else:
        for cls, f, n in want:
            pool = [r for r in rows if r['cls'] == cls and f(r) and r not in pick]
            pick += random.sample(pool, min(n, len(pool)))
    if os.path.exists(WORK): shutil.rmtree(WORK)
    for m in MODELS: os.makedirs(os.path.join(WORK, 'in'), exist_ok=True); os.makedirs(os.path.join(WORK, 'out_' + m), exist_ok=True)
    sel = []
    for k, r in enumerate(pick):
        img = np.asarray(Image.open(os.path.join(DDS, r['dds'])).convert('RGBA'))
        if r['cls'] == 'normal':
            # renormalising needs full XYZ: two-channel normals (e.g. *_XY_Norm, blue != Z) are upscaled per channel as data
            v = img[..., :3].astype(np.float64) / 255 * 2 - 1
            if float(np.abs(np.linalg.norm(v, axis=-1) - 1).mean()) > 0.08: r['cls'] = 'data'
        img = source(r)
        jobs = []
        hrange = None
        if V2 and r['cls'] == 'normal':
            hgt = normals_to_height(img); lo, hi = float(hgt.min()), float(hgt.max()); hrange = [lo, hi]
            g8 = np.clip(np.round((hgt - lo) / max(hi - lo, 1e-9) * 255), 0, 255).astype(np.uint8)
            jobs.append(('ht', np.stack([g8, g8, g8], -1)))
        if r['cls'] == 'data':
            for ci, ch in enumerate('RGB'):
                g = img[..., ci]; jobs.append(('ch' + ch, np.stack([g, g, g], -1)))
        else:
            jobs.append(('rgb', img[..., :3]))
        if r['alpha_read'] or (r['cls'] == 'data' and r['format'] == 'PF_DXT5'):
            a = img[..., 3]; jobs.append(('chA', np.stack([a, a, a], -1)))
        names = []
        for tag, arr in jobs:
            nm = '%03d_%s.png' % (k, tag); Image.fromarray(np.ascontiguousarray(arr), 'RGB').save(os.path.join(WORK, 'in', nm)); names.append(nm)
        sel.append(OD([('k', k), ('object_path', r['object_path']), ('dds', r['dds']), ('cls', r['cls']), ('lod_group', r.get('lod_group')),
                       ('format', r['format']), ('size', r['size']), ('srgb', r.get('srgb')), ('alpha_read', r['alpha_read']), ('inputs', names),
                       ('height_range', hrange)]))
    json.dump(sel, open(SEL, 'w', encoding='utf-8'), indent=1)
    excl = Counter(r['cls'] for r in load_rows())
    print('picked', len(sel), Counter(s['cls'] for s in sel), 'inputs', sum(len(s['inputs']) for s in sel), '| all textures by class', dict(excl))

def gpu():
    t = {}
    for m, (model, scale) in MODELS.items():
        t0 = time.time()
        p = subprocess.run([ESR, '-i', os.path.join(WORK, 'in'), '-o', os.path.join(WORK, 'out_' + m), '-n', model, '-s', str(scale), '-f', 'png'],
                           capture_output=True, text=True, errors='replace')
        t[m] = round(time.time() - t0, 1)
        print(m, 'rc', p.returncode, '%.1fs' % t[m], (p.stderr or '')[-300:].strip().splitlines()[-1:] if p.returncode else '', flush=True)
    json.dump(t, open(os.path.join(WORK, 'gpu_times.json'), 'w'), indent=1)

def psnr(a, b):
    m = float(((a.astype(np.float64) - b) ** 2).mean()); return 99.0 if m == 0 else 10 * np.log10(255.0 ** 2 / m)

def model_out(m, name, w2, h2):
    im = Image.open(os.path.join(WORK, 'out_' + m, name)).convert('RGB')
    if im.size != (w2, h2): im = im.resize((w2, h2), Image.BOX)        # x4plus: 4x -> 2x by area average
    return np.asarray(im)

def rebuild(s, m):
    """HD RGBA (uint8) for selection entry s from model m's channel outputs"""
    w, h = s['size']; w2, h2 = 2 * w, 2 * h
    outs = {nm.split('_', 1)[1][:-4]: model_out(m, nm, w2, h2) for nm in s['inputs']}
    if s['cls'] == 'data':
        rgb = np.stack([outs['chR'][..., 0], outs['chG'][..., 1], outs['chB'][..., 2]], -1)
    else:
        rgb = outs['rgb'].copy()
    if s['cls'] == 'normal':
        v = rgb.astype(np.float64) / 255 * 2 - 1
        v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
        rgb = np.clip(np.round((v + 1) / 2 * 255), 0, 255).astype(np.uint8)
    a = outs['chA'][..., 0] if 'chA' in outs else np.full((h2, w2), 255, np.uint8)
    return np.dstack([rgb, a]).astype(np.uint8)

# Fidelity: iterative back-projection (Irani & Peleg) forces the HD texture's area-downsample to equal the original, so colours
# and every pattern at the original resolution are the artist's; only detail above the original resolution comes from the model.
# Gate: the model's raw output must already be close (RAW_MIN_DB: it did not rewrite the image), and the corrected texture
# must reproduce the original (FINAL_MIN_DB, FINAL_MAX_SHIFT). Calibrated on the pilot: Lanczos 2x scores 35-61 dB raw.
RAW_MIN_DB, FINAL_MIN_DB, FINAL_MAX_SHIFT, IBP_ITERS = 28.0, 40.0, 0.6, 6

def _box_down(a):
    h, w = a.shape[0] // 2, a.shape[1] // 2
    return a[:2 * h, :2 * w].reshape(h, 2, w, 2, -1).mean((1, 3))

def _up(r, w2, h2):
    return np.dstack([np.asarray(Image.fromarray(r[..., c].astype(np.float32), 'F').resize((w2, h2), Image.BILINEAR)) for c in range(r.shape[2])])

def back_project(orig, hd, s):
    o = orig.astype(np.float64); x = hd.astype(np.float64)
    for _ in range(IBP_ITERS):
        x = np.clip(x + _up(o - _box_down(x), x.shape[1], x.shape[0]), 0, 255)
    x = np.round(x).astype(np.uint8)
    if s['cls'] == 'normal':                     # unit length after the correction
        v = x[..., :3].astype(np.float64) / 255 * 2 - 1; v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
        x = np.dstack([np.clip(np.round((v + 1) / 2 * 255), 0, 255).astype(np.uint8), x[..., 3]])
    return x

def gate(orig, hd, s):
    """faithfulness: HD area-downsampled back to the original size must reproduce the original"""
    w, h = s['size']
    down = np.asarray(Image.fromarray(hd, 'RGBA').resize((w, h), Image.BOX)).astype(np.float64)
    ch = [0, 1, 2] + ([3] if any('chA' in n for n in s['inputs']) else [])
    o = orig[..., ch].astype(np.float64); d = down[..., ch]
    p = psnr(o, d); shift = float(np.abs(o.reshape(-1, len(ch)).mean(0) - d.reshape(-1, len(ch)).mean(0)).max())
    return p, shift, bool(p >= 38.0 and shift <= 1.0)

def encode(hd, s, rel, modern=None):
    """full fresh mip chain via texconv (CPU encoder). modern=False: the original block formats (DXT1 / DXT5 / A8R8G8B8, Rendering's
    loader path, values stored as-is); modern=True: BC7 (sRGB colour / data) and BC5 (normal XY). v1 default: modern."""
    modern = (not V2) if modern is None else modern
    src = os.path.join(WORK, 'enc', '%03d_%s.png' % (s['k'], os.path.basename(rel)[:-4])); os.makedirs(os.path.dirname(src), exist_ok=True)
    if not os.path.exists(src): Image.fromarray(hd, 'RGBA').save(src)
    root = OUTV if not (V2 and modern) else OUTV + '_bc7'
    out = os.path.join(root, os.path.dirname(rel)); os.makedirs(out, exist_ok=True)
    if not modern:
        fmt = ['-f', {'PF_DXT1': 'BC1_UNORM', 'PF_DXT5': 'BC3_UNORM', 'PF_A8R8G8B8': 'B8G8R8A8_UNORM'}[s['format']]]
    else:
        fmt = {'colour': ['-f', 'BC7_UNORM_SRGB', '-srgb'], 'normal': ['-f', 'BC5_UNORM'], 'data': ['-f', 'BC7_UNORM']}[s['cls']]
    p = subprocess.run([TEXCONV, '-nologo', '-y', '-nogpu', '-m', '0', *fmt, '-o', out, src], capture_output=True, text=True, errors='replace')
    tmp = os.path.join(out, os.path.basename(src)[:-4] + '.dds'); dst = os.path.join(out, os.path.basename(rel))
    if p.returncode != 0 or not os.path.exists(tmp): return None
    os.replace(tmp, dst)
    return dst

def sharpness(img, s):
    """mean |Laplacian| of the luminance (normals: of the lit relief), used only to rank faithful candidates"""
    x = (_lit(img) if s['cls'] == 'normal' else img)[..., :3].astype(np.float64).mean(-1)
    lap = 4 * x - np.roll(x, 1, 0) - np.roll(x, -1, 0) - np.roll(x, 1, 1) - np.roll(x, -1, 1)
    return float(np.abs(lap).mean())

def height_candidate(s, m, target):
    """C) normals re-derived from an upscaled height field: float height (Frankot-Chellappa of the lock target) bicubic-upsampled,
    plus the model's added detail (model output minus a bicubic upscale of its own 8-bit input, in height units); normals from the
    HD height at half-pixel step. Back-projection afterwards locks it to the target like every other candidate."""
    w, h = s['size']; lo, hi = s['height_range']; sc = (hi - lo) / 255.0
    hgt = normals_to_height(target)
    base = np.asarray(Image.fromarray(hgt.astype(np.float32), 'F').resize((2 * w, 2 * h), Image.BICUBIC)).astype(np.float64)
    nm = next(n for n in s['inputs'] if n.endswith('_ht.png'))
    g8 = np.asarray(Image.open(os.path.join(WORK, 'in', nm)).convert('L')).astype(np.float32)
    g8_up = np.asarray(Image.fromarray(g8, 'F').resize((2 * w, 2 * h), Image.BICUBIC)).astype(np.float64)
    mod = model_out(m, nm, 2 * w, 2 * h)[..., 0].astype(np.float64)
    v = height_to_normals(base + (mod - g8_up) * sc, 0.5)
    a = target[..., 3]; a2 = np.asarray(Image.fromarray(a).resize((2 * w, 2 * h), Image.BICUBIC))
    return np.dstack([np.clip(np.round((v + 1) / 2 * 255), 0, 255).astype(np.uint8), a2])

def cell(arr, x, y, n):
    c = np.ascontiguousarray(arr[y:y + n, x:x + n])
    return Image.fromarray(c, 'RGBA').convert('RGB').resize((256, 256), Image.NEAREST)

def post():
    sel = json.load(open(SEL, encoding='utf-8')); res = []; tiles = {}
    for s in sel:
        orig = source(s)                        # v2: the deblocked original is the lock target
        w, h = s['size']
        lanczos = np.asarray(Image.fromarray(orig, 'RGBA').resize((2 * w, 2 * h), Image.LANCZOS))
        rec = OD([('object_path', s['object_path']), ('cls', s['cls']), ('lod_group', s['lod_group']), ('size', s['size']), ('format', s['format'])])
        if V2:
            raw0 = np.asarray(Image.open(os.path.join(DDS, s['dds'])).convert('RGBA'))
            rec['deblock_psnr_vs_original'] = round(psnr(raw0[..., :3], orig[..., :3].astype(np.float64)), 2)
        hds = {}
        cands = OD()
        for m in MODELS:
            cands[m] = rebuild(s, m)
            if V2 and s.get('height_range'):
                cands[m + '+height'] = height_candidate(s, m, orig)
        for c, raw in cands.items():
            p0, sh0, _ = gate(orig, raw, s)
            hd = back_project(orig, raw, s); p, sh, _ = gate(orig, hd, s); hds[c] = hd
            ok = bool(p0 >= RAW_MIN_DB and p >= FINAL_MIN_DB and sh <= FINAL_MAX_SHIFT)
            rec[c] = OD([('raw_psnr', round(p0, 2)), ('raw_mean_shift', round(sh0, 3)),
                         ('psnr_downsampled_vs_original', round(p, 2)), ('max_mean_shift', round(sh, 3)), ('faithful', ok),
                         ('sharpness_vs_lanczos', round(sharpness(hd, s) / max(sharpness(lanczos, s), 1e-9), 3))])
        # pick among faithful candidates: v1 the highest PSNR; v2 the sharpest (the gate already guarantees faithfulness);
        # none faithful -> keep the original (not in the pack)
        good = [c for c in cands if rec[c]['faithful']]
        key = (lambda c: rec[c]['sharpness_vs_lanczos']) if V2 else (lambda c: rec[c]['psnr_downsampled_vs_original'])
        best = max(good, key=key) if good else None
        rec['chosen'] = best or 'original (rejected: no faithful upscale)'
        if best:
            dst = encode(hds[best], s, s['dds'])
            rec['hd_dds'] = os.path.relpath(dst, OUTV).replace(os.sep, '/') if dst else None
            rec['hd_bytes'] = os.path.getsize(dst) if dst else None
            rec['hd_png_uncompressed'] = os.path.relpath(os.path.join(WORK, 'enc', '%03d_%s.png' % (s['k'], os.path.basename(s['dds'])[:-4])), OUTV).replace(os.sep, '/')
            if V2:          # the same HD also as BC7 / BC5, so the user can compare both formats after compression
                d7 = encode(hds[best], s, s['dds'], modern=True)
                rec['hd_dds_bc7'] = os.path.relpath(d7, OUTV + '_bc7').replace(os.sep, '/') if d7 else None
                rec['hd_bytes_bc7'] = os.path.getsize(d7) if d7 else None
        rec['orig_bytes'] = os.path.getsize(os.path.join(DDS, s['dds']))
        res.append(rec)
        # centre 64 px of the original vs the matching 128 px of each 2x version, all shown at 256 px
        x0, y0 = max(0, w // 2 - 32), max(0, h // 2 - 32)
        cells = [cell(orig, x0, y0, 64), cell(lanczos, 2 * x0, 2 * y0, 128)] + [cell(hds[m], 2 * x0, 2 * y0, 128) for m in MODELS]
        tiles.setdefault(s['cls'], []).append((rec, cells))
    for cls, L in tiles.items():
        W = 4 * 262 + 6; Hh = 30 + len(L) * 290
        sheet = Image.new('RGB', (W, Hh), (18, 18, 22)); d = ImageDraw.Draw(sheet)
        d.text((6, 8), '%s: original (nearest) | Lanczos 2x | %s | %s   (centre crop; gate = downsample back vs original)' % ((cls,) + tuple(MODELS)), fill=(230, 230, 230))
        for i, (rec, cells) in enumerate(L):
            y = 30 + i * 290
            lab = '%s %s %s | ' % (rec['object_path'].split('.')[-1], rec['size'], rec['lod_group'] or '-') + \
                  ' | '.join('%s %.1f dB %s' % (m[:14], rec[m]['psnr_downsampled_vs_original'], 'OK' if rec[m]['faithful'] else 'REJECT') for m in MODELS) + \
                  ' | chosen: %s' % rec['chosen'][:22]
            d.text((6, y + 6), lab, fill=(255, 210, 120))
            for j, c in enumerate(cells): sheet.paste(c, (6 + j * 262, y + 26))
        sheet.save(os.path.join(OUTV, '_pilot_sheet_%s.png' % cls))
    MB = 1024 ** 2
    by = OD()
    for cls in ('colour', 'normal', 'data'):
        rr = [r for r in res if r['cls'] == cls]; ok = [r for r in rr if r.get('hd_bytes')]
        by[cls] = OD([('pilot', len(rr)), ('accepted', len(ok)), ('rejected', len(rr) - len(ok)),
                      ('chosen_models', dict(Counter(r['chosen'] for r in rr))),
                      ('hd_over_original_bytes', round(sum(r['hd_bytes'] for r in ok) / max(1, sum(r['orig_bytes'] for r in ok)), 2))])
    # whole-pack size estimate: per class, all eligible originals x pilot byte ratio x pilot acceptance rate
    rows = load_rows(); est = OD()
    for cls, b in by.items():
        orig = sum(os.path.getsize(os.path.join(DDS, r['dds'])) for r in rows if r['cls'] == cls and r['status'] == 'ok')
        est[cls] = OD([('original_MB', round(orig / MB)), ('hd_pack_MB_estimate', round(orig * b['hd_over_original_bytes'] * b['accepted'] / max(1, b['pilot']) / MB))])
        if V2:          # the same estimate for the BC7 / BC5 encodes
            ok = [r for r in res if r['cls'] == cls and r.get('hd_bytes_bc7')]
            ratio7 = sum(r['hd_bytes_bc7'] for r in ok) / max(1, sum(r['orig_bytes'] for r in ok))
            est[cls]['hd_pack_MB_estimate_bc7'] = round(orig * ratio7 * b['accepted'] / max(1, b['pilot']) / MB)
    if V2:
        est_formats = OD([('dxt_GB', round(sum(v['hd_pack_MB_estimate'] for v in est.values()) / 1024, 1)),
                          ('bc7_GB', round(sum(v['hd_pack_MB_estimate_bc7'] for v in est.values()) / 1024, 1))])
    out = OD([('generated_by', 'AssetTools/scripts/wfc/hd_pilot.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('decision', 'user 2026-10-09: optional faithful 2x HD pack (originals stay default; no remastering)'),
              ('models', OD((m, OD([('model', v[0]), ('native_scale', v[1])])) for m, v in MODELS.items())),
              ('gpu_seconds', json.load(open(os.path.join(WORK, 'gpu_times.json')))),
              ('gate', 'model raw output >= %.0f dB (area-downsample vs original); after back-projection >= %.0f dB and max per-channel mean shift <= %.1f/255; else keep the original' % (RAW_MIN_DB, FINAL_MIN_DB, FINAL_MAX_SHIFT)),
              ('by_class', by), ('pack_size_estimate', est), ('pack_total_MB_estimate', sum(v['hd_pack_MB_estimate'] for v in est.values())),
              ('pack_size_estimate_formats', est_formats if V2 else None),
              ('sheets', [os.path.relpath(os.path.join(OUTV, '_pilot_sheet_%s.png' % c), REB).replace(os.sep, '/') for c in tiles]), ('textures', res)])
    os.makedirs(os.path.join(AT, 'manifests', 'hd'), exist_ok=True)
    json.dump(out, open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v2.json' if V2 else 'hd_pilot.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(OD([('by_class', by), ('pack_size_estimate', est), ('total_MB', out['pack_total_MB_estimate'])]), indent=1))

COMPARE = ['VH_SoldierTankAutCore_GrungeClr', 'WEP_TortureSword_CLR', 'WEP_Bazooka_CLR', 'WEP_SentryBlaster01_CLR', 'TrypBridgeSupport_CLR',
           'ENV_IAC_CleanTerminalFloor_TEXSET_Color_NormX', 'museumWall2_CLR', 'VH_AirRaid_NORM']

def _lit(rgb, bc5=False):
    """normal map -> greyscale relief lit by a raking light (easier to judge than raw normal colours)"""
    v = rgb[..., :3].astype(np.float64) / 255 * 2 - 1
    if bc5: v[..., 2] = np.sqrt(np.clip(1 - v[..., 0] ** 2 - v[..., 1] ** 2, 0, 1))
    v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
    L = np.array([-0.6, 0.5, 0.62]); L /= np.linalg.norm(L)
    g = np.clip(v @ L, 0, 1) * 235 + 20
    return np.dstack([g, g, g]).astype(np.uint8)

def compare():
    """user-facing before / after: the most detailed 128 px region of the original (bilinear to 768) vs the same region of the
    shipped HD DDS (256 px, bilinear to 768), labelled Original / HD"""
    res = {r['object_path'].split('.')[-1]: r for r in json.load(open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot.json'), encoding='utf-8'))['textures']}
    sel = {s['object_path'].split('.')[-1]: s for s in json.load(open(SEL, encoding='utf-8'))}
    od = os.path.join(HD, 'compare'); os.makedirs(od, exist_ok=True); made = []
    for name in COMPARE:
        r, s = res.get(name), sel.get(name)
        if not r or not r.get('hd_dds'): continue
        orig = np.asarray(Image.open(os.path.join(DDS, s['dds'])).convert('RGBA'))[..., :3]
        hd = np.asarray(Image.open(os.path.join(HD, r['hd_dds'])).convert('RGB'))
        if s['cls'] == 'normal': orig, hd = _lit(orig), _lit(hd, bc5=True)
        g = np.abs(np.diff(orig.astype(np.float64).mean(-1), axis=0))[:, :-1] + np.abs(np.diff(orig.astype(np.float64).mean(-1), axis=1))[:-1, :]
        n = 128; h, w = g.shape
        best = max(((g[y:y + n, x:x + n].sum(), x, y) for y in range(0, max(1, h - n), 32) for x in range(0, max(1, w - n), 32)))
        _, x, y = best
        a = Image.fromarray(np.ascontiguousarray(orig[y:y + n, x:x + n])).resize((768, 768), Image.BILINEAR)
        b = Image.fromarray(np.ascontiguousarray(hd[2 * y:2 * y + 2 * n, 2 * x:2 * x + 2 * n])).resize((768, 768), Image.BILINEAR)
        im = Image.new('RGB', (768 * 2 + 30, 768 + 70), (16, 16, 20)); d = ImageDraw.Draw(im)
        im.paste(a, (10, 50)); im.paste(b, (768 + 20, 50))
        d.text((10, 10), 'Original  (%dx%d, %s)' % (s['size'][0], s['size'][1], s['format'].replace('PF_', '')), fill=(235, 235, 235))
        d.text((768 + 20, 10), 'HD  (%dx%d, %s, faithful: downsample = original)' % (2 * s['size'][0], 2 * s['size'][1],
               'BC5' if s['cls'] == 'normal' else 'BC7'), fill=(255, 210, 120))
        d.text((10, 30), '%s  %s  - zoomed crop%s' % (name, s['lod_group'] or 'environment', ', normal map shown lit' if s['cls'] == 'normal' else ''), fill=(170, 170, 170))
        p = os.path.join(od, '%02d_%s.png' % (len(made) + 1, name)); im.save(p, optimize=True); made.append((p, os.path.getsize(p)))
    for p, sz in made: print(os.path.relpath(p, AT), '%.1f MB' % (sz / 2 ** 20))

def compare_v2():
    """user-facing format choice: the same most-detailed region, 4 columns at 512 px: Original (bilinear) | HD A+C uncompressed |
    HD as DXT (original formats, decoded from the shipped file) | HD as BC7 / BC5 (decoded from the file); sizes are the pilot's"""
    man = json.load(open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v2.json'), encoding='utf-8'))
    res = {r['object_path'].split('.')[-1]: r for r in man['textures']}
    sel = {s['object_path'].split('.')[-1]: s for s in json.load(open(SEL, encoding='utf-8'))}
    est = man.get('pack_size_estimate_formats') or {}
    od = os.path.join(OUTV, 'compare'); os.makedirs(od, exist_ok=True); made = []
    for name in COMPARE:
        r, s = res.get(name), sel.get(name)
        if not r or not r.get('hd_dds') or not r.get('hd_dds_bc7'): continue
        nrm = s['cls'] == 'normal'
        orig = np.asarray(Image.open(os.path.join(DDS, s['dds'])).convert('RGB'))
        raw = np.asarray(Image.open(os.path.join(OUTV, r['hd_png_uncompressed'])).convert('RGB'))
        dxt = np.asarray(Image.open(os.path.join(OUTV, r['hd_dds'])).convert('RGB'))
        bc7 = np.asarray(Image.open(os.path.join(OUTV + '_bc7', r['hd_dds_bc7'])).convert('RGB'))
        if nrm: orig, raw, dxt, bc7 = _lit(orig), _lit(raw), _lit(dxt), _lit(bc7, bc5=True)
        g = orig.astype(np.float64).mean(-1); g = np.abs(np.diff(g, axis=0))[:, :-1] + np.abs(np.diff(g, axis=1))[:-1, :]
        n = 96; h, w = g.shape
        _, x, y = max(((g[yy:yy + n, xx:xx + n].sum(), xx, yy) for yy in range(0, max(1, h - n), 16) for xx in range(0, max(1, w - n), 16)))
        S = 512
        cols = [('Original  %dx%d %s' % (s['size'][0], s['size'][1], s['format'].replace('PF_', '')), orig, 1),
                ('HD A+C, uncompressed', raw, 2),
                ('HD in original formats (%s)  pack ~%s GB' % (s['format'].replace('PF_', ''), est.get('dxt_GB', '?')), dxt, 2),
                ('HD in %s  pack ~%s GB' % ('BC5' if nrm else 'BC7', est.get('bc7_GB', '?')), bc7, 2)]
        im = Image.new('RGB', (4 * S + 50, S + 74), (16, 16, 20)); d = ImageDraw.Draw(im)
        d.text((10, 8), '%s  (%s)%s - zoomed crop, all from the same region; HD is locked to the original: shrunk back down it equals it' % (
            name, s['lod_group'] or 'environment', ', normal map shown lit' if nrm else ''), fill=(170, 170, 170))
        for i, (lab, arr, f) in enumerate(cols):
            c = Image.fromarray(np.ascontiguousarray(arr[f * y:f * (y + n), f * x:f * (x + n)])).resize((S, S), Image.BILINEAR)
            im.paste(c, (10 + i * (S + 10), 56)); d.text((10 + i * (S + 10), 34), lab, fill=(255, 210, 120) if i else (235, 235, 235))
        p = os.path.join(od, '%02d_%s.png' % (len(made) + 1, name)); im.save(p, optimize=True); made.append((p, os.path.getsize(p)))
    for p, sz in made: print(os.path.relpath(p, AT), '%.1f MB' % (sz / 2 ** 20))

if __name__ == '__main__':
    {'prep': prep, 'gpu': gpu, 'post': post, 'compare': compare, 'compare_v2': compare_v2}[sys.argv[1]]()
