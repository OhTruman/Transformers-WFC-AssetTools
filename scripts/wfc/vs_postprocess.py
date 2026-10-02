"""Authored post-process setup of a map, from manifests/authored.db (authored.py) + config + the CLUT volume.

Output: ExtractedAssets/VerticalSlice/Maps/<MAP>/postprocess.json (+ postprocess_clut.png, 1024x32 strip:
        column = z*32 + x, row = y; R = x, G = y, B = z)
  scene_chain     the engine's scene post-process chain (Coalesced [Engine.Engine] DefaultPostProcessName) and its
                  effects with effective props; each effect's bUseWorldSettings
  world_settings  DefaultPostProcessSettings of every sublevel WorldInfo (struct deep-merged over Default__WorldInfo /
                  Default__TnWorldInfo) + which one governs (persistent level from TransLevels.ini) + authored-key list
  resolved        the values the uber/motion-blur effects run with on this map (world settings, since bUseWorldSettings)
  clut            ColorCorrectionTexture decode stats + least-squares affine fit of the grade
  volumes         PostProcessVolumes in the map (none on Streets)
  semi_transparent_chain, screen_effects (HUD chains + materials), camera (TnCamera post-process modifier,
                  target focuser), weapons_fine_aim_focus, system_settings (config)
  python vs_postprocess.py [MAP]
"""
import json, os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree, texture3d, matgraph, extract  # noqa: E402
from vs_common import VS  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
CFG = os.path.join(os.path.dirname(extract.OUT), 'config', 'Coalesced_ini', 'TransGame', 'Config', 'Xenon', 'Cooked')
EDITOR = ('NodePosX', 'NodePosY', 'DrawWidth', 'DrawHeight', 'OutDrawY', 'InDrawY')

def ini(fname):
    """{section: [(key, value), ...]}"""
    out, sec = {}, None
    p = os.path.join(CFG, fname)
    if not os.path.exists(p): return out
    for l in open(p, encoding='utf-8', errors='replace'):
        l = l.rstrip('\n')
        m = re.match(r'^\[(.+)\]\s*$', l)
        if m: sec = m.group(1); out.setdefault(sec, []); continue
        if sec and '=' in l and not l.lstrip().startswith(';'):
            k, v = l.split('=', 1); out[sec].append((k.strip(), v.strip()))
    return out

def first(cfg, sec, key):
    return next((v for k, v in cfg.get(sec, []) if k == key), None)

def effect_rec(e):
    o = A.get(e); eff = A.effective(e)
    return {'effect': e.rsplit('.', 1)[-1], 'object': e, 'class': o['class'] if o else None,
            'authored': {k: v for k, v in ((o or {}).get('props') or {}).items() if k not in EDITOR},
            'effective': {k: x['value'] for k, x in eff.items() if k not in EDITOR},
            'effective_from': {k: x['from'] for k, x in eff.items() if k not in EDITOR}}

def chain_rec(ch):
    c = A.get(ch)
    if not c: return {'chain': ch, 'missing': True}
    return {'chain': ch, 'package_owner': c['package'], 'effects': [effect_rec(e) for e in (c['props'] or {}).get('Effects') or [] if e]}

def mat_rec(m):
    r = A.get(m)
    if not r: return {'material': m, 'missing': True}
    out = {'material': m, 'class': r['class']}
    if r['class'].startswith('MaterialInstance'):
        p = r['props'] or {}
        out['overrides'] = {k: [{a: b for a, b in x.items() if a != 'ExpressionGUID'} for x in p.get(k) or []]
                            for k in ('ScalarParameterValues', 'VectorParameterValues', 'TextureParameterValues') if p.get(k)}
        out['parent'] = p.get('Parent')
        if p.get('Parent'): out['parent_summary'] = mat_rec(p['Parent'])
        return out
    g = matgraph.graph(m, r['package'])
    out['meta'] = g.get('meta')
    out['roots'] = {pin: sorted(set('%s %s' % x for x in matgraph.leaves(matgraph.upstream(g, v['node']))))
                    for pin, v in (g.get('roots') or {}).items()}
    return out

