"""Targeted evidence pass 2 (2026-10-01): answers to the rebuild's open questions, assembled from authored.db and the
slice manifests produced by vs_character_materials / vs_evidence / vs_mapfx / vs_audio.

Output: AssetTools/manifests/vs_evidence_pass2.json   (human summary: docs/EVIDENCE_PASS2.md)
Each item: {id, topic, confidence, source, object, value, handoff, note}.  Re-run after the inputs.
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, extract  # noqa: E402
from vs_common import VS  # noqa: E402

F = []
def item(i, topic, conf, source, obj, value, handoff, note=None):
    r = {'id': i, 'topic': topic, 'confidence': conf, 'source': source, 'object': obj, 'value': value, 'handoff': handoff}
    if note: r['note'] = note
    F.append(r)

def j(p): return json.load(open(p, encoding='utf-8'))

def main():
    OPT = os.path.join(VS, 'Characters', 'Optimus')
    MAP = os.path.join(VS, 'Maps', 'MP_IAC_Streets')
    cm = j(os.path.join(OPT, 'materials_authored.json'))
    ev = j(os.path.join(extract.MANI, 'vs_evidence.json'))
    E = {f['id']: f for f in ev['findings']}
    # ---------------------------------------------------------------- 1 materials
    T = '1 Optimus materials'
    d = cm.get('robot_mesh_discrepancy', {})
    item('P1.mesh', T, 'CONFIRMED', 'MP_IAC_Streets_BASE_m cook + Optimus_ROBODEF.SkelMesh', 'TR_Optimus_ROBO_p.RB_OptimusWeaponArm_SKEL',
         {'authored_mp_robot_mesh': cm['meshes']['robot_mp'], 'slice_robot_glb_source': cm['meshes']['robot_slice_source']['mesh'],
          'vertices_only_in_slice_source': d.get('source_vertices_absent_in_mp_mesh'), 'absent_region_gltf_bbox': d.get('absent_region_gltf_bbox')},
         'Rendering+Gameplay', d.get('note'))
    for m, r in cm['materials'].items():
        sw = {k: v['compiled_state'] for k, v in (r.get('static_switches_compiled') or {}).items() if v['compiled_state'] in (True, False)}
        eff = {k: v['value'] for k, v in (r.get('effective_parameters') or {}).items()
               if (r.get('compiled_resource_parameters') and k in {x for vv in r['compiled_resource_parameters'].values() for x in vv})}
        item('P1.mat.' + m.rsplit('.', 1)[-1], T, 'CONFIRMED (values) / HIGH (switch inference)', 'authored.db MIC chain + cooked compiled resource', m,
             {'roles': r.get('roles'), 'chain': r.get('chain'), 'meta': {k: v for k, v in (r.get('meta') or {}).items() if k in ('BlendMode', 'LightingModel', 'TwoSided', 'PhysMaterial')},
              'compiled_parameters': r.get('compiled_resource_parameters'), 'compiled_static_switches': sw,
              'final_parameters_used_by_compiled_shader': eff,
              'textures': {k: {a: (t or {}).get(a) for a in ('texture', 'file', 'Format', 'SRGB', 'UnpackMin')} for k, t in (r.get('textures') or {}).items()}},
             'Rendering')
    item('P1.team_color', T, 'CONFIRMED (values) / HIGH (runtime application)', 'TransGame class defaults', 'TnCharacterApplier + TnTeamInfo/TnFactionTeam*',
         cm['runtime_colors'], 'Rendering',
         'EnergonColor is a runtime parameter driven by team; InteriorAlt_Energon_MAT bakes its colour as switch-selected constants '
         '(red 1.25 / blue 0.2, x1.75) and is NOT recoloured by the applier.')
    # ---------------------------------------------------------------- 2 boost / dash / ram
    T = '2 boost / hover dash / ram-nitro'
    vf = 'TR_Optimus_VEHDEF_p.OptimusTruckForm'; v = A.values(vf)
    item('P2.boost', T, 'CONFIRMED (data) / HIGH (wheels-mode physics)', 'MP_IAC_Streets_BASE_m', vf + ' / VEH_Car_ANIMTREE',
         {'input': 'XboxTypeS_LeftTrigger "FineAim | Boost" -> StartBoost/StopBoost (vehicle form)',
          'anim': 'AmpAnimSwitch on _VehicleForm._InputState._Boosting: Hovering <-> Driving (wheels); transitions Nav_HoverToBoost_VEH / Nav_BoostToHover_VEH (blend 0.05/0.1)',
          'physics': {'CarBlueprint': v.get('CarBlueprint'), 'Truck_Physics': {k: x['value'] for k, x in A.effective('VEH_SHARED_p.Truck_Physics').items() if k != 'WheelPhysicsBlueprints'}},
          'fx': v.get('BoostFx'), 'sockets': {s: E['Q1.socket.' + s]['value'] for s in ('BoostSocket_L', 'BoostSocket_R')},
          'audio': {'events': {'start': 'Auto_Boost_Start -> VEH_OPTIMUS_BOOST_START', 'loop': 'Auto_Boost_Loop -> VEH_OPTIMUS_BOOST_LOOP (SoundParameter Optimus_Prime_Speed)',
                               'end': 'Auto_Boost_End -> VEH_OPTIMUS_BOOST_END', 'wheels': 'Auto_Boost_Wheels -> VEH_OPTIMUS_BOOST_WHEELS',
                               'land': 'BoostLandSound >=0.15 s Wheels_Light, >=2.0 s Wheels_Heavy'},
                    'component': {k: A.values(v['AudioComp']).get(k) for k in ('BoostFadeOutTime', 'BoostWheelsGroundCheckDelay', 'EngineFadeOutTime')}},
          'car_ai_boost_hints (TnCarFormBlueprint CDO)': {k: A.values('TransGame.Default__TnCarFormBlueprint').get(k) for k in ('BoostStartDistance', 'BoostStopDistance', 'BoostStartAngle', 'BoostStopAngle')},
          'material_change': 'none authored (no boost parameter in the vehicle master/MIC)'}, 'Gameplay+Systems')
    item('P2.hover_dash', T, 'CONFIRMED (speed/duration) / NATIVE (cooldown, trigger)', 'VEH_SHARED_p.HoverTruck_Physics', 'TnHoverCarSimulationBlueprint',
         {'DashSpeed': 3000.0, 'DashDuration': 0.5, 'class_default_DashSpeed': 5000.0, 'class_default_DashDuration': 0.3,
          'TimeBetweenDashes': 'only a x1.0 modifier is authored (TnCarForm.TimeBetweenDashesModifier); base value native',
          'fx': 'no dash-specific vehicle FX property exists (TnVehicleFormBlueprint has BoostFx/HoverFX/JumpFX only; Truck has RamFX)',
          'audio': 'no dash-specific vehicle sound event in Veh_Optimus_Prime_SoundSet',
          'robot_dodge_for_contrast': 'robot dodge = Nav_Boost_{F,B,L,R} + DashPulse_1_FX on BoosterSocket_L/R (SharedAcrobatics DodgeSpeed 3000, DodgeTime 0.5)'},
         'Gameplay', 'Keep separate from boost: dash is a hover-mode burst (TnHoverCarSimulation._DashDirection/_DashTimeRemaining).')
    item('P2.ram_nitro', T, 'CONFIRMED (data) / NATIVE (nitro timing, activation)', vf, 'TnTruckFormBlueprint + TnTruckForm',
         {'input': 'VehicleSpecialMove (RB / LeftShift) -> StartVehicleSpecialMove/StopVehicleSpecialMove; truck special = Ram (TnTruckForm._RamState, _NitroTimeRemaining)',
          'damage': {k: v.get(k) for k in ('RamDamageToPlayerRobots', 'RamDamageToAiRobots', 'RamDamageToPlayerVehicles', 'RamDamageToAiVehicles', 'ExtraRamZVelocity')},
          'fx': v.get('RamFX'), 'ram_socket': E['Q1.socket.RamSocket']['value'],
          'audio': {'Auto_Ram_Boost': 'VEH_OPTIMUS_RAM_BOOST_START (-8 dB)', 'Auto_Ram_Nitro': 'VEH_OPTIMUS_RAM_NITRO_START (-5 dB, layers incl. MECH_TRANS_RAM_ACTIVATE)',
                    'Auto_Ram_Impact': 'BL_VEH_SOUNDWAVE.VEH_TRUCK_RAM_IMPACT (3 variants)', 'Auto_Ram_Alert': 'BL_VEH_SOUNDWAVE.VEH_TRUCK_RAM_ALERT (-15 dB, looping CustomLoopingSound)'},
          'nitro_force_feedback (TnTruckFormBlueprint CDO)': A.values('TransGame.Default__TnTruckFormBlueprint').get('NitroForceFeedback'),
          'nitro_base_values': 'NOT authored: only x1.0 modifiers (NitroDuration/SpeedScale/SteeringScale/TimeBetweenNitros, MaxRamMass) on TnTruckForm CDO',
          'anim': 'VEH_Car_ANIMTREE Ram state names Transform_RamIn_VEH / Transform_RamOut_VEH, but NO such AnimSequence exists anywhere in the cook -> no ram animation'},
         'Gameplay+Systems', 'Nitro duration INFERRED ~3 s only from NitroForceFeedback Duration 3.0 (not a gameplay value).')
    # ---------------------------------------------------------------- 3 transformation
    T = '3 transformation presentation'
    for k in ('Q5.notifies.Transform_ToVehicle_ROBO', 'Q5.notifies.Transform_ToRobot_ROBO', 'Q5.notifies.Transform_ToVehicle_VEH',
              'Q5.notifies.Transform_ToRobot_VEH', 'Q5.visibility_timeline', 'Q5.cues', 'Q5.blend', 'Q5.weapon_restore', 'Q5.root_motion', 'Q5.camera'):
        f = E[k]; item('P3.' + k.split('.', 1)[1], T, f['confidence'], f['source_package'], f['object'], f['value'], f['handoff'], f.get('note'))
    item('P3.no_transform_fx', T, 'CONFIRMED (absence)', 'schema + Optimus clips', 'TnTransformer / TnTransformation / forms',
         {'transform_effect_properties': 'none in the schema (only TnPawn._RestoreWeaponTransformFractionRemaining, TnPlayerController.TransformFailedSound)',
          'TransformFailedSound': A.values([r['opath'] for r in A.find('%.Default__TnPlayerController')][0]).get('TransformFailedSound'),
          'effects_in_clips': 'Optimus transform clips carry no HmAnimNotify_PlayEffect; vehicle FX toggled by TnAnimNotify_ToggleVehicleFx'},
         'Systems')
    # ---------------------------------------------------------------- 4 fine aim
    T = '4 fine aim'
    for k in ('Q3.fov', 'Q3.orbit_distance', 'Q3.look_speed', 'Q3.offset', 'Q3.transition', 'Q3.weapon_pcs', 'Q3.fineaim_manager', 'Q3.ionblaster_fineaim', 'Q3.bindings'):
        f = E[k]; item('P4.' + k.split('.', 1)[1], T, f['confidence'], f['source_package'], f['object'], f['value'], f['handoff'], f.get('note'))
    wm = A.values('WEP_IonBlaster_p.IonBlaster_WEPMESH')
    snd = {e['WeaponEventType']: e['WeaponSound'] for e in wm.get('WeaponEventSounds') or [] if 'FineAim' in e['WeaponEventType']}
    item('P4.sounds', T, 'CONFIRMED', 'MP_IAC_Streets_BASE_m', 'WEP_IonBlaster_p.IonBlaster_WEPMESH.WeaponEventSounds', {
        'events': snd, 'cues': {c: {'root': {k: A.cue(c).get('root', {}).get(k) for k in ('Volume', 'DistanceMin', 'Category')},
                                    'waves': [(w['wave'], w['wav']) for w in A.cue(c)['waves']]} for c in snd.values()}}, 'Systems',
         'Gun foley + robot movement foley variants; the Ion Blaster reuses the PULSE_RIFLE fine-aim cues.')
    # ---------------------------------------------------------------- 5 locomotion
    T = '5 fast robot movement'
    for k in ('Q4.blueprint_speed', 'Q4.velocity_blend', 'Q4.clip_speeds', 'Q4.acrobatics', 'Q4.acrobatics_slot', 'Q4.momentum'):
        f = E[k]; item('P5.' + k.split('.', 1)[1], T, f['confidence'], f['source_package'], f['object'], f['value'], f['handoff'], f.get('note'))
    item('P5.rate', T, 'CONFIRMED (absence)', 'schema + Robot_ANIMTREE', 'TnVelocityAnimBlend / AnimNodeSequence', {
        'TnVelocityAnimBlend_props': ['MinSpeed 450', 'MaxSpeed 1200'], 'strafer_nodes_Rate': 'not authored (1.0)', 'Strafers synch RateScale': 1.0,
        'sprint_state': 'none (no run/sprint clip, node or input; LT is FineAim on foot)'}, 'Gameplay',
         'Play-rate scaling with speed (foot-slip) is not authored; at BaseGroundSpeed 1400 the 12-12.8 m/s jog clips would slip ~10% unless native scales them.')
    # ---------------------------------------------------------------- 6 map effects
    T = '6 map effect fidelity'
    fx = j(os.path.join(MAP, 'map_fx.json')); au = j(os.path.join(MAP, 'audio.json'))
    em = [c for c in fx['particle_components'] if c['owner_class'] == 'Emitter']
    aud = [(e['tag'], e['cue'], np.array(e['location_ue'])) for k in ('point', 'volume', 'line') for e in au['emitters'][k]]
    rows = []
    for c in em:
        p = np.array(c['ue_matrix'][3][:3]); dd, tg, cu = min(((float(np.linalg.norm(p - a[2])), a[0], a[1]) for a in aud), key=lambda x: x[0])
        sc = (c['props'].get('InstanceParameters') or [{}])[0].get('Color')
        rows.append({'emitter': c['owner'].rsplit('.', 1)[-1], 'template': c['props'].get('Template'), 'steam_color_rgb': [sc['R'], sc['G'], sc['B']] if sc else None,
                     'prefab': c['prefab'], 'location_ue': p.round(1).tolist(), 'gltf_matrix': c['gltf_matrix'],
                     'nearest_audio': {'tag': tg, 'cue': cu, 'distance_ue': round(dd)}})
    ps = fx['particle_systems']['FX_Level_Generic_p.FX.Steam_Sm_FX']
    item('P6.emitters', T, 'CONFIRMED (actors/templates/transforms) / INFERRED (audio pairing by proximity)', 'MP_IAC_Streets_ART_m', 'Emitter x8', rows,
         'Rendering+Systems', 'There are exactly 8 level emitters; the prefab steam vent IS Emitter_5707 (PrefabInstance_4340 ArchetypeToInstanceMap), not a 9th. '
         'No authored emitter<->sound link exists; each steam emitter sits 2-15 m from an EMIT_ENERGON_VENTS / EMIT_ENERGON_LIQUID_CRATERS audio emitter.')
    em0 = ps['emitters'][0]; rq = em0['lods'][0].get('RequiredModule', {}).get('props', {})
    item('P6.steam_fx', T, 'CONFIRMED (tagged) / PARTIAL (module roles)', 'MP_IAC_Streets_ART_m', 'FX_Level_Generic_p.FX.Steam_Sm_FX', {
        'LODDistances': ps['props'].get('LODDistances'), 'emitter': em0['name'], 'lods': len(em0['lods']),
        'required': {k: rq.get(k) for k in ('Material', 'SpawnRate', 'BurstList', 'EmitterLoops', 'EmitterDuration')},
        'native_distribution_tables_lod0': em0['lods'][0]['native_stream'],
        'material': 'FX_Materials_p.Materials.Steam_Mat: Translucent + Unlit, SmokeBall_CLR/SmokeTile_CLR, DynamicParameter "Desat1", BiasScale 500 (depth-biased alpha)',
        'instance_parameter': 'SteamColor (per-emitter colour override; routed to the particle colour module, native stream)'}, 'Rendering')
    out = {'schema': 'vs_evidence_pass2/1', 'generated_by': 'AssetTools/scripts/wfc/vs_evidence2.py', 'items': F,
           'consume': {
               'Rendering': ['ExtractedAssets/VerticalSlice/Characters/Optimus/materials_authored.json',
                             'ExtractedAssets/content/TR_Optimus_ROBO_p/RB_OptimusWeaponArm_SKEL.gltf (authored MP robot mesh)',
                             'ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/{materials_authored,lighting,postprocess,map_fx}.json',
                             'AssetTools/manifests/vs_evidence_pass2.json'],
               'Gameplay': ['AssetTools/manifests/vs_evidence.json (Q3,Q4,Q5)', 'AssetTools/manifests/vs_evidence_pass2.json (P2-P5)',
                            'ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/{gameplay,physics}.json + collision_pawn.glb / collision_weapon.glb'],
               'Systems': ['AssetTools/manifests/vs_evidence.json (Q1 cues/FX)', 'AssetTools/manifests/vs_evidence_pass2.json (P2,P3,P4.sounds,P6)',
                           'ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/{audio,map_fx}.json']}}
    path = os.path.join(extract.MANI, 'vs_evidence_pass2.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    from collections import Counter
    print('items', len(F), dict(Counter(f['topic'] for f in F)), '->', path)

if __name__ == '__main__':
    main()
