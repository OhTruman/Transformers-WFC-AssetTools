"""M4b remake PILOT (Integration 2026-10-11): ~20 REMAKE textures across the failure classes, candidate remakes per the user's rule
of 2026-10-09 (near-identical to the original, with the detail its resolution could not hold; layout, patterns and palette kept;
nothing invented). Pilot only: nothing goes into the pack, the index or ExtractedAssets. Outputs in out/hd/remake_pilot.

Every variant ends in the same back-projection lock as M4 (its area-downsample reproduces the deblocked original) and is judged by
M4's gate (final psnr >= 40, mean shift <= 0.6, tone check) plus three faithfulness checks:
  invented    share of 64 px tiles whose new-octave power sits above the original's own falloff (hd_v4.spectral_excess > 0)
  new_colours share of HD pixels whose colour (5 bits / channel, +-1 step) does not occur in the original
  period      for a regular pattern (axis autocorrelation >= 0.5 in the original): the HD autocorrelation at twice the period
and the detail gain over Lanczos (hd_v4.detail_gain; >= 1.25 = reads as HD, the M4 PASS threshold). The chosen remake is the
variant with the highest gain among those that pass every check; none passing = the original stays (REMAKE stays open).

Variants (CPU only, from the M4 model outputs already on disk; no new GPU work):
  direct:<model>  one model's output locked alone (M4 fused models and fell back to Lanczos where they disagreed)
  edge            Lanczos 2x with edges pulled to the local min / max along the original's own structure (no halo, no new
                  values beyond the neighbourhood range, no model): crisper edges, no new texture
  pattern         regular patterns: the periodic part (median along the lattice found by autocorrelation) upscaled and edge-pulled,
                  the non-periodic rest by Lanczos: hole and dot shapes stay as authored
  height          normal maps: Frankot-Chellappa height, Lanczos 2x, edge-pulled, normals re-derived (relief from the original only)
  two-channel normals (blue not Z): processed as RG data, blue kept as authored, no XYZ renormalisation (the M4 flattening cause)

  python hd_remake.py pick | run | sheet
"""
import json, os, sys, time
from collections import OrderedDict as OD, Counter
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if '--v2' not in sys.argv: sys.argv.append('--v2')
import hd_full as F  # noqa: E402
import hd_v3 as V3  # noqa: E402
H, V4 = F.H, F.V4
OUT = os.path.join(H.HD, 'remake_pilot')
EYE = [2411, 2403, 2452, 3780, 2221, 165, 1742, 3432, 1118]
LOCK_ITERS = 20
INVENT_MAX, NEWCOL_MAX, PERIOD_MIN = 0.10, 0.01, 0.85

def verdicts(): return json.load(open(os.path.join(F.FULL, 'verdicts.json'), encoding='utf-8'))
def sel_by_k(): return {s['k']: s for s in json.load(open(H.SEL, encoding='utf-8'))}

def why_class(v):
    w = ' | '.join(v['why'])
    return ('eye' if 'eye:' in w else 'gate' if 'no faithful upscale' in w else 'small' if 'too small' in w else
            'lanczos' if 'Lanczos' in w else 'gain' if 'detail gain' in w else '?')

