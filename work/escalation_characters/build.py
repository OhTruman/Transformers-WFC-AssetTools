"""Escalation horde: runtime packaging of the 14 AI bodies + 7 AI-only weapons (Integration go 2026-10-18).

Outputs (ExtractedAssets stays read-only): AssetTools/out/escalation_characters/<id>/{robot.glb, vehicle.glb, character.json, textures/}
and AssetTools/out/escalation_characters/weapons/<pid>/{weapon.glb, weapon.json}; index: out/escalation_characters/index.json.
Exporters unchanged in behaviour: vs_roster_export.export / vs_weapon_export.export (only their new out_dir argument is used).
Entries are built with the same functions the MP roster uses (mp_roster.form_record / animset / compat / skin / gltf):
  character: chassis ROBODEF (AiCharacterDataResolved.ChassisType of the template) -> robot form record; TransformerVehicle -> vehicle
  form record; per-form anim-set compatibility by bone names; transform clips from the anim sets' 'transform' category.
  weapon: the same record construction as mp_roster.weapons() for a class without a TnDataProvider_Weapon (no provider ids, ratings,
  restrictions); its gameplay block = the Escalation data object (SurvivalData else PlayerData, RE MP_ESCALATION_RE 7.4).
  python build.py weapon <TnWeaponClass> | character <TemplateName> | index      (one per process, run_bounded)
"""
import json, os, sys
from collections import OrderedDict as OD
sys.dont_write_bytecode = False
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'wfc'))
# opt-in (campaign characters, 2026-10-23): WFC_CHAR_OUT / WFC_ROSTER_JSON redirect the output root / roster; unset = Escalation as before
OUT = os.environ.get('WFC_CHAR_OUT') or os.path.join(ROOT, 'out', 'escalation_characters')
ROSTER = json.load(open(os.environ.get('WFC_ROSTER_JSON') or os.path.join(HERE, '..', 'escalation_roster', 'roster.json'), encoding='utf-8'))

WEAPONS = ['TransContent.TnWeaponCeremonialStaffHolo', 'TransContent.TnWeaponBombingRunVehicle', 'TransContent.TnWeaponHeavyMGAIHover',
           'TransContent.TnWeaponPlaneStrafingRun', 'TransContent.TnWeaponTankCannonHeavy',
           'TransContent.TnWeaponTankRobotCannonHeavyDecepticon', 'TransContent.TnWeaponTankRobotGatlingGunDecepticon']

