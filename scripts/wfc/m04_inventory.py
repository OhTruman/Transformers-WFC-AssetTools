"""MP_IAC_Streets complete placed-object inventory + current-rebuild comparison (M04).

Sources (all read-only):
  cooked levels MP_IAC_Streets_{BASE,ART,AUDIO}_m via manifests/authored.db + inventory.db (+ native tails for
    lightmap type and PrefabInstance maps)
  current slice exports: ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/{props,map_fx,gameplay,audio,lighting,
    physics,spawnpoints,collision,lightmaps,props_authored}.json
  current rebuild render evidence: Rebuild-Rendering/work/render/MP_IAC_Streets/map_audit.json (Rendering lane's own
    renderer dump audit; read-only, quoted with its timestamp)
Outputs (AssetTools/manifests/):
  streets_actor_inventory.json   every placed actor + every component, transform, render/collision/light flags,
                                 classification vs the rebuild, provenance
  streets_rebuild_diff.json      classification counts + every non-matching record
  streets_lighting_audit.json    per StaticMeshComponent cooked lightmap type and its binding in lightmaps.json
  streets_movers.json            every authored moving / animated object (physics, RotationRate, Matinee tracks)
  streets_prefabs.json           every PrefabInstance member resolved to its placed object and slice coverage
"""
import json, os, re, struct, sys, time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree, vs_mapfx  # noqa: E402
from m03_common import write, CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import VS  # noqa: E402

MAP = 'MP_IAC_Streets'
LEVELS = [MAP + '_BASE_m', MAP + '_ART_m', MAP + '_AUDIO_m']
SLICE = os.path.join(VS, 'Maps', MAP)
AUDIT = r'F:/Transformers Rebuild/Rebuild-Rendering/work/render/MP_IAC_Streets/map_audit.json'

CLS = ['PRESENT AND MATCHING', 'PRESENT BUT WRONG TRANSFORM', 'PRESENT BUT WRONG MATERIAL', 'PRESENT BUT WRONG STATE',
       'PRESENT BUT INCOMPLETE', 'MISSING FROM REBUILD', 'EXTRA / REBUILD-ONLY', 'CONTAINER / NON-RENDERED AUTHORED OBJECT']
CATEGORY = {
    'StaticMeshCollectionActor': 'world geometry (static mesh collection)', 'StaticMeshActor': 'world geometry (static mesh)',
    'StaticInterpActor': 'mover (static interp)', 'InterpActor': 'mover (interp)', 'BRUSH': 'builder brush (BSP source)',
    'Model': 'BSP model', 'BlockingVolume': 'collision volume', 'TriggerVolume': 'trigger volume',
    'TnForcedDirVolume': 'gameplay volume', 'TnSpawnCluster': 'spawn cluster volume', 'DecalActor': 'decal',
    'Emitter': 'environment FX', 'HeightFog': 'fog', 'StaticLightCollectionActor': 'lights', 'LightsVisibilitiesVolume': 'light visibility volume',
    'AmbientSound': 'audio (point)', 'HmAmbientSoundLineEmitter': 'audio (line)', 'HmAmbientSoundVolumeEmitter': 'audio (volume)',
    'TnTeamPlayerStart': 'player start (team)', 'TnFreeForAllPlayerStart': 'player start (FFA)',
    'TnAmmoCratePickupFactory': 'pickup', 'TnHealthPickupFactory': 'pickup', 'TnOverShieldPickupFactory': 'pickup',
    'TnGameObjectivePickupFactoryFlag': 'objective (CTF)', 'TnGameObjectivePickupFactoryBomb': 'objective (EXT)',
    'TnFlagCapturePoint': 'objective (CTF)', 'TnBombPlantPoint': 'objective (EXT)', 'TnDominationPoint': 'objective (DOM)',
    'TnKingOfTheHillZone': 'objective (KOTH)', 'TnStaticDestructibleActor': 'destructible', 'PrefabInstance': 'prefab container',
    'Sequence': 'Kismet sequence', 'TnWorldInfo': 'world info', 'CameraActor': 'level camera (editor mesh)',
    'BeastSettingsReferer': 'settings reference', 'TnAssetReferencesMultiplayer': 'asset reference list'}
