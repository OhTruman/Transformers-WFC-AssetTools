"""Level E, generative route (docs/HD_BEYOND_D_PLAN.md; user 2026-10-12 "it can go beyond faithful ... realistic and new").

Stable Diffusion 1.5 + ControlNet tile (CreativeML OpenRAIL-M; manifests/hd/e_models.json) img2img on the reviewed D texture, on
DirectML: the D texture is cut into overlapping 512 px tiles (wrap-padded, so the texture still tiles), each tile is re-drawn at a
low / medium denoise with the D tile itself as the tile-ControlNet condition and a short material prompt, the tiles are feathered
back together, and then the same locks as the synthesis route apply (hd_e_pilot.py):
  - exact two-step back-projection to D's own colour at the ORIGINAL resolution (palette, layout, shapes stay the artist's),
  - D kept in the tint (Masks B) / emissive (Masks R) regions plus a rim,
  - gates at the original resolution (hd_e_pilot.gates), eye review 100 %.
Only detail finer than one original pixel can come from the model.

  python hd_e_gen.py probe                 load the pipeline on DML, one 512 tile, time + peak memory
  python hd_e_gen.py ladder                out/hd/push_e_gen/ladder/<i>.png: orig | D | G1 | G2 | G3 (+ gates.json)
  python hd_e_gen.py pack [G1|G2|G3]       out/hd/push_e_gen/pack (+ hd_index.json), a separate root for WFC_HD_ROOT

Waits for Integration's go (GPU / heavy job); stops with exit 75 on PERF_HOLD / low free commit between tiles.
"""
import json, os, sys, time
from collections import OrderedDict as OD
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('WFC_HD_PUSH_SET', 'full')
import hd_e_pilot as EP  # noqa: E402
import hd_push as P  # noqa: E402

AT = EP.AT
MODELS = os.path.join(AT, 'work', 'models')
G_ROOT = os.path.join(AT, 'out', 'hd', 'push_e_gen')
DENOISE = OD([('G1', 0.25), ('G2', 0.40), ('G3', 0.55)])
TILE, OV, STEPS, CFG, CN_SCALE = 512, 64, 20, 5.0, 0.9
NEG = 'text, letters, logo, watermark, people, face, cartoon, painting, illustration, blurry, lowres, jpeg artifacts, oversaturated'
CLASSES = [  # (name keywords, material prompt): first match wins
    (('floor', 'grate', 'tracks', 'rail'), 'worn industrial metal floor plates, scuffs, scratches, grime in seams, chipped paint'),
    (('wall', 'arch', 'panel', 'sign', 'deco'), 'weathered sci-fi metal wall panels, fine scratches, dust, grime, small dents'),
    (('rock', 'stone', 'canyon', 'cliff'), 'rough weathered stone surface, fine cracks, grit, dust'),
    (('glass', 'sheild', 'shield'), 'scratched transparent panel, fine smudges'),
    (('rust', 'stain'), 'rusted corroded metal, flaking paint, pitting, streaks'),
]
DEFAULT = 'worn painted sci-fi machinery metal, fine scratches, grime, chipped paint, small dents'

def prompt(png):
    n = png.lower()
    m = next((p for ks, p in CLASSES if any(k in n for k in ks)), DEFAULT)
    return m + ', realistic photographic texture, high detail, sharp, even lighting'

_pipe = None
def pipe():
    global _pipe
    if _pipe is None:
        import torch, torch_directml
        from diffusers import ControlNetModel, StableDiffusionControlNetImg2ImgPipeline, DPMSolverMultistepScheduler
        dev = torch_directml.device()
        cn = ControlNetModel.from_pretrained(os.path.join(MODELS, 'controlnet_tile_sd15'), torch_dtype=torch.float16)
        p = StableDiffusionControlNetImg2ImgPipeline.from_pretrained(os.path.join(MODELS, 'sd15'), controlnet=cn, variant='fp16',
                                                                    torch_dtype=torch.float16, safety_checker=None,
                                                                    requires_safety_checker=False)
        p.scheduler = DPMSolverMultistepScheduler.from_config(p.scheduler.config)
        p.set_progress_bar_config(disable=True)
        _pipe = (p.to(dev), dev)
    return _pipe

def gen_tile(rgb_u8, txt, strength, seed):
    import torch
    p, dev = pipe(); im = Image.fromarray(rgb_u8)
    g = torch.Generator().manual_seed(seed)
    out = p(prompt=txt, negative_prompt=NEG, image=im, control_image=im, strength=strength, num_inference_steps=STEPS,
            guidance_scale=CFG, controlnet_conditioning_scale=CN_SCALE, generator=g, output_type='np').images[0]
    return (np.clip(out, 0, 1) * 255).astype(np.float32)

