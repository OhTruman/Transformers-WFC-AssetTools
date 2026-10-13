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
            if not c[0].startswith(('ENV_', 'DES_')) or any(k.lower() in c[0].lower() for k in NOT_COLOUR): continue
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

def gen(maps=None):
    us, R = units(maps)
    for p in (RES, REVIEW, PACK): os.makedirs(p, exist_ok=True)
    for mp, r, d, m, md in us:
        if os.path.exists(res_path(r)): continue
        EP.stop(); t0 = time.time()
        o = P.orig(r); D = EP.load_d(d); f = D.shape[1] / o.shape[1]
        M0 = EP.load_d(md) if md else None; pr = EP.protect_mask(M0, (D.shape[1], D.shape[0]), f); txt = G.prompt(r['png'])
        E3 = G.lock(G.cached(r['i'], LEVEL, lambda: G.regenerate(D[..., :3], txt, STRENGTH, r['i'])), D, o, pr)
        g = EP.gates(D, E3, o, M0)
        frm = 'sd15+controlnet_tile denoise %.2f steps %d cfg %.1f seed %d prompt "%s"' % (STRENGTH, G.STEPS, G.CFG, r['i'], txt)
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
    maps = sys.argv[2].split(',') if len(sys.argv) > 2 else None
    if a == 'list':
        us, _ = units(maps)
        for mp, r, d, m, md in us: print(r['i'], mp, r['kind'], d['level'], d['size'], r['png'], '+ masks' if md else '')
        print(len(us), 'units', round(sum(d['size'][0] * d['size'][1] for _, _, d, _, _ in us) / 2 ** 20, 1), 'units of 1024^2 (at HD size)')
    elif a == 'gen': gen(maps)
    elif a == 'sheets': sheets()
    elif a == 'pack': pack()