def pick():
    """the pilot set: the eye REMAKEs that show each defect, then the largest textures (>= 256 px) of each automatic class"""
    v = verdicts(); sel = sel_by_k(); recs = {r['k']: r for r in F.load_recs()}
    R = [int(k) for k, x in v.items() if x['verdict'] == 'REMAKE']
    rows = [(k, 'eye') for k in EYE]
    def take(cls_, test, n):
        c = sorted((k for k in R if why_class(v[str(k)]) == cls_ and min(sel[k]['size']) >= 256 and test(k) and k not in [r[0] for r in rows]),
                   key=lambda k: (-sel[k]['size'][0] * sel[k]['size'][1], k))
        rows.extend((k, cls_) for k in c[:n])
    g = lambda k: sel[k]['cls']; lod = lambda k: sel[k].get('lod_group')
    take('lanczos', lambda k: g(k) == 'colour' and lod(k) == 'TEXTUREGROUP_Character', 1)
    take('lanczos', lambda k: g(k) == 'colour' and lod(k) is None, 1)
    take('lanczos', lambda k: g(k) == 'data' and lod(k) is None, 1)
    take('lanczos', lambda k: g(k) == 'data' and lod(k) == 'TEXTUREGROUP_Character', 1)
    take('lanczos', lambda k: g(k) == 'normal', 1)
    take('gain', lambda k: g(k) == 'normal', 2)
    take('gain', lambda k: g(k) == 'colour', 1)
    take('gate', lambda k: g(k) == 'colour' and (recs.get(k, {}).get('final_psnr') or 99) < 40, 1)
    take('gate', lambda k: g(k) == 'colour' and (recs.get(k, {}).get('final_psnr') or 0) >= 40, 1)
    take('gate', lambda k: g(k) == 'data', 1)
    os.makedirs(OUT, exist_ok=True)
    json.dump([OD([('k', k), ('class', c), ('object_path', sel[k]['object_path']), ('size', sel[k]['size']), ('tex_cls', sel[k]['cls']),
                   ('why', v[str(k)]['why'])]) for k, c in rows], open(os.path.join(OUT, 'pick.json'), 'w', encoding='utf-8'), indent=1)
    print(len(rows), Counter(c for _, c in rows))

# ---- building blocks -------------------------------------------------------------------------------------------------------
def shift(a, dy, dx): return np.pad(a, ((1, 1), (1, 1)) + ((0, 0),) * (a.ndim - 2), mode='edge')[1 + dy:1 + dy + a.shape[0], 1 + dx:1 + dx + a.shape[1]]

def edge_pull(img, t=0.6):
    """move each value toward its 3x3 neighbourhood max (where above the local mean) or min (below), weighted by the structure
    strength of the image itself: steeper edges, nothing outside the local value range (no halos), flat areas untouched"""
    x = img.astype(np.float32)
    mx = x.copy(); mn = x.copy()                                              # running 3x3 max / min (no 9x stack in memory)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx: t_ = shift(x, dy, dx); np.maximum(mx, t_, out=mx); np.minimum(mn, t_, out=mn)
    lum = V4.luma(x) if x.ndim == 3 and x.shape[2] >= 3 else x
    S = np.hypot(*np.gradient(lum)); S = np.clip(V4.box_blur(S, 1) / (np.percentile(S, 95) + 1e-6), 0, 1)
    if x.ndim == 3: S = S[..., None]
    loc = np.stack([V4.box_blur(x[..., c], 1) for c in range(x.shape[2])], -1) if x.ndim == 3 else V4.box_blur(x, 1)
    goal = np.where(x >= loc, mx, mn)
    goal -= x; goal *= t * S.astype(np.float32); goal += x
    return np.clip(goal, 0, 255, out=goal)

def lanczos2(a):
    h, w = a.shape[:2]
    if a.ndim == 2: return np.asarray(Image.fromarray(a.astype(np.float32), 'F').resize((2 * w, 2 * h), Image.LANCZOS))
    return np.stack([lanczos2(a[..., c]) for c in range(a.shape[2])], -1)

def lockx(target, hd, renorm):
    o = target.astype(np.float64); x = hd.astype(np.float64)
    for _ in range(LOCK_ITERS):
        x = np.clip(x + H._up(o - V3.box_down(x, 2), x.shape[1], x.shape[0]), 0, 255)
    x = np.round(x).astype(np.uint8)
    if renorm:
        v = x[..., :3].astype(np.float64) / 255 * 2 - 1; v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
        x = np.dstack([np.clip(np.round((v + 1) / 2 * 255), 0, 255).astype(np.uint8), x[..., 3]])
    return x

