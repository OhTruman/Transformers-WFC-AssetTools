"""Eye verdicts for the faithful HD pack -> out/hd/full/verdicts.json (k -> {verdict, why}), read by `hd_full.py index`.

Review 2026-10-11: all 237 review sheets (hd_full.py sheets: original | HD at the most detailed 64 px spot) were checked by eye; 60
flagged textures were then checked at full resolution (two 64 px spots, original nearest x2 vs HD 1:1). Verdicts:
  PASS    the HD texture goes into hd_index.json (Rendering's loader uses it)
  REMAKE  the HD texture is not faithful (pattern changed / detail invented / artefacts); the original stays in use and the texture
          goes to manifests/hd/remake_candidates.json for the M4b remake pass
  KEEP    must stay pixel-exact (lookup tables, custom-colour masks, palette swatches); the original stays in use, not a remake target
Every eye REMAKE / KEEP below was seen at full resolution. On top of the eye review, the user's rule of 2026-10-09 (PASS = faithful
AND reads as HD; REMAKE = still pixelated / soft) is applied with the pilot's automatic thresholds (hd_v4.verdict): REMAKE if the
gate rejected it, the original's short side < 64, the blend is mostly Lanczos (> 60 %), or the detail gain over Lanczos < 1.25.

  python hd_verdicts.py gain --shard i/N   CPU: detail gain per faithful texture -> out/hd/full/_gain_s<i>.json (resumable)
  python hd_verdicts.py                    verdicts.json from the eye lists + the automatic rules (needs every gain)
  python hd_verdicts.py showcase           before / after sheet (PASS and REMAKE examples) for the user
"""
import glob, json, os, re, sys, time
from collections import OrderedDict as OD, Counter
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if '--v2' not in sys.argv: sys.argv.append('--v2')
import hd_full as F  # noqa: E402
V4, H = F.V4, F.H

REMAKE = OD([
    (2411, 'regular perforated grid: square holes re-drawn as a hex-like mesh (hole shape changed)'),
    (2403, 'regular rounded dot grid (mask) became irregular blobs'),
    (2405, 'perforation relief (normal) reinterpreted as irregular shapes'),
    (2452, 'regular dot-column relief (normal) turned into noise'),
    (2457, 'regular dot-column relief (normal) turned into noise'),
    (2462, 'regular dot-column relief (normal) turned into noise'),
    (2987, 'regular dot-column relief (normal) turned into noise'),
    (2221, 'green / purple fringe pixels along the window-frame edges'),
    (3139, 'bright dotted-line artefacts along dark edges'),
    (3143, 'bright dotted-line artefacts along dark edges'),
    (3780, 'grain in the dark flats amplified into speckle (weapon, most-seen)'),
    (165, 'faint line art resolved into a detailed drawing that is not discernible in the original (invented)'),
    (1098, 'faint line art resolved into a detailed figure that is not discernible in the original (invented)'),
    (2552, 'fine crinkle relief invented over the blocky original'),
    (1742, 'fine crack relief invented over the blocky original'),
    (1754, 'fine grain relief invented over the blocky original'),
    (3432, 'two-channel normal (blue = 0, not Z): XYZ renormalisation flattened the RG relief (std 31 -> 26)'),
    (3683, 'two-channel normal (blue = 0, not Z): XYZ renormalisation flattened the RG relief'),
    (1118, 'two-channel normal (blue ~ 6, not Z): XYZ renormalisation; blue channel not preserved'),
])
KEEP_RULES = [
    (r'LUT$', 'colour lookup table: the HD version adds a seam at the cell boundaries; lookups must stay exact'),
    (r'CustAB', 'custom-colour / aux-glow mask: the HD version invents vein-like structure (seen on 3692, 3696, 3483, 3303); '
                'team-colour masks must stay exact'),
    (r'^[AD]_[a-z]+$', 'palette swatch: the HD version smooths the authored 8 px colour steps'),
]

