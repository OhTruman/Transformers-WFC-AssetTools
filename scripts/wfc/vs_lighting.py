"""Authored lighting setup of a map, from manifests/authored.db (authored.py) + the light collection's
native placement matrices.

Output: ExtractedAssets/VerticalSlice/Maps/<MAP>/lighting.json
  lights[]          every LightComponent (StaticLightCollectionActor + standalone light actors):
                    class, EFFECTIVE props (deep-merged with class defaults: Brightness, color, Radius,
                    FalloffExponent, cone angles, LightingChannels, LightAffectsClassification, shadow
                    flags, LightGuid/LightmapGuid ...), world matrix (UE + glTF), position, direction
  globals           directional / sky lights, HeightFog, LightsVisibilitiesVolume
  world             TnWorldInfo lighting + post-process (struct deep-merged), LevelLightingGroups,
                    PackedLightAndShadowMapTextureSize, EffectAmbientColor, bake settings
  characters        light environments + lighting channels of the slice's robot/vehicle/weapon meshes
  stats, notes
Colors: cooked FColor bytes are B,G,R,A (CONFIRMED via Engine.Default__HUD.RedColor = R255);
  every color is emitted as {'R','G','B','A'} plus 'rgb' [0..255] and 'linear_x_brightness'.
Matrices: cooked tagged FMatrix rows are (W,X,Y,Z) (typed_props.fix_raw); the collection actor's native
  block (N x 64 B, after its tags) is standard row-major and is used for placement.
  python vs_lighting.py [MAP]
"""
import json, os, re, sys
from collections import Counter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from vs_common import VS, ue_to_gltf_matrix, ue_points_to_gltf, ue_actor_matrix  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
os.makedirs(OUT, exist_ok=True)
SKIP = ('HashGridBBox', 'TickGroup', 'CachedParentToWorld')

def color(c, brightness=None):
    if not isinstance(c, dict) or 'R' not in c: return c
    out = {'R': c['R'], 'G': c['G'], 'B': c['B'], 'A': c.get('A', 0), 'rgb': [c['R'], c['G'], c['B']],
           'hex': '#%02x%02x%02x' % (c['R'], c['G'], c['B'])}
    if brightness is not None:
        out['linear_x_brightness'] = [round(((x / 255.0) ** 2.2) * brightness, 5) for x in (c['R'], c['G'], c['B'])]
    return out

def norm(v):
    if isinstance(v, dict):
        if set(v) >= {'R', 'G', 'B'} and all(isinstance(v[k], int) for k in ('R', 'G', 'B')): return color(v)
        return {k: norm(x) for k, x in v.items()}
    if isinstance(v, list): return [norm(x) for x in v]
    return v

def channels(v):
    return sorted(k for k, x in (v or {}).items() if x is True and k != 'bInitialized')

def light_record(op, M, source):
    o = A.get(op); eff = A.effective(op); v = {k: x['value'] for k, x in eff.items()}
    rec = {'light': op.rsplit('.', 1)[-1], 'object': op, 'class': o['class'], 'source': source,
           'authored_props': sorted((o['props'] or {}).keys()),
           'props': {k: norm(x) for k, x in v.items() if k not in SKIP}}
    rec['brightness'] = v.get('Brightness', 1.0)
    rec['color'] = color(v.get('LightColor'), rec['brightness'])
    rec['channels_on'] = channels(v.get('LightingChannels'))
    if M is not None:
        M = np.asarray(M, float)
        rec['ue_matrix'] = M.tolist(); rec['gltf_matrix'] = ue_to_gltf_matrix(M)
        rec['location_ue'] = M[3, :3].round(3).tolist()
        rec['location_gltf'] = ue_points_to_gltf([M[3, :3]])[0].round(4).tolist()
        fwd = M[0, :3] / (np.linalg.norm(M[0, :3]) or 1)          # UE light direction = component X axis
        rec['direction_ue'] = fwd.round(5).tolist()
        rec['direction_gltf'] = [round(float(x), 5) for x in (fwd[0], fwd[2], fwd[1])]
        rec['scale'] = round(float(np.linalg.norm(M[0, :3])), 4)
    return rec

def collection_matrices(sub, op):
    p = objtree.package(sub); i = p._idx.get(op.lower())
    e = p.exports[i - 1]; _, used = p._tr.read_object(i)
    raw = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
    return np.frombuffer(raw, '>f4').reshape(-1, 4, 4).astype('f8')

