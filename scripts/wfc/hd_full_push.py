"""HD full pass build (docs/HD_FULL_PASS_PLAN.md; user decision 2026-10-12 via Integration: D, "D all the way").
Per texture the ladder D -> C -> B -> A -> original (hd_push.variants): the strongest level that passes the drift gate and
broken_blocks = 0 is encoded into out/hd/push_full/pack. A TEXSET Color / Masks pair is one unit and takes one level. Eye review
caps a texture's level or rejects it (hd_full_eye.py, never hand edits); the pack index lists only eye-reviewed batches.

  python hd_full_push.py status                    built / ready / total per batch of 100 units
  python hd_full_push.py build [B-B2] [i/n]        build the ready units (resumable; exits 75 on a PERF_HOLD file)
  python hd_full_push.py sheets B                  eye-review sheets of batch B (8 textures per sheet)
  python hd_full_push.py pack                      pack/hd_index.json from the reviewed batches
"""
import glob, json, os, sys, time
from collections import OrderedDict as OD, Counter
os.environ['WFC_HD_PUSH_SET'] = 'full'
os.environ.setdefault('WFC_HD_TORCH_BLUR', '1')
import numpy as np
import torch
torch.set_num_threads(int(os.environ.get('WFC_HD_BUILD_THREADS', '4')))
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hd_push as P  # noqa: E402
import hd_full_eye as E  # noqa: E402
H, V4 = P.H, P.V4
P.BB_NORMAL_NOISE = False   # 2026-10-12 calibration on 30 normal outputs: the > 6x flags were grain / small-texture upscales, none garbage
OUT = P.OUT; PACK = os.path.join(OUT, 'pack'); RES = os.path.join(OUT, 'results'); TILE = os.path.join(OUT, 'review')
SHEETS = os.path.join(OUT, 'sheets')
LEVELS = P.VARIANTS                    # gen4x (A), gen4x_mid (B), gen4x_mid_nrm (C), gen4x_d (D)
BATCH = 100                            # units per batch (eye review and progress lines go per batch)
S, SPOT = 288, 48                      # review tile: 48 px original spot at 6x

def units(R):
    """TEXSET pairs as one unit (the Color unit carries its Masks partner), everything else alone; selection order"""
    out, seen = [], set()
    for r in R:
        if r['i'] in seen: continue
        p = P.partner(r, R)
        u = [r] if p is None else ([r, p] if r['kind'] == 'texset_color' else [p, r])
        out.append(u); seen.update(x['i'] for x in u)
    return out

def need(r, R):
    """model outputs a texture's build reads"""
    k = r['kind']; n = []
    if k in ('colour', 'texset_color', 'texset_masks', 'data'): n.append(P.raw_path(r, 'rgb'))
    if k in ('colour', 'data') and r['format'] == 'PF_DXT5': n.append(P.raw_path(r, 'alpha'))
    if k == 'normal':
        n.append(P.raw_path(r, 'nrm')); ls = P.lumsrc(r, R)
        if ls: n.append(P.raw_path(ls, 'rgb'))
    if k in ('texset_color', 'texset_masks'):
        c = r if k == 'texset_color' else P.partner(r, R)
        if c: n += [P.raw_path(c, 'texnrm'), P.raw_path(c, 'rgb')]
    return n

def ready(u, R): return all(os.path.exists(p) for r in u for p in need(r, R))
def cap(r):
    c = E.EYE.get(r['png'], 'gen4x_d')
    return None if c is None else LEVELS.index(c)
def res_path(r): return os.path.join(RES, '%05d.json' % r['i'])
def done(r):
    p = res_path(r)
    if not os.path.exists(p): return False
    return json.load(open(p, encoding='utf-8')).get('cap') == E.EYE.get(r['png'], 'gen4x_d')

def show(a, k, alpha=False):
    """what the eye checks: lit shading for normals, the alpha (TEXSET normal half / DXT5 alpha) as grey, else RGB"""
    if alpha: return np.dstack([a[..., 3]] * 3)
    return H._lit(a, True) if k == 'normal' else np.ascontiguousarray(a[..., :3])

def has_alpha(r): return r['kind'] in ('texset_color', 'texset_masks') or r['format'] == 'PF_DXT5'