def axis_period(lum, axis):
    """strongest period (2..64 px) of the luma along one axis and its normalised autocorrelation"""
    x = lum - lum.mean(axis=axis, keepdims=True)
    F_ = np.fft.rfft(x, axis=axis); ac = np.fft.irfft(np.abs(F_) ** 2, n=lum.shape[axis], axis=axis).mean(axis=1 - axis)
    ac = ac / max(ac[0], 1e-9); n = min(65, len(ac) // 4)
    if n <= 3: return None, 0.0
    best = max(range(2, n), key=lambda p: ac[p] if ac[p] >= ac[p - 1] and ac[p] >= ac[p + 1] else -9)
    return best, float(ac[best])

def autocorr_at(lum, axis, p):
    x = lum - lum.mean(axis=axis, keepdims=True)
    ac = np.fft.irfft(np.abs(np.fft.rfft(x, axis=axis)) ** 2, n=lum.shape[axis], axis=axis).mean(axis=1 - axis)
    return float(ac[p] / max(ac[0], 1e-9)) if p < len(ac) else 0.0

def periods(target):
    lum = V4.luma(target); out = {}
    for ax in (0, 1):
        p, c = axis_period(lum, ax)
        if p and c >= 0.5: out[ax] = (p, c)
    return out

def pattern_rebuild(target, per):
    """periodic part = median of the 7 lattice neighbours along each periodic axis; upscaled + edge-pulled; rest by Lanczos"""
    x = target.astype(np.float32); P = x.copy()
    for ax, (p, _) in per.items():
        P = np.median(np.stack([np.roll(P, i * p, axis=ax) for i in range(-3, 4)]), 0)
    R = x - P
    Phd = edge_pull(edge_pull(lanczos2(P), 0.7), 0.7)
    W = np.clip(1 - V4.box_blur(np.abs(V4.luma(R)), 2) / 12.0, 0, 1)        # where the pattern explains the original
    W = lanczos2(W)[..., None]
    base = edge_pull(lanczos2(x))
    return np.clip(W * (Phd + lanczos2(R)) + (1 - W) * base, 0, 255)

def height_variant(target):
    hgt = H.normals_to_height(target)
    hu = lanczos2(hgt) * 2.0                                                  # heights in original px -> HD px units
    lo, hi = hu.min(), hu.max(); sc = (hu - lo) / max(hi - lo, 1e-9) * 255
    hu = edge_pull(sc, 0.6) / 255 * (hi - lo) + lo
    v = H.height_to_normals(hu, 1.0)
    a = lanczos2(target[..., 3:4].astype(np.float64))
    return np.dstack([np.clip((v + 1) / 2 * 255, 0, 255), a])

def two_channel(s):
    raw = np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGBA'))
    return s['cls'] == 'normal' and float(raw[..., 2].mean()) < 16

def m4_attempt(s, target):
    """what M4 produced (the rejected result too, for gate failures): the shipped _hdpng, else the fuse recomputed"""
    recs = {r['k']: r for r in F.load_recs()}; r = recs.get(s['k'], {})
    if r.get('hd_png'): return np.asarray(Image.open(os.path.join(F.FULL, r['hd_png'])).convert('RGBA'))
    w, h = s['size']; lz = np.asarray(Image.fromarray(target, 'RGBA').resize((2 * w, 2 * h), Image.LANCZOS))
    locked = OD([('lanczos', V3.lock(target, lz, s, 2))])
    for c in F.candidates(s):
        raw = F.cand_img(s, c)
        if raw is None: continue
        hd, g = V3.evaluate(target, raw, s, 2)
        if g['faithful']: locked[c] = hd
    fused, _ = V4.fuse(target, locked, lz, s)
    return V3.lock(target, fused, s, 2)

# ---- metrics ---------------------------------------------------------------------------------------------------------------
def metrics(target, hd, s, per, disp_cls):
    p, sh, _ = H.gate(target, hd, s); tone = V4.tone_check(target, hd, s)
    gain = V4.detail_gain(target, hd, s)
    f = (lambda a: V4.luma(H._lit(a, disp_cls == 'normal2'))) if disp_cls in ('normal', 'normal2') else V4.luma
    L = f(hd); T = V4.TILE; ex = []
    for i in range(0, L.shape[0] - T + 1, T):
        for j in range(0, L.shape[1] - T + 1, T): ex.append(V4.spectral_excess(L[i:i + T, j:j + T]))
    invented = float(np.mean(np.array(ex) > 0)) if ex else 0.0
    q = lambda a: (a[..., :3].astype(np.int32) >> 3)
    pal = np.zeros((34, 34, 34), bool); qo = q(target) + 1
    for dz in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1): pal[qo[..., 0] + dz, qo[..., 1] + dy, qo[..., 2] + dx] = True
    qh = q(hd) + 1; newc = float((~pal[qh[..., 0], qh[..., 1], qh[..., 2]]).mean())
    per_ok = None
    if per:
        lh = V4.luma(hd); per_ok = round(min(autocorr_at(lh, ax, 2 * pp) / max(c, 1e-6) for ax, (pp, c) in per.items()), 3)
    ok = bool(p >= H.FINAL_MIN_DB and sh <= H.FINAL_MAX_SHIFT and tone['ok'] and invented <= INVENT_MAX and newc <= NEWCOL_MAX
              and (per_ok is None or per_ok >= PERIOD_MIN))
    return OD([('final_psnr', round(p, 2)), ('max_mean_shift', round(sh, 3)), ('tone_ok', tone['ok']), ('detail_gain', round(gain, 3)),
               ('invented_tiles', round(invented, 3)), ('new_colours', round(newc, 4)), ('period_kept', per_ok), ('faithful', ok)])

