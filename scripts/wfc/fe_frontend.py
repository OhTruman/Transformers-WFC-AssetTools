"""WFC frontend / game-flow authored data (startup -> main menu -> multiplayer -> map/mode -> loading) - manifests only.

Outputs (AssetTools/manifests/):
  frontend_flow.json          startup config, movie files, the UI levels' Kismet (UI_FrontEnd_m, capture vignette, lobbies,
                              campaign lobby, customization) with movie order, GFx open/close, fscommands, music/ambience
  frontend_gfx.json           every Scaleform movie under content/UI_*: exports, sprites + frame labels, text fields, imports,
                              loaded .swf names, localization keys, AS-defined _global callbacks, HmInterface bridge calls,
                              UI sound names, input names, images, the cooked GFxMovie / GFxMovieInfo objects
  frontend_bindings.json      UnrealScript ActionScript-binding classes (GFxEngine ExternalInterfaceTypeNames): interface
                              name + function exports = the native/script side of every bridge call (handed to RE)
  frontend_maps.json          every TnDataProvider_MapInfo (TransLevels.ini) with localized names (INT/FRA), thumbnails,
                              compatible modes, ids, ordering, cooked-package presence
  frontend_modes.json         game modes (GameModeInfo), playlists (TransPlaylists.ini), settings classes, localized names
  frontend_audio.json         UI / frontend / lobby music, ambience and UI sound cues (graphs + WAV files)
  frontend_loading.json       loading presentation: config, movies, LoadScreen GFx, tips (EngageText), Kismet hooks
  frontend_localization.json  frontend-relevant localization sections (INT + FRA) and every $key referenced by the GFx movies
Every record carries a confidence (CONFIRMED / HIGH CONFIDENCE / PARTIAL / UNKNOWN) and its source.
  python fe_frontend.py
"""
import glob, json, os, re, sys
from collections import Counter, defaultdict, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree, gfxscan, as2dis  # noqa: E402
from m03_common import write, CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import ROOT  # noqa: E402

CFG = os.path.join(ROOT, 'config')
INI = os.path.join(CFG, 'Coalesced_ini', 'TransGame', 'Config', 'Xenon', 'Cooked')
INT = os.path.join(CFG, 'Coalesced_int', 'TransGame', 'Localization', 'INT')
FRA = os.path.join(CFG, 'Coalesced_FRA', 'TransGame', 'Localization', 'FRA')
MOVIES = os.path.join(ROOT, 'movies')
CONTENT = os.path.join(ROOT, 'content')
UI_LEVELS = ['UI_FrontEnd_m', 'UI_FrontEnd_capture_VIG_m', 'UI_PartyLobby_m', 'UI_Lobby_m', 'UI_CampaignLobby_m',
             'UI_CharacterCustomization_m']
UI_CUE_PKGS = ('BL_HUD_INTERFACE', 'BL_LVL_HUD_INTERFACE')

def rel(p): return os.path.relpath(p, ROOT).replace(os.sep, '/')

# ------------------------------------------------------------------ ini / int
def read_ini(path):
    """[section] -> OrderedDict key -> value or list (repeated keys)."""
    out = OrderedDict(); sec = None
    if not os.path.exists(path): return out
    data = open(path, 'rb').read()
    if data[:2] in (bytes([0xFF, 0xFE]), bytes([0xFE, 0xFF])): text = data.decode('utf-16')
    else:
        try: text = data.decode('utf-8')
        except UnicodeDecodeError: text = data.decode('cp1252')
    for raw in text.splitlines():
        l = raw.rstrip('\r\n')
        if not l.strip() or l.lstrip().startswith(';'): continue
        m = re.match(r'^\[(.+)\]\s*$', l)
        if m: sec = out.setdefault(m.group(1), OrderedDict()); continue
        if sec is None or '=' not in l: continue
        k, v = l.split('=', 1); k = k.strip(); v = v.strip()
        if k in sec:
            if not isinstance(sec[k], list): sec[k] = [sec[k]]
            sec[k].append(v)
        else:
            sec[k] = v
    return out

def loc_tables(lang_dir):
    t = {}
    for f in sorted(glob.glob(os.path.join(lang_dir, '*.*'))):
        t[os.path.splitext(os.path.basename(f))[0]] = read_ini(f)
    return t

# ------------------------------------------------------------------ GFx
IFACES, BINDFUNCS = {}, {}

