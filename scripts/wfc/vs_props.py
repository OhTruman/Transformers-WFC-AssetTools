"""Authored placed-prop + static-mesh setup of a map, from manifests/authored.db (authored.py) + cooked sections.

Output: ExtractedAssets/VerticalSlice/Maps/<MAP>/props_authored.json  (props.json from vs_map.py is unchanged)
  props[]    one per placed StaticMeshComponent (same order/keys as props.json: sublevel+actor[+index]) with
             container actor class, tag/group, prefab provenance, effective component render/lighting flags (with source),
             lightmap resolution (override / mesh / default), movement (Physics, RotationRate deg/s, attachment)
  meshes{}   every StaticMesh used: authored Bounds (UE + glTF), LightMapResolution/CoordinateIndex, LOD settings,
             TransparentForShadows, BodySetup, cooked LOD0 sections (triangles, materials, collision/shadow flags),
             usage count, glTF file + its triangle count and bounds
  movers     rotating / interpolating / attached props (hierarchy)
  validation glTF LOD0 triangles == cooked section triangles; glTF bounds inside authored Bounds; transform sources
  python vs_props.py [MAP]
"""
import json, os, re, sys
from collections import Counter, defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, smsections  # noqa: E402
from vs_common import ROOT, VS, load_gltf, accessor, ue_points_to_gltf  # noqa: E402
from vs_mapfx import prefab_instances  # noqa: E402
import objtree  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
RENDER = ('CastShadow', 'bCastDynamicShadow', 'bSelfShadowOnly', 'bAcceptsLights', 'bAcceptsDynamicLights', 'bForceDirectLightMap',
          'bUsePrecomputedShadows', 'bOverrideLightMapResolution', 'OverriddenLightMapResolution', 'OverriddenLightMapFormat',
          'bAcceptsDecals', 'bAcceptsDecalsDuringGameplay', 'bAcceptsFoliage', 'bAllowCullDistanceVolume', 'bAllowApproximateOcclusion',
          'CachedMaxDrawDistance', 'LDMaxDrawDistance', 'LDCullDistance', 'HiddenGame', 'bOnlyOwnerSee', 'bOwnerNoSee', 'DepthPriorityGroup',
          'MotionBlurScale', 'ForcedLodModel', 'bUseAsOccluder', 'bCastHiddenShadow', 'Scale', 'Scale3D', 'LightEnvironment')
UU_DEG = 360.0 / 65536.0

def channels(v): return sorted(k for k, x in (v or {}).items() if x is True and k != 'bInitialized')