def gain():
    """detail gain (hd_v4.detail_gain: structure-aligned detail over a plain Lanczos 2x) of every faithful texture"""
    shard = tuple(int(x) for x in sys.argv[sys.argv.index('--shard') + 1].split('/')) if '--shard' in sys.argv else (0, 1)
    out = os.path.join(F.FULL, '_gain_s%d.json' % shard[0])
    done = json.load(open(out, encoding='utf-8')) if os.path.exists(out) else {}
    sel = {s['object_path']: s for s in json.load(open(H.SEL, encoding='utf-8'))}
    todo = [r for r in F.load_recs() if r.get('hd_png') and r['k'] % shard[1] == shard[0]]
    t0 = time.time(); n = 0
    for r in todo:
        key = '%d@%s' % (r['k'], r.get('t', 0))                             # a --redo record gets a fresh gain
        if key in done: continue
        s = sel[r['object_path']]
        hd = np.asarray(Image.open(os.path.join(F.FULL, r['hd_png'])).convert('RGBA'))
        done[key] = round(V4.detail_gain(H.source(s), hd, s), 4); n += 1
        if n % 50 == 0:
            json.dump(done, open(out, 'w', encoding='utf-8')); print(n, 'gains', '%.0fs' % (time.time() - t0), flush=True)
    json.dump(done, open(out, 'w', encoding='utf-8')); print('gain done', n, 'new', '%.0fs' % (time.time() - t0))

def main():
    recs = F.load_recs(); verd = OD(); why_n = Counter(); gains = {}
    for gp in glob.glob(os.path.join(F.FULL, '_gain_s*.json')): gains.update(json.load(open(gp, encoding='utf-8')))
    sel = {s['object_path']: s for s in json.load(open(H.SEL, encoding='utf-8'))}
    for r in sorted(recs, key=lambda r: r['k']):
        k, name = r['k'], r['object_path'].split('.')[-1]
        keep = next((w for p, w in KEEP_RULES if re.search(p, name)), None)
        if keep: v = ('KEEP', [keep])
        elif not r.get('hd_png'): v = ('REMAKE', ['no faithful upscale (gate: final psnr %s, mean shift %s, tone ok %s)' % (
            r.get('final_psnr'), r.get('max_mean_shift'), (r.get('tone') or {}).get('ok'))])
        else:
            why = ['eye: ' + REMAKE[k]] if k in REMAKE else []
            g = gains.get('%d@%s' % (k, r.get('t', 0)))
            if g is None: raise SystemExit('no detail gain for %d: run hd_verdicts.py gain first' % k)
            size = sel[r['object_path']]['size']
            if min(size) < V4.MIN_SIDE_HD: why.append('original too small (%dx%d)' % tuple(size))
            if r['blend_share'].get('lanczos', 0) > V4.LANCZOS_SHARE_MAX:
                why.append('blend mostly Lanczos (%.0f%%): models found little faithful detail' % (100 * r['blend_share']['lanczos']))
            if g < V4.DETAIL_GAIN_MIN: why.append('detail gain %.2f < %.2f: reads soft / not HD' % (g, V4.DETAIL_GAIN_MIN))
            v = ('REMAKE', why) if why else ('PASS', ['eye: faithful on the review sheet; detail gain %.2f' % g])
        verd[str(k)] = OD([('verdict', v[0]), ('why', v[1]), ('object_path', r['object_path'])]); why_n[v[0]] += 1
    missing = [k for k in REMAKE if str(k) not in verd]
    if missing: raise SystemExit('REMAKE ids not in the records: %s' % missing)
    out = os.path.join(F.FULL, 'verdicts.json')
    json.dump(verd, open(out, 'w', encoding='utf-8'), indent=1)
    print('verdicts', dict(why_n), '->', out)

