"""Frontend delivery package: one consolidated, machine-readable handoff for the Frontend lane.

Consolidates the already-recovered frontend manifests (fe_frontend.py, fe_presentation.py, fe_map_catalog.py) plus the
RE script decompilation (read-only, RE-Workspace/work/script/decomp) into AssetTools/manifests/frontend_package/:

  frontend_package.json  screens (boot -> title -> main -> multiplayer -> party lobby -> game lobby -> loading -> match ->
                         post-match -> return) with their movies, submovies, UI controller, level, music, sounds,
                         transitions; per-movie dependency records (imports, fonts, textures + PNGs, data-store bindings,
                         localization keys, sound cues, fscommands, bridge calls, callbacks); font library chain;
                         travel URL formats
  mp_registry.json       runtime map + mode registry (all MP maps and modes, selection rules, settings defaults/options,
                         HUD/score/objective presentation references, audio, localization)
  loading_handoff.json   exact selected map/mode -> loading screen relationships (movie, GFx, text, tips, spinner, audio)
  hud_handoff.json       HUD / scoreboard / match-flow inputs and dependencies grouped by element
Every relationship carries a confidence and a source. Nothing is invented: absent data is stated as absent.
  python fe_package.py
"""
import glob, json, os, re, sys
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, gfxscan  # noqa: E402
from m03_common import CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import ROOT  # noqa: E402
import fe_frontend as FE  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
OUT = os.path.join(MANI, 'frontend_package')
GEN = 'AssetTools/scripts/wfc/fe_package.py'
DECOMP = 'RE-Workspace/work/script/decomp'
CONTENT = os.path.join(ROOT, 'content')

def J(n): return json.load(open(os.path.join(MANI, n), encoding='utf-8'))
def rel(p): return os.path.relpath(p, ROOT).replace(os.sep, '/')
def src(*s): return list(s)

