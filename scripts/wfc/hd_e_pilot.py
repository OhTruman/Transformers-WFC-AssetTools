"""Level E pilot (user 2026-10-12 via Integration: "it can go beyond faithful ... realistic and new"; docs/HD_BEYOND_D_PLAN.md).

E adds surface detail the original never had (grime in cavities, edge wear, micro grain, matching micro relief) on top of the
reviewed D result, under a SOFT lock: the result, box-downsampled to the original size, is pulled back to D's own downsample, so
layout, shapes and palette stay the artist's and only sub-original-pixel detail is new. No diffusion here (no diffusion stack is
installed): this is the plan's detail-map synthesis route, from local CC0 models only (1x-PBRify-Height on the D colour).

  python hd_e_pilot.py list                 pilot units (Rust textures already packed at D, colour-bearing)
  python hd_e_pilot.py ladder               out/hd/push_e_pilot/ladder/<i>.png: orig | D | E1 | E2 | E3, busiest + flattest spot
  python hd_e_pilot.py pack [E1|E2|E3]      out/hd/push_e_pilot/pack (+ hd_index.json) at one strength, for WFC_HD_ROOT

Resumable; stops (exit 75) on PERF_HOLD or low free commit, like the D jobs. CPU only.
"""
import glob, json, os, sys, time
from collections import OrderedDict as OD
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('WFC_HD_PUSH_SET', 'full')
import hd_push as P  # noqa: E402

AT = os.path.dirname(os.path.dirname(HERE))
D_ROOT = os.path.join(AT, 'out', 'hd', 'push_full')
E_ROOT = os.path.join(AT, 'out', 'hd', 'push_e_pilot')
RUST_TSV = os.path.join(os.path.dirname(AT), 'Rebuild-Rendering', 'work', 'handoff_assettools', 'MP_IAC_Rust_textures.tsv')
STRENGTH = OD([('E1', 0.5), ('E2', 1.0), ('E3', 1.6)])
GRIME, WEAR, GRAIN, SHADE, MICRO = 0.45, 0.30, 2.5, 18.0, 0.6   # at strength 1: cavity darkening, edge lightening, grain and
# height shading (8-bit levels), relief. v1 (grain 10, no shading) read as sensor noise on the first ladder: grain cut, detail from height

def stop():
    s = glob.glob(os.path.join(P.REB, '*', 'work', 'PERF_HOLD')) + P.low_commit()
    if s: print('stopping:', s, flush=True); sys.exit(75)

def units():
    """colour-bearing D-packed rows that Rust's materials bind (Rendering's list), with their TEXSET partner"""
    idx = json.load(open(os.path.join(D_ROOT, 'pack', 'hd_index.json'), encoding='utf-8'))
    packed = {r['object_path'].lower(): r for r in idx['rows']}
    rust = [l.split('\t')[0].lower() for l in open(RUST_TSV, encoding='utf-8') if not l.startswith('#')][1:]
    R = P.rows(); by_obj = {r['object_path'].lower(): r for r in R}; out = []   # not by png: 8 selection rows share a png path
    for op in rust:
        d = packed.get(op)
        if not d: continue
        r = by_obj[op]
        if r['kind'] not in ('colour', 'texset_color'): continue
        if r['png'].split('/')[1].upper().startswith(('CHR_', 'WEP_', 'CH_', 'TR_CHR')): continue   # characters / weapons: not by default
        m = P.partner(r, R) if r['kind'] == 'texset_color' else None
        md = packed.get(m['object_path'].lower()) if m else None
        out.append((r, d, m, md))
    return out, R

def load_d(d):
    return np.asarray(Image.open(os.path.join(D_ROOT, 'pack', d['dds'])).convert('RGBA')).astype(np.float32)

