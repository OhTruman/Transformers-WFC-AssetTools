"""Optional faithful 2x HD texture pack - full run with the v5 method (user 2026-10-09; budget approved by Integration):
  every texture   RealPLKSR (4x-PBRify-RPLKSRd-V3) + Real-ESRGAN animevideov3 x2 (ncnn) + Lanczos, then the v5 per-tile ensemble
  normals         + 4x-Normal-RG0-BC1
  char / weapon   + 4x-PBRify-UpscalerDAT2-V1 on colour (most-seen surfaces)
  data maps       RealPLKSR + Lanczos per channel; exact masks (CustAB / AuxGlow / alpha-as-data) stay exact (classed data)
All under AssetTools/out/hd/full (work) and AssetTools/out/hd/pack (DDS in the original block formats + hd_index.json for
Rendering's loader; REMAKE textures are left out of the index so the original stays in use). Every stage is resumable.

  python hd_full.py prep                 CPU: deblocked source -> channel inputs (in/, in_normal/, in_dat/) + selection.json
  python hd_full.py gpu [--models ...]   GPU: ncnn animevideov3, then hd_torch (RealPLKSR / normals / DAT2), resumable per file
  python hd_full.py post [--resume]      CPU: lock + gate + tone + v5 ensemble + encode; per-texture records in _partial.jsonl
  python hd_full.py sheets               CPU: per-class review sheets (original | HD at the most detailed spot) for the eye verdict
  python hd_full.py index                hd_index.json + CREDITS.txt from the PASS records (verdicts in verdicts.json)
"""
import json, os, shutil, subprocess, sys, time
from collections import OrderedDict as OD, Counter
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if '--v2' not in sys.argv: sys.argv.append('--v2')
import hd_pilot as H  # noqa: E402
import hd_v4 as V4  # noqa: E402
V3 = V4.V3
AT = H.AT
FULL = os.path.join(H.HD, 'full'); PACK = os.path.join(H.HD, 'pack')
H.WORK = FULL; H.SEL = os.path.join(FULL, 'selection.json'); H.OUTV = PACK
RPLKSR, DAT2, NCNN = '4x-PBRify-RPLKSRd-V3', '4x-PBRify-UpscalerDAT2-V1', 'animevideov3_x2'
MOST_SEEN = ('TEXTUREGROUP_Character', 'TEXTUREGROUP_Weapon')

def eligible():
    return [r for r in H.load_rows() if r['status'] == 'ok' and r['cls'] != 'excluded' and r['format'] != 'PF_G8' and min(r['size']) >= 4]