def run():
    pk = json.load(open(os.path.join(OUT, 'pick.json'), encoding='utf-8')); sel = sel_by_k(); res = []
    os.makedirs(os.path.join(OUT, 'png'), exist_ok=True); t0 = time.time()
    for row in pk:
        s = dict(sel[row['k']]); two = two_channel(s)
        if two:   # raw RG + authored blue as data: deblocked, no renormalisation
            raw = np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGBA'))
            target = np.clip(np.round(H.deblock(raw)), 0, 255).astype(np.uint8); s_eval = dict(s, cls='data')
        else:
            target = H.source(s); s_eval = s
        renorm = s['cls'] == 'normal' and not two; disp = 'normal2' if two else s['cls']
        per = periods(target)
        m4 = m4_attempt(s, H.source(s))
        M = OD(); blue = np.clip(np.round(lanczos2(target[..., 2])), 0, 255).astype(np.uint8) if two else None
        def keep(name, hd):
            if two: hd[..., 2] = blue                                       # authored blue, not a renormalised Z
            M[name] = metrics(target, hd, s_eval, per, disp)
            Image.fromarray(hd, 'RGBA').save(os.path.join(OUT, 'png', '%05d_%s.png' % (s['k'], name.replace(':', '-'))))
        for c in F.candidates(s):
            raw_ = V3.assemble(s, c, 2) if (two and c == V3.NORMAL) else F.cand_img(s, c)
            if raw_ is None: continue
            keep('direct:' + {F.RPLKSR: 'RPLKSR', F.DAT2: 'DAT2', V3.NORMAL: 'NormalRG0'}.get(c, 'animevideov3'), lockx(target, raw_, renorm)); del raw_
        w, h = s['size']
        lz = np.asarray(Image.fromarray(target, 'RGBA').resize((2 * w, 2 * h), Image.LANCZOS))
        keep('edge', lockx(target, edge_pull(lz), renorm)); del lz
        if per: keep('pattern', lockx(target, pattern_rebuild(target, per), renorm))
        if s['cls'] == 'normal' and not two: keep('height', lockx(target, height_variant(target), renorm))
        m4m = metrics(H.source(s), m4, s, per, s['cls'])
        Image.fromarray(m4, 'RGBA').save(os.path.join(OUT, 'png', '%05d_M4.png' % s['k'])); del m4
        ok = [n_ for n_ in M if M[n_]['faithful']]
        best = max(ok, key=lambda n_: M[n_]['detail_gain']) if ok else None
        verdict = ('REMAKE candidate' if best and M[best]['detail_gain'] >= V4.DETAIL_GAIN_MIN else
                   'faithful but still soft' if best else 'no faithful remake (original stays)')
        res.append(OD([('k', s['k']), ('class', row['class']), ('object_path', s['object_path']), ('size', s['size']), ('tex_cls', s['cls']),
                       ('two_channel_normal', two), ('periods', {('y' if a == 0 else 'x'): [pp, round(c, 2)] for a, (pp, c) in per.items()}),
                       ('m4_why', row['why']), ('m4_metrics', m4m), ('variants', M), ('chosen', best), ('verdict', verdict)]))
        print(s['k'], row['class'], verdict, best, best and M[best]['detail_gain'], '%.0fs' % (time.time() - t0), flush=True)
    json.dump(OD([('generated', time.strftime('%Y-%m-%d %H:%M')), ('rule', 'user 2026-10-09: near-identical, detail the resolution could '
                  'not hold, layout / patterns / palette kept, nothing invented'), ('checks', OD([('invented_tiles_max', INVENT_MAX),
                  ('new_colours_max', NEWCOL_MAX), ('period_kept_min', PERIOD_MIN), ('detail_gain_min', V4.DETAIL_GAIN_MIN),
                  ('gate', 'final psnr >= 40, mean shift <= 0.6, tone check (M4)')])), ('textures', res)]),
              open(os.path.join(OUT, 'remake_pilot.json'), 'w', encoding='utf-8'), indent=1)

