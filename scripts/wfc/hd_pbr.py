"""Optional 'Modern' materials mode (user decision 2026-10-09, confirmed in this session): generated PBR maps per surface, consistent
with the original art (designs, colours and patterns unchanged; the colour map is the faithful HD albedo). Sample for Rendering's
Original-vs-Modern preview first; the full pilot follows.

  python hd_pbr.py sample            -> out/hd/pbr_sample/<texture>/{albedo,height,roughness,ao,metalness}.png + sheet.png + maps.json

Maps:
  height     1x-PBRify-Height (CC0, Kim2091 PBRify_Remix; SPAN) on the HD albedo
  roughness  1x-PBRify-RoughnessV2 (CC0) on the HD albedo
  ao         derived from height: multi-scale cavity (how far each texel lies below its 4 / 16 / 64 px neighbourhood mean)
  metalness  PROVISIONAL heuristic (no redistributable generator): painted metal is a dielectric in PBR, so only bright,
             desaturated, smooth texels (bare-metal wear / edges) become metallic; everything else 0
  normal     the texture's own normal map stays the source of truth (not regenerated)
Runs on CPU (1x SPAN models are light), so no GPU window is needed.
"""
import json, os, sys
from collections import OrderedDict as OD
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hd_torch as T  # noqa: E402

AT = T.AT
HD = os.path.join(AT, 'out', 'hd')
SAMPLE = ['WEP_Bazooka_CLR', 'VH_SoldierTankAutCore_GrungeClr', 'ENV_IAC_CleanTerminalFloor_TEXSET_Color_NormX', 'WallDeco_01_CLR']

def run_model(name, img, dev):
    d = T.load(name, dev)
    return T.upscale(d, dev, img)

def ao_from_height(h):
    hf = h.astype(np.float32) / 255
    acc = np.zeros_like(hf)
    for r in (4, 16, 64):
        m = np.asarray(Image.fromarray(h, 'L').filter(ImageFilter.BoxBlur(r))).astype(np.float32) / 255
        acc += np.clip((m - hf) * 4.0, 0, 1)
    return np.clip(np.round((1 - acc / 3) * 255), 0, 255).astype(np.uint8)

def metalness(albedo, rough):
    a = albedo[..., :3].astype(np.float32) / 255
    v = a.max(-1); sat = (v - a.min(-1)) / np.maximum(v, 1e-6); r = rough.astype(np.float32) / 255
    m = np.clip((v - 0.55) / 0.25, 0, 1) * np.clip((0.25 - sat) / 0.15, 0, 1) * np.clip((0.6 - r) / 0.3, 0, 1)
    return np.round(m * 255).astype(np.uint8)

def sample():
    import torch
    dev = torch.device('cpu')
    man = json.load(open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v3.json'), encoding='utf-8'))
    by = {r['object_path'].split('.')[-1]: r for r in man['textures']}
    od = os.path.join(HD, 'pbr_sample'); os.makedirs(od, exist_ok=True); index = OD()
    for name in SAMPLE:
        r = by.get(name)
        if not r or not r.get('hd2_png'): print('skip', name); continue
        albedo = np.asarray(Image.open(os.path.join(HD, 'v3', r['hd2_png'])).convert('RGB'))
        hgt = run_model('1x-PBRify-Height', albedo, dev).mean(-1).astype(np.uint8)
        rough = run_model('1x-PBRify-RoughnessV2', albedo, dev).mean(-1).astype(np.uint8)
        ao = ao_from_height(hgt); met = metalness(albedo, rough)
        d = os.path.join(od, name); os.makedirs(d, exist_ok=True)
        maps = OD([('albedo', albedo), ('height', hgt), ('roughness', rough), ('ao', ao), ('metalness', met)])
        for k, v in maps.items(): Image.fromarray(v).save(os.path.join(d, k + '.png'))
        index[name] = OD([('object_path', r['object_path']), ('albedo_source', 'v3 best-B HD (%s, locked to the deblocked original)' % r['chosen_2x']),
                          ('size', list(albedo.shape[1::-1])), ('maps', OD((k, os.path.relpath(os.path.join(d, k + '.png'), AT).replace(os.sep, '/')) for k in maps)),
                          ('normal_map', 'the texture\'s own normal map (original or its HD version), not regenerated'),
                          ('stats', OD([('roughness_mean', round(float(rough.mean()) / 255, 3)), ('metal_fraction', round(float((met > 127).mean()), 4)),
                                        ('ao_mean', round(float(ao.mean()) / 255, 3))]))])
        # sheet: centre 512 px of each map
        hh, ww = albedo.shape[:2]; y0, x0 = max(0, hh // 2 - 256), max(0, ww // 2 - 256)
        sheet = Image.new('RGB', (5 * 522 + 10, 512 + 50), (16, 16, 20)); dr = ImageDraw.Draw(sheet)
        for i, (k, v) in enumerate(maps.items()):
            c = Image.fromarray(np.ascontiguousarray(v[y0:y0 + 512, x0:x0 + 512])).convert('RGB')
            sheet.paste(c, (10 + i * 522, 40)); dr.text((10 + i * 522, 14), k + (' (PROVISIONAL)' if k == 'metalness' else ''), fill=(235, 235, 235))
        sheet.save(os.path.join(d, 'sheet.png'))
        print(name, index[name]['stats'], flush=True)
    json.dump(OD([('generated_by', 'AssetTools/scripts/wfc/hd_pbr.py'), ('decision', 'user 2026-10-09: optional Modern materials mode; Original stays available'),
                  ('models', {m: T.MODELS[m]['license'] for m in ('1x-PBRify-Height', '1x-PBRify-RoughnessV2')}),
                  ('metalness', 'PROVISIONAL heuristic: painted metal = dielectric; bright, desaturated, smooth texels -> metal'),
                  ('textures', index)]), open(os.path.join(od, 'maps.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    {'sample': sample}[sys.argv[1]]()
