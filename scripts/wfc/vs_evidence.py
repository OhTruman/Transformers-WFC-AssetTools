"""Targeted authored-evidence manifest for the integrated vertical slice
(Optimus robot/vehicle, Ion Blaster, MP_IAC_Streets).

Answers the Experimental/Fidelity agent's open questions straight from cooked data and
writes AssetTools/manifests/vs_evidence.json.  Every finding is a record:
  {id, question, confidence, source_package, object, class, property, value, handoff, note}
Confidence vocabulary: CONFIRMED | HIGH CONFIDENCE | PARTIAL | INFERRED | UNKNOWN.
Raw supporting dumps (cue graphs, particle summaries, camera strategies, material
traces) are kept under 'supporting'.

Evidence package for the slice: MP_IAC_Streets_BASE_m (holds the complete Optimus /
Ion Blaster / camera / anim-tree cook); TransGame.xxx for class defaults; the map's
ART package for placed content.  Re-run:  python vs_evidence.py   (~1-2 min)
"""
import glob, json, os, re, sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, effective, particles, matgraph, extract  # noqa: E402
import typed_props as tp  # noqa: E402

PKG = 'MP_IAC_Streets_BASE_m'
ART = 'MP_IAC_Streets_ART_m'
ROOT = os.path.dirname(extract.OUT)          # ExtractedAssets
CFG = os.path.join(ROOT, 'config', 'Coalesced_ini', 'TransGame', 'Config', 'Xenon', 'Cooked')

F = []
def find(qid, question, conf, obj, prop, value, handoff, note=None, pkg=PKG, cls=None):
    if cls is None:
        try:
            p = objtree.package(pkg); i = p._idx.get(obj.lower())
            cls = p.class_name(p.exports[i - 1]) if i else None
        except Exception:
            cls = None
    r = OrderedDict([('id', qid), ('question', question), ('confidence', conf), ('source_package', pkg),
                     ('object', obj), ('class', cls), ('property', prop), ('value', value), ('handoff', handoff)])
    if note: r['note'] = note
    F.append(r)

def props(obj, pkg=PKG):
    p = objtree.package(pkg); i = p._idx.get(obj.lower())
    return tp.simplify(p._tr.read_dict(i)) if i else None

def eff(obj, pkg=PKG):
    return effective.effective(obj, pkg)

_wav = None
def wav_of(wave_opath):
    global _wav
    if _wav is None:
        _wav = {}
        for fn in ('audio_native.jsonl', 'audio.jsonl'):
            for l in open(os.path.join(extract.MANI, 'extracted', fn), encoding='utf-8'):
                r = json.loads(l); o = r.get('output') or ''
                w = os.path.splitext(o)[0] + '.wav'
                if os.path.exists(os.path.join(ROOT, w)): _wav.setdefault(r['object_path'], w)
    return _wav.get(wave_opath)

def cue(opath, pkg=PKG):
    """SoundCue graph -> {root params, category, events:[{time, volume, pitch, wave, wav}], nodes}"""
    flat = objtree.flatten(objtree.dump(opath, pkg, max_depth=10))
    out = {'cue': opath, 'nodes': {}}
    for k, v in flat.items():
        c = v['class']; pr = v['props']
        if c == 'SoundNodeRoot':
            out['root'] = {a: b for a, b in pr.items() if a not in ('ChildNodes', 'Category', 'SecondaryCategory', 'PlayMixerPreset')}
            for a in ('Category', 'SecondaryCategory'):
                if pr.get(a) in flat: out[a.lower()] = flat[pr[a]]['props'].get('CategoryName')
        elif c in ('SoundNodeWaveEx', 'SoundNodeWave'):
            out['nodes'][k] = {'class': c, 'duration': pr.get('Duration'), 'wav': wav_of(k)}
        elif c != 'SoundCue' and not c.startswith('SoundMixer'):
            out['nodes'][k] = {'class': c, 'props': pr}
    ev = []
    for k, v in flat.items():
        if v['class'] == 'SoundNodeWaveEvent':
            kids = [x for x in (v['props'].get('ChildNodes') or []) if x]
            w = kids[0] if kids else None
            # several children = variants (class default LastWaveNode -1: random / no-repeat pick, INFERRED)
            ev.append({'time': v['props'].get('Time', 0.0), 'volume_db': v['props'].get('Volume', 0.0),
                       'pitch': v['props'].get('Pitch', 0.0), 'wave': w, 'wav': wav_of(w) if w else None,
                       'variants': [{'wave': x, 'wav': wav_of(x)} for x in kids] if len(kids) > 1 else None,
                       'other': {a: b for a, b in v['props'].items() if a not in ('Time', 'Volume', 'Pitch', 'ChildNodes')}})
    out['wave_events'] = sorted(ev, key=lambda e: e['time'])
    return out

def anim_seqs(animset, pkg=PKG):
    """AnimSet -> {SequenceName: {length, frames, rate, additive, translation_scale, notifies[]}}"""
    p = objtree.package(pkg)
    ad = props(animset, pkg) or {}
    out = {}
    for s in ad.get('Sequences') or []:
        d = props(s, pkg) or {}
        nots = []
        for n in d.get('Notifies') or []:
            o = n.get('Notify'); nd = None; ncls = None
            if o and o.lower() in p._idx:
                nd = props(o, pkg); ncls = p.class_name(p.exports[p._idx[o.lower()] - 1])
                # resolve enum defaults (option byte 0 when not serialized)
                if ncls == 'TnAnimNotify_ToggleHidden' and 'Option' not in nd: nd['Option'] = 'Toggle_Unhide (class default, enum 0)'
                if ncls == 'TnAnimNotify_ToggleVehicleFx' and 'Option' not in nd: nd['Option'] = 'Toggle_EnableFx (class default, enum 0)'
            nots.append({'time': n.get('Time'), 'duration': n.get('Duration'), 'class': ncls, 'props': nd, 'object': o})
        out[d.get('SequenceName')] = {'object': s, 'length': d.get('SequenceLength'), 'frames': d.get('NumFrames'),
                                      'rate_scale': d.get('RateScale', 1.0), 'additive': d.get('bIsAdditive', False),
                                      'translation_scale': d.get('TranslationScale'), 'loop_offset': d.get('LoopOffsetTime'),
                                      'notifies': sorted(nots, key=lambda x: x['time'] or 0)}
    return out

