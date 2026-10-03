"""Streets pickup factories + pickup particle effects (M03 P2 / P7).

Outputs:
  AssetTools/manifests/streets_pickup_factories.json
      per factory class: class chain, authored/inherited properties, inventory payload (what is given), sounds,
      component archetypes (which effect component exists, attached or not, auto-activate), native functions
      that own the runtime state machine; per instance: transform, RespawnTime, team/objective fields,
      linked effect components and their resolved templates, presence in the slice manifests.
  AssetTools/manifests/streets_pickup_fx.json
      the three particle systems used by the 37 pickup components, fully decoded:
      ParticleSystem / Emitter / LOD tagged props, RequiredModule (material, spawn rate, local space ...),
      TypeDataMesh mesh (+ its cooked section materials), and every compiled module with its distributions
      assigned to module + property (pstream.py). Material summaries for every particle material.
  python vs_pickups.py
"""
import glob, json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree, pstream as PS, particles, smsections  # noqa: E402
from m03_common import field, lit, write, pkg_of, cls_of, CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import VS, ROOT  # noqa: E402

MAP = 'MP_IAC_Streets'
SLICE = os.path.join(VS, 'Maps', MAP)
FACTORY_CLASSES = ['TnAmmoCratePickupFactory', 'TnHealthPickupFactory', 'TnOverShieldPickupFactory',
                   'TnGameObjectivePickupFactoryFlag', 'TnGameObjectivePickupFactoryBomb']
FX_PACKAGE = 'TransGame'     # the three pickup ParticleSystems are cooked in the always-loaded TransGame package
EXPECTED = {'FX_Pickups_p.FX.Pickup_FX': 27, 'FX_Pickups_p.FX.HealthPickup_FX': 9, 'FX_Pickups_p.FX.OvershieldPickup_FX': 1}
ROLE = {'FX_Pickups_p.FX.Pickup_FX': 'weapon/generic pickup light beam (Experimental/Systems "weapon pickup effect")',
        'FX_Pickups_p.FX.HealthPickup_FX': 'health pickup (energon cube + glows)',
        'FX_Pickups_p.FX.OvershieldPickup_FX': 'overshield pickup (overshield mesh + glows)'}

def gltf(mesh):
    pkg, name = mesh.split('.')[0], mesh.rsplit('.', 1)[-1]
    c = glob.glob(os.path.join(ROOT, 'content', pkg, '**', name + '.gltf'), recursive=True)
    return os.path.relpath(c[0], ROOT).replace(os.sep, '/') if c else None

def native_functions(cls_path):
    """Function/State exports of the class in TransGame; their tiny serial sizes show they carry no script bytecode."""
    inv = objtree.inv()
    rows = inv.execute("SELECT class, opath, serial_size FROM exports WHERE package='TransGame' AND opath LIKE ?",
                       (cls_path + '.%',)).fetchall()
    return [{'kind': c, 'name': o.split('.', 2)[2], 'serial_size': s} for c, o, s in rows if c in ('Function', 'State')]

def component_rec(comp_path, factory_cdo):
    """Effect component on a class CDO: template, auto-activate, and whether it is in the Components array (attached)."""
    v = A.values(comp_path)
    comps = A.values(factory_cdo).get('Components') or []
    return {'component_archetype': comp_path,
            'Template': field(comp_path, 'Template'),
            'bAutoActivate': field(comp_path, 'bAutoActivate', default=True,
                                   note='ParticleSystemComponent default bAutoActivate is true when unset'),
            'in_Components_array': {'value': comp_path in comps, 'object': factory_cdo, 'property': 'Components',
                                    'confidence': CONF,
                                    'meaning': 'UE3 attaches only components listed in the actor Components array at '
                                               'spawn; a component outside it exists (cooked) but is not attached unless '
                                               'native code attaches it'},
            'SecondsBeforeInactive': v.get('SecondsBeforeInactive'), 'CullDistance': v.get('CullDistance')}