def weapon_record(cls):
    import mp_roster as M, authored as A
    pk, c = cls.split('.', 1); cdo = '%s.Default__%s' % (pk, c)
    e = A.effective(cdo) if A.get(cdo) else {}
    g = lambda k: (e.get(k) or {}).get('value')
    wm, ad = g('WeaponMeshTemplate'), g('AiData')
    wd_sp, wd_sv, wd_mp = g('PlayerData'), g('SurvivalData'), g('MultiplayerData')
    wd = wd_sv or wd_sp
    m = A.effective(wm) if wm and A.get(wm) else {}
    mg = lambda k: (m.get(k) or {}).get('value')
    anim_mesh = M.V(mg('AnimatedMesh')) if mg('AnimatedMesh') else {}
    skm = anim_mesh.get('SkeletalMesh') or anim_mesh.get('Mesh')
    if skm and A.get(skm) and A.get(skm)['class'].endswith('Component'): skm = M.V(skm).get('SkeletalMesh')
    pmc = M.V(mg('PickupMesh')) if mg('PickupMesh') else {}
    d = A.effective(wd) if wd and A.get(wd) else {}
    dg = lambda k: (d.get(k) or {}).get('value')
    keys = ('MaxAmmoCount', 'MaxAmmoClipCount', 'InitialReserveAmmoCount', 'DefaultPickupAmount', 'ShotCost', 'InstantHitDamage',
            'InstantHitDamageTypes', 'NumShotsToFire', 'FireIntervalModifier', 'FireInterval', 'WeaponFireTypes', 'WeaponProjectiles',
            'WeaponRange', 'RangeDamageModifiers', 'PerShotSpreadModifier', 'FineAimSpreadModifier', 'WeaponReloadAnimTime', 'EquipTime',
            'PutDownTime', 'bAutoFire', 'bAutoReload', 'GroundSpeedMultiplier', 'HeatProperties', 'OwnerAnimations')
    return OD([('class', cls), ('provider_ids', []), ('display_name', {'ItemName': g('ItemName')}), ('description', None),
               ('weapon_type_code', None), ('slot', None), ('restrictions', {}), ('ui_ratings', {}),
               ('mp', {'in_every_mp_map': False, 'in_any_mp_map': False, 'escalation_ai_weapon': True}),
               ('mesh', {'weapon_mesh_template': wm, 'skeletal_mesh': skm, 'gltf': M.gltf(skm),
                         'mesh_note': None if skm else 'the weapon mesh component authors no SkeletalMesh (fires from sockets) - CONFIRMED absence',
                         'pickup_mesh': pmc.get('SkeletalMesh') or pmc.get('StaticMesh'), 'pickup_mesh_translation': pmc.get('Translation'),
                         'muzzle_sockets': mg('MuzzleFlashSockets'), 'buff_materials': mg('BuffMaterials'),
                         'idle_animation': mg('IdleAnimation'), 'event_anims': mg('WeaponEventAnims')}),
               ('effects', {'muzzle_flashes': mg('MuzzleFlashes'), 'tracers': mg('TracerTemplates'), 'default_squib': mg('DefaultSquib'),
                            'effects_type': mg('WeaponEffectsType')}),
               ('sounds', {'events': mg('WeaponEventSounds'), 'pickup': mg('PickupSound'), 'impact': mg('DefaultImpactSound'),
                           'bullet_by': mg('BulletBySound')}),
               ('gameplay (versus WEPDATA = MultiplayerData, CONFIRMED)', {}),
               ('gameplay (escalation WEPDATA: SurvivalData else PlayerData, RE 7.4)', dict({'object': wd}, **{k: dg(k) for k in keys if dg(k) is not None})),
               ('wepdata_objects', {'MultiplayerData (versus)': wd_mp, 'PlayerData (campaign / SP)': wd_sp, 'SurvivalData (Escalation)': wd_sv,
                                    'AiData': ad}),
               ('gameplay (player WEPDATA)', {'object': wd_sp}),
               ('ai_data', {'object': ad, 'DesiredFiringRange': (A.effective(ad).get('DesiredFiringRange') or {}).get('value') if ad and A.get(ad) else None}),
               ('damage_types', {}), ('kill_feed_icon', None), ('confidence', 'CONFIRMED (cooked CDO / WEPMESH / WEPDATA)')])

def character_entry(tpl):
    import mp_roster as M, authored as A
    t = next(x for x in ROSTER['templates'] if x['template'] == tpl or x['template'].split('.')[-1] == tpl)   # full opath or bare name
    robo = t['chassis']; veh = t['vehicle_form']
    robot = M.form_record(robo, 'SkelMesh', 'robot')
    vehicle = M.form_record(veh, 'SkeletalMesh', 'vehicle') if veh else None
    compat, trans = {}, {'robot (to vehicle / to robot)': [], 'vehicle (to vehicle / to robot)': []}
    for form, f in (('robot', robot), ('vehicle', vehicle)):
        if not f: continue
        joints = (M.skin(f['skeletal_mesh']) or {}).get('joints') if f['skeletal_mesh'] else None
        compat[form] = {'skeleton_signature': f['skeleton_signature'], 'joint_count': f['joint_count'],
                        'anim_sets': {a: M.compat(M.animset(a), joints) for a in f['anim_sets'] or [] if a}}
        key = 'robot (to vehicle / to robot)' if form == 'robot' else 'vehicle (to vehicle / to robot)'
        for a in f['anim_sets'] or []:
            r = M.animset(a)
            for seq in (r.get('by_category') or {}).get('transform', []):
                if seq.startswith('Transform_To'): trans[key].append({'clip': seq, 'anim_set': a, 'gltf': r.get('gltf_anim')})
    fac = 'Autobot' if '_Autobot' in tpl or 'Aut_' in tpl else ('Neutral' if '_Neutral' in tpl or 'NeutraD' in tpl else 'Decepticon')
    return OD([('re_identity', {'UniqueIconicId': tpl}), ('display', {'iconic': {'INT': tpl}}), ('faction', fac),
               ('class', None), ('availability', 'Escalation horde (AI only)'), ('mp_status', 'Escalation AI template (not a player chassis)'),
               ('locks', None), ('robot', robot), ('vehicle', vehicle), ('animation_compat', compat), ('transform_clips', trans),
               ('stats', {'ai_template': t['template'], 'chassis': robo}),
               ('weapons', dict({'ai_weapon_classes': [w['class'] for w in t['weapon_classes']]},
                                **({'action_weapon_classes': t['action_weapon_classes']} if 'action_weapon_classes' in t else {}))),
               ('abilities', {}), ('ui', {}), ('audio', {'voice': robot.get('sound_event_set'), 'vehicle': (vehicle or {}).get('sound_event_set')})])