def showcase():
    """before / after sheet for the user: PASS examples (highest detail gain per class) and REMAKE examples (the eye reasons first,
    then the automatic ones), each original nearest x2 | HD at the most detailed 96 px spot -> out/hd/full/before_after_M4.png"""
    from PIL import ImageDraw
    verd = json.load(open(os.path.join(F.FULL, 'verdicts.json'), encoding='utf-8'))
    recs = {r['k']: r for r in F.load_recs()}; sel = {s['k']: s for s in json.load(open(H.SEL, encoding='utf-8'))}
    gains = {}
    for gp in glob.glob(os.path.join(F.FULL, '_gain_s*.json')): gains.update(json.load(open(gp, encoding='utf-8')))
    g = lambda k: gains.get('%d@%s' % (k, recs[k].get('t', 0)), 0)
    passes = []
    for cls, grp in (('colour', 'TEXTUREGROUP_Character'), ('colour', 'TEXTUREGROUP_Weapon'), ('colour', None), ('normal', None), ('data', None)):
        c = [k for k, v in verd.items() if v['verdict'] == 'PASS' and recs[int(k)]['cls'] == cls and recs[int(k)].get('lod_group') == grp
             and min(sel[int(k)]['size']) >= 256]
        passes += sorted((int(k) for k in c), key=g, reverse=True)[:2]
    eye = [3780, 2411, 2452, 1742]                                       # 3432 (two-channel normal) lights black: blue is not Z
    auto = [int(k) for k, v in verd.items() if v['verdict'] == 'REMAKE' and int(k) not in REMAKE and recs[int(k)].get('hd_png')
            and any('reads soft' in w for w in v['why']) and min(sel[int(k)]['size']) >= 256][:2]
    rows = [('PASS', k) for k in passes] + [('REMAKE', k) for k in eye + auto]
    n, S, W = 96, 300, 2 * 300 + 30
    im = Image.new('RGB', (2 * W + 20, ((len(rows) + 1) // 2) * (S + 44) + 30), (16, 16, 20)); d = ImageDraw.Draw(im)
    d.text((10, 8), 'M4 faithful HD pack - original (nearest x2) | HD 2x, same spot. PASS = in the pack; REMAKE = original stays, listed for M4b',
           fill=(235, 235, 235))
    for i, (v, k) in enumerate(rows):
        r, s = recs[k], sel[k]
        o = np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGB'))
        hd = np.asarray(Image.open(os.path.join(F.FULL, r['hd_png'])).convert('RGB'))
        if s['cls'] == 'normal': o, hd = H._lit(o), H._lit(hd)
        gr = o.astype(float).mean(-1); gr = np.abs(np.diff(gr, axis=0))[:, :-1] + np.abs(np.diff(gr, axis=1))[:-1, :]
        nn = min(n, *gr.shape)
        _, x, y = max(((gr[yy:yy + nn, xx:xx + nn].sum(), xx, yy) for yy in range(0, max(1, gr.shape[0] - nn), 16)
                       for xx in range(0, max(1, gr.shape[1] - nn), 16)))
        a = Image.fromarray(np.ascontiguousarray(o[y:y + nn, x:x + nn])).resize((S, S), Image.NEAREST)
        b = Image.fromarray(np.ascontiguousarray(hd[2 * y:2 * y + 2 * nn, 2 * x:2 * x + 2 * nn])).resize((S, S), Image.LANCZOS)
        X = 10 + (i % 2) * (W + 10); Y = 30 + (i // 2) * (S + 44)
        im.paste(a, (X, Y + 30)); im.paste(b, (X + S + 10, Y + 30))
        why = verd[str(k)]['why'][0].replace('eye: ', '')
        d.text((X, Y + 2), '%s  %05d %s %dx%d' % (v, k, r['object_path'].split('.')[-1][:44], *s['size']),
               fill=(120, 230, 140) if v == 'PASS' else (255, 150, 120))
        d.text((X, Y + 16), why[:96], fill=(180, 180, 180))
    out = os.path.join(F.FULL, 'before_after_M4.png'); im.save(out, optimize=True); print(out, len(rows), 'examples')

if __name__ == '__main__':
    {'gain': gain, 'showcase': showcase}.get(sys.argv[1] if len(sys.argv) > 1 else '', main)()
