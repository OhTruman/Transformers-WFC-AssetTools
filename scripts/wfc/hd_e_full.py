"""Level E full pass (docs/HD_FINISH_PLAN.md, approved by Integration 2026-10-13): G2 only (SD 1.5 + ControlNet tile, denoise 0.40,
sliced) over the reviewed D pack, per map, in exclusive DML windows. Milestone 1 = the world colour textures bound by the user's
maps (Molten, Streets, Gorge, Rust, Debris; Rendering's materials-bound TSVs). Same locks / protection / gates as the Rust pilot
(hd_e_gen.py, hd_e_pilot.py); a unit that fails a gate keeps D (no E row).

  python hd_e_full.py list [MAPS]       units in order (MAPS default: the milestone-1 maps), with D level and size
  python hd_e_full.py gen [MAPS]        generate + lock + encode per unit (resumable, checkpointed; exit 75 on hold / low commit)
  python hd_e_full.py sheets            review sheets (orig | D | E, busiest + flattest spot), 8 units per sheet
  python hd_e_full.py pack              pack/hd_index.json from reviewed, gate-passing, not rejected units (hd_e_eye.py)

Output root: out/hd/push_e_full (pack/, results/, review/, sheets/, raw/, height/). Frozen copies: push_e_snap_<date>_<scope>.
"""
import glob, json, os, sys, time
from collections import OrderedDict as OD
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('WFC_HD_PUSH_SET', 'full')
import hd_e_gen as G  # noqa: E402
import hd_e_pilot as EP  # noqa: E402
import hd_push as P  # noqa: E402

AT = EP.AT
F_ROOT = os.path.join(AT, 'out', 'hd', 'push_e_full')
G.G_ROOT = F_ROOT                      # checkpoints (raw/) and heights go under the full-pass root
D_PACK = os.path.join(AT, 'out', 'hd', 'push_full', 'pack')
TSV_DIR = os.path.join(os.path.dirname(AT), 'Rebuild-Rendering', 'work', 'handoff_assettools')
MILESTONE1 = ['MP_KON_Molten', 'MP_IAC_Streets', 'MP_UND_Gorge', 'MP_IAC_Rust', 'MP_ORB_Debris']
LEVEL, STRENGTH = 'G2', G.DENOISE['G2']
NOT_COLOUR = ('NORM', 'MASK', 'Masks_NormY', 'SPEC', 'EMIS', 'GLOW', 'Cube', 'Alpha', '_DIS', 'Illum', 'Flare', 'Nebula')
RES, REVIEW, SHEETS, PACK = (os.path.join(F_ROOT, x) for x in ('results', 'review', 'sheets', 'pack'))

def map_objects(maps):
    """world (ENV_ / DES_) colour-like 2d texture objects each map's materials bind, maps in order, most-used first, de-duplicated"""
    seen, out = set(), []
    for m in maps:
        rows = []
        for l in open(os.path.join(TSV_DIR, '%s_textures.tsv' % m), encoding='utf-8'):
            c = l.rstrip('\n').split('\t')
            if l.startswith('#') or c[0] == 'object' or len(c) < 3 or c[2] != '2d': continue
            if not c[0].startswith(('ENV_', 'DES_')) or any(k in c[0] for k in NOT_COLOUR): continue      # case-sensitive: NORM must not hit Color_NormX
            rows.append((-int(c[1] or 0), c[0].lower()))
        for _, o in sorted(rows):
            if o not in seen: seen.add(o); out.append((m, o))
    return out

def units(maps=None):
    """(map, r, d, m, md): colour rows of the live D pack in map order; m / md = the TEXSET masks half and its D row"""
    idx = json.load(open(os.path.join(D_PACK, 'hd_index.json'), encoding='utf-8'))
    packed = {x['object_path'].lower(): x for x in idx['rows']}
    R = P.rows(); by_obj = {r['object_path'].lower(): r for r in R}; out = []
    for mp, o in map_objects(maps or MILESTONE1):
        d = packed.get(o); r = by_obj.get(o)
        if d is None or r is None or r['kind'] not in ('colour', 'texset_color'): continue
        m = P.partner(r, R) if r['kind'] == 'texset_color' else None
        md = packed.get(m['object_path'].lower()) if m else None
        out.append((mp, r, d, m, md))
    return out, R