_ELSE = {}
def elsewhere(fn):
    if fn not in _ELSE:
        _ELSE[fn] = [r[0] for r in objtree.inv().execute(
            "SELECT DISTINCT opath FROM exports WHERE class='Function' AND package IN ('TransGame','HM_Engine','Engine','GFxUI') "
            "AND opath LIKE ?", ('%.' + fn,)).fetchall()][:6]
    return _ELSE[fn]

def load_bindings():
    inv = objtree.inv()
    for cn in A.values('GFxUI.Default__GFxEngine').get('ExternalInterfaceTypeNames') or []:
        pk, c = cn.split('.')
        cdo = '%s.Default__%s' % (pk, c)
        iname = A.values(cdo).get('InterfaceName') if A.get(cdo) else None
        BINDFUNCS[cn] = {r[0].split('.')[-1] for r in inv.execute(
            "SELECT opath FROM exports WHERE package=? AND class='Function' AND opath LIKE ?", (pk, cn + '.%')).fetchall()}
        if iname: IFACES[iname] = cn

def gfx_record(path, ue):
    s = gfxscan.scan(path)
    ex = s['exports']
    sprites = {str(k): {'export': ex.get(k), 'frames': v['frames'], 'labels': v['labels'],
                        'instances': sorted({p.get('name') for p in v['places'] if p.get('name')})}
               for k, v in s['sprites'].items() if ex.get(k) or v['labels']}
    strings = [x for a in s['action_strings'] for x in a['strings']]
    # _global callbacks defined by the movie (script/native calls into AS): DefineFunction assigned to _global.<name>
    # outside the __Packages class definitions; AS2 class constructors (__Packages.*) are excluded
    classes = {v.split('.', 1)[1] for v in ex.values() if v.startswith('__Packages.')} | {v.split('.')[-1] for v in ex.values() if v.startswith('__Packages.')}
    callbacks = set()
    for code in ('root',) + tuple(s['sprites'].keys()):
        if code != 'root' and str(ex.get(code, '')).startswith('__Packages.'): continue
        try:
            blocks = as2dis.actions_for(path, code, False)
        except Exception:
            continue
        for blk in blocks:
            try:
                lines = as2dis.dis(blk)
            except Exception:
                continue
            for i, l in enumerate(lines):
                if 'DefineFunction' not in l or i < 1: continue
                m = re.findall(r"Push '([A-Za-z_][\w]*)'", lines[i - 1])
                if not m or m[-1] in classes: continue
                if any("'_global'" in x for x in lines[max(0, i - 3):i]):
                    callbacks.add(m[-1])
    # AS -> script bridge: flash.external.ExternalInterface.call("<Interface>.<Method>")
    bridge = sorted({x for x in strings if re.fullmatch(r'[A-Z][A-Za-z]+\.[A-Za-z_]\w*', x) and x.split('.')[0] in IFACES})
    swf = sorted({x for x in strings if re.search(r'\.(swf|gfx)$', x, re.I)})
    # $File.Section.Key localization keys, also inside comma-separated prompt specs; $Name = font alias (gfxfontlib)
    pool = strings + [tf.get('initial_text') or '' for tf in s['text_fields'].values()]
    lockeys = sorted({m for x in pool for m in re.findall(r'\$[A-Za-z]\w*\.\w+\.\w+', x)})
    font_aliases = sorted({x for x in pool if re.fullmatch(r'\$[A-Za-z]\w*', x)})
    ui_sounds = sorted({x for x in strings if re.fullmatch(r'[A-Z][A-Z0-9_]{3,}', x) and
                        A.con().execute("SELECT 1 FROM objects WHERE class='SoundCue' AND (opath=? OR opath=?)",
                                        ('BL_HUD_INTERFACE.' + x, 'BL_LVL_HUD_INTERFACE.' + x)).fetchone()})
    inputs = sorted({x for x in strings if re.fullmatch(r'(XboxTypeS_\w+|Gamepad\w+|ButtonA|ButtonB|ButtonX|ButtonY|START|BACK|'
                                                         r'Accept|Cancel|Back|Select|LB|RB|LT|RT|DPad\w*|onPress|onRelease|'
                                                         r'onRollOver|onRollOut|onKeyDown|onKeyUp)', x)})
    fs = sorted({x for x in strings if x in ('fscommand',) or x.startswith('enter') or x.startswith('start')})
    d = os.path.dirname(path); base = os.path.splitext(os.path.basename(path))[0]
    imgs = sorted(rel(p) for p in glob.glob(os.path.join(d, base + '_*.png')))
    return {'file': rel(path), 'signature': s['signature'], 'swf_version': s['version'],
            'stage': None, 'exports': sorted(ex.values()), 'sprite_count': len(s['sprites']),
            'sprites_exported_or_labelled': sprites, 'root_labels': s['root']['labels'],
            'root_instances': sorted({p.get('name') for p in s['root']['places'] if p.get('name')}),
            'text_fields': {str(k): v for k, v in s['text_fields'].items()},
            'imports': s['imports'], 'fonts': s['fonts'], 'loads_movies': swf, 'localization_keys': lockeys, 'font_aliases': font_aliases,
            '_global_callbacks_defined (called from script/native)': sorted(callbacks),
            'bridge_calls (ExternalInterface.call)': [{'call': b, 'binding_class': IFACES[b.split('.')[0]],
                                                       'function_exported': b.split('.', 1)[1] in BINDFUNCS.get(IFACES[b.split('.')[0]], ()),
                                                       **({} if b.split('.', 1)[1] in BINDFUNCS.get(IFACES[b.split('.')[0]], ()) else
                                                          {'same_name_function_elsewhere': elsewhere(b.split('.', 1)[1])})}
                                                      for b in bridge],
            'as2_classes': sorted(v for v in ex.values() if v.startswith('__Packages.')),
            'ui_sound_cues_named': ui_sounds, 'input_names': inputs, 'fscommand_like_strings': fs,
            'images_extracted': imgs, 'ue_objects': ue,
            'confidence': CONF + ' (tags/bytecode of the cooked movie); behaviour of callbacks belongs to script/native (RE)'}

