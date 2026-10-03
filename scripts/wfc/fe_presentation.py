"""Frontend asset inventory, mode presentation and HUD/scoreboard authored data (manifests only; no behaviour).

Needs frontend_gfx.json from fe_frontend.py.  Outputs (AssetTools/manifests/):
  frontend_assets.json            every UI_* package: role, size, cooked object classes, extracted files by type,
                                  plus the frontend levels' imported packages
  frontend_mode_presentation.json per mode: names/description/rules text (INT+FRA), tips, menu order, settings classes,
                                  rules classes, announcer dialog (event -> cue -> OPRIME/MGTRON WAVs), mode music,
                                  mode-specific messages and HUD observers, GFx symbols named after the mode
  frontend_hud.json               TnHUD movies, data observers + AS callbacks (resolved against Hud_GFX), UIController
                                  movies (countdown, pause, respawn, end game), element catalog (health, overshield, ammo,
                                  weapon, crosshair, timer, score, kills, objectives, scoreboard, results), textures, cues, text
  python fe_presentation.py
"""
import glob, json, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree, ue3pkg, extract  # noqa: E402
from m03_common import write, CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import ROOT  # noqa: E402
import fe_frontend as FE  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
CONTENT = os.path.join(ROOT, 'content')
GEN = 'AssetTools/scripts/wfc/fe_presentation.py'
ANNOUNCER_SET = 'SoundEvents_Dialog.Announcer.CHR_ANNOUNCER_DIALOG'

def rel(p): return os.path.relpath(p, ROOT).replace(os.sep, '/')
def J(n): return json.load(open(os.path.join(MANI, n), encoding='utf-8'))

def cue_brief(c):
    if not c: return None
    q = A.cue(c)
    return {'cue': c, 'missing': bool(q.get('missing')), 'category': q.get('category'),
            'wavs': [w['wav'] for w in q.get('waves', [])]}

# ------------------------------------------------------------------ phase 1: asset inventory
def assets():
    inv = objtree.inv()
    pk = inv.execute("SELECT package, role, contains_map, uncompressed_size FROM packages "
                     "WHERE package >= 'UI_' AND package < 'UI`' ORDER BY package").fetchall()
    out = {}
    for name, role, is_map, size in pk:
        cls = Counter(r[0] for r in inv.execute(
            "SELECT DISTINCT class, opath FROM exports WHERE opath >= ? AND opath < ?", (name + '.', name + '/')).fetchall())
        d = os.path.join(CONTENT, name)
        files = defaultdict(list)
        for p in sorted(glob.glob(os.path.join(d, '**', '*.*'), recursive=True)):
            files[os.path.splitext(p)[1].lstrip('.').lower()].append(rel(p))
        kind = ('level' if is_map else 'scaleform movies' if name.startswith('UI_GFx') else
                'level thumbnails' if 'Thumbnails' in name else 'logo' if 'Logo' in name else
                'fonts' if 'Font' in name else 'materials' if 'Materials' in name else
                'hud markers' if 'HudMarkers' in name else 'textures/other')
        out[name] = {'role': role, 'kind (name-based, HIGH)': kind, 'uncompressed_size': size,
                     'cooked_classes': dict(cls), 'extracted_files': {k: (v if len(v) <= 40 else v[:40] + ['... %d more' % (len(v) - 40)])
                                                                      for k, v in files.items()},
                     'extracted_counts': {k: len(v) for k, v in files.items()}}
    deps = {}
    for lv in FE.UI_LEVELS:
        path = os.path.join(extract.COOKED, lv + '.xxx')
        if not os.path.exists(path): continue
        p = ue3pkg.Package(path)
        deps[lv] = sorted({p.object_path(i + 1).split('.')[0] for i, e in enumerate(p.exports)
                           if p.class_name(e) == 'Package' and e['export_flags'] & 1})
        del p
    write('frontend_assets.json', {
        'generated_by': GEN,
        'packages': out,
        'ui_level_cooked_source_packages (forced exports inside each level file)': deps,
        'notes': ['GFx movie internals (symbols, labels, fonts, sounds, callbacks) are in frontend_gfx.json',
                  'external textures a movie binds at runtime are listed per movie under ue_objects.movie_instance.ExternalTextures',
                  'faction imagery: UI_CustomChar_p palette swatches, CharacterSelect/Customize PNGs, lobby faction fscommands; '
                  'no separate faction-art package exists (CONFIRMED by package list)'],
        'confidence': CONF + ' (package list, classes, files); kind labels HIGH (name-based)'})
    return out