def tree_nodes(tree, pkg=PKG):
    p = objtree.package(pkg); pre = tree.lower() + '.'
    out = {}
    for k, i in sorted(p._idx.items(), key=lambda x: x[1]):
        if not (k.startswith(pre) or k == tree.lower()): continue
        c = p.class_name(p.exports[i - 1])
        if c.startswith(('MaterialExpression',)): continue
        try: d = tp.simplify(p._tr.read_dict(i))
        except Exception as ex: d = {'__error__': str(ex)}
        for ch in d.get('Children') or []:
            if isinstance(ch, dict):
                for x in ('Weight', 'TotalWeight', 'bMirrorSkeleton', 'DrawY'): ch.pop(x, None)
        for x in ('PreviewCamPos', 'PreviewCamRot', 'MorphConnDrawY', 'NodePosX', 'NodePosY', 'DrawWidth', 'DrawHeight', 'OutDrawY'):
            d.pop(x, None)
        out[p.object_path(i)] = {'class': c, 'props': d}
    return out

def sockets(mesh, pkg=PKG):
    p = objtree.package(pkg); pre = mesh.lower() + '.'
    out = {}
    for k, i in p._idx.items():
        if k.startswith(pre) and p.class_name(p.exports[i - 1]) == 'SkeletalMeshSocket':
            d = props(p.object_path(i), pkg)
            out[d.get('SocketName')] = {'bone': d.get('BoneName'), 'location_ue': d.get('RelativeLocation', {'X': 0, 'Y': 0, 'Z': 0}),
                                        'rotation_ue': d.get('RelativeRotation', {'Pitch': 0, 'Yaw': 0, 'Roll': 0}),
                                        'scale': d.get('RelativeScale', {'X': 1, 'Y': 1, 'Z': 1}), 'object': p.object_path(i)}
    return dict(sorted(out.items()))

def ini_lines(fname, pattern):
    path = os.path.join(CFG, fname)
    if not os.path.exists(path): return []
    return [l.rstrip() for l in open(path, encoding='utf-8', errors='replace') if re.search(pattern, l)]

