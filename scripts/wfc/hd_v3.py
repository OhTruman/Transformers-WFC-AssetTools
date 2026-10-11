"""HD pack step B evaluation (stronger models, hd_torch.py outputs in out/hd/_work_v3): same faithfulness lock as v2 (back-projection
to the DXT-deblocked original), same gate, pick the sharpest faithful candidate per texture; plus a 4x tier for character / weapon
textures (the most-seen surfaces) from the transformer outputs, locked at factor 4. Encodes the picks in the original block formats
(Rendering's loader path) and writes user-facing comparisons Original | v2 | best B 2x | best B 4x.

  python hd_v3.py post        -> manifests/hd/hd_pilot_v3.json, out/hd/v3/...
  python hd_v3.py compare     -> out/hd/v3/compare/*.png
"""
import json, os, sys
from collections import OrderedDict as OD, Counter
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if '--v2' not in sys.argv: sys.argv.append('--v2')       # hd_pilot in v2 mode: deblocked source / lock target, original formats
import hd_pilot as H  # noqa: E402

AT = H.AT
H.WORK = os.path.join(H.HD, '_work_v3'); H.SEL = os.path.join(H.WORK, 'selection.json'); H.OUTV = os.path.join(H.HD, 'v3')
FAST = ['4x-PBRify-RPLKSRd-V3', '2x-AoMR-mosr']
TRANSFORMERS = ['4x-PBRify-UpscalerDAT2-V1', '4x-TextureDAT2-otf', '4x-Textures-GTAV-rgt-s']
NORMAL = '4x-Normal-RG0-BC1'
V2MAN = os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v2.json')

def out_img(m, name, size):
    """model output for one input PNG resized (area) to `size`; None if the model did not process that input"""
    p = os.path.join(H.WORK, 'out_' + m, name)
    if not os.path.exists(p): return None
    im = Image.open(p).convert('RGB')
    return np.asarray(im if im.size == size else im.resize(size, Image.BOX))

def assemble(s, m, f):
    """HD RGBA at f x from model m (None if m lacks any needed input); data channels separately, alpha separately"""
    w, h = s['size']; size = (f * w, f * h)
    ins = [n for n in s['inputs'] if not n.endswith('_ht.png')]
    outs = {}
    for n in ins:
        o = out_img(m, n, size)
        if o is None: return None
        outs[n.split('_', 1)[1][:-4]] = o
    rgb = np.stack([outs['chR'][..., 0], outs['chG'][..., 1], outs['chB'][..., 2]], -1) if s['cls'] == 'data' else outs['rgb'].copy()
    a = outs['chA'][..., 0] if 'chA' in outs else np.full(size[::-1], 255, np.uint8)
    return np.dstack([rgb, a]).astype(np.uint8)

def normal_rg0(s, f):
    """4x-Normal-RG0-BC1 output (B zeroed by convention): Z reconstructed from XY, unit length"""
    w, h = s['size']; n = next(x for x in s['inputs'] if x.endswith('_rgb.png'))
    o = out_img(NORMAL, n, (f * w, f * h))
    if o is None: return None
    v = o[..., :3].astype(np.float64) / 255 * 2 - 1
    v[..., 2] = np.sqrt(np.clip(1 - v[..., 0] ** 2 - v[..., 1] ** 2, 0, 1))
    v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
    return np.dstack([np.clip(np.round((v + 1) / 2 * 255), 0, 255).astype(np.uint8), np.full((f * h, f * w), 255, np.uint8)])

def box_down(a, f):
    h, w = a.shape[0] // f, a.shape[1] // f
    return a[:f * h, :f * w].reshape(h, f, w, f, -1).mean((1, 3))

def lock(target, hd, s, f, iters=6):
    """back-projection at factor f: the area-downsample of the result equals the (deblocked) original"""
    o = target.astype(np.float64); x = hd.astype(np.float64)
    for _ in range(iters):
        x = np.clip(x + H._up(o - box_down(x, f), x.shape[1], x.shape[0]), 0, 255)
    x = np.round(x).astype(np.uint8)
    if s['cls'] == 'normal':
        v = x[..., :3].astype(np.float64) / 255 * 2 - 1; v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
        x = np.dstack([np.clip(np.round((v + 1) / 2 * 255), 0, 255).astype(np.uint8), x[..., 3]])
    return x