# ------------------------------------------------------------------ phase 4: modes
def announcer_table():
    t = {}
    for e in A.values(ANNOUNCER_SET).get('SoundEventSet') or []:
        if e.get('Event'): t[e['Event']] = e.get('Sound')
    return t

def dialog(ev, table):
    if not ev: return None
    c = table.get(ev)
    return {'event': ev, 'cue': c, 'wavs': cue_brief(c)['wavs'] if c else [],
            'resolved_via': ANNOUNCER_SET if c else None, 'confidence': CONF if c else UNK + ' (event not in the announcer set)'}

SCORE_PANEL = {'DM': 'mc_scoreFreeForAll', 'TDM': 'mc_scoreTeam', 'CTF': 'mc_scoreTeam', 'KOTH': 'mc_scoreTeam',
               'DOM': 'mc_scoreTeam', 'EXT': 'mc_scoreTeam', 'SV': 'mc_scoreSurvival', 'CP': 'mc_scoreCoop', 'CCP': 'mc_scoreCoop'}

def icon_rec(gfx, tag):
    r = gfx.get('UI_GFxShared_p/SharedIcons_GFX') or {}
    sym = 'mc_gameModeIcon' + tag
    if sym not in r.get('exports', []):
        return {'symbol': None, 'confidence': UNK}
    return {'movie': 'UI_GFxShared_p/SharedIcons_GFX', 'file': r['file'], 'symbol': sym,
            'loaded_by': 'GameLobby_GFX / PartyLobby_GFX mc_gameModeIconLoadReference (HIGH, name)',
            'bitmaps': (r.get('symbol_bitmaps (export -> bitmaps drawn via placements / shape bitmap fills)') or {}).get(sym) or [],
            'art': ('vector shapes only (no bitmap fill or external image under the symbol; CONFIRMED by gfxscan.symbol_bitmaps) - '
                    'render the symbol from SharedIcons_GFX'
                    if sym in (r.get('vector_only_exports') or []) else 'bitmap-backed (see bitmaps)'),
            'confidence': CONF + ' (exported symbol)'}