def main():
    mode, arg = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    import materials
    if mode == 'weapon':
        import vs_weapon_export as W
        pid = arg.split('.')[-1].replace('TnWeapon', '')
        m = W.export(pid, weapon_record(arg), materials.assets(), {}, {}, 'WeaponSocket_Primary', out_dir=os.path.join(OUT, 'weapons', pid))
        print(pid, json.dumps(m['validation'])[:300])
    elif mode == 'character':
        import vs_roster_export as R
        cid = os.environ.get('WFC_CHAR_ID') or arg.split('.')[-1].replace('_AICD', '')
        # AnimSets that ExtractedAssets holds only as raw .psa were converted into AssetTools/out/campaign_anims (campaign_anim_gaps.py,
        # same conventions); fall back to that copy when the content glTF is absent (path relative to the exporter's ROOT)
        orig_set_gltf = R.set_gltf
        def set_gltf(set_op):
            p = orig_set_gltf(set_op)
            if p: return p
            pkg, name = set_op.split('.', 1)
            alt = os.path.join(ROOT, 'out', 'campaign_anims', pkg, name.split('.')[-1] + '.anim.gltf')
            return os.path.relpath(alt, R.ROOT).replace(os.sep, '/') if os.path.exists(alt) else None
        R.set_gltf = set_gltf
        m = R.export(cid, character_entry(arg), None, materials.assets(), R.runtime_colors_common(), out_dir=os.path.join(OUT, cid))
        print(cid, json.dumps(m['validation'])[:300])
    elif mode == 'index':
        idx = OD()
        for d in sorted(os.listdir(OUT)):
            p = os.path.join(OUT, d)
            if d == 'weapons' or not os.path.isdir(p): continue
            cj = os.path.join(p, 'character.json'); c = json.load(open(cj, encoding='utf-8')) if os.path.exists(cj) else {}
            files = {f: os.path.getsize(os.path.join(p, f)) for f in ('robot.glb', 'vehicle.glb', 'character.json') if os.path.exists(os.path.join(p, f))}
            tex = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(os.path.join(p, 'textures')) for f in fs)
            idx[d] = OD([('template', (c.get('stats') or {}).get('ai_template')), ('chassis', (c.get('stats') or {}).get('chassis')),
                         ('faction', c.get('faction')),
                         ('robot_glb', os.path.relpath(os.path.join(p, 'robot.glb'), ROOT).replace(os.sep, '/') if 'robot.glb' in files else None),
                         ('vehicle_glb', os.path.relpath(os.path.join(p, 'vehicle.glb'), ROOT).replace(os.sep, '/') if 'vehicle.glb' in files else None),
                         ('character_json', os.path.relpath(cj, ROOT).replace(os.sep, '/') if c else None),
                         ('robot_clips', len((c.get('robot') or {}).get('animations') or [])),
                         ('vehicle_clips', len((c.get('vehicle') or {}).get('animations') or [])),
                         ('weapons', (c.get('weapons') or {}).get('ai_weapon_classes')),
                         ('bytes', dict(files, textures=tex)), ('validation', c.get('validation'))])
        wp = OD()
        for d in sorted(os.listdir(os.path.join(OUT, 'weapons'))) if os.path.isdir(os.path.join(OUT, 'weapons')) else []:
            p = os.path.join(OUT, 'weapons', d)
            wp[d] = {f: os.path.getsize(os.path.join(p, f)) for f in os.listdir(p) if os.path.isfile(os.path.join(p, f))}
        json.dump(OD([('generated_by', 'AssetTools/work/escalation_characters/build.py'), ('root', 'AssetTools (paths relative to it)'),
                      ('contract', 'same as VerticalSlice/Characters/<id> (vs_roster_export) and Weapons/<pid> (vs_weapon_export)'),
                      ('characters', idx), ('weapons', wp)]), open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), indent=1)
        print(json.dumps({k: (v['robot_clips'], v['vehicle_clips'], sum(v['bytes'].values())) for k, v in idx.items()}))
        print(json.dumps({k: sum(v.values()) for k, v in wp.items()}))

if __name__ == '__main__':
    main()
