"""Canonical multiplayer HUD / in-match UI package (authored content only; behaviour stays with RE/Gameplay).

Inputs: frontend_hud.json, frontend_gfx.json, frontend_mode_presentation.json, mp_content/*.json, the cooked Hud_GFX movie
(layout tree), cooked class defaults (TnHUD, observers, message classes), RE script decompilation (read-only).
Output: manifests/hud/hud_package.json      python hud_package.py
"""
import json, os, re, sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, gfxscan, as2dis  # noqa: E402
from m03_common import CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import ROOT  # noqa: E402
import fe_frontend as FE  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
OUT = os.path.join(MANI, 'hud')
GEN = 'AssetTools/scripts/wfc/hud_package.py'
HUD = 'content/UI_GFxHud_p/Hud_GFX.gfx'

def J(p): return json.load(open(os.path.join(MANI, p), encoding='utf-8'))

RE_NOTE = 'RE-Workspace/notes/OVERNIGHT_2026-10-04_HUD_VEHICLE_FRONTEND_ROSTER_AI.md section A'
# RE A1 element map (CONFIRMED by RE with gfxplace.py): element, controller char, anchor, offset from anchor
RE_ELEMENTS = [
    ('health_overshield_bar', 572, 'topLeft_mc', (20, 10)), ('team_chat', 573, 'topLeft_mc', (15, 130)), ('ability_1', 588, 'topLeft_mc', (24, 70)),
    ('kill_feed_game_messages', 591, 'bottomLeft_mc', (0, -40)), ('ammo_pickup_notify', 593, 'topRight_mc', (-115, 65)),
    ('ammo', 600, 'topRight_mc', (-20, 10)), ('grenades', 601, 'topRight_mc', (10, 46)), ('ability_0', 603, 'topRight_mc', (-24, 70)),
    ('vehicle_ability_2', 605, 'topRight_mc', (-24, 70)), ('objective_list', 607, 'bottomRight_mc', (-340, -124)),
    ('killstreak', 608, 'bottomRight_mc', (-100, -27)), ('killstreak_buff', 609, 'bottomRight_mc', (-50, -97)), ('wave_indicator', 610, None, None),
    ('crosshair_hit_markers', 621, 'midCenter_mc', (0, 0)), ('damage_direction_arrows', 622, 'midCenter_mc', (0, 0)),
    ('score_widget', 633, 'topCenter_mc', (0, 5)), ('match_round_clock (countdown_mc)', 632, 'topCenter_mc', (0, 50)),
    ('game_reward_announcements', 638, 'topCenter_mc', (0, 112)), ('score_xp_popups', 640, 'topCenter_mc', (0, 175)),
    ('level_up', 643, 'midRight_mc', (-80, 0)), ('bad_connection', 644, 'midRight_mc', (-30, -90)),
    ('contextual_prompt (notifyManager_mc)', 646, 'bottomCenter_mc', (0, -30)), ('ctf_flag_return_progress', 652, 'bottomCenter_mc', (0, -100))]

def layout(sc, sid, depth=0, seen=None):
    """named-instance tree of a sprite: instance -> {char, export, kind, x_px, y_px, children}."""
    seen = seen or set()
    if sid in seen or depth > 4: return {}
    seen = seen | {sid}
    out = OrderedDict()
    sp = sc['sprites'].get(sid)
    if not sp: return out
    for pl in sp['places']:
        if 'char' not in pl: continue
        c = pl['char']
        if not pl.get('name') and c not in sc['sprites']: continue      # unnamed shapes are art, not structure
        pname = pl.get('name') or '#%d' % c                              # unnamed widget-controller sprites keep their char id
        kind = 'sprite' if c in sc['sprites'] else 'text' if c in sc['text_fields'] else 'shape/other'
        t = pl.get('translate_twips') or (0, 0)
        rec = {'char': c, 'export': sc['exports'].get(c), 'kind': kind, 'frame': pl.get('frame'),
               'x_px': round(t[0] / 20.0, 2), 'y_px': round(t[1] / 20.0, 2)}
        if kind == 'sprite':
            rec['frames'] = sc['sprites'][c]['frames']; rec['labels'] = [l['label'] for l in sc['sprites'][c]['labels']]
            kids = layout(sc, c, depth + 1, seen)
            if kids: rec['children'] = kids
        elif kind == 'text':
            tf = sc['text_fields'][c]
            rec['text'] = {k: tf.get(k) for k in ('font', 'height_twips', 'color_rgba', 'align', 'initial_text', 'variable')}
        out.setdefault(pname, rec)
    return out

