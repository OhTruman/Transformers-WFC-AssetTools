"""Canonical multiplayer roster package keyed by RE chassis ids (RE-Workspace/notes/data/mp_chassis_roster.json, read-only).

RE's roster is the identity / behaviour evidence; this package cross-checks every RE field against AssetTools' own extraction
(mp_characters.json) and joins the recovered assets: meshes, skeletons, anim sets, transform clips, materials, textures,
portraits, class icons, weapons, abilities, audio, and the resolved stat blueprints (per-chassis ROBODEF / VEHDEF scalar export
requested by RE OVERNIGHT_2026-10-04 'STILL OPEN').
Output: manifests/mp_content/roster_package.json        python mp_roster_package.py
Escalation horde (Gameplay E3a / Integration 2026-10-23): the 14 AI bodies of out/escalation_characters (index.json) are appended to
`chassis` after the MP entries, keyed by their id (AICD name minus _AICD), from their ROBODEF (CONFIRMED cooked values) and character.json;
they are not in RE's MP roster, so re_identity.source says so and no RE cross-check applies. MP entries and every other key are unchanged
(re_cross_check_summary counts the MP roster only; escalation_horde_chassis lists the added ids).
"""
import json, os, re, sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from m03_common import CONF, HIGH, PART, UNK  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
RE_ROSTER = r'F:/Transformers Rebuild/RE-Workspace/notes/data/mp_chassis_roster.json'
RE_NOTE = 'RE-Workspace/notes/OVERNIGHT_2026-10-04_HUD_VEHICLE_FRONTEND_ROSTER_AI.md section E'
GEN = 'AssetTools/scripts/wfc/mp_roster_package.py'

def J(p): return json.load(open(os.path.join(MANI, p), encoding='utf-8'))
def V(o): return A.values(o) if o and A.get(o) else {}
def scalars(o):
    return {k: v for k, v in V(o).items() if isinstance(v, (int, float, str, bool)) and not (isinstance(v, str) and '.' in v and v.split('.')[0].endswith('_p'))}

def specialty_health(cls):
    """versus health / speed of a specialty: TransGame.Default__TnSpecialty<Class>.HealthBlueprint + SpeedMultiplier."""
    if not cls: return None
    v = V('TransGame.Default__TnSpecialty' + cls)
    hb = v.get('HealthBlueprint'); h = V(hb) if hb else {}
    seg = h.get('Segments') or []
    return {'specialty': cls, 'health_blueprint': hb, 'segments': seg, 'health_max': sum(seg) if seg else None,
            'overshield': h.get('Overshield'), 'speed_multiplier': v.get('SpeedMultiplier')}

def resolve_bp(o, depth=0):
    """blueprint object -> its authored values (one level of sub-objects resolved)."""
    v = V(o)
    if not v: return None
    out = {}
    for k, x in v.items():
        if isinstance(x, str) and depth == 0 and A.get(x) and x.startswith(o + '.'):
            out[k] = resolve_bp(x, 1)
        else:
            out[k] = x
    return {'object': o, 'class': (A.get(o) or {}).get('class'), 'values': out}

def VEH_IDS(weapons):
    return {pid for w in weapons.values() if w.get('weapon_type_code') == '3' for pid in w.get('provider_ids') or []}

