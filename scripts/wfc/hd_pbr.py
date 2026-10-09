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

# --- v2: maps from the original artists' masks (channel semantics: Rendering, compiled original graphs, 2026-10-09) ---------
# family -> (gloss texture parameter, gloss channel, paint parameter(s) and channels, Blinn-Phong spec power from gloss g)
FAMILIES = OD([
    ('WEP_PhongMain_MAT', dict(gloss=('MasksMap', 1), paint=[('MasksMap', 2)], power=lambda g: (2 + 40 * (g + 0.15)) / 2)),
    ('CHR_Transformer_NormSpec_Cust_E_Mat', dict(gloss=('Lum_Map', 0), paint=[('CustClrAlphasMap', 0), ('CustClrAlphasMap', 1)],
                                                 power=lambda g: 2 + 40 * (g + 0.15))),
    ('TEXSET', dict(gloss=('Masks_NormY', 1), paint=[], power=lambda g: 45 * (g + 1 / (1 + np.exp(-(30 * g - 15)))) + 0.15)),
])

def material_of(tex):
    """(family, {parameter: texture object path}) of the first material instance that uses `tex`"""
    import authored as A
    for r in A.refs_to(tex):
        src = r[0] if isinstance(r, (tuple, list)) else r
        g = A.get(src) or {}
        if g.get('class') == 'TextureSet' and tex.endswith('_Color_NormX'):
            # TEXSET pair: Color_NormX (colour + normal X in alpha) and its Masks_NormY sibling (G gloss, normal Y in alpha)
            return 'TEXSET', {'Color_NormX': tex, 'Masks_NormY': tex[:-len('_Color_NormX')] + '_Masks_NormY'}
        if g.get('class') != 'MaterialInstanceConstant': continue
        v = A.values(src) or {}; params = {p.get('ParameterName'): p.get('ParameterValue') for p in v.get('TextureParameterValues') or []}
        par = v.get('Parent')
        for _ in range(6):
            if not par: break
            for fam in FAMILIES:
                if fam != 'TEXSET' and par.endswith(fam): return fam, params
            pv = A.values(par) or {}
            for p in pv.get('TextureParameterValues') or []: params.setdefault(p.get('ParameterName'), p.get('ParameterValue'))
            par = pv.get('Parent')
    # no material found: the normal map by name (same package / group, *_NORM), family unknown
    stem = tex.rsplit('_', 1)[0]
    rows = {json.loads(l)['object_path'] for l in open(os.path.join(AT, 'manifests', 'extracted', 'textures_dds.jsonl'), encoding='utf-8')}
    return None, ({'NormalMap': stem + '_NORM'} if stem + '_NORM' in rows else {})

def channel(opath, ch, size):
    """one channel of an original texture (DDS export), resized to `size` (bicubic; data maps)"""
    rows = {json.loads(l)['object_path']: json.loads(l) for l in open(os.path.join(AT, 'manifests', 'extracted', 'textures_dds.jsonl'), encoding='utf-8')}
    r = rows.get(opath)
    if not r: return None
    a = np.asarray(Image.open(os.path.join(AT, 'out', 'dds', r['dds'])).convert('RGBA'))[..., ch]
    return np.asarray(Image.fromarray(a).resize(size, Image.BICUBIC)).astype(np.float32) / 255