# ===================================================================================== Q1
def q1(sup):
    Q = '1 vehicle boost presentation'
    vf = 'TR_Optimus_VEHDEF_p.OptimusTruckForm'
    v = props(vf)
    for key, h in (('BoostFx', 'Systems'), ('HoverFX', 'Systems'), ('JumpFX', 'Systems'), ('RamFX', 'Systems')):
        find('Q1.' + key, Q, 'CONFIRMED', vf, key, v.get(key), h,
             'TnVehicleFxPlayer.VehicleFxParams: particle template per vehicle socket')
    sk = sockets('TR_Optimus_VEH_p.VH_OptimusPrime_SKEL')
    sup['vehicle_sockets'] = sk
    for s in ('BoostSocket_L', 'BoostSocket_R', 'JumpBoostSocket_C', 'JumpBoostSocket_L', 'JumpBoostSocket_R',
              'HoverBooster_LFront', 'HoverBooster_RFront', 'HoverBooster_LBack', 'HoverBooster_RBack',
              'HoverBooster_LBack2', 'HoverBooster_RBack2', 'RamSocket'):
        find('Q1.socket.' + s, Q, 'CONFIRMED', sk[s]['object'], 'SocketName/BoneName/RelativeLocation/RelativeRotation/RelativeScale',
             {k: sk[s][k] for k in ('bone', 'location_ue', 'rotation_ue', 'scale')}, 'Systems',
             'UE units/rotator units (65536 = 360 deg), relative to the bone')
    sup['particle_systems'] = {}
    for ps in sorted({x['ParticleSystemTemplate'] for k in ('BoostFx', 'HoverFX', 'JumpFX', 'RamFX') for x in (v.get(k) or [])} |
                     {'FX_Navigation_p.DashPulse_1_FX'}):
        try:
            s = particles.summarize(ps, PKG); sup['particle_systems'][ps] = s
            ems = [{'name': e['name'], 'material': (e['lods'][0].get('RequiredModule') or {}).get('props', {}).get('Material'),
                    'duration': (e['lods'][0].get('RequiredModule') or {}).get('props', {}).get('EmitterDuration'),
                    'loops': (e['lods'][0].get('RequiredModule') or {}).get('props', {}).get('EmitterLoops', 0),
                    'burst': (e['lods'][0].get('RequiredModule') or {}).get('props', {}).get('BurstList'),
                    'local_space': (e['lods'][0].get('RequiredModule') or {}).get('props', {}).get('bUseLocalSpace'),
                    'type_data': (e['lods'][0].get('TypeDataModule') or {}).get('class'), 'mesh': e['lods'][0].get('mesh')}
                   for e in s['emitters'] if e['lods']]
            find('Q1.fx.' + ps.rsplit('.', 1)[-1], Q, 'CONFIRMED', ps, 'Emitters[].LOD0.RequiredModule/TypeDataModule', ems, 'Systems',
                 'EmitterLoops 0 (absent) = loop forever in UE3; full module distribution tables in supporting.particle_systems '
                 '(native per-LOD stream: values CONFIRMED, module role by order = PARTIAL)')
        except Exception as ex:
            sup['particle_systems'][ps] = {'error': str(ex)}
    ac = vf + '.HmPlayerVehicleAudioComponent_6670'
    find('Q1.audio_component', Q, 'CONFIRMED', ac, 'BoostSound/BoostSounds/BoostStopSound/BoostWheelsSound/BoostLandSound/...',
         props(ac), 'Systems', 'Events are SoundEvents_Vehicles.* names; mapped to cues by the SoundEventSet below')
    ss = 'SoundEvents_Vehicles_Trans.Veh_Optimus_Prime_SoundSet'
    sset = props(ss)
    find('Q1.sound_event_set', Q, 'CONFIRMED', ss, 'SoundEventSet[] (Event -> Sound)',
         {e['Event'].rsplit('.', 1)[-1]: e['Sound'] for e in sset['SoundEventSet']}, 'Systems')
    sup['cues'] = {}
    for c in sorted({e['Sound'] for e in sset['SoundEventSet'] if e.get('Sound') and 'OPTIMUS' in e['Sound']}):
        sup['cues'][c] = cue(c)
    for c in ('BL_VEH_OPTIMUS_PRIME.VEH_OPTIMUS_BOOST_START', 'BL_VEH_OPTIMUS_PRIME.VEH_OPTIMUS_BOOST_LOOP',
              'BL_VEH_OPTIMUS_PRIME.VEH_OPTIMUS_BOOST_END', 'BL_VEH_OPTIMUS_PRIME.VEH_OPTIMUS_BOOST_WHEELS'):
        g = sup['cues'][c]
        find('Q1.cue.' + c.rsplit('.', 1)[-1], Q, 'CONFIRMED', c, 'SoundNodeRoot + SoundNodeWaveEvent graph',
             {'root': g.get('root'), 'category': g.get('category'),
              'wave_events': [{k: e[k] for k in ('time', 'volume_db', 'pitch', 'wave', 'wav', 'variants')} for e in g['wave_events']]},
             'Systems', 'Volume dB, Pitch = semitone offset (field names; FMOD Ex semantics HIGH CONFIDENCE)')
    tree = 'VEH_Proxy_p.VEH_Car_ANIMTREE'
    sup['vehicle_animtree'] = tree_nodes(tree)
    find('Q1.anim.boost_switch', Q, 'CONFIRMED', tree + '.AmpAnimSwitch_3253', 'SelectorProperty / Children',
         {'selector': '_VehicleForm._InputState._Boosting', 'children': {'0 (not boosting)': 'Hovering state',
          '1 (boosting)': 'Driving state (no clip; wheels via SkelControlWheel; Ram sub-switch)'}}, 'Gameplay')
    find('Q1.anim.boost_transitions', Q, 'CONFIRMED', tree, 'HmAnimTransitionWithBlend_7946 / _3724',
         {'Hovering.Default -> Nav_HoverToBoost_VEH': {'BlendIn': 0.05, 'BlendOut': 0.1},
          'Driving.Default  -> Nav_BoostToHover_VEH': {'BlendIn': 0.05, 'BlendOut': 0.1}}, 'Gameplay',
         'Nav_HoverToBoost_VEH IS the authored normal-boost entry clip. Which edge (enter vs leave) plays the "Default" '
         'transition is AmpAnimState native logic: INFERRED = played when leaving the state (HoverToBoost on hover->boost).')
    find('Q1.anim.hover_blend', Q, 'CONFIRMED', tree + '.TnAccelerationAnimBlend_2889', 'Children',
         'Idle/Up/Down=Nav_Hover_Pose_VEH, Forward=Nav_Hover_F_VEH, Backward=Nav_Hover_B_VEH, Right=Nav_Hover_R_VEH, '
         'Left=Nav_Hover_L_VEH; + additive ADD_Nav_Hover_VEH (looping)', 'Gameplay',
         'Blend driven by ACCELERATION (class name), not velocity - weighting law native (UNKNOWN)')
    find('Q1.physics.hover', Q, 'CONFIRMED', 'VEH_SHARED_p.HoverTruck_Physics', 'effective (object over Default__TnHoverCarSimulationBlueprint)',
         {k: x['value'] for k, x in eff('VEH_SHARED_p.HoverTruck_Physics').items()}, 'Gameplay',
         'CORRECTION: the Optimus hover blueprint overrides DashSpeed 3000 (CDO 5000), DashDuration 0.5 (CDO 0.3), '
         'SuspensionRadius 185 (CDO 200). Suspension: HoverTruck_Suspension Damping 4000 RestingLength 250.')
    find('Q1.physics.car', Q, 'CONFIRMED', 'VEH_SHARED_p.Truck_Physics', 'effective', {k: x['value'] for k, x in eff('VEH_SHARED_p.Truck_Physics').items()},
         'Gameplay', 'CarBlueprint of OptimusTruckForm. HIGH CONFIDENCE that boost = wheels-down car mode (Driving anim state keyed on '
         '_Boosting, BoostWheelsSound + BoostWheelsGroundCheckDelay 0.27, BoostLandSound = wheel-land cues): the switch to '
         'CarBlueprint physics while boosting is native (INFERRED).')
    m = matgraph.graph('TR_AllShader_p.Release.CHR_Transformer_NormSpec_Cust_E_Mat', PKG)
    pnames = sorted({n['props'].get('ParameterName') for n in m['nodes'].values() if n['props'].get('ParameterName')})
    find('Q1.boost_material', Q, 'CONFIRMED', 'TR_AllShader_p.Release.CHR_Transformer_NormSpec_Cust_E_Mat', 'parameter names',
         [x for x in pnames if re.search('boost|speed|thrust', x, re.I)], 'Rendering',
         'No boost-driven material parameter exists in the vehicle master or MIC; boost visuals are particle FX only. '
         'TnAnimNotify_ToggleVehicleFx toggles the vehicle FX set around transforms.')

