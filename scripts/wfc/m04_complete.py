"""Canonical MP_IAC_Streets map description (M04).

Writes:
  AssetTools/manifests/mp_iac_streets_complete.json   - one entry point: identity, level hierarchy (persistent level,
      streaming sublevels, companions, dependencies), per-level counts/bounds/flags, world settings, map extents,
      complete counts by category, current-rebuild comparison (percentages), the reasons the rebuild reads as
      incomplete, handoffs, and links to every focused manifest / render file (relative paths).
  ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/render_index.json - deterministic list of every render layer of
      the full authored map: existing files + the authored renderables not yet in world.glb (domination totems,
      destructible intact mesh) + per-object authored state that changes rendering (hidden objective bases, movers).
Run after m04_bsp.py, m04_inventory.py, m04_kismet.py and the M03 builders.
"""
import json, os, sys, time
from collections import Counter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from m03_common import write, MANI, field, CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import VS, ROOT  # noqa: E402

MAP = 'MP_IAC_Streets'
LEVELS = [MAP + '_BASE_m', MAP + '_ART_m', MAP + '_AUDIO_m']
SLICE = os.path.join(VS, 'Maps', MAP)
REL = 'VerticalSlice/Maps/' + MAP + '/'

SKY = lambda m: any(t in m for t in ('SpaceDome', 'CityBackdrop'))

def J(path): return json.load(open(path, encoding='utf-8'))

def prop_aabbs(props, meshes):
    out = []
    for x in props:
        b = (meshes.get(x['mesh']) or {}).get('bounds_ue')
        m = np.array(x['ue_matrix'], 'f8')
        if not b:
            out.append((m[3, :3], m[3, :3])); continue
        o = np.array(b['origin']); e = np.array(b.get('extent') or b.get('box_extent') or [0, 0, 0])
        cs = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) * e + o
        w = np.c_[cs, np.ones(8)] @ m
        out.append((w[:, :3].min(0), w[:, :3].max(0)))
    return out