def flat(tree, path=''):
    for k, v in tree.items():
        p = (path + '/' + k).lstrip('/')
        yield p, v
        yield from flat(v.get('children') or {}, p)

ELEMENTS = OrderedDict([
    ('match_clock', r'time|clock|timer|countdown'), ('team_score', r'scoreteam|teamscore|score_?team|logoautobot|logodecepticon|roundsegment'),
    ('local_score', r'freeforall|pointtransaction|pointmultiplier|localscore'), ('health', r'health|vitalbar|segment|hurt|incap|downed'),
    ('overshield', r'overshield|shield'), ('ammo', r'ammo|clip|reload|infinity|grenade'), ('crosshair', r'crosshair|scope|reticule|rangefinder|spread|lockon'),
    ('kill_feed', r'death_|notify$|gamemessage|killfeed'), ('kills_deaths', r'kill|death|streak'), ('objective_markers', r'objective|marker'),
    ('weapon', r'currentweapon|weaponicon|tnweapon|chargingindicator'), ('abilities_class', r'tnability|specialty|ability'),
    ('damage', r'damage|causedamage|hurt|missilewarning'), ('notifications', r'notify|levelup|tutorial|message|pickupnotification|cantransform|transformdisrupt'),
    ('waves_escalation', r'wave|survival|coop')])