def evaluate(target, raw, s, f):
    p0, sh0, _ = H.gate(target, raw, s); hd = lock(target, raw, s, f); p, sh, _ = H.gate(target, hd, s)
    ok = bool(p0 >= H.RAW_MIN_DB and p >= H.FINAL_MIN_DB and sh <= H.FINAL_MAX_SHIFT)
    return hd, OD([('raw_psnr', round(p0, 2)), ('final_psnr', round(p, 2)), ('max_mean_shift', round(sh, 3)), ('faithful', ok)])

def post():
    sel = json.load(open(H.SEL, encoding='utf-8')); v2 = {r['object_path']: r for r in json.load(open(V2MAN, encoding='utf-8'))['textures']}
    res = []
    for s in sel:
        target = H.source(s); w, h = s['size']
        lz = H.resize_straight(target, (2 * w, 2 * h), Image.LANCZOS); base = H.sharpness(lz, s)
        rec = OD([('object_path', s['object_path']), ('cls', s['cls']), ('lod_group', s['lod_group']), ('size', s['size']), ('format', s['format']), ('cands', OD())])
        hds = {}
        names = FAST + TRANSFORMERS + ([NORMAL] if s['cls'] == 'normal' else [])
        for m in names:
            raw = normal_rg0(s, 2) if m == NORMAL else assemble(s, m, 2)
            if raw is None: continue
            hd, g = evaluate(target, raw, s, 2); g['sharpness_vs_lanczos'] = round(H.sharpness(hd, s) / max(base, 1e-9), 3)
            rec['cands'][m] = g; hds[m] = hd
        v2r = v2.get(s['object_path']) or {}
        rec['v2_chosen'] = v2r.get('chosen'); rec['v2_sharpness'] = (v2r.get(v2r.get('chosen')) or {}).get('sharpness_vs_lanczos')
        good = [m for m, g in rec['cands'].items() if g['faithful']]
        best = max(good, key=lambda m: rec['cands'][m]['sharpness_vs_lanczos']) if good else None
        rec['chosen_2x'] = best or 'original (rejected)'
        if best:
            d = H.encode(hds[best], s, s['dds']); rec['hd2_dds'] = os.path.relpath(d, H.OUTV).replace(os.sep, '/') if d else None
            rec['hd2_bytes'] = os.path.getsize(d) if d else None
            png = os.path.join(H.OUTV, '_png2', '%03d.png' % s['k']); os.makedirs(os.path.dirname(png), exist_ok=True)
            Image.fromarray(hds[best], 'RGBA').save(png); rec['hd2_png'] = os.path.relpath(png, H.OUTV).replace(os.sep, '/')
        # 4x tier: character / weapon textures with transformer outputs
        if s['lod_group'] in ('TEXTUREGROUP_Character', 'TEXTUREGROUP_Weapon'):
            c4 = OD()
            for m in TRANSFORMERS:
                raw = assemble(s, m, 4)
                if raw is None: continue
                hd4, g = evaluate(target, raw, s, 4); c4[m] = (hd4, g)
            ok4 = {m: v for m, v in c4.items() if v[1]['faithful']}
            if ok4:
                m4 = max(ok4, key=lambda m: H.sharpness(ok4[m][0], s)); rec['chosen_4x'] = m4; rec['cands_4x'] = OD((m, v[1]) for m, v in c4.items())
                png = os.path.join(H.OUTV, '_png4', '%03d.png' % s['k']); os.makedirs(os.path.dirname(png), exist_ok=True)
                Image.fromarray(ok4[m4][0], 'RGBA').save(png); rec['hd4_png'] = os.path.relpath(png, H.OUTV).replace(os.sep, '/')
                # 4x size: encode into a separate root
                save = H.OUTV; H.OUTV = os.path.join(H.HD, 'v3_4x')
                d4 = H.encode(ok4[m4][0], dict(s, k=1000 + s['k']), s['dds']); H.OUTV = save
                rec['hd4_bytes'] = os.path.getsize(d4) if d4 else None
        rec['orig_bytes'] = os.path.getsize(os.path.join(H.DDS, s['dds']))
        res.append(rec); print(s['object_path'].split('.')[-1][:34], s['cls'], 'v2', rec['v2_chosen'], rec['v2_sharpness'], '-> 2x', rec['chosen_2x'],
                               (rec['cands'].get(rec['chosen_2x']) or {}).get('sharpness_vs_lanczos'), '| 4x', rec.get('chosen_4x'), flush=True)
    by = OD()
    for cls in ('colour', 'normal', 'data'):
        rr = [r for r in res if r['cls'] == cls]; ok = [r for r in rr if r.get('hd2_bytes')]
        by[cls] = OD([('pilot', len(rr)), ('accepted', len(ok)), ('chosen', dict(Counter(r['chosen_2x'] for r in rr))),
                      ('median_sharpness_v2', float(np.median([r['v2_sharpness'] for r in rr if r['v2_sharpness']] or [0]))),
                      ('median_sharpness_v3', float(np.median([r['cands'][r['chosen_2x']]['sharpness_vs_lanczos'] for r in ok] or [0])))])
    four = [r for r in res if r.get('hd4_bytes')]
    out = OD([('generated_by', 'AssetTools/scripts/wfc/hd_v3.py'), ('models', 'AssetTools/bin/hdmodels/models.json'),
              ('lock', 'back-projection to the DXT-deblocked original (2x: factor 2; 4x tier: factor 4); gate as hd_pilot'),
              ('by_class', by), ('four_x_tier', OD([('textures', len(four)), ('chosen', dict(Counter(r['chosen_4x'] for r in four))),
                                                    ('bytes_over_original', round(sum(r['hd4_bytes'] for r in four) / max(1, sum(r['orig_bytes'] for r in four)), 2))])),
              ('textures', res)])
    json.dump(out, open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v3.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(OD([('by_class', by), ('four_x_tier', out['four_x_tier'])]), indent=1))