INVENT_OVER_LANCZOS = 0.10
# eye review of the chosen variants (48 px close-ups at 6x: original nearest | M4 | remake), 2026-10-11. The automatic checks do
# not see model-specific redraws (hex mesh, speckle, crinkle relief): a model variant keeps its model's eye defect
EYE_REVIEW = {
    2411: ('reject', 'square holes still redrawn as a rounded / hex mesh (the M4 defect, model-born)'),
    2452: ('ok', 'dot columns keep their authored shape, crisper; M4 had turned them to noise'),
    3780: ('reject', 'DAT2 speckle in the dark flats, as in M4'),
    2221: ('reject', 'green / purple fringe pixels along the frame edge remain'),
    165: ('ok', 'invented line art gone; relief from the original only'),
    1742: ('reject', 'invented crinkle relief remains (normal model)'),
    3432: ('ok', 'RG relief back at the original contrast (M4 flattened it); blue as authored'),
    3363: ('soft', 'near-uniform grunge: nothing for a remake to add'),
    265: ('ok', 'lettering and rim intact, crisper than M4'),
    0: ('ok', 'mask shapes exact and crisp; M4 added stray strokes'),
    3314: ('ok', 'line art crisp, exact'),
    1566: ('reject', 'speckle in the flat areas, as in M4'),
    517: ('soft', 'faithful, but the pixel staircases on the diagonals stay (edge pull keeps the original geometry)'),
    633: ('ok', 'clean edges, no new relief'),
    2164: ('ok', 'subtle: soft clouds by nature, faithful'),
}