# ===================================================================================== Q2
def q2(sup):
    Q = '2 Optimus vehicle materials'
    chain = matgraph.mic_chain('TR_Optimus_VEH_p.RB_OptimusPrime_Cust2_Mat_INST', PKG)
    sup['vehicle_mic_chain'] = [{'object': c['object'], 'class': c.get('class'), 'package': c.get('package'),
                                 'props': {k: v for k, v in (c.get('props') or {}).items() if k not in ('ReferencedTextures', 'ExpressionTree', 'Expressions')}}
                                for c in chain]
    mic = chain[0]['props']
    find('Q2.mic', Q, 'CONFIRMED', chain[0]['object'], 'Texture/Scalar/VectorParameterValues, Parent',
         {'parent': mic.get('Parent'),
          'textures': {x['ParameterName']: x['ParameterValue'] for x in mic.get('TextureParameterValues', [])},
          'scalars': {x['ParameterName']: x['ParameterValue'] for x in mic.get('ScalarParameterValues', [])},
          'vectors': {x['ParameterName']: x['ParameterValue'] for x in mic.get('VectorParameterValues', [])}},
         'Rendering', 'Vehicle slot 0 material (slot 1 = InteriorAlt_Energon_MAT_INST). Chain length 2: MIC -> master Material.')
    M = 'TR_AllShader_p.Release.CHR_Transformer_NormSpec_Cust_E_Mat'
    g = matgraph.graph(M, PKG)
    sup['master_parameters'] = {n['props']['ParameterName'] + ('#' + k.rsplit('_', 1)[-1] if n['class'].endswith('VectorParameter') else ''):
                                {'class': n['class'], 'default': n['props'].get('DefaultValue', n['props'].get('Texture'))}
                                for k, n in g['nodes'].items() if n['props'].get('ParameterName')}
    find('Q2.normal_alpha', Q, 'CONFIRMED', M, 'consumers of VarienceNormal_XY_Map / Normal_Map',
         {'VarienceNormal_XY_Map': matgraph.consumers(g, 'VarienceNormal_XY_Map'), 'Normal_Map': matgraph.consumers(g, 'Normal_Map'),
          'UseReconstructedNormal (default)': g['nodes']['MaterialExpressionStaticSwitchParameter_1800']['props'].get('DefaultValue'),
          'reconstruction': 'Normal = Append(Append(A, G), sqrt(1 - dot(AG, AG)))  [switch A = true]'},
         'Rendering', 'The DXT5 alpha of VH_Optimus_NORM is read ONLY as normal X (output 4 -> AppendVector.A); G = normal Y. '
         'No other node reads A, R or B of that sampler: alpha is NOT gloss/spec/mask. The *2-1 unpack is not in the graph '
         '(it is TextureSample unpack / compiled shader: Rendering confirmed from microcode).')
    E = {k: g['nodes'][k]['props']['DefaultValue'] for k in ('MaterialExpressionVectorParameter_1067', 'MaterialExpressionVectorParameter_6593',
                                                           'MaterialExpressionVectorParameter_5032')}
    find('Q2.energon_branch', Q, 'CONFIRMED', M, 'StaticSwitch UseNeutralEnergonColor / UseAutobotEnergonColor + 3 EnergonColor VectorParameters',
         {'UseNeutralEnergonColor': {'default': g['nodes']['MaterialExpressionStaticSwitchParameter_12630']['props'].get('DefaultValue', False),
                                     'true': E['MaterialExpressionVectorParameter_1067'], 'false': 'UseAutobotEnergonColor'},
          'UseAutobotEnergonColor': {'default': g['nodes']['MaterialExpressionStaticSwitchParameter_6570']['props'].get('DefaultValue', False),
                                     'true': E['MaterialExpressionVectorParameter_6593'], 'false': E['MaterialExpressionVectorParameter_5032']},
          'resolved_with_defaults': E['MaterialExpressionVectorParameter_6593'],
          'formula': 'Energon = (E + E*pow((sin(sin(fractalMaps.R(panned) + Time*energonSpeed)) + 1)*energonIntensity, energonContrast))'
                     ' * Lum_Map.B * Energon_Intensity;  Emissive = PowerDown*(EmissivePart*CustClrAlphasMap.B + Energon) -> '
                     'UpLight/ScanLines/Overshield switches -> Desaturation -> EmissiveColor'},
         'Rendering', 'The red/pink is the AUTHORED Autobot energon colour (1.25, 0.05, 0.05) selected by the master\'s default static '
         'switches (no tagged MIC override). It appears only where Lum_Map (VH_Optimus_SpecPwr_DifLum_EnrGlow) BLUE > 0. '
         'All three vector params share the name EnergonColor, so a runtime MID SetVectorParameterValue("EnergonColor") '
         '(team colour) would override the selected one - whether gameplay does that is native (UNKNOWN).')
    sec = __import__('smsections').sections(ART, 'ENV_ORB_D1_Debris_p.Meshes.column_Base_STAT')
    find('Q2.sidesupport', Q, 'CONFIRMED', 'ENV_ORB_D1_Debris_p.Meshes.column_Base_STAT', 'FStaticMeshElement[0].Material (cooked Streets copy)',
         [{'section': s['index'], 'material': s['material'], 'triangles': s['num_triangles']} for s in sec], 'Rendering',
         'Root cause of the "SideSupport_MATINST cannot compile" issue: AssetTools resolved umodel\'s short glTF name '
         '"SideSupport_MATINST" to ENV_ORB_D1_Debris_p.Materials.SideSupport_MATINST (not cooked into Streets). The cooked '
         'element binds ENV_IAC_Deco_1_p.Material.SideSupport_MATINST -> ENV_NEU_VariantShaders_p.Materials.SideSupport_MATINST '
         '-> ENV_IAC_Shader_p.Material.IAC_Base_Shader_MAT -> ENV_AllShader_p.Release.ENV_PhongMain_NS_Mat, all present in '
         'Streets ART/BASE. FIXED in vs_map.py (props.json section_materials; world.glb rebuilt).', pkg=ART)