def stage_size(path):
    import zlib, struct
    b = open(path, 'rb').read()
    if b[:3] in (b'CFX', b'CWS'): b = b[:8] + zlib.decompress(b[8:])
    nb = b[8] >> 3; bits = ''.join(format(x, '08b') for x in b[8:8 + 1 + (5 + 4 * nb) // 8 + 1])[5:]
    v = [int(bits[i * nb:(i + 1) * nb], 2) for i in range(4)]
    return {'width_px': (v[1] - v[0]) / 20.0, 'height_px': (v[3] - v[2]) / 20.0}

def attachments(path, sc):
    """attachMovie calls: (symbol linkage, target clip variable, new instance name) taken from the pushes preceding each call."""
    out = []
    owners = [None] + list(sc['sprites'].keys())
    for sid in owners:
        for init in (False, True):
            try: blocks = as2dis.actions_for(path, sid if sid is not None else 'root', init)
            except Exception: continue
            for b in blocks:
                try: L = as2dis.dis(b)
                except Exception: continue
                for i, l in enumerate(L):
                    if "'attachMovie'" not in l: continue
                    win = ' '.join(L[max(0, i - 8):i])
                    strs = re.findall(r"'([^']*)'", win)
                    sym = [x for x in strs if x.startswith('mc_') or x in sc['exports'].values()]
                    tgt = [x for x in strs if x.endswith('_mc') or x.endswith('Anchor_mc')]
                    out.append({'owner_sprite': sid, 'owner_export': sc['exports'].get(sid), 'symbol': sym[-1] if sym else '(dynamic)',
                                'target_or_instance': tgt[-2:] if tgt else None})
    return out

def main():
    os.makedirs(OUT, exist_ok=True)
    hud = J('frontend_hud.json'); gfx = J('frontend_gfx.json')['movies']; h = gfx['UI_GFxHud_p/Hud_GFX']
    pres = J('frontend_mode_presentation.json'); chars = J('mp_content/mp_characters.json')['characters']
    classes = J('mp_content/mp_classes.json'); weapons = J('mp_content/mp_weapons.json')['weapons']
    sc = gfxscan.scan(os.path.join(ROOT, HUD))
    root = OrderedDict()
    for pl in sc['root']['places']:
        if pl.get('name') and 'char' in pl:
            root[pl['name']] = {'char': pl['char'], 'export': sc['exports'].get(pl['char']), 'children': layout(sc, pl['char'])}
    allpaths = list(flat(root))
    bm = h['symbol_bitmaps (export -> bitmaps drawn via placements / shape bitmap fills)']
    exports = [e for e in h['exports'] if not e.startswith('__Packages')]
    obs = hud['data_observers']; cbs = hud['hud_callbacks (TnHUD properties)']
    loc = (FE.loc_tables(FE.INT).get('UIText') or {}); locF = (FE.loc_tables(FE.FRA).get('UIText') or {})
    hud_text = loc.get('Hud') or {}
    elements = OrderedDict()
    for name, rx in ELEMENTS.items():
        R = re.compile(rx, re.I)
        elements[name] = {
            'scaleform_owner': 'UI_GFxHud_p/Hud_GFX',
            'layout_instances': {p: {k: v[k] for k in ('char', 'export', 'kind', 'x_px', 'y_px', 'frames', 'labels', 'text') if k in v}
                                 for p, v in allpaths if R.search(p.rsplit('/', 1)[-1]) or (v.get('export') and R.search(v['export']))},
            'exported_symbols': {e: [b['png'] for b in bm.get(e, [])] for e in exports if R.search(e)},
            'observers': [{'class': o['class'], 'callback': o['callback'], 'props': o['props']} for o in obs if R.search((o['class'] or '') + (o['callback'] or ''))],
            'tnhud_callbacks': {k: v for k, v in cbs.items() if R.search(k + v)},
            'strings (UIText [Hud])': {k: {'INT': v, 'FRA': (locF.get('Hud') or {}).get(k)} for k, v in hud_text.items() if R.search(k)},
            'grouping': HIGH + ' (name match); symbol / observer / string existence ' + CONF}
    # icon sets bound to authored ids
    iconic = {(c.get('iconic_preset') or {}).get('CharacterName'): c['chassis_id'] for c in chars if c.get('iconic_preset')}
    def icons(names):
        return {n: [b['png'] for b in bm.get(n, [])] for n in names}
    icon_sets = OrderedDict([
        ('characters (export = PCD CharacterName / FriendlyIconicName)', {e: {'chassis': iconic.get(e) or next((c['chassis_id'] for c in chars if c['display_name']['iconic']['INT'] == e), None),
                                                                              'png': [b['png'] for b in bm.get(e, [])]}
                                                                         for e in exports if e in iconic or any(c['display_name']['iconic']['INT'] == e for c in chars)}),
        ('vehicle_forms', icons([e for e in exports if e in ('Car', 'Jet', 'Tank', 'Truck')])),
        ('abilities (export = ability class name)', icons([e for e in exports if e.startswith('TnAbility')])),
        ('weapons (export = weapon class name)', icons([e for e in exports if e.startswith('TnWeapon')])),
        ('killstreaks (export = killstreak UniqueId)', icons([e for e in exports if e in classes['killstreaks']])),
        ('grenades', icons([e for e in exports if e.startswith('GrenadeIcon')])),
        ('kill_feed (death_<DamageType>)', icons([e for e in exports if e.startswith('death_')])),
        ('misc', icons([e for e in exports if e in ('IconUnknown', 'Unknown', 'Infinity', 'PowerIcon')]))])
    crosshair = {
        'SetWeaponCrosshair (Hud_GFX _global, bytecode)': {'0': 'mc_crosshairGeneric', '1': 'mc_crosshairShotgun', '2': 'mc_crosshairIonBlaster',
                                                           '3': 'mc_crosshairBazooka', 'animation': 'attachMovie into crosshairAnchor_mc, rotate in from 60 deg (interp easeout 0.3 s)'},
        'NotifyTargetTypeChanged colours (bytecode)': {'0': '#50B5D5', '1': '#FF3333', 'other': '#FFFFFF', 'animation': 'colour interp easeout 0.2 s'},
        'who_selects_crosshair_type': 'no script caller of SetWeaponCrosshair - native (RE). Name-based expectation (PROVISIONAL): '
                                      'Shotgun/EMPShotgun -> 1, IonBlaster -> 2, Bazooka/RocketLauncher -> 3, others -> 0',
        'reticule_type (script)': 'TnWeapon.GetReticuleType: WeaponType WT_Mounted -> WRT_Turret (1) else ReticuleType; no weapon authors '
                                  'ReticuleType (enum EWeaponReticuleType {WRT_Default, WRT_Turret}) -> turret reticule only for mounted turrets; '
                                  'Hud DisplayTurretReticule / mc_turretReticule',
        'scopes': {'symbols': [e for e in exports if 'Scope' in e], 'weapons_with_fine_aim_scope (HasFineAimScope)': sorted(
            c.split('.')[1] for c in weapons if (A.values('%s.Default__%s' % tuple(c.split('.', 1))) or {}).get('HasFineAimScope'))},
        'other': {'increase_damage': 'mc_crosshairIncreaseDamage', 'range_finder': 'mc_rangeFinderCrosshair', 'lock_on': ['mc_markerLockOn', 'mc_markerLockOnTriangleLocked']},
        'confidence': CONF + ' for symbols / mappings in bytecode; per-weapon crosshair type UNKNOWN (native)'}
    movies = hud['movies']
    def mrec(k):
        r = gfx.get(k) or {}
        return {'movie': k, 'file': r.get('file'), 'exports': [e for e in r.get('exports', []) if not e.startswith('__Packages')],
                'text_fields': r.get('text_fields'), 'localization_keys': r.get('localization_keys'),
                'callbacks_defined': r.get('_global_callbacks_defined (called from script/native)'), 'fonts': r.get('fonts'),
                'images': r.get('images_extracted')}
    msgs = pres['shared_messages']
    def cls_strings(o):
        v = A.values(o) if A.get(o) else {}
        return {k: x for k, x in v.items() if isinstance(x, str) and not x.startswith(('TransGame.', 'TransContent.', 'Engine.', 'SoundEvents'))}
    pkg = OrderedDict([
        ('generated_by', GEN),
        ('ownership', {'scaleform': 'UI_GFxHud_p.Hud_GFX_1 (TnHUD.HudMovie) - all HUD widgets except world markers',
                       'canvas': 'objective / player markers: TnObjectiveMarkerTypeTransformerVersus / TnObjectiveMarkerTypeDomination '
                                 '(materials in UI_HudMarkers_p, font UI_TransEngineFonts_p.MarkerFont); TnHUD console messages '
                                 '(ConsoleFontSize, ConsoleMessagePosY, HudCanvasScale)',
                       'other_movies': {k: v['instance'] for k, v in movies.items()}}),
        ('stage', stage_size(os.path.join(ROOT, HUD))),
        ('layout (Hud_GFX named-instance tree, px = twips/20)', root),
        ('layout_note', 'hud_mc holds 9 placement anchors (top/mid/bottom x left/center/right) + zoomScopeAttachPoint_mc; widgets are '
                        'attached at runtime with attachMovie (see runtime_attachments) - placement = anchor position + widget symbol'),
        ('runtime_attachments (attachMovie calls, bytecode; symbol/target from the preceding pushes - HIGH)', [
            dict(a, anchor_region=next((p.split('/')[1] for p, v in allpaths if v.get('char') == a['owner_sprite'] and p.count('/') >= 1), None))
            for a in attachments(os.path.join(ROOT, HUD), sc)]),
        ('element_map (RE A1, CONFIRMED; cross-checked against this movie)', [
            dict(element=e, controller_char=ch, anchor=an, offset=off,
                 absolute_px=(lambda a: [a['x_px'] + off[0], a['y_px'] + off[1]] if a and off else None)((root.get('hud_mc') or {}).get('children', {}).get(an)) if an else None,
                 assettools_anchor=next((p.split('/')[1] for p, v in allpaths if v.get('char') == ch and p.count('/') >= 1), None),
                 char_exists=ch in sc['sprites'])
            for e, ch, an, off in RE_ELEMENTS]),
        ('element_behaviour_reference', RE_NOTE + ' (A1-A8: health segments 38 px / skew -8 deg / low health <= 0.9; ammo skew +8 deg, '
                                          'ClipSegmentCap 60, low clip 25 %; kill feed 5 rows, 5.0 s + 1.0 s fade, 22 px step; '
                                          'announcements 4.5 s / reward 4.8 s; XP popups 2.0 s / 4.0 s killstreak) - behaviour is RE/Frontend-owned'),
        ('spatial_cues (the only directional HUD elements, RE A9 CONFIRMED)', {
            'damage_direction_arrows': {'symbol': 'mc_damageArrow', 'controller': 622, 'inputs': ['NotifyDamageIndicatorAdded', 'NotifyPlayerRotationChanged']},
            'missile_lock_warnings': {'symbols': ['mc_missileWarningVictim', 'mc_missileWarningVictimBrackets', 'mc_missileWarningVictimInbound',
                                                 'mc_missileWarningVictimLocked'], 'strings': ['$UIText.Hud.LockDetected', '$UIText.Hud.MissileInbound']},
            'offscreen_objective_arrows': {'owner': 'canvas TnObjectiveMarkerType* (OffscreenMarkerSize 0.0625, RotationParam ArrowAngle, DrawWhenOffscreen per type)',
                                           'materials': 'UI_HudMarkers_p (MarkerAlly / MarkerEnemy / MPMarkerDominationNode / TargetHealthBar)'},
            'ally_name_tags': {'owner': 'canvas TnObjectiveMarkerTypeTransformerVersus (AllyMarkerSetup DrawLabelWhenUnfocused, LabelFont MarkerFont)',
                               'class_specific': 'ally health bar on name tags only for Scientist viewers (RE E)'},
            'enemy_tags': 'only via buffs: OrbitalReconStreak (TnBuffSeeEnemyObjectiveMarkers) or HardLock'}),
        ('icon_sets', icon_sets),
        ('crosshair', crosshair),
        ('scoreboard', {**mrec('UI_GFxInGameStats_p/InGameStats_GFX'), 'player_list': mrec('UI_GFxPlayerList_p/PlayerList_GFX'),
                        'strings': loc.get('PlayerList')}),
        ('respawn', {**mrec('UI_GFxRespawn_p/MultiplayerRespawn_GFX'), 'strings': loc.get('Respawn')}),
        ('pregame_countdown', {**mrec('UI_GFxPreGameCountdown_p/PreGameCountdown_GFX'), 'TnVersusGame': {'MatchAutoStartCountdown': 10, 'MatchOverCountdown': 15}}),
        ('match_result', {**mrec('UI_GFxEndGameStats_p/EndGameStats_GFX'), 'strings': loc.get('EndGameStats'),
                          'game_over_message': msgs.get('TnVersusGameOverMessage'),
                          'music': {t: (m.get('music') or {}) for t, m in pres['modes'].items() if m.get('music')}}),
        ('notifications', {
            'score / point events': {'callback': cbs.get('PointEventScaleformCallback'), 'symbols': ['mc_pointTransaction', 'mc_pointTransactionLabel',
                                                                                                       'mc_pointTransactionKillstreakLabel', 'mc_pointMultiplier']},
            'game messages': {'callback': cbs.get('GameMessageCallBack'), 'class_strings': {c: cls_strings('TransGame.Default__' + c)
                                                                                           for c in ('TnGameMessage', 'TnKillStreakMessage', 'TnKillStreakEndedMessage', 'TnKillstreakActivatedMessage')}},
            'announcements (announcer-linked visuals)': {'callback': cbs.get('GameAnnouncementCallBack'), 'reward': cbs.get('RewardAnnouncementCallBack'),
                                                          'game_type_message': {t: m.get('game_type_message') for t, m in pres['modes'].items()},
                                                          'progress_announcements': msgs.get('TnGameProgressAnnouncementMessage'),
                                                          'killstreak_announcer': msgs.get('TnKillStreakAnnouncer')},
            'level_up': {'callback': cbs.get('NotifyLevelUpCallBack'), 'symbol': 'mc_levelUpNotify'},
            'ammo_pickup': {'callback': cbs.get('NotifyAmmoAddedCallback'), 'symbol': 'mc_ammoPickupNotification'},
            'message_colors': hud['message_colors (TnMessageTextColors)']}),
        ('class_specific', {s: {'abilities': sorted(k for k, a in classes['abilities'].items() if a.get('SpecialtyRestriction') == s),
                                'ability_icons': {('TnAbility' + k): [b['png'] for b in bm.get('TnAbility' + k, [])]
                                                  for k, a in classes['abilities'].items() if a.get('SpecialtyRestriction') == s},
                                'killstreaks': sorted(k for k, a in classes['killstreaks'].items() if s in (a.get('SpecialtyRestriction') or ''))}
                            for s in ('Scout', 'Scientist', 'Soldier', 'Leader')}),
        ('weapon_specific', {'weapon_icons': icon_sets['weapons (export = weapon class name)'], 'scopes': crosshair['scopes'],
                             'heat': 'NormalizedHeat / Heat observers (NotifyNormalizedHeatChanged / NotifyHeatChanged: no movie defines them)',
                             'charging': 'mc_chargingIndicator (charge weapons, e.g. PlasmaCannon)'}),
        ('fonts', {'embedded': h['fonts'], 'aliases': h.get('font_aliases'), 'fontlib': 'UI_GFxFonts_p.Fonts_EFIGS', 'canvas': 'UI_TransEngineFonts_p.MarkerFont'}),
        ('strings (UIText)', {s: loc.get(s) for s in ('Hud', 'EndGameStats', 'Respawn', 'PauseMenu', 'Downed', 'PlayerList')}),
        ('unresolved_for_RE', hud['unresolved_callbacks (no movie in this set defines it)']),
        ('minimap_radar', {'verdict': 'NONE - shipped WFC multiplayer has no minimap, radar or compass (CONFIRMED, closed; do not add one as "original")',
                           'evidence': ['AssetTools manifests/hud/minimap_radar_search.json (cooked objects, every GFx, localization, ini, filenames, decomp)',
                                        RE_NOTE + ' A9 (decompiled script, GFx constant pools, authored.db, default.xex strings Radar/MiniMap/Compass/Blip: 0 hits)']}),
        ('confidence', CONF + ' (cooked movie + class defaults + bytecode); element grouping HIGH')])
    json.dump(pkg, open(os.path.join(OUT, 'hud_package.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('->', os.path.join(OUT, 'hud_package.json'), 'layout instances', len(allpaths), {k: len(v['layout_instances']) for k, v in elements.items()})

if __name__ == '__main__':
    main()