def main():
    props = json.load(open(os.path.join(OUT, 'props.json'), encoding='utf-8'))['props']
    subs = sorted({p['sublevel'] for p in props})
    prefab = {}
    for s in subs: prefab.update(prefab_instances(objtree.package(s)))
    out = {'map': MAP, 'source': 'manifests/authored.db + cooked FStaticMeshElement sections', 'props': [], 'meshes': {}, 'movers': [], 'notes': []}
    use = Counter(p['mesh'] for p in props if p.get('mesh'))
    # ------------------------------------------------------------------ props
    for p in props:
        actor = p['sublevel'] + '.TheWorld.PersistentLevel.' + p['actor'].split('.')[0]
        av = A.values(actor); ao = A.get(actor) or {}
        comp = p.get('component') or av.get('StaticMeshComponent') or av.get('CollisionComponent')
        ce = A.effective(comp) if comp else {}
        cv = {k: x['value'] for k, x in ce.items()}
        mv = A.values(p['mesh']) if p.get('mesh') else {}
        lm_res = cv.get('OverriddenLightMapResolution') if cv.get('bOverrideLightMapResolution') else mv.get('LightMapResolution')
        r = {'actor': p['actor'], 'sublevel': p['sublevel'], 'container_class': ao.get('class'), 'component': comp, 'mesh': p.get('mesh'),
             'tag': av.get('Tag'), 'group': av.get('Group'), 'prefab': prefab.get(actor),
             'render': {k: cv.get(k) for k in RENDER if k in cv},
             'render_from': {k: ce[k]['from'].rsplit('.', 1)[-1] for k in RENDER if k in ce},
             'lighting_channels_on': channels(cv.get('LightingChannels')),
             'lightmap_resolution': lm_res, 'lightmap_resolution_source': 'component override' if cv.get('bOverrideLightMapResolution') else 'mesh',
             'mesh_authored_on_component': 'StaticMesh' in ((A.get(comp) or {}).get('props') or {}) if comp else None}
        if ao.get('class') in ('StaticInterpActor', 'InterpActor', 'KActor', 'StaticMeshActor'):
            mov = {k: av.get(k) for k in ('Physics', 'RotationRate', 'Base', 'bHardAttach', 'bHidden', 'bStatic', 'bMovable') if av.get(k) is not None}
            if mov.get('RotationRate'):
                rr = mov['RotationRate']; mov['rotation_deg_per_s'] = {a: round(rr.get(a, 0) * UU_DEG, 3) for a in ('Pitch', 'Yaw', 'Roll')}
            if mov.get('Base'): mov['Base'] = mov['Base'].rsplit('.', 1)[-1]
            r['movement'] = mov
            if mov.get('Physics') not in (None, 'PHYS_None') or mov.get('Base'):
                out['movers'].append({'actor': p['actor'], 'class': ao.get('class'), 'mesh': p.get('mesh'), **mov,
                                      'referenced_by_kismet': [s.rsplit('.', 1)[-1] for s, _ in A.refs_to(actor) if '.Main_Sequence.' in s]})
        out['props'].append(r)
    # ------------------------------------------------------------------ meshes
    gl_of = {p['mesh']: p.get('gltf') for p in props if p.get('mesh')}
    sub_of = {p['mesh']: p['sublevel'] for p in props if p.get('mesh')}
    tri_ok = bounds_ok = 0; tri_bad = []; bounds_bad = []
    for m in sorted(use):
        mv = A.values(m); mo = A.get(m) or {}
        rec = {'mesh': m, 'uses': use[m], 'authored': sorted((mo.get('props') or {}).keys()),
               **{k: mv.get(k) for k in ('LightMapResolution', 'LightMapCoordinateIndex', 'LODDistanceRatio', 'LODMaxRange',
                                         'TransparentForShadows', 'BodySetup', 'InternalVersion', 'bUsedForInstancing', 'UseSimpleLineCollision',
                                         'UseSimpleBoxCollision', 'UseSimpleRigidBodyCollision') if k in mv}}
        b = mv.get('Bounds') or {}
        if b:
            # BoxSphereBounds is a tagged struct here: omitted fields are struct defaults (zero)
            o = np.array([(b.get('Origin') or {}).get(a, 0.0) for a in 'XYZ']); e = np.array([(b.get('BoxExtent') or {}).get(a, 0.0) for a in 'XYZ'])
            rec['bounds_ue'] = {'origin': o.round(3).tolist(), 'box_extent': e.round(3).tolist(), 'sphere_radius': b.get('SphereRadius')}
            g_lo, g_hi = ue_points_to_gltf([o - e])[0], ue_points_to_gltf([o + e])[0]
            rec['bounds_gltf'] = {'min': np.minimum(g_lo, g_hi).round(4).tolist(), 'max': np.maximum(g_lo, g_hi).round(4).tolist()}
        secs = None
        for cand in [sub_of[m]] + [s for s in subs if s != sub_of[m]]:
            secs = smsections.sections(cand, m)
            if secs: rec['sections_from'] = cand; break
        rec['sections'] = [{k: s[k] for k in ('index', 'material', 'num_triangles', 'enable_collision', 'cast_shadow')} for s in secs or []]
        rec['triangles_lod0_cooked'] = sum(s['num_triangles'] for s in secs or [])
        gl = gl_of.get(m)
        rec['gltf'] = gl
        if gl and os.path.exists(os.path.join(ROOT, gl)):
            g, bins = load_gltf(os.path.join(ROOT, gl))
            T, Ps = 0, []
            for pr in g['meshes'][0]['primitives']:
                if 'indices' in pr: T += g['accessors'][pr['indices']]['count'] // 3
                P = accessor(g, bins, pr['attributes']['POSITION'])
                if len(P): Ps.append(P)
            rec['triangles_gltf'] = T
            if Ps:
                P = np.concatenate(Ps); rec['gltf_bbox'] = {'min': P.min(0).round(4).tolist(), 'max': P.max(0).round(4).tolist()}
            if T == rec['triangles_lod0_cooked']: tri_ok += 1
            else: tri_bad.append((m, T, rec['triangles_lod0_cooked']))
            if Ps and b:
                tol = 0.01 + 0.002 * float(np.linalg.norm(np.array(rec['bounds_gltf']['max']) - np.array(rec['bounds_gltf']['min'])))
                inside = bool((P.min(0) >= np.array(rec['bounds_gltf']['min']) - tol).all() and (P.max(0) <= np.array(rec['bounds_gltf']['max']) + tol).all())
                bounds_ok += inside
                if not inside: bounds_bad.append(m)
        out['meshes'][m] = rec
    # ------------------------------------------------------------------ stats
    P = out['props']
    def cnt(f): return dict(Counter(f(x) for x in P))
    out['stats'] = {
        'props': len(P), 'unique_meshes': len(out['meshes']), 'containers': cnt(lambda x: x['container_class']),
        'prefab_props': sum(1 for x in P if x['prefab']), 'tags': dict(Counter(x['tag'] for x in P).most_common(8)),
        'cast_shadow_false': sum(1 for x in P if x['render'].get('CastShadow') is False),
        'dynamic_shadow_casters': sum(1 for x in P if x['render'].get('bCastDynamicShadow')),
        'accepts_dynamic_lights': sum(1 for x in P if x['render'].get('bAcceptsDynamicLights')),
        'force_direct_lightmap': sum(1 for x in P if x['render'].get('bForceDirectLightMap')),
        'lightmap_resolution_overrides': sum(1 for x in P if x['lightmap_resolution_source'] == 'component override'),
        'lightmap_resolutions': dict(Counter(x['lightmap_resolution'] for x in P).most_common(10)),
        'accepts_decals_false': sum(1 for x in P if x['render'].get('bAcceptsDecals') is False),
        'cull_distance_volume_opt_out': sum(1 for x in P if x['render'].get('bAllowCullDistanceVolume') is False),
        'draw_distance_set': sum(1 for x in P if x['render'].get('CachedMaxDrawDistance') or x['render'].get('LDMaxDrawDistance')),
        'hidden_in_game': sum(1 for x in P if x['render'].get('HiddenGame')),
        'lighting_channels': cnt(lambda x: ','.join(x['lighting_channels_on'])),
        'movers': dict(Counter(m.get('Physics') for m in out['movers'])),
        'validation': {'gltf_tris_equal_cooked_lod0': '%d/%d' % (tri_ok, tri_ok + len(tri_bad)), 'tri_mismatch': tri_bad[:10],
                       'gltf_inside_authored_bounds': '%d/%d' % (bounds_ok, bounds_ok + len(bounds_bad)), 'bounds_outliers': bounds_bad[:10]}}
    out['notes'] += [
        'Component values are EFFECTIVE (authored delta merged over the archetype chain: stock StaticMeshActor/StaticMeshComponent '
        'templates or prefab archetypes); render_from names the object that set each value.',
        'No component authors CachedMaxDrawDistance/LDMaxDrawDistance and the map has no CullDistanceVolume: props draw at any '
        'distance in the original (bAllowCullDistanceVolume opt-outs are moot on Streets).',
        'LightMapResolution: component override if bOverrideLightMapResolution, else StaticMesh.LightMapResolution (default 64); '
        'the cooked lightmaps themselves are in lightmaps.json.']
    path = os.path.join(OUT, 'props_authored.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['stats'], default=str)[:3000]); print('->', path)

if __name__ == '__main__':
    main()