def prep():
    for d in ('in', 'in_normal', 'in_dat'): os.makedirs(os.path.join(FULL, d), exist_ok=True)
    old = {s['object_path']: s for s in json.load(open(H.SEL, encoding='utf-8'))} if os.path.exists(H.SEL) else {}
    sel = []; t0 = time.time()
    for k, r in enumerate(sorted(eligible(), key=lambda r: r['object_path'])):
        if r['object_path'] in old and all(os.path.exists(os.path.join(FULL, 'in', n)) for n in old[r['object_path']]['inputs']):
            sel.append(old[r['object_path']]); continue
        img = np.asarray(Image.open(os.path.join(H.DDS, r['dds'])).convert('RGBA'))
        if r['cls'] == 'normal':
            v = img[..., :3].astype(np.float64) / 255 * 2 - 1
            if float(np.abs(np.linalg.norm(v, axis=-1) - 1).mean()) > 0.08: r['cls'] = 'data'
        img = H.source(r); jobs = []
        if r['cls'] == 'data':
            for ci, ch in enumerate('RGB'): g = img[..., ci]; jobs.append(('ch' + ch, np.stack([g, g, g], -1)))
        else:
            jobs.append(('rgb', img[..., :3]))
        if r['alpha_read'] or (r['cls'] == 'data' and r['format'] == 'PF_DXT5'):
            a = img[..., 3]; jobs.append(('chA', np.stack([a, a, a], -1)))
        names = []
        for tag, arr in jobs:
            nm = '%05d_%s.png' % (k, tag); Image.fromarray(np.ascontiguousarray(arr), 'RGB').save(os.path.join(FULL, 'in', nm)); names.append(nm)
            if r['cls'] == 'normal' and tag == 'rgb':
                b = arr.copy(); b[..., 2] = 0; Image.fromarray(b).save(os.path.join(FULL, 'in_normal', nm))     # RG0 convention
            if r['cls'] == 'colour' and r.get('lod_group') in MOST_SEEN:
                shutil.copy(os.path.join(FULL, 'in', nm), os.path.join(FULL, 'in_dat', nm))
        sel.append(OD([('k', k), ('object_path', r['object_path']), ('dds', r['dds']), ('png', r.get('png')), ('cls', r['cls']),
                       ('lod_group', r.get('lod_group')), ('format', r['format']), ('size', r['size']), ('srgb', r.get('srgb')),
                       ('alpha_read', r['alpha_read']), ('inputs', names), ('height_range', None)]))
        if k % 250 == 0:
            json.dump(sel, open(H.SEL, 'w', encoding='utf-8'), indent=0); print(k, '%.0fs' % (time.time() - t0), flush=True)
    json.dump(sel, open(H.SEL, 'w', encoding='utf-8'), indent=0)
    print('selection', len(sel), Counter(s['cls'] for s in sel), 'inputs', sum(len(s['inputs']) for s in sel),
          'dat subset', len(os.listdir(os.path.join(FULL, 'in_dat'))), 'normals', len(os.listdir(os.path.join(FULL, 'in_normal'))))

def gpu():
    py = sys.executable; ht = os.path.join(HERE, 'hd_torch.py')
    names = sys.argv[sys.argv.index('--models') + 1].split(',') if '--models' in sys.argv else ['ncnn', 'normal', 'rplksr', 'dat2']
    for m in names:             # fast first (Integration: fast models + normals first)
        t0 = time.time()
        if m == 'ncnn':
            od = os.path.join(FULL, 'out_' + NCNN); os.makedirs(od, exist_ok=True)
            # ncnn has no per-file resume: run only the inputs without an output, via a staging folder
            todo = [f for f in os.listdir(os.path.join(FULL, 'in')) if not os.path.exists(os.path.join(od, f))]
            stage = os.path.join(FULL, '_ncnn_in'); shutil.rmtree(stage, ignore_errors=True); os.makedirs(stage)
            for f in todo: shutil.copy(os.path.join(FULL, 'in', f), os.path.join(stage, f))
            if todo: subprocess.run([H.ESR, '-i', stage, '-o', od, '-n', 'realesr-animevideov3', '-s', '2', '-f', 'png'], capture_output=True)
            shutil.rmtree(stage, ignore_errors=True)
        elif m == 'normal':
            subprocess.run([py, ht, 'run', '--work', FULL, '--in', os.path.join(FULL, 'in_normal'), '--models', V3.NORMAL, '--save-scale', '2'])
        elif m == 'rplksr':
            # colour + normal inputs only (Integration 2026-10-10: data / mask maps keep animevideov3 + Lanczos; halves the GPU time)
            cn = os.path.join(FULL, 'in_cn'); os.makedirs(cn, exist_ok=True)
            for s in json.load(open(H.SEL, encoding='utf-8')):
                if s['cls'] in ('colour', 'normal'):
                    for n in s['inputs']:
                        if not os.path.exists(os.path.join(cn, n)): shutil.copy(os.path.join(FULL, 'in', n), os.path.join(cn, n))
            subprocess.run([py, ht, 'run', '--work', FULL, '--in', cn, '--models', RPLKSR, '--save-scale', '2'])
        elif m == 'dat2':
            subprocess.run([py, ht, 'run', '--work', FULL, '--in', os.path.join(FULL, 'in_dat'), '--models', DAT2, '--save-scale', '2'])
        print(m, '%.0fs' % (time.time() - t0), flush=True)

