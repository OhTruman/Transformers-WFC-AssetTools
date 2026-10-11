"""M4 errata (Integration 2026-10-11): M4's gate, tone check and Lanczos references resized RGBA with PIL, which premultiplies
alpha; every texture with a non-opaque alpha was measured wrong (hd_pilot.resize_straight now resizes per channel). No new
upscaling: the M4 result is recomputed from the M4 model outputs on disk exactly as hd_full.post_one does (with the straight
Lanczos), and only measured. Nothing is written to the pack or hd_index.json (3f410a1 ships with M3); outputs in out/hd/errata.

  python hd_errata.py regate [--shard i/N]  the 212 M4 gate failures: recomputed result -> gate / tone / gain / automatic rules
  python hd_errata.py passgain [--shard i/N] alpha textures that PASS: detail gain re-measured on the shipped HD (straight
                                            reference); < 1.25 -> listed for an eye recheck
  python hd_errata.py report                errata.json (PASS / REMAKE deltas) + close-up sheets for the eye review
"""
import glob, json, os, sys, time
from collections import OrderedDict as OD, Counter
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if '--v2' not in sys.argv: sys.argv.append('--v2')
import hd_full as F  # noqa: E402
import hd_v3 as V3  # noqa: E402
H, V4 = F.H, F.V4
OUT = os.path.join(H.HD, 'errata')

def shard():
    return tuple(int(x) for x in sys.argv[sys.argv.index('--shard') + 1].split('/')) if '--shard' in sys.argv else (0, 1)

def base():
    v = json.load(open(os.path.join(F.FULL, 'verdicts.json'), encoding='utf-8'))
    sel = {s['k']: s for s in json.load(open(H.SEL, encoding='utf-8'))}
    return v, sel, {r['k']: r for r in F.load_recs()}

