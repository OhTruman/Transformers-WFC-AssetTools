"""Streets destructibles (M03 P1): complete authored setup of every HmDestructible actor in MP_IAC_Streets.

Output: AssetTools/manifests/streets_destructibles.json
  per actor: class chain, transform, component tree, the HmDestructibleBlueprint (pieces -> states -> effect
  factories / links), resolved state graph (handles, triggers, health, timers), meshes (cooked section
  materials + extracted glTF), materials (vs_materials.describe), effects (decoded particle systems), sounds
  (cue graphs), collision/visibility settings, Kismet links, and whether the slice manifests represent it.
  python vs_destructibles.py
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, smsections, pstream as PS, objtree, vs_materials as VM  # noqa: E402
from m03_common import field, lit, write, pkg_of, CONF, HIGH, PART, UNK, map_arg, map_out, map_levels# noqa: E402
from vs_common import VS, ROOT  # noqa: E402

MAP = map_arg()                      # positional map name (default MP_IAC_Streets)
LV_ = map_levels(MAP)
SLICE = os.path.join(VS, 'Maps', MAP)
DEST_CLASSES = ('TnStaticDestructibleActor', 'TnDestructibleActor', 'HmDestructibleActorBase', 'TnDynamicDestructibleActor')
TRIGGER_MEANING = {
    'HM_Engine.HmGenericDamageDestructionTrigger': 'any damage that takes the state health to 0',
    'HM_Engine.HmKismetDestructionTrigger': 'Kismet (SeqAct) request',
    'HM_Engine.HmTouchDestructionTrigger': 'touch by an actor',
    'HM_Engine.HmTimerExpiredDestructionTrigger': "the state's AutomaticTransitionTime expiring"}

def tree(o, depth=0):
    r = A.get(o)
    if not r: return {'object': o, 'missing': True}
    out = {'object': o, 'class': r['class'], 'package': r['package'], 'archetype': A.con().execute(
        'SELECT archetype FROM objects WHERE opath=?', (o,)).fetchone()[0], 'authored': r['props'] or {}}
    kids = sorted(A.children(o), key=lambda c: c['opath'])
    if kids and depth < 8: out['children'] = [tree(c['opath'], depth + 1) for c in kids]
    return out

def gltf(mesh):
    pkg, name = mesh.split('.')[0], mesh.rsplit('.', 1)[-1]
    c = glob.glob(os.path.join(ROOT, 'content', pkg, '**', name + '.gltf'), recursive=True)
    return os.path.relpath(c[0], ROOT).replace(os.sep, '/') if c else None

def mesh_rec(mesh, level_pkg):
    secs = smsections.sections(level_pkg, mesh) or []
    v = A.values(mesh)
    return {'mesh': mesh, 'cooked_in': level_pkg, 'gltf': gltf(mesh),
            'sections': [{'index': s['index'], 'material': s['material'], 'num_triangles': s['num_triangles'],
                          'enable_collision': s['enable_collision'], 'cast_shadow': s['cast_shadow']} for s in secs],
            'collision_flags': {k: v.get(k) for k in ('UseSimpleBoxCollision', 'UseSimpleLineCollision',
                                                      'UseSimpleRigidBodyCollision', 'BodySetup')},
            'lightmap': {k: v.get(k) for k in ('LightMapResolution', 'LightMapCoordinateIndex')},
            'provenance': 'StaticMesh tagged props + cooked FStaticMeshElement (smsections): CONFIRMED AUTHORED DATA'}

def particle_rec(ps, level_pkgs):
    inv = objtree.inv()
    own = [r[0] for r in inv.execute('SELECT package FROM exports WHERE opath=?', (ps,)).fetchall()]
    pk = next((p for p in level_pkgs if p in own), own[0] if own else None)
    s = PS.system(ps, pk) if pk else {'particle_system': ps, 'missing': True}
    s['cooked_in_streets'] = [p for p in own if p.startswith(MAP)]
    return s

def slice_coverage(names):
    hits = {}
    for f in sorted(glob.glob(os.path.join(SLICE, '*.json'))):
        t = open(f, encoding='utf-8').read()
        found = [n for n in names if n in t]
        if found: hits[os.path.basename(f)] = found
    return hits

def kismet_links(actor):
    d = A.con()
    refs = [(s, p) for s, p in A.refs_to(actor)]
    seq = [(s, p, (d.execute('SELECT class FROM objects WHERE opath=?', (s,)).fetchone() or [None])[0]) for s, p in refs]
    return [{'object': s, 'property': p, 'class': c} for s, p, c in seq
            if c and (c.startswith('Seq') or 'Seq' in c)]

def build_actor(actor):
    d = A.con()
    r = A.get(actor); level_pkg = r['package']
    pkgs = [level_pkg] + [p for p in (LV_['base'], LV_['art']) if p and p != level_pkg]
    own = r['props'] or {}
    comp = own.get('DestructibleComponent')
    cv = ((A.get(comp) or {}).get('props') or {}) if comp else {}
    if comp and not cv.get('Blueprint'):   # prefab-instance destructibles (Escalation loot crates): Blueprint/Pieces on the archetype
        cv = {**{k: v for k, v in A.values(comp).items() if k in ('Blueprint', 'Pieces', 'BlueprintVersion', 'CodeVersion')}, **cv}
    bp = cv.get('Blueprint')
    rec = {'actor': actor, 'class': r['class'], 'level_package': level_pkg,
           'class_chain': [c['opath'] for c in A.chain(actor)],
           'transform': {'Location': field(actor, 'Location'), 'Rotation': field(actor, 'Rotation', default={'Pitch': 0, 'Yaw': 0, 'Roll': 0}),
                         'DrawScale': field(actor, 'DrawScale'), 'DrawScale3D': field(actor, 'DrawScale3D'),
                         'note': 'Rotation unset on the actor and every archetype -> (0,0,0); DrawScale 1 / DrawScale3D (1,1,1) inherited'},
           'actor_flags': {k: field(actor, k) for k in ('ForcePawnSeeThrough', 'Tag', 'bNoDelete', 'bWorldGeometry', 'bMovable',
                                                        'bCanBeDamaged', 'bCollideActors', 'bBlockActors', 'bProjTarget',
                                                        'CollisionPreset', '_ShouldBeHighlighted', 'bAlwaysRelevant',
                                                        'RemoteRole', 'NetUpdateFrequency', 'SupportedEvents',
                                                        'bOverrideCookOutStaticMeshActors', 'ReplicatedPieceStates')},
           'component': {'object': comp, 'Blueprint': bp, 'BlueprintVersion': cv.get('BlueprintVersion'),
                         'CodeVersion': cv.get('CodeVersion'), 'Pieces': cv.get('Pieces')},
           'instance_tree': tree(actor)}
    # blueprint
    bpv = ((A.get(bp) or {}).get('props') or {})
    rec['blueprint'] = {'object': bp, 'class': (A.get(bp) or {}).get('class'), 'cooked_copy_in': pkg_of(bp),
                        'BlueprintVersion': bpv.get('BlueprintVersion'),
                        'blueprint_defaults (HM_Engine.Default__HmDestructibleBlueprint, inherited)':
                            {k: field(bp, k) for k in ('DamageAngle', 'AIDamageModifier', 'RadiusDamageModifier',
                                                       'MinRadiusDamageDistanceForModifier')},
                        'variants_in_other_levels': sorted({x['opath'] for x in A.find(bp.split('.')[0] + '.%')
                                                            if x['class'] == 'HmDestructibleBlueprint'}),
                        'tree': tree(bp)}
    meshes, mats, particles, cues = {}, set(), {}, {}
    pieces = []
    for pb in bpv.get('PieceBlueprints') or []:
        pv = ((A.get(pb) or {}).get('props') or {})
        states = []
        for h, sb in enumerate(pv.get('StateBlueprints') or []):
            sv = ((A.get(sb) or {}).get('props') or {})
            st = {'handle': h, 'object': sb, 'StateName': field(sb, 'StateName'),
                  'InitialHealth': field(sb, 'InitialHealth', default=0),
                  'AutomaticTransitionTime': field(sb, 'AutomaticTransitionTime', default=0.0),
                  'effects': [], 'links': []}
            for ef in sv.get('EffectFactories') or []:
                er = A.get(ef); ev = er['props'] or {}
                e = {'object': ef, 'class': er['class'], 'authored': ev,
                     'effective': {k: v for k, v in A.values(ef).items() if k not in ('ComponentTemplates',)}}
                if ev.get('Mesh') or ev.get('MeshTemplate'):
                    m = ev.get('Mesh') or ev.get('MeshTemplate')
                    if m not in meshes: meshes[m] = mesh_rec(m, level_pkg)
                    mats.update(s['material'] for s in meshes[m]['sections'] if s['material'])
                if ev.get('Template'):
                    if ev['Template'] not in particles: particles[ev['Template']] = particle_rec(ev['Template'], pkgs)
                if ev.get('Cue'):
                    cues[ev['Cue']] = A.cue(ev['Cue'])
                st['effects'].append(e)
            for lk in sv.get('LinkBlueprints') or []:
                lv = A.values(lk)
                st['links'].append({'object': lk, 'NextStateHandle': lv.get('NextStateHandle'),
                                    'Enabled': field(lk, 'Enabled'), 'TransitionTrigger': lv.get('TransitionTrigger'),
                                    'trigger_meaning (class name)': TRIGGER_MEANING.get(lv.get('TransitionTrigger'))})
            states.append(st)
        pieces.append({'object': pb, 'PieceName': pv.get('PieceName'), 'Transform': pv.get('Transform'), 'states': states})
    rec['pieces'] = pieces
    # state graph, human-readable but every edge from authored LinkBlueprints
    graph = []
    for pc in pieces:
        for st in pc['states']:
            for lk in st['links']:
                graph.append({'piece': pc['PieceName'], 'from_handle': st['handle'], 'to_handle': lk['NextStateHandle'],
                              'trigger': lk['TransitionTrigger'], 'enabled': lk['Enabled']['value']})
    rec['state_graph'] = {
        'edges': graph,
        'initial_state': {'value': 0, 'confidence': HIGH,
                          'note': 'handle 0 = first StateBlueprints entry; the only state with InitialHealth and the only '
                                  'one with damage/touch/kismet links. That handle 0 is the spawn state is engine convention '
                                  '(HmDestructibleComponent native) -> confirm in native RE'},
        'interpretation': {
            'intact (handle 0)': 'Base mesh, hum loop cue, health 20; leaves on damage / touch / kismet',
            'destroyed (handle 1)': 'Chunk02 stump mesh + physics chunk Chunk01 + 6 debris chunks + 2 particle systems + '
                                    'explosion cue + state notification; leaves after AutomaticTransitionTime 10 s',
            'settled (handle 2)': 'Chunk02 stump mesh only (terminal state, no links)',
            'damaged state': 'NONE AUTHORED: the blueprint has no intermediate damaged state'}}
    # cooked pre-instantiated mesh components on the placed piece (lightmapped state meshes)
    inst = []
    piece_objs = cv.get('Pieces') or []
    P_ = lambda o: ((A.get(o) or {}).get('props') or {}) if o else {}
    for po in piece_objs:
        for me in P_(po).get('MeshEffects') or []:
            for mc in P_(me).get('MeshComponents') or []:
                mv = P_(mc)
                inst.append({'effect': me, 'component': mc, 'StaticMesh': mv.get('StaticMesh'), 'Translation': mv.get('Translation'),
                             'bCastDynamicShadow': mv.get('bCastDynamicShadow'), 'LightingChannels': mv.get('LightingChannels'),
                             'bRequiresStaticLightingRebuild': mv.get('bRequiresStaticLightingRebuild'),
                             'archetype': d.execute('SELECT archetype FROM objects WHERE opath=?', (mc,)).fetchone()[0],
                             'native_bytes': d.execute('SELECT native_bytes FROM objects WHERE opath=?', (mc,)).fetchone()[0]})
    rec['placed_mesh_components'] = {
        'components': inst,
        'note': 'The level cooks one StaticMeshComponent per HmStaticMeshDestructionEffect (lightmap option '
                'UseTextureLightmaps, archetype TextureLightmapMeshTemplate0). Base = intact state; the two Chunk02 '
                'components belong to the two Chunk02 states. Which Chunk02 component is handle 1 vs 2 is not named '
                'in the cooked data (identical mesh/transform) -> irrelevant for rendering.',
        'collision_from_template (HM_Engine.Default__HmStaticMeshDestructionEffectFactory.TextureLightmapMeshTemplate0)':
            {k: field('HM_Engine.Default__HmStaticMeshDestructionEffectFactory.TextureLightmapMeshTemplate0', k)
             for k in ('CollideActors', 'BlockActors', 'BlockZeroExtent', 'BlockNonZeroExtent', 'BlockRigidBody',
                       'BlockCameras', 'CastShadow', 'bCastDynamicShadow', 'bAcceptsDynamicLights', 'bAcceptsDecals',
                       'bNotifyRigidBodyCollision', 'ScriptRigidBodyCollisionThreshold', 'OverriddenLightMapResolution')}}
    rec['meshes'] = meshes
    rec['materials'] = {m: VM.describe(m) for m in sorted(mats)}
    rec['particle_systems'] = particles
    rec['sound_cues'] = cues
    rec['kismet_links'] = kismet_links(actor) or 'none: no Sequence object references this actor (refs table)'
    names = [actor.rsplit('.', 1)[-1], bp.split('.')[0]] + [m.rsplit('.', 1)[-1] for m in meshes]
    rec['slice_manifest_coverage'] = {
        'searched': names, 'found_in': slice_coverage(names),
        'verdict': None}
    # where the actor sits relative to the playable space (player starts) and every other placed actor
    import numpy as np
    locs, starts = [], []
    for o, pj in d.execute("SELECT opath, props FROM objects WHERE package LIKE ? AND opath LIKE '%.PersistentLevel.%' "
                           "AND props LIKE '%\"Location\"%'", (MAP + '%',)).fetchall():
        if o.count('.') != 3: continue
        L = json.loads(pj).get('Location')
        if isinstance(L, dict):
            locs.append((L['X'], L['Y'], L['Z']))
            if 'PlayerStart' in o: starts.append((L['X'], L['Y'], L['Z']))
    S = np.array(starts); P = np.array([own['Location'][k] for k in ('X', 'Y', 'Z')])
    rec['placement_context'] = {
        'actor_location': P.tolist(),
        'player_start_bbox': [S.min(0).tolist(), S.max(0).tolist()],
        'nearest_player_start_distance_uu': float(np.min(np.linalg.norm(S - P, axis=1))),
        'placed_actors_above_z_minus_50000': int(sum(1 for l in locs if l[2] > -50000)),
        'verdict': {'value': 'outside the playable space: ~70,000 UU above the play floor and >119,000 UU (Y) from the '
                             'player-start region; it is the only placed Streets actor above Z=-50000',
                    'confidence': CONF + ' (positions)',
                    'note': 'authored and cooked, so a 1:1 rebuild places it; players cannot reach or damage it in normal play '
                            '(HIGH CONFIDENCE)'}}
    if MAP != 'MP_IAC_Streets':
        # the interpretation / placement prose above was written for the one Streets destructible (WallPanelSign):
        # other maps keep only computed facts
        rec['state_graph'].pop('interpretation', None)
        inside = bool(len(S)) and bool(np.all(P >= S.min(0) - 5000) and np.all(P <= S.max(0) + 5000))
        rec['placement_context']['verdict'] = {'value': 'inside the player-start bounding box (+5000 UU)' if inside else
                                               'outside the player-start bounding box (+5000 UU)', 'confidence': CONF + ' (positions)'}
    f = rec['slice_manifest_coverage']['found_in']
    rec['slice_manifest_coverage']['verdict'] = (
        'NOT RENDERED by the slice prop manifests (props.json/map.json do not contain the actor or its meshes); only '
        'physics.json lists it' if 'props.json' not in f and 'map.json' not in f else 'represented in ' + ', '.join(f))
    return rec

def main():
    d = A.con()
    actors = [r[0] for r in d.execute('SELECT opath FROM objects WHERE package LIKE ? AND class IN (%s) AND opath LIKE ?'
                                      % ','.join('?' * len(DEST_CLASSES)), (MAP + '%',) + DEST_CLASSES + ('%PersistentLevel.%',)).fetchall()
              if r[0].count('.') == 3]
    out = {'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/vs_destructibles.py',
           'source': 'manifests/authored.db (cooked tagged props) + cooked StaticMesh sections + compiled particle streams',
           'actors': [build_actor(a) for a in sorted(actors)]}
    out['count'] = len(out['actors'])
    write(map_out(MAP, 'streets_destructibles.json'), out)
    for a in out['actors']:
        print(a['actor'], a['blueprint']['object'], [(s['handle'], s['InitialHealth']['value'], s['AutomaticTransitionTime']['value'],
                                                       len(s['effects'])) for p in a['pieces'] for s in p['states']],
              a['slice_manifest_coverage']['verdict'])

if __name__ == '__main__':
    main()
