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
WORK = os.path.join(HD, '_work')
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
    if r.get('srgb') is False or re.search(r'mask|maks|spec|difflum|_lum$|rough|gloss|height', name): return 'data'
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

def prep():
    rows = [r for r in load_rows() if r['status'] == 'ok' and 64 <= min(r['size']) and max(r['size']) <= 1024 and r['format'] != 'PF_G8']
    random.seed(9)
    pick = []
    want = [('colour', lambda r: r.get('lod_group') is None and not r['alpha_read'], 8), ('colour', lambda r: r.get('lod_group') == 'TEXTUREGROUP_Character', 6),
            ('colour', lambda r: r.get('lod_group') == 'TEXTUREGROUP_Weapon', 6), ('colour', lambda r: r['alpha_read'], 8),
            ('normal', lambda r: True, 12), ('data', lambda r: True, 10)]
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
        jobs = []
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
                       ('format', r['format']), ('size', r['size']), ('srgb', r.get('srgb')), ('alpha_read', r['alpha_read']), ('inputs', names)]))
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

def encode(hd, s, rel):
    """BC7 (sRGB for colour) / BC5 (normal XY) with a full fresh mip chain via texconv (CPU encoder)"""
    src = os.path.join(WORK, 'enc', os.path.basename(rel)[:-4] + '.png'); os.makedirs(os.path.dirname(src), exist_ok=True)
    Image.fromarray(hd, 'RGBA').save(src)
    out = os.path.join(HD, os.path.dirname(rel)); os.makedirs(out, exist_ok=True)
    fmt = {'colour': ['-f', 'BC7_UNORM_SRGB', '-srgb'], 'normal': ['-f', 'BC5_UNORM'], 'data': ['-f', 'BC7_UNORM']}[s['cls']]
    p = subprocess.run([TEXCONV, '-nologo', '-y', '-nogpu', '-m', '0', *fmt, '-o', out, src], capture_output=True, text=True, errors='replace')
    dst = os.path.join(out, os.path.basename(src)[:-4] + '.dds')
    return dst if p.returncode == 0 and os.path.exists(dst) else None

def cell(arr, x, y, n):
    c = np.ascontiguousarray(arr[y:y + n, x:x + n])
    return Image.fromarray(c, 'RGBA').convert('RGB').resize((256, 256), Image.NEAREST)

def post():
    sel = json.load(open(SEL, encoding='utf-8')); res = []; tiles = {}
    for s in sel:
        orig = np.asarray(Image.open(os.path.join(DDS, s['dds'])).convert('RGBA'))
        w, h = s['size']
        lanczos = np.asarray(Image.fromarray(orig, 'RGBA').resize((2 * w, 2 * h), Image.LANCZOS))
        rec = OD([('object_path', s['object_path']), ('cls', s['cls']), ('lod_group', s['lod_group']), ('size', s['size']), ('format', s['format'])])
        hds = {}
        for m in MODELS:
            raw = rebuild(s, m); p0, sh0, _ = gate(orig, raw, s)
            hd = back_project(orig, raw, s); p, sh, _ = gate(orig, hd, s); hds[m] = hd
            ok = bool(p0 >= RAW_MIN_DB and p >= FINAL_MIN_DB and sh <= FINAL_MAX_SHIFT)
            rec[m] = OD([('raw_psnr', round(p0, 2)), ('raw_mean_shift', round(sh0, 3)),
                         ('psnr_downsampled_vs_original', round(p, 2)), ('max_mean_shift', round(sh, 3)), ('faithful', ok)])
        # pick: the faithful model with the higher PSNR; none faithful -> keep the original (not in the pack)
        cand = [m for m in MODELS if rec[m]['faithful']]
        best = max(cand, key=lambda m: rec[m]['psnr_downsampled_vs_original']) if cand else None
        rec['chosen'] = best or 'original (rejected: no faithful upscale)'
        if best:
            dst = encode(hds[best], s, s['dds'])
            rec['hd_dds'] = os.path.relpath(dst, HD).replace(os.sep, '/') if dst else None
            rec['hd_bytes'] = os.path.getsize(dst) if dst else None
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
        sheet.save(os.path.join(HD, '_pilot_sheet_%s.png' % cls))
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
    out = OD([('generated_by', 'AssetTools/scripts/wfc/hd_pilot.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('decision', 'user 2026-10-09: optional faithful 2x HD pack (originals stay default; no remastering)'),
              ('models', OD((m, OD([('model', v[0]), ('native_scale', v[1])])) for m, v in MODELS.items())),
              ('gpu_seconds', json.load(open(os.path.join(WORK, 'gpu_times.json')))),
              ('gate', 'model raw output >= %.0f dB (area-downsample vs original); after back-projection >= %.0f dB and max per-channel mean shift <= %.1f/255; else keep the original' % (RAW_MIN_DB, FINAL_MIN_DB, FINAL_MAX_SHIFT)),
              ('by_class', by), ('pack_size_estimate', est), ('pack_total_MB_estimate', sum(v['hd_pack_MB_estimate'] for v in est.values())),
              ('sheets', ['AssetTools/out/hd/_pilot_sheet_%s.png' % c for c in tiles]), ('textures', res)])
    os.makedirs(os.path.join(AT, 'manifests', 'hd'), exist_ok=True)
    json.dump(out, open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot.json'), 'w', encoding='utf-8'), indent=1)
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

if __name__ == '__main__':
    {'prep': prep, 'gpu': gpu, 'post': post, 'compare': compare}[sys.argv[1]]()