def res_path(r): return os.path.join(RES, '%05d.json' % r['i'])

def tile(o, D, E, f, label):
    S = 240; n, busy, flat = EP.spots(o)
    im = Image.new('RGB', (3 * (S + 6), 2 * S + 36), (16, 16, 20)); dr = ImageDraw.Draw(im)
    dr.text((3, 2), label[:118], fill=(230, 230, 230))
    for row, (x, y) in enumerate((busy, flat)):
        yy = 18 + row * (S + 18)
        im.paste(Image.fromarray(np.ascontiguousarray(o[y:y + n, x:x + n, :3])).resize((S, S), Image.NEAREST), (0, yy))
        for c, img in enumerate((D[..., :3], E), 1):
            cr = np.clip(np.round(img), 0, 255).astype(np.uint8)[int(f * y):int(f * (y + n)), int(f * x):int(f * (x + n))]
            im.paste(Image.fromarray(np.ascontiguousarray(cr)).resize((S, S), Image.LANCZOS), (c * (S + 6), yy))
    return im

GEN_SCALE = int(os.environ.get('WFC_E_GEN_SCALE', '2'))   # 2: generate at 2x the original, D's 4x fine band on top (Integration
                                                          # 2026-10-13, option a: 4x less GPU); 4: generate at the HD size (Rust pilot)

def generate(r, D, o, txt, level=None, scale=None):
    """E colour before the lock. At scale 2 the model redraws D box-downsampled to 2x the original; the result is upscaled to the
    HD size and D's own detail above 2x (D - up(down(D))) is added back, so E's new mid-scale detail sits under D's fine band"""
    level = level or LEVEL; scale = scale or GEN_SCALE; s = G.DENOISE[level]
    Hh, W = D.shape[:2]; oh, ow = o.shape[:2]; w2, h2 = 2 * ow, 2 * oh
    if scale >= 4 or (w2, h2) == (W, Hh): return G.cached(r['i'], level, lambda: G.regenerate(D[..., :3], txt, s, r['i']))
    D2 = EP.area(D[..., :3], w2, h2)
    g2 = G.cached(r['i'], level + 'x2', lambda: G.regenerate(np.clip(np.round(D2), 0, 255).astype(np.float32), txt, s, r['i']))
    fine = D[..., :3] - EP.up(D2.astype(np.float32), W, Hh)
    return np.clip(EP.up(g2.astype(np.float32), W, Hh) + fine, 0, 255)

AB_ARMS = [('E-2x-G2', 2, 'G2'), ('E-2x-G3', 2, 'G3'), ('E-4x-G3', 4, 'G3')]

