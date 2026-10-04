"""Handoffs built on mp_roster.py outputs: character-select UI, AI/bot evidence, versus-mode objective visuals, character bundles.

Outputs (manifests/mp_content/):
  character_select_ui.json   CharacterSelect / CustomTransformers / lobby movies -> per-character portrait symbols + PNGs, weapon /
                             ability icons, data-store bindings, Customize.* bridge calls with script status, palettes, the
                             UI_CharacterCustomization_m preview scene (camera ids, Matinees, pawn factories)
  ai_bot_evidence.json       what exists for AI: MP versus bot evidence (negative) vs campaign / Escalation AI content and config
  versus_mode_visuals.json   objective meshes / markers / icons / announcer per versus mode from class defaults (map-independent)
  bundles/<chassis>.json     portable per-character bundle manifests referencing the central extracted library (no copies)
  python mp_handoffs.py
"""
import glob, json, os, re, sys
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from m03_common import CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import ROOT  # noqa: E402
import fe_frontend as FE  # noqa: E402
import mp_roster as R  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
OUT = R.OUT
GEN = 'AssetTools/scripts/wfc/mp_handoffs.py'
DECOMP = 'RE-Workspace/work/script/decomp (read-only)'

def J(p): return json.load(open(os.path.join(MANI, p), encoding='utf-8'))
def write(name, obj):
    p = os.path.join(OUT, name); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(obj, open(p, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str); print('->', p)

# ------------------------------------------------------------------ character select UI
def select_ui(chars, pkg, rehand):
    cs = pkg['movies']['UI_GFxCharacterSelect_p/CharacterSelect_GFX']
    ct = pkg['movies']['UI_GFxCustomize_p/CustomTransformers_GFX']
    bm = cs['textures']['symbol_bitmaps']
    low = {k.lower(): k for k in bm}
    def sym(name):
        if not name: return None
        hit = bm.get(name) and name or low.get(name.lower())
        return {'symbol': hit, 'match': 'exact' if hit == name else ('case-insensitive' if hit else None),
                'png': [b['png'] for b in bm.get(hit, [])] if hit else None}
    per = OrderedDict()
    for c in chars:
        cn = (c.get('iconic_preset') or {}).get('CharacterName')
        per[c['chassis_id']] = {
            'iconic_character_name (PCD Data.CharacterName = portrait key)': cn,
            'robot_portrait': sym(cn + '_Robot') if cn else None, 'vehicle_portrait': sym(cn + '_Vehicle') if cn else None,
            'locked_robot_portrait': sym(cn + 'Locked_Robot') if cn else None,
            'locked_vehicle_portrait': sym(cn + 'Locked_Vehicle') if cn else None,
            'customization_camera_id': c['customization_camera_id'], 'mp_status': c['mp_status']}
    calls = {k: v for k, v in rehand['as_to_script_calls_resolved (function exported on the binding class)'].items() if k.startswith('Customize.')}
    other = {k: v for k, v in rehand['as_to_script_calls_unresolved (no script function of that name - native-only or dead AS code, UNKNOWN)'].items()
             if k.startswith('Customize.')}
    flow = J('frontend_flow.json')['levels'].get('UI_CharacterCustomization_m', {})
    nodes = flow.get('nodes', [])
    cams = [n for n in nodes if n['class'] in ('SeqVar_TnCustomizationCameraId',)]
    pawnf = [n for n in nodes if n['class'] == 'SeqAct_TnPawnFactory']
    write('character_select_ui.json', OrderedDict([
        ('generated_by', GEN),
        ('movies', {'character_select': 'UI_GFxCharacterSelect_p/CharacterSelect_GFX (iconic / class selection, loaded by lobbies)',
                    'customize': 'UI_GFxCustomize_p/CustomTransformers_GFX (custom character editor; TnUIControllerMultiplayer.InGameLobbyUI)'}),
        ('portrait_rule', {'rule': 'CharacterSelect_GFX AS builds the bitmap linkage as PlayableCharacterData[i].CharacterName + "_Robot" / '
                                   '"_Vehicle" (root DoAction) - CONFIRMED (bytecode)', 'locked_variants': '<Name>Locked_Robot/_Vehicle exports exist '
                                   'for Arcee and Slipstream (campaign-unlock characters)'}),
        ('per_character', per),
        ('weapon_icons (export = TnDataProvider_Weapon.UniqueId)', {k: [b['png'] for b in v] for k, v in bm.items()
                                                                     if k in {w for x in J('mp_content/mp_weapons.json')['weapons'].values() for w in x['provider_ids']}}),
        ('ability_icons (export = TnDataProvider_Ability.UniqueId)', {k: [b['png'] for b in v] for k, v in bm.items()
                                                                       if k in J('mp_content/mp_classes.json')['abilities']}),
        ('customize_weapon_icons', {k: [b['png'] for b in v] for k, v in ct['textures']['symbol_bitmaps'].items() if not k.startswith(('autobot', 'decepticon'))}),
        ('palettes', {'GFxMovie.ExternalTextures (lobbies)': [e for e in pkg['movies']['UI_GFxLobbies_p/PartyLobby_GFX']['textures']
                                                              ['runtime_external (GFxMovie.ExternalTextures: resource slot -> texture)']],
                      'binding': 'TnCharacterApplier PrimaryColor -> Cust_Color_A, SecondaryColor -> Cust_COLOR_B, team energon -> EnergonColor '
                                 '(docs/EVIDENCE_PASS2.md section 1)'}),
        ('data_store_bindings', {'character_select': cs['data_store_bindings'], 'customize': ct['data_store_bindings']}),
        ('localization_keys', {'character_select': cs['localization_keys'], 'customize': ct['localization_keys']}),
        ('bridge_calls_customize', {'resolved (TnCharacterScriptBinding function exists)': sorted(calls),
                                    'unresolved (RE)': sorted(other)}),
        ('selection_logic (script, read-only)', {
            'list': 'TnCharacterScriptBinding.GetPlayableCharacters: iconic mode -> GRI.GetPlayableIconicCharacterNames filtered by '
                    'IsCharacterUnlocked (LockedCharacter + CustomCharacterData.IsChassisUnlocked); custom mode -> PC.GetCustomCharacterNames',
            'iconic_mode': 'GRI._bIconicMode = GameTeamStatus 2 or 4 (TnGameReplicationInfo.UpdateIconicModeFromTeamStatus)',
            'claimed': '<CurrentGame:ClaimedIconicCharacters> - an iconic character can be claimed once per team (CharacterSelect strings Claimed / Unclaimed)',
            'save': 'Customize.CommitCharacter / WriteCustomizationFile -> custom character file; ProfileSettings',
            'source': DECOMP}),
        ('preview_scene', {'level': 'UI_CharacterCustomization_m (streamed by the lobby movies: fscommand initStreamingLvl)',
                           'camera_actor': 'CameraActor_2082 (FOV 70)',
                           'camera_selection': '%d SeqVar_TnCustomizationCameraId + SeqCond_CompareInt chains pick one of %d SeqAct_Interp camera moves; '
                                               'chassis CustomizationCameraId 0 car, 1 jet, 2 locked/leader, 3 tank (TransCustomization.ini)'
                                               % (len(cams), flow.get('kismet_class_counts', {}).get('SeqAct_Interp', 0)),
                           'pawn_factories': [n['object'] for n in pawnf],
                           'fscommands': sorted({n['authored'].get('FsCommand') for n in nodes if n['class'] == 'GFxEvent_FsCommand'}),
                           'placeholders': 'two SkeletalMeshActors tagged RB_Ratchet_SKEL (editor stand-ins)',
                           'customize_bridge': 'Customize.UpdatePreviewCharacter / TransformPreviewCharacter / TransformPreviewCharacterToRobot'}),
        ('confidence', CONF + ' (movie structure, config, script); placeholders / role descriptions HIGH')]))

# ------------------------------------------------------------------ AI
def ai_evidence(chars):
    inv = objtree.inv()
    cls = ('TnSeqAct_AiSpawnCharacter', 'TnActorFactoryAI', 'TnSurvivalGenerator', 'TnSurvivalSpawnList', 'TnAiSquad', 'TnTacticalVolume',
           'TnSurvivalSpawnPoint')
    rows = inv.execute('SELECT package, class, COUNT(*) FROM exports WHERE class IN (%s) GROUP BY package, class' % ','.join('?' * len(cls)), cls).fetchall()
    per = defaultdict(dict)
    for p, c, n in rows: per[p][c] = n
    versus = ['MP_IAC_Streets_BASE_m', 'MP_IAC_Seed_BASE_m', 'MP_IAC_Berth_BASE_m', 'MP_UND_Complex_BASE_m', 'MP_IAC_Rust_BASE_m',
              'MP_ORB_Debris_BASE_m', 'MP_KON_Molten_BASE_m', 'MP_UND_Gorge_BASE_m']
    vs_lvls = [p for p in per if any(p.lower().startswith(v.lower().rsplit('_base_m', 1)[0].lower()) for v in versus)]
    ini = FE.read_ini(os.path.join(FE.INI, 'Xe-TransGame.ini')); cini = FE.read_ini(os.path.join(FE.INI, 'TransCustomization.ini'))
    ai_cfg = {s: dict(v) for s, v in list(ini.items()) + list(cini.items()) if re.search(r'TnAi|Ai\]?$|AiRobot|AiVehicle|Difficulty', s)}
    names = (FE.loc_tables(FE.INT).get('TransGame') or {}).get('AICharacterNames')
    w = J('mp_content/mp_weapons.json')['weapons']
    spawn_lists = sorted({r[0] for r in inv.execute("SELECT DISTINCT opath FROM exports WHERE class='TnSurvivalSpawnList'").fetchall()})[:40]
    sl = {o: {k: x for k, x in (A.values(o) or {}).items()} for o in spawn_lists[:12]}
    write('ai_bot_evidence.json', OrderedDict([
        ('generated_by', GEN),
        ('conclusion', {
            'multiplayer_versus_bots': 'NOT SHIPPED. No versus map (all 8) cooks an AI spawner (TnActorFactoryAI, TnSeqAct_AiSpawnCharacter, '
                                       'TnSurvivalGenerator); versus game classes (TnVersusGame / TnTeamGame / TnFreeForAllGame) have no bot path '
                                       'in script; the only NumBots references are stock Engine.GameInfo / HmGameInfo counters. Automated-testing '
                                       'policies (TnAutomatedTestingPolicy, TnOnlineTestingPolicy) drive real player controllers for QA, not AI. '
                                       'Any offline versus AI in the rebuild is a NEW FEATURE, not original behaviour.',
            'exception_noted': 'MP_ORB_Debris_BASE_m cooks one TnAiSquad actor with no spawner (unused / leftover) - CONFIRMED presence, role UNKNOWN',
            'escalation': 'Escalation (SV, MP_ESC_*) is the shipped MP mode with AI: 36 TnSurvivalGenerator per map + TnSurvivalSpawnList waves',
            'campaign': 'campaign levels cook TnActorFactoryAI / TnTacticalVolume / TnAiSquad in %d packages' %
                        sum(1 for p in per if p[:1] in 'AD' and p[1:2].isdigit()),
            'confidence': CONF + ' (cooked class census + script decompilation)'}),
        ('versus_levels_with_ai_classes', {p: per[p] for p in vs_lvls}),
        ('escalation_levels', {p: v for p, v in per.items() if 'ESC' in p}),
        ('useful_for_future_bots (authored, reusable)', {
            'weapon_ai_data': {c: {'ai_data': x['ai_data']} for c, x in w.items() if x['mp']['in_every_mp_map']},
            'ai_ability_variants (config)': sorted(s for s in ai_cfg if 'Ability' in s and s.endswith('Ai')),
            'ai_config_sections': ai_cfg,
            'ai_character_names (TransGame.int [AICharacterNames])': names,
            'ai_transformer_archetypes': [o for o in J('mp_content/mp_characters.json')['other_transformer_archetypes (not chassis)']],
            'navigation': 'every versus map has a NavigationPoint / ReachSpec network (vs_navigation.py; Streets 123 nodes, Gorge 148) - '
                          'authored for AI pathing; usable by future bots',
            'escalation_spawn_lists (sample)': sl}),
        ('owner', 'Gameplay/RE own AI behaviour; this is content evidence only')]))

# ------------------------------------------------------------------ versus mode visuals (map independent)
def mode_visuals():
    E = lambda o: {k: v['value'] for k, v in A.effective(o).items()} if A.get(o) else {}
    def comps_of(cdo):
        """component sub-objects of a class default that carry a mesh (detected by class, not by property name)."""
        out = {}
        for k, v in E(cdo).items():
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, str) and A.get(x) and A.get(x)['class'].endswith('Component'):
                    c = comp(x)
                    if c and any(m in c for m in ('StaticMesh', 'SkeletalMesh', 'Template')):
                        out[k + ':' + x.rsplit('.', 1)[-1]] = {'class': A.get(x)['class'], **c}
        return out
    def comp(o):
        v = A.values(o) if o and A.get(o) else {}
        return {k: v.get(k) for k in ('StaticMesh', 'SkeletalMesh', 'Materials', 'Translation', 'Scale3D', 'Template') if v.get(k)}
    out = OrderedDict()
    flag = E('TransContent.Default__TnWeaponFlag'); bomb = E('TransContent.Default__TnWeaponBomb')
    def wm(t):
        te = E(t) if t else {}
        pm = te.get('PickupMesh')
        return {'weapon_mesh_template': t, 'pickup_component': pm, **comp(pm)}
    out['CTF'] = {'flag_weapon': {'class': 'TransContent.TnWeaponFlag', **wm(flag.get('WeaponMeshTemplate'))},
                  'factory': 'TransContent.TnGameObjectivePickupFactoryFlag (resting mesh = TnWeapon.CreatePickupFactoryMesh; beam FX_Pickups_p.FX.Pickup_FX)',
                  'capture_point': comps_of('TransContent.Default__TnFlagCapturePoint') or 'no mesh component on the class default',
                  'dropped_pickup': flag.get('DroppedPickupClass'),
                  'objective_bases': 'PROP_NEU_Pickups_p.ObjBases.Base_A / Base_D (InterpActors per map, Kismet-shown in CTF/EXT)'}
    out['EXT'] = {'bomb_weapon': {'class': 'TransContent.TnWeaponBomb', **wm(bomb.get('WeaponMeshTemplate'))},
                  'dropped_mesh': bomb.get('DroppedPickupMesh'), 'dropped_pickup': bomb.get('DroppedPickupClass'),
                  'bomb_explode_mesh': 'PROP_NEU_Pickups_p.MPBomb.NEU_MPBombExplode_SKEL (+ MPBombExplode_ANIM)',
                  'factory': 'TransContent.TnGameObjectivePickupFactoryBomb',
                  'plant_point': comps_of('TransContent.Default__TnBombPlantPoint') or 'no mesh component on the class default',
                  'hud': 'TnHudDataObserverBombDefuseTimer'}
    kz = 'TransContent.Default__TnKingOfTheHillZone'
    out['KOTH'] = {'mesh_components': comps_of(kz),
                   'zone_colors': {k: E(kz).get(k) for k in ('NeutralColor', 'CaptureColor')} if A.get(kz) else None}
    dp = 'TransContent.Default__TnDominationPoint'
    out['DOM'] = {'mesh_components': comps_of(dp),
                  'marker': 'TnObjectiveMarkerTypeDomination -> UI_HudMarkers_p.MPMarkerDominationNode_MAT',
                  'anim_set': 'NEU_EnergonTotem_ANM (StandBy / DeActivate / AUT_Activate / DEC_Activate)'}
    pres = J('frontend_mode_presentation.json')['modes']
    for t in ('DM', 'TDM', 'CTF', 'KOTH', 'DOM', 'EXT', 'SV'):
        o = out.setdefault(t, {})
        p = pres.get(t, {})
        o.update({'icon': (p.get('icon') or {}).get('symbol'), 'announcer': p.get('announcer'), 'music': list((p.get('music') or {}).keys()),
                  'name': (p.get('text') or {}).get('FriendlyName'), 'hud_score_panel': p.get('hud_score_panel (Hud_GFX export, name-based HIGH)')})
    out['markers (canvas)'] = J('frontend_hud.json')['objective_marker_types']
    write('versus_mode_visuals.json', OrderedDict([('generated_by', GEN),
        ('source', 'class defaults (TransContent / TransGame), weapon-mesh templates, frontend_mode_presentation.json, frontend_hud.json; '
                   'per-map placement stays in each map manifest (Streets: render_index.json)'),
        ('modes', out), ('confidence', CONF)]))

