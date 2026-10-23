"""Stronger upscalers for the optional faithful HD pack (step B, user 2026-10-09 "push further first"): PyTorch + spandrel on the
AMD GPU through DirectML (CPU fallback), tiled. Models / licences / hashes: AssetTools/bin/hdmodels/models.json (OpenModelDB records,
redistributable licences only: CC0-1.0 / CC-BY-4.0). Inputs and outputs follow hd_pilot.py's work layout (channel PNGs), so
hd_pilot's back-projection lock, gate, encoders and comparison images apply unchanged.

  python hd_torch.py probe                       time each model on one small and one large input (GPU schedule estimate)
  python hd_torch.py run [--models a,b] [--in DIR] [--work DIR]   upscale every input PNG with each model -> <work>/out_<model>/
Environment: torch 2.4.1+cpu, torch-directml 0.2.5.dev240914, spandrel 0.4.2 (AssetTools/bin/py).
"""
import json, os, sys, time
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MODELS = json.load(open(os.path.join(AT, 'bin', 'hdmodels', 'models.json'), encoding='utf-8'))
TILE, PAD = int(os.environ.get("WFC_HD_TILE", "192")), 16   # WFC_HD_TILE: smaller tiles when VRAM is shared

def device():
    import torch
    if os.environ.get('WFC_HD_DEVICE') == 'cpu':      # e.g. a small rerun inside run_bounded's 6 GB cap (DML commit counts against it); unset = DML as before
        return torch.device('cpu'), 'cpu (WFC_HD_DEVICE)'
    try:
        import torch_directml
        return torch_directml.device(), 'directml:' + torch_directml.device_name(0).strip()
    except Exception as ex:
        return torch.device('cpu'), 'cpu (%s)' % str(ex)[:60]

def load(name, dev):
    import spandrel
    d = spandrel.ModelLoader().load_from_file(os.path.join(AT, MODELS[name]['file']))
    d.model.eval().to(dev)
    return d

def upscale(d, dev, img, check=None):
    """img HxWx3 uint8 -> (s*H)x(s*W)x3 uint8, tiled with PAD overlap (reflect padding at the border)"""
    import torch
    s = d.scale; h, w = img.shape[:2]
    x = torch.from_numpy(np.ascontiguousarray(img)).permute(2, 0, 1).float().div(255)[None]
    out = np.zeros((s * h, s * w, 3), np.float32)
    with torch.no_grad():
        for y0 in range(0, h, TILE):
            for x0 in range(0, w, TILE):
                if check is not None: check()                               # e.g. a PERF_HOLD set mid-texture (big CPU textures take minutes)
                ya, yb, xa, xb = max(0, y0 - PAD), min(h, y0 + TILE + PAD), max(0, x0 - PAD), min(w, x0 + TILE + PAD)
                t = x[..., ya:yb, xa:xb]
                ph, pw = (-t.shape[2]) % 8, (-t.shape[3]) % 8              # windowed transformers want multiples of 8
                ph, pw = max(ph, 16 - t.shape[2]), max(pw, 16 - t.shape[3])  # and >= 16 px per side (RGT: log(H // 16) on a 4 px strip)
                if ph or pw:                                                # reflect needs pad < size; tiny (4x4) inputs replicate
                    t = torch.nn.functional.pad(t, (0, pw, 0, ph), mode='reflect' if ph < t.shape[2] and pw < t.shape[3] else 'replicate')
                r = d.model(t.to(dev)).float().clamp(0, 1).cpu()[0].permute(1, 2, 0).numpy()
                r = r[:s * (yb - ya), :s * (xb - xa)]
                cy, cx = s * (y0 - ya), s * (x0 - xa); th, tw = s * (min(h, y0 + TILE) - y0), s * (min(w, x0 + TILE) - x0)
                out[s * y0:s * y0 + th, s * x0:s * x0 + tw] = r[cy:cy + th, cx:cx + tw]
    return np.clip(np.round(out * 255), 0, 255).astype(np.uint8)

