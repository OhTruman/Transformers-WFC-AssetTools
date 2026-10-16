"""M6 Modern materials: roughness maps for Systems' worklist (Rebuild-Systems/docs/handoff/SYSTEMS_M6_WORKLIST.json).

Per row (the texture feeding the material's SpecularPower, else SpecularColor, else DiffuseColor):
  gloss   = the artists' gloss signal from that texture, at HD (the frozen D pack's version when packed, else the original
            upscaled): TEXSET *_Masks_NormY -> G; *SpecPwr*_EnrGlow / *_AuxGlow -> R; weapon *_MASK -> G (Systems'
            WEP_PhongMain table: G = reflection / gloss); *_SPEC / colour -> luminance
  rough   = 1 - gloss, for diffuse-colour parents (no gloss data) only weakly (strength 0.3) around a flat value
  target  = an affine remap so the map's mean equals the row's target_mean_roughness (Systems: sqrt(2/(SpecularPower+2)) of the
            materials using it); the relative variation of the artists' gloss is kept, clipped to [0.03, 1]
  output  = BC4_UNORM (linear), half the HD colour resolution, DX10 header; pack/hd_pbr_index.json sibling rows
            {key, tex, role, dds, format, space, srgb, bytes, from} (Rendering resolves by (tex, role); hd_index.json untouched)
ORM (metal) rows are held: Systems decides the 18 orm_candidate rows after the family review. PROVISIONAL until the family review
sheets (sheets) are signed off.

  python hd_m6.py gen [root]     generate + encode into <root>/pack (default out/hd/push_m6), resumable; exits 75 on PERF_HOLD
  python hd_m6.py sheets [root]  review sheets (D colour | gloss source | roughness), 8 rows per sheet
"""
import glob, json, os, subprocess, sys, time
from collections import OrderedDict as OD
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
AT = os.path.dirname(os.path.dirname(HERE)); REB = os.path.dirname(AT)
WORKLIST = os.path.join(REB, 'Rebuild-Systems', 'docs', 'handoff', 'SYSTEMS_M6_WORKLIST.json')
D_SNAP = os.path.join(AT, 'out', 'hd', 'push_full_snap_20261016_b0-31', 'pack')
DDS_INDEX = os.path.join(AT, 'manifests', 'extracted', 'textures_dds.jsonl')
TEXCONV = os.path.join(AT, 'bin', 'texconv', 'texconv.exe')
GEN = 'AssetTools hd_m6.py v1 (gloss channel remap to the Systems target mean)'

def hold():
    h = glob.glob(os.path.join(REB, '*', 'work', 'PERF_HOLD'))
    if h: print('PERF_HOLD present: stopping', h, flush=True); sys.exit(75)

def source(tex):
    """(channel or 'luma', strength) for the gloss signal of a parent texture"""
    n = tex.rsplit('.', 1)[-1].lower()
    if n.endswith('_masks_normy'): return 1, 1.0
    if 'specpwr' in n or n.endswith('_enrglow') or n.endswith('_auxglow'): return 0, 1.0
    if n.endswith('_mask'): return 1, 1.0
    if 'spec' in n: return 'luma', 1.0
    return 'luma', 0.3                                  # diffuse fallback: no gloss data, weak variation only

def load_rgba(tex, dpack, orig):
    d = dpack.get(tex.lower())
    if d: return np.asarray(Image.open(os.path.join(D_SNAP, d['dds'])).convert('RGBA')), 'D pack (%s)' % d['level']
    o = orig[tex.lower()]
    im = Image.open(os.path.join(AT, 'out', 'dds', o['dds'])).convert('RGBA')
    return np.asarray(im.resize((im.width * 4, im.height * 4), Image.BICUBIC)), 'original x4 bicubic'

def roughness(rgba, tex, target):
    ch, k = source(tex)
    a = rgba.astype(np.float32) / 255
    g = (a[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)) if ch == 'luma' else a[..., ch]
    r = 1 - g
    r = r.mean() + k * (r - r.mean())                    # diffuse parents: damped variation
    m, s = float(r.mean()), float(r.std())
    out = r - m + target                                  # mean -> Systems target, variation kept
    for _ in range(4):                                    # re-centre after clipping
        out = np.clip(out, 0.03, 1.0); out = out + (target - out.mean())
    return np.clip(out, 0.03, 1.0), ch, k