# ===================================================================================== Q3
def q3(sup):
    Q = '3 fine aim'
    strat = {}
    for s in ('CAM_Strategies_p.OverTheShoulder_STRATEGY', 'CAM_Driving_Strategies_p.HoverTruck_Optimus_STRATEGY',
              'CAM_Driving_Strategies_p.Truck_Optimus_STRATEGY'):
        strat[s] = objtree.flatten(objtree.dump(s, PKG, max_depth=4))
    sup['camera_strategies'] = strat
    cs = props('CAM_Strategies_p.Truck_Optimus_CAMSET')
    find('Q3.camset', Q, 'CONFIRMED', 'CAM_Strategies_p.Truck_Optimus_CAMSET', 'Strategies[] (Type -> Strategy)',
         {x['Type'].rsplit('.', 1)[-1]: x.get('Strategy') or x.get('StrategyClass') for x in cs['Strategies']}, 'Gameplay')
    ots = strat['CAM_Strategies_p.OverTheShoulder_STRATEGY']
    def beh(cls):
        return next((v['props'] for k, v in ots.items() if v['class'] == cls), {})
    find('Q3.fov', Q, 'CONFIRMED', 'CAM_Strategies_p.OverTheShoulder_STRATEGY', 'TnFovCameraBehavior DefaultFOV / FOVsByPCS', beh('TnFovCameraBehavior'),
         'Gameplay', 'Ion Blaster has no WeaponPCS, so fine aim activates only TnPCS_FineAim -> FOV 45 deg, SmoothTime 0.1 '
         '(default 80 / 0.4). Weapon-specific bands: HeavyPistol/BurstRifle +FineAim 30, SniperRifle +FineAim 20, Hovering +FineAim 45. '
         'FOV axis (horizontal vs vertical) not stated in data.')
    find('Q3.orbit_distance', Q, 'CONFIRMED', 'CAM_Strategies_p.OverTheShoulder_STRATEGY', 'TnLocationOffsetCameraBehavior',
         beh('TnLocationOffsetCameraBehavior'), 'Gameplay',
         'Robot follow distance = 800 UU (8 m). Only Sniper/HeavyPistol/BurstRifle + FineAim pull in to 100 UU; generic FineAim '
         '(Ion Blaster) keeps 800.')
    find('Q3.look_speed', Q, 'CONFIRMED', 'CAM_Strategies_p.OverTheShoulder_STRATEGY', 'TnOrbitRotationCameraBehavior',
         beh('TnOrbitRotationCameraBehavior'), 'Gameplay',
         'FineAim alone: Yaw 25 / Pitch 12.5 vs default 50 / 25 = 0.5x sensitivity; ramp 0.4 s, RampZone 0.7, x2.5; '
         'SpeedTransitionTime 0.5; Low/High sensitivity option multipliers 0.8 / 1.5; pitch range +-75 deg. Units (deg/s) INFERRED.')
    find('Q3.offset', Q, 'CONFIRMED', 'CAM_Strategies_p.OverTheShoulder_STRATEGY', 'TnScreenSpaceOffsetByPitchCameraBehavior',
         beh('TnScreenSpaceOffsetByPitchCameraBehavior'), 'Gameplay',
         'Offsets are 3 keys over PitchRange (-75, 0, +75 deg presumably min/mid/max) in UU; X/Y/Z semantics (forward/right/up) INFERRED.')
    find('Q3.anchor', Q, 'CONFIRMED', 'CAM_Strategies_p.OverTheShoulder_STRATEGY', 'HmOffsetAnchorPointRelativeToActorCameraBehavior.Offset',
         beh('HmOffsetAnchorPointRelativeToActorCameraBehavior'), 'Gameplay')
    find('Q3.transition', Q, 'CONFIRMED', 'CAM_Strategies_p.OverTheShoulder_STRATEGY', 'TransitionTime / TransitionOverrides',
         {k: ots['CAM_Strategies_p.OverTheShoulder_STRATEGY']['props'].get(k) for k in ('TransitionTime', 'TransitionOverrides')}, 'Gameplay')
    find('Q3.weapon_pcs', Q, 'CONFIRMED', 'TransContent.Default__TnWeapon*', 'WeaponPCS / HasFineAimScope',
         {'TnWeaponIonBlaster': None, 'TnWeaponBurstRifle': 'TnPCS_BurstRifle', 'TnWeaponHeavyPistol': 'TnPCS_HeavyPistol (+scope)',
          'TnWeaponSniperRifle': 'TnPCS_SniperRifle (+scope)'}, 'Gameplay', 'All other weapon CDOs set neither.')
    fam = {k: x['value'] for k, x in eff('TransGame.Default__TnFineAimManager', 'TransGame').items()}
    find('Q3.fineaim_manager', Q, 'CONFIRMED', 'TransGame.Default__TnFineAimManager', '_GroundSpeedMultiplier / _TargetSnapTimeout', fam,
         'Gameplay', 'Ground speed x0.5 while fine-aiming (underscore = script default of a runtime field; use HIGH CONFIDENCE).', pkg='TransGame')
    wd = {k: x['value'] for k, x in eff('WEP_IonBlaster_p.IonBlaster_WEPDATA').items()
          if re.search('FineAim|RecoilCamera|CameraShake|Spread|GroundSpeed', k)}
    find('Q3.ionblaster_fineaim', Q, 'CONFIRMED', 'WEP_IonBlaster_p.IonBlaster_WEPDATA', 'FineAim*/RecoilCameraParams/CameraShakeParams/Spread', wd,
         'Gameplay', 'MultiplayerData of TnWeaponIonBlaster (SP/SV/AI variants exist).')
    find('Q3.bindings', Q, 'CONFIRMED', 'Xe-TransInput.ini', '[*.PlayerInput] Bindings / [HM_Engine.HmPlayerInput] / TnInputCommandToBindingMapper',
         ini_lines('Xe-TransInput.ini', r'FineAim|Boost|LeftTrigger|RightMouseButton|MouseCameraSensitivity|MouseOrbitRotation|DeadZone=|XboxTypeS_Right[XY]|LookRightScale|LookUpScale'),
         'Gameplay', 'LT = "FineAim | Boost" (same trigger fine-aims as robot, boosts as vehicle); PC RMB = "ToggleFineAim | Boost".',
         pkg='Coalesced.ini (decoded)', cls='ini')

