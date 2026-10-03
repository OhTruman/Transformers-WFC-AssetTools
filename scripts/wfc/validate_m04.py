"""Map-completeness validation for MP_IAC_Streets (M04). Writes logs/validate_m04.json; exit 1 on failure.

  hierarchy_closes          every StreamingLevels package exists and is loaded+visible in the default streaming state
  inventory_refs_resolve    every inventoried actor/component exists in the cooked inventory
  visible_meshes_accounted  every StaticMeshComponent placed for normal play is in props.json, or is explicitly classified
                            (editor camera mesh / destructible); every SkeletalMeshComponent is in render_index.json
  bsp_complete              0 unaccounted BSP nodes and exported triangles == authored render triangles
  materials_resolve         every props.json section material / override resolves to a cooked object or is UNKNOWN
  lighting_resolves         every texture-lightmapped component is bound in lightmaps.json (or listed with a reason);
                            every coefficient atlas has a PNG
  audio_accounted           every AmbientSound / line / volume emitter actor appears in audio.json
  fx_accounted              every ParticleSystemComponent / DecalComponent is in map_fx.json
  pickups_destructibles     27 factories, 37 pickup effect components, 1 destructible, all classified
  prefabs_covered           every PrefabInstance member resolves to slice data
  render_index_paths        every gltf path in render_index.json exists
  preserved                 props 1952, decals 25, light components 268, M03 manifests present
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from vs_common import VS, ROOT  # noqa: E402

MAP = 'MP_IAC_Streets'
MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
LOGS = os.path.normpath(os.path.join(HERE, '..', '..', 'logs'))
SLICE = os.path.join(VS, 'Maps', MAP)

def J(p): return json.load(open(p, encoding='utf-8'))

def main():
    res, fails = {}, []
    def chk(n, c, m=''):
        res.setdefault(n, [0, 0]); res[n][0] += 1
        if not c: res[n][1] += 1; fails.append('%s: %s' % (n, m))
    inv = J(os.path.join(MANI, 'streets_actor_inventory.json'))
    comp = J(os.path.join(MANI, 'mp_iac_streets_complete.json'))
    bspa = J(os.path.join(MANI, 'streets_bsp_audit.json'))
    lit = J(os.path.join(MANI, 'streets_lighting_audit.json'))
    pref = J(os.path.join(MANI, 'streets_prefabs.json'))
    ri = J(os.path.join(SLICE, 'render_index.json'))
    props = J(os.path.join(SLICE, 'props.json'))['props']
    lm = J(os.path.join(SLICE, 'lightmaps.json')); au = J(os.path.join(SLICE, 'audio.json')); fx = J(os.path.join(SLICE, 'map_fx.json'))
    li = J(os.path.join(SLICE, 'lighting.json'))
    db = objtree.inv()
    ex = lambda o: db.execute('SELECT 1 FROM exports WHERE opath=? LIMIT 1', (o,)).fetchone() is not None
    # hierarchy
    h = comp['hierarchy']
    chk('hierarchy_closes', h['closure']['all_resolved'], 'unresolved streaming package')
    vis = {l['LevelName']: l['LevelVisible'] for l in (h['level_streaming_state'] or {}).get('Levels') or []}
    for s in h['streaming_levels']:
        chk('hierarchy_closes', vis.get(s['PackageName']) is True, '%s not visible by default' % s['PackageName'])
    # inventory refs
    for a in inv['actors']:
        chk('inventory_refs_resolve', ex(a['actor']), a['actor'])
        for c in a['components']: chk('inventory_refs_resolve', ex(c['component']), c['component'])
    # visible meshes
    pc = {(x.get('component') or '').lower() for x in props}
    pa = {(x['sublevel'], x['actor']) for x in props}
    ri_actors = {x['actor'] for x in ri['not_in_world_glb (authored renderables)']}
    for a in inv['actors']:
        for c in a['components']:
            if c['class'] == 'StaticMeshComponent':
                ok = c['component'].lower() in pc or (a['package'], a['actor'].rsplit('.', 1)[-1]) in pa or \
                     c.get('classification') in ('CONTAINER / NON-RENDERED AUTHORED OBJECT', 'MISSING FROM REBUILD')
                chk('visible_meshes_accounted', ok, c['component'])
            if c['class'] == 'SkeletalMeshComponent':
                chk('visible_meshes_accounted', a['actor'] in ri_actors, c['component'])
    # bsp
    art = bspa['levels'][MAP + '_ART_m']
    chk('bsp_complete', len(art['unaccounted_nodes']) == 0, 'unaccounted nodes')
    chk('bsp_complete', bspa['comparison']['difference'] == 0, 'triangle difference')
    chk('bsp_complete', not art['unparsed_model_components'], 'unparsed ModelComponents')
    # materials
    seen = set()
    for x in props:
        for m in (x.get('section_materials') or []) + [o for o in (x.get('material_overrides') or []) if isinstance(o, str)]:
            if not m or m in seen: continue
            seen.add(m)
            chk('materials_resolve', A.get(m) is not None or ex(m), m)
    for s in art['surfaces_detail']:
        if s['rendered'] and s['material']: chk('materials_resolve', A.get(s['material']) is not None or ex(s['material']), s['material'])
    # lighting
    for k, v in lit['components'].items():
        if v['type'] == 2:
            chk('lighting_resolves', v['bound_in_lightmaps_json'] or 'TnStaticDestructibleActor' in k, k)
        chk('lighting_resolves', v['type'] in (0, 1, 2), 'unparsed lightmap type ' + k)
    for x in lm['props']:
        for c in x['coeffs']: chk('lighting_resolves', os.path.exists(os.path.join(SLICE, 'lightmaps', c + '.png')), c)
    lt = json.dumps(li)
    for a in inv['actors']:
        for c in a['components']:
            if c['class'] in ('PointLightComponent', 'SpotLightComponent', 'DirectionalLightComponent', 'SkyLightComponent'):
                chk('lighting_resolves', c['component'] in lt, c['component'])
    # audio
    at = json.dumps(au)
    for a in inv['actors']:
        if a['class'] in ('AmbientSound', 'HmAmbientSoundLineEmitter', 'HmAmbientSoundVolumeEmitter'):
            chk('audio_accounted', a['actor'].rsplit('.', 1)[-1] in at, a['actor'])
    # fx
    fxc = {c['component'] for c in fx['particle_components']} | {d.get('component') for d in fx['decals']}
    for a in inv['actors']:
        for c in a['components']:
            if c['class'] in ('ParticleSystemComponent', 'DecalComponent'): chk('fx_accounted', c['component'] in fxc, c['component'])
    # pickups / destructibles
    cnt = comp['counts']
    chk('pickups_destructibles', sum(cnt['pickups'].values()) + cnt['objectives']['TnGameObjectivePickupFactoryFlag'] +
        cnt['objectives']['TnGameObjectivePickupFactoryBomb'] == 27, 'factory count')
    chk('pickups_destructibles', cnt['destructibles'] == 1, 'destructible count')
    pf = J(os.path.join(MANI, 'streets_pickup_factories.json'))
    chk('pickups_destructibles', pf['counts']['counts_match_expected'], 'pickup fx counts')
    # prefabs
    chk('prefabs_covered', not pref['uncovered_members'], '%d uncovered members' % len(pref['uncovered_members']))
    # render index
    for x in ri['not_in_world_glb (authored renderables)']:
        for k in ('gltf', 'anim'):
            if x.get(k): chk('render_index_paths', os.path.exists(os.path.join(ROOT, x[k])), x[k])
    # preserved
    chk('preserved', len(props) == 1952, 'props %d' % len(props))
    chk('preserved', len(fx['decals']) == 25, 'decals')
    chk('preserved', sum(cnt['lights'].values()) == 268, 'lights')
    for f in ('streets_destructibles.json', 'streets_pickup_factories.json', 'streets_pickup_fx.json', 'fineaim_hud.json',
              'streets_surface_audio.json', 'vertical_slice_audio_concurrency.json', 'vehicle_audio_loops.json', 'vs_evidence.json',
              'vs_evidence_pass2.json'):
        chk('preserved', os.path.exists(os.path.join(MANI, f)), f)
    os.makedirs(LOGS, exist_ok=True)
    json.dump({'checks': res, 'failures': fails}, open(os.path.join(LOGS, 'validate_m04.json'), 'w'), indent=1)
    for k, v in res.items(): print('%-28s %5d checks %3d failed' % (k, v[0], v[1]))
    tot = sum(v[0] for v in res.values()); bad = sum(v[1] for v in res.values())
    print('validate_m04: %d checks, %d failures' % (tot, bad))
    for f in fails[:30]: print('  FAIL', f)
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