def regenerate(rgb, txt, strength, seed):
    """whole texture: wrap-pad, overlapping tiles, feathered blend, crop back (keeps the texture tileable)"""
    Hh, W = rgb.shape[:2]; pad = OV
    src = np.pad(rgb, ((pad, pad), (pad, pad), (0, 0)), mode='wrap').astype(np.uint8)
    H2, W2 = src.shape[:2]; acc = np.zeros((H2, W2, 3), np.float32); wsum = np.zeros((H2, W2, 1), np.float32)
    t = min(TILE, H2, W2); step = t - OV
    ramp = np.minimum(np.arange(t) + 1, np.arange(t)[::-1] + 1).astype(np.float32); ramp = np.minimum(ramp / OV, 1)
    wt = (ramp[:, None] * ramp[None, :])[..., None]
    ys = list(range(0, max(1, H2 - t), step)) + [H2 - t]; xs = list(range(0, max(1, W2 - t), step)) + [W2 - t]
    for k, y in enumerate(sorted(set(ys))):
        for x in sorted(set(xs)):
            EP.stop()
            acc[y:y + t, x:x + t] += gen_tile(src[y:y + t, x:x + t], txt, strength, seed + 7919 * k + x) * wt
            wsum[y:y + t, x:x + t] += wt
    return (acc / np.maximum(wsum, 1e-6))[pad:pad + Hh, pad:pad + W]

def cached(i, level, fn):
    """checkpoint each regenerated texture (before the lock) so a stop / driver reset resumes at the next unit / strength"""
    p = os.path.join(G_ROOT, 'raw', '%05d_%s.png' % (i, level))
    if os.path.exists(p): return np.asarray(Image.open(p)).astype(np.float32)
    g = fn(); os.makedirs(os.path.dirname(p), exist_ok=True)
    Image.fromarray(np.clip(np.round(g), 0, 255).astype(np.uint8)).save(p + '.tmp.png'); os.replace(p + '.tmp.png', p)
    return g

def lock(G, D, o, prot):
    """exact two-step lock to D's colour at the original resolution, then D in protected regions"""
    Hh, W = D.shape[:2]; oh, ow = o.shape[:2]; rgb = G.copy()
    for _ in range(2):
        corr = EP.area(D[..., :3], ow, oh) - EP.area(np.clip(rgb, 0, 255).astype(np.float32), ow, oh)
        rgb = rgb + EP.up(corr.astype(np.float32), W, Hh)
    if prot is not None: rgb = rgb * (1 - prot[..., None]) + D[..., :3] * prot[..., None]
    return np.clip(rgb, 0, 255)

def vram_gb():
    """this process's dedicated GPU memory (Windows 'GPU Process Memory' counter; DML has no allocator stats)"""
    import subprocess
    c = ("(Get-Counter '\\GPU Process Memory(pid_%d*)\\Dedicated Usage').CounterSamples | Measure-Object CookedValue -Sum"
         " | ForEach-Object { $_.Sum }" % os.getpid())
    try: return float(subprocess.run(['powershell', '-NoProfile', '-Command', c], capture_output=True, text=True).stdout.strip()) / 2 ** 30
    except Exception: return float('nan')

def probe():
    import psutil, threading
    peak = [0.0]; done = threading.Event()
    def watch():
        while not done.is_set(): peak[0] = max(peak[0], vram_gb()); time.sleep(2)
    threading.Thread(target=watch, daemon=True).start()
    t0 = time.time(); pipe(); t1 = time.time()
    x = (np.random.default_rng(0).random((TILE, TILE, 3)) * 255).astype(np.uint8)
    gen_tile(x, DEFAULT, 0.4, 0); t2 = time.time()
    ts = []
    for k in range(3):                                   # warm tiles (the first includes DML kernel compilation)
        a = time.time(); gen_tile(x, DEFAULT, 0.4, k + 1); ts.append(time.time() - a)
    done.set(); peak[0] = max(peak[0], vram_gb())
    print('load %.0fs, first %d tile %.1fs, warm tiles %s s, peak VRAM %.1f GB, rss %.1f GB, free commit %.1f GB' % (
        t1 - t0, TILE, t2 - t1, ' / '.join('%.1f' % t for t in ts), peak[0], psutil.Process().memory_info().rss / 2 ** 30,
        P.free_commit_gb()), flush=True)