def modes(gfx):
    table = announcer_table()
    base = A.values('TransGame.Default__TnOnlineGameSettingsBase')
    order = [re.search(r'GameSettingsClassName="TransGame\.TnOnlineGameSettings(\w+?)Public"', p).group(1)
             for p in (FE.read_ini(os.path.join(FE.INI, 'TransPlaylists.ini')).get('TransGame.TnOnlinePlaylistManager') or {}).get('Playlists', [])]
    INT = FE.loc_tables(FE.INT).get('TransGame', {}); FRA = FE.loc_tables(FE.FRA).get('TransGame', {})
    ui = FE.loc_tables(FE.INT).get('UIText', {}).get('GameTypes') or {}
    names = {'DM': ['Deathmatch', 'FreeForAll', 'DM'], 'TDM': ['TeamDeathmatch', 'TDM'], 'CTF': ['CodeOfPower', 'CTF'],
             'KOTH': ['PowerStruggle', 'KOTH'], 'DOM': ['Domination', 'Conquest', 'DOM'],
             'EXT': ['Extinction', 'EXT', 'Bomb'], 'SV': ['Escalation', 'Survival', 'SV'], 'CP': ['CP', 'COOP'], 'CCP': ['CCP']}
    out = {}
    for tm in base.get('TagToModeMap') or []:
        tag = tm['Tag']
        if tag == 'SOLO': continue
        cls = 'TnOnlineGameSettings' + tag
        v = A.values('TransGame.Default__' + cls) if A.get('TransGame.Default__' + cls) else {}
        pub = A.values('TransGame.Default__' + cls + 'Public') if A.get('TransGame.Default__' + cls + 'Public') else {}
        msg_o = 'TransGame.Default__TnGameTypeMessage' + tag
        msg = A.values(msg_o) if A.get(msg_o) else {}
        tips = []
        for t in v.get('EngageText') or []:
            if t not in tips: tips.append(t)
        words = [w for w in names.get(tag, [tag]) if len(w) > 4]
        short = [w for w in names.get(tag, [tag]) if len(w) <= 4]
        rxw = re.compile('|'.join(words), re.I) if words else None
        rxs = re.compile('|'.join('(?<![A-Z])%s(?![a-z0-9_])' % w for w in short)) if short else None
        class _R:
            @staticmethod
            def search(x): return (rxw and rxw.search(x)) or (rxs and rxs.search(x))
        rx = _R
        sym = []
        for k, r in gfx.items():
            hits = sorted({x for x in r['exports'] if rx.search(x)} |
                          {l['label'] for s in r['sprites_exported_or_labelled'].values() for l in s['labels'] if rx.search(l['label'])} |
                          {l['label'] for l in r['root_labels'] if rx.search(l['label'])} |
                          {os.path.basename(p) for p in r['images_extracted'] if rx.search(os.path.basename(p))})
            if hits: sym.append({'movie': k, 'names': hits[:30]})
        out[tag] = {
            'menu_order (TnOnlinePlaylistManager.Playlists)': order.index(tag) if tag in order else None,
            'mode_property_id (TagToModeMap)': tm.get('PropertyId'),
            'settings_class': 'TransGame.' + cls,
            'text': {'FriendlyName': {'INT': (INT.get(cls) or {}).get('FriendlyName'), 'FRA': (FRA.get(cls) or {}).get('FriendlyName')},
                     'Description': {'INT': (INT.get(cls) or {}).get('Description'), 'FRA': (FRA.get(cls) or {}).get('Description')},
                     'RulesFormat': {'INT': (INT.get(cls) or {}).get('RulesFormat'), 'FRA': (FRA.get(cls) or {}).get('RulesFormat')},
                     'rules_tokens (TnOnlineGameSettingsBase.RulePairs)': base.get('RulePairs'),
                     'UIText.GameTypes': {k: x for k, x in ui.items() if rx.search(k)}},
            'loading_tips (EngageText, de-duplicated; base tips in frontend_loading.json)': tips,
            'settings': {k: v.get(k) for k in ('GameClass', 'LobbyGameClass', 'NumRequiredPlayers', 'TeamType', 'TimeLimits',
                                              'ScoreLimits', 'GoalScores', 'KillLimits', 'RoundLimits', 'Rules') if k in v},
            'public_settings': {k: pub.get(k) for k in ('NumPublicConnections', 'StatsWriters') if k in pub},
            'announcer': {'GameTypeDialog': dialog(msg.get('GameTypeDialog'), table),
                          'GameDescriptionDialog': dialog(msg.get('GameDescriptionDialog'), table)},
            'music': {k: cue_brief(msg.get(k)) for k in ('GameTypeMusic', 'GameNearlyCompleteMusic', 'AutobotsWinMusic',
                                                         'DecepticonsWinMusic', 'TieMusic') if msg.get(k)},
            'game_type_message': {'class': msg_o if msg else None, 'GameTypeMessage': msg.get('GameTypeMessage'),
                                  'Lifetime': msg.get('Lifetime'), 'PosY': msg.get('PosY')},
            'gfx_symbols_named_after_mode (name match, HIGH)': sym,
            'icon': icon_rec(gfx, tag),
            'hud_score_panel (Hud_GFX export, name-based HIGH)': SCORE_PANEL.get(tag),
            'confidence': CONF + ' (authored text/classes/cues); behaviour of rules/messages = RE/Gameplay'}
    extra = {}
    for c in ('TnCTFMessage', 'TnDominationMessage', 'TnGameProgressAnnouncementMessage', 'TnKillStreakAnnouncer', 'TnAnnouncer',
              'TnMessageTextColors', 'TnGameMessage', 'TnKillStreakMessage', 'TnKillStreakEndedMessage', 'TnKillstreakActivatedMessage'):
        o = 'TransGame.Default__' + c
        if not A.get(o): continue
        v = A.values(o)
        rec = {k: x for k, x in v.items() if k not in ('bIsSpecial', 'bIsConsoleMessage')}
        evs = {x for x in json.dumps(v).split('"') if x.startswith('SoundEvents_Dialog.')}
        rec['dialog_resolved'] = {e: dialog(e, table) for e in sorted(evs)}
        extra[c] = rec
    go = A.values('TransContent.Default__TnVersusGameOverMessage')
    extra['TnVersusGameOverMessage'] = {**go, 'dialog_resolved': {e: dialog(go.get(e), table) for e in ('AutobotWinSound', 'DecepticonWinSound')}}
    write('frontend_mode_presentation.json', {
        'generated_by': GEN,
        'sources': ['TransGame.Default__TnOnlineGameSettings<TAG>(Public) CDOs', 'TransGame.int / TransGame.FRA [TnOnlineGameSettings<TAG>]',
                    'TransGame.Default__TnGameTypeMessage<TAG>', ANNOUNCER_SET + ' (bound by every MP TnWorldInfo.AnnouncerSoundEventSet)',
                    'TransPlaylists.ini', 'UIText.int [GameTypes]', 'frontend_gfx.json'],
        'announcer_voices (TnAnnouncer: Team0/Team1 DialogCharacter)': A.values('TransGame.Default__TnAnnouncer'),
        'announcer_note': 'each switchboard cue carries the Optimus (team 0) and Megatron (team 1) take; which one plays is '
                          'decided by script/native (RE)',
        'modes': out, 'shared_messages': extra,
        'other_mode_icons (SharedIcons_GFX)': sorted(e for e in (gfx.get('UI_GFxShared_p/SharedIcons_GFX') or {}).get('exports', [])
                                                     if e.startswith('mc_gameModeIcon')),
        'unlisted_mode_RO': 'SharedIcons mc_gameModeIconRO and announcer event MP_GameTypeRollOutDialog exist, but no GameModeInfo, '
                            'playlist or settings class: a cut/unused "Roll Out" mode (UNKNOWN status, not shipped as playable)',
        'announcer_event_table': {e: c for e, c in sorted(announcer_table().items())}})
    return out

