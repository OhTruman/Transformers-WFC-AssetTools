"""Generic map completion: canonical map manifest + render index + completeness report for ANY multiplayer map.

Consumes only generic pipeline outputs (no Streets-specific evidence):
  ExtractedAssets/VerticalSlice/Maps/<MAP>/ {map, props, props_authored, map_fx, lighting, lightmaps, materials_authored,
      collision, physics, navigation, gameplay, audio, postprocess}.json + world.glb / collision*.glb / lightmaps/
  manifests: inventory (streets_actor_inventory.json or next_map/<MAP>_actor_inventory.json), transform validation,
      vs_validate report, frontend_package/mp_registry.json, mp_content/versus_mode_visuals.json
Mode-state rules are class-level script semantics (RE notes MILESTONE04_STREETS_* + script decompilation, read-only): they apply
to every map that places the class. Per-map Kismet visibility comes from gameplay.json (SeqCond_GameRuleActive -> ToggleHidden).
Outputs: manifests/maps/<MAP>/{map_complete,render_index_generic,completeness}.json
  python map_complete.py MP_UND_Gorge        (also run for MP_IAC_Streets as a cross-check against its validated render_index)
"""
import json, os, sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from m03_common import CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import ROOT, VS  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_UND_Gorge'
MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
SLICE = os.path.join(VS, 'Maps', MAP)
OUT = os.path.join(MANI, 'maps', MAP)
GEN = 'AssetTools/scripts/wfc/map_complete.py'
MODES = ['DM', 'TDM', 'CTF', 'EXT', 'DOM', 'KOTH']
RULE_MODE = {'TnGameRules_ScoreBombingRun': 'EXT', 'TnGameRules_SingleFlagCTF': 'CTF', 'TnGameRules_ScoreFlags': 'CTF',
             'TnGameRules_ScoreDomination': 'DOM', 'TnGameRules_ScoreKingOfTheHill': 'KOTH'}
CLASS_RULES = OrderedDict([   # class-level presentation rules (script semantics, CONFIRMED by RE for Streets; class-wide)
    ('TnDominationPoint', {'visible_in': ['DOM'], 'mechanism': 'script PostBeginPlay hides outside DOM (totem anim still started)',
                           'collision_when_hidden': 'n/a (cylinder touch only)'}),
    ('TnKingOfTheHillZone', {'visible_in': ['KOTH'], 'mechanism': 'active-zone ring (class template ActiveMeshComponent0 = pTorus1_STAT) shown only on '
                                                                 'the active zone in KOTH; zone DrawScale3D applies'}),
    ('TnGameObjectivePickupFactoryFlag', {'visible_in': ['CTF'], 'mechanism': 'PostBeginPlay: !HasRule(RequiredGameRuleClass) -> Disabled (hidden, no collision)'}),
    ('TnGameObjectivePickupFactoryBomb', {'visible_in': ['EXT'], 'mechanism': 'as flag'}),
    ('TnFlagCapturePoint', {'visible_in': ['CTF'], 'mechanism': 'inert outside CTF (no mesh on the class default)'}),
    ('TnBombPlantPoint', {'visible_in': ['EXT'], 'mechanism': 'inert outside EXT; PlantedBombMesh NEU_MPBombExplode_SKEL + DetonateEffect on the class default'}),
    ('TnAmmoCratePickupFactory', {'visible_in': MODES, 'mechanism': 'available in every mode; beam + crate mesh while available'}),
    ('TnHealthPickupFactory', {'visible_in': MODES, 'mechanism': 'available in every mode'}),
    ('TnOverShieldPickupFactory', {'visible_in': MODES, 'mechanism': 'available in every mode'})])

def J(p, default=None):
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default
def rel(p): return os.path.relpath(p, ROOT).replace(os.sep, '/')
def slice_(n): return J(os.path.join(SLICE, n), {})
def mani(name):
    """per-map manifest written by a map-agnostic script (m03_common.map_out naming)."""
    return J(os.path.join(MANI, name if MAP == 'MP_IAC_Streets' else 'next_map/%s_%s' % (MAP, name.replace('streets_', ''))), {})

