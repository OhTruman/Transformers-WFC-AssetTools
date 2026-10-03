"""Validator for the frontend manifests (fe_frontend.py). Writes logs/validate_frontend.json; exit 1 on failure.

  files_exist        every movie / thumbnail / gfx / image / wav path named in the manifests exists under ExtractedAssets
  kismet_movies      every SeqAct_MoviePlayer MovieName in the UI levels has a .mkv
  streets            MP_IAC_Streets is present with name, thumbnail, cooked package and all six versus modes
  maps_modes         every shipped map's CompatibleGameTypes are known mode tags; every menu-visible playlist has a mode
  ui_cues            every music / ambience / GFx UI sound resolves to a SoundCue with at least one WAV
  bindings           every binding class exists; bridge calls carry a resolution status
  mode_presentation  every mode has name + icon symbol; music / announcer cues resolve to existing WAVs
  hud                every HUD/UIController movie has a GFx record; observers exist; marker textures exist
  map_catalog        Streets reference record; streamed levels present; thumbnails exist; readiness covers all maps
  loc                GFx localization keys: resolved share reported (unresolved listed, not a failure)
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from vs_common import ROOT  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
LOGS = os.path.normpath(os.path.join(HERE, '..', '..', 'logs'))
VERSUS = {'DM', 'TDM', 'CTF', 'KOTH', 'EXT', 'DOM'}

def J(n): return json.load(open(os.path.join(MANI, n), encoding='utf-8'))

def main():
    res, fails = {}, []
    def chk(n, c, m=''):
        res.setdefault(n, [0, 0]); res[n][0] += 1
        if not c: res[n][1] += 1; fails.append('%s: %s' % (n, m))
    names = ['frontend_flow.json', 'frontend_gfx.json', 'frontend_bindings.json', 'frontend_maps.json', 'frontend_modes.json',
             'frontend_audio.json', 'frontend_loading.json', 'frontend_localization.json']
    M = {n: J(n) for n in names}
    for n, j in M.items():
        for p in set(re.findall(r'"((?:content|movies|config)/[^"]+\.(?:mkv|png|gfx|wav|int|ini))"', json.dumps(j))):
            chk('files_exist', os.path.exists(os.path.join(ROOT, p)), '%s: %s' % (n, p))
    fl = M['frontend_flow.json']
    for lv, r in fl['levels'].items():
        for n in r.get('nodes', []):
            if n['class'] == 'SeqAct_MoviePlayer':
                mv = n['authored'].get('MovieName')
                chk('kismet_movies', mv + '.mkv' in fl['movie_files'], '%s %s' % (lv, mv))
    mp = M['frontend_maps.json']; st = mp['streets']
    chk('streets', st is not None, 'missing')
    if st:
        chk('streets', st['FriendlyName']['INT'] == 'Streets', 'name')
        chk('streets', bool(st['thumbnail_png']) and os.path.exists(os.path.join(ROOT, st['thumbnail_png'])), 'thumbnail')
        chk('streets', bool(st['cooked_package_present']), 'package')
        chk('streets', VERSUS <= set(st['CompatibleGameTypes']), 'modes')
    md = M['frontend_modes.json']
    tags = set(md['mode_tags'])
    for m in mp['maps']:
        if m['cooked_package_present']:
            for t in m['CompatibleGameTypes']: chk('maps_modes', t in tags, '%s %s' % (m['MapFilename'], t))
    for p in md['playlists']:
        if str(p.get('VisibleInMenu')).lower() == 'true': chk('maps_modes', bool(p.get('GameModeTag')), p['section'])
    au = M['frontend_audio.json']
    for sec in ('music (Kismet SeqAct_PlayMusic in UI levels)', 'ambience_and_oneshots (Kismet in UI levels)',
                'gfx_ui_sounds (names passed to Sound.PlaySound in AS, matched to cue names)'):
        for c, r in au[sec].items():
            chk('ui_cues', not r.get('missing') and (len(r['waves']) > 0 or r.get('authored_silent')), c)
    for cn in M['frontend_bindings.json']['bindings']:
        pk, c = cn.split('.')
        b = M['frontend_bindings.json']['bindings'][cn]
        chk('bindings', (A.get('%s.Default__%s' % (pk, c)) is not None) == b.get('class_cooked'), cn)
    for r in M['frontend_gfx.json']['movies'].values():
        for b in r['bridge_calls (ExternalInterface.call)']:
            chk('bindings', 'function_exported' in b, b['call'])
    # presentation / HUD / catalog (fe_presentation.py, fe_map_catalog.py)
    mp = J('frontend_mode_presentation.json')
    for tag, r in mp['modes'].items():
        chk('mode_presentation', bool(r['text']['FriendlyName']['INT']), tag + ' name')
        chk('mode_presentation', r['icon'].get('symbol') is not None, tag + ' icon')
        for k, c in r['music'].items():
            chk('mode_presentation', c and not c['missing'] and all(os.path.exists(os.path.join(ROOT, w)) for w in c['wavs']), tag + ' ' + k)
        for k, d in r['announcer'].items():
            if d: chk('mode_presentation', bool(d['wavs']) and all(os.path.exists(os.path.join(ROOT, w)) for w in d['wavs']), tag + ' ' + k)
    for tag in VERSUS:
        chk('mode_presentation', tag in mp['modes'], 'missing mode ' + tag)
    hd = J('frontend_hud.json')
    for k, v in hd['movies'].items():
        chk('hud', v['record'] is not None, 'movie record ' + k)
    for o in hd['data_observers']:
        chk('hud', A.get(o['object']) is not None, o['object'])
    for p in hd['hud_marker_textures (UI_HudMarkers_p)']:
        chk('hud', os.path.exists(os.path.join(ROOT, p)), p)
    cat = J('mp_map_catalog.json')
    st = [m for m in cat['maps'] if m['MapFilename'].lower() == 'mp_iac_streets_base_m']
    chk('map_catalog', len(st) == 1 and 'reference_implementation' in st[0], 'streets reference')
    for m in cat['maps']:
        if m.get('cooked'):
            chk('map_catalog', not m['packages']['missing_streamed'], m['MapFilename'] + ' streamed levels')
            chk('map_catalog', bool(m['thumbnail_png']) and os.path.exists(os.path.join(ROOT, m['thumbnail_png'])), m['MapFilename'] + ' thumb')
    rd = J('mp_next_map_readiness.json')
    chk('map_catalog', len(rd['ranking']) == sum(1 for m in cat['maps'] if m.get('cooked')) - 1, 'readiness covers all cooked maps')
    lk = M['frontend_localization.json']
    resolved = sum(1 for v in lk['gfx_keys'].values() if v['INT'])
    os.makedirs(LOGS, exist_ok=True)
    out = {'checks': res, 'failures': fails, 'localization_keys': {'total': len(lk['gfx_keys']), 'resolved_INT': resolved}}
    json.dump(out, open(os.path.join(LOGS, 'validate_frontend.json'), 'w'), indent=1)
    for k, v in res.items(): print('%-14s %5d checks %3d failed' % (k, v[0], v[1]))
    print('localization keys resolved %d/%d' % (resolved, len(lk['gfx_keys'])))
    tot = sum(v[0] for v in res.values()); bad = sum(v[1] for v in res.values())
    print('validate_frontend: %d checks, %d failures' % (tot, bad))
    for f in fails[:30]: print('  FAIL', f)
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