def periodic_grain(h, w, f, seed):
    """tileable band-limited noise (FFT): only wavelengths below 2 original pixels, so it vanishes in the soft lock's downsample"""
    rng = np.random.default_rng(seed)
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.rfftfreq(w)[None, :]; k = np.sqrt(fx * fx + fy * fy)
    band = (k > 1.0 / (2 * f)) * np.power(np.maximum(k, 1e-6), -0.8)
    z = np.fft.irfft2(band * np.exp(2j * np.pi * rng.random(k.shape)), s=(h, w)).astype(np.float32)
    return z / (z.std() + 1e-6)

def height(rgb_u8, cache):
    """1x-PBRify-Height on the D colour (cached per texture: it is the slow step)"""
    if os.path.exists(cache): return np.asarray(Image.open(cache)).astype(np.float32) / 65535
    import torch, hd_torch as T
    torch.set_num_threads(int(os.environ.get('WFC_HD_CPU_THREADS', '12'))); dev = torch.device('cpu')
    h = T.upscale(T.load('1x-PBRify-Height', dev), dev, rgb_u8).astype(np.float32).mean(-1) / 255
    os.makedirs(os.path.dirname(cache), exist_ok=True); Image.fromarray((h * 65535).astype(np.uint16)).save(cache)
    return h

def area(x, w, h):
    return np.stack([np.asarray(Image.fromarray(x[..., c], 'F').resize((w, h), Image.BOX)) for c in range(x.shape[-1])], -1)

def up(x, w, h):
    return np.stack([np.asarray(Image.fromarray(x[..., c], 'F').resize((w, h), Image.BILINEAR)) for c in range(x.shape[-1])], -1)

TINT_AB = os.path.join(os.path.dirname(AT), 'Rebuild-Systems', 'docs', 'handoff', 'SYSTEMS_M6_TINT_AB.json')
_tint = None
def tint_ab():
    global _tint
    if _tint is None:
        _tint = json.load(open(TINT_AB, encoding='utf-8')) if os.path.exists(TINT_AB) else {'by_mask': {}, 'unparsed': []}
    return _tint

def protect_mask(M, size, f, mask_name=None):
    """texels E must leave as D. Systems 2026-10-13 (agents/systems 5fc3a0b6, SYSTEMS_M6_TINT_AB.json): Masks B is a colour tint ONLY in
    ENV_PhongMain_NS materials with Enable_CustomColorTint; there diffuse = albedo x mix(CustA, CustB, B). Protect where that tint
    T deviates from white (max channel |T - 1| > 0.1, worst case over every material sharing the mask) so E bakes no hue into a tinted
    texel; elsewhere B is a detail-normal mask (not protected). R (emissive) is always protected, with a feathered rim.
    The table is keyed by the mask's full object path (Systems b4560051; every tint-enabled material parses).
    1 = protected. M: the TEXSET Masks half (HxWx4) or None"""
    if M is None: return None
    b = M[..., 2].astype(np.float32) / 255; m = (M[..., 0].astype(np.float32) / 255 > 0.1).astype(np.float32)
    bm = tint_ab()['by_mask']; mats = None
    if mask_name: mats = bm.get(mask_name) or next((v for k, v in bm.items() if k.lower() == mask_name.lower()), None)
    if mats:
        dev = np.zeros_like(b)
        for x in mats:
            A = np.array(x['A'], np.float32); B = np.array(x['B'], np.float32)
            T = A[None, None, :] * (1 - b[..., None]) + B[None, None, :] * b[..., None]
            dev = np.maximum(dev, np.abs(T - 1).max(-1))
        m = np.maximum(m, (dev > 0.1).astype(np.float32))
    if M.shape[1::-1] != tuple(size): m = np.asarray(Image.fromarray(m.astype(np.float32), 'F').resize(tuple(size), Image.BILINEAR))
    m = (m > 0.5).astype(np.float32)
    return np.clip(P.gblur(m[..., None], 2 * f)[..., 0] * 3, 0, 1)        # feathered rim, about 2 original pixels