# ------------------------------------------------------------------ phase 6: HUD
CATS = [('health', r'health|segment|downed|energon'), ('overshield', r'overshield|shield'),
        ('ammo', r'ammo|clip|reserve|magazine'), ('reload', r'reload|jam'), ('weapon', r'weapon'),
        ('crosshair', r'crosshair|reticule|reticle|spread|lockon|lock_on|rangefinder'), ('heat', r'heat|overheat'),
        ('timer', r'timer|clock|time'), ('team_score', r'score|team|point'), ('kill_death', r'kill|death|obituar|feed|streak'),
        ('objective_markers', r'marker|objective|capture|bomb|flag|node'), ('damage', r'damage|hit'),
        ('abilities', r'abilit|cooldown|buff'), ('form', r'form|transform|vehicle'), ('messages', r'message|announc|tutorial'),
        ('grenades', r'grenade')]

def categorize(names):
    c = defaultdict(list)
    for n in names:
        for cat, rx in CATS:
            if re.search(rx, n, re.I): c[cat].append(n)
    return {k: sorted(set(v)) for k, v in c.items()}

def movie_brief(r):
    if not r: return None
    return {'file': r['file'], 'exports': r['exports'], 'root_labels': r['root_labels'],
            'sprites_exported_or_labelled': r['sprites_exported_or_labelled'], 'text_fields': r['text_fields'],
            'localization_keys': r['localization_keys'], 'fonts': r['fonts'], 'imports': r['imports'],
            'callbacks_defined': r['_global_callbacks_defined (called from script/native)'],
            'bridge_calls': [b['call'] for b in r['bridge_calls (ExternalInterface.call)']],
            'ui_sound_cues_named': r['ui_sound_cues_named'], 'images_extracted': r['images_extracted'],
            'ue_objects': r['ue_objects']}

