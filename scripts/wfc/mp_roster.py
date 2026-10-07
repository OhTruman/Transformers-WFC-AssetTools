"""Multiplayer character / class / weapon content handoff (authored data only).

Sources (all cooked or config; nothing inferred from filenames alone):
  * MP maps' TnAssetReferencesMultiplayer actors (what every MP level cooks: Transformers + Weapons)  -> MP membership
  * TransCustomization.ini / TransWeapons.ini providers (Chassis, Specialty, Ability, Skill, Killstreak, Weapon) + TransGame.int/.FRA
  * TnProfileSettings.PresetIconicCharacters (TR_SPPlayerCharacterData_p.*_PCD_SP) and TR_MPPlayerCharacterData_p.*_PCD_MP
  * ROBODEF (TnTransformer archetype) / VEHDEF (Tn*FormBlueprint) / SkeletalMesh / AnimSet / AnimSequence / TnWeapon / WEPMESH / WEPDATA
  * RE script decompilation (read-only): TnCharacterScriptBinding (lock filtering), TnProfileSettings / TnPlayerReplicationInfoSurvival
    (UnlockChassis callers)
  * extracted glTF skins (joint names) for bone-level animation compatibility
Outputs: manifests/mp_content/{mp_characters,mp_classes,mp_weapons,mp_animation_compat}.json
  python mp_roster.py
"""
import glob, hashlib, json, os, re, sys
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from m03_common import CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import ROOT  # noqa: E402
import fe_frontend as FE  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
OUT = os.path.join(MANI, 'mp_content')
GEN = 'AssetTools/scripts/wfc/mp_roster.py'
PROV = 'RE-Workspace/work/script/decomp (read-only)'
FACTION = {'0': 'Autobot', '1': 'Decepticon', '2': 'Any', '3': 'Neutral'}
VEH_FORM = {'TnCarFormBlueprint': 'car', 'TnPlaneFormBlueprint': 'jet', 'TnJetFormBlueprint': 'jet', 'TnTankFormBlueprint': 'tank', 'TnTruckFormBlueprint': 'truck'}
UNLOCKS = {   # TnProfileSettings.CheckForLevelCompletionAchievements (script)
    'Car5': 'complete the Autobot campaign (any difficulty) - TnProfileSettings.CheckForLevelCompletionAchievements',
    'Jet8': 'complete the Decepticon campaign (any difficulty) - TnProfileSettings.CheckForLevelCompletionAchievements'}
DEV_UNLOCK = ('Car5', 'Car6', 'Car7', 'Jet7', 'Jet8', 'Tank4', 'Tank5', 'Truck5')   # TnPlayerReplicationInfoSurvival.CheckForUpdate