def ladder():
    us, R = EP.units(); out = os.path.join(G_ROOT, 'ladder'); os.makedirs(out, exist_ok=True); S = 240
    gp = os.path.join(G_ROOT, 'gates.json'); rep = json.load(open(gp, encoding='utf-8')) if os.path.exists(gp) else {}
    for r, d, m, md in us:
        p = os.path.join(out, '%05d.png' % r['i'])
        if os.path.exists(p): continue
        EP.stop(); t0 = time.time()
        o = P.orig(r); D = EP.load_d(d); f = D.shape[1] / o.shape[1]
        M = EP.load_d(md) if md else None; pr = EP.protect_mask(M, (D.shape[1], D.shape[0]), f); txt = prompt(r['png'])
        Gs = OD((k, lock(cached(r['i'], k, lambda s=s: regenerate(D[..., :3], txt, s, r['i'])), D, o, pr)) for k, s in DENOISE.items())
        rep[r['png']] = OD((k, EP.gates(D, g, o, M)) for k, g in Gs.items())
        for k in rep[r['png']]: rep[r['png']][k]['from'] = 'sd15+controlnet_tile denoise %.2f steps %d cfg %.1f seed %d prompt "%s"' % (
            DENOISE[k], STEPS, CFG, r['i'], txt)
        n, busy, flat = EP.spots(o); im = Image.new('RGB', (5 * (S + 6), 2 * S + 36), (16, 16, 20)); dr = ImageDraw.Draw(im)
        dr.text((3, 2), '%05d %s  orig | D | G1 | G2 | G3  (busiest, flattest)' % (r['i'], r['png'][-80:]), fill=(230, 230, 230))
        for row, (x, y) in enumerate((busy, flat)):
            yy = 18 + row * (S + 18)
            im.paste(Image.fromarray(np.ascontiguousarray(o[y:y + n, x:x + n, :3])).resize((S, S), Image.NEAREST), (0, yy))
            for c, img in enumerate([D[..., :3]] + list(Gs.values()), 1):
                cr = np.clip(np.round(img), 0, 255).astype(np.uint8)[int(f * y):int(f * (y + n)), int(f * x):int(f * (x + n))]
                im.paste(Image.fromarray(np.ascontiguousarray(cr)).resize((S, S), Image.LANCZOS), (c * (S + 6), yy))
        im.save(p); json.dump(rep, open(gp, 'w', encoding='utf-8'), indent=1)
        print('ladder', r['i'], '%.0fs' % (time.time() - t0), {k: v['pass'] for k, v in rep[r['png']].items()}, flush=True)
    print('ladder done', flush=True)

def pack(level='G2'):
    s = DENOISE[level]; us, R = EP.units(); root = os.path.join(G_ROOT, 'pack'); rows = []
    for r, d, m, md in us:
        EP.stop(); o = P.orig(r); D = EP.load_d(d); f = D.shape[1] / o.shape[1]
        M0 = EP.load_d(md) if md else None; pr = EP.protect_mask(M0, (D.shape[1], D.shape[0]), f)
        G = lock(cached(r['i'], level, lambda: regenerate(D[..., :3], prompt(r['png']), s, r['i'])), D, o, pr); E = D.copy(); E[..., :3] = G
        hgt = EP.height(G.astype(np.uint8), os.path.join(G_ROOT, 'height', '%05d.png' % r['i']))   # relief from the E colour
        hp = hgt - P.gblur(hgt[..., None], 2 * f)[..., 0]
        if r['kind'] == 'texset_color': E[..., 3] = EP.relief(D[..., 3], hp, 0, 1.0, (D.shape[1], D.shape[0]))
        todo = [(r, d, E)]
        if m is not None and md is not None:
            M = EP.load_d(md); M[..., 3] = EP.relief(M[..., 3], hp, 1, 1.0, (M.shape[1], M.shape[0])); todo.append((m, md, M))
        for rr, dd, img in todo:
            dst = P.encode(np.clip(np.round(img), 0, 255).astype(np.uint8), rr, root)
            tmp = os.path.join(P.OUT, '_enc', 'pack', '%03d.png' % rr['i'])
            if os.path.exists(tmp): os.remove(tmp)
            rows.append(OD([('key', dd['key']), ('object_path', dd['object_path']), ('dds', dd['dds']), ('format', dd['format']),
                            ('size', dd['size']), ('bytes', os.path.getsize(dst)), ('level', 'e_' + level.lower()), ('d_level', dd['level']),
                            ('from', 'sd15+controlnet_tile denoise %.2f seed %d' % (s, r['i']))]))
        print('pack', r['i'], level, flush=True)
    json.dump(OD([('version', 1), ('generator', 'scripts/wfc/hd_e_gen.py pack %s' % level), ('generated', time.strftime('%Y-%m-%d %H:%M')),
                  ('note', 'E generative pilot (Rust); not for install'), ('rows', rows)]),
              open(os.path.join(root, 'hd_index.json'), 'w', encoding='utf-8'), indent=1)
    print(len(rows), 'rows', round(sum(x['bytes'] for x in rows) / 2 ** 20, 1), 'MB', flush=True)

if __name__ == '__main__':
    a = sys.argv[1] if len(sys.argv) > 1 else 'probe'
    if a == 'probe': probe()
    elif a == 'ladder': ladder()
    elif a == 'pack': pack(sys.argv[2] if len(sys.argv) > 2 else 'G2')