def eye():
    J = json.load(open(os.path.join(OUT, 'remake_pilot.json'), encoding='utf-8'))
    for r in J['textures']:
        e = EYE_REVIEW.get(r['k'])
        r['eye_review'] = OD([('verdict', e[0]), ('note', e[1])]) if e else None
        r['final'] = ('remake candidate' if e and e[0] == 'ok' else 'rejected by eye' if e and e[0] == 'reject' else
                      'faithful, not HD' if e and e[0] == 'soft' else r['verdict'])
    J['eye_review'] = '2026-10-11, close-ups of the chosen variant; reject = the defect is still visible'
    json.dump(J, open(os.path.join(OUT, 'remake_pilot.json'), 'w', encoding='utf-8'), indent=1)
    print(Counter(r['final'] for r in J['textures']))

def rescore():
    """re-judge the saved variants (no regeneration): 'invented' relative to a plain Lanczos 2x of the same original (normal maps and
    grainy art sit above the colour falloff by nature; only an excess over Lanczos is new), periodic patterns from 3 px up (a
    2 px period is DXT / pixel-doubling structure, not an authored pattern)"""
    J = json.load(open(os.path.join(OUT, 'remake_pilot.json'), encoding='utf-8')); sel = sel_by_k()
    for r in J['textures']:
        s = dict(sel[r['k']]); two = r['two_channel_normal']
        if two:
            raw = np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGBA'))
            target = np.clip(np.round(H.deblock(raw)), 0, 255).astype(np.uint8); s_eval = dict(s, cls='data')
        else: target = H.source(s); s_eval = s
        disp = 'normal2' if two else s['cls']
        per = {a: v for a, v in periods(target).items() if v[0] >= 3}
        w, h = s['size']
        lz = lockx(target, np.asarray(Image.fromarray(target, 'RGBA').resize((2 * w, 2 * h), Image.LANCZOS)), s['cls'] == 'normal' and not two)
        base = metrics(target, lz, s_eval, per, disp); r['lanczos_reference'] = base
        r['periods'] = {('y' if a == 0 else 'x'): [pp, round(c, 2)] for a, (pp, c) in per.items()}
        for n_ in list(r['variants']):
            if n_ == 'pattern' and not per: r['variants'].pop(n_); continue
            hd = np.asarray(Image.open(os.path.join(OUT, 'png', '%05d_%s.png' % (r['k'], n_.replace(':', '-')))).convert('RGBA'))
            m = metrics(target, hd, s_eval, per, disp)
            m['invented_over_lanczos'] = round(m['invented_tiles'] - base['invented_tiles'], 3)
            m['faithful'] = bool(m['final_psnr'] >= H.FINAL_MIN_DB and m['max_mean_shift'] <= H.FINAL_MAX_SHIFT and m['tone_ok']
                                 and m['invented_over_lanczos'] <= INVENT_OVER_LANCZOS and m['new_colours'] <= NEWCOL_MAX
                                 and (m['period_kept'] is None or m['period_kept'] >= PERIOD_MIN))
            r['variants'][n_] = m
        ok = [n_ for n_, m in r['variants'].items() if m['faithful']]
        r['chosen'] = max(ok, key=lambda n_: r['variants'][n_]['detail_gain']) if ok else None
        b = r['chosen']
        r['verdict'] = ('REMAKE candidate' if b and r['variants'][b]['detail_gain'] >= V4.DETAIL_GAIN_MIN else
                        'faithful but still soft' if b else 'no faithful remake (original stays)')
        print(r['k'], r['class'], r['verdict'], b, flush=True)
    J['checks']['invented'] = 'share of 64 px tiles above the falloff, minus that of a plain Lanczos 2x of the same original, <= %.2f' % INVENT_OVER_LANCZOS
    J['checks']['period'] = 'patterns from 3 px; HD autocorrelation at 2x the period / original >= %.2f' % PERIOD_MIN
    J['rescored'] = time.strftime('%Y-%m-%d %H:%M')
    json.dump(J, open(os.path.join(OUT, 'remake_pilot.json'), 'w', encoding='utf-8'), indent=1)