def escalation_horde():
    """the Escalation AI bodies as roster entries: re_identity from the ROBODEF (collision cylinder, size, movement, health, momentum,
    vehicle form) + the packaged character.json (meshes, definitions); robot_only for a chassis without a vehicle form (Spider)"""
    root = os.path.normpath(os.path.join(HERE, '..', '..', 'out', 'escalation_characters'))
    ix = os.path.join(root, 'index.json')
    if not os.path.exists(ix): return OrderedDict()
    idx = json.load(open(ix, encoding='utf-8'))
    ids = sorted((idx.get('characters') or idx).keys()) if isinstance(idx.get('characters') or idx, dict) else sorted(c['id'] for c in idx.get('characters'))
    out = OrderedDict()
    for cid in ids:
        cj = os.path.join(root, cid, 'character.json')
        if not os.path.exists(cj): continue
        c = json.load(open(cj, encoding='utf-8'))
        rd = (c.get('stats') or {}).get('chassis'); v = V(rd); rob = c.get('robot') or {}; veh = c.get('vehicle') or {}
        has_veh = bool(veh) and 'skipped' not in veh
        col = v.get('Collision') or {}
        ident = OrderedDict([('UniqueId', cid), ('ObjectPath', rd), ('ai_template', (c.get('stats') or {}).get('ai_template')),
                             ('robot_skel', rob.get('mesh_object')), ('robot_animtree', rob.get('anim_tree')),
                             ('collision', OrderedDict([('CollisionRadius', col.get('CollisionRadius')), ('CollisionHeight', col.get('CollisionHeight'))])),
                             ('size', v.get('Size')), ('ground_speed', v.get('BaseGroundSpeed')), ('accel', v.get('AccelRate')), ('air_speed', v.get('AirSpeed')),
                             ('health', v.get('Health')), ('segmented_health', v.get('SegmentedHealth')), ('momentum', v.get('MomentumBlueprint')),
                             ('vehicle_form', v.get('TransformerVehicle') if has_veh else None), ('vehicle_skel', veh.get('mesh_object') if has_veh else None),
                             ('robot_only', not has_veh),
                             ('source', CONF + ': ROBODEF values (authored.db) + AssetTools character.json; not in RE mp_chassis_roster.json')])
        out[cid] = OrderedDict([('re_identity', ident), ('re_cross_check', {'fields_compared': 0, 'mismatches': [], 'detail': {'note': 'no RE roster row (AI-only body)'}}),
                                ('display', c.get('display')), ('faction', c.get('faction')), ('class', c.get('class (chassis DefaultSpecialty)')),
                                ('availability', c.get('availability')), ('mp_status', c.get('mp_status')), ('locks', c.get('locks')),
                                ('robot', {k: rob.get(k) for k in ('definition', 'mesh_object', 'glb', 'physics_asset', 'anim_tree')}),
                                ('vehicle', {k: veh.get(k) for k in ('definition', 'mesh_object', 'glb', 'physics_asset', 'anim_tree')} if has_veh else None),
                                ('character_json', 'AssetTools/out/escalation_characters/%s/character.json' % cid),
                                ('stats', {'robot_scalars (ROBODEF)': scalars(rd)}), ('escalation_horde', True),
                                ('confidence', CONF + ' (ROBODEF values; AI-only body, no RE roster row)')])
    return out