def non_opaque(s):
    return float((np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGBA'))[..., 3] < 255).mean())

def recompute(s):
    """hd_full.post_one without writing anything (the straight Lanczos is the only change)"""
    target = H.source(s); w, h = s['size']
    lz = H.resize_straight(target, (2 * w, 2 * h), Image.LANCZOS)
    locked = OD([('lanczos', V3.lock(target, lz, s, 2))])
    for c in F.candidates(s):
        raw = F.cand_img(s, c)
        if raw is None: continue
        hd, g = V3.evaluate(target, raw, s, 2)
        if g['faithful']: locked[c] = hd
    fused, share = V4.fuse(target, locked, lz, s)
    hd = V3.lock(target, fused, s, 2)
    const = [c for c in range(4) if target[..., c].min() == target[..., c].max()]
    if const: hd = hd.copy(); hd[..., const] = target[0, 0, const]
    return target, hd, share

def auto_rules(s, share, gain):
    why = []
    if min(s['size']) < V4.MIN_SIDE_HD: why.append('original too small (%dx%d)' % tuple(s['size']))
    if share.get('lanczos', 0) > V4.LANCZOS_SHARE_MAX: why.append('blend mostly Lanczos (%.0f%%)' % (100 * share['lanczos']))
    if gain < V4.DETAIL_GAIN_MIN: why.append('detail gain %.2f < %.2f' % (gain, V4.DETAIL_GAIN_MIN))
    return why

def regate():
    v, sel, recs = base(); i, n = shard(); os.makedirs(os.path.join(OUT, 'png'), exist_ok=True)
    out = os.path.join(OUT, '_regate_s%d.jsonl' % i)
    done = {json.loads(l)['k'] for l in open(out, encoding='utf-8')} if os.path.exists(out) else set()
    ks = sorted(int(k) for k, x in v.items() if x['verdict'] == 'REMAKE' and any('no faithful upscale' in w for w in x['why']))
    t0 = time.time()
    for k in ks:
        if k % n != i or k in done: continue
        s = sel[k]
        try:
            target, hd, share = recompute(s)
            p, sh, _ = H.gate(target, hd, s); tone = V4.tone_check(target, hd, s); gain = V4.detail_gain(target, hd, s)
            ok = bool(p >= H.FINAL_MIN_DB and sh <= H.FINAL_MAX_SHIFT and tone['ok'])
            why = ([] if ok else ['gate (straight): psnr %.2f shift %.3f tone %s' % (p, sh, tone['ok'])]) + (auto_rules(s, share, gain) if ok else [])
            png = os.path.join(OUT, 'png', '%05d.png' % k); Image.fromarray(hd, 'RGBA').save(png)
            rec = OD([('k', k), ('object_path', s['object_path']), ('cls', s['cls']), ('size', s['size']), ('non_opaque', round(non_opaque(s), 4)),
                      ('m4', OD([('final_psnr', recs.get(k, {}).get('final_psnr')), ('max_mean_shift', recs.get(k, {}).get('max_mean_shift')),
                                 ('tone_ok', (recs.get(k, {}).get('tone') or {}).get('ok'))])),
                      ('final_psnr', round(p, 2)), ('max_mean_shift', round(sh, 3)), ('tone', tone), ('blend_share', share),
                      ('detail_gain', round(gain, 4)), ('faithful', ok), ('auto_why', why),
                      ('candidate', 'PASS (needs eye review)' if ok and not why else 'REMAKE'), ('png', os.path.relpath(png, OUT).replace(os.sep, '/'))])
        except Exception as ex:
            rec = OD([('k', k), ('object_path', s['object_path']), ('error', '%s: %s' % (type(ex).__name__, str(ex)[:200]))])
        with open(out, 'a', encoding='utf-8') as f: f.write(json.dumps(rec) + '\n')
        print(k, rec.get('candidate', rec.get('error')), '%.0fs' % (time.time() - t0), flush=True)

def passgain():
    v, sel, recs = base(); i, n = shard(); os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, '_passgain_s%d.jsonl' % i)
    done = {json.loads(l)['k'] for l in open(out, encoding='utf-8')} if os.path.exists(out) else set()
    gains = {}
    for gp in glob.glob(os.path.join(F.FULL, '_gain_s*.json')): gains.update(json.load(open(gp, encoding='utf-8')))
    idx = {r['object_path'] for r in json.load(open(os.path.join(F.PACK, 'hd_index.json'), encoding='utf-8'))['rows']}
    t0 = time.time()
    for k in sorted(int(k) for k, x in v.items() if x['verdict'] == 'PASS'):
        if k % n != i or k in done: continue
        s, r = sel[k], recs[k]
        no = non_opaque(s)
        if no <= 0.01: continue
        target = H.source(s); hd = np.asarray(Image.open(os.path.join(F.FULL, r['hd_png'])).convert('RGBA'))
        g = V4.detail_gain(target, hd, s)
        rec = OD([('k', k), ('object_path', s['object_path']), ('cls', s['cls']), ('non_opaque', round(no, 4)), ('in_index', s['object_path'] in idx),
                  ('gain_m4', gains.get('%d@%s' % (k, r.get('t', 0)))), ('gain_straight', round(g, 4)),
                  ('recheck', bool(g < V4.DETAIL_GAIN_MIN))])
        with open(out, 'a', encoding='utf-8') as f: f.write(json.dumps(rec) + '\n')
        print(k, rec['gain_m4'], '->', rec['gain_straight'], 'RECHECK' if rec['recheck'] else '', '%.0fs' % (time.time() - t0), flush=True)

def load(pat):
    rows = {}
    for p in sorted(glob.glob(os.path.join(OUT, pat))):
        for l in open(p, encoding='utf-8'): r = json.loads(l); rows[r['k']] = r
    return rows

def closeups(ks, name, sel, hd_path):
    """48 px spots at 6x: original nearest | HD (errata) for the eye review"""
    n, S = 48, 288; per = 8
    for part in range(0, len(ks), per):
        grp = ks[part:part + per]; im = Image.new('RGB', (2 * S + 20, len(grp) * (S + 24)), (16, 16, 20)); d = ImageDraw.Draw(im)
        for j, k in enumerate(grp):
            s = sel[k]; show = (lambda a: H._lit(a)) if s['cls'] == 'normal' else (lambda a: a[..., :3])
            o = show(np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGBA')))
            hd = show(np.asarray(Image.open(hd_path(k)).convert('RGBA')))
            gr = V4.luma(o); gr = np.abs(np.diff(gr, axis=0))[:, :-1] + np.abs(np.diff(gr, axis=1))[:-1, :]
            nn = min(n, *gr.shape)
            _, x, y = max(((gr[yy:yy + nn, xx:xx + nn].sum(), xx, yy) for yy in range(0, max(1, gr.shape[0] - nn), 8)
                           for xx in range(0, max(1, gr.shape[1] - nn), 8)))
            Y = j * (S + 24); d.text((4, Y + 4), '%05d %s %dx%d' % (k, s['object_path'].split('.')[-1][:50], *s['size']), fill=(230, 230, 230))
            im.paste(Image.fromarray(np.ascontiguousarray(o[y:y + nn, x:x + nn])).resize((S, S), Image.NEAREST), (0, Y + 20))
            im.paste(Image.fromarray(np.ascontiguousarray(hd[2 * y:2 * y + 2 * nn, 2 * x:2 * x + 2 * nn])).resize((S, S), Image.NEAREST), (S + 20, Y + 20))
        im.save(os.path.join(OUT, '%s_%02d.png' % (name, part // per + 1)))

def report():
    v, sel, recs = base(); rg = load('_regate_s*.jsonl'); pg = load('_passgain_s*.jsonl')
    errs = [r for r in rg.values() if 'error' in r]
    moved = sorted(k for k, r in rg.items() if r.get('candidate', '').startswith('PASS'))
    still = Counter(('opaque' if r.get('non_opaque', 0) <= 0.01 else 'alpha') + ': ' + ('gate' if not r['faithful'] else 'auto rules')
                    for r in rg.values() if 'error' not in r and not r['candidate'].startswith('PASS'))
    recheck = sorted(k for k, r in pg.items() if r['recheck'])
    closeups(moved, 'eye_regate', sel, lambda k: os.path.join(OUT, rg[k]['png']))
    closeups(recheck, 'eye_passgain', sel, lambda k: os.path.join(F.FULL, recs[k]['hd_png']))
    J = OD([('generated', time.strftime('%Y-%m-%d %H:%M')), ('cause', 'PIL premultiplied-alpha RGBA resize in hd_pilot.gate, hd_v4.tone_check, '
            'hd_v4.detail_gain / fuse Lanczos reference; fixed by hd_pilot.resize_straight'),
            ('shipped_pixels', 'unaffected: the lock is numpy, straight alpha; 3f410a1 DDS are correct'),
            ('regate', OD([('textures', len(rg)), ('errors', [r['k'] for r in errs]), ('remake_to_pass_candidates', len(moved)),
                           ('still_remake', dict(still)), ('eye_review_sheets', 'out/hd/errata/eye_regate_*.png'), ('rows', list(rg.values()))])),
            ('passgain', OD([('alpha_pass_textures', len(pg)), ('below_threshold_recheck', len(recheck)),
                             ('eye_review_sheets', 'out/hd/errata/eye_passgain_*.png'), ('rows', list(pg.values()))]))])
    json.dump(J, open(os.path.join(OUT, 'errata.json'), 'w', encoding='utf-8'), indent=1)
    print('regate', len(rg), 'errors', len(errs), '-> PASS candidates', len(moved), dict(still), '| passgain', len(pg), 'recheck', len(recheck))

if __name__ == '__main__':
    {'regate': regate, 'passgain': passgain, 'report': report}[sys.argv[1]]()