def factory_class_rec(cls):
    d = A.con()
    cdo = d.execute('SELECT opath FROM objects WHERE opath LIKE ? AND class = ?', ('%.Default__' + cls, cls)).fetchone()[0]
    v = A.values(cdo)
    inv_cls = v.get('InventoryType')
    inv_cdo = None
    if inv_cls:
        pk, nm = inv_cls.split('.')
        inv_cdo = '%s.Default__%s' % (pk, nm)
    ivals = A.values(inv_cdo) if inv_cdo and A.get(inv_cdo) else {}
    rec = {'class': cls, 'cdo': cdo, 'class_chain': [c['opath'] for c in A.chain(cdo)],
           'factory_properties': {k: field(cdo, k) for k in ('InventoryType', 'RespawnTime', 'ShouldDisplayHighlightFx',
                                                             'RequiredGameRuleClass', 'MarkerType', 'MarkerString',
                                                             'WaitAfterScoreTime', 'bOnlyReplicateHidden', 'CollisionPreset',
                                                             'bCollideActors', 'bAlwaysRelevant', 'SupportedEvents')
                                  if k in v or k in ('RespawnTime', 'InventoryType')},
           'collision_cylinder': {k: field(v['CylinderComponent'], k) for k in ('CollisionRadius', 'CollisionHeight', 'Translation')}
                                 if v.get('CylinderComponent') else None,
           'effect_components': {k: component_rec(v[k], cdo) for k in ('PickupEffect', 'CustomPickupEffect') if v.get(k)},
           'inventory': {'class': inv_cls, 'cdo': inv_cdo,
                         'payload': {k: lit(ivals[k], inv_cdo, k, origin='authored/inherited on inventory CDO')
                                     for k in ('AddedHealth', 'ValidWeaponTypes', 'PickupSound', 'PickupObtainedDialog',
                                               'DroppedPickupClass', 'PickupRotationRate', 'MaxDesireability') if k in ivals},
                         'pickup_mesh': None},
           'native_functions': native_functions('TransGame.' + cls) + (native_functions('TransGame.TnPickupFactory')
                                                                         if cls != 'TnPickupFactory' else [])}
    pm = ivals.get('PickupFactoryMesh')
    if pm:
        mv = A.values(pm)
        rec['inventory']['pickup_mesh'] = {'component': pm, 'StaticMesh': mv.get('StaticMesh'), 'gltf': gltf(mv['StaticMesh']) if mv.get('StaticMesh') else None,
                                           'CullDistance': mv.get('CullDistance'), 'CastShadow': mv.get('CastShadow'),
                                           'CollideActors': mv.get('CollideActors'), 'PickupRotationRate': ivals.get('PickupRotationRate'),
                                           'component_transform': {'Translation': mv.get('Translation'), 'Rotation': mv.get('Rotation'),
                                                                   'Scale': mv.get('Scale'), 'Scale3D': mv.get('Scale3D')},
                                           'attach': 'PickupFactory.SetPickupMesh -> Inventory.CreatePickupFactoryMesh (new copy of the '
                                                     'template) -> AttachComponent; no script offset (RE script decomp, read-only). '
                                                     'Mesh sits at the factory origin (component transform identity).',
                                           'confidence': CONF}
    elif inv_cdo and 'WeaponMeshTemplate' in A.effective(inv_cdo):
        ie = A.effective(inv_cdo)
        tmpl = ie['WeaponMeshTemplate']['value']; te = A.effective(tmpl); pmc = te['PickupMesh']['value']; pe = A.effective(pmc)
        mesh = (pe.get('SkeletalMesh') or pe.get('StaticMesh') or {}).get('value')
        rec['inventory']['pickup_mesh'] = {
            'via': 'TnWeapon.CreatePickupFactoryMesh: TnWeaponMesh(default.WeaponMeshTemplate).GetValidPickupMesh() cloned, '
                   'SetRotation(default.SpawnOffsetAngle), SetScale(default.PickupScale) (RE script decomp, read-only)',
            'WeaponMeshTemplate': tmpl, 'component': pmc, 'component_class': A.get(pmc)['class'], 'mesh': mesh,
            'gltf': gltf(mesh) if mesh else None,
            'Translation': (pe.get('Translation') or {}).get('value'), 'SpawnOffsetAngle': ie['SpawnOffsetAngle']['value'],
            'PickupScale': ie['PickupScale']['value'], 'PickupMaterialOverride': (te.get('PickupMaterialOverride') or {}).get('value'),
            'CastShadow': (pe.get('CastShadow') or {}).get('value'), 'PickupRotationRate': ie['PickupRotationRate']['value'],
            'confidence': CONF}
    else:
        rec['inventory']['pickup_mesh'] = {'value': None, 'confidence': CONF,
                                           'note': 'inventory CDO has no PickupFactoryMesh: the visible pickup is the particle effect (mesh emitter)'}
    for k in ('DroppedPickupParticles',):
        if ivals.get(k): rec['inventory']['dropped_pickup_particles'] = {'component': ivals[k], 'Template': A.values(ivals[k]).get('Template')}
    if ivals.get('PickupSound'):
        rec['inventory']['pickup_sound_cue'] = A.cue(ivals['PickupSound'])
    return rec