# ===================================================================================== Q4
def q4(sup):
    Q = '4 fast robot movement'
    rd = 'TR_Optimus_ROBODEF_p.Optimus_ROBODEF'
    e = eff(rd)
    find('Q4.blueprint_speed', Q, 'CONFIRMED', rd, 'BaseGroundSpeed / AccelRate / AirSpeed / AirControl / TerminalVelocity / BaseEyeHeight',
         {k: e[k]['value'] for k in ('BaseGroundSpeed', 'AccelRate', 'AirSpeed', 'AirControl', 'TerminalVelocity', 'BaseEyeHeight', 'Mass') if k in e},
         'Gameplay', 'CONFLICT with the rebuild\'s TnPlayerPawn.GroundSpeed 550 / AccelRate 2048 (pawn CDO). TnPawn has runtime '
         '_BaseGroundSpeed (CDO 600) and _SpeedMultiplierFactors: HIGH CONFIDENCE the Optimus blueprint value (1400 UU/s = 14 m/s) '
         'is the authored base ground speed, multiplied by weapon GroundSpeedMultiplier (Ion Blaster 1.0) and fine aim (0.5). '
         'The native copy blueprint -> pawn is not decompiled.')
    find('Q4.velocity_blend', Q, 'CONFIRMED', 'TR_Shared_ANIMTREE_p.Robot_ANIMTREE.TnVelocityAnimBlend_10449', 'MinSpeed / MaxSpeed / Children',
         {'MinSpeed': 450.0, 'MaxSpeed': 1200.0, 'Walking': 'Nav_StrafeWalk_{F,B,L,R}', 'Jogging': 'Nav_StrafeJog_{F,B,L,R}'},
         'Gameplay', 'The robot tree has NO separate run/sprint node or clip: the fast state is the jog set at >= 1200 UU/s. '
         'Synch group "Strafers" keeps walk/jog/wounded phases locked. Turret variants for WS_TWO_HANDED_GUN.')
    find('Q4.clip_speeds', Q, 'HIGH CONFIDENCE', 'robot.glb (from TR_HeavyMedium_ANM_p.Shared_ROBO_ANIM)', 'foot-plant speed (measured)',
         {'Nav_StrafeWalk_F/B/L/R': '4.4-4.7 m/s', 'Nav_StrafeJog_F/L/R': '12.2-12.8 m/s', 'Nav_StrafeJog_B': '8.9 m/s',
          'length': {'walk': 1.1, 'jog': 0.767}}, 'Gameplay',
         'Measured stance-foot speed relative to the in-place root (scratch footspeed.py). Matches MinSpeed 450 / MaxSpeed 1200 exactly: '
         'blend endpoints are the clips\' natural speeds. At 5.5 m/s the tree is ~13% jog = mostly walk.', pkg='ExtractedAssets', cls='glTF')
    sa = 'TR_Acrobatics_p.SharedAcrobatics'
    find('Q4.acrobatics', Q, 'CONFIRMED', sa, 'effective', {k: x['value'] for k, x in eff(sa).items() if k != 'LandingAnims'}, 'Gameplay',
         'JumpHeight 500 UU (rebuild uses MaxJumpHeight 625 from pawn caps) ; DodgeSpeed 3000 UU/s for DodgeTime 0.5 s.')
    find('Q4.landing', Q, 'CONFIRMED', sa, 'LandingAnims[] (MinHeight/MinSpeed/BlendOutTime/DisallowMovement + chooser)',
         [dict(x, AnimChooser=props(x['AnimChooser'])) for x in props(sa)['LandingAnims']], 'Gameplay')
    mo = 'TR_Acrobatics_p.TruckTransformerMomentum'
    find('Q4.momentum', Q, 'CONFIRMED', mo, 'OnGround / InAir {Forward, Neutral, Backward}', props(mo), 'Gameplay',
         'Semantics native (UNKNOWN); class TnTransformerMomentumBlueprint - likely momentum carried through transform.')
    sup['robot_animtree'] = tree_nodes('TR_Shared_ANIMTREE_p.Robot_ANIMTREE')
    acro = 'TR_Shared_ANIMTREE_p.Robot_ANIMTREE.HmAnimNodeScriptableSlot_13957.TnAcrobaticsSlotLogic_10124'
    a = props(acro)
    res = {}
    for k, v in a.items():
        def rs(x):
            if isinstance(x, dict):
                return {kk: (props(vv)['Profiles'] if kk == 'AnimChooser' and vv else rs(vv)) for kk, vv in x.items()}
            return x
        res[k] = rs(v)
    find('Q4.acrobatics_slot', Q, 'CONFIRMED', acro, 'Single/Double jump, Hovering, Falling, Skidding, Dodge, Rammed animations',
         res, 'Gameplay', 'Dodge = Nav_Boost_{F,B,L,R} (one-handed), blend 0.2/0.2; DashPulse_1_FX on BoosterSocket_L/R via notifies.')
    sup['robot_sequences'] = anim_seqs('TR_HeavyMedium_ANM_p.Shared_ROBO_ANIM')
    for n in ('Nav_Boost_F', 'Nav_Boost_B', 'Nav_Boost_L', 'Nav_Boost_R'):
        s = sup['robot_sequences'][n]
        find('Q4.dodge.' + n, Q, 'CONFIRMED', s['object'], 'Notifies[]',
             [{'t': x['time'], 'class': x['class'], 'props': {k: v for k, v in (x['props'] or {}).items() if k != 'Parameters'}} for x in s['notifies']],
             'Systems', 'Bumblebee trail sockets (Wing*/Elbow*/KneeSide*) are shared-set notifies; they only render if the robot mesh has those sockets.')