def sample2():
    import torch
    sys.path.insert(0, HERE)
    import hd_pilot as Hp
    dev = torch.device('cpu')
    man = json.load(open(os.path.join(AT, 'manifests', 'hd', 'hd_pilot_v3.json'), encoding='utf-8'))
    by = {r['object_path'].split('.')[-1]: r for r in man['textures']}
    od = os.path.join(HD, 'pbr_sample_v2'); os.makedirs(od, exist_ok=True); index = OD()
    for name in SAMPLE:
        r = by.get(name)
        if not r or not r.get('hd2_png'): print('skip', name); continue
        albedo = np.asarray(Image.open(os.path.join(HD, 'v3', r['hd2_png'])).convert('RGB')); H_, W_ = albedo.shape[:2]; size = (W_, H_)
        fam, params = material_of(r['object_path'])
        rough_ml = run_model('1x-PBRify-RoughnessV2', albedo, dev).mean(-1).astype(np.float32) / 255
        hgt_ml = run_model('1x-PBRify-Height', albedo, dev).mean(-1).astype(np.float32) / 255
        rec = OD([('object_path', r['object_path']), ('material_family', fam or 'unknown (heuristic, PROVISIONAL)'), ('params', params)])
        a = albedo.astype(np.float32) / 255; v = a.max(-1); sat = (v - a.min(-1)) / np.maximum(v, 1e-6)
        if fam:
            F = FAMILIES[fam]
            gp = params.get(F['gloss'][0]); gloss = channel(gp, F['gloss'][1], size) if gp else None
            paint = np.zeros((H_, W_), np.float32)
            for pn, ch in F['paint']:
                pp = params.get(pn)
                if pp: paint = np.maximum(paint, channel(pp, ch, size))
        else:
            gloss, paint = None, np.zeros((H_, W_), np.float32)
        if gloss is not None:
            # roughness from the artists' gloss through the material's own spec power (Blinn-Phong n -> GGX alpha = sqrt(2/(n+2)),
            # roughness = sqrt(alpha)); the generated roughness only adds micro-variation (its high-pass, +-0.08)
            n = FAMILIES[fam]['power'](gloss); base = np.sqrt(np.sqrt(2 / (n + 2)))
            micro = rough_ml - np.asarray(Image.fromarray(rough_ml, 'F').resize((W_ // 8, H_ // 8), Image.BOX).resize(size, Image.BILINEAR))
            rough = np.clip(base + np.clip(micro, -0.08, 0.08), 0.03, 1)
            metal = np.clip((gloss - 0.35) / 0.3, 0, 1) * (1 - np.clip(paint, 0, 1)) * np.clip((0.35 - sat) / 0.2, 0, 1)
            rec['roughness_source'] = 'original gloss (%s ch %d) via the material spec power; PBRify micro-variation' % F['gloss']
            rec['metalness_source'] = 'original gloss high AND not painted (%s) AND low saturation' % (F['paint'] or 'no paint mask')
        else:
            rough = rough_ml; metal = metalness(albedo, (rough_ml * 255).astype(np.uint8)).astype(np.float32) / 255
            rec['roughness_source'] = 'PBRify-RoughnessV2 (no material masks found, PROVISIONAL)'; rec['metalness_source'] = 'heuristic (PROVISIONAL)'
        # height: shape from the texture's own normal map (Frankot-Chellappa), fine detail from PBRify height (high-pass)
        nrm_p = params.get('NormalMap') or params.get('VarienceNormal_XY_Map')
        hgt = None
        if fam == 'TEXSET':
            # normal from the TEXSET alphas: X = Color_NormX.a, Y = Masks_NormY.a, Z rebuilt
            nx, ny = channel(params['Color_NormX'], 3, size), channel(params['Masks_NormY'], 3, size)
            if nx is not None and ny is not None:
                vx, vy = nx * 2 - 1, ny * 2 - 1; vz = np.sqrt(np.clip(1 - vx ** 2 - vy ** 2, 0, 1))
                nimg = np.round((np.dstack([vx, vy, vz]) + 1) / 2 * 255).astype(np.uint8)
                h0 = Hp.normals_to_height(nimg); h0 = (h0 - h0.min()) / max(np.ptp(h0), 1e-9)
                hp_ = hgt_ml - np.asarray(Image.fromarray(hgt_ml, 'F').resize((W_ // 8, H_ // 8), Image.BOX).resize(size, Image.BILINEAR))
                hgt = np.clip(h0 + 0.25 * hp_, 0, 1); rec['height_source'] = 'TEXSET normal (Color_NormX.a, Masks_NormY.a) integrated + PBRify high-pass'
        if nrm_p and hgt is None:
            rows = {json.loads(l)['object_path']: json.loads(l) for l in open(os.path.join(AT, 'manifests', 'extracted', 'textures_dds.jsonl'), encoding='utf-8')}
            nr = rows.get(nrm_p)
            if nr:
                nimg = np.asarray(Image.open(os.path.join(AT, 'out', 'dds', nr['dds'])).convert('RGBA').resize(size, Image.BICUBIC)).copy()
                if 'XY' in nrm_p or float(np.abs(np.linalg.norm(nimg[..., :3] / 255 * 2 - 1, axis=-1) - 1).mean()) > 0.08:   # XY normals: rebuild Z
                    vv = nimg[..., :2].astype(np.float64) / 255 * 2 - 1
                    nimg[..., 2] = np.clip(np.round((np.sqrt(np.clip(1 - (vv ** 2).sum(-1), 0, 1)) + 1) / 2 * 255), 0, 255)
                h0 = Hp.normals_to_height(nimg); h0 = (h0 - h0.min()) / max(np.ptp(h0), 1e-9)
                hp_ = hgt_ml - np.asarray(Image.fromarray(hgt_ml, 'F').resize((W_ // 8, H_ // 8), Image.BOX).resize(size, Image.BILINEAR))
                hgt = np.clip(h0 + 0.25 * hp_, 0, 1); rec['height_source'] = 'own normal map %s (integrated) + PBRify high-pass detail' % nrm_p
        if hgt is None:
            hgt = hgt_ml; rec['height_source'] = 'PBRify-Height only (no normal map found)'
        h8 = np.round(hgt * 255).astype(np.uint8); ao = ao_from_height(h8)
        d = os.path.join(od, name); os.makedirs(d, exist_ok=True)
        maps = OD([('albedo', albedo), ('height', h8), ('roughness', np.round(rough * 255).astype(np.uint8)), ('ao', ao),
                   ('metalness', np.round(metal * 255).astype(np.uint8))])
        for k, vv in maps.items(): Image.fromarray(vv).save(os.path.join(d, k + '.png'))
        rec['maps'] = OD((k, os.path.relpath(os.path.join(d, k + '.png'), AT).replace(os.sep, '/')) for k in maps)
        rec['stats'] = OD([('roughness_mean', round(float(rough.mean()), 3)), ('metal_fraction', round(float((metal > 0.5).mean()), 4)), ('ao_mean', round(float(ao.mean()) / 255, 3))])
        y0, x0 = max(0, H_ // 2 - 256), max(0, W_ // 2 - 256)
        sheet = Image.new('RGB', (5 * 522 + 10, 512 + 50), (16, 16, 20)); dr = ImageDraw.Draw(sheet)
        for i, (k, vv) in enumerate(maps.items()):
            sheet.paste(Image.fromarray(np.ascontiguousarray(vv[y0:y0 + 512, x0:x0 + 512])).convert('RGB'), (10 + i * 522, 40)); dr.text((10 + i * 522, 14), k, fill=(235, 235, 235))
        sheet.save(os.path.join(d, 'sheet.png'))
        index[name] = rec; print(name, fam, rec['stats'], flush=True)
    json.dump(OD([('generated_by', 'AssetTools/scripts/wfc/hd_pbr.py sample2'), ('channel_semantics', 'Rendering, compiled original material graphs (2026-10-09)'),
                  ('textures', index)]), open(os.path.join(od, 'maps.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    {'sample': sample, 'sample2': sample2}[sys.argv[1]]()