def ue_movie_objects():
    d = A.con(); out = defaultdict(dict)
    for o, c in d.execute("SELECT opath, class FROM objects WHERE class IN ('GFxMovieInfo', 'GFxMovie')").fetchall():
        base = o.rsplit('.', 1)[-1]
        if c == 'GFxMovie' and base.endswith('_1'): base = base[:-2]
        v = A.values(o)
        key = o.split('.')[0] + '/' + base
        if c == 'GFxMovieInfo':
            out[key]['movie_info'] = {'object': o, 'SourceFile': v.get('SourceFile'), 'bUsesFontlib': v.get('bUsesFontlib'),
                                      'References': [r for r in v.get('References') or [] if r],
                                      'UserReferences': [r for r in v.get('UserReferences') or [] if r]}
        else:
            out[key]['movie_instance'] = {'object': o, **{k: v.get(k) for k in ('ExternalTextures', 'CaptureKeys', 'FocusIgnoreKeys',
                                          'ExternalInterfaces', 'TimingMode', 'RenderTextureMode', 'Depth', 'bGammaCorrection',
                                          'IgnoreGlobalCapture') if v.get(k) not in (None, [], '')}}
    return out

# ------------------------------------------------------------------ Kismet
def node(o):
    r = A.get(o); p = r['props'] or {}
    outs = {ol.get('LinkDesc'): [l['LinkedOp'].rsplit('.', 1)[-1] for l in ol.get('Links') or [] if l.get('LinkedOp')]
            for ol in p.get('OutputLinks') or []}
    var = {vl.get('LinkDesc'): [((A.get(x) or {}).get('props') or {}).get('ObjValue') or x.rsplit('.', 1)[-1]
                                for x in vl.get('LinkedVariables') or [] if x] for vl in p.get('VariableLinks') or []}
    keep = {k: v for k, v in p.items() if k not in ('InputLinks', 'OutputLinks', 'VariableLinks', 'ParentSequence', 'ObjPosX', 'ObjPosY',
                                                     'DrawWidth', 'DrawHeight', 'EventLinks', 'MaxWidth', 'ObjInstanceVersion',
                                                     'SequenceObjects', 'DefaultViewX', 'DefaultViewY', 'DefaultViewZoom')}
    return {'object': o.rsplit('.', 1)[-1], 'class': r['class'], 'authored': keep,
            'outputs': {k: v for k, v in outs.items() if v}, 'variables': {k: v for k, v in var.items() if v}}

def level_kismet(lv):
    ms = lv + '.TheWorld.PersistentLevel.Main_Sequence'
    if not A.get(ms): return []
    acc = []
    def walk(seq):
        for o in (A.get(seq)['props'] or {}).get('SequenceObjects') or []:
            if not o or not A.get(o): continue
            n = node(o); acc.append(n)
            if n['class'] == 'Sequence': walk(o)
    walk(ms)
    return acc

