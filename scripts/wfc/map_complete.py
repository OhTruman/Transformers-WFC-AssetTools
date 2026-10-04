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
    c('postprocess', 'COMPLETE' if pp else 'MISSING', {k: pp.get(k) for k in ('scene_chain', 'governing', 'volumes')} if pp else None)
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
    c('vs_validate', 'PASS' if vv and not vv.get('failures') else 'NOT RUN / FAIL', {'checks': len(vv.get('checks', [])) if vv else 0, 'failures': vv.get('failures') if vv else None})
    special = {k: v for k, v in (m.get('unhandled_actor_classes') or {}).items() if k in ('SkeletalMeshActor', 'LensFlareSource', 'HeightFog', 'PrefabInstance')}
    blockers = OrderedDict([
        ('ASSETTOOLS', [x for x in [
            'SkeletalMeshActor x%d not exported to world.glb (mesh + anim known in inventory)' % special['SkeletalMeshActor'] if special.get('SkeletalMeshActor') else None,
            'height fog not fully exported' if checks['fog'].get('owner') == 'ASSETTOOLS' else None,
            'map-specific render_index enrichments (pickup FX component matrices, destructible states) are Streets-only (m04_complete)' if not streets else None] if x]),
        ('RE', [x for x in [
            'TnRadialForceVolume runtime force (x%d)' % (inv.get('actor_counts_by_class') or {}).get('TnRadialForceVolume', 0) if (inv.get('actor_counts_by_class') or {}).get('TnRadialForceVolume') else None,
            'LensFlareSource rendering semantics' if special.get('LensFlareSource') else None] if x]),
        ('RENDERING', [x for x in ['particles (%d components)' % nfx if nfx else None, 'decals (%d)' % ndec if ndec else None,
                                   'height fog (%d, lighting.json globals.height_fogs)' % hf if hf else None, 'lens flares (%d)' % special.get('LensFlareSource', 0) if special.get('LensFlareSource') else None] if x]),
        ('GAMEPLAY', [x for x in ['movers runtime (%d)' % len(movers) if movers else None, 'mode gating per mode_visual_state', 'pickup state machines (RE P2)'] if x]),
        ('SYSTEMS', ['ambient audio zones / reverb from audio.json']),
        ('FRONTEND', ['registry entry present' if regmap else 'map missing from mp_registry'])])
    status = 'GEOMETRY + AUTHORED DATA COMPLETE (not a playability claim)' if all(v['status'] in ('COMPLETE', 'EXPORTED', 'AUTHORED', 'PASS', 'NONE') for v in checks.values()) else 'INCOMPLETE'
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