def ab(ids):
    """A/B for the user's path / strength choice (Integration 2026-10-13) on Rust pilot units: Original | D | E-2x-G2 | E-2x-G3 |
    E-4x-G3, 100 % HD-pixel crops at the busiest and flattest spot, same locks / protection / gates. 4x arms reuse the pilot's
    checkpoints (push_e_gen/raw); 2x arms are generated here (checkpointed under push_e_full/raw)"""
    us, R = EP.units(); sel = [u for u in us if u[0]['i'] in ids]; out = os.path.join(F_ROOT, 'ab'); os.makedirs(out, exist_ok=True)
    rows, rep = [], OD()
    for r, d, m, md in sel:
        EP.stop(); o = P.orig(r); D = EP.load_d(d); f = D.shape[1] / o.shape[1]
        M0 = EP.load_d(md) if md else None; pr = EP.protect_mask(M0, (D.shape[1], D.shape[0]), f, md['object_path'] if md else None); txt = G.prompt(r['png'])
        arms = OD(); secs = OD()
        for name, sc, lv in AB_ARMS:
            t0 = time.time()
            if sc == 4:
                p4 = os.path.join(AT, 'out', 'hd', 'push_e_gen', 'raw', '%05d_%s.png' % (r['i'], lv))
                raw = np.asarray(Image.open(p4)).astype(np.float32) if os.path.exists(p4) else generate(r, D, o, txt, lv, 4)
            else: raw = generate(r, D, o, txt, lv, 2)
            arms[name] = G.lock(raw, D, o, pr); secs[name] = round(time.time() - t0)
        rep[r['png']] = OD((k, OD([('gates', EP.gates(D, v, o, M0)), ('seconds', secs[k])])) for k, v in arms.items())
        S = 300; n, busy, flat = EP.spots(o); n = min(n, 32); cols = [D[..., :3]] + list(arms.values())
        im = Image.new('RGB', ((len(cols) + 1) * (S + 6), 2 * S + 36), (16, 16, 20)); dr = ImageDraw.Draw(im)
        dr.text((3, 2), '%05d %s   Original | D | %s   (100%% HD pixels)' % (r['i'], r['png'][-50:], ' | '.join(arms)), fill=(230, 230, 230))
        for row, (x, y) in enumerate((busy, flat)):
            yy = 18 + row * (S + 18); k = int(f * n)
            im.paste(Image.fromarray(np.ascontiguousarray(o[y:y + n, x:x + n, :3])).resize((S, S), Image.NEAREST), (0, yy))
            for c, img in enumerate(cols, 1):
                cr = np.clip(np.round(img), 0, 255).astype(np.uint8)[int(f * y):int(f * y) + k, int(f * x):int(f * x) + k]
                im.paste(Image.fromarray(np.ascontiguousarray(cr)).resize((S, S), Image.NEAREST if k <= S else Image.LANCZOS), (c * (S + 6), yy))
        rows.append(im); print('ab', r['i'], {k: (v['gates']['pass'], v['seconds']) for k, v in rep[r['png']].items()}, flush=True)
    sh = Image.new('RGB', (rows[0].width, sum(i.height for i in rows)), (16, 16, 20)); y = 0
    for i in rows: sh.paste(i, (0, y)); y += i.height
    sh.save(os.path.join(out, 'ab_sheet.png')); json.dump(rep, open(os.path.join(out, 'ab_gates.json'), 'w', encoding='utf-8'), indent=1)
    print('ab sheet', os.path.join(out, 'ab_sheet.png'), flush=True)

G.DENOISE.setdefault('G4', 0.70)        # stronger level for the "full overhaul" (user 2026-10-13); not in the pilot ladder