def candidates(s):
    names = ['ncnn:' + NCNN] + ([RPLKSR] if s['cls'] in ('colour', 'normal') else [])
    if s['cls'] == 'normal': names.append(V3.NORMAL)
    if s['cls'] == 'colour' and s.get('lod_group') in MOST_SEEN: names.append(DAT2)
    return names

def cand_img(s, c):
    if c.startswith('ncnn:'):
        try: return H.rebuild(s, c[5:])
        except Exception: return None
    try: return V3.normal_rg0(s, 2) if c == V3.NORMAL else V3.assemble(s, c, 2)
    except Exception: return None                                       # output missing (failed / skipped in the GPU run)

def post():
    sel = json.load(open(H.SEL, encoding='utf-8')); os.makedirs(PACK, exist_ok=True)
    # --shard i/N: this worker takes textures with k % N == i and appends to its own _partial_s<i>.jsonl (parallel CPU workers)
    shard = tuple(int(x) for x in sys.argv[sys.argv.index('--shard') + 1].split('/')) if '--shard' in sys.argv else None
    if shard: sel = [x for x in sel if x['k'] % shard[1] == shard[0]]
    part = os.path.join(FULL, '_partial_s%d.jsonl' % shard[0] if shard else '_partial.jsonl'); done = set()
    # --redo k,k,...: rerun these textures after a post fix; newer records (field 't') supersede the old ones in load_recs()
    redo = set(int(x) for x in sys.argv[sys.argv.index('--redo') + 1].split(',')) if '--redo' in sys.argv else None
    if redo is not None:
        sel = [x for x in sel if x['k'] in redo]; part = os.path.join(FULL, '_partial_redo.jsonl')
        import glob                                                         # H.encode reuses enc/<k>_*.png: drop it so the DDS is rebuilt
        for x in sel:
            for f in glob.glob(os.path.join(FULL, 'enc', '%03d_*.png' % x['k'])): os.remove(f)
    elif '--resume' in sys.argv:
        for pf in partial_files():
            for l in open(pf, encoding='utf-8'):
                try:
                    r = json.loads(l)
                    if 'error' not in r: done.add(r['object_path'])        # failed textures are retried on --resume
                except Exception: pass
    elif os.path.exists(part):
        os.replace(part, part + '.bak')
    t0 = time.time(); n = 0
    for s in sel:
        if s['object_path'] in done: continue
        try: rec = post_one(s)
        except Exception as ex:                                             # one bad texture must not stop the run; it stays original
            rec = OD([('k', s['k']), ('object_path', s['object_path']), ('png', s.get('png')), ('cls', s['cls']), ('faithful', False),
                      ('error', '%s: %s' % (type(ex).__name__, str(ex)[:300])), ('t', time.time())]); print('FAIL', s['k'], str(ex)[:120], flush=True)
        with open(part, 'a', encoding='utf-8') as f: f.write(json.dumps(rec) + chr(10))
        n += 1
        if n % 100 == 0: print(n, 'textures', '%.0fs' % (time.time() - t0), flush=True)
    print('post done', n, 'new', '%.0fs' % (time.time() - t0))

def partial_files():
    import glob
    return sorted(glob.glob(os.path.join(FULL, '_partial*.jsonl')))   # _partial, _partial_s<i> (shards), _partial_redo

def load_recs():
    """the latest record per texture (a retried failure or a --redo appends a newer one: larger 't', or later in the file for
    records written before 't' existed); records that still failed are left out (the texture stays original) and counted"""
    last = OD()
    for pf in partial_files():
        for l in open(pf, encoding='utf-8'):
            try: r = json.loads(l)
            except Exception: continue
            if r.get('t', 0) < last.get(r['object_path'], {}).get('t', 0): continue
            last.pop(r['object_path'], None); last[r['object_path']] = r
    errs = [r for r in last.values() if 'error' in r]
    if errs: print(len(errs), 'textures failed in post (kept original):', ', '.join(str(r['k']) for r in errs[:20]))
    return [r for r in last.values() if 'error' not in r]