def clut_analysis(opath, pkg_name):
    p = objtree.package(pkg_name)
    vol, info = texture3d.decode_texture3d(p, opath)
    v = vol[..., :3].astype(float)
    sx, sy, sz = info['size']
    # input colour of cell (x,y,z) = (x,y,z)/(N-1) for R,G,B (UE3 uber shader: tex3D(c*(N-1)/N + 0.5/N))
    zz, yy, xx = np.indices((sz, sy, sx))
    inp = np.stack([xx / (sx - 1), yy / (sy - 1), zz / (sz - 1)], -1).reshape(-1, 3)
    outc = v.reshape(-1, 3) / 255.0
    X = np.c_[inp, np.ones(len(inp))]
    coef, res, *_ = np.linalg.lstsq(X, outc, rcond=None)
    pred = X @ coef
    grey = np.array([v[k, k, k] for k in range(min(sx, sy, sz))]) / 255.0
    lum_in = inp @ np.array([0.299, 0.587, 0.114]); sat_in = inp.max(1) - inp.min(1); sat_out = outc.max(1) - outc.min(1)
    mask = sat_in > 0.2
    strip = vol.transpose(1, 0, 2, 3).reshape(sy, sz * sx, 4)
    png = os.path.join(OUT, 'postprocess_clut.png')
    try:
        from PIL import Image
        Image.fromarray(strip).save(png)
    except Exception:
        import zlib, struct as st
        raw = b''.join(b'\x00' + strip[r].tobytes() for r in range(strip.shape[0]))
        def chunk(t, d): return st.pack('>I', len(d)) + t + d + st.pack('>I', zlib.crc32(t + d) & 0xffffffff)
        open(png, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', st.pack('>IIBBBBB', strip.shape[1], strip.shape[0], 8, 6, 0, 0, 0)) +
                              chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
    return {'object': opath, **info, 'png': os.path.relpath(png, os.path.dirname(VS)).replace(os.sep, '/'),
            'layout': 'cell (x,y,z) -> output RGB for input (R=x, G=y, B=z)/(N-1); strip column z*N+x, row y',
            'validation': {'tail_bytes_expected': 20 + sx * sy * sz * 4,
                           'monotone_R_along_x': round(float((np.diff(v[..., 0], axis=2) >= -1).mean()), 4),
                           'monotone_G_along_y': round(float((np.diff(v[..., 1], axis=1) >= -1).mean()), 4),
                           'monotone_B_along_z': round(float((np.diff(v[..., 2], axis=0) >= -1).mean()), 4),
                           'alpha_values': sorted(set(int(a) for a in np.unique(vol[..., 3])))[:4]},
            'affine_fit': {'matrix_out_from_in': np.round(coef[:3].T, 4).tolist(), 'offset': np.round(coef[3], 4).tolist(),
                           'rms_residual_8bit': round(float(np.sqrt(((pred - outc) ** 2).mean()) * 255), 3)},
            'grey_ramp_out': {'black': np.round(grey[0], 4).tolist(), 'mid': np.round(grey[len(grey) // 2], 4).tolist(),
                              'white': np.round(grey[-1], 4).tolist()},
            'output_range': {'min': np.round(outc.min(0), 4).tolist(), 'max': np.round(outc.max(0), 4).tolist()},
            'saturation_ratio_out_over_in': round(float((sat_out[mask] / sat_in[mask]).mean()), 4),
            'mean_luma_shift': round(float((outc @ np.array([0.299, 0.587, 0.114]) - lum_in).mean()), 4)}

def main():
    eng = ini('Xe-TransEngine.ini'); lev = ini('Xe-TransLevels.ini') or ini('TransLevels.ini')
    subs = sorted({r['opath'].split('.')[0] for r in A.find(MAP + '_%.TheWorld', 'World')})
    out = {'map': MAP, 'source': 'manifests/authored.db + Coalesced Xe-TransEngine.ini', 'notes': []}
    # ------------------------------------------------------------ scene chain
    dpn = first(eng, 'Engine.Engine', 'DefaultPostProcessName')
    out['config'] = {'Engine.Engine.DefaultPostProcessName': dpn,
                     'Engine.Engine.DefaultPostProcess (stale)': first(eng, 'Engine.Engine', 'DefaultPostProcess'),
                     'Engine.Engine.DefaultUIScenePostProcessName': first(eng, 'Engine.Engine', 'DefaultUIScenePostProcessName'),
                     'DisplayGamma': next((v for s in eng for k, v in eng[s] if k == 'DisplayGamma'), None),
                     'SystemSettings': {k: v for k, v in eng.get('SystemSettings', [])
                                        if re.search('Bloom|MotionBlur|DepthOfField|Distortion|LensFlare|FogVolume|FloatingPoint|Upscal|Screen|Res[XY]|AmbientOcclusion|Gamma', k)}}
    out['scene_chain'] = chain_rec(dpn) if dpn else None
    out['notes'].append('[Engine.Engine] also sets DefaultPostProcess=PostProcess_XENON.PostProcessChain_0, but no PostProcess_XENON '
                        'package exists in the dump: INFERRED stale; the cooked scene chain is DefaultPostProcessName.')
    # ------------------------------------------------------------ world settings
    out['world_settings'] = {}
    for sub in subs:
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'TnWorldInfo'):
            own = (r['props'] or {}).get('DefaultPostProcessSettings') or {}
            eff = A.effective(r['opath']).get('DefaultPostProcessSettings', {})
            out['world_settings'][sub] = {'world_info': r['opath'], 'authored_fields': own,
                                          'effective': eff.get('value'), 'struct_defaults_from': eff.get('struct_defaults_from')}
            v = A.values(r['opath'])
            out['world_settings'][sub]['other'] = {k: v.get(k) for k in ('SemiTransparentPostProcess', 'bUseGlobalPostProcess',
                                                   'DefaultAmbientOcclusionSettings') if k in v}
    persistent = next((s for s in subs if s.lower().endswith('_base_m')), subs[0])
    out['governing_world'] = persistent
    out['notes'].append('Governing WorldInfo = the persistent level %s (Streets BASE streams ART + AUDIO; TransLevels.ini / '
                        'LevelStreaming, CONFIRMED in Rendering pass 8). Sublevel WorldInfos are not used for post-process.' % persistent)
    ws = out['world_settings'][persistent]['effective'] or {}
    # ------------------------------------------------------------ resolved
    fx = {e['class']: e for e in (out['scene_chain'] or {}).get('effects', [])}
    res = {'motion_blur': {'enabled': ws.get('bEnableMotionBlur'), 'from': 'world (bUseWorldSettings=%s)' % fx.get('MotionBlurEffect', {}).get('effective', {}).get('bUseWorldSettings')}}
    for k in ('Amount', 'MaxVelocity', 'CurveExponent', 'InnerRadius', 'OuterRadius', 'RadialBlurExponent', 'AccumulationSoftness', 'Technique', 'NumSamples'):
        res['motion_blur'][k] = ws.get('MotionBlur_' + k)
    res['bloom'] = {'enabled': ws.get('bEnableBloom'), 'scale': ws.get('Bloom_Scale'), 'threshold': ws.get('Bloom_Threshold')}
    res['dof'] = {k: ws.get(k) for k in ('bEnableDOF', 'DOF_FocusType', 'DOF_FocusDistance', 'DOF_FocusNearFalloff', 'DOF_FocusFarFalloff',
                                         'DOF_MaxNearBlurAmount', 'DOF_MaxFarBlurAmount', 'DOF_FalloffExponent', 'DOF_BlurKernelSize',
                                         'DOF_ModulateBlurColor', 'DOFXScale', 'DOFYScale', 'DOFAndBloomXScale', 'DOFAndBloomYScale')}
    res['scene_tone'] = {k: ws.get(k) for k in ('bEnableSceneEffect', 'Scene_Desaturation', 'Scene_HighLights', 'Scene_MidTones', 'Scene_Shadows', 'ColorCorrectionTexture')}
    res['ambient_occlusion'] = ws.get('bAllowAmbientOcclusion')
    res['effect_class_defaults_NOT_used'] = {k: fx.get('UberPostProcessEffect', {}).get('effective', {}).get(k)
                                             for k in ('SceneShadows', 'SceneHighLights', 'SceneMidTones', 'SceneDesaturation', 'FocusNearFalloff', 'FocusFarFalloff')}
    out['resolved'] = res
    out['notes'].append('Both scene effects have bUseWorldSettings=true, so their parameters come from the governing world\'s '
                        'PostProcessSettings (UE3 semantics, CONFIRMED flag). The UberPostProcessEffect class defaults '
                        '(MidTones 1.3, HighLights 0.8, Desaturation 0.4, Shadows -0.003) apply only where world settings are bypassed.')
    clut = ws.get('ColorCorrectionTexture')
    out['clut'] = clut_analysis(clut, persistent) if clut else None
    # ------------------------------------------------------------ volumes, other chains, camera
    out['volumes'] = [{'volume': r['opath'], 'props': A.values(r['opath'])} for s in subs for r in A.find(s + '.TheWorld.PersistentLevel.%', 'PostProcessVolume')]
    stp = (A.values(out['world_settings'][persistent]['world_info']) or {}).get('SemiTransparentPostProcess')
    out['semi_transparent_chain'] = chain_rec(stp) if stp else None
    if out['semi_transparent_chain']:
        for e in out['semi_transparent_chain']['effects']:
            if e['effective'].get('Material'): e['material_summary'] = mat_rec(e['effective']['Material'])
    hud = [r for r in A.find('UI_GFxHud_p.%') if (r['props'] or {}).get('PostProcessChains')]
    out['screen_effects'] = []
    for r in hud:
        for i, ch in enumerate(r['props']['PostProcessChains']):
            c = chain_rec(ch)
            for e in c.get('effects', []):
                if e['effective'].get('Material'): e['material_summary'] = mat_rec(e['effective']['Material'])
            out['screen_effects'].append({'owner': r['opath'], 'index': i, 'default_active_index': A.values(r['opath']).get('CurrentPostProcessChainIndex'), **c})
    cam = {}
    for o in ('TransGame.Default__TnCamera.PPM0', 'TransGame.Default__TnCamera.TargetFocuser0'):
        v = A.values(o); cam[o] = {'class': (A.get(o) or {}).get('class'), 'effective': v}
    out['camera'] = cam
    rows = A.con().execute("SELECT opath FROM objects WHERE class='TnWeaponData' AND props LIKE '%\"bShouldApplyFineAimTargetFocus\":true%'").fetchall()
    out['weapons_fine_aim_focus'] = {'enabled_by': [r[0] for r in rows],
                                     'ion_blaster_mp': A.values('WEP_IonBlaster_p.IonBlaster_WEPDATA').get('bShouldApplyFineAimTargetFocus', False),
                                     'default_params': A.values('TransGame.Default__TnWeaponData').get('FineAimTargetFocusParams')}
    out['notes'].append('Fine-aim target-focus DOF (TnTargetFocuser) is applied only by weapon data with bShouldApplyFineAimTargetFocus; '
                        'the MP Ion Blaster does not set it (bool default false) - only AI/mounted weapons and the MP bomb do.')
    out['notes'].append('Screen effects: the HUD (Hud_GFX_1) owns StaticDischarge (index 0) and LowHealth (index 1) chains, '
                        'CurrentPostProcessChainIndex -1 by default; activation thresholds are native/ActionScript (UNKNOWN).')
    out['notes'].append('Streets has no PostProcessVolumes and its only matinee (SkyBeam) animates a move track - no authored '
                        'post-process animation on this map.')
    path = os.path.join(OUT, 'postprocess.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps({'scene_chain': [e['class'] for e in (out['scene_chain'] or {}).get('effects', [])], 'governing': persistent,
                      'bloom': res['bloom'], 'dof_on': res['dof']['bEnableDOF'], 'mblur_on': res['motion_blur']['enabled'],
                      'clut_fit_rms': (out['clut'] or {}).get('affine_fit', {}).get('rms_residual_8bit'), 'volumes': len(out['volumes']),
                      'screen_effects': len(out['screen_effects'])}), '->', path)

if __name__ == '__main__':
    main()