def tile(r, o, hd, f, lvl, gates):
    """one review row: original spot (nearest) | HD spot | alpha original | alpha HD | full HD thumbnail"""
    k = r['kind']; O = show(o, k); g = V4.luma(O).astype(np.float32)
    g = np.abs(np.diff(g, axis=0))[:, :-1] + np.abs(np.diff(g, axis=1))[:-1, :]; n = min(SPOT, *g.shape)
    _, x, y = max(((g[yy:yy + n, xx:xx + n].sum(), xx, yy) for yy in range(0, max(1, g.shape[0] - n), 8)
                   for xx in range(0, max(1, g.shape[1] - n), 8)))
    im = Image.new('RGB', (5 * (S + 8), S + 20), (16, 16, 20)); d = ImageDraw.Draw(im)
    gt = gates[lvl] if lvl else None
    d.text((4, 3), '%05d %s  [%s]  level %s%s' % (r['i'], r['png'][:90], k, lvl or 'ORIGINAL',
                                                  '' if gt is None else '  ssim %.3f shift %.2f lc %.2f' % (gt['ssim'], gt['mean_shift'], gt['local_contrast_ratio'])),
           fill=(235, 235, 235))
    crop = lambda a, s: np.ascontiguousarray(a[s * y:s * (y + n), s * x:s * (x + n)])
    cols = [Image.fromarray(crop(O, 1)).resize((S, S), Image.NEAREST), Image.fromarray(crop(show(hd, k), f)).resize((S, S), Image.LANCZOS)]
    if has_alpha(r):
        cols += [Image.fromarray(crop(show(o, k, True), 1)).resize((S, S), Image.NEAREST),
                 Image.fromarray(crop(show(hd, k, True), f)).resize((S, S), Image.LANCZOS)]
    else: cols += [None, None]
    th = Image.fromarray(show(hd, k)); th.thumbnail((S, S), Image.LANCZOS); cols.append(th)
    for c, t in enumerate(cols):
        if t is not None: im.paste(t, (c * (S + 8), 20))
    if not has_alpha(r): d.text((2 * (S + 8) + 90, 20 + S // 2), '(no alpha)', fill=(120, 120, 120))
    return im

def encode(u8, r):
    dst = P.encode(u8, r, PACK)
    tmp = os.path.join(OUT, '_enc', 'pack', '%03d.png' % r['i'])
    if os.path.exists(tmp): os.remove(tmp)                       # 4096² PNGs: do not keep (disk)
    return dst

def build_unit(u, R):
    caps = [cap(r) for r in u]; data = []
    for r in u:
        o, f, W, Hh, V = P.variants(r, R)
        gates = OD((v, P.drift(o, np.clip(np.round(img), 0, 255).astype(np.uint8), r['kind'])) for v, img in V.items())
        # broken_blocks catches garbage / flat MODEL tiles, so it is judged on A (the anchored model output). B / C / D are fixed
        # filters of A: their own count (kept as broken_blocks_level) flags the intended fine band in flat blocks (> 6x Lanczos)
        bb_a = gates['gen4x']['broken_blocks']
        for v in LEVELS[1:]:
            g = gates[v]; g['broken_blocks_level'] = g['broken_blocks']; g['broken_blocks'] = bb_a
            g['ok'] = bool(g['ssim'] >= P.SSIM_MIN and g['mean_shift'] <= P.SHIFT_MAX and g['new_colours'] <= P.NEWCOL_MAX and bb_a == 0)
        data.append((r, o, f, W, Hh, V, gates))
    top = min(caps) if None not in caps else None
    q = None
    if top is not None:
        q = next((j for j in range(top, -1, -1) if all(g[6][LEVELS[j]]['ok'] for g in data)), None)
    for r, o, f, W, Hh, V, gates in data:
        lvl = LEVELS[q] if q is not None else None; dst = os.path.join(PACK, r['dds']); nb = None
        if lvl:
            u8 = np.clip(np.round(V[lvl]), 0, 255).astype(np.uint8); encode(u8, r); nb = os.path.getsize(dst)
            hd = u8
        else:
            if os.path.exists(dst): os.remove(dst)
            hd = np.clip(np.round(V['gen4x']), 0, 255).astype(np.uint8)       # shown for reference only (not packed)
        os.makedirs(TILE, exist_ok=True); tile(r, o, hd, f, lvl, gates).save(os.path.join(TILE, '%05d.png' % r['i']))
        rec = OD([('i', r['i']), ('png', r['png']), ('dds', r['dds']), ('object_path', r['object_path']), ('format', r['format']),
                  ('kind', r['kind']), ('verdict_m4', r.get('verdict')), ('size', r['size']), ('hd_size', [W, Hh]),
                  ('unit', [x['i'] for x in u]), ('cap', E.EYE.get(r['png'], 'gen4x_d')), ('level', lvl), ('bytes', nb),
                  ('gates', gates), ('built', time.strftime('%Y-%m-%d %H:%M'))])
        os.makedirs(RES, exist_ok=True); json.dump(rec, open(res_path(r), 'w', encoding='utf-8'), indent=1)
    return q

def batches(U): return [U[b:b + BATCH] for b in range(0, len(U), BATCH)]

def status():
    R = P.rows(); out = []
    for b, bu in enumerate(batches(units(R))):
        built = sum(all(done(r) for r in u) for u in bu); rd = sum(ready(u, R) for u in bu)
        out.append((b, built, rd, len(bu)))
        print('batch %3d  built %3d  ready %3d  units %3d  %s' % (b, built, rd, len(bu), 'REVIEWED' if b in E.REVIEWED else ''))
    return out

def build():
    R = P.rows(); B = batches(units(R)); args = sys.argv[2:]
    rng = next((a for a in args if '-' in a and a.replace('-', '').isdigit()), None)
    b0, b1 = (int(rng.split('-')[0]), int(rng.split('-')[1])) if rng else (0, len(B) - 1)
    sh = next((a.split('/') for a in args if '/' in a and a.replace('/', '').isdigit()), None)
    n = 0; t0 = time.time()
    for b in range(b0, min(b1, len(B) - 1) + 1):
        for j, u in enumerate(B[b]):
            if sh and j % int(sh[1]) != int(sh[0]): continue
            if all(done(r) for r in u) or not ready(u, R): continue
            hold = glob.glob(os.path.join(P.REB, '*', 'work', 'PERF_HOLD')) + P.low_commit()
            if hold: print('PERF_HOLD present: stopping', hold, flush=True); sys.exit(75)
            t = time.time(); q = build_unit(u, R); n += 1
            print('b%d %s %s -> %s  %.0fs' % (b, [r['i'] for r in u], u[0]['kind'], LEVELS[q] if q is not None else 'ORIGINAL', time.time() - t), flush=True)
    print('build pass done: %d units in %.0fs' % (n, time.time() - t0), flush=True)

def sheets():
    R = P.rows(); b = int(sys.argv[2]); bu = batches(units(R))[b]
    rs = [json.load(open(res_path(r), encoding='utf-8')) for u in bu for r in u if os.path.exists(res_path(r))]
    rs = [x for x in rs if x['level']]                                          # ORIGINAL: nothing to review
    os.makedirs(SHEETS, exist_ok=True)
    for old in glob.glob(os.path.join(SHEETS, 'b%03d_*.png' % b)): os.remove(old)
    for s in range(0, len(rs), 8):
        ts = [Image.open(os.path.join(TILE, '%05d.png' % x['i'])) for x in rs[s:s + 8]]
        im = Image.new('RGB', (ts[0].width, 22 + sum(t.height for t in ts)), (16, 16, 20)); d = ImageDraw.Draw(im)
        d.text((4, 4), 'batch %d sheet %d   columns: original 48 px spot (nearest, 6x) | HD | alpha original | alpha HD | HD full' % (b, s // 8 + 1),
               fill=(255, 220, 0))
        y = 22
        for t in ts: im.paste(t, (0, y)); y += t.height
        im.save(os.path.join(SHEETS, 'b%03d_%02d.png' % (b, s // 8 + 1)))
    lv = Counter(x['level'] for x in rs)
    print('batch', b, 'textures to review', len(rs), dict(lv), 'sheets', (len(rs) + 7) // 8)

def pack():
    R = P.rows(); rows_ = []; lv = Counter()
    for b, bu in enumerate(batches(units(R))):
        if b not in E.REVIEWED: continue
        for u in bu:
            for r in u:
                if not done(r): continue          # missing, or built before its eye cap: stale level, never packed
                x = json.load(open(res_path(r), encoding='utf-8'))
                if not x['level']: continue
                # key from the texture's own dds path: 8 selection rows carry a png path borrowed from a same-named texture in
                # another package (e.g. WEP_StandardRocket's EditorTextureSet as CanyonFloor_A's), so png keys would collide.
                # Identical to the png key for every other row (checked on batches 0-2: 0 differences)
                rows_.append(OD([('key', x['dds'].lower()[:-4] + '.png'),('object_path', x['object_path']), ('dds', x['dds']), ('format', x['format']),
                                 ('size', x['hd_size']), ('bytes', x['bytes']), ('level', x['level'])])); lv[x['level']] += 1
    json.dump(OD([('version', 1), ('generator', 'AssetTools/scripts/wfc/hd_full_push.py (HD full pass, ladder D->C->B->A, eye-reviewed batches)'),
                  ('generated', time.strftime('%Y-%m-%d %H:%M')), ('reviewed_batches', sorted(E.REVIEWED)), ('textures', len(rows_)),
                  ('rows', rows_)]), open(os.path.join(PACK, 'hd_index.json'), 'w', encoding='utf-8'), indent=1)
    print(len(rows_), 'textures', round(sum(x['bytes'] for x in rows_) / 2 ** 20, 1), 'MB', dict(lv))

if __name__ == '__main__':
    {'status': status, 'build': build, 'sheets': sheets, 'pack': pack}[sys.argv[1]]()