def main():
    os.makedirs(OUT, exist_ok=True)
    streets = MAP == 'MP_IAC_Streets'
    inv = J(os.path.join(MANI, 'streets_actor_inventory.json' if streets else 'next_map/%s_actor_inventory.json' % MAP), {})
    tv = J(os.path.join(MANI, 'streets_transform_validation.json' if streets else 'next_map/%s_transform_validation.json' % MAP), {})
    vv = J(os.path.join(MANI, 'vertical_slice_validation.json' if streets else 'next_map/%s_validation.json' % MAP), {})
    m, props, fx, lt, lm, mats = slice_('map.json'), slice_('props.json'), slice_('map_fx.json'), slice_('lighting.json'), slice_('lightmaps.json'), slice_('materials_authored.json')
    col, phy, nav, gp, au, pp = slice_('collision.json'), slice_('physics.json'), slice_('navigation.json'), slice_('gameplay.json'), slice_('audio.json'), slice_('postprocess.json')
    reg = J(os.path.join(MANI, 'frontend_package', 'mp_registry.json'), {})
    regmap = next((x for x in reg.get('maps', []) if x['internal_name'].lower().startswith(MAP.lower())), None)
    vis = J(os.path.join(MANI, 'mp_content', 'versus_mode_visuals.json'), {}).get('modes', {})
    actors = inv.get('actors', [])
    by_cls = lambda c: [a for a in actors if a['class'] == c]
    # ---------------- mode visual state
    kismet_rules = []
    for r in gp.get('mode_dependent_visibility') or []:
        mode = RULE_MODE.get((r.get('rule') or '').split('.')[-1], r.get('mode_comment'))
        kismet_rules.append({'rule': r.get('rule'), 'mode': mode, 'action': r.get('action'),
                             'targets': [{k: t.get(k) for k in ('actor', 'mesh', 'initially_hidden', 'gltf_matrix')} for t in r.get('targets', [])]})
    kismet_hidden = {t['actor'] for r in kismet_rules if r['action'] == 'UnHide' for t in r['targets'] if t.get('initially_hidden')}
    mode_state = OrderedDict()
    for cls, rule in CLASS_RULES.items():
        acts = by_cls(cls)
        if acts: mode_state[cls] = {**rule, 'actors': [a['actor'].rsplit('.', 1)[-1] for a in acts], 'count': len(acts),
                                    'source': 'class script semantics (RE MILESTONE04_STREETS_RUNTIME_SEMANTICS / decomp) - ' + CONF}
    if kismet_hidden:
        mode_state['Kismet-hidden objective props'] = {'visible_in': sorted({r['mode'] for r in kismet_rules if r['action'] == 'UnHide'}),
                                                       'actors': sorted(kismet_hidden), 'mechanism': 'bHidden=true, SeqCond_GameRuleActive -> SeqAct_ToggleHidden UnHide; '
                                                       'collision stays on while hidden', 'source': 'gameplay.json (map Kismet) - ' + CONF}
    tdm_hidden = sorted({x for k, v in mode_state.items() if 'TDM' not in v['visible_in'] for x in v['actors']})
    # ---------------- movers
    movers = [{'actor': a['actor'].rsplit('.', 1)[-1], 'class': a['class'], 'physics': a.get('Physics'), 'hidden': a.get('bHidden'),
               'rotation_rate': next((c.get('RotationRate') for c in [a] if c.get('RotationRate')), None) or
                                (A.values(a['actor']).get('RotationRate') if A.get(a['actor']) else None)}
              for a in actors if a['class'] in ('InterpActor', 'StaticInterpActor', 'KActor')]
    # ---------------- pickups (generic visuals from class defaults)
    picks = []
    for p in gp.get('pickups') or []:
        cls = p['class']
        rec = {'actor': p['actor'], 'class': cls, 'gltf_matrix_factory': p.get('gltf_matrix'), 'respawn': (p.get('effective') or {}).get('RespawnTime')}
        if cls == 'TnAmmoCratePickupFactory':
            rec['visual'] = {'mesh': 'PROP_NEU_Pickups_p.AmmoPickup.PROP_NEU_AmmoPickup_STAT', 'at': 'factory origin (CONFIRMED, docs/FORMAT_NOTES.md)',
                             'rotation': 'yaw PickupRotationRate 10000 (54.93 deg/s) while available', 'beam': 'FX_Pickups_p.FX.Pickup_FX'}
        elif cls in ('TnHealthPickupFactory', 'TnOverShieldPickupFactory'):
            rec['visual'] = {'particle': 'FX_Pickups_p.FX.' + ('HealthPickup_FX' if 'Health' in cls else 'OvershieldPickup_FX'),
                             'note': 'mesh-emitter particle (cube / shield) in CustomPickupEffect; no factory mesh'}
        picks.append(rec)
    for o in gp.get('objectives') or []:
        pass
    flag_mesh = (vis.get('CTF') or {}).get('flag_weapon', {}); bomb_mesh = (vis.get('EXT') or {}).get('bomb_weapon', {})
    obj_visuals = [{'actor': a['actor'].rsplit('.', 1)[-1], 'class': a['class'],
                    'resting_mesh': (flag_mesh if 'Flag' in a['class'] else bomb_mesh).get('SkeletalMesh'),
                    'component_translation': (flag_mesh if 'Flag' in a['class'] else bomb_mesh).get('Translation'),
                    'transform': a.get('transform'), 'visible_in': CLASS_RULES[a['class']]['visible_in']}
                   for a in actors if a['class'] in ('TnGameObjectivePickupFactoryFlag', 'TnGameObjectivePickupFactoryBomb')]
    # ---------------- generic enrichments (formerly Streets-only in m04_complete)
    pf = mani('streets_pickup_factories.json'); pfx = mani('streets_pickup_fx.json')
    pickup_fx_index = [{'actor': i['actor'].rsplit('.', 1)[-1], 'class': i['class'], 'effects': i.get('effects'),
                        'collision_cylinder': i.get('collision_cylinder'), 'respawn': i.get('RespawnTime')} for i in pf.get('instances') or []]
    if pfx: pickup_fx_index = {'instances': pickup_fx_index, 'systems': {k: {x: v.get(x) for x in ('emitters', 'role', 'usage') if x in v}
                                                                        for k, v in (pfx.get('systems') or {}).items()},
                               'source': 'manifests %s' % ('streets_pickup_*.json' if streets else 'next_map/%s_pickup_*.json' % MAP)}
    dd = mani('streets_destructibles.json')
    from vs_common import ue_actor_matrix, ue_to_gltf_matrix, ue_trans
    import glob as _g
    v3 = lambda x, ks, d: [x.get(k, d) for k in ks] if isinstance(x, dict) else [d] * 3
    val = lambda f: f.get('value') if isinstance(f, dict) and 'value' in f else f
    def gltf_of(mesh):
        g = _g.glob(os.path.join(ROOT, 'content', *mesh.split('.')) + '.gltf') if mesh else []
        return rel(g[0]) if g else None
    destr_actors = []
    for a in dd.get('actors') or []:
        t = a.get('transform') or {}
        A_ = ue_actor_matrix(v3(val(t.get('Location')), 'XYZ', 0.0), v3(val(t.get('Rotation')), ('Pitch', 'Yaw', 'Roll'), 0),
                             val(t.get('DrawScale')) or 1.0, v3(val(t.get('DrawScale3D')), 'XYZ', 1.0))
        states = []
        for pc in a.get('pieces') or []:
            ppos = (val(pc.get('Transform')) or {}).get('Position') or {}
            PT = ue_trans([ppos.get('X', 0), ppos.get('Y', 0), ppos.get('Z', 0)])
            for st in pc.get('states') or []:
                sm = [e['authored'].get('Mesh') for e in st.get('effects') or [] if e['class'] == 'HmStaticMeshDestructionEffectFactory' and e['authored'].get('Mesh')]
                sk = [e['authored'].get('ComponentTemplate') for e in st.get('effects') or [] if e['class'] == 'HmAnimatedMeshDestructionEffectFactory']
                Ms = PT @ A_
                states.append({'piece': pc.get('PieceName'), 'handle': st.get('handle'),
                               'static_meshes': [{'mesh': m_, 'gltf': gltf_of(m_), 'gltf_matrix': ue_to_gltf_matrix(Ms)} for m_ in sm],
                               'animated_mesh_templates': sk or None,
                               'effects': dict(Counter(e['class'] for e in st.get('effects') or []))})
        destr_actors.append({'actor': (a.get('actor') or '').rsplit('.', 1)[-1], 'class': a.get('class'), 'blueprint': (a.get('blueprint') or {}).get('object'),
                             'actor_gltf_matrix': ue_to_gltf_matrix(A_), 'states': states})
    destr_index = {'count': dd.get('count', 0), 'actors': destr_actors,
                   'composition': 'state static meshes = piece translation x actor matrix (UE row vectors); CONFIRMED for Streets '
                                  '(cooked per-state StaticMeshComponents carry exactly the piece Translation), applied generically',
                   'initial_state': 'handle 0 (engine convention, HIGH; Streets M03)',
                   'source': 'destructibles manifest (full state machines, particles, sounds, links)'}
    skel = []
    for a in [x for x in actors if x['class'] in ('SkeletalMeshActor', 'HmSkeletalMeshActor', 'TnTransformingWorldActor')]:
        comp = next((c for c in a.get('components') or [] if 'SkeletalMeshComponent' in (c.get('class') or '')), {})
        mesh = comp.get('SkeletalMesh') or (A.values(comp['component']).get('SkeletalMesh') if comp.get('component') else None)
        t = a.get('transform') or {}
        gm = ue_to_gltf_matrix(ue_actor_matrix(v3(t.get('Location'), 'XYZ', 0.0), v3(t.get('Rotation'), ('Pitch', 'Yaw', 'Roll'), 0),
                                               t.get('DrawScale') or 1.0, v3(t.get('DrawScale3D'), 'XYZ', 1.0)))
        skel.append({'actor': a['actor'].rsplit('.', 1)[-1], 'class': a['class'], 'level': a['actor'].split('.', 1)[0], 'mesh': mesh,
                     'gltf': gltf_of(mesh), 'anim_sets': comp.get('AnimSets'), 'gltf_matrix': gm,
                     'transform_ue': t, 'tag': a.get('Tag'), 'hidden': a.get('bHidden')})
    # ---------------- render index (generic)
    files = {f: rel(os.path.join(SLICE, f)) for f in ('world.glb', 'collision.glb', 'collision_pawn.glb', 'collision_weapon.glb', 'navigation.glb')
             if os.path.exists(os.path.join(SLICE, f))}
    ri = OrderedDict([
        ('generated_by', GEN), ('map', MAP),
        ('layers', {**files, 'lightmaps': rel(os.path.join(SLICE, 'lightmaps.json')) if lm else None, 'map_fx': rel(os.path.join(SLICE, 'map_fx.json')) if fx else None,
                    'lighting': rel(os.path.join(SLICE, 'lighting.json')) if lt else None, 'postprocess': rel(os.path.join(SLICE, 'postprocess.json')) if pp else None,
                    'audio': rel(os.path.join(SLICE, 'audio.json')) if au else None}),
        ('mode_visual_state', mode_state),
        ('tdm_render_state', {'hidden': tdm_hidden, 'count': len(tdm_hidden)}),
        ('kismet_mode_rules', kismet_rules),
        ('pickup_factories', picks), ('objective_factory_resting_meshes', obj_visuals),
        ('movers', movers), ('matinee', gp.get('matinee')),
        ('pickup_effects (component matrices + decoded emitters)', pickup_fx_index),
        ('destructibles', destr_index),
        ('skeletal_actors (not in world.glb: spawn from gltf)', skel),
        ('not_in_world_glb', {'classes': (m.get('unhandled_actor_classes') or {}),
                              'note': 'actor classes vs_map does not export as geometry (skeletal actors, lens flares, fog, sounds, Kismet containers)'})])
    json.dump(ri, open(os.path.join(OUT, 'render_index_generic.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    # ---------------- completeness checks
    st = (tv or {}).get('stats', {})
    nfx = len(fx.get('particle_components', [])); ndec = len(fx.get('decals', []))
    lmo = [p for p in lm.get('props', [])] if lm else []
    checks = OrderedDict()
    def c(name, status, evidence, owner=None, blocker=None):
        checks[name] = {'status': status, 'evidence': evidence, **({'owner': owner, 'blocker': blocker} if blocker else {})}
    c('level_hierarchy', 'COMPLETE' if m.get('sublevels') else 'MISSING', {'sublevels': m.get('sublevels')})
    c('bsp', 'COMPLETE' if any((v.get('render_triangles') or 0) for v in (m.get('bsp') or {}).values()) else 'MISSING',
      {k: {x: v.get(x) for x in ('render_triangles', 'skipped_polys', 'validation_issues')} for k, v in (m.get('bsp') or {}).items()})
    c('placed_meshes', 'COMPLETE' if m.get('props_missing_mesh') == 0 else 'PARTIAL', {'placed': m.get('placed_props'), 'unique': m.get('unique_meshes'), 'missing_mesh': m.get('props_missing_mesh')})
    c('collection_actor_transforms', 'COMPLETE' if st.get('exact_matches') and st.get('exact_matches') == st.get('components_checked') else 'UNVALIDATED',
      {k: st.get(k) for k in ('components_checked', 'exact_matches', 'mirrored_det_negative', 'any_negative_axis', 'non_uniform', 'two_negative_axes_not_mirrored')})
    c('collision', 'COMPLETE' if 'collision.glb' in files and 'collision_pawn.glb' in files else 'PARTIAL',
      {'files': [f for f in files if f.startswith('collision')], 'volumes': Counter(v['class'] for v in (phy.get('volumes') or []))})
    c('lightmaps', 'COMPLETE' if lm and not lm.get('atlases_without_png') else 'PARTIAL',
      {'atlases_used': lm.get('atlases_used') if lm else None, 'without_png': lm.get('atlases_without_png') if lm else None,
       'world_glb_lightmapped_nodes': st.get('world_glb_lightmapped_nodes')})
    c('materials', 'COMPLETE' if mats and not mats.get('missing') else 'PARTIAL', {'count': len(mats.get('materials') or mats.get('records') or []) if mats else None,
                                                                                 'missing': mats.get('missing') if mats else None})
    c('decals', 'EXPORTED' if ndec else 'NONE', {'decals': ndec}, 'RENDERING', 'decal projection is renderer work' if ndec else None)
    hf = (inv.get('actor_counts_by_class') or {}).get('HeightFog', 0); fv = (inv.get('actor_counts_by_class') or {}).get('FogVolumeConstantDensityInfo', 0)
    nfog = len(((lt or {}).get('globals') or {}).get('height_fogs') or [])
    c('fog', ('COMPLETE' if nfog == hf else 'PARTIAL') if hf or fv else 'NONE',
      {'HeightFog_actors': hf, 'height_fogs_in_lighting_json': nfog, 'FogVolumeConstantDensityInfo': fv},
      'ASSETTOOLS' if nfog != hf else ('RENDERING' if hf else None),
      'height fog not exported' if nfog != hf else ('height fog rendering (%d components, lighting.json globals.height_fogs)' % hf if hf else None))
    c('lights', 'COMPLETE' if lt.get('lights') else 'MISSING', {'lights': len(lt.get('lights') or []), 'validation': lt.get('validation')})
    # post-process volumes: CLUT / scene tone per volume and how much of the play space they cover (player starts inside the brush)
    import numpy as _np
    starts_g = [_np.array(x['location_gltf']) for x in gp.get('player_starts') or [] if x.get('location_gltf')]
    def inside(polys, q):
        for poly in polys:
            P = _np.array(poly, float)
            if len(P) < 3: continue
            n = _np.cross(P[1] - P[0], P[2] - P[0]); ln = _np.linalg.norm(n)
            if ln < 1e-9: continue
            c_ = P.mean(0); n = n / ln
            # orient outward: hull centroid is the mean of all vertices
            if _np.dot(n, c_ - hull_c) < 0: n = -n
            if _np.dot(q - P[0], n) > 1e-3: return False
        return True
    ppv = []
    for v in (col.get('volumes') or []):
        if v['class'] != 'PostProcessVolume': continue
        hull_c = _np.array([pt for poly in v['polygons_gltf'] for pt in poly], float).mean(0)
        n_in = sum(1 for q in starts_g if inside(v['polygons_gltf'], q))
        pv = next((x for x in (pp.get('volumes') or []) if x['volume'].endswith(v['actor'])), {})
        ppv.append({'volume': v['actor'], 'player_starts_inside': '%d/%d' % (n_in, len(starts_g)), 'clut': (pv.get('clut') or {}).get('object'),
                    'clut_png': (pv.get('clut') or {}).get('png'), 'scene_tone': pv.get('scene_tone'), 'priority_enabled': pv.get('priority_enabled')})
    c('postprocess', 'COMPLETE' if pp else 'MISSING', dict(({k: pp.get(k) for k in ('scene_chain', 'governing')} if pp else {}),
                                                         world_clut=(pp.get('clut') or {}).get('object') if pp else None, volumes=ppv),
      'RENDERING' if any(x['clut'] for x in ppv) else None,
      'colour grade authored on a PostProcessVolume (CLUT + scene tone): apply volume settings, not only the world CLUT'
      if any(x['clut'] for x in ppv) else None)
    c('map_fx', 'EXPORTED' if nfx else 'NONE', {'particle_components': nfx, 'systems': len(fx.get('particle_systems') or {})},
      'RENDERING', 'particle systems must be simulated by the renderer (decoded module streams via pstream.py)' if nfx else None)
    c('movers', 'AUTHORED', {'count': len(movers), 'physics': Counter(str(x['physics']) for x in movers), 'matinee': len(gp.get('matinee') or [])},
      'GAMEPLAY', 'PHYS_Rotating / Interpolating movers must be animated at runtime' if movers else None)
    c('pickups', 'COMPLETE' if picks else 'NONE', {'count': len(picks), 'by_class': Counter(p['class'] for p in picks)})
    c('player_starts', 'COMPLETE', {k: len(v) if isinstance(v, list) else v for k, v in (gp.get('player_starts') or {}).items()} if isinstance(gp.get('player_starts'), dict)
      else {'count': len(gp.get('player_starts') or [])})
    c('objectives', 'COMPLETE' if gp.get('objectives') else 'NONE', {'count': len(gp.get('objectives') or [])})
    c('mode_hidden_state', 'COMPLETE', {'classes': list(mode_state), 'tdm_hidden': len(tdm_hidden)})
    c('ambient_audio', 'COMPLETE' if au and not au.get('missing_cues') else 'PARTIAL',
      (au or {}).get('counts'))
    c('navigation', 'COMPLETE' if nav else 'MISSING', {'nodes': len(nav.get('nodes') or []), 'edges': len(nav.get('edges') or [])} if nav else None)
    c('loading_metadata', 'COMPLETE' if regmap else 'MISSING', {'loading_screen': (regmap or {}).get('loading_screen')})
    c('thumbnail', 'COMPLETE' if (regmap or {}).get('preview', {}).get('png') else 'MISSING', (regmap or {}).get('preview'))
    c('frontend_name', 'COMPLETE' if (regmap or {}).get('display_name', {}).get('INT') else 'MISSING', (regmap or {}).get('display_name'))
    c('mode_compatibility', 'COMPLETE' if (regmap or {}).get('supported_modes') else 'MISSING', (regmap or {}).get('supported_modes'))
    sa = J(os.path.join(OUT, 'structure_audit.json'), {})
    ba = mani('streets_bsp_audit.json'); bdf = mani('streets_bsp_default_faces.json'); ki = mani('streets_kismet.json'); sau = mani('streets_surface_audio.json')
    cnt = inv.get('actor_counts_by_class') or {}
    c('sublevels', 'COMPLETE' if m.get('sublevels') else 'MISSING', {'sublevels': m.get('sublevels'), 'source': 'name prefix + authored LevelStreaming'})
    c('bsp_alignment', 'COMPLETE' if (ba.get('comparison') or {}).get('difference') == 0 else 'UNVALIDATED', ba.get('comparison'))
    c('bsp_default_material_faces', 'COMPLETE' if bdf.get('counts', {}).get('visible_in_play') == 0 else 'AUTHORED',   # authored DefaultMaterial faces seen in play (Streets: 3, M05)
      bdf.get('counts'), 'RENDERING' if bdf.get('counts', {}).get('visible_in_play') else None,
      'faces authored with EngineMaterials.DefaultMaterial visible in play' if bdf.get('counts', {}).get('visible_in_play') else None)
    c('negative_nonuniform_scales', 'COMPLETE' if st.get('exact_matches') == st.get('components_checked') and (sa.get('mirrored_instances') or {}).get('verdict') == 'CONSISTENT'
      else 'UNVALIDATED', {'mirrored': st.get('mirrored_det_negative'), 'non_uniform': st.get('non_uniform'),
                           'winding': (sa.get('mirrored_instances') or {}).get('verdict')})
    ms = (mats or {}).get('stats') or {}
    c('material_instances', 'COMPLETE' if ms and not ms.get('missing') else 'PARTIAL', {'by_class': ms.get('by_class'), 'masters': ms.get('masters')})
    c('textures', 'COMPLETE' if (lm or {}).get('atlases_without_png') == [] and ms and not ms.get('missing') else 'PARTIAL',
      {'note': 'material texture parameters resolve through materials_authored.json; lightmap atlases as PNG', 'lightmap_pngs':
       len(os.listdir(os.path.join(SLICE, 'lightmaps'))) if os.path.isdir(os.path.join(SLICE, 'lightmaps')) else 0})
    lst = (lt or {}).get('stats') or {}
    c('dynamic_lights', 'COMPLETE', {'by_classification': lst.get('by_classification'), 'built_into_lightmap': lst.get('built_into_lightmap'),
                                     'cast_dynamic_shadows': lst.get('cast_dynamic_shadows'), 'disabled': lst.get('disabled')},
      'RENDERING', 'dynamic (non-lightmapped) lights: %s' % ((lst.get('lights') or 0) - (lst.get('built_into_lightmap') or 0)))
    c('particles', 'EXPORTED' if nfx else 'NONE', {'components': nfx, 'emitter_actors': cnt.get('Emitter', 0)}, 'RENDERING', 'runtime simulation' if nfx else None)
    c('moving_scenery', 'AUTHORED' if movers else 'NONE', {'movers': len(movers), 'in_world_glb_missing': (sa.get('actors') or {}).get('non_collection_actors_missing_from_world_glb')},
      'GAMEPLAY' if movers else None, 'animate PHYS_Rotating / Matinee at runtime' if movers else None)
    c('blocking_volumes', 'COMPLETE', {k: cnt.get(k, 0) for k in ('BlockingVolume', 'TnTransformerBlockingVolume', 'TnForcedDirVolume', 'PhysicsVolume')})
    c('playable_space', 'COMPLETE' if (sa.get('verdict') or {}).get('status') == 'PASS' else 'ATTENTION',
      {k: (sa.get('playable_space') or {}).get(k) for k in ('player_starts', 'starts_on_reachable_floor', 'walk_graph_area_m2', 'bounds', 'placement_checks')})
    c('collision_vs_visible', 'COMPLETE' if (sa.get('verdict') or {}).get('status') == 'PASS' else 'ATTENTION',
      {k: (sa.get('collision_vs_visible') or {}).get(k) for k in ('agreement_pct', 'agreement_pct_excluding_volume_tops', 'blocking_gaps_explained')})
    c('actor_visibility', 'COMPLETE' if not (sa.get('actors') or {}).get('mode_gated_missing_from_world_glb') else 'PARTIAL', sa.get('actors'))
    c('mode_specific_actors', 'COMPLETE', {k: v['count'] if 'count' in v else len(v.get('actors', [])) for k, v in mode_state.items()})
    c('audio_emitters', 'COMPLETE' if au and not au.get('missing_cues') else 'PARTIAL', {k: (au.get('counts') or {}).get(k) for k in ('point', 'volume', 'line', 'cues', 'waves_with_wav')})
    c('zones_reverb', 'COMPLETE' if (au.get('counts') or {}).get('zones') is not None else 'MISSING', {k: (au.get('counts') or {}).get(k) for k in ('zones', 'reverb_presets')},
      'SYSTEMS', 'ambient zones / reverb presets applied at runtime (Kismet SeqAct_AmbientAudioZone / SeqAct_Reverb)')
    c('surface_audio', 'COMPLETE' if sau else 'MISSING', (sau.get('headline') or {}).get('value'))
    out_of_play = []
    bb = (sa.get('playable_space') or {}).get('bounds')
    if bb:
        for p in props.get('props', []):
            x, y, z = p['gltf_matrix'][12:15]
            if not (bb['x_m'][0] - 50 <= x <= bb['x_m'][1] + 50 and bb['z_m'][0] - 50 <= z <= bb['z_m'][1] + 50) or y > bb['floor_height_m'][1] + 150 or y < bb['floor_height_m'][0] - 150:
                out_of_play.append(p['mesh'])
    c('skyline_background_geometry', 'COMPLETE', {'props_outside_playable_bounds_plus_50m': len(out_of_play), 'by_mesh': dict(Counter(out_of_play).most_common(15)),
                                                  'note': 'exported in world.glb like any prop; oversized shells (>2 km) excluded from collision'})
    c('kismet_references', 'COMPLETE' if ki else 'MISSING', {'summary': ki.get('summary'), 'relationships': len(ki.get('actor_relationships') or [])})
    c('destructibles', 'COMPLETE', {'count': dd.get('count', 0)})
    # hazard / kill volumes (PhysicsVolume / DynamicPhysicsVolume with bPainCausing, effective values over the class chain)
    hz = []
    for v in (col.get('volumes') or []):
        if 'PhysicsVolume' not in v['class']: continue
        o = next((o_ for lv in (m.get('sublevels') or []) for o_ in [lv + '.TheWorld.PersistentLevel.' + v['actor']] if A.get(o_)), None)
        ev_ = A.values(o) if o else {}
        if not ev_.get('bPainCausing'): continue
        hz.append({'actor': v['actor'], 'class': v['class'], 'object': o, 'polygons_gltf': v['polygons_gltf'],
                   'DamagePerSec': ev_.get('DamagePerSec'), 'DamageType': ev_.get('DamageType'), 'PainInterval': ev_.get('PainInterval'),
                   'bAIShouldIgnorePain': ev_.get('bAIShouldIgnorePain'), 'bEntryPain': ev_.get('bEntryPain'),
                   'bPhysicsOnContact': ev_.get('bPhysicsOnContact'), 'GroundFriction': ev_.get('GroundFriction'),
                   'kind': 'instant kill' if (ev_.get('DamagePerSec') or 0) >= 1e6 or 'InstantKill' in str(ev_.get('DamageType')) else 'damage over time'})
    json.dump({'generated_by': GEN, 'map': MAP, 'kill_z': [ (phy.get('world') or {}).get(lv, {}).get('KillZ') for lv in (phy.get('world') or {})],
               'hazard_volumes': hz, 'note': 'damage applied by PhysicsVolume.PainTimer (stock UE3: DamagePerSec * PainInterval while touching); '
                                             'GAMEPLAY must simulate'}, open(os.path.join(OUT, 'hazard_volumes.json'), 'w', encoding='utf-8'), indent=1, default=str)
    c('kill_volumes', 'COMPLETE', {'hazard_volumes': len(hz), 'by_kind': dict(Counter(h['kind'] for h in hz)),
                                   'kill_z_ue': [(phy.get('world') or {}).get(lv, {}).get('KillZ') for lv in (phy.get('world') or {})],
                                   'file': 'manifests/maps/%s/hazard_volumes.json' % MAP},
      'GAMEPLAY' if hz else None, 'pain / kill volumes and KillZ must be applied at runtime' if hz else None)
    c('structure_audit', (sa.get('verdict') or {}).get('status', 'NOT RUN'), sa.get('verdict'))
    c('vs_validate', 'PASS' if vv and not vv.get('failures') else 'NOT RUN / FAIL', {'checks': len(vv.get('checks', [])) if vv else 0, 'failures': vv.get('failures') if vv else None})
    special = {k: v for k, v in (m.get('unhandled_actor_classes') or {}).items() if k in ('SkeletalMeshActor', 'LensFlareSource', 'HeightFog', 'PrefabInstance')}
    blockers = OrderedDict([
        ('ASSETTOOLS', [x for x in [
            'SkeletalMeshActor x%d without a resolved glTF' % sum(1 for x in skel if not x['gltf']) if any(not x['gltf'] for x in skel) else None,
            'height fog not fully exported' if checks['fog'].get('owner') == 'ASSETTOOLS' else None,
            'structure audit attention: %s' % (sa.get('verdict') or {}).get('failures') if (sa.get('verdict') or {}).get('status') == 'ATTENTION' else None] if x]),
        ('RE', [x for x in [
            'TnRadialForceVolume runtime force (x%d)' % (inv.get('actor_counts_by_class') or {}).get('TnRadialForceVolume', 0) if (inv.get('actor_counts_by_class') or {}).get('TnRadialForceVolume') else None,
            'LensFlareSource rendering semantics' if special.get('LensFlareSource') else None] if x]),
        ('RENDERING', [x for x in ['skeletal actors (%d) spawned from glTF (render_index_generic)' % len(skel) if skel else None,
                                   'particles (%d components)' % nfx if nfx else None, 'decals (%d)' % ndec if ndec else None,
                                   'height fog (%d, lighting.json globals.height_fogs)' % hf if hf else None, 'lens flares (%d)' % special.get('LensFlareSource', 0) if special.get('LensFlareSource') else None] if x]),
        ('GAMEPLAY', [x for x in ['movers runtime (%d)' % len(movers) if movers else None, 'mode gating per mode_visual_state', 'pickup state machines (RE P2)'] if x]),
        ('SYSTEMS', ['ambient audio zones / reverb from audio.json']),
        ('FRONTEND', ['registry entry present' if regmap else 'map missing from mp_registry'])])
    status = 'GEOMETRY + AUTHORED DATA COMPLETE (not a playability claim)' if all(v['status'] in ('COMPLETE', 'EXPORTED', 'AUTHORED', 'PASS', 'NONE') for v in checks.values()) else 'INCOMPLETE'   # ATTENTION / PARTIAL / MISSING -> INCOMPLETE
    xcheck = None
    if streets:   # cross-check against the validated Streets render_index (m04_complete.py)
        canon = J(os.path.join(SLICE, 'render_index.json'), {}).get('tdm_render_state') or {}
        cs = {(x if isinstance(x, str) else (x.get('actor') or '')).rsplit('.', 1)[-1] for x in canon.get('hide') or []}
        xcheck = {'validated_tdm_hidden': len(cs), 'generic_tdm_hidden': len(tdm_hidden), 'identical': cs == set(tdm_hidden),
                  'only_in_generic': sorted(set(tdm_hidden) - cs), 'only_in_validated': sorted(cs - set(tdm_hidden))}
    comp = OrderedDict([('generated_by', GEN), ('map', MAP), ('status', status),
                        ('playable_claim', 'NOT CLAIMED: runtime behaviour (modes, movers, pickups, FX, audio) belongs to Gameplay/Rendering/Systems'),
                        ('checks', checks), ('blockers_by_owner', blockers), ('cross_check_vs_validated_streets', xcheck)])
    json.dump(comp, open(os.path.join(OUT, 'completeness.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    json.dump(OrderedDict([('generated_by', GEN), ('map', MAP), ('registry', regmap), ('slice_dir', rel(SLICE)),
                           ('files', sorted(rel(os.path.join(dp, f)) for dp, _, fs in os.walk(SLICE) for f in fs if not f.endswith('.png'))),
                           ('lightmap_pngs', len([f for f in os.listdir(os.path.join(SLICE, 'lightmaps'))]) if os.path.isdir(os.path.join(SLICE, 'lightmaps')) else 0),
                           ('actor_counts', inv.get('actor_counts_by_class')), ('render_index', rel(os.path.join(OUT, 'render_index_generic.json'))),
                           ('completeness', rel(os.path.join(OUT, 'completeness.json')))]),
              open(os.path.join(OUT, 'map_complete.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print(MAP, status, {k: v['status'] for k, v in checks.items()}, 'tdm hidden', len(tdm_hidden))

if __name__ == '__main__':
    main()