def probe():
    dev, how = device(); print('device', how)
    src = os.path.join(AT, 'out', 'hd', '_work_v2', 'in')
    files = sorted(os.listdir(src), key=lambda f: Image.open(os.path.join(src, f)).size[0])
    small, large = files[0], files[-1]
    res = {}
    for m in MODELS:
        try:
            d = load(m, dev); r = {}
            for f in (small, large):
                im = np.asarray(Image.open(os.path.join(src, f)).convert('RGB')); t0 = time.time(); upscale(d, dev, im)
                r[f] = (im.shape[1], im.shape[0], round(time.time() - t0, 1))
            res[m] = r; print(m, r, flush=True)
        except Exception as ex:
            res[m] = {'error': str(ex)[:200]}; print(m, 'FAIL', str(ex)[:200], flush=True)
    json.dump({'device': how, 'probe': res}, open(os.path.join(AT, 'out', 'hd', 'torch_probe.json'), 'w'), indent=1)

def run():
    dev, how = device(); print('device', how)
    work = sys.argv[sys.argv.index('--work') + 1] if '--work' in sys.argv else os.path.join(AT, 'out', 'hd', '_work_v3')
    src = sys.argv[sys.argv.index('--in') + 1] if '--in' in sys.argv else os.path.join(work, 'in')
    names = sys.argv[sys.argv.index('--models') + 1].split(',') if '--models' in sys.argv else list(MODELS)
    # --save-scale 2: area-downsample the model output to 2x before saving (the pack is 2x; a 4x RealPLKSR output of the full
    # pack would be ~100 GB of PNG)
    save_scale = int(sys.argv[sys.argv.index('--save-scale') + 1]) if '--save-scale' in sys.argv else None
    times = {}
    for m in names:
        d = load(m, dev); od = os.path.join(work, 'out_' + m); os.makedirs(od, exist_ok=True); t0 = time.time(); fails = []
        for f in sorted(os.listdir(src)):
            if f.endswith('.png') and not os.path.exists(os.path.join(od, f)):
                try:                                                        # one bad input must not stop (and idle) the GPU run
                    im = Image.open(os.path.join(src, f)).convert('RGB'); out = Image.fromarray(upscale(d, dev, np.asarray(im)))
                    if save_scale and out.size != (save_scale * im.size[0], save_scale * im.size[1]):
                        out = out.resize((save_scale * im.size[0], save_scale * im.size[1]), Image.BOX)
                    tmp = os.path.join(od, f + '.part.png'); out.save(tmp); os.replace(tmp, os.path.join(od, f))   # no half-written files on a stop
                except Exception as ex:
                    fails.append({'file': f, 'error': '%s: %s' % (type(ex).__name__, str(ex)[:300])}); print('FAIL', m, f, str(ex)[:120], flush=True)
        # failed inputs are retried on the next run; downstream treats a missing output as "no candidate from this model"
        json.dump(fails, open(os.path.join(work, 'failures_%s.json' % m), 'w'), indent=1)
        times[m] = round(time.time() - t0, 1); print(m, '%.0fs' % times[m], 'failed', len(fails), flush=True)
    json.dump({'device': how, 'seconds': times}, open(os.path.join(work, 'torch_times.json'), 'w'), indent=1)

def credits(used=None):
    """CREDITS.txt that ships with the HD pack: every model whose outputs are in the pack, with author, licence, source and hash
    (CC-BY-4.0 requires attribution; CC0 listed for provenance)"""
    used = used or (sys.argv[sys.argv.index('--used') + 1].split(',') if '--used' in sys.argv else list(MODELS))
    L = ['Transformers: War for Cybertron - optional HD texture pack', '',
         'The HD textures are 2x upscales of the original game textures, locked to the originals (shrunk back down, each equals the',
         'original). They were made with the following models; their licences permit redistributing the outputs.', '']
    for m in used:
        r = MODELS[m]
        L += ['%s' % m, '  author:  %s' % r['author'], '  licence: %s%s' % (r['license'], ' (attribution required)' if r['license'].startswith('CC-BY') else ''),
              '  source:  %s' % r['url'], '  sha256:  %s' % r['sha256'], '']
    L += ['Tools: spandrel (MIT), PyTorch (BSD-3-Clause), torch-directml (MIT), Real-ESRGAN ncnn-vulkan (BSD-3-Clause),',
          'DirectXTex texconv (MIT). Original textures: Transformers: War for Cybertron (c) their respective owners.']
    p = os.path.join(AT, 'out', 'hd', 'CREDITS.txt'); open(p, 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print('wrote', p)

if __name__ == '__main__':
    {'probe': probe, 'run': run, 'credits': credits}[sys.argv[1]]()