# ------------------------------------------------------------------ bundles
def bundles(chars, compat, weapons, classes):
    picks = ['Car', 'Jet', 'Tank', 'Truck', 'Car2', 'Truck2']
    made = []
    for cid in picks:
        c = next(x for x in chars if x['chassis_id'] == cid)
        if not c['in_all_mp_maps']: continue
        pre = c.get('iconic_preset') or {}
        def files_of(form):
            f = c[form] or {}
            out = {'mesh_gltf': f.get('gltf'), 'materials': [s['material'] for s in f.get('material_slots (umodel short names resolved within the mesh package family - HIGH)', [])],
                   'extra_materials': [f.get('overshield_material'), f.get('energy_death_material')] + (f.get('buff_materials') or []),
                   'anim_sets': {a: {'gltf': (compat['anim_sets'].get(a) or {}).get('gltf_anim'),
                                     'compat': compat['per_character'][cid][form]['anim_sets'].get(a, {}).get('status')}
                                 for a in f.get('anim_sets') or [] if a}}
            out['material_files'] = sorted({R.rel(p) for m in out['materials'] + out['extra_materials'] if m
                                            for p in glob.glob(os.path.join(ROOT, 'content', *m.split('.')) + '.mat')})
            pkgdir = os.path.join(ROOT, 'content', (f.get('skeletal_mesh') or '.').split('.')[0])
            out['textures (package dir)'] = sorted(R.rel(p) for p in glob.glob(os.path.join(pkgdir, '*.png')))
            return out
        wnames = (pre.get('WeaponTypes') or []) + (pre.get('VehicleWeapons') or []) + (pre.get('MeleeWeapons') or [])
        wmap = {p: cls for cls, w in weapons['weapons'].items() for p in w['provider_ids']}
        b = OrderedDict([
            ('bundle', cid), ('display', c['display_name']), ('faction', c['faction']), ('class', c['default_class']),
            ('vehicle_form', c['vehicle_form']), ('mp_status', c['mp_status']),
            ('definitions', {'robot': c['robot']['definition'], 'vehicle': c['vehicle']['definition']}),
            ('robot', files_of('robot')), ('vehicle', files_of('vehicle')),
            ('arm_blueprint', c['robot'].get('arm_blueprint')),
            ('stats', {'robot': c['robot'].get('movement'), 'collision': c['robot'].get('collision'), 'size': c['robot'].get('size')}),
            ('iconic_loadout (PCD)', {'weapons': {n: {'class': wmap.get(n), 'gltf': (weapons['weapons'].get(wmap.get(n)) or {}).get('mesh', {}).get('gltf')}
                                                  for n in wnames},
                                      'abilities': pre.get('Abilities'), 'skills': pre.get('Skills'), 'starting_form': pre.get('StartingForm')}),
            ('class_default_secondary', classes['specialties (classes)'].get(c['default_class'], {}).get('DefaultSecondaryWeapon')),
            ('sockets', {'robot_required': c['robot'].get('required_sockets'), 'vehicle_weapon_sockets': c['vehicle'].get('weapon_sockets')}),
            ('voice', c['voice_sound_event_set']), ('cameras', c['robot'].get('cameras')),
            ('skeleton', {'robot': c['robot']['skeleton_signature'], 'vehicle': c['vehicle']['skeleton_signature'],
                          'shares_robot_skeleton_with': [k.split(':')[1] for k in []] or
                          next((v for k, v in compat['shared_skeletons'].items() if k == 'robot:' + str(c['robot']['skeleton_signature'])), [])}),
            ('note', 'references the central library under ExtractedAssets/content; no files copied. Shared anim sets are referenced once.'),
            ('confidence', CONF + ' (definitions); material slot resolution HIGH')])
        missing = [p for form in ('robot', 'vehicle') for p in [b[form]['mesh_gltf']] + [x['gltf'] for x in b[form]['anim_sets'].values()]
                   if p and not os.path.exists(os.path.join(ROOT, p))]
        b['validation'] = {'missing_files': missing, 'all_anim_sets_compatible': all(x['compat'] == 'compatible'
                                                                                     for form in ('robot', 'vehicle') for x in b[form]['anim_sets'].values()),
                           'non_compatible': {a: x['compat'] for form in ('robot', 'vehicle') for a, x in b[form]['anim_sets'].items() if x['compat'] != 'compatible'}}
        write('bundles/%s.json' % cid, b); made.append(cid)
    return made

def main():
    chars = J('mp_content/mp_characters.json')['characters']
    pkg = J('frontend_package/frontend_package.json')
    rehand = J('frontend_re_handoff.json')
    select_ui(chars, pkg, rehand)
    ai_evidence(chars)
    mode_visuals()
    made = bundles(chars, J('mp_content/mp_animation_compat.json'), J('mp_content/mp_weapons.json'), J('mp_content/mp_classes.json'))
    print('bundles', made)

if __name__ == '__main__':
    main()