def movie_order(nodes):
    """Follow SeqAct_MoviePlayer 'Stopped' links from the movie triggered by an fscommand."""
    by = {n['object']: n for n in nodes}
    seqs = []
    for n in nodes:
        if n['class'] != 'GFxEvent_FsCommand': continue
        first = [x for x in n['outputs'].get('Out', []) if by.get(x, {}).get('class') == 'SeqAct_MoviePlayer']
        for f in first:
            chain, cur = [], f
            while cur and cur not in chain:
                chain.append(cur)
                nxt = [x for x in by[cur]['outputs'].get('Stopped', []) if by.get(x, {}).get('class') == 'SeqAct_MoviePlayer']
                cur = nxt[0] if nxt else None
            after = by[chain[-1]]['outputs'].get('Stopped', [])
            seqs.append({'trigger_fscommand': n['authored'].get('FsCommand'), 'trigger_movie': n['authored'].get('Movie'),
                         'movies': [by[c]['authored'].get('MovieName') for c in chain], 'player_actions': chain,
                         'after_last_movie': [{'op': x, 'class': by.get(x, {}).get('class')} for x in after]})
    return seqs

# ------------------------------------------------------------------ audio
def cue_rec(c):
    q = A.cue(c)
    return {'cue': c, 'root': q.get('root'), 'category': q.get('category'),
            'waves': [{'wave': w['wave'], 'wav': w['wav'], 'duration': w['duration']} for w in q.get('waves', [])],
            'missing': q.get('missing', False),
            'authored_silent': (not q.get('missing')) and not q.get('waves'),
            'note': 'cue authored with no wave (silent) - CONFIRMED' if (not q.get('missing') and not q.get('waves')) else None}