def main():
    subs = sorted({r['opath'].split('.')[0] for r in A.find(MAP + '_%.TheWorld', 'World')})
    out = {'map': MAP, 'source': 'manifests/authored.db + StaticLightCollectionActor native matrices', 'sublevels': subs,
           'lights': [], 'globals': {}, 'world': {}, 'characters': {}, 'notes': []}
    val = {'cached_vs_native_max_abs': 0.0, 'compared': 0}
    for sub in subs:
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'StaticLightCollectionActor'):
            comps = (r['props'] or {}).get('LightComponents') or []
            Ms = collection_matrices(sub, r['opath'])
            assert len(Ms) == len(comps), (len(Ms), len(comps))
            for k, c in enumerate(comps):
                rec = light_record(c, Ms[k], r['opath'].rsplit('.', 1)[-1])
                cp = A.values(c).get('CachedParentToWorld')
                if cp:
                    val['compared'] += 1
                    val['cached_vs_native_max_abs'] = max(val['cached_vs_native_max_abs'], float(np.abs(np.array(cp).reshape(4, 4) - Ms[k]).max()))
                out['lights'].append(rec)
        # standalone light actors (PointLight, SpotLight, DirectionalLight, ... outside collections)
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', None):
            if r['outer'] != sub + '.TheWorld.PersistentLevel': continue
            if not re.search(r'Light$|LightToggleable$|LightMovable$', r['class']) or 'Collection' in r['class']: continue
            v = A.values(r['opath'])
            lc = next((x for k, x in v.items() if isinstance(x, str) and 'LightComponent' in x), None)
            if not lc: continue
            loc = [v.get('Location', {}).get(a, 0.0) for a in 'XYZ']; rot = [v.get('Rotation', {}).get(a, 0) for a in ('Pitch', 'Yaw', 'Roll')]
            out['lights'].append(light_record(lc, ue_actor_matrix(loc, rot, v.get('DrawScale', 1.0)), r['opath'].rsplit('.', 1)[-1]))
    # ---------------------------------------------------------------- globals
    for rec in out['lights']:
        if rec['class'] in ('DirectionalLightComponent', 'SkyLightComponent'):
            role = ('dominant_baked_directional' if rec['class'] == 'DirectionalLightComponent' and 'Static' in rec['channels_on']
                    else 'dynamic_fill_directional' if rec['class'] == 'DirectionalLightComponent' else 'dynamic_sky_light')
            g = {k: rec.get(k) for k in ('light', 'class', 'brightness', 'color', 'channels_on', 'direction_ue', 'direction_gltf')}
            g['props'] = rec['props']
            if rec['class'] == 'SkyLightComponent':
                g['lower_color'] = color(rec['props'].get('LowerColor', {}).get('rgb') and A.values(rec['object']).get('LowerColor'),
                                         A.values(rec['object']).get('LowerBrightness', 0.0))
            out['globals'][role] = g
    for sub in subs:
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'HeightFogComponent'):
            v = A.values(r['opath']); act = A.values(r['outer'])
            out['globals']['height_fog'] = {'component': r['opath'], 'props': norm(v), 'color': color(v.get('LightColor'), v.get('LightBrightness')),
                                            'actor_location_ue': act.get('Location'), 'actor_draw_scale': act.get('DrawScale')}
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'LightsVisibilitiesVolume'):
            p = objtree.package(sub); i = p._idx.get(r['opath'].lower()); e = p.exports[i - 1]
            out['globals']['lights_visibilities_volume'] = {'actor': r['opath'], 'props': norm(A.values(r['opath'])),
                                                            'native_bytes': e['serial_size'] - p._tr.read_object(i)[1],
                                                            'note': 'precomputed per-cell light visibility (native; PARTIAL per Rendering)'}
    # ---------------------------------------------------------------- world info
    for sub in subs:
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'TnWorldInfo'):
            own = r['props'] or {}; v = A.values(r['opath'])
            out['world'][sub] = {'authored_keys': sorted(k for k in own if re.search('Light|PostProcess|Ambient|Shadow|Lightmap|Fog|Static', k)),
                                 'values': {k: norm(x) for k, x in v.items()
                                            if re.search('Light|Bright|Shadow|Ambient|Env|Beast|Character|PostProcess|Lightmap|Fog|Skylight', k)}}
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'BeastSettingsReferer'):
            out['world'].setdefault('beast_settings', {})[sub] = norm(A.values(r['opath']))
    # ---------------------------------------------------------------- characters (slice)
    for name, mesh, le in (('robot', 'TransGame.Default__TnRobotForm.RobotMeshComponent0', 'TransGame.Default__TnRobotForm.LightEnvironment0'),
                           ('truck_vehicle', 'TransGame.Default__TnTruckForm.VehicleMesh', 'TransGame.Default__TnTruckForm.MyLightEnv'),
                           ('weapon', 'TransGame.Default__TnWeaponMesh.MeshA', 'TransGame.Default__TnWeaponMesh.MyLightEnvironment')):
        e = A.effective(le); mv = A.values(mesh)
        out['characters'][name] = {
            'light_environment': le, 'light_environment_props': {k: x['value'] for k, x in e.items() if k != 'TickGroup'},
            'light_environment_props_from': {k: x['from'] for k, x in e.items() if k != 'TickGroup'},
            'mesh_component': mesh,
            'mesh_lighting': {k: norm(mv.get(k)) for k in ('LightingChannels', 'bAcceptsLights', 'bAcceptsDynamicLights', 'CastShadow',
                                                           'bCastDynamicShadow', 'bSelfShadowOnly', 'bUseOnePassLightingOnTranslucency') if k in mv},
            'mesh_channels_on_authored': channels(mv.get('LightingChannels'))}
    # ---------------------------------------------------------------- stats + notes
    L = out['lights']
    out['stats'] = {'lights': len(L), 'by_class': dict(Counter(x['class'] for x in L)),
                    'by_classification': dict(Counter(x['props'].get('LightAffectsClassification') for x in L)),
                    'by_channels': dict(Counter(','.join(x['channels_on']) for x in L)),
                    'cast_dynamic_shadows': sum(1 for x in L if x['props'].get('CastDynamicShadows')),
                    'built_into_lightmap': sum(1 for x in L if x['props'].get('bHasLightEverBeenBuiltIntoLightMap')),
                    'disabled': sum(1 for x in L if not x['props'].get('bEnabled', True)),
                    'brightness_range': [min(x['brightness'] for x in L), max(x['brightness'] for x in L)] if L else None,
                    'unique_colors': len({x['color']['hex'] for x in L if isinstance(x.get('color'), dict)}),
                    'validation': val}
    out['notes'] += [
        "Lighting channels are deep-merged through each light's archetype chain, including the stock actor component templates "
        '(e.g. Engine.Default__DirectionalLight.DirectionalLightComponent0 / Default__PointLight.PointLightComponent0 turn Dynamic off).',
        'All 265 local point/spot lights: LAC_STATIC_AFFECTING, channels BSP+Static+CompositeDynamic (Dynamic off), built into the '
        'lightmaps. Dominant DirectionalLight (Brightness 6): BSP+Static+CompositeDynamic. Fill DirectionalLight (0.2): CompositeDynamic '
        'only (BSP/Static/Dynamic off) = a character-only light. SkyLight (0.1, LowerBrightness 0): Dynamic+CompositeDynamic.',
        "So EVERY light reaches characters through the CompositeDynamic path (UE3: composited into the owner's light environment; "
        'HIGH CONFIDENCE, native), and only the SkyLight also lights dynamic primitives directly. With the authored character '
        'light environment TotalLightCount 2, the environment keeps the 2 strongest contributions as lights and folds the rest '
        "into its ambient term (INFERRED from UE3 DLE semantics; consistent with Rendering's decoded 2-light + ambient-cube shader). "
        'The LightsVisibilitiesVolume holds the precomputed per-cell visibility used for that compositing (native).',
        "Character mesh channels: only PlayerOnly is authored on TnRobotForm's mesh; PrimitiveComponent's native default channel "
        'mask is not serialized (INFERRED: Dynamic on, as in stock UE3).',
        'COLOR BYTE ORDER (CONFIRMED via Engine.Default__HUD RedColor/ConsoleColor): cooked FColor = B,G,R,A. Reading the raw bytes '
        'as R,G,B turns blue-violet into red-pink: HeightFog bytes 234,91,116 = RGB (116,91,234); dominant light = RGB (117,117,255).',
        'linear_x_brightness = (sRGB->linear of the 8-bit color) x Brightness; UE3 treats FColor light colors as sRGB-encoded '
        '(FLinearColor(FColor)) - INFERRED for this licensee build.']
    path = os.path.join(OUT, 'lighting.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps({k: v for k, v in out['stats'].items() if k in ('lights', 'by_class', 'built_into_lightmap', 'validation', 'unique_colors')}), '->', path)

if __name__ == '__main__':
    main()