def instance_rec(o, slice_gameplay, slice_fx):
    d = A.con()
    v = A.get(o)['props'] or {}
    cls = A.get(o)['class']
    eff = {}
    for k in ('PickupEffect', 'CustomPickupEffect'):
        c = v.get(k)
        if not c: continue
        arch = d.execute('SELECT archetype FROM objects WHERE opath=?', (c,)).fetchone()[0]
        ev = A.values(c)
        eff[k] = {'component': c, 'archetype': arch, 'Template': ev.get('Template'), 'bAutoActivate': ev.get('bAutoActivate'),
                  'instance_overrides': A.get(c)['props'] or {},
                  'in_map_fx_json': c in slice_fx}
    short = o.rsplit('.', 1)[-1]
    return {'actor': o, 'class': cls, 'package': A.get(o)['package'],
            'transform': {'Location': v.get('Location'), 'Rotation': v.get('Rotation') or {'Pitch': 0, 'Yaw': 0, 'Roll': 0},
                          'DrawScale': A.values(o).get('DrawScale'), 'note': 'unset Rotation -> (0,0,0)'},
            'RespawnTime': field(o, 'RespawnTime'),
            'DefenderTeamIndex': field(o, 'DefenderTeamIndex', default=0) if 'Objective' in cls else None,
            'NetworkID': v.get('NetworkID'), 'Base': v.get('Base'), 'MaxPathSize': v.get('MaxPathSize'),
            'effects': eff,
            'collision_cylinder': v.get('CylinderComponent'),
            'in_gameplay_json': short in slice_gameplay}

def fx_rec(ps):
    s = PS.system(ps, FX_PACKAGE)
    p = objtree.package(FX_PACKAGE)
    mats = {}
    for e in s['emitters']:
        for L in e['lods']:
            m = (L.get('RequiredModule') or {}).get('props', {}).get('Material')
            if m: mats.setdefault(m, None)
            if L.get('mesh'):
                secs = smsections.sections(FX_PACKAGE, L['mesh']) or []
                td = (L.get('TypeDataModule') or {}).get('props') or {}
                L['mesh_record'] = {'mesh': L['mesh'], 'gltf': gltf(L['mesh']), 'cooked_in': FX_PACKAGE,
                                    'section_materials': [x['material'] for x in secs],
                                    'TypeDataMesh_props': td,
                                    'material_rule': ('RequiredModule.Material is used when bOverrideMaterial is set; '
                                                      'otherwise the mesh section materials render (UE3 mesh emitter)')}
                if td.get('bOverrideMaterial') and not (L.get('RequiredModule') or {}).get('props', {}).get('Material'):
                    L['mesh_record']['material_resolution'] = {
                        'confidence': PART,
                        'value': [x['material'] for x in secs],
                        'note': 'bOverrideMaterial=true but RequiredModule.Material is unset and no MeshMaterial module is '
                                'compiled: the only authored material reference is the mesh section material; what the '
                                'native renderer substitutes for a null override is UNKNOWN (native RE)'}
                for x in secs:
                    if x['material']: mats.setdefault(x['material'], None)
    s['materials'] = {m: particles.material_summary(p, m) for m in mats}
    s['role'] = ROLE[ps]
    # compact per-emitter digest for implementers
    dig = []
    for e in s['emitters']:
        for L in e['lods']:
            rq = (L.get('RequiredModule') or {}).get('props') or {}
            dig.append({'emitter': e['name'], 'lod': L['level'], 'material': rq.get('Material'),
                        'mesh': L.get('mesh'), 'SpawnRate': rq.get('SpawnRate'), 'bUseLocalSpace': rq.get('bUseLocalSpace'),
                        'EmitterLoops': rq.get('EmitterLoops', 'unset -> 0 = loop forever (UE3 default)'),
                        'EmitterDuration': rq.get('EmitterDuration', 'unset -> UE3 default 1.0'),
                        'ScreenAlignment': rq.get('ScreenAlignment', 'unset -> PSA_Square (UE3 default)'),
                        'modules': [m['module'] for m in L.get('compiled_modules', [])],
                        'assignment_complete': L.get('assignment_complete')})
    s['digest'] = dig
    return s