def e_colour(D, o, hgt, s, seed, prot=None):
    """E at strength s on the D colour (HxWx4 float); returns RGB float and the fine height used for relief"""
    Hh, W = D.shape[:2]; oh, ow = o.shape[:2]; f = W / ow
    hp = hgt - P.gblur(hgt[..., None], 2 * f)[..., 0]                      # fine relief
    cav = np.clip(P.gblur(hgt[..., None], 8 * f)[..., 0] - hgt, 0, None); cav /= np.percentile(cav, 99) + 1e-6
    edg = np.clip(hp, 0, None); edg /= np.percentile(edg, 99) + 1e-6
    cav = np.clip(cav, 0, 1); edg = np.clip(edg, 0, 1)
    rgb = D[..., :3]; Y = P.V4.luma(rgb).astype(np.float32)[..., None]
    grey = np.repeat(Y, 3, -1)
    rgb = rgb + s * 0.3 * cav[..., None] * (grey - rgb)                    # grime desaturates cavities ...
    rgb = rgb * (1 - s * GRIME * cav[..., None])                           # ... and darkens them
    rgb = rgb + s * WEAR * edg[..., None] * (np.maximum(grey, 160) - rgb)  # wear lightens raised edges toward bare grey
    hs = hp / (hp.std() + 1e-6)
    rgb = rgb + s * SHADE * np.clip(hs, -3, 3)[..., None] * (rgb / 255 + 0.15)   # relief shading: the height's own micro-structure
    rgb = rgb + s * GRAIN * periodic_grain(Hh, W, f, seed)[..., None]      # faint micro grain
    # soft lock: restore D's own colour at the original resolution (palette, layout, shapes); two back-projection steps
    for _ in range(2):
        corr = area(D[..., :3], ow, oh) - area(np.clip(rgb, 0, 255).astype(np.float32), ow, oh)
        rgb = rgb + up(corr.astype(np.float32), W, Hh)
    if prot is not None: rgb = rgb * (1 - prot[..., None]) + D[..., :3] * prot[..., None]
    return np.clip(rgb, 0, 255), hp

def relief(alpha, hp, comp, s, size):
    """add micro relief from the fine height to a TEXSET normal component (0 = NormX, 1 = NormY), at the target size"""
    if hp.shape[::-1] != tuple(size): hp = np.asarray(Image.fromarray(hp, 'F').resize(tuple(size), Image.BILINEAR))
    d = hp / (hp.std() + 1e-6); g = np.gradient(d)[1 - comp]                # x gradient for NormX, y for NormY
    return np.clip(alpha - s * MICRO * 127.5 * 0.25 * g, 0, 255)

def lab(x):
    """sRGB 8-bit (float) -> CIE Lab (D65)"""
    c = x / 255.0; c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    X = c @ np.array([[0.4124, 0.2126, 0.0193], [0.3576, 0.7152, 0.1192], [0.1805, 0.0722, 0.9505]], np.float32)
    X = X / np.array([0.9505, 1.0, 1.089], np.float32); t = np.where(X > 0.008856, np.cbrt(X), 7.787 * X + 16 / 116)
    return np.stack([116 * t[..., 1] - 16, 500 * (t[..., 0] - t[..., 1]), 200 * (t[..., 1] - t[..., 2])], -1)