# ===================================================================================== Q5
def q5(sup):
    Q = '5 transformation presentation'
    robo = anim_seqs('TR_HeavyMedium_ANM_p.Optimus_ROBO_ANIM'); veh = anim_seqs('TR_HeavyMedium_ANM_p.Optimus_VEH_ANIM')
    sup['optimus_robot_sequences'] = robo; sup['optimus_vehicle_sequences'] = veh
    for name, s in [(n, robo[n]) for n in ('Transform_ToVehicle_ROBO', 'Transform_ToRobot_ROBO', 'Transform_ToVehicle_SuperBoost_Robo')] + \
                   [(n, veh[n]) for n in ('Transform_ToVehicle_VEH', 'Transform_ToRobot_VEH', 'Transform_ToVehicle_SuperBoost_Veh')]:
        find('Q5.notifies.' + name, Q, 'CONFIRMED', s['object'], 'SequenceLength / NumFrames / Notifies[]',
             {'length': s['length'], 'frames': s['frames'], 'translation_scale': s['translation_scale'],
              'notifies': [{'t': x['time'], 'class': x['class'], 'props': x['props']} for x in s['notifies']]},
             'Gameplay', 'ToggleHidden hides/unhides the mesh that plays the clip. Times are seconds of the AUTHORED SequenceLength; '
             'robot.glb/vehicle.glb clip lengths are one frame shorter ((NumFrames-1)/30) - scale or offset accordingly.')
    find('Q5.visibility_timeline', Q, 'HIGH CONFIDENCE', 'Optimus_ROBO_ANIM + Optimus_VEH_ANIM', 'derived from the notifies above',
         {'robot->vehicle (both 2.0 s clips started together)': ['0.125 robot: sound BL_TRANSFORM.OPTIMUS_BOT2VEH',
                                                                 '0.396 vehicle: UNHIDE', '0.880 robot: HIDE', '1.800 vehicle: ENABLE vehicle FX'],
          'vehicle->robot (both 1.167 s clips)': ['0.000 vehicle: DISABLE vehicle FX', '0.000 robot: sound BL_TRANSFORM.OPTIMUS_VEH2BOT',
                                                 '0.098 robot: UNHIDE', '0.663 vehicle: HIDE']},
         'Gameplay', 'Replaces the guessed kTransformHandoffFrac=0.5: both meshes are visible together between unhide and hide '
                     '(0.396-0.880 s and 0.098-0.663 s). That the two clips start simultaneously is INFERRED from equal authored lengths.')
    find('Q5.cues', Q, 'CONFIRMED', 'BL_TRANSFORM.OPTIMUS_BOT2VEH / OPTIMUS_VEH2BOT', 'SoundCue graph',
         {c: (lambda g: {'root': g.get('root'), 'category': g.get('category'),
                         'wave_events': [{k: e[k] for k in ('time', 'volume_db', 'pitch', 'wave', 'wav', 'variants')} for e in g['wave_events']]})(cue(c))
          for c in ('BL_TRANSFORM.OPTIMUS_BOT2VEH', 'BL_TRANSFORM.OPTIMUS_VEH2BOT', 'BL_TRANSFORM.VEH_SUPER_BOOST_TRUCK')},
         'Systems', 'Triggered by HmAnimNotify_Sound in the robot clips (times above).')
    tr = {k: x['value'] for k, x in eff('TransGame.Default__TnTransformation', 'TransGame').items()}
    find('Q5.blend', Q, 'CONFIRMED', 'TransGame.Default__TnTransformation', '_BlendInTime / _BlendOutTime', tr, 'Gameplay', pkg='TransGame')
    pw = {k: x['value'] for k, x in eff('TransGame.Default__TnPawn', 'TransGame').items() if 'Transform' in k or 'Weapon' in k}
    find('Q5.weapon_restore', Q, 'CONFIRMED', 'TransGame.Default__TnPawn', '_RestoreWeaponTransformFractionRemaining', pw.get('_RestoreWeaponTransformFractionRemaining'),
         'Gameplay', 'Value CONFIRMED; meaning INFERRED: weapon is restored when 75% of the vehicle->robot transform remains '
         '(i.e. 25% in). No weapon hide notify exists in any Optimus transform clip; the weapon is attached to the robot mesh, '
         'so it disappears with the robot HIDE at 0.880 s. TnPlayerPawn.ShouldHolsterWeapon / TnWeapon._IsHolstered are runtime.', pkg='TransGame')
    find('Q5.root_motion', Q, 'HIGH CONFIDENCE', 'robot.glb Transform_ToVehicle_ROBO', 'C_Root_Reference_XR translation (glTF m)',
         {'Transform_ToVehicle_ROBO': 'root rises 0.849 m and moves up to 0.519 m along +X(fwd) then ends at (0, 0.849, 0)',
          'Transform_ToRobot_ROBO': 'none', 'vehicle clips': 'none (TranslationScale 0)',
          'vehicle C_Reference_XR height': '1.5 m in transform clips, 0.6 m in hover/boost clips'}, 'Gameplay',
         'Robot clips TranslationScale 1.0, vehicle 0.0. Whether the pawn consumes root motion is native (TnPawn._TransformationPositionShift is runtime).',
         pkg='ExtractedAssets', cls='glTF')
    cs = props('CAM_Strategies_p.Truck_Optimus_CAMSET')
    find('Q5.camera', Q, 'CONFIRMED', 'CAM_Strategies_p.Truck_Optimus_CAMSET', 'TransformTo* strategy types',
         {x['Type'].rsplit('.', 1)[-1]: x.get('Strategy') for x in cs['Strategies'] if 'Transform' in x['Type']}, 'Gameplay',
         'ToVehicle uses the HoverTruck strategy, ToRobo the OverTheShoulder strategy (TransitionTime 1.5 s on OTS).')