def lock_soft(Gc, D, o, prot, k=2):
    """lock to D's colour at 1/k of the original resolution (k = 2: layout, colours and designs stay; detail up to k original pixels
    is free), then D in protected regions"""
    Hh, W = D.shape[:2]; oh, ow = o.shape[:2]; lw, lh = max(1, ow // k), max(1, oh // k); rgb = Gc.copy()
    for _ in range(2):
        corr = EP.area(D[..., :3], lw, lh) - EP.area(np.clip(rgb, 0, 255).astype(np.float32), lw, lh)
        rgb = rgb + EP.up(corr.astype(np.float32), W, Hh)
    if prot is not None: rgb = rgb * (1 - prot[..., None]) + D[..., :3] * prot[..., None]
    return np.clip(rgb, 0, 255)

def ab4(ids):
    """second A/B (Integration 2026-10-13): Original | D | E-4x-G3 (exact lock) | E-4x-G4 (denoise 0.70, lock at half the
    original resolution); 100 % HD crops at the busiest and flattest spot; same protection / gates (gates vs D at full original res)"""
    us, R = EP.units(); sel = [u for u in us if u[0]['i'] in ids]; out = os.path.join(F_ROOT, 'ab'); os.makedirs(out, exist_ok=True)
    rows, rep = [], OD()
    for r, d, m, md in sel:
        EP.stop(); o = P.orig(r); D = EP.load_d(d); f = D.shape[1] / o.shape[1]
        M0 = EP.load_d(md) if md else None; pr = EP.protect_mask(M0, (D.shape[1], D.shape[0]), f, md['object_path'] if md else None); txt = G.prompt(r['png'])
        p3 = os.path.join(AT, 'out', 'hd', 'push_e_gen', 'raw', '%05d_G3.png' % r['i'])
        raw3 = np.asarray(Image.open(p3)).astype(np.float32) if os.path.exists(p3) else generate(r, D, o, txt, 'G3', 4)
        t0 = time.time(); raw4 = generate(r, D, o, txt, 'G4', 4); dt = round(time.time() - t0)
        arms = OD([('E-4x-G3', G.lock(raw3, D, o, pr)), ('E-4x-G4', lock_soft(raw4, D, o, pr))])
        rep[r['png']] = OD((k, OD([('gates', EP.gates(D, v, o, M0))])) for k, v in arms.items())
        rep[r['png']]['E-4x-G4']['seconds'] = dt
        rep[r['png']]['protected_pct'] = round(100 * float(pr.mean()), 1) if pr is not None else 0.0
        S = 300; n, busy, flat = EP.spots(o); n = min(n, 32); cols = [D[..., :3]] + list(arms.values())
        im = Image.new('RGB', ((len(cols) + 1) * (S + 6), 2 * S + 36), (16, 16, 20)); dr = ImageDraw.Draw(im)
        dr.text((3, 2), '%05d %s   Original | D | E-4x-G3 | E-4x-G4 (soft lock)   protected %s%%' % (r['i'], r['png'][-50:], rep[r['png']]['protected_pct']), fill=(230, 230, 230))
        for row, (x, y) in enumerate((busy, flat)):
            yy = 18 + row * (S + 18); kk = int(f * n)
            im.paste(Image.fromarray(np.ascontiguousarray(o[y:y + n, x:x + n, :3])).resize((S, S), Image.NEAREST), (0, yy))
            for c, img in enumerate(cols, 1):
                cr = np.clip(np.round(img), 0, 255).astype(np.uint8)[int(f * y):int(f * y) + kk, int(f * x):int(f * x) + kk]
                im.paste(Image.fromarray(np.ascontiguousarray(cr)).resize((S, S), Image.NEAREST if kk <= S else Image.LANCZOS), (c * (S + 6), yy))
        rows.append(im); print('ab4', r['i'], {k: v['gates']['pass'] for k, v in rep[r['png']].items() if isinstance(v, dict) and 'gates' in v}, dt, 's', flush=True)
    sh = Image.new('RGB', (rows[0].width, sum(i.height for i in rows)), (16, 16, 20)); y = 0
    for i in rows: sh.paste(i, (0, y)); y += i.height
    sh.save(os.path.join(out, 'ab4_sheet.png')); json.dump(rep, open(os.path.join(out, 'ab4_gates.json'), 'w', encoding='utf-8'), indent=1)
    print('ab4 sheet', os.path.join(out, 'ab4_sheet.png'), flush=True)

def gen(maps=None):
    us, R = units(maps)
    for p in (RES, REVIEW, PACK): os.makedirs(p, exist_ok=True)
    for mp, r, d, m, md in us:
        if os.path.exists(res_path(r)): continue
        EP.stop(); t0 = time.time()
        o = P.orig(r); D = EP.load_d(d); f = D.shape[1] / o.shape[1]
        M0 = EP.load_d(md) if md else None; pr = EP.protect_mask(M0, (D.shape[1], D.shape[0]), f, md['object_path'] if md else None); txt = G.prompt(r['png'])
        E3 = G.lock(generate(r, D, o, txt), D, o, pr)
        g = EP.gates(D, E3, o, M0)
        frm = 'sd15+controlnet_tile at %dx, denoise %.2f steps %d cfg %.1f seed %d prompt "%s"' % (GEN_SCALE, STRENGTH, G.STEPS, G.CFG, r['i'], txt)
        rec = OD([('i', r['i']), ('map', mp), ('png', r['png']), ('key', d['key']), ('d_level', d['level']), ('gates', g), ('from', frm),
                  ('rows', [])])
        if g['pass']:
            E = D.copy(); E[..., :3] = E3
            hgt = EP.height(E3.astype(np.uint8), os.path.join(F_ROOT, 'height', '%05d.png' % r['i']))
            hp = hgt - P.gblur(hgt[..., None], 2 * f)[..., 0]
            if r['kind'] == 'texset_color': E[..., 3] = EP.relief(D[..., 3], hp, 0, 1.0, (D.shape[1], D.shape[0]))
            todo = [(r, d, E)]
            if m is not None and md is not None:
                M = EP.load_d(md); M[..., 3] = EP.relief(M[..., 3], hp, 1, 1.0, (M.shape[1], M.shape[0])); todo.append((m, md, M))
            for rr, dd, img in todo:
                dst = P.encode(np.clip(np.round(img), 0, 255).astype(np.uint8), rr, PACK)
                tmp = os.path.join(P.OUT, '_enc', 'pack', '%03d.png' % rr['i'])
                if os.path.exists(tmp): os.remove(tmp)
                rec['rows'].append(OD([('key', dd['key']), ('object_path', dd['object_path']), ('dds', dd['dds']), ('format', dd['format']),
                                       ('size', dd['size']), ('bytes', os.path.getsize(dst)), ('level', 'e_' + LEVEL.lower()),
                                       ('d_level', dd['level']), ('from', frm)]))
        tile(o, D, E3, f, '%05d %s %s  orig | D | E(%s)  gates %s' % (r['i'], mp, r['png'][-60:], LEVEL, 'PASS' if g['pass'] else 'FAIL -> D')
             ).save(os.path.join(REVIEW, '%05d.png' % r['i']))
        json.dump(rec, open(res_path(r) + '.tmp', 'w', encoding='utf-8'), indent=1); os.replace(res_path(r) + '.tmp', res_path(r))
        print('e', r['i'], mp, d['size'], 'PASS' if g['pass'] else 'FAIL', '%.0fs' % (time.time() - t0), flush=True)
    print('gen done', flush=True)

def sheets():
    os.makedirs(SHEETS, exist_ok=True)
    fs = sorted(glob.glob(os.path.join(REVIEW, '*.png')))
    for s in range(0, len(fs), 8):
        ims = [Image.open(p) for p in fs[s:s + 8]]
        o = Image.new('RGB', (max(i.width for i in ims), sum(i.height for i in ims)), (16, 16, 20)); y = 0
        for i in ims: o.paste(i, (0, y)); y += i.height
        o.save(os.path.join(SHEETS, 'e%03d.png' % (s // 8 + 1)))
    print(len(fs), 'units', (len(fs) + 7) // 8, 'sheets', flush=True)

def pack():
    import hd_e_eye as EE
    rows = []; n = rej = fail = unrev = 0
    for p in sorted(glob.glob(os.path.join(RES, '*.json'))):
        x = json.load(open(p, encoding='utf-8')); n += 1
        if x['map'] not in EE.REVIEWED_MAPS: unrev += 1; continue
        if x['png'] in EE.REJECT: rej += 1; continue
        if not x['rows']: fail += 1; continue
        rows.extend(x['rows'])
    json.dump(OD([('version', 1), ('generator', 'scripts/wfc/hd_e_full.py pack (level E, G2, eye-reviewed)'),
                  ('generated', time.strftime('%Y-%m-%d %H:%M')), ('level', 2), ('over', 'D root (push_full / push_full_snap_*)'),
                  ('reviewed_maps', sorted(EE.REVIEWED_MAPS)), ('textures', len(rows)), ('rows', rows)]),
              open(os.path.join(PACK, 'hd_index.json'), 'w', encoding='utf-8'), indent=1)
    print(len(rows), 'rows', round(sum(r['bytes'] for r in rows) / 2 ** 20, 1), 'MB; units', n, 'gate-fail', fail, 'rejected', rej,
          'unreviewed', unrev, flush=True)

if __name__ == '__main__':
    a = sys.argv[1] if len(sys.argv) > 1 else 'list'
    args = [x for x in sys.argv[2:] if not x.startswith('--')]          # hd_push appends --v2 on import
    maps = args[0].split(',') if args else None
    if a == 'list':
        us, _ = units(maps)
        for mp, r, d, m, md in us: print(r['i'], mp, r['kind'], d['level'], d['size'], r['png'], '+ masks' if md else '')
        print(len(us), 'units', round(sum(d['size'][0] * d['size'][1] for _, _, d, _, _ in us) / 2 ** 20, 1), 'units of 1024^2 (at HD size)')
    elif a == 'gen': gen(maps)
    elif a == 'sheets': sheets()
    elif a == 'pack': pack()
    elif a == 'ab': ab([int(x) for x in args[0].split(',')])
    elif a == 'ab4': ab4([int(x) for x in args[0].split(',')])
