"""HD pack v4 (user 2026-10-09: "squeeze every drop ... best looking HD ... nothing invented"): structure-aware best-of ensemble.

Every candidate (Real-ESRGAN v2 outputs, RealPLKSR, AoMR-mosr, the DAT transformers where run, the normal model for normals, and
plain Lanczos as the safe fallback) is first locked to the deblocked original (back-projection, as v2 / v3), then scored per
64 px tile:
  aligned   HD detail (HD minus Lanczos of the target) where the original has structure (smoothed gradient magnitude) -> real
            detail at edges / panel lines / wear
  flat      HD detail where the original is flat -> invented grain (penalised x FLAT_W)
  grid      excess edge energy on the 4 px block grid vs off-grid -> mosaic / block patterns (penalised x GRID_W)
Per-tile soft weights (softmax of the score, feathered across tiles: no seams) blend the candidates; the blend is locked again and
gated as before. GTAV-rgt is excluded (visible patchwork in v3).

  python hd_v4.py post      -> manifests/hd/hd_pilot_v4.json, out/hd/v4 (DXT) + out/hd/v4_bc7
  python hd_v4.py compare   -> out/hd/v4/compare (Original | v2 | v4)
"""
import json, os, sys
from collections import OrderedDict as OD, Counter
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hd_v3 as V3  # noqa: E402  (sets hd_pilot to v2 mode: deblocked source, original-format encode)
H = V3.H
AT = H.AT
H.OUTV = os.path.join(H.HD, 'v4')
V2W = os.path.join(H.HD, '_work_v2')
TILE, FLAT_W, GRID_W, TEMP = 64, 1.5, 3.0, 0.15
CANDS = ['v2:animevideov3_x2', 'v2:x4plus_down2', '4x-PBRify-RPLKSRd-V3', '2x-AoMR-mosr', '4x-PBRify-UpscalerDAT2-V1', '4x-TextureDAT2-otf']

def luma(a):
    return a[..., :3].astype(np.float64) @ np.array([0.299, 0.587, 0.114])

def candidate(s, c):
    if c == 'lanczos': return None
    if c.startswith('v2:'):
        save = H.WORK; H.WORK = V2W
        try: return H.rebuild(s, c[3:])
        except Exception: return None
        finally: H.WORK = save
    if c == V3.NORMAL: return V3.normal_rg0(s, 2)
    return V3.assemble(s, c, 2)

def box_blur(a, r):
    """(2r+1)^2 box blur of a 2-D float array with edge padding (summed-area table)"""
    p = np.pad(a.astype(np.float64), r + 1, mode='edge'); c = p.cumsum(0).cumsum(1); k = 2 * r + 1
    out = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return out[:a.shape[0], :a.shape[1]] / (k * k)