def compare():
    man = json.load(open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v3.json'), encoding='utf-8'))
    v2 = {r['object_path']: r for r in json.load(open(V2MAN, encoding='utf-8'))['textures']}
    sel = {s['object_path']: s for s in json.load(open(H.SEL, encoding='utf-8'))}
    od = os.path.join(H.OUTV, 'compare'); os.makedirs(od, exist_ok=True); made = []
    for r in man['textures']:
        name = r['object_path'].split('.')[-1]
        if name not in H.COMPARE or not r.get('hd2_dds'): continue
        s = sel[r['object_path']]; nrm = s['cls'] == 'normal'
        orig = np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGB'))
        v2p = v2[r['object_path']].get('hd_dds')
        v2i = np.asarray(Image.open(os.path.join(H.HD, 'v2', v2p)).convert('RGB')) if v2p else None
        b2 = np.asarray(Image.open(os.path.join(H.OUTV, r['hd2_dds'])).convert('RGB'))
        b4 = np.asarray(Image.open(os.path.join(H.OUTV, r['hd4_png'])).convert('RGB')) if r.get('hd4_png') else None
        if nrm: orig, b2 = H._lit(orig), H._lit(b2); v2i = H._lit(v2i) if v2i is not None else None
        g = orig.astype(np.float64).mean(-1); g = np.abs(np.diff(g, axis=0))[:, :-1] + np.abs(np.diff(g, axis=1))[:-1, :]
        n = 96; hh, ww = g.shape
        _, x, y = max(((g[yy:yy + n, xx:xx + n].sum(), xx, yy) for yy in range(0, max(1, hh - n), 16) for xx in range(0, max(1, ww - n), 16)))
        cols = [('Original %dx%d' % tuple(s['size']), orig, 1)]
        if v2i is not None: cols.append(('v2 (Real-ESRGAN, 2x, DXT)', v2i, 2))
        cols.append(('B: %s 2x, DXT' % r['chosen_2x'], b2, 2))
        if b4 is not None: cols.append(('B: %s 4x' % r['chosen_4x'], b4, 4))
        S = 512; im = Image.new('RGB', (len(cols) * (S + 10) + 10, S + 74), (16, 16, 20)); d = ImageDraw.Draw(im)
        d.text((10, 8), '%s (%s)%s - same zoomed region; every HD version shrinks back to the original' % (name, s['lod_group'] or 'environment',
               ', normal map shown lit' if nrm else ''), fill=(170, 170, 170))
        for i, (lab, arr, f) in enumerate(cols):
            c = Image.fromarray(np.ascontiguousarray(arr[f * y:f * (y + n), f * x:f * (x + n)])).resize((S, S), Image.BILINEAR)
            im.paste(c, (10 + i * (S + 10), 56)); d.text((10 + i * (S + 10), 34), lab, fill=(255, 210, 120) if i else (235, 235, 235))
        p = os.path.join(od, '%02d_%s.png' % (H.COMPARE.index(name) + 1, name)); im.save(p, optimize=True); made.append(p)
    for p in sorted(made): print(os.path.relpath(p, AT), '%.1f MB' % (os.path.getsize(p) / 2 ** 20))

if __name__ == '__main__':
    {'post': post, 'compare': compare}[sys.argv[1]]()