def main():
    inv = J(os.path.join(MANI, 'streets_actor_inventory.json'))
    diff = J(os.path.join(MANI, 'streets_rebuild_diff.json'))
    bspa = J(os.path.join(MANI, 'streets_bsp_audit.json'))
    lit = J(os.path.join(MANI, 'streets_lighting_audit.json'))
    kis = J(os.path.join(MANI, 'streets_kismet.json'))
    pref = J(os.path.join(MANI, 'streets_prefabs.json'))
    props = J(os.path.join(SLICE, 'props.json'))['props']
    pa = J(os.path.join(SLICE, 'props_authored.json'))
    lm = J(os.path.join(SLICE, 'lightmaps.json'))
    au = J(os.path.join(SLICE, 'audio.json')); fx = J(os.path.join(SLICE, 'map_fx.json')); li = J(os.path.join(SLICE, 'lighting.json'))
    gp = J(os.path.join(SLICE, 'gameplay.json')); nav = J(os.path.join(SLICE, 'navigation.json'))
    d = A.con(); invdb = objtree.inv()
    # ---------------- hierarchy
    base = LEVELS[0]
    wi = base + '.TheWorld.PersistentLevel.TnWorldInfo_15559'
    streaming = [{'object': o, 'class': A.get(o)['class'], 'PackageName': A.get(o)['props'].get('PackageName'),
                  'confidence': CONF} for o in A.values(wi).get('StreamingLevels') or []]
    lss = A.get(base + '.Default')['props'] if A.get(base + '.Default') else None
    pk_rows = invdb.execute("SELECT package, family, role, export_count, uncompressed_size FROM packages WHERE family LIKE ? OR package LIKE ?",
                            (MAP + '%', '%' + MAP.upper() + '%')).fetchall()
    deps = {lv: sorted(r[0] for r in invdb.execute('SELECT depends_on FROM package_deps WHERE package=?', (lv,)).fetchall()) for lv in LEVELS}
    per_level = {}
    for lv in LEVELS:
        acts = [a for a in inv['actors'] if a['package'] == lv]
        L = np.array([[a['transform']['Location'].get(k, 0) for k in ('X', 'Y', 'Z')] for a in acts if a['class'] not in ('TnWorldInfo', 'Model', 'ModelComponent')])
        wv = [o for o, c in d.execute("SELECT opath, class FROM objects WHERE package=? AND class='TnWorldInfo'", (lv,)).fetchall()]
        per_level[lv] = {'level_object': lv + '.TheWorld.PersistentLevel', 'world_info': wv[0] if wv else None,
                         'role': 'persistent level (gameplay/design: starts, pickups, objectives, volumes, Kismet, movers)' if lv == base else
                                 ('art sublevel (static meshes, BSP, lights, decals, emitters, fog, destructible)' if lv.endswith('_ART_m')
                                  else 'audio sublevel (ambient sounds, audio zones, reverb Kismet)'),
                         'streaming': 'persistent' if lv == base else 'LevelStreamingKismet in persistent WorldInfo.StreamingLevels; '
                                      'LevelStreamingState "Default": LevelVisible=true',
                         'level_transform': 'none (UE3 streaming levels have no offset; all placements are world space)',
                         'actors': len(acts), 'components': sum(len(a['components']) for a in acts),
                         'actor_location_bounds_ue': [L.min(0).tolist(), L.max(0).tolist()] if len(L) else None,
                         'world_info_flags': {k: v for k, v in (A.get(wv[0])['props'] if wv else {}).items()
                                              if k.startswith('b') or k in ('CameraTimeStepSeconds', 'FlushTextureStreamingOnInitialLoad',
                                                                            'ServerShouldWaitForAllClientsToFullyLoad')},
                         'package_dependencies': deps[lv]}
    hierarchy = {
        'persistent_level_package': base, 'streaming_levels': streaming, 'level_streaming_state': lss,
        'kismet_streaming_actions': 'none: no SeqAct_LevelStreaming / SeqAct_LevelVisibility in any Streets sequence',
        'normal_play_coexistence': {'value': 'BASE + ART + AUDIO all loaded and visible for the whole match', 'confidence': CONF,
                                    'evidence': 'LevelStreamingState "Default" lists both sublevels LevelVisible=true; nothing in Kismet '
                                                'streams them out'},
        'companions': [{'package': r[0], 'family': r[1], 'role': r[2], 'exports': r[3], 'bytes': r[4]} for r in pk_rows],
        'closure': {'normal_play_level_references': [s['PackageName'] for s in streaming],
                    'all_resolved': all(invdb.execute('SELECT 1 FROM packages WHERE package=?', (s['PackageName'],)).fetchone() for s in streaming)},
        'levels': per_level}
    # ---------------- extents
    meshes = pa.get('meshes') or {}
    ab = prop_aabbs(props, meshes)
    mn = np.min([a for a, b in ab], 0); mx = np.max([b for a, b in ab], 0)
    starts = [a for a in inv['actors'] if 'PlayerStart' in a['class']]
    S = np.array([[a['transform']['Location'][k] for k in ('X', 'Y', 'Z')] for a in starts])
    navs = np.array([[n['location_ue'][i] for i in range(3)] for n in nav['nodes'] if n.get('location_ue')]) if nav.get('nodes') and nav['nodes'][0].get('location_ue') else None
    vols = [a for a in inv['actors'] if a['class'] == 'BlockingVolume']
    core = [b for b in ab if np.all(b[0] > S.min(0) - 20000) and np.all(b[1] < S.max(0) + 20000)]
    extents = {
        'authored_world_bounds_ue (union of every placed static-mesh AABB)': [mn.round(1).tolist(), mx.round(1).tolist()],
        'authored_world_size_m': ((mx - mn) / 100).round(1).tolist(),
        'largest_contributors': sorted(({'mesh': x['mesh'], 'aabb_size_m': ((b - a) / 100).round(1).tolist()} for x, (a, b) in zip(props, ab)),
                                       key=lambda r: -max(r['aabb_size_m']))[:5],
        'world_bounds_excluding_sky_and_backdrop_ue': [np.min([a for x, (a, b) in zip(props, ab) if not SKY(x['mesh'])], 0).round(1).tolist(),
                                                       np.max([b for x, (a, b) in zip(props, ab) if not SKY(x['mesh'])], 0).round(1).tolist()],
        'world_size_excluding_sky_and_backdrop_m': ((np.max([b for x, (a, b) in zip(props, ab) if not SKY(x['mesh'])], 0) -
                                                     np.min([a for x, (a, b) in zip(props, ab) if not SKY(x['mesh'])], 0)) / 100).round(1).tolist(),
        'playable_bounds_ue (player starts)': [S.min(0).round(1).tolist(), S.max(0).round(1).tolist()],
        'playable_size_m (player starts)': ((S.max(0) - S.min(0)) / 100).round(1).tolist(),
        'navigation_bounds_ue': [navs.min(0).round(1).tolist(), navs.max(0).round(1).tolist()] if navs is not None else 'see navigation.json',
        'vertical_bounds_ue': {'player_starts_z': [float(S[:, 2].min()), float(S[:, 2].max())],
                               'geometry_z': [float(mn[2]), float(mx[2])]},
        'background_geometry': 'CityBackdrop_STAT x2, SpaceDome_STATMESH, distant towers/buildings - included in props.json',
        'outlier_actor': 'TnStaticDestructibleActor_14465 at Z=-352 (only actor above Z=-50000; outside play space)',
        'level_regions': {'value': len(au.get('zones') or []), 'basis': 'authored audio zones (Kismet SeqEvent_Touch volumes), '
                          'the only authored region partition of the playable space', 'names': [z.get('comment') for z in au.get('zones') or []]},
        'gameplay_spaces': {'spawn_clusters': sum(1 for a in inv['actors'] if a['class'] == 'TnSpawnCluster'),
                            'koth_zones': 5, 'domination_points': 3, 'ctf_bases': 2, 'bomb_sites': 2},
        'confidence': CONF + ' (positions/bounds from cooked transforms and StaticMesh Bounds)'}
    # ---------------- counts
    ac = Counter(a['class'] for a in inv['actors'])
    cc = Counter(c['class'] for a in inv['actors'] for c in a['components'])
    vis_comp = {k: cc.get(k, 0) for k in ('StaticMeshComponent', 'SkeletalMeshComponent', 'ParticleSystemComponent', 'DecalComponent', 'ModelComponent', 'HeightFogComponent')}
    counts = {'placed_actors': len(inv['actors']), 'placed_components': sum(cc.values()),
              'actors_by_class': dict(sorted(ac.items())), 'components_by_class': dict(sorted(cc.items())),
              'visible_components': vis_comp,
              'bsp': {k: bspa['levels'][MAP + '_ART_m'][k] for k in ('nodes', 'surfaces', 'points', 'triangles_in_render_elements', 'render_elements', 'model_components')},
              'static_meshes': {'placed': len(props), 'unique_meshes': len({x['mesh'] for x in props})},
              'movers': sum(1 for a in inv['actors'] if a['class'] in ('StaticInterpActor', 'InterpActor')),
              'destructibles': ac.get('TnStaticDestructibleActor', 0), 'decals': len(fx['decals']),
              'lights': {k: cc.get(k, 0) for k in ('PointLightComponent', 'SpotLightComponent', 'DirectionalLightComponent', 'SkyLightComponent')},
              'lightmaps': lit['by_lightmap_type'], 'lightmap_atlases_png': len(os.listdir(os.path.join(SLICE, 'lightmaps'))),
              'fx': {'particle_components': len(fx['particle_components']), 'level_emitters': ac.get('Emitter', 0),
                     'pickup_fx_components': 37, 'destructible_fx_factories': 2},
              'audio': {k: au['counts'][k] for k in ('point', 'line', 'volume', 'zones', 'reverb_presets', 'cues')},
              'pickups': {k: ac.get(k, 0) for k in ('TnAmmoCratePickupFactory', 'TnHealthPickupFactory', 'TnOverShieldPickupFactory')},
              'starts': {k: ac.get(k, 0) for k in ('TnTeamPlayerStart', 'TnFreeForAllPlayerStart')},
              'objectives': {k: ac.get(k, 0) for k in ('TnGameObjectivePickupFactoryFlag', 'TnGameObjectivePickupFactoryBomb', 'TnFlagCapturePoint',
                                                       'TnBombPlantPoint', 'TnDominationPoint', 'TnKingOfTheHillZone')},
              'volumes': {k: ac.get(k, 0) for k in ('BlockingVolume', 'TriggerVolume', 'TnForcedDirVolume', 'TnSpawnCluster')},
              'kismet': kis['counts'], 'prefabs': {'instances': pref['prefab_instances'], 'members': pref['members'],
                                                   'uncovered_members': len(pref['uncovered_members'])}}
    # ---------------- comparison
    cm = diff['classification_counts']['components']
    visible_kinds = ('StaticMeshComponent', 'SkeletalMeshComponent', 'ParticleSystemComponent', 'DecalComponent')
    vis = [c for a in inv['actors'] for c in a['components'] if c['class'] in visible_kinds and c.get('classification') != 'CONTAINER / NON-RENDERED AUTHORED OBJECT']
    vc = Counter(c['classification'] for c in vis)
    nvis = len(vis) + 540 + 1  # + BSP render elements + destructible actor
    comparison = {
        'visible_authored_render_items': {'static/skeletal/particle/decal components': len(vis), 'bsp_render_elements': 540,
                                          'destructible_actor': 1, 'total': nvis},
        'by_classification (visible components)': dict(vc),
        'percent_of_visible_items_present_and_matching': round(100.0 * (vc.get('PRESENT AND MATCHING', 0) + 540) / nvis, 2),
        'percent_missing_or_not_drawn': round(100.0 * (vc.get('MISSING FROM REBUILD', 0) + vc.get('PRESENT BUT INCOMPLETE', 0) + 1) / nvis, 2),
        'percent_wrong_state_or_material': round(100.0 * (vc.get('PRESENT BUT WRONG STATE', 0) + vc.get('PRESENT BUT WRONG MATERIAL', 0)) / nvis, 2),
        'actor_classification': diff['classification_counts']['actors'],
        'non_matching_detail': 'manifests/streets_rebuild_diff.json',
        'evidence': 'slice exports + Rendering lane renderer-dump audit (%s)' % inv['sources']['rebuild_render_evidence']['mtime']}
    tv = J(os.path.join(MANI, 'streets_transform_validation.json')) if os.path.exists(os.path.join(MANI, 'streets_transform_validation.json')) else {'stats': {}}
    ts = tv['stats']
    comparison['transform_fix (StaticMeshCollectionActor component scale, this pass)'] = {
        'components_checked': ts.get('components_checked'), 'exact_matches': ts.get('exact_matches'),
        'pre_fix_export_wrong_transform': ts.get('smca_records_changed_vs_before'),
        'mirrored_det_negative': ts.get('mirrored_det_negative'), 'any_negative_axis': ts.get('any_negative_axis'),
        'note': 'The pre-fix world.glb / collision drew these components with CachedParentToWorld only (component Scale*Scale3D dropped): '
                'PRESENT BUT WRONG TRANSFORM in any rebuild still loading the pre-fix export. The Rendering audit statuses quoted '
                'above were measured against that pre-fix world.glb and do not cover transform correctness.',
        'details': 'manifests/streets_transform_validation.json, manifests/streets_transform_fix_audit.json'}
    why = [
        {'cause': 'PRIMARY (fixed in this export): %s of 1906 StaticMeshCollectionActor meshes were exported without their component '
                  'Scale*Scale3D - wrong size and %s mirrored copies drawn un-mirrored; collision had the same error (RE M04 native-scene '
                  'report)' % (ts.get('smca_records_changed_vs_before'), ts.get('mirrored_det_negative')), 'items': ts.get('smca_records_changed_vs_before'),
         'confidence': CONF},
        {'cause': 'all 45 particle components (8 level steam emitters + 37 pickup effects) are exported but not drawn', 'items': 45, 'confidence': CONF},
        {'cause': 'all 70 ambient-sound actors (40 point, 13 line, 17 volume) + 9 audio zones/reverb + 11 positional one-shot pools: exported in '
                  'audio.json; Experimental M03 measured 0 active (Systems runtime since in progress)', 'items': 70, 'confidence': HIGH},
        {'cause': 'animated environment drawn frozen: 3 PHYS_Rotating DecoSphere domes (15 deg/s) + SkyBeam Matinee (9 s loop) on 3 actors', 'items': 6, 'confidence': CONF},
        {'cause': 'mode-dependent state ignored: 4 objective-base InterpActors are authored bHidden and only unhidden in CTF/EXT, but are drawn always', 'items': 4, 'confidence': CONF},
        {'cause': '3 domination energon totems (animated SkeletalMesh) not exported', 'items': 3, 'confidence': CONF},
        {'cause': 'AssetTools lightmaps.json lacked 39 actor-placed bindings + 9 coefficient atlases (FIXED in this pass); Rendering binds '
                  'its own lightmaps, so the runtime effect depends on which binding the renderer used', 'items': 39, 'confidence': CONF},
        {'cause': '360 of 540 BSP render elements carry no static light interactions (LightMapType 0); authored, not an export defect', 'items': 360, 'confidence': CONF},
        {'cause': 'LightsVisibilitiesVolume not implemented (semantics UNKNOWN)', 'items': 1, 'confidence': CONF},
        {'cause': 'not missing geometry: BSP 2460/2460 triangles, 1952/1952 placed static meshes, 25/25 decals, 268/268 light components, '
                  '0 rebuild-only extras, 3 sublevels all loaded; the authored playable footprint is ~%.0f x %.0f m' %
                  tuple(extents['playable_size_m (player starts)'][:2]), 'confidence': CONF}]
    files = {
        'focused_manifests (AssetTools/manifests/)': {
            'streets_actor_inventory.json': 'every placed actor + component, transforms, flags, classification',
            'streets_rebuild_diff.json': 'classification counts + every non-matching record',
            'streets_bsp_audit.json': 'BSP model, surfaces, render elements, node accounting',
            'streets_lighting_audit.json': 'per StaticMeshComponent lightmap type + binding',
            'streets_movers.json': 'movers / rotating / Matinee', 'streets_prefabs.json': 'PrefabInstance members -> placed objects',
            'streets_kismet.json': 'sequence graph + actor relationships', 'future_hud_handoff.json': 'HUD/objective references',
            'streets_destructibles.json': 'destructible (M03)', 'streets_pickup_factories.json': 'pickups (M03)',
            'streets_pickup_fx.json': 'pickup FX decoded (M03)', 'streets_surface_audio.json': 'surface audio (M03)',
            'vertical_slice_audio_concurrency.json': 'cue concurrency (M03)'},
        'render_and_world_data (ExtractedAssets/%s)' % REL: {
            'world.glb': 'BSP + every placed static mesh (instanced)', 'render_index.json': 'full-map render layer index (this pass)',
            'props.json': 'placed meshes', 'props_authored.json': 'authored per-component render/movement flags',
            'lightmaps.json': 'texture-lightmap bindings (all levels, this pass)', 'lightmaps/': 'atlas PNGs',
            'map_fx.json': 'decals + particle components', 'lighting.json': 'lights, fog, channels', 'postprocess.json': 'post process + CLUT',
            'materials_authored.json': 'map materials', 'audio.json': 'ambient audio placement/zones',
            'gameplay.json': 'starts, pickups, objectives, modes, Kismet, Matinee', 'physics.json': 'collision/physics',
            'collision_pawn.glb': 'pawn collision world', 'collision_weapon.glb': 'weapon-trace collision world',
            'navigation.json': 'path network', 'spawnpoints.json': 'starts/clusters'}}
    world = {'world_info': wi, 'DefaultPostProcessSettings': A.values(wi).get('DefaultPostProcessSettings'),
             'LevelCamera': A.values(wi).get('LevelCamera'), 'AnnouncerSoundEventSet': A.values(wi).get('AnnouncerSoundEventSet'),
             'height_fog / lights / post process': 'lighting.json + postprocess.json (M02 passes)', 'confidence': CONF}
    out = {'map': MAP, 'generated': time.strftime('%Y-%m-%d %H:%M'), 'generated_by': 'AssetTools/scripts/wfc/m04_complete.py',
           'identity': {'map': MAP, 'game_mode_playlists': [m['tag'] for m in gp.get('modes') or []],
                        'packages': [base, MAP + '_ART_m', MAP + '_AUDIO_m'], 'persistent': base},
           'hierarchy': hierarchy, 'world_settings': world, 'extents': extents, 'counts': counts,
           'current_rebuild_comparison': comparison, 'why_the_rebuild_reads_as_incomplete': why,
           'presentation_vs_mode_logic': {
               'always_relevant_presentation': ['world.glb geometry', 'decals', 'lights/lightmaps/fog/post', '8 level steam emitters',
                                                'movers (rotating domes, SkyBeam Matinee)', 'ambient audio', 'pickup factories + their FX (all modes)',
                                                'domination totems (placed in every mode; behaviour DOM-only, native)'],
               'game_mode_specific': ['objective-base InterpActors (CTF / EXT unhide)', 'flag factories (SingleFlagCTF)', 'bomb factory (ScoreBombingRun)',
                                      'TnFlagCapturePoint / TnBombPlantPoint / TnKingOfTheHillZone / TnDominationPoint logic', 'team vs FFA starts']},
           'files': files}
    write('mp_iac_streets_complete.json', out)
    # ---------------- render index
    ri = {'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/m04_complete.py', 'coordinate_system': 'see map.json (glTF Y-up metres)',
          'layers': {'world.glb': {'contains': 'BSP (540 render elements, 2460 triangles) + 1952 placed static meshes', 'complete': True},
                     'lightmaps.json + lightmaps/': {'bindings': lm['count'], 'atlases': len(os.listdir(os.path.join(SLICE, 'lightmaps')))},
                     'map_fx.json': {'decals': len(fx['decals']), 'particle_components': len(fx['particle_components'])},
                     'lighting.json': {'light_components': 268}, 'postprocess.json': {}, 'audio.json': au['counts']},
          'not_in_world_glb (authored renderables)': [], 'authored_render_state': []}
    for a in inv['actors']:
        if a['class'] == 'TnDominationPoint':
            sk = next(c for c in a['components'] if c['class'] == 'SkeletalMeshComponent')
            ri['not_in_world_glb (authored renderables)'].append({
                'actor': a['actor'], 'kind': 'domination energon totem (SkeletalMesh)', 'mesh': sk.get('SkeletalMesh'),
                'gltf': 'content/PROP_NEU_Pickups_p/EnergonTotem/NEU_EnergonTotem_SKEL.gltf',
                'anim': 'content/PROP_NEU_Pickups_p/EnergonTotem/NEU_EnergonTotem_ANM.anim.gltf',
                'idle_anim (DeactivatedLoopAnim)': A.values(a['actor']).get('DeactivatedLoopAnim'),
                'transform': a['transform'], 'CastShadow': sk.get('CastShadow'), 'confidence': CONF})
        if a['class'] == 'TnStaticDestructibleActor':
            ri['not_in_world_glb (authored renderables)'].append({
                'actor': a['actor'], 'kind': 'destructible (intact state mesh)', 'mesh': 'DES_IAC_WallPanelSign_p.Meshes.WallPanelSign_Base_STAT',
                'gltf': 'content/DES_IAC_WallPanelSign_p/Meshes/WallPanelSign_Base_STAT.gltf', 'transform': a['transform'],
                'component_translation_ue': [0, 0, -160], 'details': 'manifests/streets_destructibles.json', 'note': 'outside the playable space',
                'confidence': CONF})
        if a['class'] == 'InterpActor' and a['bHidden']:
            ri['authored_render_state'].append({'actor': a['actor'], 'state': 'bHidden=true at load; Kismet UnHide in CTF and EXT only',
                                                'in_world_glb': True, 'confidence': CONF})
        if a['Physics'] == 'PHYS_Rotating' or a['actor'].rsplit('.', 1)[-1] in {x['actor'] for m in gp.get('matinee') or [] for x in m.get('actors') or []}:
            ri['authored_render_state'].append({'actor': a['actor'], 'state': ('PHYS_Rotating %s' % A.values(a['actor']).get('RotationRate'))
                                                if a['Physics'] == 'PHYS_Rotating' else 'SkyBeam Matinee track (streets_movers.json)',
                                                'in_world_glb': True, 'confidence': CONF})
    ri['not_drawn_but_exported'] = {'particle_components': len(fx['particle_components']), 'ambient_audio_actors': 70}
    # ---------------- game-mode visual state (exact rule-class match on the mode's Rules list)
    # sources: authored Kismet (streets_kismet.json: GameplayStarted -> SeqCond_GameRuleActive -> SeqAct_ToggleHidden UnHide),
    # authored class defaults (bHidden, RequiredGameRuleClass), and the RE script decompilation of the PostBeginPlay /
    # InitialState gates (RE-Workspace/notes/MILESTONE04_STREETS_RUNTIME_SEMANTICS.md section 4, read-only).
    MODES = ['DM', 'TDM', 'CTF', 'EXT', 'DOM', 'KOTH']
    def row(shown, how, conf, collision=None, extra=None):
        r = {'visible_by_mode': {m: (m in shown) for m in MODES}, 'mechanism': how, 'confidence': conf}
        if collision: r['collision'] = collision
        if extra: r.update(extra)
        return r
    rules = {
        'InterpActor (objective bases, authored bHidden)': row({'CTF', 'EXT'},
            'authored bHidden=true; Kismet UnHide when GameRuleActive(SingleFlagCTF) or (ScoreBombingRun)', CONF,
            'collides while hidden (stock UE3 SetHidden does not change collision; HIGH)'),
        'TnDominationPoint': row({'DOM'}, 'PostBeginPlay: !HasRule(ScoreDomination) -> InitialState Inactive -> SetHidden(true)', CONF,
            'cylinder kept, Touch/UnTouch ignored', {'note': 'idle anim EnergonTotem_StandBy starts in every mode (hidden outside DOM)'}),
        'TnKingOfTheHillZone': row(set(), 'class default bHidden=true; in KOTH only the randomly chosen active zone is shown '
                                   '(ActivateNewZone) with ActiveMesh FX_Mesh_p.Mesh.pTorus1_STAT', CONF,
                                   extra={'visible_by_mode_note': {'KOTH': 'one active zone at a time'}}),
        'TnGameObjectivePickupFactoryFlag': row({'CTF'}, 'RequiredGameRuleClass SingleFlagCTF; otherwise InitialState Disabled '
                                                '(SetHidden + SetCollision(false,false))', CONF, 'none outside CTF'),
        'TnGameObjectivePickupFactoryBomb': row({'EXT'}, 'RequiredGameRuleClass ScoreBombingRun; otherwise Disabled', CONF, 'none outside EXT'),
        'TnFlagCapturePoint': row(set(), 'no visual component; objective logic + HUD marker only in CTF', CONF),
        'TnBombPlantPoint': row(set(), 'no placed visual; objective logic + HUD marker only in EXT (PlantedBombMesh spawned on plant)', CONF),
        'TnAmmoCratePickupFactory / TnHealthPickupFactory / TnOverShieldPickupFactory': row(set(MODES),
            'no mode gate', CONF)}
    targets = {'TnDominationPoint': [], 'TnKingOfTheHillZone': [], 'TnGameObjectivePickupFactoryFlag': [],
               'TnGameObjectivePickupFactoryBomb': [], 'TnFlagCapturePoint': [], 'TnBombPlantPoint': []}
    bases = []
    for a in inv['actors']:
        if a['class'] in targets: targets[a['class']].append(a['actor'])
        if a['class'] == 'InterpActor' and a['bHidden']: bases.append(a['actor'])
    ri['mode_visual_state'] = {
        'modes': MODES, 'rule_match': 'exact rule-class match against the mode Rules list (GameInfo.HasRule)',
        'by_class': {k: dict(v, actors=(bases if k.startswith('InterpActor') else targets.get(k, 'all instances')))
                     for k, v in rules.items()}}
    tdm_hidden = []
    for k, v in ri['mode_visual_state']['by_class'].items():
        if isinstance(v['actors'], list) and not v['visible_by_mode']['TDM']:
            tdm_hidden += [{'actor': x, 'class': k, 'collision': v.get('collision')} for x in v['actors']]
    ri['tdm_render_state'] = {
        'mode': 'TDM (Civil War, vertical-slice mode; DM identical)',
        'hide': tdm_hidden,
        'note': 'objective bases (4) remain in world.glb but must not be drawn; totems are not in world.glb (render_index '
                'not_in_world_glb lists them) and must not be spawned visible; KOTH rings are template components, do not '
                'instance; flag/bomb factories are Disabled (no draw, no collision). Ammo/health/overshield pickups are active.',
        'confidence': CONF}
    # KOTH active-zone rings: class template component ActiveMeshComponent0 (no instance cooked in the level; created at
    # spawn from TransContent.Default__TnKingOfTheHillZone), placed with the zone actor transform (DrawScale3D applies).
    import smsections
    from vs_common import ue_actor_matrix, ue_to_gltf_matrix
    tmpl = 'TransContent.Default__TnKingOfTheHillZone.ActiveMeshComponent0'
    tv = A.values(tmpl); kz = A.values('TransContent.Default__TnKingOfTheHillZone')
    tmesh = tv.get('StaticMesh')
    secs = smsections.sections(MAP + '_BASE_m', tmesh) or []
    def v3(d, keys, dflt):
        return [d.get(k, dflt) for k in keys] if isinstance(d, dict) else list(d or [dflt] * 3)
    for a in inv['actors']:
        if a['class'] != 'TnKingOfTheHillZone': continue
        t = a['transform']
        M = ue_actor_matrix(v3(t['Location'], 'XYZ', 0.0), v3(t['Rotation'], ('Pitch', 'Yaw', 'Roll'), 0), t.get('DrawScale', 1.0),
                            v3(t['DrawScale3D'], 'XYZ', 1.0))
        ri['not_in_world_glb (authored renderables)'].append({
            'actor': a['actor'], 'kind': 'KOTH active-zone ring (class template StaticMeshComponent)', 'mesh': tmesh,
            'gltf': 'content/' + tmesh.split('.')[0] + '/Mesh/' + tmesh.rsplit('.', 1)[-1] + '.gltf',
            'component_template': tmpl, 'component_transform': 'identity (template has no Translation/Rotation; Scale 1)',
            'section_materials': [s['material'] for s in secs], 'material_overrides': tv.get('Materials'),
            'transform': t, 'ue_matrix': M.tolist(), 'gltf_matrix': ue_to_gltf_matrix(M),
            'CastShadow': tv.get('CastShadow'), 'CollideActors': tv.get('CollideActors'),
            'runtime_colors (zone class defaults)': {'NeutralColor': kz.get('NeutralColor'), 'CaptureColor': kz.get('CaptureColor')},
            'visible_in_modes': ['KOTH'], 'visibility_rule': 'only the currently active zone (random at MatchStarting, rotates via ActivateNewZone)',
            'confidence': CONF})
    for x in ri['not_in_world_glb (authored renderables)']:
        if 'domination' in x['kind']:
            x['visible_in_modes'] = ['DOM']
            t = x['transform']
            M = ue_actor_matrix(v3(t['Location'], 'XYZ', 0.0), v3(t['Rotation'], ('Pitch', 'Yaw', 'Roll'), 0), t.get('DrawScale', 1.0),
                                v3(t['DrawScale3D'], 'XYZ', 1.0))
            x['ue_matrix'] = M.tolist(); x['gltf_matrix'] = ue_to_gltf_matrix(M)
            x['section_materials'] = 'skeletal mesh slots (see glTF materials)'
            x['component_template'] = 'TransContent.Default__TnDominationPoint.PointMesh0'
    for x in ri['authored_render_state']:
        if x['actor'] in bases:
            x['visible_in_modes'] = ['CTF', 'EXT']; x['tdm'] = 'hidden'
    json.dump(ri, open(os.path.join(SLICE, 'render_index.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print('->', os.path.join(SLICE, 'render_index.json'))
    print(json.dumps({'extents': {k: v for k, v in extents.items() if 'size' in k or 'bounds_ue' in k}, 'comparison': {k: v for k, v in comparison.items() if k.startswith('percent') or k.startswith('visible') or k.startswith('by_')}}, indent=1, default=str))

if __name__ == '__main__':
    main()