def tile_scores(target, hd, lz, s):
    """per-tile score (rows x cols) for one locked candidate"""
    t = luma(lz); d = np.abs(luma(H._lit(hd) if s['cls'] == 'normal' else hd) - (luma(H._lit(lz)) if s['cls'] == 'normal' else t))
    g = np.hypot(*np.gradient(luma(H._lit(lz)) if s['cls'] == 'normal' else t))
    S = box_blur(g, 3)
    S = S / (np.percentile(S, 95) + 1e-6); S = np.clip(S, 0, 1)
    h, w = d.shape; rows, cols = max(1, h // TILE), max(1, w // TILE)
    x = luma(hd); ex = np.abs(np.diff(x, axis=1)); ey = np.abs(np.diff(x, axis=0))
    gx = np.zeros_like(ex, bool); gx[:, 3::4] = True; gy = np.zeros_like(ey, bool); gy[3::4, :] = True
    out = np.zeros((rows, cols))
    for i in range(rows):
        for j in range(cols):
            sl = (slice(i * TILE, (i + 1) * TILE), slice(j * TILE, (j + 1) * TILE))
            dd, ss = d[sl], S[sl]
            aligned = float((dd * ss).mean()); flat = float((dd * (1 - ss)).mean())
            exs, gxs = ex[sl[0], sl[1]][:, :-1] if ex[sl[0], sl[1]].shape[1] > 1 else ex[sl[0], sl[1]], gx[sl[0], sl[1]][:, :-1] if gx[sl[0], sl[1]].shape[1] > 1 else gx[sl[0], sl[1]]
            on, off = (exs[gxs].mean() if gxs.any() else 0.0), (exs[~gxs].mean() if (~gxs).any() else 0.0)
            grid = max(0.0, float(on - off))
            out[i, j] = aligned - FLAT_W * flat - GRID_W * grid
    return out

def fuse(target, locked, lz, s):
    names = list(locked); h, w = lz.shape[:2]
    sc = np.stack([tile_scores(target, locked[n], lz, s) for n in names])          # K x rows x cols
    wts = np.exp((sc - sc.max(0, keepdims=True)) / (TEMP * (np.abs(sc).mean() + 1e-6)))
    wts /= wts.sum(0, keepdims=True)
    acc = np.zeros(lz.shape, np.float64)
    for k, n in enumerate(names):
        wm = np.asarray(Image.fromarray(wts[k].astype(np.float32), 'F').resize((w, h), Image.BILINEAR))[..., None]   # feathered
        acc += wm * locked[n].astype(np.float64)
    share = OD((n, round(float(wts[k].mean()), 3)) for k, n in enumerate(names))
    return np.clip(np.round(acc), 0, 255).astype(np.uint8), share

def post():
    sel = json.load(open(H.SEL, encoding='utf-8')); res = []
    for s in sel:
        target = H.source(s); w, h = s['size']
        lz = np.asarray(Image.fromarray(target, 'RGBA').resize((2 * w, 2 * h), Image.LANCZOS))
        locked = OD([('lanczos', V3.lock(target, lz, s, 2))])
        names = CANDS + ([V3.NORMAL] if s['cls'] == 'normal' else [])
        for c in names:
            raw = candidate(s, c)
            if raw is None: continue
            hd, g = V3.evaluate(target, raw, s, 2)
            if g['faithful']: locked[c] = hd
        fused, share = fuse(target, locked, lz, s)
        hd = V3.lock(target, fused, s, 2); p, sh, _ = H.gate(target, hd, s)
        ok = bool(p >= H.FINAL_MIN_DB and sh <= H.FINAL_MAX_SHIFT)
        rec = OD([('object_path', s['object_path']), ('cls', s['cls']), ('lod_group', s['lod_group']), ('size', s['size']), ('format', s['format']),
                  ('candidates_faithful', list(locked)), ('blend_share', share), ('final_psnr', round(p, 2)), ('max_mean_shift', round(sh, 3)), ('faithful', ok)])
        if ok:
            png = os.path.join(H.OUTV, '_png', '%03d.png' % s['k']); os.makedirs(os.path.dirname(png), exist_ok=True)
            Image.fromarray(hd, 'RGBA').save(png); rec['hd_png'] = os.path.relpath(png, H.OUTV).replace(os.sep, '/')
            d = H.encode(hd, s, s['dds'], modern=False); rec['hd_dds'] = os.path.relpath(d, H.OUTV).replace(os.sep, '/') if d else None
            rec['hd_bytes'] = os.path.getsize(d) if d else None
            d7 = H.encode(hd, s, s['dds'], modern=True); rec['hd_dds_bc7'] = os.path.relpath(d7, H.OUTV + '_bc7').replace(os.sep, '/') if d7 else None
            rec['hd_bytes_bc7'] = os.path.getsize(d7) if d7 else None
        rec['orig_bytes'] = os.path.getsize(os.path.join(H.DDS, s['dds']))
        res.append(rec)
        print(s['object_path'].split('.')[-1][:34], s['cls'], 'faithful' if ok else 'REJECT', dict(sorted(share.items(), key=lambda x: -x[1])[:3]), flush=True)
    out = OD([('generated_by', 'AssetTools/scripts/wfc/hd_v4.py'), ('scoring', OD([('tile', TILE), ('flat_weight', FLAT_W), ('grid_weight', GRID_W), ('temperature', TEMP)])),
              ('candidates', CANDS + [V3.NORMAL, 'lanczos']), ('accepted', sum(1 for r in res if r['faithful'])), ('textures', res)])
    json.dump(out, open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v4.json'), 'w', encoding='utf-8'), indent=1)
    tot = Counter(); [tot.update({k: v}) for r in res for k, v in r['blend_share'].items()]
    print('accepted', out['accepted'], '/', len(res), '| mean blend share', {k: round(v / len(res), 3) for k, v in tot.most_common()})

def compare():
    man = json.load(open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v4.json'), encoding='utf-8'))
    v2 = {r['object_path']: r for r in json.load(open(V3.V2MAN, encoding='utf-8'))['textures']}
    sel = {s['object_path']: s for s in json.load(open(H.SEL, encoding='utf-8'))}
    od = os.path.join(H.OUTV, 'compare'); os.makedirs(od, exist_ok=True)
    for r in man['textures']:
        name = r['object_path'].split('.')[-1]
        if name not in H.COMPARE or not r.get('hd_dds'): continue
        s = sel[r['object_path']]; nrm = s['cls'] == 'normal'
        orig = np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGB'))
        v2p = v2[r['object_path']].get('hd_dds')
        a2 = np.asarray(Image.open(os.path.join(H.HD, 'v2', v2p)).convert('RGB')) if v2p else None
        a4 = np.asarray(Image.open(os.path.join(H.OUTV, r['hd_dds'])).convert('RGB'))
        a7 = np.asarray(Image.open(os.path.join(H.OUTV + '_bc7', r['hd_dds_bc7'])).convert('RGB')) if r.get('hd_dds_bc7') else None
        if nrm: orig, a4 = H._lit(orig), H._lit(a4); a2 = H._lit(a2) if a2 is not None else None; a7 = H._lit(a7, bc5=True) if a7 is not None else None
        g = orig.astype(np.float64).mean(-1); g = np.abs(np.diff(g, axis=0))[:, :-1] + np.abs(np.diff(g, axis=1))[:-1, :]
        n = 96; hh, ww = g.shape
        _, x, y = max(((g[yy:yy + n, xx:xx + n].sum(), xx, yy) for yy in range(0, max(1, hh - n), 16) for xx in range(0, max(1, ww - n), 16)))
        cols = [('Original %dx%d' % tuple(s['size']), orig, 1)] + ([('v2 (shown before)', a2, 2)] if a2 is not None else []) + \
               [('v4 ensemble, original formats', a4, 2)] + ([('v4 ensemble, %s' % ('BC5' if nrm else 'BC7'), a7, 2)] if a7 is not None else [])
        S = 512; im = Image.new('RGB', (len(cols) * (S + 10) + 10, S + 74), (16, 16, 20)); d = ImageDraw.Draw(im)
        d.text((10, 8), '%s (%s)%s - same zoomed region; every HD version shrinks back to the original' % (name, s['lod_group'] or 'environment',
               ', normal map shown lit' if nrm else ''), fill=(170, 170, 170))
        for i, (lab, arr, f) in enumerate(cols):
            c = Image.fromarray(np.ascontiguousarray(arr[f * y:f * (y + n), f * x:f * (x + n)])).resize((S, S), Image.BILINEAR)
            im.paste(c, (10 + i * (S + 10), 56)); d.text((10 + i * (S + 10), 34), lab, fill=(255, 210, 120) if i else (235, 235, 235))
        p = os.path.join(od, '%02d_%s.png' % (H.COMPARE.index(name) + 1, name)); im.save(p, optimize=True); print(os.path.relpath(p, AT))

MIN_SIDE_HD, LANCZOS_SHARE_MAX, DETAIL_GAIN_MIN = 64, 0.6, 1.25

def detail_gain(target, hd, s):
    """structure-aligned detail of the HD texture relative to a plain Lanczos 2x of the same target (1.0 = nothing added)"""
    w, h = s['size']
    lz = np.asarray(Image.fromarray(target, 'RGBA').resize((2 * w, 2 * h), Image.LANCZOS))
    f = (lambda a: luma(H._lit(a))) if s['cls'] == 'normal' else luma
    g = np.hypot(*np.gradient(f(lz))); S = np.clip(box_blur(g, 3) / (np.percentile(box_blur(g, 3), 95) + 1e-6), 0, 1)
    hp = lambda a: np.abs(f(a) - box_blur(f(a), 1))
    return float((hp(hd) * S).mean() / max((hp(lz) * S).mean(), 1e-9))

def verdict():
    """PASS (faithful and reads as HD: keep) / REMAKE (still pixelated / soft: listed for the remake pass after the full pack;
    user 2026-10-09). Automatic rules (reviewed by eye on the thumbnails before reporting):
      REMAKE if the gate rejected it, the original's short side < MIN_SIDE_HD, the blend fell back mostly to Lanczos (no model
      found faithful detail to add), or the structure-aligned detail gain over Lanczos < DETAIL_GAIN_MIN"""
    import authored as A
    con = A.con()
    man = json.load(open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v4.json'), encoding='utf-8'))
    sel = {s['object_path']: s for s in json.load(open(H.SEL, encoding='utf-8'))}
    rp = os.path.join(AT, 'manifests', 'hd', 'remake_candidates.json')
    remake = OD((r['object_path'], r) for r in (json.load(open(rp, encoding='utf-8')).get('textures', []) if os.path.exists(rp) else []))
    td = os.path.join(H.HD, 'remake_thumbs'); os.makedirs(td, exist_ok=True); counts = Counter()
    for r in man['textures']:
        s = sel[r['object_path']]; target = H.source(s); why = []
        if not r['faithful'] or not r.get('hd_png'): why.append('no faithful upscale (gate)')
        else:
            hd = np.asarray(Image.open(os.path.join(H.OUTV, r['hd_png'])).convert('RGBA'))
            gain = detail_gain(target, hd, s); r['detail_gain'] = round(gain, 3)
            if min(s['size']) < MIN_SIDE_HD: why.append('original too small (%dx%d)' % tuple(s['size']))
            if r['blend_share'].get('lanczos', 0) > LANCZOS_SHARE_MAX: why.append('blend mostly Lanczos (%.0f%%): models found little faithful detail' % (100 * r['blend_share']['lanczos']))
            if gain < DETAIL_GAIN_MIN: why.append('detail gain %.2f < %.2f: reads soft / not HD' % (gain, DETAIL_GAIN_MIN))
        r['verdict'] = 'REMAKE' if why else 'PASS'; counts[(r['cls'], r['verdict'])] += 1
        if why:
            uses = con.execute("SELECT COUNT(DISTINCT src) FROM refs WHERE dst = ?", (r['object_path'],)).fetchone()[0]
            th = os.path.join(td, r['object_path'].replace('.', '_') + '.png')
            o = Image.fromarray(target[..., :3]).resize((256, 256), Image.BILINEAR)
            sheet = Image.new('RGB', (522, 286), (16, 16, 20)); sheet.paste(o, (5, 25))
            if r.get('hd_png'): sheet.paste(Image.open(os.path.join(H.OUTV, r['hd_png'])).convert('RGB').resize((256, 256), Image.BILINEAR), (266, 25))
            ImageDraw.Draw(sheet).text((5, 5), 'original | best faithful HD', fill=(230, 230, 230)); sheet.save(th)
            remake[r['object_path']] = OD([('object_path', r['object_path']), ('class', r['cls']), ('lod_group', r['lod_group']), ('size', s['size']),
                                           ('referencing_objects', uses), ('why', why), ('thumbnail', os.path.relpath(th, AT).replace(os.sep, '/')),
                                           ('source', 'hd_v4 pilot')])
        else:
            remake.pop(r['object_path'], None)
    json.dump(man, open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v4.json'), 'w', encoding='utf-8'), indent=1)
    json.dump(OD([('generated_by', 'AssetTools/scripts/wfc/hd_v4.py verdict'),
                  ('rule', 'user 2026-10-09: PASS = faithful and reads as HD (kept); REMAKE = still pixelated / soft -> remake pass after the full pack'),
                  ('thresholds', OD([('min_side', MIN_SIDE_HD), ('lanczos_share_max', LANCZOS_SHARE_MAX), ('detail_gain_min', DETAIL_GAIN_MIN)])),
                  ('textures', list(remake.values()))]), open(rp, 'w', encoding='utf-8'), indent=1)
    print({'%s %s' % k: v for k, v in sorted(counts.items())}, '| remake list', len(remake))

if __name__ == '__main__':
    {'post': post, 'compare': compare, 'verdict': verdict}[sys.argv[1]]()