def main():
    re_r = json.load(open(RE_ROSTER, encoding='utf-8'))
    mine = {c['chassis_id']: c for c in J('mp_content/mp_characters.json')['characters']}
    compat = J('mp_content/mp_animation_compat.json'); sel = J('mp_content/character_select_ui.json')['per_character']
    classes = J('mp_content/mp_classes.json'); weapons = J('mp_content/mp_weapons.json')['weapons']
    presets = J('mp_content/mp_characters.json')['class_default_presets (TR_MPPlayerCharacterData_p)']
    wmap = {p: cls for cls, w in weapons.items() for p in w['provider_ids']}
    out = OrderedDict()
    mism_total = 0
    for row in re_r['chassis']:
        cid = row['UniqueId']; m = mine.get(cid)
        r, v = (m or {}).get('robot') or {}, (m or {}).get('vehicle') or {}
        ours = {'ObjectPath': r.get('definition'), 'robot_skel': r.get('skeletal_mesh'), 'robot_animtree': r.get('anim_tree'),
                'vehicle_form': v.get('definition'), 'vehicle_class': v.get('definition_class'), 'vehicle_skel': v.get('skeletal_mesh'),
                'melee_set': r.get('melee_set'), 'cameras': r.get('cameras'), 'size': r.get('size'),
                'ground_speed': (r.get('movement') or {}).get('BaseGroundSpeed'), 'accel': (r.get('movement') or {}).get('AccelRate'),
                'air_speed': (r.get('movement') or {}).get('AirSpeed'), 'collision': r.get('collision'), 'regen': r.get('health_regen'),
                'vehicle_damage_mult': v.get('damage_multiplier'), 'DefaultSpecialty': (m or {}).get('default_class'),
                'UniqueIconicId': (m or {}).get('iconic_id')}
        checks = {}
        for k, x in ours.items():
            if k not in row: continue
            rv = row[k]
            same = (rv == x) or (isinstance(rv, float) and isinstance(x, float) and abs(rv - x) < 1e-4) or \
                   (isinstance(rv, dict) and isinstance(x, dict) and all(abs((x.get(kk) or 0) - vv) < 1e-4 for kk, vv in rv.items() if isinstance(vv, (int, float))))
            checks[k] = 'match' if same else ('RE unset - AssetTools value inherited from the class default' if rv is None and x is not None
                                              else {'RE': rv, 'AssetTools': x})
        mism = [k for k, x in checks.items() if isinstance(x, dict)]; mism_total += len(mism)
        rd = r.get('definition'); vd = v.get('definition')
        rdv = V(rd); vdv = V(vd)
        def clips(form):
            f = (m or {}).get(form) or {}
            tr, other = [], []
            for s in f.get('anim_sets') or []:
                for seq in (compat['anim_sets'].get(s) or {}).get('by_category', {}).get('transform', []):
                    rec = {'clip': seq, 'anim_set': s, 'gltf': (compat['anim_sets'].get(s) or {}).get('gltf_anim')}
                    (tr if re.match(r'Transform_To(Robot|Vehicle)', seq) else other).append(rec)
            cats = {}
            for s in f.get('anim_sets') or []:
                for c, names in (compat['anim_sets'].get(s) or {}).get('by_category', {}).items():
                    cats.setdefault(c, 0); cats[c] += len(names)
            return tr, other, cats
        rt, ro, rc = clips('robot'); vt, vo, vc = clips('vehicle')
        pre = (m or {}).get('iconic_preset') or {}
        loadout = {n: wmap.get(n) for n in (pre.get('WeaponTypes') or []) + (pre.get('VehicleWeapons') or []) + (pre.get('MeleeWeapons') or [])}
        out[cid] = OrderedDict([
            ('re_identity', row), ('re_cross_check', {'fields_compared': len(checks), 'mismatches': mism, 'detail': {k: x for k, x in checks.items() if x != 'match'}}),
            ('display', (m or {}).get('display_name')), ('faction', (m or {}).get('faction')), ('class', (m or {}).get('default_class')),
            ('availability', (m or {}).get('availability')), ('mp_status', (m or {}).get('mp_status')), ('locks', (m or {}).get('locks')),
            ('robot', {k: r.get(k) for k in ('definition', 'skeletal_mesh', 'gltf', 'joint_count', 'skeleton_signature', 'physics_asset', 'anim_tree',
                                             'anim_sets', 'material_slots (umodel short names resolved within the mesh package family - HIGH)',
                                             'overshield_material', 'energy_death_material', 'buff_materials', 'arm_blueprint', 'required_sockets', 'face_fx')}),
            ('vehicle', {k: v.get(k) for k in ('definition', 'definition_class', 'vehicle_form', 'skeletal_mesh', 'gltf', 'joint_count', 'skeleton_signature',
                                               'physics_asset', 'anim_tree', 'anim_sets', 'material_slots (umodel short names resolved within the mesh package family - HIGH)',
                                               'overshield_material', 'energy_death_material', 'weapon_sockets', 'fx', 'gib_templates')}),
            ('textures (package dirs)', (m or {}).get('extracted_package_dirs')),
            ('transform_clips', {'robot (to vehicle / to robot)': rt, 'vehicle (to vehicle / to robot)': vt,
                                 'ability_form_clips': ro + vo, 'note': 'Transform_ToVehicle_ROBO plays on the robot mesh, Transform_ToVehicle_VEH on the '
                                 'vehicle mesh (both visible during the overlap window - EVIDENCE_PASS2 section 3); names CONFIRMED from AnimSequence objects'}),
            ('clip_counts_by_category (name-based HIGH)', {'robot': rc, 'vehicle': vc}),
            ('animation_compat', (compat['per_character'].get(cid) or {})),
            ('stats', {'robot_scalars (ROBODEF)': scalars(rd), 'vehicle_scalars (VEHDEF)': scalars(vd),
                       'segmented_health': resolve_bp(rdv.get('SegmentedHealth')), 'momentum': resolve_bp(rdv.get('MomentumBlueprint')),
                       'acrobatics': resolve_bp(rdv.get('AcrobaticsManagerBlueprint')),
                       'vehicle_physics': {k: resolve_bp(x) for k, x in vdv.items() if k.endswith('Blueprint') and isinstance(x, str) and 'Physics' in x},
                       'class_speed_multiplier': (classes['specialties (classes)'].get((m or {}).get('default_class')) or {}).get('speed_multiplier'),
                       'versus_health (TnSpecialty.Apply -> InitializeSegmentedHealth(HealthBlueprint); RE TARGETED_PASS3 A4, CONFIRMED)': {
                           'rule': 'every versus mode applies the specialty buffs (TnGame.ApplySpecialtyBuffs=True; False only for campaign, '
                                   'Escalation, campaign lobby): health = specialty blueprint, replacing the ROBODEF SharedHealth above',
                           'select_by': 'the selected character data Specialty (CharacterData.Specialty via TnPlayerPawn.ApplySpecialty), never '
                                        'the chassis. MP custom characters: Specialty = the slot preset class -> use by_specialty[<class>]. '
                                        'Iconic / SP presets: use by_iconic_preset_specialty. (RE 2026-10-05)',
                           'by_iconic_preset_specialty': specialty_health(pre.get('Specialty')),
                           'by_specialty': {c: specialty_health(c) for c in ('Leader', 'Scientist', 'Scout', 'Soldier')},
                           'chassis_default_class_ui_only (TnDataProvider_Chassis.DefaultSpecialty - NOT what Apply reads)': (m or {}).get('default_class')}}),
            ('ui', {'portraits': sel.get(cid), 'class_icon': (classes['specialties (classes)'].get((m or {}).get('default_class')) or {}).get('ui_icons')}),
            ('weapons', {'iconic_loadout': loadout,
                         'allowed_on_foot_by_provider (TnDataProvider_Weapon FactionRestriction + ChassisRestriction; WeaponType != 3)':
                             sorted(pid for w in weapons.values() if w.get('weapon_type_code') != '3' for pid, r in (w.get('restrictions') or {}).items()
                                    if r.get('FactionRestriction') in ('Any', (m or {}).get('faction'))
                                    and (not r.get('ChassisRestriction') or cid in r['ChassisRestriction'])),
                         'vehicle_form_weapons (WeaponType 3)': {'from_iconic_preset': sorted(k for k in loadout if k in VEH_IDS(weapons)),
                                                                 'note': 'vehicle-form weapon providers carry no chassis restriction; the weapon is fixed '
                                                                         'by the preset VehicleWeapons, not chosen in a loadout'},
                         'class_default_secondary': (classes['specialties (classes)'].get((m or {}).get('default_class')) or {}).get('DefaultSecondaryWeapon')}),
            ('abilities', {'iconic': pre.get('Abilities'), 'skills': pre.get('Skills'),
                           'class_pool': sorted(k for k, a in classes['abilities'].items() if a.get('SpecialtyRestriction') == (m or {}).get('default_class'))}),
            ('audio', {'voice': (m or {}).get('voice_sound_event_set'), 'vehicle': (m or {}).get('vehicle_sound_event_set'), 'vehicle_death_sound': v.get('death_sound')}),
            ('confidence', CONF + ' (RE identity + AssetTools extraction agree field by field unless listed in re_cross_check.mismatches)')])
    mp_count = len(out)
    horde = escalation_horde()
    for k, x in horde.items():
        if k in out: raise SystemExit('horde id collides with an MP chassis: ' + k)
        out[k] = x
    defaults = OrderedDict()
    for cls, p in presets.items():
        defaults[cls] = {'Autobot': p['ChassisTypes'][0], 'Decepticon': p['ChassisTypes'][1],
                         'names': [out[c]['display']['iconic']['INT'] for c in p['ChassisTypes']],
                         'weapons': p['WeaponTypes'], 'vehicle_weapons': p['VehicleWeapons'], 'melee': p['MeleeWeapons'], 'abilities': p['Abilities'],
                         'source': 'TR_MPPlayerCharacterData_p.%s_PCD_MP (Factions [Autobot, Decepticon] -> ChassisTypes)' % cls}
    shared = J('mp_content/mp_characters.json')
    json.dump(OrderedDict([
        ('generated_by', GEN), ('re_evidence', [RE_ROSTER.replace('F:/Transformers Rebuild/', ''), RE_NOTE]),
        ('default_four_classes (MP presets)', defaults),
        ('re_cross_check_summary', {'chassis': mp_count, 'field_mismatches_total': mism_total}),
        ('shared_health_note', 'ROBODEF SegmentedHealth = TR_Health_p.SharedHealth (175/125/125/125, overshield 550) is the value '
                               'ApplyTransformer sets; in VERSUS the specialty blueprint replaces it (Leader 300 / Scientist 180 / Scout 200 / '
                               'Soldier 330, overshield 200: stats.versus_health). SharedHealth stands in campaign / Escalation / campaign lobby '
                               '(RE TARGETED_PASS3_2026-10-05 A4).'),
        ('chassis', out)] + ([('escalation_horde_chassis', OrderedDict([('ids', list(horde)), ('source', 'AssetTools out/escalation_characters (ROBODEF '
                               'values; not in RE mp_chassis_roster.json)')]))] if horde else [])), open(os.path.join(MANI, 'mp_content', 'roster_package.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('chassis', len(out), 'mismatches', mism_total, {k: v['re_cross_check']['mismatches'] for k, v in out.items() if v['re_cross_check']['mismatches']})
    print({k: (v['Autobot'], v['Decepticon'], v['names']) for k, v in defaults.items()})

if __name__ == '__main__':
    main()