def encode_bc4(img01, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    src = dst[:-4] + '.tmp.png'
    Image.fromarray(np.clip(np.round(img01 * 255), 0, 255).astype(np.uint8), 'L').save(src)
    p = subprocess.run([TEXCONV, '-nologo', '-y', '-nogpu', '-dx10', '-m', '0', '-f', 'BC4_UNORM', '-o', os.path.dirname(dst), src],
                       capture_output=True, text=True, errors='replace')
    out = src[:-4] + '.dds'
    os.remove(src)
    if p.returncode != 0 or not os.path.exists(out): raise RuntimeError('texconv: ' + p.stdout[-300:])
    os.replace(out, dst); return os.path.getsize(dst)

def gen(root):
    w = json.load(open(WORKLIST, encoding='utf-8'))
    dpack = {r['object_path'].lower(): r for r in json.load(open(os.path.join(D_SNAP, 'hd_index.json'), encoding='utf-8'))['rows']}
    orig = {json.loads(l)['object_path'].lower(): json.loads(l) for l in open(DDS_INDEX, encoding='utf-8')}
    pack = os.path.join(root, 'pack'); res = os.path.join(root, 'results'); os.makedirs(res, exist_ok=True)
    for i, row in enumerate(w['rows']):
        rp = os.path.join(res, '%04d.json' % i)
        if os.path.exists(rp): continue
        hold(); t0 = time.time()
        rgba, src = load_rgba(row['tex'], dpack, orig)
        H, W = rgba.shape[:2]
        half = np.asarray(Image.fromarray(rgba).resize((max(4, W // 2), max(4, H // 2)), Image.BOX))
        rough, ch, k = roughness(half, row['tex'], float(row['target_mean_roughness']))
        rel = row['tex'].replace('.', '/') + '_ROUGH.dds'
        nb = encode_bc4(rough, os.path.join(pack, 'm6', rel))
        rec = OD([('key', row['tex'].lower() + '#roughness'), ('tex', row['tex']), ('role', 'roughness'), ('dds', 'm6/' + rel),
                  ('format', 'BC4'), ('space', 'linear'), ('srgb', False), ('bytes', nb), ('size', [rough.shape[1], rough.shape[0]]),
                  ('from', GEN), ('gloss_source', '%s (%s), channel %s, strength %.1f' % (src, row['tex'].rsplit('.', 1)[-1], ch, k)),
                  ('target_mean', round(float(row['target_mean_roughness']), 4)), ('mean', round(float(rough.mean()), 4)),
                  ('std', round(float(rough.std()), 4)), ('orm_candidate', bool(row.get('orm_candidate_materials')))])
        json.dump(rec, open(rp + '.tmp', 'w', encoding='utf-8'), indent=1); os.replace(rp + '.tmp', rp)
        print('m6', i, row['tex'].rsplit('.', 1)[-1], rec['size'], 'mean %.3f -> %.3f' % (rec['mean'], rec['target_mean']), '%.1fs' % (time.time() - t0), flush=True)
    rows = [json.load(open(p, encoding='utf-8')) for p in sorted(glob.glob(os.path.join(res, '*.json')))]
    idx = OD([('version', 1), ('generator', GEN), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('note', 'M6 roughness siblings (BC4 linear), PROVISIONAL until the family review; ORM held'),
              ('rows', [OD((k, r[k]) for k in ('key', 'tex', 'role', 'dds', 'format', 'space', 'srgb', 'bytes', 'from')) for r in rows])])
    json.dump(idx, open(os.path.join(pack, 'hd_pbr_index.json'), 'w', encoding='utf-8'), indent=1)
    print(len(rows), 'roughness rows', round(sum(r['bytes'] for r in rows) / 2 ** 20, 1), 'MB', flush=True)

def sheets(root):
    res = sorted(glob.glob(os.path.join(root, 'results', '*.json'))); out = os.path.join(root, 'sheets'); os.makedirs(out, exist_ok=True)
    dpack = {r['object_path'].lower(): r for r in json.load(open(os.path.join(D_SNAP, 'hd_index.json'), encoding='utf-8'))['rows']}
    orig = {json.loads(l)['object_path'].lower(): json.loads(l) for l in open(DDS_INDEX, encoding='utf-8')}
    S = 300
    for s in range(0, len(res), 8):
        rows = []
        for p in res[s:s + 8]:
            r = json.load(open(p, encoding='utf-8'))
            rgba, _ = load_rgba(r['tex'], dpack, orig)
            rough = np.asarray(Image.open(os.path.join(root, 'pack', r['dds'])).convert('L'))
            im = Image.new('RGB', (3 * (S + 6), S + 20), (16, 16, 20)); dr = ImageDraw.Draw(im)
            dr.text((3, 3), '%s  mean %.3f (target %.3f) std %.3f  %s' % (r['tex'].rsplit('.', 1)[-1][:60], r['mean'], r['target_mean'], r['std'],
                                                                     'ORM-candidate' if r['orm_candidate'] else ''), fill=(230, 230, 230))
            im.paste(Image.fromarray(rgba[..., :3]).resize((S, S)), (0, 20))
            im.paste(Image.fromarray(rgba[..., 3]).convert('RGB').resize((S, S)) if False else Image.fromarray(rgba[..., :3]).convert('L').convert('RGB').resize((S, S)), (S + 6, 20))
            im.paste(Image.fromarray(rough).convert('RGB').resize((S, S)), (2 * (S + 6), 20))
            rows.append(im)
        sh = Image.new('RGB', (rows[0].width, sum(i.height for i in rows)), (16, 16, 20)); y = 0
        for i in rows: sh.paste(i, (0, y)); y += i.height
        sh.save(os.path.join(out, 'm6_%03d.png' % (s // 8 + 1)))
    print(len(res), 'rows', (len(res) + 7) // 8, 'sheets', flush=True)

if __name__ == '__main__':
    a = sys.argv[1] if len(sys.argv) > 1 else 'gen'
    root = sys.argv[2] if len(sys.argv) > 2 else os.path.join(AT, 'out', 'hd', 'push_m6')
    {'gen': gen, 'sheets': sheets}[a](root)