def main():
    ini = {f: read_ini(os.path.join(INI, f)) for f in ('Xe-TransEngine.ini', 'Xe-TransGame.ini', 'Xe-TransUI.ini',
                                                       'TransLevels.ini', 'TransPlaylists.ini')}
    INTt = loc_tables(INT); FRAt = loc_tables(FRA) if os.path.isdir(FRA) else {}
    movies = sorted(os.path.basename(p) for p in glob.glob(os.path.join(MOVIES, '*.mkv')))
    inv = objtree.inv()

    # ---------------- flow
    eng = ini['Xe-TransEngine.ini']; gm = ini['Xe-TransGame.ini']
    flow = {'generated_by': 'AssetTools/scripts/wfc/fe_frontend.py',
            'startup_config (Xe-TransEngine.ini [URL], CONFIRMED)': {k: (eng.get('URL') or {}).get(k) for k in ('Map', 'LocalMap', 'TransitionMap')},
            'movie_settings (Engine.MovieSettings)': eng.get('Engine.MovieSettings'),
            'loading_movie_config (Xe-TransGame.ini [LoadingMovie])': gm.get('LoadingMovie'),
            'frontend_game_class': {'TransContent.TnFrontEndGame': gm.get('TransContent.TnFrontEndGame'),
                                    'TransContent.TnPartyLobbyGame': gm.get('TransContent.TnPartyLobbyGame')},
            'movie_files': {m: rel(os.path.join(MOVIES, m)) for m in movies},
            'levels': {}}
    for lv in UI_LEVELS:
        if not A.con().execute('SELECT 1 FROM objects WHERE package=? LIMIT 1', (lv,)).fetchone():
            flow['levels'][lv] = {'present_in_authored_db': False}; continue
        nodes = level_kismet(lv)
        cls = Counter(n['class'] for n in nodes)
        flow['levels'][lv] = {
            'kismet_class_counts': dict(cls),
            'movie_sequences': movie_order(nodes),
            'gfx_open': [n for n in nodes if n['class'] in ('GFxAction_OpenMovie', 'GFxAction_CloseMovie', 'TnSeqAct_OpenFrontEnd')],
            'fscommands': [{'fscommand': n['authored'].get('FsCommand'), 'movie': n['authored'].get('Movie'), 'outputs': n['outputs']}
                           for n in nodes if n['class'] == 'GFxEvent_FsCommand'],
            'music': [n['authored'].get('MusicTrack') for n in nodes if n['class'] == 'SeqAct_PlayMusic'],
            'sounds': [{'cue': n['authored'].get('PlaySound') or n['authored'].get('SoundToPlay'), 'class': n['class'],
                        **{k: n['authored'].get(k) for k in ('FadeInTime', 'FadeOutTime', 'DelayMin', 'DelayMax', 'ObjComment') if k in n['authored']}}
                       for n in nodes if n['class'] in ('SeqAct_PlaySound', 'SeqAct_PlayPlayerPositionalSound')],
            'events': [n for n in nodes if n['class'].startswith('SeqEvent') or n['class'].startswith('GFxEvent')],
            'nodes': nodes, 'confidence': CONF + ' (authored Kismet graph); runtime of each SeqAct is engine/script'}
    fe = flow['levels'].get('UI_FrontEnd_m', {})
    flow['summary'] = {
        'boot': 'engine loads Map=UI_FrontEnd_m (Xe-TransEngine.ini [URL]); TnSeqAct_OpenFrontEnd -> SeqAct_InstallGame -> '
                'GFxAction_OpenMovie UI_GFxFrontEnd_p.MovieLoader_GFX_1',
        'movie_sequence': (fe.get('movie_sequences') or [{}])[0].get('movies'),
        'skip_path': 'MovieLoader fscommand "enterFrontEnd" triggers the same front-end setup without the movies; which one '
                     'MovieLoader sends is decided in its ActionScript via the Game bridge (HasWatchedIntroMovie) - see '
                     'frontend_gfx.json MovieLoader_GFX and frontend_bindings.json TnGameActionScriptBinding (RE)',
        'main_menu': 'FrontEnd_GFX (menus mc_menuPressStart / mc_menuMain360 / mc_menuOnline / mc_menuSolo / mc_menuCampaign ...); '
                     'fscommand "startMainMenuCamera" -> orbit camera matinee',
        'multiplayer': 'party lobby UI_PartyLobby_m + PartyLobby_GFX, game lobby UI_Lobby_m + GameLobby_GFX (Online bridge: '
                       'PlayPlaylist / OpenPartyLobby / SetSelectedMapID / SubmitMapVeto ...)',
        'loading': 'see frontend_loading.json',
        'confidence': CONF + ' for the authored links; HIGH for the role descriptions'}
    write('frontend_flow.json', flow)

    # ---------------- gfx
    load_bindings()
    ue = ue_movie_objects()
    recs = {}
    for path in sorted(glob.glob(os.path.join(CONTENT, 'UI_*', '*.gfx'))):
        pkg = os.path.basename(os.path.dirname(path)); base = os.path.splitext(os.path.basename(path))[0]
        recs[pkg + '/' + base] = gfx_record(path, ue.get(pkg + '/' + base))
    write('frontend_gfx.json', {'generated_by': 'AssetTools/scripts/wfc/fe_frontend.py', 'movies': recs,
                                'notes': ['_global callbacks = functions the movie defines on _global; script/native invokes them '
                                          '(TnHUD-style CallbackBindingName or binding classes). Their call sites are RE scope.',
                                          'bridge_calls = ExternalInterface.call("<Interface>.<Method>") strings; Interface resolves '
                                          'to the binding class via its InterfaceName (frontend_bindings.json); function_exported '
                                          'tells whether that UnrealScript function exists on the binding class; when it does not, '
                                          'same_name_function_elsewhere lists script functions of that name (dispatch target is '
                                          'native/script - RE); none at all = UNKNOWN (possibly dead AS code)',
                                          'loads_movies: relative .swf names loaded at runtime (MovieLoader/menu loaders); '
                                          'they correspond to the cooked GFx movies of the same base name']})

    # ---------------- bindings
    names = A.values('GFxUI.Default__GFxEngine').get('ExternalInterfaceTypeNames') or []
    binds = {}
    for cn in names:
        pk, c = cn.split('.')
        cdo = '%s.Default__%s' % (pk, c)
        funcs = [r[0].split('.')[-1] for r in inv.execute("SELECT opath FROM exports WHERE package=? AND class='Function' AND opath LIKE ?",
                                                         (pk, cn + '.%')).fetchall()]
        binds[cn] = {'InterfaceName': A.values(cdo).get('InterfaceName') if A.get(cdo) else None, 'functions': funcs,
                     'class_cooked': A.get(cdo) is not None,
                     'confidence': CONF + ' (class + function exports); behaviour = UnrealScript/native (RE)'}
    write('frontend_bindings.json', {'generated_by': 'AssetTools/scripts/wfc/fe_frontend.py',
                                     'source': 'GFxUI.Default__GFxEngine.ExternalInterfaceTypeNames + TransGame/HM_Engine Function exports',
                                     'bindings': binds,
                                     'input_command_bindings (TnInputCommandToBindingMapper, prompts shown by the UI)':
                                         A.values('TransGame.Default__TnInputCommandToBindingMapper').get('InputCommandToKeyBindings')})

    # ---------------- maps
    tl = ini['TransLevels.ini']
    base = tl.get('TransGame.TnDataProvider_MapInfo') or {}
    tg_int = INTt.get('TransGame', {}); tg_fra = FRAt.get('TransGame', {})
    thumbs = {os.path.splitext(os.path.basename(p))[0]: rel(p) for p in glob.glob(os.path.join(CONTENT, 'UI_LevelThumbnails_p', '*.png'))}
    maps = []
    for order, (sec, v) in enumerate(tl.items()):
        if not sec.endswith(' TnDataProvider_MapInfo'): continue
        name = sec.split(' ')[0]
        if not name.upper().startswith('MP_'): continue
        img = v.get('ImagePath') or base.get('ImagePath')
        thumb = img.split('.')[-1] if img else None
        fn = v.get('MapFilename') or name
        cooked = inv.execute('SELECT package FROM packages WHERE lower(package)=lower(?)', (fn,)).fetchone()
        gt = v.get('CompatibleGameTypes'); gt = gt if isinstance(gt, list) else ([gt] if gt else [])
        maps.append({'section': sec, 'ini_order': order, 'MapFilename': fn, 'MapId': v.get('MapId'), 'PresenceId': v.get('PresenceId'),
                     'Faction': v.get('Faction', base.get('Faction')), 'CompatibleGameTypes': gt,
                     'ImagePath': img, 'thumbnail_png': thumbs.get(thumb), 'image_inherited_default': 'ImagePath' not in v,
                     'FriendlyName': {'INT': (tg_int.get(sec) or {}).get('FriendlyName'), 'FRA': (tg_fra.get(sec) or {}).get('FriendlyName')},
                     'Description': {'INT': (tg_int.get(sec) or {}).get('Description'), 'FRA': (tg_fra.get(sec) or {}).get('Description')},
                     'cooked_package_present': cooked[0] if cooked else None,
                     'other_keys': {k: x for k, x in v.items() if k not in ('MapId', 'PresenceId', 'MapFilename', 'ImagePath', 'CompatibleGameTypes', 'Faction')},
                     'confidence': CONF})
    sel = [m for m in maps if m['cooked_package_present']]
    write('frontend_maps.json', {'generated_by': 'AssetTools/scripts/wfc/fe_frontend.py',
                                 'source': 'TransLevels.ini [<map> TnDataProvider_MapInfo] + TransGame.int (INT/FRA) + UI_LevelThumbnails_p',
                                 'default_provider': base, 'maps': maps,
                                 'shipped_selectable (cooked package present)': [m['MapFilename'] for m in sel],
                                 'not_cooked (listed in config only)': [m['MapFilename'] for m in maps if not m['cooked_package_present']],
                                 'ordering_note': 'menu order = ini section order (HIGH); MapId is the online id',
                                 'streets': next((m for m in maps if m['MapFilename'].lower() == 'mp_iac_streets_base_m'), None)})

    # ---------------- modes
    gmi = {}
    for sec, v in list(gm.items()) + list(INTt.get('TransGame', {}).items()):
        if 'GameModeInfo' in sec:
            k = sec.split(' ')[0]
            gmi.setdefault(k, {}).update(v)
    for sec, v in FRAt.get('TransGame', {}).items():
        if 'GameModeInfo' in sec: gmi.setdefault(sec.split(' ')[0], {})['FriendlyName_FRA'] = v.get('FriendlyName')
    pls = []
    for sec, v in ini['TransPlaylists.ini'].items():
        if 'TnDataProvider_OnlinePlaylist' in sec:
            n = sec.split(' ')[0]
            pls.append({'section': n, **v, 'DisplayName': {'INT': (INTt.get('TransGame', {}).get(sec) or {}).get('DisplayName'),
                                                           'FRA': (FRAt.get('TransGame', {}).get(sec) or {}).get('DisplayName')}})
    pm = ini['TransPlaylists.ini'].get('TransGame.TnOnlinePlaylistManager') or {}
    gs = {}
    for o, in A.con().execute("SELECT opath FROM objects WHERE opath LIKE 'TransGame.Default__TnOnlineGameSettings%' AND opath NOT LIKE '%.%.%'").fetchall():
        v = A.values(o); gs[o.split('Default__')[1]] = {k: v.get(k) for k in ('GameModeTag', 'GameClass', 'Rules', 'NumPublicConnections',
                                                                             'TimeLimits', 'ScoreLimits', 'MapCycle', 'bIsLanMatch') if k in v}
    mode_tags = sorted({p.get('GameModeTag') for p in pls if p.get('GameModeTag')})
    write('frontend_modes.json', {'generated_by': 'AssetTools/scripts/wfc/fe_frontend.py',
                                  'game_mode_info (TnDataProvider_GameModeInfo: Xe-TransGame.ini + TransGame.int)': gmi,
                                  'playlists': pls, 'playlist_manager': pm, 'online_game_settings_classes': gs,
                                  'mode_tags': mode_tags,
                                  'maps_per_mode': {t: [m['MapFilename'] for m in sel if t in m['CompatibleGameTypes']] for t in mode_tags},
                                  'menu_visible_playlists': [p['section'] for p in pls if str(p.get('VisibleInMenu')).lower() == 'true'],
                                  'icons': 'no per-mode icon asset found by name; mode presentation is text + GFx symbols '
                                           '(see frontend_gfx.json PartyLobby/GameLobby) - UNKNOWN beyond that',
                                  'confidence': CONF})

    # ---------------- audio
    music, sounds = set(), set()
    for lv in flow['levels'].values():
        for m in lv.get('music') or []:
            if m and m.get('SoundCue'): music.add(m['SoundCue'])
        for s in lv.get('sounds') or []:
            if s.get('cue'): sounds.add(s['cue'])
    gfx_ui = sorted({c for r in recs.values() for c in r['ui_sound_cues_named']})
    allui = [r[0] for r in A.con().execute("SELECT opath FROM objects WHERE class='SoundCue' AND (opath LIKE 'BL_HUD_INTERFACE.%' OR opath LIKE 'BL_LVL_HUD_INTERFACE.%')").fetchall()]
    write('frontend_audio.json', {'generated_by': 'AssetTools/scripts/wfc/fe_frontend.py',
                                  'music (Kismet SeqAct_PlayMusic in UI levels)': {c: cue_rec(c) for c in sorted(music)},
                                  'ambience_and_oneshots (Kismet in UI levels)': {c: cue_rec(c) for c in sorted(sounds)},
                                  'gfx_ui_sounds (names passed to Sound.PlaySound in AS, matched to cue names)': {
                                      c: cue_rec(next(p + '.' + c for p in UI_CUE_PKGS if A.get(p + '.' + c))) for c in gfx_ui},
                                  'all_ui_cues': sorted(allui),
                                  'notes': ['AS Sound.PlaySound(name) -> TnSoundActionScriptBinding.PlaySound: the name equals a SoundCue '
                                            'name in BL_HUD_INTERFACE / BL_LVL_HUD_INTERFACE (HIGH; lookup code is script/native)',
                                            'logo/intro movie audio is inside the Bink movies; MoviesToAlwaysPlaySound lists the logos']})

    # ---------------- loading
    lt = INTt.get('TransGame', {}).get('TnOnlineGameSettingsBase') or {}
    tips = [v for k, v in sorted(lt.items()) if k.startswith('EngageText')]
    write('frontend_loading.json', {'generated_by': 'AssetTools/scripts/wfc/fe_frontend.py',
                                    'config (Xe-TransGame.ini [LoadingMovie])': gm.get('LoadingMovie'),
                                    'region_rects (Xe-TransEngine.ini)': {k: v for sec in eng.values() for k, v in sec.items()
                                                                          if k in ('RegionLoadingScreen', 'RegionMovie')},
                                    'movies': {m: rel(os.path.join(MOVIES, m)) for m in movies if 'Loading' in m or 'InitialStartup' in m},
                                    'gfx': {k: recs[k] for k in recs if k.startswith('UI_GFxLoading_p/')},
                                    'kismet_hooks': {'UI_FrontEnd_m SeqAct_SetLoadingMovieFilename': 'set on PreGameplaySetup and on '
                                                     'entering the front end; native TnOnlineActionScriptBindingNative.SetLoadingMovieFilename'},
                                    'loading_tips (TnOnlineGameSettingsBase.EngageText, INT)': tips,
                                    'map_info_on_loading_screen': 'LoadScreen_GFX exports mc_levelInfo (map name/thumbnail panel, HIGH) '
                                                                  'and mc_engageText (tips, HIGH); data feed is script (RE)',
                                    'music': 'none authored for loading in Kismet; loading movie audio is in the Bink file (HIGH)',
                                    'confidence': CONF + ' for config/files; HIGH for role of each symbol'})

    # ---------------- localization
    keys = sorted({k for r in recs.values() for k in r['localization_keys']})
    def resolve(k, T):
        parts = k.lstrip('$').split('.')
        if len(parts) < 3: return None
        f, sec, key = parts[0], parts[1], '.'.join(parts[2:])
        return ((T.get(f) or {}).get(sec) or {}).get(key)
    res = {k: {'INT': resolve(k, INTt), 'FRA': resolve(k, FRAt)} for k in keys}
    def prefixed(k):
        f, sec, key = k.lstrip('$').split('.', 2)
        return sorted(x for x in ((INTt.get(f) or {}).get(sec) or {}) if x.startswith(key) and x != key)[:12]
    write('frontend_localization.json', {'generated_by': 'AssetTools/scripts/wfc/fe_frontend.py',
                                         'files': {'INT': rel(INT), 'FRA': rel(FRA) if os.path.isdir(FRA) else None},
                                         'gfx_keys': res,
                                         'runtime_suffixed_key_prefixes (AS appends a suffix; HIGH)': {
                                             k: prefixed(k) for k, v in res.items() if not v['INT'] and prefixed(k)},
                                         'unresolved_gfx_keys': [k for k, v in res.items() if not v['INT'] and not prefixed(k)],
                                         'sections': {f: {s: dict(v) for s, v in INTt.get(f, {}).items()}
                                                      for f in ('UIText', 'UIText_360', 'GFxUI')},
                                         'transgame_frontend_sections': {s: dict(v) for s, v in INTt.get('TransGame', {}).items()
                                                                         if any(t in s for t in ('MapInfo', 'GameModeInfo', 'OnlinePlaylist',
                                                                                                 'TnOnlineGameSettings', 'GameLobby',
                                                                                                 'TnFactionTeam', 'TnGameReplicationInfo'))}})
    # ---------------- RE handoff: everything that crosses the AS <-> UnrealScript/native boundary
    calls = defaultdict(lambda: {'movies': set()})
    for k, r in recs.items():
        for b in r['bridge_calls (ExternalInterface.call)']:
            c = calls[b['call']]; c['movies'].add(k); c.update({x: y for x, y in b.items() if x != 'call'})
    cb = defaultdict(set)
    for k, r in recs.items():
        for f in r['_global_callbacks_defined (called from script/native)']:
            if f not in ('addInterp', 'createInterpController', 'findInterpValue', 'removeInterpController', 'updateInterpObjects'):
                cb[f].add(k)
    fs = defaultdict(set)
    for lv, r in flow['levels'].items():
        for f in r.get('fscommands') or []: fs[f['fscommand']].add(lv + ' <- ' + str(f['movie']))
    write('frontend_re_handoff.json', {
        'generated_by': 'AssetTools/scripts/wfc/fe_frontend.py',
        'scope': 'UI calls whose behaviour is UnrealScript or native code. AssetTools recovers names and call sites only; '
                 'semantics, arguments and return values are RE scope. Nothing here is implemented or guessed.',
        'as_to_script_calls_resolved (function exported on the binding class)': {
            k: {'binding_class': v['binding_class'], 'movies': sorted(v['movies'])} for k, v in sorted(calls.items()) if v['function_exported']},
        'as_to_script_calls_other_class (same-name function elsewhere; dispatch path UNKNOWN)': {
            k: {'binding_class': v['binding_class'], 'candidates': v['same_name_function_elsewhere'], 'movies': sorted(v['movies'])}
            for k, v in sorted(calls.items()) if not v['function_exported'] and v.get('same_name_function_elsewhere')},
        'as_to_script_calls_unresolved (no script function of that name - native-only or dead AS code, UNKNOWN)': {
            k: {'binding_class': v['binding_class'], 'movies': sorted(v['movies'])}
            for k, v in sorted(calls.items()) if not v['function_exported'] and not v.get('same_name_function_elsewhere')},
        'script_to_as_callbacks (_global functions defined by movies; caller is script/native)': {k: sorted(v) for k, v in sorted(cb.items())},
        'fscommands (AS -> Kismet GFxEvent_FsCommand)': {k: sorted(v) for k, v in sorted(fs.items())},
        'binding_classes_not_cooked': [k for k, v in binds.items() if not v['class_cooked']],
        'native_flag_status': 'UNKNOWN: WFC UFunction FunctionFlags tail not decoded (iNative/OperPrecedence decode; flag word '
                              'layout differs between Engine and TransGame exports). RE should classify native vs script per function.',
        'kismet_natives': {'SeqAct_SetLoadingMovieFilename': 'TnOnlineActionScriptBindingNative.SetLoadingMovieFilename',
                           'TnSeqAct_OpenFrontEnd': 'TransGame Kismet action (class), runtime RE',
                           'SeqAct_InstallGame': 'Xbox 360 install action, runtime RE'}})

    print('maps', len(maps), 'shipped', len(sel), 'modes', len(gmi), 'playlists', len(pls), 'gfx', len(recs),
          'loc keys', len(keys), 'unresolved', sum(1 for v in res.values() if not v['INT']))

if __name__ == '__main__':
    main()