def write(name, obj):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    json.dump(obj, open(p, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('->', p)

def png_for(opath):
    """Extracted PNG of a cooked texture object (content/<pkg>/[<group>/]<name>.png)."""
    if not opath: return None
    parts = opath.split('.')
    for cand in (os.path.join(CONTENT, *parts) + '.png', os.path.join(CONTENT, parts[0], parts[-1]) + '.png'):
        if os.path.exists(cand): return rel(cand)
    return None

def obj_class(opath):
    r = A.get(opath) if opath else None
    return r['class'] if r else None

# ------------------------------------------------------------------ movies
def movie_key_for_swf(url, keys):
    """Resolve an SWF-relative path (as authored in the movie) to the cooked movie key."""
    stem = os.path.splitext(os.path.basename(url))[0].lower()
    if stem == 'gfxfontlib':
        return 'UI_GFxFonts_p/Fonts_EFIGS'          # GFxUI.int [FontLib] FontLib=UI_GFxFonts_p.Fonts_EFIGS
    for k in keys:
        b = k.split('/')[1].lower()
        if b in (stem, stem + '_gfx'): return k
    return None

def movie_records(gfx, loc, audio):
    keys = sorted(gfx)
    cue_of = audio['gfx_ui_sounds (names passed to Sound.PlaySound in AS, matched to cue names)']
    font_cfg = FE.loc_tables(FE.INT).get('GFxUI', {})
    aliases = {'$' + k: v for k, v in (font_cfg.get('Fonts') or {}).items()}
    out = OrderedDict()
    for k in keys:
        r = gfx[k]
        sc = gfxscan.scan(os.path.join(ROOT, r['file']))
        strings = [x for a in sc['action_strings'] for x in a['strings']]
        mi = (r['ue_objects'] or {}).get('movie_instance') or {}
        info = (r['ue_objects'] or {}).get('movie_info') or {}
        refs = []
        for x in info.get('References') or []:
            refs.append({'object': x, 'class': obj_class(x), 'png': png_for(x)})
        ext = [{'resource': e['Resource'], 'texture': e['Texture'], 'class': obj_class(e['Texture']), 'png': png_for(e['Texture'])}
               for e in mi.get('ExternalTextures') or []]
        subs = [{'swf': u, 'movie': movie_key_for_swf(u, keys)} for u in r['loads_movies']]
        imps = defaultdict(list)
        for i in r['imports']: imps[i['url']].append(i['name'])
        out[k] = {
            'file': r['file'],
            'ue_movie_info': info.get('object'), 'ue_movie_instance': mi.get('object'),
            'instance_settings': {x: mi.get(x) for x in ('TimingMode', 'RenderTextureMode', 'bGammaCorrection', 'Depth',
                                                         'CaptureKeys', 'FocusIgnoreKeys') if mi.get(x) is not None},
            'imports (shared libraries)': [{'swf': u, 'movie': movie_key_for_swf(u, keys), 'symbols': n} for u, n in imps.items()],
            'submovies (loaded at runtime)': subs,
            'fonts': {'embedded': r['fonts'], 'aliases_used': {a: aliases.get(a) for a in r['font_aliases']}},
            'textures': {'runtime_external (GFxMovie.ExternalTextures: resource slot -> texture)': ext,
                         'cooked_references (GFxMovieInfo.References)': refs,
                         'symbol_bitmaps': r['symbol_bitmaps (export -> bitmaps drawn via placements / shape bitmap fills)']},
            'exports': r['exports'],
            'timelines (exported or labelled sprites)': {s: {'export': v['export'], 'frames': v['frames'], 'labels': v['labels'],
                                                              'instances': v['instances']}
                                                          for s, v in r['sprites_exported_or_labelled'].items()},
            'root_labels': r['root_labels'],
            'text_fields': r['text_fields'],
            'data_store_bindings': sorted({x for x in strings if re.fullmatch(r'<[A-Za-z_]+:[^<>]+>', x)}),
            'localization_keys': {key: loc['gfx_keys'].get(key) for key in r['localization_keys']},
            'sound_cues': {c: {'cue': cue_of.get(c, {}).get('cue'), 'wavs': [w['wav'] for w in cue_of.get(c, {}).get('waves', [])]}
                           for c in r['ui_sound_cues_named']},
            'fscommands_sent': sorted({x for x in strings if x in FSCMDS}),
            'bridge_calls (AS -> script)': [b['call'] for b in r['bridge_calls (ExternalInterface.call)']],
            'callbacks_defined (script -> AS)': r['_global_callbacks_defined (called from script/native)'],
            'confidence': CONF + ' (cooked movie tags/bytecode, cooked GFx objects)'}
    return out

FSCMDS = set()

# ------------------------------------------------------------------ screens
def screens(flow, mv, hud):
    fe = flow['levels']['UI_FrontEnd_m']
    seq = fe['movie_sequences'][0]
    ui = hud['ui_controller_multiplayer (TransContent.TnUIControllerMultiplayer)']
    pl = A.values('TransContent.Default__TnUIControllerPartyLobby'); gl = A.values('TransContent.Default__TnUIControllerGameLobby')
    def mk(inst):
        if not inst: return None
        p, b = inst.split('.'); return p + '/' + (b[:-2] if b.endswith('_1') else b)
    def lv_audio(lv):
        r = flow['levels'].get(lv) or {}
        return {'music': [m.get('SoundCue') for m in r.get('music') or [] if m], 'sounds': [s.get('cue') for s in r.get('sounds') or []]}
    S = OrderedDict()
    S['boot_legal'] = {
        'what': 'legal screen played by the engine while the first map loads',
        'movie_file': 'movies/TF_InitialStartup_<NA|EU>_<INT|FRA>.mkv (+ TF_InitialStartup.mkv / _FRA)',
        'config': 'Xe-TransGame.ini [LoadingMovie] InitialStartupFileName=TF_InitialStartup',
        'next': 'level UI_FrontEnd_m (Xe-TransEngine.ini [URL] Map=UI_FrontEnd_m)',
        'confidence': CONF + ' (config + inspected frames); region/language variant choice is native (RE)'}
    S['logo_sequence'] = {
        'level': 'UI_FrontEnd_m', 'game_class': 'TransContent.TnFrontEndGame (MaxPlayers=1)',
        'movie': mk('UI_GFxFrontEnd_p.MovieLoader_GFX_1'),
        'opened_by': 'Kismet TnSeqAct_OpenFrontEnd -> SeqAct_InstallGame -> GFxAction_OpenMovie MovieLoader_GFX_1',
        'video_chain': seq['movies'], 'video_trigger': 'fscommand "%s" from MovieLoader_GFX' % seq['trigger_fscommand'],
        'skip_trigger': 'fscommand "enterFrontEnd" (MovieLoader decides via Game.HasWatchedIntroMovie - RE)',
        'audio': 'inside the logo/intro movies ([Engine.MovieSettings] MoviesToAlwaysPlaySound = the three logos)',
        'next': 'title', 'confidence': CONF}
    S['title'] = {
        'level': 'UI_FrontEnd_m', 'movie': 'UI_GFxFrontEnd_p/FrontEnd_GFX', 'symbol': 'mc_menuPressStart',
        'logo': 'mc_transformersLogo + external textures TransformersWFCLogo[TM]_<LANG> (FrontEnd_GFX_1.ExternalTextures)',
        'text': {'$UIText.MainMenu.PressStart': 'Press START button'},
        'entered_after': 'after the last intro movie stops: camera matinees, music, reveal sound, SetLoadingMovieFilename, ToggleHUD',
        'audio': lv_audio('UI_FrontEnd_m'), 'confidence': CONF + ' (symbol + Kismet); press-start handling is AS/script'}
    S['main_menu'] = {
        'level': 'UI_FrontEnd_m', 'movie': 'UI_GFxFrontEnd_p/FrontEnd_GFX',
        'symbols': [e for e in mv['UI_GFxFrontEnd_p/FrontEnd_GFX']['exports'] if e.startswith('mc_menu')],
        'submovies': [s['movie'] for s in mv['UI_GFxFrontEnd_p/FrontEnd_GFX']['submovies (loaded at runtime)']],
        'fscommands': ['startMainMenuCamera -> Kismet orbit-camera matinee'],
        'multiplayer_entry': 'Online.OpenPartyLobby (bridge) -> level UI_PartyLobby_m (TnPlayerController.GetPartyMapName)',
        'confidence': CONF}
    S['settings'] = {
        'movie': 'UI_GFxSettings_p/SettingsMenu_GFX', 'loaded_from': [k for k, v in mv.items()
                                                                       if any(s['movie'] == 'UI_GFxSettings_p/SettingsMenu_GFX' for s in v['submovies (loaded at runtime)'])],
        'related': ['UI_GFxBrightness_p/Brightness_GFX', 'UI_GFxBrightness_p/CalibrationImage_GFX'],
        'confidence': CONF}
    S['party_lobby'] = {
        'what': 'Multiplayer menu: playlist / mode selection, private match setup, party, character customization',
        'level': 'UI_PartyLobby_m', 'game_class': 'TransContent.TnPartyLobbyGame (MaxPlayers=10, PresenceId 4)',
        'ui_controller': 'TransContent.TnUIControllerPartyLobby', 'movie': mk(pl.get('LobbyUI')),
        'mode_selection_symbols': [e for e in mv[mk(pl.get('LobbyUI'))]['exports'] if 'GameMode' in e or 'Playlist' in e or 'gameMode' in e],
        'submovies': [s['movie'] for s in mv[mk(pl.get('LobbyUI'))]['submovies (loaded at runtime)']],
        'prompts': {k: A.values('TransContent.Default__TnPartyLobbyGame').get(k) for k in
                    ('SearchingMessage', 'JoiningMessage', 'HostingMessage', 'CancelSearchMessage', 'HostingTitle', 'SearchingTitle')},
        'audio': lv_audio('UI_PartyLobby_m'),
        'to_game_lobby': 'TnOnlineGameSettingsBase.BuildLobbyURL: <LobbyMapName>?Game=<LobbyGameClass>?GameModeTag=<TAG>'
                         '?GameTeamStatus=<TeamType>?MaxPlayers=<n>?IconicMode=<0|1> (LobbyMapName = UI_Lobby_m for versus modes)',
        'character_customization_level': 'UI_CharacterCustomization_m (lobby fscommands hide/unhide/fadein/glow Autobot|Decepticon, initStreamingLvl)',
        'confidence': CONF + ' (classes, movies, script URL builder)'}
    gv = A.values('TransGame.Default__TnGameReplicationInfoGameLobby')
    S['game_lobby'] = {
        'what': 'pre-match lobby: map display / host map choice / map veto, teams, character select, countdown',
        'level': 'UI_Lobby_m', 'game_class': 'TransContent.TnGameLobbyGame<Team|FreeForAll|...> (per mode LobbyGameClass)',
        'ui_controller': 'TransContent.TnUIControllerGameLobby', 'movie': mk(gl.get('LobbyUI')),
        'map_display': {'symbols': ['mc_mapDisplay', 'mc_mapImage', 'mc_mapLabelCampaign'],
                        'data_store_bindings': ['<TnMenuItems:Maps>', '<CurrentGame:SelectedMapID>', '<CurrentGame:GameTeamStatus>'],
                        'image': 'MapInfo.ImagePath -> Self.SetExternalTextureWithPath (fallback UI_LevelThumbnails_p.LevelUnavailable); '
                                 'GameLobby_GFX_1 ExternalTextures slot LevelThumb = UI_LevelThumbnails_p.LevelMultiGeneric by default',
                        'confidence': CONF + ' (AS strings + cooked GFxMovie); bridge behaviour RE'},
        'map_choice': 'host: Online.SetSelectedMapID; others: map veto (submitMapVeto / SubmitMapVeto); rotation = '
                      'TnGameReplicationInfoGameLobby.SelectRandomMap over GetCompatibleMaps (see mp_registry selection_rules)',
        'status_strings': {k: gv.get(k) for k in ('WaitingForPlayersStatus', 'WaitingForOnePlayerStatus',
                                                  'WaitingForCharacterChoiceStatus', 'WaitingForHostToStartStatus', 'WaitingForBalancedTeamsStatus')},
        'timers': {'LobbyIntermissionTime': gv.get('LobbyIntermissionTime'), 'LowCountdownTickThreshold': gv.get('LowCountdownTickThreshold')},
        'sounds': {k: gv.get(k) for k in ('LowCountdownTickSound', 'PlayerJoinedSound', 'PlayerLeftSound')},
        'MessageOfTheDay': gv.get('MessageOfTheDay'),
        'submovies': [s['movie'] for s in mv[mk(gl.get('LobbyUI'))]['submovies (loaded at runtime)']],
        'audio': lv_audio('UI_Lobby_m'),
        'to_match': 'game URL = <MapFilename> (+ GRI.ModifyURL ?MapId=<id>) + TnOnlineGameSettingsBase.BuildURL '
                    '?Game=<GameClass>?GameModeTag=<TAG>?GameTeamStatus=..?GameRules=..?MaxPlayers=..?StatsWriters=..'
                    '?LobbyGameClassName=..?IconicMode=..?TimeLimit=<TimeLimits[index]> (+properties, ?listen)',
        'confidence': CONF}
    S['loading'] = {'see': 'loading_handoff.json', 'trigger': 'TnGame.ServerTravelToMap / TnPlayerController.PreClientTravel -> '
                    'TnMoviePlayer.StartLoadingMovie(URL)', 'confidence': CONF}
    S['match'] = {
        'game_class': 'TransContent.TnVersusGame', 'ui_controller': 'TransContent.TnUIControllerMultiplayer',
        'movies': {k: mk(v) for k, v in ui.items() if k.endswith('UI') and isinstance(v, str)},
        'hud': 'TransGame.TnHUD -> ' + mk(hud['tnhud']['HudMovie']) + ', scoreboard ' + mk(hud['tnhud']['ScoreboardMovie']),
        'countdowns': {'MatchAutoStartCountdown': 10, 'MatchOverCountdown': 15, 'source': 'TransContent.Default__TnVersusGame'},
        'see': 'hud_handoff.json', 'confidence': CONF}
    S['post_match'] = {
        'movie': mk(ui.get('EndGameUI')), 'messages': 'TnVersusGameOverMessage (win/lose/tie text + announcer, mp_registry)',
        'return': 'TnGame.ReturnToGameLobby -> ServerTravel(<lobby URL>?MapId=<current>) -> loading (lobby branch: no map name, '
                  'base tips) -> game_lobby',
        'confidence': CONF + ' (script)'}
    S['quit_to_front_end'] = {'via': 'Game.QuitToMainMenu (bridge) / TnGame.OpenFrontEndMap -> "disconnect local" + '
                                     'ClientTravel UI_FrontEnd_m', 'confidence': CONF + ' (script)'}
    S['pause'] = {'movie': mk(ui.get('PauseUI')), 'confidence': CONF}
    return S

# ------------------------------------------------------------------ registry
def registry(maps_cat, modes_fm, pres, loc_int):
    base = A.values('TransGame.Default__TnOnlineGameSettingsBase')
    reg_modes = OrderedDict()
    for tag, p in pres['modes'].items():
        cls = 'TransGame.Default__TnOnlineGameSettings' + tag
        e = A.effective(cls) if A.get(cls) else {}
        pub = A.effective(cls + 'Public') if A.get(cls + 'Public') else {}
        V = lambda d, k: (d.get(k) or {}).get('value')
        lsm = V(e, 'LocalizedSettingsMappings') or []
        ls = {x['Id']: x for x in V(e, 'LocalizedSettings') or []}
        pm = V(e, 'PropertyMappings') or []
        props = {x['PropertyId']: x for x in V(e, 'Properties') or []}
        settings = []
        for m in lsm:
            cur = ls.get(m['Id'])
            vm = {v['Id']: v['Name'] for v in m.get('ValueMappings') or []}
            settings.append({'id': m['Id'], 'name': m['Name'], 'header': m.get('ColumnHeaderText'),
                             'values': [{'id': v['Id'], 'name': v['Name']} for v in m.get('ValueMappings') or []],
                             'default_value_id (LocalizedSettings.ValueIndex = ValueMappings.Id)': cur['ValueIndex'] if cur else None,
                             'default_value': vm.get(cur['ValueIndex']) if cur else None,
                             **({'note': 'online game-mode context value (advertised; its own numbering, not the TagToModeMap '
                                         'PropertyId); the CDO lists no value names for it - display text comes from FriendlyName'}
                                if m['Name'] == 'GameMode' else {}),
                             'advertised': cur['AdvertisementType'] if cur else None, 'kind': 'localized setting'})
        for m in pm:
            cur = props.get(m['Id'])
            settings.append({'id': m['Id'], 'name': m['Name'], 'header': m.get('ColumnHeaderText'), 'mapping': m.get('MappingType'),
                             'values': [v.get('Value1') for v in m.get('PredefinedValues') or []],
                             'default_value': ((cur or {}).get('Data') or {}).get('Value1'), 'kind': 'property'})
        playlist = next((x for x in modes_fm['playlists'] if x.get('GameModeTag') == tag), None)
        reg_modes[tag] = {
            'id': tag, 'property_id (TagToModeMap)': p['mode_property_id (TagToModeMap)'],
            'display_name': p['text']['FriendlyName'], 'description': p['text']['Description'], 'rules_text': p['text']['RulesFormat'],
            'rules_tokens': {x['Token']: x['PropertyId'] for x in base.get('RulePairs') or []},
            'menu_order': p.get('menu_order (TnOnlinePlaylistManager.Playlists)'),
            'playlist': {k: playlist.get(k) for k in ('section', 'PlaylistId', 'VisibleInMenu', 'DisplayName')} if playlist else None,
            'settings_class': 'TransGame.TnOnlineGameSettings' + tag, 'public_settings_class': 'TransGame.TnOnlineGameSettings%sPublic' % tag,
            'game_class': V(e, 'GameClass'), 'lobby_game_class': V(e, 'LobbyGameClass'), 'lobby_map': V(e, 'LobbyMapName'),
            'team_type': V(e, 'TeamType'), 'players': {'NumRequiredPlayers': V(e, 'NumRequiredPlayers'),
                                                      'NumPublicConnections': V(pub, 'NumPublicConnections')},
            'TimeLimits_seconds': V(e, 'TimeLimits'), 'settings': settings, 'rules_classes': V(e, 'Rules'),
            'stats_writers': V(pub, 'StatsWriters'),
            'icon': p['icon'], 'hud_score_panel': p['hud_score_panel (Hud_GFX export, name-based HIGH)'],
            'loading_tips': {'source': 'TnOnlineGameSettings%s.EngageText' % tag,
                             'unique': p['loading_tips (EngageText, de-duplicated; base tips in frontend_loading.json)'],
                             'array_length': len(V(e, 'EngageText') or [])},
            'announcer': p['announcer'], 'music': p['music'], 'game_type_message': p['game_type_message'],
            'objective_presentation': OBJ_PRES.get(tag, {}),
            'menu_visible': bool(playlist and str(playlist.get('VisibleInMenu')).lower() == 'true'),
            'confidence': CONF + ' (settings CDOs, TransGame.int, playlists, message classes)'}
    reg_maps = []
    for m in maps_cat['maps']:
        r = {'internal_name': m['MapFilename'], 'MapId': m['MapId'], 'PresenceId': m['PresenceId'], 'menu_order': m['ini_order'],
             'display_name': m['FriendlyName'], 'description': m['Description'], 'Faction': m['Faction'],
             'DlcId': 'not authored (engine default 0; playlists list ContentIds=(0))',
             'preview': {'ImagePath': m['ImagePath'], 'png': m['thumbnail_png'], 'inherited_default': m['image_inherited_default'],
                         'unavailable_image': 'UI_LevelThumbnails_p.LevelUnavailable'},
             'supported_modes': m['CompatibleGameTypes'], 'cooked': m.get('cooked'),
             'family_prefix': m['family_prefix (MP_<prefix>_)'],
             'loading_screen': 'shared: LoadScreen_GFX title = mode FriendlyName, text = UIText.LoadScreen.LoadingMap ("in `m") '
                               'with `m = this display_name; no per-map loading art (loading_handoff.json)',
             'confidence': m['confidence']}
        if m.get('cooked'):
            pk = m['packages']
            deps = m['source_package_dependencies (cooked copies inside the level files, by object count)']
            r.update({
                'packages': {'persistent': pk['base'], 'streamed': [s['PackageName'] for s in pk['streamed_levels (LevelStreaming objects)']],
                             'companions': pk['companions (_LM / _LOC)'], 'uncompressed_bytes': pk['uncompressed_bytes']},
                'audio': {'audio_sublevel': [s['PackageName'] for s in pk['streamed_levels (LevelStreaming objects)'] if 'audio' in (s['PackageName'] or '').lower()],
                          'level_sound_banks': sorted(d for d in deps if d.startswith('BL_LVL_MP')),
                          'announcer_set': m['world_info']['AnnouncerSoundEventSet']},
                'localization': {'names': 'TransGame.int/.FRA [%s TnDataProvider_MapInfo] FriendlyName' % m['MapFilename'],
                                 'packages': [c for c in pk['companions (_LM / _LOC)'] if '_LOC_' in c]},
                'players': {'mode_actors': m['mode_actors']},
                'world_info': m['world_info']})
            if m.get('reference_implementation'): r['reference_implementation'] = m['reference_implementation']
        reg_maps.append(r)
    return reg_modes, reg_maps

OBJ_PRES = {
    'CTF': {'hud_observer': 'TransGame.TnHudDataObserverSingleFlagCTF', 'messages': 'TransGame.TnCTFMessage (attacker/defender lines)',
            'world_actors': ['TnGameObjectivePickupFactoryFlag', 'TnFlagCapturePoint'], 'marker': 'TnObjectiveMarkerTypeTransformerVersus'},
    'DOM': {'hud_observer': 'TransGame.TnHudDataObserverDominationCapture (TnHUD.TemporaryObserverClasses)',
            'messages': 'TransGame.TnDominationMessage (capturing/captured A-E)', 'world_actors': ['TnDominationPoint'],
            'marker': 'TnObjectiveMarkerTypeDomination (UI_HudMarkers_p.MPMarkerDominationNode_MAT, Capture/Defend labels)'},
    'EXT': {'hud_observer': 'TransGame.TnHudDataObserverBombDefuseTimer (TnHUD.TemporaryObserverClasses)',
            'world_actors': ['TnGameObjectivePickupFactoryBomb', 'TnBombPlantPoint']},
    'KOTH': {'world_actors': ['TnKingOfTheHillZone'], 'note': 'active zone ring = pTorus1_STAT (render_index)'},
    'TDM': {'note': 'no objective actors; score = kills (TnGameRules_ScoreKillsTDM)'},
    'DM': {'note': 'no objective actors; score = kills (TnGameRules_ScoreKillsDM)'}}

def main():
    gfx = J('frontend_gfx.json')['movies']; flow = J('frontend_flow.json'); loc = J('frontend_localization.json')
    audio = J('frontend_audio.json'); hud = J('frontend_hud.json'); pres = J('frontend_mode_presentation.json')
    modes_fm = J('frontend_modes.json'); maps_cat = J('mp_map_catalog.json'); loading = J('frontend_loading.json')
    for lv in flow['levels'].values():
        for f in lv.get('fscommands') or []: FSCMDS.add(f['fscommand'])
    mv = movie_records(gfx, loc, audio)
    sc = screens(flow, mv, hud)
    font_cfg = FE.loc_tables(FE.INT).get('GFxUI', {})
    write('frontend_package.json', OrderedDict([
        ('generated_by', GEN),
        ('sources', ['manifests/frontend_*.json', 'manifests/mp_map_catalog.json', 'authored.db / inventory.db',
                     DECOMP + ' (TnMoviePlayer, TnOnlineGameSettingsBase, TnGame, TnGameReplicationInfoGameLobby, '
                              'TnDataStore_MenuItems, TnDataProvider_MapInfo, TnPlayerController) - read-only']),
        ('screen_order', list(sc)),
        ('screens', sc),
        ('movies', mv),
        ('font_library', {'GFxUI.int [FontLib]': font_cfg.get('FontLib'), 'GFxUI.int [Fonts] (alias -> face)': font_cfg.get('Fonts'),
                          'movie': 'UI_GFxFonts_p/Fonts_EFIGS', 'embedded_faces': gfx['UI_GFxFonts_p/Fonts_EFIGS']['fonts'],
                          'imported_as': '../_Shared/Fonts/gfxfontlib.swf', 'canvas_fonts': ['UI_TransEngineFonts_p.MarkerFont',
                                                                                              'UI_TransEngineFonts_p.SubtitleFont'],
                          'confidence': CONF}),
        ('config', {'boot_map': flow['startup_config (Xe-TransEngine.ini [URL], CONFIRMED)'],
                    'loading_movie': flow['loading_movie_config (Xe-TransGame.ini [LoadingMovie])'],
                    'movie_settings': flow['movie_settings (Engine.MovieSettings)'],
                    'gfx_external_interfaces': J('frontend_bindings.json')['source']}),
        ('handoffs', {'registry': 'mp_registry.json', 'loading': 'loading_handoff.json', 'hud': 'hud_handoff.json',
                      'RE (unresolved calls)': '../frontend_re_handoff.json'})]))
    reg_modes, reg_maps = registry(maps_cat, modes_fm, pres, None)
    gl = A.values('TransGame.Default__TnGameReplicationInfoGameLobby')
    write('mp_registry.json', OrderedDict([
        ('generated_by', GEN),
        ('selection_rules', {
            'compatible_maps (TnGameReplicationInfoGameLobby.GetCompatibleMaps)': 'every MapInfo provider whose CompatibleGameTypes '
                'contains the mode tag and whose IsProviderDisabled() is false',
            'IsProviderDisabled (TnDataProvider_MapInfo)': '!HasRequiredAssets() (native: shipped behaviour excludes uncooked maps - '
                'HIGH) or !GRI.MapCanBePlayed(map) (DlcId in the selected playlist ContentIds; all shipped playlists ContentIds=(0))',
            'rotation (SelectRandomMap/RandomMap)': 'random different compatible map after each match (PreviousMapId + RandRange(1,n)) mod n',
            'map_name_lookup (TnDataStore_MenuItems)': 'ConvertMapIdToFriendlyName / ConvertMapIdToMapFilename / GetMapFaction by MapId',
            'default_quickmatch_playlist': modes_fm['playlist_manager'].get('DefaultQuickmatchPlaylistId'),
            'confidence': CONF + ' (script decomp, read-only)'}),
        ('modes', reg_modes),
        ('maps', reg_maps),
        ('shared_presentation', {'announcer_voices': pres['announcer_voices (TnAnnouncer: Team0/Team1 DialogCharacter)'],
                                 'messages': pres['shared_messages'], 'lobby': {k: gl.get(k) for k in ('LowCountdownTickSound',
                                                                                                        'PlayerJoinedSound', 'PlayerLeftSound')}})]))
    write('loading_handoff.json', loading_handoff(gfx, flow, loading, pres, reg_maps))
    write('hud_handoff.json', hud_handoff(hud, gfx, mv))

# ------------------------------------------------------------------ loading
def loading_handoff(gfx, flow, loading, pres, reg_maps):
    ls = gfx['UI_GFxLoading_p/LoadScreen_GFX']
    probe = flow['movie_probe (ffprobe; content CONFIRMED where inspected)']
    sc = gfxscan.scan(os.path.join(ROOT, ls['file']))
    motif = {sid: {'frames': sc['sprites'][sid]['frames'], 'labels': sc['sprites'][sid]['labels'],
                   'bitmaps': [{'image': b, 'png': rel(os.path.join(CONTENT, 'UI_GFxLoading_p', b + '.png'))}
                               for b in sorted(gfxscan.symbol_bitmaps(sc, sid))]}
             for sid in (141, 140, 18, 136) if sid in sc['sprites']}
    base_tips = loading['loading_tips (TnOnlineGameSettingsBase.EngageText, INT)']
    per_mode = {t: {'name': m['text']['FriendlyName'],
                    'tips_unique': m['loading_tips (EngageText, de-duplicated; base tips in frontend_loading.json)'],
                    'note': ('all 26 array entries are the same sentence in the shipped data: every loading screen for this mode '
                             'shows that one tip' if len(m['loading_tips (EngageText, de-duplicated; base tips in frontend_loading.json)']) == 1
                             else None)}
                for t, m in pres['modes'].items()}
    return OrderedDict([
        ('generated_by', GEN),
        ('script_source', DECOMP + '/TransGame.TnMoviePlayer.txt (read-only); callers TnGame.ServerTravelToMap, '
                          'TnPlayerController.PreClientTravel'),
        ('decision (TnMoviePlayer.StartLoadingMovie(PendingURL))', [
            {'when': 'URL option Game contains "TnPartyLobbyGame"', 'title': '', 'text': '', 'tips': 'TnOnlineGameSettingsBase.EngageText'},
            {'when': 'Game contains "TnGameLobbyGame"', 'title': '', 'text': '', 'tips': 'TnOnlineGameSettingsBase.EngageText'},
            {'when': 'MapId option present (match load)', 'title': 'FriendlyName of the settings class for GameModeTag '
                     '(UIDataStore_OnlineGameSettings.GetSettingsClassForName) e.g. "Team Deathmatch"',
             'text': 'Localize("LoadScreen","LoadingMap","UIText") = "in `m" with `m = TnDataStore_MenuItems.ConvertMapIdToFriendlyName(MapId) '
                     'e.g. "in Streets"',
             'tips': 'settings class EngageText (falls back to base when the class is not found)'},
            {'when': 'otherwise', 'title': '', 'text': '', 'tips': 'TnOnlineGameSettingsBase.EngageText'},
            {'when': 'campaign checkpoint load', 'title': '$UIText.LoadScreen.ResumeAutobot|ResumeDecepticon', 'text': '',
             'tips': 'TnOnlineGameSettingsCP.EngageText'}]),
        ('delivery_to_movie', {
            'SetLevelText': 'HmMoviePlayer.AddDeferredMethod("_global.SetLevelText", [Title, Message]) -> AS stores '
                            'LevelTitle = Title.toUpperCase(), LevelDescription = Message, calls levelInfo_mc.UpdateLevelInfo',
            'AddEngageText': 'called 3 times, each with EngageText[RandomInt(len)] (independent picks, repeats possible) -> AS pushes to '
                             'EngageTextArray, engageText_mc.UpdateEngageText',
            'confidence': CONF + ' (script + LoadScreen_GFX bytecode)'}),
        ('movies', {
            'gfx_loading_screen': {'movie': 'UI_GFxLoading_p/LoadScreen_GFX', 'file': ls['file'],
                                   'set_by': 'UI_FrontEnd_m Kismet SeqAct_SetLoadingMovieFilename(Filename = SeqVar_String '
                                             '"UI_GFxLoading_p.LoadScreen_GFX") on entering the front end and on SeqEvent_PreGameplaySetup',
                                   'native': 'TnOnlineActionScriptBindingNative.SetLoadingMovieFilename (RE)'},
            'video_default': {'config': '[LoadingMovie] DefaultFileName=TF_LoadingScreen', 'files': {
                m: probe.get(m) for m in probe if m.startswith('TF_LoadingScreen')}},
            'alpha_overlay': {'config': '[LoadingMovie] AlphaFileName=UI_GFxLoading_p.LoadScreenAlpha_GFX',
                              'movie': 'UI_GFxLoading_p/LoadScreenAlpha_GFX', 'exports': gfx['UI_GFxLoading_p/LoadScreenAlpha_GFX']['exports'],
                              'video': probe.get('LoadingScreenAlpha.mkv')},
            'initial_startup': {'config': '[LoadingMovie] InitialStartupFileName=TF_InitialStartup',
                                'files': {m: probe.get(m) for m in probe if m.startswith('TF_InitialStartup')}},
            'which_plays_when': 'Kismet points the loading movie at LoadScreen_GFX once the front end is up, so front-end -> lobby -> '
                                'match loads use the GFx screen; DefaultFileName (TF_LoadingScreen video) is the configured default '
                                'before that. Composition/selection inside HmMoviePlayer is native (RE) - HIGH'}),
        ('loadscreen_gfx_layout', {
            'root': [{'instance': 'mc_loadingMotifAnim', 'sprite': 141}],
            'mc_levelInfo': {'title_txt': ls['text_fields'].get('2'), 'description_txt': ls['text_fields'].get('3'),
                             'animation': 'alpha ease-in of title/description (interp "easeout")'},
            'mc_engageText': {'engage_txt': ls['text_fields'].get('5')},
            'loading_label': ls['text_fields'].get('137'),
            'fonts': ls['fonts'], 'font_note': 'title/description/tips use embedded "Distilla Cyrillic Regular"',
            'spinner_motif (sprite timelines + ring textures)': motif,
            'gradients_and_font_textures': [p for p in ls['images_extracted']],
            'confidence': CONF}),
        ('text', {'$UIText.LoadScreen': FE.loc_tables(FE.INT).get('UIText', {}).get('LoadScreen'),
                  'FRA': FE.loc_tables(FE.FRA).get('UIText', {}).get('LoadScreen')}),
        ('tips', {'base (TnOnlineGameSettingsBase.EngageText)': base_tips, 'per_mode': per_mode}),
        ('map_names (MapId -> display name used on the loading screen)', {
            str(m['MapId']): {'INT': m['display_name']['INT'], 'FRA': m['display_name']['FRA'], 'map': m['internal_name'],
                              'cooked': m['cooked']} for m in reg_maps}),
        ('audio', {'loading_music': 'none authored (no Kismet/script loading music)',
                   'video_audio': {m: (probe.get(m) or {}).get('audio') for m in probe if m.startswith(('TF_Loading', 'LoadingScreenAlpha', 'TF_Initial'))},
                   'gfx_sounds': gfx['UI_GFxLoading_p/LoadScreen_GFX']['ui_sound_cues_named']}),
        ('example (vertical slice)', {
            'url': 'MP_IAC_Streets_Base_m?MapId=508?Game=TransContent.TnVersusGame?GameModeTag=TDM...',
            'title': 'TEAM DEATHMATCH (AS upper-cases)', 'text': 'in Streets',
            'tips': '3 picks from TnOnlineGameSettingsTDM.EngageText = "Don\'t get fooled. Decoy Traps can be destroyed by shooting them."',
            'confidence': CONF + ' (composition of the rules above)'})])

# ------------------------------------------------------------------ HUD
def hud_handoff(hud, gfx, mv):
    h = gfx['UI_GFxHud_p/Hud_GFX']
    bm = h['symbol_bitmaps (export -> bitmaps drawn via placements / shape bitmap fills)']
    def syms(rx):
        return sorted(e for e in h['exports'] if re.search(rx, e, re.I))
    def with_bitmaps(names):
        return {n: bm.get(n) for n in names}
    obs = hud['data_observers']
    def observers(rx):
        return [{'class': o['class'], 'callback': o['callback'], 'props': o['props']} for o in obs
                if re.search(rx, (o['class'] or '') + (o['callback'] or ''), re.I)]
    cbs = hud['hud_callbacks (TnHUD properties)']
    groups = OrderedDict([
        ('health', r'health|segment|downed'), ('overshield', r'overshield'), ('ammo_reload', r'ammo|clip|reserve|jam|reload'),
        ('weapon', r'weapon|grenade'), ('crosshair', r'reticule|crosshair|spread|lockon|lock_on|rangefinder'), ('heat', r'heat'),
        ('score_team', r'score|point|team'), ('clock', r'time|timer|clock|countdown|wave'),
        ('kills_deaths', r'kill|death|streak|obituar'), ('objectives', r'objective|marker|capture|bomb|flag|domination'),
        ('abilities', r'abilit|cooldown|buff'), ('messages', r'message|announc|tutorial')])
    elements = OrderedDict()
    for g, rx in groups.items():
        s = syms(rx)
        elements[g] = {'hud_symbols': with_bitmaps(s),
                       'observers (script -> AS)': observers(rx),
                       'tnhud_callbacks': {k: v for k, v in cbs.items() if re.search(rx, k + v, re.I)},
                       'text': {k: v for k, v in (hud['text (UIText.int sections)'].get('Hud') or {}).items() if re.search(rx, k, re.I)}}
    elements['objectives']['canvas_markers'] = hud['objective_marker_types']
    elements['objectives']['marker_textures'] = hud['hud_marker_textures (UI_HudMarkers_p)']
    sb = 'UI_GFxInGameStats_p/InGameStats_GFX'
    return OrderedDict([
        ('generated_by', GEN), ('scope', 'authored inputs and dependencies only; values are driven by script/native (RE)'),
        ('movies', {k: {'instance': v['instance'], 'movie': (v['instance'] or '').replace('.', '/').rsplit('_1', 1)[0]}
                    for k, v in hud['movies'].items()}),
        ('hud_movie', {'movie': 'UI_GFxHud_p/Hud_GFX', 'file': h['file'], 'fonts': h['fonts'], 'font_aliases': h['font_aliases'],
                       'imports': mv['UI_GFxHud_p/Hud_GFX']['imports (shared libraries)'],
                       'exports': len(h['exports']), 'bitmap_backed_exports': len(bm),
                       'uncooked_bitmaps': sorted({x['image'] for v in bm.values() for x in v if not x['png']}),
                       'text_fields': len(h['text_fields'])}),
        ('elements', elements),
        ('scoreboard', {'movie': sb, 'exports': gfx[sb]['exports'], 'text_fields': gfx[sb]['text_fields'],
                        'callbacks_defined': gfx[sb]['_global_callbacks_defined (called from script/native)'],
                        'submovie_player_list': 'UI_GFxPlayerList_p/PlayerList_GFX (loaded by PartyLobby; defines UpdatePlayerListData)',
                        'localization_keys': gfx[sb]['localization_keys']}),
        ('match_flow_movies', {k: hud['movies'][k] for k in ('GameStartUI', 'PauseUI', 'SpectatingUI', 'EndGameUI') if k in hud['movies']}),
        ('end_of_match', {'movie': 'UI_GFxEndGameStats_p/EndGameStats_GFX', 'exports': gfx['UI_GFxEndGameStats_p/EndGameStats_GFX']['exports'],
                          'localization_keys': gfx['UI_GFxEndGameStats_p/EndGameStats_GFX']['localization_keys'],
                          'messages': 'TnVersusGameOverMessage (mp_registry shared_presentation)'}),
        ('kill_feed_icons (death_<DamageType> bitmaps)', with_bitmaps(syms(r'^death_'))),
        ('unresolved_callbacks', hud['unresolved_callbacks (no movie in this set defines it)']),
        ('message_colors', hud['message_colors (TnMessageTextColors)']),
        ('ui_sounds', hud['ui_sound_cues_named_by_hud_movies']),
        ('confidence', CONF + ' (authored objects + movie structure); element grouping by name = HIGH')])

if __name__ == '__main__':
    main()