def post_one(s):
    if True:
        target = H.source(s); w, h = s['size']
        lz = np.asarray(Image.fromarray(target, 'RGBA').resize((2 * w, 2 * h), Image.LANCZOS))
        locked = OD([('lanczos', V3.lock(target, lz, s, 2))]); missing = []
        for c in candidates(s):
            raw = cand_img(s, c)
            if raw is None: missing.append(c); continue
            hd, g = V3.evaluate(target, raw, s, 2)
            if g['faithful']: locked[c] = hd
        fused, share = V4.fuse(target, locked, lz, s)
        hd = V3.lock(target, fused, s, 2)
        const = [c for c in range(4) if target[..., c].min() == target[..., c].max()]
        if const:                                                           # a channel constant in the original stays exactly constant
            hd = hd.copy(); hd[..., const] = target[0, 0, const]
        p, sh, _ = H.gate(target, hd, s); tone = V4.tone_check(target, hd, s)
        ok = bool(p >= H.FINAL_MIN_DB and sh <= H.FINAL_MAX_SHIFT and tone['ok'])
        rec = OD([('k', s['k']), ('object_path', s['object_path']), ('png', s.get('png')), ('cls', s['cls']), ('lod_group', s['lod_group']),
                  ('size', s['size']), ('format', s['format']), ('srgb', s.get('srgb')), ('candidates_missing', missing),
                  ('blend_share', share), ('final_psnr', round(p, 2)), ('max_mean_shift', round(sh, 3)), ('tone', tone), ('faithful', ok),
                  ('const_channels', const), ('t', time.time())])
        if ok:
            png = os.path.join(FULL, '_hdpng', '%05d.png' % s['k']); os.makedirs(os.path.dirname(png), exist_ok=True)
            Image.fromarray(hd, 'RGBA').save(png); rec['hd_png'] = os.path.relpath(png, FULL).replace(os.sep, '/')
            d = H.encode(hd, s, s['dds'], modern=False)
            rec['hd_dds'] = os.path.relpath(d, PACK).replace(os.sep, '/') if d else None; rec['hd_bytes'] = os.path.getsize(d) if d else None
        return rec