NON_RENDERED = {'BRUSH', 'BlockingVolume', 'TriggerVolume', 'TnForcedDirVolume', 'TnSpawnCluster', 'Sequence', 'TnWorldInfo',
                'BeastSettingsReferer', 'TnAssetReferencesMultiplayer', 'PrefabInstance', 'TnTeamPlayerStart',
                'TnFreeForAllPlayerStart', 'TnKingOfTheHillZone', 'TnFlagCapturePoint', 'TnBombPlantPoint',
                'AmbientSound', 'HmAmbientSoundLineEmitter', 'HmAmbientSoundVolumeEmitter', 'LightsVisibilitiesVolume',
                'StaticLightCollectionActor', 'Model', 'CameraActor'}
RENDER_KEYS = ('StaticMesh', 'SkeletalMesh', 'Materials', 'HiddenGame', 'HiddenEditor', 'CastShadow', 'bCastDynamicShadow',
               'CollideActors', 'BlockActors', 'BlockRigidBody', 'BlockZeroExtent', 'BlockNonZeroExtent', 'BlockCameras',
               'LightingChannels', 'CullDistance', 'bAcceptsLights', 'bAcceptsDynamicLights', 'bUsePrecomputedShadows',
               'Translation', 'Rotation', 'Scale', 'Scale3D', 'Template', 'DecalMaterial', 'bAutoActivate')