def main():
    d = A.con()
    gp = json.load(open(os.path.join(SLICE, 'gameplay.json'), encoding='utf-8'))
    gtxt = json.dumps(gp)
    fxj = json.load(open(os.path.join(SLICE, 'map_fx.json'), encoding='utf-8'))
    fxcomps = {c['component'] for c in fxj['particle_components']}
    classes = {c: factory_class_rec(c) for c in FACTORY_CLASSES}
    classes['TnPickupFactory (shared base)'] = {'cdo': 'TransGame.Default__TnPickupFactory',
                                                'effect_components': {'PickupEffect': component_rec('TransGame.Default__TnPickupFactory.PickupEffect0',
                                                                                                    'TransGame.Default__TnPickupFactory')},
                                                'native_functions': native_functions('TransGame.TnPickupFactory')}
    inst = []
    for c in FACTORY_CLASSES:
        for (o,) in d.execute('SELECT opath FROM objects WHERE class=? AND package LIKE ? ORDER BY opath', (c, MAP + '%')).fetchall():
            inst.append(instance_rec(o, gtxt, fxcomps))
    tcount = Counter(e['Template'] for i in inst for e in i['effects'].values())
    fac = {'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/vs_pickups.py',
           'source': 'manifests/authored.db (cooked tagged props of the placed factories, their component archetypes and class CDOs)',
           'factory_classes': classes, 'instances': inst,
           'counts': {'instances_by_class': dict(Counter(i['class'] for i in inst)),
                      'effect_components_by_template': dict(tcount), 'expected': EXPECTED,
                      'counts_match_expected': all(tcount.get(k) == n for k, n in EXPECTED.items())},
           'state_behaviour': {
               'authored': ['RespawnTime per instance (ammo 30 s, health 60 s, overshield 120 s; objective factories inherit '
                            '9999999 from TnGameObjectiveWeaponPickupFactory)',
                            'PickupEffect (Pickup_FX) component archetype bAutoActivate=false on every factory class',
                            'CustomPickupEffect (HealthPickup_FX / OvershieldPickup_FX) auto-activates (bAutoActivate unset = true)',
                            'health/overshield class Components array omits PickupEffect0: their Pickup_FX component is cooked but '
                            'not attached at spawn', 'ammo crate + objective classes DO list PickupEffect0 in Components (attached, inactive)',
                            'TnAmmoCratePickupFactory.ShouldDisplayHighlightFx=true (also TnWeaponPickupFactory)',
                            'objective factories: RequiredGameRuleClass (flag: TnGameRules_SingleFlagCTF, bomb: TnGameRules_ScoreBombingRun)',
                            'Engine.PickupFactory SupportedEvents include SeqEvent_PickupStatusChange'],
               'script (UnrealScript, decompiled by RE; not authored data)': [
                   'TnPickupFactory.SetPickupVisible / SetPickupHidden / SetPickupMesh / IsReadyToPickup / GiveTo / TakePickUp / '
                   'GetRespawnTime and state Pickup are UnrealScript (RE decompilation). Correction: an earlier version of this '
                   'manifest called them native stubs from their 50-144-byte export sizes - that was wrong.',
                   'TnHealthPickupFactory overrides SetPickupVisible'],
               'beam_activation (CONFIRMED - RE MILESTONE04_STREETS_PICKUP_OBJECTIVE_PRESENTATION.md s1, script decompilation)': {
                   'rule': 'TnPickupFactory.SetPickupVisible -> PickupEffect.ActivateSystem(); SetPickupHidden -> '
                           'PickupEffect.DeactivateSystem(). InitializePickup calls SetPickupVisible at begin play, so an attached '
                           'Pickup_FX beam is ON whenever the factory is available, OFF while taken/Sleeping.',
                   'ammo crates (14)': 'beam on while available, every mode; off when taken; on again after RespawnTime 30 s',
                   'flag factories (2)': 'CTF only (otherwise Disabled: actor hidden, no collision). Each round only the '
                                         'defending-team factory is in Pickup (beam on); the other Sleeps (beam off). '
                                         'Taken -> Sleeping (RespawnTime 9999999); returned -> Pickup immediately',
                   'bomb factory (1)': 'EXT only (otherwise Disabled). Taken -> Sleeping; returned after a score after '
                                       'WaitAfterScoreTime 5.0 s, other returns immediately',
                   'health / overshield Pickup_FX (10)': 'never drawn: not in the Components array, never attached',
                   'ShouldDisplayHighlightFx': 'True on TnAmmoCratePickupFactory and on TnWeaponPickupFactory (inherited by '
                                               'flag/bomb); the controlling authored value'},
               'implementation_guidance': [
                   'health/overshield: CustomPickupEffect visible while the pickup is available; hide on pickup; show again '
                   'after RespawnTime (CONFIRMED by the same SetPickupVisible/Hidden path)',
                   'ammo crate: static mesh PROP_NEU_AmmoPickup_STAT (rotating Yaw 10000/65536 turn/s) plus the Pickup_FX '
                   'highlight beam, both shown while available',
                   'health/overshield Pickup_FX components: do not render (not attached)']}}
    write('streets_pickup_factories.json', fac)
    fx = {'generated_by': 'AssetTools/scripts/wfc/vs_pickups.py', 'package': FX_PACKAGE,
          'decoder': 'scripts/wfc/pstream.py (WFC compiled particle module stream), validated by pstream_validate.py',
          'usage': {ps: {'components': n, 'role': ROLE[ps]} for ps, n in tcount.items()},
          'systems': {ps: fx_rec(ps) for ps in EXPECTED}}
    write('streets_pickup_fx.json', fx)
    print(json.dumps(fac['counts'], indent=1))
    for ps, s in fx['systems'].items():
        print(ps, [(x['emitter'], x['lod'], x['assignment_complete']) for x in s['digest']])

if __name__ == '__main__':
    main()