def sheets():
    """review sheets per class (and LOD group), 16 textures each: original | HD at the most detailed 64 px spot"""
    recs = load_recs()
    sel = {s['object_path']: s for s in json.load(open(H.SEL, encoding='utf-8'))}
    od = os.path.join(FULL, 'review'); os.makedirs(od, exist_ok=True)
    groups = OD()
    for r in recs:
        if r.get('hd_png'): groups.setdefault('%s_%s' % (r['cls'], (r.get('lod_group') or 'environment').replace('TEXTUREGROUP_', '')), []).append(r)
    n, C, cell = 64, 4, 200; made = 0
    for gname, rs in groups.items():
        for part in range(0, len(rs), 16):
            chunk = rs[part:part + 16]; rows = (len(chunk) + C - 1) // C
            sheet = Image.new('RGB', (C * (2 * cell + 20), rows * (cell + 22)), (16, 16, 20)); d = ImageDraw.Draw(sheet)
            for k, r in enumerate(chunk):
                s = sel[r['object_path']]; o = np.asarray(Image.open(os.path.join(H.DDS, s['dds'])).convert('RGB'))
                hd = np.asarray(Image.open(os.path.join(FULL, r['hd_png'])).convert('RGB'))
                if s['cls'] == 'normal': o, hd = H._lit(o), H._lit(hd)
                g = o.astype(float).mean(-1); g = np.abs(np.diff(g, axis=0))[:, :-1] + np.abs(np.diff(g, axis=1))[:-1, :]
                hh, ww = g.shape; nn = min(n, hh, ww)
                _, x, y = max(((g[yy:yy + nn, xx:xx + nn].sum(), xx, yy) for yy in range(0, max(1, hh - nn), 16) for xx in range(0, max(1, ww - nn), 16)))
                a = Image.fromarray(np.ascontiguousarray(o[y:y + nn, x:x + nn])).resize((cell, cell), Image.BILINEAR)
                b = Image.fromarray(np.ascontiguousarray(hd[2 * y:2 * y + 2 * nn, 2 * x:2 * x + 2 * nn])).resize((cell, cell), Image.BILINEAR)
                X = (k % C) * (2 * cell + 20); Y = (k // C) * (cell + 22)
                sheet.paste(a, (X, Y + 20)); sheet.paste(b, (X + cell + 4, Y + 20))
                d.text((X, Y + 4), '%05d %s' % (r['k'], r['object_path'].split('.')[-1][:34]), fill=(230, 230, 230))
            sheet.save(os.path.join(od, '%s_%03d.png' % (gname, part // 16))); made += 1
    print('sheets', made, 'in', od)

def index():
    """hd_index.json (Rendering's loader) from the faithful records whose verdict (verdicts.json from hd_verdicts.py: k -> PASS /
    REMAKE / KEEP + why) is PASS; REMAKE and gate failures -> remake_candidates.json; KEEP (must stay exact) is in neither, the
    original stays in use; CREDITS.txt for the models used"""
    import authored as A
    recs = load_recs()
    vp = os.path.join(FULL, 'verdicts.json'); verd = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    rows = []; remake = []; used = Counter(); total = 0; con = A.con()
    for r in recs:
        v = verd.get(str(r['k'])) or {'verdict': 'PENDING'}
        if r.get('hd_dds') and v['verdict'] == 'PASS':
            rows.append(OD([('key', (r.get('png') or '').lower()), ('object_path', r['object_path']), ('dds', r['hd_dds']), ('format', r['format']),
                            ('size', [2 * r['size'][0], 2 * r['size'][1]]), ('srgb', r.get('srgb')), ('class', r['cls']),
                            ('bytes', r['hd_bytes']), ('final_psnr', r['final_psnr']), ('max_mean_shift', r['max_mean_shift'])]))
            total += r['hd_bytes'] or 0
            used.update(k for k, x in r['blend_share'].items() if x > 0.01)
        elif v['verdict'] == 'REMAKE' or (not r.get('hd_dds') and v['verdict'] != 'KEEP'):
            uses = con.execute("SELECT COUNT(DISTINCT src) FROM refs WHERE dst = ?", (r['object_path'],)).fetchone()[0]
            remake.append(OD([('object_path', r['object_path']), ('class', r['cls']), ('lod_group', r['lod_group']), ('size', r['size']),
                              ('referencing_objects', uses), ('why', v.get('why') or (['no faithful upscale (gate)'] if not r.get('hd_dds') else [])),
                              ('source', 'hd_full')]))
    idx = OD([('version', 1), ('generator', 'AssetTools/scripts/wfc/hd_full.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('gate', 'back-projection lock to the deblocked original + tone check (native std / darkest 10 % / local contrast) + eye review'),
              ('textures', len(rows)), ('total_bytes', total),
              ('kept_original', sum(1 for r in recs if (verd.get(str(r['k'])) or {}).get('verdict') == 'KEEP')), ('rows', rows)])
    json.dump(idx, open(os.path.join(PACK, 'hd_index.json'), 'w', encoding='utf-8'), indent=1)
    json.dump(OD([('generated_by', 'AssetTools/scripts/wfc/hd_full.py index'), ('textures', remake)]),
              open(os.path.join(AT, 'manifests', 'hd', 'remake_candidates.json'), 'w', encoding='utf-8'), indent=1)
    import hd_torch as T
    T.credits([m for m in (RPLKSR, DAT2, V3.NORMAL) if used.get(m)])
    shutil.copy(os.path.join(H.HD, 'CREDITS.txt'), os.path.join(PACK, 'CREDITS.txt'))
    print('index', len(rows), 'PASS', '%.2f GB' % (total / 2 ** 30), '| remake', len(remake), '| pending', sum(1 for r in recs if str(r['k']) not in verd))

if __name__ == '__main__':
    {'prep': prep, 'gpu': gpu, 'post': post, 'sheets': sheets, 'index': index}[sys.argv[1]]()