def rel(p): return os.path.relpath(p, ROOT).replace(os.sep, '/')
def write(name, obj):
    os.makedirs(OUT, exist_ok=True)
    json.dump(obj, open(os.path.join(OUT, name), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('->', os.path.join(OUT, name))

_GL = {}
def gltf(op):
    if not op: return None
    if op not in _GL:
        pkg, name = op.split('.')[0], op.rsplit('.', 1)[-1]
        c = glob.glob(os.path.join(ROOT, 'content', pkg, '**', name + '.gltf'), recursive=True)
        _GL[op] = rel(c[0]) if c else None
    return _GL[op]

_SK = {}
def skin(op):
    """joint names + umodel material slot short names of an extracted skeletal mesh glTF."""
    if op in _SK: return _SK[op]
    g = gltf(op); r = None
    if g:
        j = json.load(open(os.path.join(ROOT, g), encoding='utf-8'))
        joints = [j['nodes'][i].get('name') for i in (j.get('skins') or [{}])[0].get('joints', [])]
        r = {'gltf': g, 'joints': joints, 'joint_count': len(joints),
             'skeleton_signature': hashlib.sha1('|'.join(joints).encode()).hexdigest()[:12] if joints else None,
             'slots_umodel': [m.get('name') for m in j.get('materials', [])]}
    _SK[op] = r
    return r

def resolve_short(short, pkgs):
    """umodel material slot short name -> material object, searched ONLY within the mesh's own package family (HIGH)."""
    for pk in pkgs:
        for x in A.find(pk + '.%' + short):
            if x['opath'].rsplit('.', 1)[-1] == short and x['class'].startswith('Material'):
                return x['opath']
    return None

def V(o): return A.values(o) if o and A.get(o) else {}

def loc(sec, key, T):
    return ((T.get('TransGame') or {}).get(sec) or {}).get(key)

# ------------------------------------------------------------------ MP membership
def mp_references():
    rows = A.con().execute("SELECT opath FROM objects WHERE class='TnAssetReferencesMultiplayer'").fetchall()
    per = {}
    for (o,) in rows:
        v = A.values(o)
        per[o.split('.')[0]] = {'Transformers': [x for x in v.get('Transformers') or [] if x],
                                'Weapons': [x for x in v.get('Weapons') or [] if x]}
    return per

# ------------------------------------------------------------------ animation
SEQ_CATS = [('transform', r'transform|trans_|tovehicle|torobot|veh2bot|bot2veh'), ('fine_aim', r'fineaim|fine_aim|aim_zoom|zoom'),
            ('reload', r'reload'), ('fire', r'fire|shoot|recoil'), ('jump', r'jump|land|fall|airborne|double'),
            ('death', r'death|die|dead|gib'), ('hit_reaction', r'react|hit|flinch|stagger|knock'),
            ('melee', r'melee|sword|punch|slam|whirl'), ('ability', r'abilit|cloak|hover|dash|shockwave|warcry|barrier|drain|sentry|decoy|repair|heal|disguise|lock'),
            ('locomotion', r'run|walk|jog|strafe|move|turn|nav_|sprint|dodge|boost|roll'), ('idle', r'idle|cust_|breath|stand'),
            ('vehicle', r'veh|drive|wheel|bank|throttle')]

def seq_category(n):
    for c, rx in SEQ_CATS:
        if re.search(rx, n, re.I): return c
    return 'other'

_AS = {}
def animset(o):
    if o in _AS: return _AS[o]
    v = V(o)
    seqs = []
    for s in v.get('Sequences') or []:
        sv = V(s)
        if sv: seqs.append({'name': sv.get('SequenceName'), 'length_s': sv.get('SequenceLength'), 'frames': sv.get('NumFrames')})
    r = {'animset': o, 'track_bones': v.get('TrackBoneNames') or [], 'preview_mesh': v.get('PreviewSkelMeshName'),
         'scale_type': v.get('ScaleType'), 'sequences': seqs,
         'by_category': {c: sorted(x['name'] for x in seqs if x['name'] and seq_category(x['name']) == c) for c in
                         sorted({seq_category(x['name']) for x in seqs if x['name']})},
         'gltf_anim': (lambda p: rel(p[0]) if p else None)(glob.glob(os.path.join(ROOT, 'content', o.split('.')[0], '**',
                                                                                  o.rsplit('.', 1)[-1] + '.anim.gltf'), recursive=True))}
    _AS[o] = r
    return r

def compat(animset_rec, joints):
    tb = animset_rec['track_bones']; js = set(joints or [])
    if not tb or not js: return {'status': 'UNKNOWN (no track list or no extracted skeleton)'}
    miss = [b for b in tb if b not in js]
    return {'status': 'compatible' if not miss else ('partial' if len(miss) < len(tb) else 'incompatible'),
            'track_bones': len(tb), 'missing_on_mesh': miss[:20], 'missing_count': len(miss)}

# ------------------------------------------------------------------ characters
def asset_copies(robot, veh):
    """packages that carry the actual robot / vehicle skeletal-mesh data (largest serialized copy), as opposed to cooked_copies
    (packages holding the ROBODEF definition): for the locked bodies these differ (Laserbeak's definition is in
    A2_KON_Soundwave_Design_m, its mesh / material / textures in A2_KON_BASE_m - Rendering report 2026-10-06)."""
    out = {}
    for form, f in (('robot', robot), ('vehicle', veh)):
        m = (f or {}).get('skeletal_mesh')
        if not m: continue
        rows = objtree.inv().execute('SELECT package, serial_size FROM exports WHERE opath=? AND class=?', (m, 'SkeletalMesh')).fetchall()
        if not rows: continue
        mx = max(r[1] for r in rows)
        out[form] = sorted(r[0] for r in rows if r[1] == mx)
    return out

def form_record(defn, mesh_key, kind):
    d = V(defn)
    mesh = d.get(mesh_key)
    sk = skin(mesh) if mesh else None
    pk = mesh.split('.')[0] if mesh else None
    fam = [pk, pk.replace('_VEH_p', '_ROBO_p') if pk else None, pk.replace('_ROBO_p', '_VEH_p') if pk else None, 'TR_AllShader_p']
    slots = [{'umodel_slot': s, 'material': resolve_short(s, [p for p in fam if p])} for s in (sk or {}).get('slots_umodel') or []]
    rec = OrderedDict([
        ('definition', defn), ('definition_class', (A.get(defn) or {}).get('class')),
        ('skeletal_mesh', mesh), ('gltf', (sk or {}).get('gltf')), ('joint_count', (sk or {}).get('joint_count')),
        ('skeleton_signature', (sk or {}).get('skeleton_signature')),
        ('physics_asset', d.get('PhysicsAsset')), ('anim_tree', d.get('AnimTree')), ('anim_sets', d.get('AnimSets') or []),
        ('material_slots (umodel short names resolved within the mesh package family - HIGH)', slots),
        ('overshield_material', d.get('OvershieldMaterial')), ('energy_death_material', d.get('EnergyDeathMaterial')),
        ('buff_materials', [x for x in d.get('BuffMaterials') or [] if x]),
        ('sound_event_set', d.get('SoundEventSet')), ('targeting_blueprint', d.get('TargetingBlueprint')),
        ('required_sockets', d.get('RequiredSockets')), ('health_regen', d.get('HealthRegenParameters')),
        ('damage_multiplier', d.get('DamageMultiplier'))])
    if kind == 'robot':
        rec.update({'arm_blueprint': d.get('ArmBlueprint'), 'cameras': d.get('Cameras'), 'size': d.get('Size'),
                    'collision': {k: (d.get('Collision') or {}).get(k) for k in ('CollisionHeight', 'CollisionRadius')},
                    'movement': {k: d.get(k) for k in ('BaseGroundSpeed', 'AccelRate', 'AirSpeed', 'AirControl', 'TerminalVelocity', 'Mass',
                                                         'BaseEyeHeight', 'Health')},
                    'mesh_translation': d.get('MeshTranslation'), 'melee_set': d.get('MeleeSet'),
                    'hit_reactions': d.get('HitReactionBlueprint'), 'deaths': d.get('DeathBlueprint'), 'wounded': d.get('WoundedBlueprint'),
                    'acrobatics': d.get('AcrobaticsManagerBlueprint'), 'momentum': d.get('MomentumBlueprint'),
                    'face_fx': V(mesh).get('FaceFXAsset') if mesh else None,
                    'skeleton_scale_type': V(mesh).get('ScaleType') if mesh else None})
    else:
        rec.update({'vehicle_form': VEH_FORM.get((A.get(defn) or {}).get('class'), (A.get(defn) or {}).get('class')),
                    'physics_blueprints': {k: d.get(k) for k in d if k.endswith('Blueprint') and 'Death' not in k and k not in ('TargetingBlueprint',)},
                    'fx': {k: d.get(k) for k in ('JumpFX', 'HoverFX', 'BoostFx', 'ThrusterFX', 'ContrailFX') if d.get(k)},
                    'weapon_sockets': d.get('WeaponSockets'), 'death_sound': d.get('DeathSound'),
                    'gib_templates': d.get('DefaultSkeletalGibTemplate'), 'deaths': d.get('DeathBlueprint')})
    return rec

def soundset(o):
    v = V(o)
    ev = [e for e in v.get('SoundEventSet') or [] if e and e.get('Event')]
    return {'object': o, 'events': len(ev), 'sample': [{'event': e['Event'].rsplit('.', 1)[-1], 'cue': e.get('Sound')} for e in ev[:12]]} if o else None

def preset(o):
    d = (V(o).get('Data') or {})
    return {'object': o, **{k: d.get(k) for k in ('CharacterName', 'Specialty', 'Factions', 'ChassisTypes', 'StartingForm', 'RevivedForm',
                                                   'WeaponTypes', 'VehicleWeapons', 'MeleeWeapons', 'Abilities', 'Skills')}}

def main():
    os.makedirs(OUT, exist_ok=True)
    ini = FE.read_ini(os.path.join(FE.INI, 'TransCustomization.ini'))
    wini = FE.read_ini(os.path.join(FE.INI, 'TransWeapons.ini'))
    INT = FE.loc_tables(FE.INT); FRA = FE.loc_tables(FE.FRA)
    refs = mp_references()
    mp_maps = sorted(k for k in refs if k.upper().startswith('MP_'))
    mp_tf = set.intersection(*(set(refs[k]['Transformers']) for k in mp_maps))
    mp_tf_any = set.union(*(set(refs[k]['Transformers']) for k in mp_maps))
    mp_wp = set.intersection(*(set(refs[k]['Weapons']) for k in mp_maps))
    mp_wp_any = set.union(*(set(refs[k]['Weapons']) for k in mp_maps))
    inv = objtree.inv()
    presets_sp = A.effective('TransGame.Default__TnProfileSettings')['PresetIconicCharacters']['value']
    sp_by_name = {(V(p).get('Data') or {}).get('CharacterName'): p for p in presets_sp}
    mp_presets = {r[0].rsplit('.', 1)[1].replace('_PCD_MP', ''): r[0] for r in
                  inv.execute("SELECT DISTINCT opath FROM exports WHERE opath LIKE 'TR_MPPlayerCharacterData_p.%_PCD_MP'").fetchall()}
    chassis = [(s.split(' ')[0], dict(v)) for s, v in ini.items() if s.endswith(' TnDataProvider_Chassis')]
    chars = []
    for cid, v in chassis:
        sec = cid + ' TnDataProvider_Chassis'
        robodef = v.get('ObjectPath')
        rd = V(robodef)
        vehdef = rd.get('TransformerVehicle')
        sizes = Counter(r[0] for r in inv.execute('SELECT serial_size FROM exports WHERE opath=?', (robodef,)).fetchall())
        pk = [r[0] for r in inv.execute('SELECT package FROM exports WHERE opath=?', (robodef,)).fetchall()]
        in_mp = robodef in mp_tf
        iconic = v.get('UniqueIconicId')
        sp = sp_by_name.get(iconic)
        locked_c = v.get('LockedChassis') == 'true'; locked_i = v.get('LockedCharacter') == 'true'
        if not in_mp:
            status = 'not referenced by MP maps (TnAssetReferencesMultiplayer) - not a shipped MP character'
        elif locked_c or locked_i:
            status = 'MP character, locked until unlocked'
        else:
            status = 'MP character, available by default'
        unlock = UNLOCKS.get(cid) or (('no unlock call for this chassis in script; native or online entitlement - UNKNOWN')
                                      if (locked_c or locked_i) and in_mp else None)
        robot = form_record(robodef, 'SkelMesh', 'robot') if rd else None
        veh = form_record(vehdef, 'SkeletalMesh', 'vehicle') if vehdef else None
        rec = OrderedDict([
            ('chassis_id', cid), ('iconic_id', iconic),
            ('display_name', {'custom_body': {'INT': loc(sec, 'FriendlyName', INT), 'FRA': loc(sec, 'FriendlyName', FRA)},
                              'iconic': {'INT': loc(sec, 'FriendlyIconicName', INT), 'FRA': loc(sec, 'FriendlyIconicName', FRA)}}),
            ('faction', FACTION.get(v.get('FactionRestriction'), v.get('FactionRestriction'))),
            ('default_class', v.get('DefaultSpecialty')),
            ('vehicle_form', (veh or {}).get('vehicle_form')),
            ('locks', {'LockedChassis': locked_c, 'LockedCharacter': locked_i,
                       'meaning': 'LockedChassis gates the body in custom-character creation; LockedCharacter gates the iconic character in '
                                  'iconic mode; both checked against CustomCharacterData.IsChassisUnlocked (TnCharacterScriptBinding)',
                       'unlock_source': unlock,
                       'developer_unlock_path': cid in DEV_UNLOCK and 'TnPlayerReplicationInfoSurvival.CheckForUpdate (guarded by a '
                                                                       'specific generator, character Barricade and an AcceptableNames list)' or None}),
            ('availability', ('SHARED (MULTIPLAYER CONFIRMED + campaign)' if in_mp and any(p[:1] in 'AD' and p[1:2].isdigit() for p in pk) else
                              'MULTIPLAYER CONFIRMED' if in_mp else
                              'CAMPAIGN ONLY' if any(p[:1] in 'AD' and p[1:2].isdigit() for p in pk) else 'UNKNOWN')),
            ('mp_status', status), ('in_all_mp_maps', in_mp), ('in_any_mp_map', robodef in mp_tf_any),
            ('customization_camera_id', v.get('CustomizationCameraId')),
            ('iconic_preset', preset(sp) if sp else None),
            ('robot', robot), ('vehicle', veh),
            ('voice_sound_event_set', soundset(rd.get('SoundEventSet'))),
            ('vehicle_sound_event_set', soundset(V(vehdef).get('SoundEventSet')) if vehdef else None),
            ('cooked_copies', {'packages': pk, 'serial_sizes': dict(sizes), 'consistent': len(sizes) == 1}),
            ('asset_cooked_copies (packages holding the full robot / vehicle mesh exports)', asset_copies(robot, veh)),
            ('extracted_package_dirs', sorted({rel(os.path.join(ROOT, 'content', p)) for p in
                                               [(robot or {}).get('skeletal_mesh', '') .split('.')[0], (veh or {}).get('skeletal_mesh', '').split('.')[0]]
                                               if p and os.path.isdir(os.path.join(ROOT, 'content', p))})),
            ('confidence', CONF + ' (config + cooked objects + script); material slot resolution HIGH')])
        chars.append(rec)
    # every TnTransformer archetype in the game, classified
    all_tf = sorted({r[0] for r in inv.execute("SELECT DISTINCT opath FROM exports WHERE class='TnTransformer' AND opath NOT LIKE '%.Default__%'").fetchall()})
    chassis_defs = {c['robot']['definition'] for c in chars if c['robot']}
    others = []
    for o in all_tf:
        if o in chassis_defs: continue
        pk = sorted({r[0] for r in inv.execute('SELECT package FROM exports WHERE opath=?', (o,)).fetchall()})
        kind = ('MP-referenced' if o in mp_tf_any else
                'campaign / escalation (cooked into campaign or ESC maps only)' if any(p[:1] in 'AD' and p[1:2].isdigit() or 'ESC' in p for p in pk)
                else 'other (own package / frontend only)')
        others.append({'definition': o, 'skeletal_mesh': V(o).get('SkelMesh'), 'cooked_in': pk[:12], 'cooked_in_count': len(pk), 'category': kind,
                       'availability': 'SHARED' if o in mp_tf_any and kind.startswith('campaign') else
                                       'CAMPAIGN ONLY' if kind.startswith('campaign') else 'MULTIPLAYER CONFIRMED' if o in mp_tf_any else 'UNKNOWN'})
    write('mp_characters.json', OrderedDict([
        ('generated_by', GEN),
        ('sources', ['TransCustomization.ini TnDataProvider_Chassis + TransGame.int/.FRA', 'TnAssetReferencesMultiplayer in %d MP maps' % len(mp_maps),
                     'TnProfileSettings.PresetIconicCharacters (TR_SPPlayerCharacterData_p)', 'TR_MPPlayerCharacterData_p class presets',
                     'ROBODEF / VEHDEF / SkeletalMesh / AnimSet cooked objects', PROV + ': TnCharacterScriptBinding, TnProfileSettings, '
                     'TnPlayerReplicationInfoSurvival', 'extracted glTF skins']),
        ('model', {'what a player picks': 'MP is class-based: Scout (car), Scientist (jet), Soldier (tank), Leader (truck). In custom mode the '
                   'player builds a character on a chassis (body) of their class and faction and customizes colours, weapons, abilities; '
                   'in iconic mode (playlist OnlyAllowIconicCharacters / GameTeamStatus 2 or 4) the player picks a preset iconic character. '
                   'Both use the chassis ROBODEF.',
                   'faction_note': 'FactionRestriction 0 Autobot, 1 Decepticon, 3 Neutral (config); iconic presets list a chassis per faction, so '
                                   'the same iconic character can appear on either team in iconic mode (e.g. AirRaid -> Jet4 for both)',
                   'confidence': CONF + ' for the data; HIGH for the summary wording'}),
        ('mp_maps_checked', mp_maps),
        ('mp_transformers_in_every_mp_map', sorted(mp_tf)),
        ('class_default_presets (TR_MPPlayerCharacterData_p)', {k: preset(o) for k, o in sorted(mp_presets.items())}),
        ('characters', chars),
        ('summary', {'chassis_entries': len(chars),
                     'mp_available_by_default': [c['chassis_id'] for c in chars if c['mp_status'].endswith('by default')],
                     'mp_locked': [c['chassis_id'] for c in chars if c['mp_status'].endswith('unlocked')],
                     'not_mp': [c['chassis_id'] for c in chars if not c['in_all_mp_maps']],
                     'duplicate_definitions': {d: [c['chassis_id'] for c in chars if c['robot'] and c['robot']['definition'] == d]
                                               for d in {c['robot']['definition'] for c in chars if c['robot']}
                                               if sum(1 for c in chars if c['robot'] and c['robot']['definition'] == d) > 1}}),
        ('other_transformer_archetypes (not chassis)', others)]))
    classes(ini, INT, FRA)
    weapons(wini, INT, FRA, mp_wp, mp_wp_any, chars)
    anim_compat(chars)

# ------------------------------------------------------------------ classes
def classes(ini, INT, FRA):
    def prov(t):
        out = OrderedDict()
        for s, v in ini.items():
            if s.endswith(' ' + t):
                sid = s.split(' ')[0]
                cls = v.get('ObjectPath')
                cd = None
                if cls and '.' in cls:
                    pk, c = cls.split('.', 1)
                    cdo = '%s.Default__%s' % (pk, c)
                    cd = {k: x for k, x in V(cdo).items() if not isinstance(x, (dict, list)) or k in ('Sounds', 'Effects')} if A.get(cdo) else None
                out[sid] = {**dict(v), 'name': {'INT': loc(s, 'FriendlyName', INT), 'FRA': loc(s, 'FriendlyName', FRA)},
                            'description': {'INT': loc(s, 'Description', INT), 'FRA': loc(s, 'Description', FRA)},
                            'class_defaults': cd}
        return out
    spec = prov('TnDataProvider_Specialty')
    for k, s in spec.items():
        s['speed_multiplier'] = (ini.get('TransGame.TnSpecialty' + k) or {}).get('SpeedMultiplier')
        s['ui_icons'] = {'class_icon': 'mc_specialtyIcon%s (UI_GFxShared_p/SharedIcons_GFX and CharacterSelect_GFX)' % k,
                         'class_info_panels': ['mc_classInfo%s' % k, 'mc_classInfoHealth%s' % k] , 'class_info_movie': 'UI_GFxCustomize_p/CustomTransformers_GFX',
                         'hud': 'Hud_GFX mc_specialtyIconReference (loads the class icon)', 'confidence': CONF + ' (exported symbols)'}
    write('mp_classes.json', OrderedDict([
        ('generated_by', GEN), ('source', 'TransCustomization.ini providers + TransGame.int/.FRA + class CDOs'),
        ('specialties (classes)', spec), ('abilities', prov('TnDataProvider_Ability')), ('skills', prov('TnDataProvider_Skill')),
        ('killstreaks', prov('TnDataProvider_Killstreak')),
        ('vehicle_form_by_class', 'Scout = car, Scientist = jet, Soldier = tank, Leader = truck (DefaultSpecialty of every chassis of '
                                  'that vehicle family in TransCustomization.ini) - CONFIRMED'),
        ('confidence', CONF)]))

# ------------------------------------------------------------------ weapons
WTYPE = {'2': 'melee', '3': 'vehicle-form weapon', '4': 'grenade'}   # 0 / 1: meaning not stated by data - see weapon_type_codes
def weapons(wini, INT, FRA, mp_wp, mp_wp_any, chars):
    prov = OrderedDict((s.split(' ')[0], dict(v)) for s, v in wini.items() if s.endswith(' TnDataProvider_Weapon'))
    by_class = defaultdict(list)
    for k, v in prov.items(): by_class[v.get('ObjectPath')].append(k)
    allcls = sorted(set(by_class) | mp_wp_any)
    gfx = json.load(open(os.path.join(MANI, 'frontend_gfx.json'), encoding='utf-8'))['movies']
    hud_bm = gfx['UI_GFxHud_p/Hud_GFX']['symbol_bitmaps (export -> bitmaps drawn via placements / shape bitmap fills)']
    recs = OrderedDict()
    for cls in allcls:
        if not cls or '.' not in cls: continue
        pk, c = cls.split('.', 1)
        cdo = '%s.Default__%s' % (pk, c)
        e = A.effective(cdo) if A.get(cdo) else {}
        g = lambda k: (e.get(k) or {}).get('value')
        # versus reads MultiplayerData (TnMultiplayerGame.DesiredWeaponDataType = 3, CONFIRMED by RE
        # work/q/streets_base_gameclasses.txt:450); PlayerData (*_SP_WEPDATA) is TnGame's default 1 = campaign / SP only
        wm, wd, ad = g('WeaponMeshTemplate'), (g('MultiplayerData') or g('PlayerData')), g('AiData')
        wd_sp, wd_sv = g('PlayerData'), g('SurvivalData')
        m = A.effective(wm) if wm and A.get(wm) else {}
        mg = lambda k: (m.get(k) or {}).get('value')
        anim_mesh = V(mg('AnimatedMesh')) if mg('AnimatedMesh') else {}
        skm = anim_mesh.get('SkeletalMesh') or anim_mesh.get('Mesh')
        if skm and A.get(skm) and A.get(skm)['class'].endswith('Component'):   # HmAnimatedMesh -> component -> SkeletalMesh
            skm = V(skm).get('SkeletalMesh')
        pmc = V(mg('PickupMesh')) if mg('PickupMesh') else {}
        d = A.effective(wd) if wd and A.get(wd) else {}
        dg = lambda k: (d.get(k) or {}).get('value')
        dsp = A.effective(wd_sp) if wd_sp and A.get(wd_sp) else {}
        spv = lambda k: (dsp.get(k) or {}).get('value')
        dmg_types = dg('InstantHitDamageTypes') or []
        icon_keys = [k for k in hud_bm if k.lower() in ('death_' + c.replace('TnWeapon', '').lower(),)]
        pids = by_class.get(cls, [])
        rec = OrderedDict([
            ('class', cls), ('provider_ids', pids),
            ('display_name', {'INT': loc(pids[0] + ' TnDataProvider_Weapon', 'FriendlyName', INT) if pids else None,
                              'FRA': loc(pids[0] + ' TnDataProvider_Weapon', 'FriendlyName', FRA) if pids else None,
                              'ItemName': g('ItemName')}),
            ('description', loc(pids[0] + ' TnDataProvider_Weapon', 'Description', INT) if pids else None),
            ('weapon_type_code', prov[pids[0]].get('WeaponType') if pids else None),
            ('slot', WTYPE.get(prov[pids[0]].get('WeaponType')) if pids else None),
            ('restrictions', {p: {'FactionRestriction': FACTION.get(prov[p].get('FactionRestriction')),
                                  'ChassisRestriction': (prov[p].get('ChassisRestriction') or '').split(',') if prov[p].get('ChassisRestriction') else []}
                              for p in pids}),
            ('ui_ratings', {p: {k: prov[p].get(k) for k in ('DamageRating', 'RangeRating', 'AccuracyRating', 'FireRateRating') if k in prov[p]}
                            for p in pids}),
            ('mp', {'in_every_mp_map': cls in mp_wp, 'in_any_mp_map': cls in mp_wp_any}),
            ('mesh', {'weapon_mesh_template': wm, 'skeletal_mesh': skm, 'gltf': gltf(skm),
                      'mesh_note': (None if skm else 'the weapon mesh component authors no SkeletalMesh: nothing is drawn for the '
                                    'held weapon (vehicle-form weapons fire from the vehicle WeaponSocket; grenades show only the '
                                    'thrown projectile / pickup mesh) - CONFIRMED absence'), 'pickup_mesh': pmc.get('SkeletalMesh') or pmc.get('StaticMesh'),
                      'pickup_mesh_translation': pmc.get('Translation'), 'muzzle_sockets': mg('MuzzleFlashSockets'),
                      'buff_materials': mg('BuffMaterials'), 'idle_animation': mg('IdleAnimation'),
                      'event_anims': mg('WeaponEventAnims')}),
            ('effects', {'muzzle_flashes': mg('MuzzleFlashes'), 'tracers': mg('TracerTemplates'), 'default_squib': mg('DefaultSquib'),
                         'effects_type': mg('WeaponEffectsType')}),
            ('sounds', {'events': mg('WeaponEventSounds'), 'pickup': mg('PickupSound'), 'impact': mg('DefaultImpactSound'), 'bullet_by': mg('BulletBySound')}),
            ('gameplay (versus WEPDATA = MultiplayerData, CONFIRMED)', {k: dg(k) for k in ('MaxAmmoCount', 'MaxAmmoClipCount', 'InitialReserveAmmoCount', 'DefaultPickupAmount',
                                                              'ShotCost', 'InstantHitDamage', 'InstantHitDamageTypes', 'NumShotsToFire',
                                                              'FireIntervalModifier', 'FireInterval', 'WeaponFireTypes', 'WeaponProjectiles',
                                                              'WeaponRange', 'RangeDamageModifiers', 'PerShotSpreadModifier', 'FineAimSpreadModifier',
                                                              'WeaponReloadAnimTime', 'EquipTime', 'PutDownTime', 'bAutoFire', 'bAutoReload',
                                                              'GroundSpeedMultiplier', 'HeatProperties', 'OwnerAnimations') if dg(k) is not None}),
            ('wepdata_objects', {'MultiplayerData (versus)': wd, 'PlayerData (campaign / SP)': wd_sp, 'SurvivalData (Escalation)': wd_sv, 'AiData': ad}),
            ('gameplay (player WEPDATA)', dict({'superseded': 'this block is PlayerData = campaign / SP values; versus uses the MultiplayerData '
                                              'block above (RE 2026-10-05)', 'object': wd_sp},
                                             **{k: spv(k) for k in ('MaxAmmoCount', 'MaxAmmoClipCount', 'InitialReserveAmmoCount', 'DefaultPickupAmount',
                                                              'ShotCost', 'InstantHitDamage', 'InstantHitDamageTypes', 'NumShotsToFire',
                                                              'FireIntervalModifier', 'FireInterval', 'WeaponFireTypes', 'WeaponProjectiles',
                                                              'WeaponRange', 'RangeDamageModifiers', 'PerShotSpreadModifier', 'FineAimSpreadModifier',
                                                              'WeaponReloadAnimTime', 'EquipTime', 'PutDownTime', 'bAutoFire', 'bAutoReload',
                                                              'GroundSpeedMultiplier', 'HeatProperties', 'OwnerAnimations') if spv(k) is not None})),
            ('ai_data', {'object': ad, 'same_as_player_data': ad == wd,
                         'DesiredFiringRange': (A.effective(ad).get('DesiredFiringRange') or {}).get('value') if ad and A.get(ad) else None}),
            ('damage_types', {t: {k: x for k, x in V('%s.Default__%s' % tuple(t.split('.', 1))).items() if not isinstance(x, (dict, list))}
                              for t in dmg_types if t and '.' in t}),
            ('kill_feed_icon', {k: hud_bm[k] for k in icon_keys} or None),
            ('confidence', CONF)])
        recs[cls] = rec
    for p, v in prov.items():
        if v.get('ChassisRestriction'):
            for ch in v['ChassisRestriction'].split(','):
                c = next((x for x in chars if x['chassis_id'] == ch), None)
                if c is not None: c.setdefault('weapons_allowed_by_provider', []).append(p)
    write('mp_weapons.json', OrderedDict([
        ('generated_by', GEN), ('sources', ['TransWeapons.ini TnDataProvider_Weapon', 'TnAssetReferencesMultiplayer.Weapons',
                                            'weapon class CDOs, *_WEPMESH (TnWeaponMesh), *_WEPDATA (TnWeaponData)', 'Hud_GFX kill-feed bitmaps']),
        ('weapon_type_codes (TnDataProvider_Weapon.WeaponType -> provider ids)', {t: sorted(k for k, v in prov.items() if v.get('WeaponType') == t)
                                                                                    for t in sorted({v.get('WeaponType') for v in prov.values()})}),
        ('weapon_type_labels', {'labels': WTYPE, 'note': 'labels only where every member shares the role (melee weapons; vehicle-form '
                                'weapons listed in presets VehicleWeapons; grenades). Codes 0 and 1 are both on-foot guns; 0 = '
                                'AssaultRifle/BurstRifle/IonBlaster, 1 = the rest incl. every class DefaultSecondaryWeapon - role names UNKNOWN'}),
        ('weapons', recs),
        ('mp_weapon_classes_not_in_providers', sorted(c for c in mp_wp_any if c not in by_class)),
        ('confidence', CONF)]))

# ------------------------------------------------------------------ animation compatibility
def anim_compat(chars):
    sets = defaultdict(set)
    for c in chars:
        for form in ('robot', 'vehicle'):
            f = c.get(form)
            if f: [sets[a].add((c['chassis_id'], form)) for a in f['anim_sets'] or [] if a]
    out_sets = OrderedDict()
    for a in sorted(sets):
        r = animset(a)
        out_sets[a] = {k: r[k] for k in ('preview_mesh', 'scale_type', 'by_category', 'gltf_anim')}
        out_sets[a]['sequence_count'] = len(r['sequences'])
        out_sets[a]['used_by'] = sorted('%s:%s' % x for x in sets[a])
    per = OrderedDict()
    for c in chars:
        row = {}
        for form in ('robot', 'vehicle'):
            f = c.get(form)
            if not f: continue
            joints = (skin(f['skeletal_mesh']) or {}).get('joints') if f['skeletal_mesh'] else None
            row[form] = {'skeleton_signature': f['skeleton_signature'], 'joint_count': f['joint_count'],
                         'anim_sets': {a: compat(animset(a), joints) for a in f['anim_sets'] or [] if a}}
        per[c['chassis_id']] = row
    groups = defaultdict(list)
    for c in chars:
        for form in ('robot', 'vehicle'):
            f = c.get(form)
            if f and f['skeleton_signature']: groups['%s:%s' % (form, f['skeleton_signature'])].append(c['chassis_id'])
    write('mp_animation_compat.json', OrderedDict([
        ('generated_by', GEN),
        ('method', 'compatible = every AnimSet.TrackBoneNames entry exists as a joint in the extracted skeletal mesh (glTF skin); '
                   'shared skeleton = identical ordered joint-name list (signature). Sequence categories are name-based (HIGH).'),
        ('shared_skeletons', {k: v for k, v in groups.items()}),
        ('per_character', per), ('anim_sets', out_sets), ('confidence', CONF + ' (bone sets); HIGH (categories)')]))

if __name__ == '__main__':
    main()