# ===================================================================================== Q6
def q6(sup):
    Q = '6 map fidelity'
    path = os.path.join(ROOT, 'VerticalSlice', 'Maps', 'MP_IAC_Streets', 'map_fx.json')
    if not os.path.exists(path):
        import vs_mapfx; vs_mapfx.main()
    fx = json.load(open(path, encoding='utf-8'))
    find('Q6.decals', Q, 'CONFIRMED', 'MP_IAC_Streets_ART_m DecalActor/DecalComponent x%d' % len(fx['decals']), 'DecalMaterial/Width/Height/Thickness/Tile/Offset/DepthBias/Orientation/receivers',
         [{'actor': d['owner'].rsplit('.', 1)[-1], 'material': d['props'].get('DecalMaterial'), 'width': d['props'].get('Width'),
           'height': d['props'].get('Height'), 'thickness': d['props'].get('Thickness'), 'tile': [d['props'].get('TileX'), d['props'].get('TileY')],
           'offset': [d['props'].get('OffsetX', 0.0), d['props'].get('OffsetY', 0.0)], 'depth_bias': d['props'].get('DepthBias'),
           'far_plane': d['props'].get('FarPlane'), 'near_plane': d['props'].get('NearPlane', 0.0),
           'receivers': len(d['props'].get('DecalReceivers') or []), 'gltf_matrix': d['gltf_matrix']} for d in fx['decals']],
         'Rendering', 'Full component props + receivers in ExtractedAssets/VerticalSlice/Maps/MP_IAC_Streets/map_fx.json. All 4 decal '
         'materials are BLEND_Additive / MLM_Unlit landmark textures.', pkg=ART, cls='DecalComponent')
    em = [c for c in fx['particle_components'] if c['owner_class'] == 'Emitter']
    find('Q6.emitters', Q, 'CONFIRMED', 'MP_IAC_Streets_ART_m Emitter x%d' % len(em), 'ParticleSystemComponent.Template/InstanceParameters + transform',
         [{'actor': c['owner'].rsplit('.', 1)[-1], 'template': c['props'].get('Template'),
           'instance_parameters': c['props'].get('InstanceParameters'), 'prefab': c['prefab'], 'gltf_matrix': c['gltf_matrix']} for c in em],
         'Systems', 'Exactly 8 level emitters; Emitter_5707 IS the SteamVentFX prefab instance (PrefabInstance_4340 ArchetypeToInstanceMap) - '
         'not an additional 9th. Each sets its own SteamColor instance parameter (violet ~(106,17,255); prefab vent (33,167,239)).',
         pkg=ART, cls='Emitter')
    gp = [c for c in fx['particle_components'] if c['owner_class'] != 'Emitter']
    find('Q6.gameplay_fx', Q, 'CONFIRMED', 'MP_IAC_Streets_BASE_m pickup/objective factories', 'ParticleSystemComponent.Template',
         [{'owner': c['owner'].rsplit('.', 1)[-1], 'owner_class': c['owner_class'], 'template': c['props'].get('Template'),
           'gltf_matrix': c['gltf_matrix']} for c in gp], 'Systems',
         'Previously omitted actor->effect relationships (ammo/health/overshield/flag/bomb pickup glows).', cls='ParticleSystemComponent')
    p = json.load(open(os.path.join(ROOT, 'VerticalSlice', 'Maps', 'MP_IAC_Streets', 'props.json'), encoding='utf-8'))['props']
    find('Q6.section_materials', Q, 'CONFIRMED', 'MP_IAC_Streets_* StaticMesh exports', 'FStaticMeshElement[].Material',
         {'props_with_section_materials': sum(1 for x in p if x.get('section_materials')), 'props': len(p),
          'note_slots_umodel_left_dummy_now_bound': ['Wall_BreakOff_sm_STAT[2] innerCyberParts_MATINST',
                                                     'ENV_CORE_CanyonFloor_C_STAT[0] ENV_CORE_CanyonFloor_A_MATINST',
                                                     'D1 debris chunks: ENV_NEU_Variation_p.ENV_cboard_CLR_Mat (textured break faces)',
                                                     'stain_long_STAT[0] stains_01_CLR_MatINST_BAT', 'InteriorDoor_STAT[0] InteriorDoorLock_MATINST']},
         'Rendering', 'props.json now carries section_materials per prop (authoritative, cooked copy). Validated 171/171 meshes; '
         '170 identical to umodel names, 1 differs only because props.json referenced a stale duplicate glTF.', pkg=ART, cls='StaticMesh')

def main():
    sup = {}
    for q in (q1, q2, q3, q4, q5, q6):
        try:
            q(sup)
        except Exception as ex:
            import traceback; traceback.print_exc()
            F.append({'id': q.__name__, 'confidence': 'UNKNOWN', 'error': repr(ex)})
    out = {'schema': 'vs_evidence/1', 'generated_by': 'AssetTools/scripts/wfc/vs_evidence.py',
           'evidence_package': PKG, 'units': 'UE units (1 UU = 1 cm) unless stated; rotators 65536 = 360 deg',
           'findings': F, 'supporting': sup}
    path = os.path.join(extract.MANI, 'vs_evidence.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    from collections import Counter
    print('findings', len(F), dict(Counter(f.get('confidence') for f in F)), '->', path)

if __name__ == '__main__':
    main()