def hud(gfx):
    import gfxscan
    allstr = {}
    for k, r in gfx.items():
        sc = gfxscan.scan(os.path.join(ROOT, r['file']))
        allstr[k] = {x for a in sc['action_strings'] for x in a['strings']}
    h = A.values('TransGame.Default__TnHUD')
    obs = []
    for o in h.get('DataObservers') or []:
        r = A.get(o)
        v = A.values(o)
        obs.append({'object': o, 'class': r['class'] if r else None, 'callback': v.get('CallbackBindingName'),
                    'props': {k: x for k, x in v.items() if k != 'CallbackBindingName'}})
    for c in h.get('TemporaryObserverClasses') or []:
        pk, cn = c.split('.')
        o = '%s.Default__%s' % (pk, cn)
        v = A.values(o) if A.get(o) else {}
        obs.append({'object': o, 'class': cn, 'callback': v.get('CallbackBindingName'), 'temporary (mode-specific)': True,
                    'props': {k: x for k, x in v.items() if k != 'CallbackBindingName'}})
    cbs = {k: v for k, v in h.items() if isinstance(v, str) and v.startswith('_global.')}
    ui = A.values('TransContent.Default__TnUIControllerMultiplayer')
    movies = {'HudMovie': h.get('HudMovie'), 'ScoreboardMovie': h.get('ScoreboardMovie')}
    movies.update({k: v for k, v in ui.items() if k.endswith('UI') and isinstance(v, str)})
    def rec_for(inst):
        if not inst: return None, None
        pkg, base = inst.split('.')
        key = pkg + '/' + (base[:-2] if base.endswith('_1') else base)
        return key, gfx.get(key)
    defined = {}
    for k, inst in movies.items():
        key, r = rec_for(inst)
        if r: defined[key] = set(r['_global_callbacks_defined (called from script/native)'])
    def where(cb):
        n = cb.split('.', 1)[1]
        return sorted(k for k, s in defined.items() if n in s)
    resolved = {}
    for o in obs:
        if o['callback']: resolved[o['callback']] = where(o['callback'])
    for k, cb in cbs.items(): resolved[cb] = where(cb)
    if ui.get('NotificationFunctionName'): resolved[ui['NotificationFunctionName']] = where(ui['NotificationFunctionName'])
    hk, hr = rec_for(h.get('HudMovie'))
    names = []
    if hr:
        names = (hr['exports'] + [l['label'] for s in hr['sprites_exported_or_labelled'].values() for l in s['labels']] +
                 [i for s in hr['sprites_exported_or_labelled'].values() for i in s['instances']] +
                 hr['_global_callbacks_defined (called from script/native)'] + [os.path.basename(p) for p in hr['images_extracted']])
    elements = {}
    script = categorize([o['class'] or '' for o in obs] + [o['callback'] or '' for o in obs] + list(cbs.values()))
    gx = categorize(names)
    for cat, _ in CATS:
        if script.get(cat) or gx.get(cat):
            elements[cat] = {'script_side (observer classes / callbacks)': script.get(cat, []),
                             'hud_gfx_side (exports, labels, instances, callbacks, images)': gx.get(cat, [])[:60]}
    elements['scoreboard'] = {'movie': movies.get('ScoreboardMovie'), 'record': 'see movies'}
    elements['match_end_results'] = {'movie': movies.get('EndGameUI'),
                                     'messages': 'TnVersusGameOverMessage (frontend_mode_presentation.json shared_messages)'}
    elements['pre_match_countdown'] = {'movie': movies.get('GameStartUI'),
                                       'TnVersusGame': {k: A.values('TransContent.Default__TnVersusGame').get(k)
                                                        for k in ('MatchAutoStartCountdown', 'MatchOverCountdown')}}
    loc = FE.loc_tables(FE.INT).get('UIText', {})
    hud_cues = sorted({c for k, r in gfx.items() if k.split('/')[0] in ('UI_GFxHud_p', 'UI_GFxInGameStats_p', 'UI_GFxEndGameStats_p',
                                                                          'UI_GFxPreGameCountdown_p', 'UI_GFxRespawn_p', 'UI_GFxPause_p')
                       for c in r['ui_sound_cues_named']})
    markers = sorted(rel(p) for p in glob.glob(os.path.join(CONTENT, 'UI_HudMarkers_p', '*.png')))
    mk = {}
    for c in ('TnObjectiveMarkerTypeTransformerVersus', 'TnObjectiveMarkerTypeDomination'):  # canvas-drawn markers
        o = 'TransGame.Default__' + c
        if A.get(o): mk[c] = A.values(o)
    write('frontend_hud.json', {
        'generated_by': GEN,
        'scope': 'authored HUD / scoreboard / match flow presentation assets. What drives each value is script/native (RE); '
                 'nothing here is behaviour.',
        'tnhud': {k: h.get(k) for k in ('HudMovie', 'DefaultHudMovie', 'ScoreboardMovie', 'HudVisible', 'HudCanvasScale',
                                        'TemporaryObserverClasses', 'TutorialDisplayer')},
        'ui_controller_multiplayer (TransContent.TnUIControllerMultiplayer)': ui,
        'data_observers': obs,
        'hud_callbacks (TnHUD properties)': cbs,
        'callback_resolution (callback -> movies defining that _global function)': resolved,
        'unresolved_callbacks (no movie in this set defines it)': {
            k: {'name_string_in_any_movie': sorted(m for m, st in allstr.items() if k.split('.', 1)[1] in st),
                'status': 'no shipped movie defines it: the script invoke has no AS target (no-op at runtime unless native '
                          'handles it) - RE'} for k, v in sorted(resolved.items()) if not v},
        'elements (name-based classification, HIGH)': elements,
        'movies': {k: {'instance': inst, 'record': movie_brief(rec_for(inst)[1])} for k, inst in movies.items()},
        'objective_marker_types': mk,
        'hud_marker_textures (UI_HudMarkers_p)': markers,
        'ui_sound_cues_named_by_hud_movies': {c: cue_brief(next((p + '.' + c for p in FE.UI_CUE_PKGS if A.get(p + '.' + c)), None))
                                             for c in hud_cues},
        'text (UIText.int sections)': {s: dict(loc.get(s) or {}) for s in ('Hud', 'EndGameStats', 'Respawn', 'PauseMenu', 'Downed', 'GameOver')},
        'message_colors (TnMessageTextColors)': A.values('TransGame.Default__TnMessageTextColors'),
        'confidence': CONF + ' for authored objects, links and assets; HIGH for element categories (name-based)'})
    return resolved

def main():
    gfx = J('frontend_gfx.json')['movies']
    a = assets()
    m = modes(gfx)
    r = hud(gfx)
    print('ui packages', len(a), 'modes', len(m), 'hud callbacks', len(r), 'unresolved', sum(1 for v in r.values() if not v))

if __name__ == '__main__':
    main()