def sheet():
    """before | M4 attempt | remake at the most detailed 96 px spot; metrics under each row"""
    J = json.load(open(os.path.join(OUT, 'remake_pilot.json'), encoding='utf-8')); sel = sel_by_k()
    n, S = 96, 256; W = 3 * S + 40; rows = J['textures']; RH = S + 70
    im = Image.new('RGB', (2 * W + 20, ((len(rows) + 1) // 2) * RH + 40), (16, 16, 20)); d = ImageDraw.Draw(im)
    d.text((10, 8), 'M4b remake PILOT - original (nearest x2) | M4 attempt | remake candidate, same spot. Not in the pack.', fill=(235, 235, 235))
    for i, r in enumerate(rows):
        s = sel[r['k']]; two = r['two_channel_normal']
        o = np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGBA'))
        m4 = np.asarray(Image.open(os.path.join(OUT, 'png', '%05d_M4.png' % r['k'])).convert('RGBA'))
        ch = r['chosen']
        rm = np.asarray(Image.open(os.path.join(OUT, 'png', '%05d_%s.png' % (r['k'], ch.replace(':', '-')))).convert('RGBA')) if ch else None
        if s['cls'] == 'normal':
            show = lambda a: H._lit(a, two)
        else:
            show = lambda a: a[..., :3]
        O = show(o); gr = V4.luma(O); gr = np.abs(np.diff(gr, axis=0))[:, :-1] + np.abs(np.diff(gr, axis=1))[:-1, :]
        nn = min(n, *gr.shape)
        _, x, y = max(((gr[yy:yy + nn, xx:xx + nn].sum(), xx, yy) for yy in range(0, max(1, gr.shape[0] - nn), 16)
                       for xx in range(0, max(1, gr.shape[1] - nn), 16)))
        tiles = [Image.fromarray(np.ascontiguousarray(O[y:y + nn, x:x + nn])).resize((S, S), Image.NEAREST)]
        for a in (m4, rm):
            if a is None: tiles.append(None); continue
            tiles.append(Image.fromarray(np.ascontiguousarray(show(a)[2 * y:2 * y + 2 * nn, 2 * x:2 * x + 2 * nn])).resize((S, S), Image.LANCZOS))
        X = 10 + (i % 2) * (W + 10); Y = 30 + (i // 2) * RH
        for j, t in enumerate(tiles):
            if t is not None: im.paste(t, (X + j * (S + 10), Y + 30))
            else: d.text((X + j * (S + 10) + 60, Y + 30 + S // 2), 'original stays', fill=(200, 120, 120))
        vm = r['variants'].get(ch) if ch else None
        fin = r.get('final', r['verdict'])
        col = (120, 230, 140) if fin == 'remake candidate' else (230, 200, 120) if fin == 'faithful, not HD' else (255, 150, 120)
        d.text((X, Y + 2), '%05d %s %dx%d  [%s] -> %s' % (r['k'], r['object_path'].split('.')[-1][:30], *s['size'], r['class'], fin.upper()), fill=col)
        if r.get('eye_review'): d.text((X, Y + 30 + S + 4), 'eye: ' + r['eye_review']['note'][:110], fill=col)
        m4m = r['m4_metrics']
        d.text((X, Y + 16), 'M4: gain %.2f psnr %.1f inv %.2f | %s' % (m4m['detail_gain'], m4m['final_psnr'], m4m['invented_tiles'],
               ('%s: gain %.2f psnr %.1f inv %.2f newcol %.3f%s' % (ch, vm['detail_gain'], vm['final_psnr'], vm['invented_tiles'], vm['new_colours'],
                '' if vm['period_kept'] is None else ' period %.2f' % vm['period_kept'])) if vm else 'no variant passed'), fill=(180, 180, 180))
    out = os.path.join(OUT, 'remake_pilot_sheet.png'); im.save(out, optimize=True); print(out, len(rows))

if __name__ == '__main__':
    {'pick': pick, 'run': run, 'rescore': rescore, 'eye': eye, 'sheet': sheet}[sys.argv[1]]()