def load(name):
    p = os.path.join(SLICE, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None

def actors_of(lv):
    rows = objtree.inv().execute("SELECT class, opath FROM exports WHERE package=? AND opath LIKE ?",
                                 (lv, lv + '.TheWorld.PersistentLevel.%')).fetchall()
    return sorted((o, c) for c, o in rows if o.count('.') == 3)

def comps_of(actor):
    rows = objtree.inv().execute("SELECT class, opath FROM exports WHERE package=? AND opath LIKE ?",
                                 (actor.split('.')[0], actor + '.%')).fetchall()
    return sorted((o, c) for c, o in rows if o.count('.') == 4 and c.endswith('Component'))

def lightmap_types():
    """{component path: (type, lightmapped-in-lightmaps.json)} for every StaticMeshComponent in the level packages."""
    lmj = load('lightmaps.json') or {'props': []}
    bound = {x['component'].lower() for x in lmj['props'] if x.get('component')}
    out = {}
    for lv in LEVELS:
        p = objtree.package(lv)
        for i, e in enumerate(p.exports):
            if p.class_name(e) != 'StaticMeshComponent': continue
            op = p.object_path(i + 1)
            if not op.startswith(lv + '.TheWorld'): continue
            try: used = p._tr.read_object(i + 1)[1]
            except Exception: out[op] = {'type': None, 'note': 'tag read failed'}; continue
            nat = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
            if len(nat) == 21:     # LODData.Num=1, no lightmap record, LightingGuid: authored with no baked lighting
                out[op] = {'type': 0, 'native_bytes': 21, 'bound_in_lightmaps_json': op.lower() in bound,
                           'note': 'LOD record without lightmap (21-byte tail)'}; continue
            t = struct.unpack_from('>i', nat, 13)[0] if len(nat) >= 17 else None
            out[op] = {'type': t if t in (0, 1, 2) else None, 'native_bytes': len(nat), 'bound_in_lightmaps_json': op.lower() in bound}
    return out

def main():
    t0 = time.time()
    props = load('props.json')['props']
    fx = load('map_fx.json'); gp = load('gameplay.json'); au = load('audio.json'); li = load('lighting.json')
    ph = load('physics.json'); pa = load('props_authored.json')
    audit = json.load(open(AUDIT, encoding='utf-8')) if os.path.exists(AUDIT) else None
    audit_mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(AUDIT))) if audit else None
    # index slice exports
    by_comp = {}
    by_actor = defaultdict(list)
    for x in props:
        if x.get('component'): by_comp[x['component'].lower()] = x
        by_actor[(x['sublevel'], x['actor'])].append(x)
    fx_comps = {c['component'] for c in fx['particle_components']} | {d.get('component') for d in fx['decals']}
    gtxt = json.dumps(gp); atxt = json.dumps(au); ptxt = json.dumps(ph); ltxt = json.dumps(li)
    rstat = defaultdict(list)
    if audit:
        for it in audit['categories']['static_meshes']['items']:
            rstat[(it['sublevel'], it['actor'], it['mesh'])].append(it)
    hidden_auth = {}
    for x in (pa or {}).get('props', []):
        if (x.get('movement') or {}).get('bHidden'): hidden_auth[x['component']] = True
    lmt = lightmap_types()
    prefab_member = {}
    for lv in LEVELS:
        prefab_member.update(vs_mapfx.prefab_instances(objtree.package(lv)))
    d = A.con()

    def cls_mesh(lv, actor_short, mesh, comp_path, actor_hidden, mover):
        """classification of one rendered static mesh component."""
        x = by_comp.get((comp_path or '').lower())
        if x is None:
            cands = [y for y in by_actor.get((lv, actor_short), []) if y['mesh'] == mesh]
            x = cands[0] if cands else None
        if x is None: return 'MISSING FROM REBUILD', 'not in props.json', None
        rs = rstat.get((lv, actor_short, mesh)) or []
        st = Counter(r['status'] for r in rs)
        reason = rs[0].get('reason') if rs else None
        if actor_hidden:
            return 'PRESENT BUT WRONG STATE', 'authored bHidden=true (unhidden only by Kismet in CTF/EXT) but exported/drawn visible', x
        if mover:
            return 'PRESENT BUT WRONG STATE', mover + ' (drawn static)', x
        if st.get('rendered_incorrectly'):
            if 'material' in (reason or ''): return 'PRESENT BUT WRONG MATERIAL', 'Rendering audit: ' + reason, x
            return 'PRESENT BUT WRONG STATE', 'Rendering audit: ' + (reason or ''), x
        if st.get('unknown'):
            return 'PRESENT AND MATCHING', 'mesh/transform exported; material UNVERIFIED (Rendering audit: %s)' % reason, x
        return 'PRESENT AND MATCHING', 'exported in props.json; Rendering audit rendered_correctly' if st else 'exported in props.json', x

    movers = {}
    for m in (gp.get('matinee') or []):
        for a in m.get('actors') or []:
            movers[a['actor']] = 'Matinee %s (looping=%s, %.2f s)' % (m['action'], m.get('looping'), m.get('length_s') or 0)
    inv, diff = [], defaultdict(list)
    counts = defaultdict(Counter)
    for lv in LEVELS:
        for actor, cls in actors_of(lv):
            short = actor.rsplit('.', 1)[-1]
            own = (A.get(actor) or {}).get('props') or {}
            eff = A.values(actor) if A.get(actor) else {}
            rec = {'actor': actor, 'class': cls, 'package': lv, 'category': CATEGORY.get(cls, 'other'),
                   'transform': {'Location': eff.get('Location', {'X': 0, 'Y': 0, 'Z': 0}),
                                 'Rotation': eff.get('Rotation', {'Pitch': 0, 'Yaw': 0, 'Roll': 0}),
                                 'DrawScale': eff.get('DrawScale', 1.0), 'DrawScale3D': eff.get('DrawScale3D', {'X': 1, 'Y': 1, 'Z': 1}),
                                 'origin': 'effective (authored over archetype/CDO chain); unset Location/Rotation = 0'},
                   'bHidden': bool(eff.get('bHidden')), 'Physics': eff.get('Physics'), 'Tag': eff.get('Tag'),
                   'prefab_member_of': (prefab_member.get(actor) or {}).get('prefab_instance'),
                   'authored_keys': sorted(own.keys())}
            if cls in ('StaticInterpActor', 'InterpActor') and eff.get('Physics') == 'PHYS_Rotating':
                mover = 'PHYS_Rotating RotationRate %s' % eff.get('RotationRate')
            else:
                mover = movers.get(short)
            comps = []
            for cp, cc in comps_of(actor):
                cv = A.values(cp) if A.get(cp) else {}
                c = {'component': cp, 'class': cc,
                     'archetype': (d.execute('SELECT archetype FROM objects WHERE opath=?', (cp,)).fetchone() or [None])[0],
                     **{k: cv[k] for k in RENDER_KEYS if k in cv and cv[k] is not None}}
                if cc == 'StaticMeshComponent':
                    c['lightmap'] = lmt.get(cp)
                    if cls == 'CameraActor':
                        c['classification'] = 'CONTAINER / NON-RENDERED AUTHORED OBJECT'
                        c['classification_note'] = 'editor mesh EditorMeshes.MatineeCam_SM (not drawn in game)'
                    elif cls == 'TnStaticDestructibleActor':
                        c['classification'] = 'MISSING FROM REBUILD'
                        c['classification_note'] = 'destructible state mesh; see streets_destructibles.json (outside playable space)'
                    else:
                        k, note, x = cls_mesh(lv, short, cv.get('StaticMesh'), cp, rec['bHidden'], mover)
                        c['classification'] = k; c['classification_note'] = note
                        if x is not None:
                            c['slice_record'] = {'gltf': x.get('gltf'), 'section_materials': x.get('section_materials'),
                                                 'material_overrides': x.get('material_overrides')}
                elif cc == 'SkeletalMeshComponent':
                    c['classification'] = 'MISSING FROM REBUILD'
                    c['classification_note'] = ('TnDominationPoint energon totem (animated) - not exported to world.glb; '
                                                'Rendering lists TnDominationPoint as intentionally invisible')
                elif cc == 'ParticleSystemComponent':
                    inx = cp in fx_comps
                    c['classification'] = 'PRESENT BUT INCOMPLETE' if inx else 'MISSING FROM REBUILD'
                    c['classification_note'] = ('exported in map_fx.json; Rendering audit: emitters active 0 (not drawn)' if inx
                                                else 'not exported')
                elif cc == 'DecalComponent':
                    c['classification'] = 'PRESENT AND MATCHING' if cp in fx_comps else 'MISSING FROM REBUILD'
                    c['classification_note'] = 'map_fx.json + Rendering audit decals rendered_correctly'
                elif cc in ('PointLightComponent', 'SpotLightComponent', 'DirectionalLightComponent', 'SkyLightComponent'):
                    c['classification'] = 'PRESENT AND MATCHING' if cp in ltxt else 'MISSING FROM REBUILD'
                    c['classification_note'] = 'lighting.json; static contribution via lightmaps, dynamic via light environments'
                elif cc in ('HeightFogComponent',):
                    c['classification'] = 'PRESENT AND MATCHING'; c['classification_note'] = 'postprocess/lighting fog; Rendering applied'
                elif cc == 'AudioComponent':
                    c['classification'] = 'PRESENT AND MATCHING' if short in atxt else 'MISSING FROM REBUILD'
                    c['classification_note'] = 'audio.json (runtime by Systems; not verified here)'
                else:
                    c['classification'] = 'CONTAINER / NON-RENDERED AUTHORED OBJECT'
                comps.append(c)
            rec['components'] = comps
            # actor-level classification
            if cls in ('Model', 'ModelComponent'):
                rec['classification'] = 'PRESENT AND MATCHING'; rec['classification_note'] = 'BSP: see streets_bsp_audit.json'
            elif cls in ('TnAmmoCratePickupFactory', 'TnHealthPickupFactory', 'TnOverShieldPickupFactory',
                         'TnGameObjectivePickupFactoryFlag', 'TnGameObjectivePickupFactoryBomb'):
                rec['classification'] = 'PRESENT BUT INCOMPLETE' if short in gtxt else 'MISSING FROM REBUILD'
                rec['classification_note'] = 'gameplay.json placement present; pickup FX not drawn (Rendering audit emitters 0)'
            elif cls == 'TnDominationPoint':
                rec['classification'] = 'PRESENT BUT INCOMPLETE'
                rec['classification_note'] = 'objective placement in gameplay.json; energon-totem skeletal mesh not exported'
            elif cls == 'Emitter':
                rec['classification'] = 'PRESENT BUT INCOMPLETE'; rec['classification_note'] = 'map_fx.json exported; not drawn'
            elif cls == 'TnStaticDestructibleActor':
                rec['classification'] = 'MISSING FROM REBUILD'
                rec['classification_note'] = 'not in world.glb/props.json (physics.json only); placed outside the playable space'
            elif cls == 'LightsVisibilitiesVolume':
                rec['classification'] = 'MISSING FROM REBUILD'
                rec['classification_note'] = 'Rendering audit: not implemented (semantics not reverse-engineered)'
            elif cls in NON_RENDERED:
                present = (short in gtxt or short in ptxt or short in atxt or short in ltxt or cls in ('BRUSH', 'Sequence', 'TnWorldInfo',
                           'BeastSettingsReferer', 'TnAssetReferencesMultiplayer', 'PrefabInstance', 'CameraActor', 'Model'))
                rec['classification'] = 'CONTAINER / NON-RENDERED AUTHORED OBJECT'
                rec['classification_note'] = ('represented in slice data (%s)' % ', '.join(n for n, t in (('gameplay.json', gtxt), ('physics.json', ptxt),
                                              ('audio.json', atxt), ('lighting.json', ltxt)) if short in t) if present and cls not in
                                              ('BRUSH', 'Sequence', 'TnWorldInfo', 'PrefabInstance', 'CameraActor', 'Model', 'BeastSettingsReferer',
                                               'TnAssetReferencesMultiplayer') else 'non-rendered by design')
                if not present: rec['classification_note'] = 'NOT represented in any slice manifest'
            else:
                cs = Counter(c.get('classification') for c in comps if c.get('classification') and
                             c['class'] in ('StaticMeshComponent', 'SkeletalMeshComponent', 'ParticleSystemComponent', 'DecalComponent'))
                worst = next((k for k in CLS[1:] if cs.get(k)), 'PRESENT AND MATCHING' if cs else 'CONTAINER / NON-RENDERED AUTHORED OBJECT')
                rec['classification'] = worst
                rec['classification_note'] = 'from components: %s' % dict(cs)
            counts['actors'][rec['classification']] += 1
            for c in comps:
                if c.get('classification'): counts['components'][c['classification']] += 1
            if rec['classification'] != 'PRESENT AND MATCHING' and rec['classification'] != 'CONTAINER / NON-RENDERED AUTHORED OBJECT':
                diff[rec['classification']].append({'actor': actor, 'class': cls, 'note': rec['classification_note']})
            for c in comps:
                k = c.get('classification')
                if k and k not in ('PRESENT AND MATCHING', 'CONTAINER / NON-RENDERED AUTHORED OBJECT'):
                    diff['component: ' + k].append({'component': c['component'], 'class': c['class'],
                                                    'mesh': c.get('StaticMesh') or c.get('SkeletalMesh') or c.get('Template'),
                                                    'note': c.get('classification_note')})
            inv.append(rec)
    # extras: props.json records with no authored component/actor
    authored_comps = {c['component'].lower() for r in inv for c in r['components']}
    authored_actor = {(r['package'], r['actor'].rsplit('.', 1)[-1]) for r in inv}
    extra = [x for x in props if not ((x.get('component') or '').lower() in authored_comps or (x['sublevel'], x['actor']) in authored_actor)]
    for x in extra: diff['EXTRA / REBUILD-ONLY'].append({'record': x.get('component') or x['actor'], 'mesh': x['mesh']})
    counts['actors']['EXTRA / REBUILD-ONLY'] += len(extra)
    cls_counts = Counter(r['class'] for r in inv)
    comp_counts = Counter(c['class'] for r in inv for c in r['components'])
    meta = {'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/m04_inventory.py',
            'sources': {'cooked': LEVELS, 'slice': SLICE, 'rebuild_render_evidence': {'file': AUDIT, 'mtime': audit_mtime,
                        'summary': (audit or {}).get('summary'), 'note': 'Rendering lane renderer-dump audit; read-only'}},
            'classification_vocabulary': CLS}
    write('streets_actor_inventory.json', {**meta, 'actor_counts_by_class': dict(sorted(cls_counts.items())),
                                           'component_counts_by_class': dict(sorted(comp_counts.items())),
                                           'actors': inv})
    write('streets_rebuild_diff.json', {**meta, 'classification_counts': {k: dict(v) for k, v in counts.items()},
                                        'non_matching': {k: v for k, v in sorted(diff.items())}})
    # lighting audit
    lt = Counter((v['type'], v.get('bound_in_lightmaps_json')) for v in lmt.values())
    write('streets_lighting_audit.json', {**meta, 'static_mesh_components': len(lmt),
          'by_lightmap_type': {'%s / bound=%s' % ({0: 'none(0)', 1: 'vertex 1D (1)', 2: 'texture 2D (2)', None: 'unparsed'}[t], b): n for (t, b), n in lt.items()},
          'texture_lightmapped_not_bound': [k for k, v in lmt.items() if v['type'] == 2 and not v['bound_in_lightmaps_json']],
          'vertex_lightmapped': [k for k, v in lmt.items() if v['type'] == 1],
          'components': lmt,
          'notes': ['type read as big-endian int32 at native offset 13 of the StaticMeshComponent tail (LODData[0].LightMap type; '
                    'same rule as vs_lightmap.py / Rendering build_lighting.py)',
                    'vertex (1D) lightmaps: per-vertex directional samples; AssetTools lightmaps.json does not carry them - '
                    'Rendering decodes them in build_lighting.parse_lightmap_1d',
                    'lights inventory: lighting.json (268 components); LightsVisibilitiesVolume semantics UNKNOWN']})
    # movers
    mv = []
    for r in inv:
        if r['class'] in ('StaticInterpActor', 'InterpActor') or r['Physics'] in ('PHYS_Rotating', 'PHYS_Interpolating'):
            sh = r['actor'].rsplit('.', 1)[-1]
            mv.append({'actor': r['actor'], 'class': r['class'], 'physics': r['Physics'],
                       'RotationRate': A.values(r['actor']).get('RotationRate'), 'bHidden': r['bHidden'],
                       'mesh': next((c.get('StaticMesh') for c in r['components'] if c.get('StaticMesh')), None),
                       'matinee': movers.get(sh), 'transform': r['transform'], 'classification': r['classification']})
    write('streets_movers.json', {**meta, 'movers': mv, 'matinee': gp.get('matinee'),
                                  'rotation_units': 'RotationRate in Unreal rotation units per second (65536 = 360 deg): 2730 = 15.0 deg/s'})
    # prefabs
    pf = defaultdict(list)
    for member, m in prefab_member.items():
        sh = member.rsplit('.', 1)[-1]; lv = member.split('.')[0]
        exists = objtree.inv().execute('SELECT class FROM exports WHERE package=? AND opath=?', (lv, member)).fetchone()
        smc = [x for x in props if x['sublevel'] == lv and (x.get('component') or '').rsplit('.', 1)[-1].startswith(sh + '_')]
        cov = ('props.json (%d component%s, collapsed into StaticMeshCollectionActor)' % (len(smc), 's' if len(smc) != 1 else '') if smc
               else ('props.json' if (lv, sh) in by_actor else ('map_fx.json' if any(c.startswith(member + '.') for c in fx_comps)
                     else ('present as cooked actor %s' % exists[0] if exists else 'NOT COOKED (editor-only or merged)'))))
        pf[m['prefab_instance']].append({'member': member, 'archetype': m['archetype'], 'template_prefab': m['template_prefab'],
                                         'cooked_class': exists[0] if exists else None, 'slice_coverage': cov})
    write('streets_prefabs.json', {**meta, 'prefab_instances': len(pf), 'members': sum(len(v) for v in pf.values()),
                                   'uncovered_members': [m for v in pf.values() for m in v if m['slice_coverage'].startswith('NOT')],
                                   'prefabs': pf})
    print('actors', len(inv), 'components', sum(len(r['components']) for r in inv), 'extras', len(extra))
    print(json.dumps({k: dict(v) for k, v in counts.items()}, indent=1))
    print('lightmap types', dict(lt), 'prefabs', len(pf), 'members', sum(len(v) for v in pf.values()), '%.0fs' % (time.time() - t0))

if __name__ == '__main__':
    main()