def gates(D, E, o, masks=None):
    """E vs D at the ORIGINAL resolution (what the soft lock promises) and vs the original's own wrap (Experimental review)"""
    oh, ow = o.shape[:2]; a = area(D[..., :3], ow, oh); b = area(E.astype(np.float32), ow, oh)
    La, Lb = lab(a), lab(b); dE = np.linalg.norm(La - Lb, axis=-1)
    sob = lambda x: np.hypot(*np.gradient(P.V4.luma(x).astype(np.float32)))
    ea, eb = sob(a), sob(b); t = max(8.0, float(np.percentile(ea, 90)))
    q = lambda x: (np.clip(x, 0, 255) // 16).astype(np.int32).reshape(-1, 3) @ np.array([256, 16, 1])
    qa, qb = q(a), q(b); ca = set(qa.tolist())
    def seam(x):   # wrap step relative to the neighbouring interior step (1.0 = the wrap looks like any other column / row)
        w = np.abs(x[:, 0] - x[:, -1]).mean() + np.abs(x[0] - x[-1]).mean()
        i = np.abs(x[:, 1] - x[:, 0]).mean() + np.abs(x[1] - x[0]).mean() + np.abs(x[:, -1] - x[:, -2]).mean() + np.abs(x[-1] - x[-2]).mean()
        return float(2 * w / (i + 1e-6))
    g = OD([('dmean_L', round(float(Lb[..., 0].mean() - La[..., 0].mean()), 2)),                 # global bias, limit |x| <= 1
            ('mean_shift', round(float(np.abs(a.mean((0, 1)) - b.mean((0, 1))).max()), 2)),       # D gate: <= 3
            ('new_colours_pct', round(100 * float(np.mean([v not in ca for v in qb.tolist()])), 2)),  # pixels in colour bins D lacks; <= 3 %
            ('dE_p99', round(float(np.percentile(dE, 99)), 2)), ('dE_mean', round(float(dE.mean()), 2)),
            ('new_edges_pct', round(100 * float(((eb > t) & (ea < 0.5 * t)).mean()), 3)),          # spurious edges
            ('lost_edges_pct', round(100 * float(((ea > t) & (eb < 0.5 * t)).mean()), 3)),
            ('seam_orig', round(seam(o[..., :3].astype(np.float32)), 2)), ('seam_d', round(seam(D[..., :3]), 2)),
            ('seam_e', round(seam(E), 2))])
    if masks is not None:                                       # dE inside each TEXSET mask channel's region (semantics UNKNOWN)
        mk = area(masks[..., :3], ow, oh) / 255
        for c, nm in enumerate('RGB'):
            sel = mk[..., c] > 0.5
            g['dE_mask%s' % nm] = round(float(dE[sel].mean()), 2) if sel.any() else None
    g['pass'] = bool(abs(g['dmean_L']) <= 1 and g['mean_shift'] <= 3 and g['new_colours_pct'] <= 3 and g['dE_p99'] <= 3
                     and g['new_edges_pct'] <= 0.5 and g['seam_e'] <= max(g['seam_d'], g['seam_orig']) * 1.15 + 0.1)
    return g

def spots(o):
    g = P.V4.luma(o[..., :3]).astype(np.float32); g = np.abs(np.diff(g, axis=0))[:, :-1] + np.abs(np.diff(g, axis=1))[:-1, :]
    n = min(48, *g.shape); c = [(g[y:y + n, x:x + n].sum(), x, y) for y in range(0, max(1, g.shape[0] - n), 8)
                               for x in range(0, max(1, g.shape[1] - n), 8)]
    return n, max(c)[1:], min(c)[1:]

def ladder():
    us, R = units(); out = os.path.join(E_ROOT, 'ladder'); os.makedirs(out, exist_ok=True); S = 240; rep = OD()
    for r, d, m, md in us:
        p = os.path.join(out, '%05d.png' % r['i'])
        if os.path.exists(p): continue
        stop(); t0 = time.time()
        o = P.orig(r); D = load_d(d); f = D.shape[1] / o.shape[1]
        hgt = height(D[..., :3].astype(np.uint8), os.path.join(E_ROOT, 'height', '%05d.png' % r['i']))
        M = load_d(md) if md else None; pr = protect_mask(M, (D.shape[1], D.shape[0]), f)
        Es = OD((k, e_colour(D, o, hgt, s, r['i'], pr)[0]) for k, s in STRENGTH.items())
        rep[r['png']] = OD((k, gates(D, e, o, M)) for k, e in Es.items())
        n, busy, flat = spots(o); im = Image.new('RGB', (5 * (S + 6), 2 * S + 36), (16, 16, 20)); dr = ImageDraw.Draw(im)
        dr.text((3, 2), '%05d %s  orig | D | E1 | E2 | E3  (busiest, flattest)' % (r['i'], r['png'][-80:]), fill=(230, 230, 230))
        for row, (x, y) in enumerate((busy, flat)):
            yy = 18 + row * (S + 18)
            im.paste(Image.fromarray(np.ascontiguousarray(o[y:y + n, x:x + n, :3])).resize((S, S), Image.NEAREST), (0, yy))
            for c, img in enumerate([D[..., :3]] + list(Es.values()), 1):
                cr = np.ascontiguousarray(np.clip(np.round(img), 0, 255).astype(np.uint8)[int(f * y):int(f * (y + n)), int(f * x):int(f * (x + n))])
                im.paste(Image.fromarray(cr).resize((S, S), Image.LANCZOS), (c * (S + 6), yy))
        im.save(p); print('ladder', r['i'], '%.0fs' % (time.time() - t0), json.dumps(rep[r['png']]['E2']), flush=True)
        g = os.path.join(E_ROOT, 'gates.json'); old = json.load(open(g, encoding='utf-8')) if os.path.exists(g) else {}
        old.update(rep); json.dump(old, open(g, 'w', encoding='utf-8'), indent=1); rep.clear()
    print('ladder done', flush=True)

def pack(level='E2'):
    s = STRENGTH[level]; us, R = units(); root = os.path.join(E_ROOT, 'pack'); rows = []
    for r, d, m, md in us:
        stop(); o = P.orig(r); D = load_d(d)
        hgt = height(D[..., :3].astype(np.uint8), os.path.join(E_ROOT, 'height', '%05d.png' % r['i']))
        M0 = load_d(md) if md else None; pr = protect_mask(M0, (D.shape[1], D.shape[0]), D.shape[1] / o.shape[1])
        rgb, hp = e_colour(D, o, hgt, s, r['i'], pr); E = D.copy(); E[..., :3] = rgb
        if r['kind'] == 'texset_color': E[..., 3] = relief(D[..., 3], hp, 0, s, (D.shape[1], D.shape[0]))
        todo = [(r, d, E)]
        if m is not None and md is not None:
            M = load_d(md); M[..., 3] = relief(M[..., 3], hp, 1, s, (M.shape[1], M.shape[0])); todo.append((m, md, M))
        for rr, dd, img in todo:
            dst = P.encode(np.clip(np.round(img), 0, 255).astype(np.uint8), rr, root)
            tmp = os.path.join(P.OUT, '_enc', 'pack', '%03d.png' % rr['i'])
            if os.path.exists(tmp): os.remove(tmp)
            rows.append(OD([('key', dd['key']), ('object_path', dd['object_path']), ('dds', dd['dds']), ('format', dd['format']),
                            ('size', dd['size']), ('bytes', os.path.getsize(dst)), ('level', 'e_' + level.lower()),
                            ('d_level', dd['level'])]))
        print('pack', r['i'], level, flush=True)
    json.dump(OD([('version', 1), ('generator', 'scripts/wfc/hd_e_pilot.py pack %s' % level),
                  ('generated', time.strftime('%Y-%m-%d %H:%M')), ('note', 'E pilot (Rust); not for install'), ('rows', rows)]),
              open(os.path.join(root, 'hd_index.json'), 'w', encoding='utf-8'), indent=1)
    print(len(rows), 'rows', round(sum(x['bytes'] for x in rows) / 2 ** 20, 1), 'MB', flush=True)

if __name__ == '__main__':
    a = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if a == 'list':
        for r, d, m, md in units()[0]: print(r['i'], r['kind'], d['level'], d['size'], r['png'], '+ masks' if md else '')
    elif a == 'ladder': ladder()
    elif a == 'pack': pack(sys.argv[2] if len(sys.argv) > 2 else 'E2')
