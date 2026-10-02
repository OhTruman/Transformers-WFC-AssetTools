"""Authoritative material handoff for the slice character (Optimus robot + vehicle), from manifests/authored.db.

Output: ExtractedAssets/VerticalSlice/Characters/Optimus/materials_authored.json
  meshes        the AUTHORED MP meshes (Optimus_ROBODEF.SkelMesh, OptimusTruckForm.SkeletalMesh, ArmBlueprint mesh) with
                umodel slot order, glTF path, and the comparison against the slice's robot.glb source mesh
  materials{}   vs_materials.describe() records (MIC chain, effective params incl. MaterialFunctions, textures/sets,
                compiled-resource parameter names) for every slot + overshield/energy-death/buff materials
  runtime_colors  the TnCharacterApplier parameter bindings and where each final value comes from (team / character data)
  python vs_character_materials.py
"""
import json, os, sys, glob
from collections import Counter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, vs_materials as VM  # noqa: E402
from vs_common import VS, ROOT, load_gltf, accessor  # noqa: E402

OUT = os.path.join(VS, 'Characters', 'Optimus')

def gltf_info(mesh_op):
    name = mesh_op.rsplit('.', 1)[-1]; pkg = mesh_op.split('.')[0]
    c = glob.glob(os.path.join(ROOT, 'content', pkg, '**', name + '.gltf'), recursive=True)
    if not c: return {'gltf': None}
    j, b = load_gltf(c[0])
    prims = j['meshes'][0]['primitives']
    return {'gltf': os.path.relpath(c[0], ROOT).replace(os.sep, '/'),
            'slots_umodel': [m.get('name') for m in j['materials']],
            'triangles': sum(j['accessors'][p['indices']]['count'] // 3 for p in prims),
            'vertices': sum(j['accessors'][p['attributes']['POSITION']]['count'] for p in prims),
            'joints': len(j.get('skins', [{}])[0].get('joints', [])),
            '_P': np.concatenate([accessor(j, b, p['attributes']['POSITION']) for p in prims])}

def main():
    robodef = 'TR_Optimus_ROBODEF_p.Optimus_ROBODEF'; rd = A.values(robodef)
    vehdef = rd['TransformerVehicle']; vd = A.values(vehdef)
    meshes = {'robot_mp': rd['SkelMesh'], 'vehicle_mp': vd['SkeletalMesh'],
              'arm_blueprint': (rd.get('ArmBlueprint') or {}).get('Mesh'), 'robot_slice_source': 'TR_Optimus_ROBO_p.RB_Optimus_A_SKELMESH'}
    out = {'character': 'Optimus Prime', 'definitions': {'robot': robodef, 'vehicle': vehdef}, 'meshes': {}, 'materials': {}, 'notes': []}
    info = {}
    for k, m in meshes.items():
        if not m: continue
        gi = gltf_info(m); info[k] = gi
        rows = A.con().execute('SELECT package FROM objects WHERE opath = ?', (m,)).fetchall()
        out['meshes'][k] = {'mesh': m, **{a: b for a, b in gi.items() if not a.startswith('_')}}
    # robot_mp vs robot_slice_source geometry diff
    if 'robot_mp' in info and 'robot_slice_source' in info and info['robot_mp'].get('gltf') and info['robot_slice_source'].get('gltf'):
        PW = info['robot_mp']['_P']; PA = info['robot_slice_source']['_P']
        S = set(map(tuple, np.round(PW / 0.002).astype(int)))
        miss = np.array([tuple(np.round(p / 0.002).astype(int)) not in S for p in PA])
        out['robot_mesh_discrepancy'] = {
            'slice_robot_glb_source': meshes['robot_slice_source'], 'authored_mp_mesh': meshes['robot_mp'],
            'source_vertices_absent_in_mp_mesh': int(miss.sum()),
            'absent_region_gltf_bbox': [PA[miss].min(0).round(3).tolist(), PA[miss].max(0).round(3).tolist()] if miss.any() else None,
            'note': 'The MP mesh omits the right forearm/elbow geometry (verts weighted to R_Arm03_Elbow_XB / R_ElbowRobo01-02_XT) '
                    'where WeaponSocket_Primary (bone R_Arm03_Elbow_XB) mounts the weapon. Same 106-joint skeleton and bounds, so '
                    'all robot.glb animations apply unchanged. Material slot ORDER differs (see slots_umodel). '
                    'RB_Optimus_A_SKELMESH is cooked only into campaign design/vignette/cine sublevels, never into Streets.'}
    # materials
    slot_mats = {k: v.get('slots_umodel') for k, v in out['meshes'].items()}
    mats = set()
    for k in ('robot_mp', 'vehicle_mp', 'arm_blueprint'):
        m = A.values(meshes[k]) if meshes.get(k) else {}
    # slot materials come from the cooked skeletal-mesh LODs (native); resolve umodel short names within the mesh package family
    def resolve_short(short, pkgs):
        for pk in pkgs:
            r = A.find(pk + '.%' + short)
            r = [x for x in r if x['opath'].rsplit('.', 1)[-1] == short and x['class'].startswith('Material')]
            if r: return r[0]['opath']
        return None
    pk_robot = ['TR_Optimus_ROBO_p', 'TR_AllShader_p']; pk_veh = ['TR_Optimus_VEH_p', 'TR_AllShader_p']
    for k, pk in (('robot_mp', pk_robot), ('vehicle_mp', pk_veh), ('arm_blueprint', pk_robot)):
        res = [resolve_short(s, pk) for s in (out['meshes'].get(k, {}).get('slots_umodel') or [])]
        if k in out['meshes']: out['meshes'][k]['slot_materials'] = res
        mats.update(x for x in res if x)
    for extra in (rd.get('OvershieldMaterial'), rd.get('EnergyDeathMaterial'), vd.get('OvershieldMaterial'), vd.get('EnergyDeathMaterial')):
        if extra: mats.add(extra)
    for x in (rd.get('BuffMaterials') or []) + (vd.get('BuffMaterials') or []):
        if x: mats.add(x)
    roles = {}
    for k in ('robot_mp', 'vehicle_mp', 'arm_blueprint'):
        for i, m in enumerate(out['meshes'].get(k, {}).get('slot_materials') or []):
            if m: roles.setdefault(m, []).append('%s slot %d' % (k, i))
    for key, lab in (('OvershieldMaterial', 'overshield'), ('EnergyDeathMaterial', 'energy death (defrag)')):
        if rd.get(key): roles.setdefault(rd[key], []).append('robot ' + lab)
        if vd.get(key): roles.setdefault(vd[key], []).append('vehicle ' + lab)
    for m in sorted(mats):
        rec = VM.describe(m, {'roles': roles.get(m, [])})
        rec['roles'] = roles.get(m, [])
        out['materials'][m] = rec
    out['masters'] = {k: v for k, v in VM.MASTERS.items() if any(r.get('master') == k for r in out['materials'].values())}
    # runtime colours
    ap = A.values('TransGame.Default__TnCharacterApplier')
    teams = {'neutral (TnTeamInfo)': A.values('TransGame.Default__TnTeamInfo').get('EnergonColor'),
             'Autobots (TnFactionTeamAutobots)': A.values('TransGame.Default__TnFactionTeamAutobots').get('EnergonColor'),
             'Decepticons (TnFactionTeamDecepticons)': A.values('TransGame.Default__TnFactionTeamDecepticons').get('EnergonColor')}
    pcd = {o: (A.values(o).get('Data') or {}) for o in ('TR_SPPlayerCharacterData_p.OptimusPrime_PCD_SP', 'TR_SPPlayerCharacterData_p.Optimus_PCD_SP',
                                                        'TR_MPPlayerCharacterData_p.Leader_PCD_MP')}
    out['runtime_colors'] = {
        'applier_parameter_bindings (TransGame.Default__TnCharacterApplier, CONFIRMED)': {
            'PrimaryColorMaterialParamName': ap.get('PrimaryColorMaterialParamName'),
            'SecondaryColorMaterialParamName': ap.get('SecondaryColorMaterialParamName'),
            'EnergonColorMaterialParamName': ap.get('EnergonColorMaterialParamName')},
        'team_energon_colors (class defaults, CONFIRMED)': teams,
        'master_energon_switch_constants': 'CHR_Transformer_NormSpec_Cust_E_Mat: Neutral (0.843,0.302,0.029) / Autobot (1.25,0.05,0.05) / '
                                           'Decepticon-branch (0.2,0.1,1.5) = exactly the three team colours above',
        'character_data_colors': {o: {k: d.get(k) for k in ('CharacterName', 'Factions', 'ChassisTypes', 'PrimaryColors', 'SecondaryColors', 'EnergonColor')}
                                  for o, d in pcd.items()},
        'customization_config': 'TransCustomization.ini [Truck TnDataProvider_Chassis] UniqueIconicId="Optimus Prime", ObjectPath='
                                'TR_Optimus_ROBODEF_p.Optimus_ROBODEF, DefaultSpecialty Leader (iconic chassis)',
        'final_value_resolution': {
            'EnergonColor': 'team colour pushed by the applier at runtime (Autobot team -> (1.25,0.05,0.05) red; equals the compiled '
                            'default). Application/timing native: HIGH CONFIDENCE.',
            'Cust_Color_A / Cust_COLOR_B': 'Optimus character data authors blank (0,0,0,255) colours: INFERRED the applier does not '
                                           'override iconic characters, so the MIC values stand (robot Cust_Mat_INST_B / vehicle '
                                           'Cust2_Mat_INST values in materials{}).'}}
    out['notes'] += [
        'Per-instance static switches are compiled into each MIC (native permutation, not decoded). Evidence per instance is '
        'compiled_resource_parameters: the parameter names the compiled shader reads.',
        'Effective parameters include those declared inside MaterialFunctions (vs_materials.describe).']
    path = os.path.join(OUT, 'materials_authored.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps({'meshes': {k: (v['mesh'], v.get('slots_umodel'), v.get('triangles')) for k, v in out['meshes'].items()},
                      'materials': {m: r.get('roles') for m, r in out['materials'].items()},
                      'discrepancy_verts': (out.get('robot_mesh_discrepancy') or {}).get('source_vertices_absent_in_mp_mesh')}, default=str, indent=1))
    print('->', path)

if __name__ == '__main__':
    main()
