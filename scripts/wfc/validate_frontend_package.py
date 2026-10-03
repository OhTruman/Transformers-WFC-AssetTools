"""Dangling-reference validator for manifests/frontend_package/*.json (fe_package.py). Writes logs/validate_frontend_package.json.

  paths          every content/... movies/... config/... path string exists under ExtractedAssets
  ue_objects     every dotted object path whose first segment is a cooked package exists in inventory.db / authored.db
  movies         every movie key used by screens / submovies / imports / HUD resolves to a movie record
  packages       every map package (persistent, streamed, companions) is a cooked package
  cues           every sound cue named by movies / registry resolves (waves or authored-silent)
  registry       mode icon symbols exist in SharedIcons_GFX, score panels in Hud_GFX, settings defaults inside their value lists,
                 every menu-visible mode has >= 1 compatible cooked map, every cooked map's modes exist
  loading        every cooked map has a loading-screen display name; every mode has tips; spinner bitmaps exist
  python validate_frontend_package.py   (exit 1 on failure)
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from vs_common import ROOT  # noqa: E402

PKG = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests', 'frontend_package'))
LOGS = os.path.normpath(os.path.join(HERE, '..', '..', 'logs'))
OBJ_RX = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$')
PATH_RX = re.compile(r'^(content|movies|config)/[^\s"<>|]+\.(png|gfx|mkv|wav|gltf|int|ini|bin|json|txt)$')

def strings(o):
    if isinstance(o, str): yield o
    elif isinstance(o, dict):
        for k, v in o.items(): yield from strings(v)
    elif isinstance(o, list):
        for v in o: yield from strings(v)

def main():
    res, fails = {}, []
    def chk(n, c, m=''):
        res.setdefault(n, [0, 0]); res[n][0] += 1
        if not c: res[n][1] += 1; fails.append('%s: %s' % (n, m))
    F = {n: json.load(open(os.path.join(PKG, n), encoding='utf-8'))
         for n in ('frontend_package.json', 'mp_registry.json', 'loading_handoff.json', 'hud_handoff.json')}
    inv = objtree.inv()
    pk = {r[0].lower() for r in inv.execute('SELECT package FROM packages')}
    srcpk = pk | {'transgame', 'transcontent', 'engine', 'core', 'gfxui', 'hm_engine', 'engineMaterials'.lower()}
    seen = set()
    for n, j in F.items():
        for s in strings(j):
            if s in seen: continue
            seen.add(s)
            if PATH_RX.match(s):
                chk('paths', os.path.exists(os.path.join(ROOT, s)), s)
            elif OBJ_RX.match(s) and s.split('.')[0].lower() in srcpk and not s.split('.')[-1].endswith(('swf', 'gfx', 'mkv', 'png', 'tga')):
                ok = inv.execute('SELECT 1 FROM exports WHERE opath=? LIMIT 1', (s,)).fetchone() is not None or A.get(s) is not None
                chk('ue_objects', ok, s)
    P = F['frontend_package.json']; mv = P['movies']
    def mkey(k): chk('movies', k in mv, str(k))
    for k, m in mv.items():
        for s in m['submovies (loaded at runtime)']: mkey(s['movie'])
        for s in m['imports (shared libraries)']: mkey(s['movie'])
    for sname, sc in P['screens'].items():
        for key in ('movie',):
            if sc.get(key): mkey(sc[key])
        for s in sc.get('submovies') or []: mkey(s)
        for v in (sc.get('movies') or {}).values(): mkey(v)
    R = F['mp_registry.json']
    for m in R['maps']:
        if not m.get('cooked'): continue
        for p in [m['packages']['persistent']] + m['packages']['streamed'] + m['packages']['companions']:
            chk('packages', p.lower() in pk, '%s %s' % (m['internal_name'], p))
    for k, m in mv.items():
        for c, r in m['sound_cues'].items():
            chk('cues', r['cue'] is not None and A.get(r['cue']) is not None, '%s %s' % (k, c))
    icons = set(mv['UI_GFxShared_p/SharedIcons_GFX']['exports']); hudx = set(mv['UI_GFxHud_p/Hud_GFX']['exports'])
    modes = R['modes']
    gm_ids = {}
    for t, m in modes.items():
        chk('registry', m['icon'].get('symbol') in icons, t + ' icon')
        chk('registry', m['hud_score_panel'] in hudx, t + ' score panel')
        for s in m['settings']:
            if s['kind'] == 'localized setting' and s['name'] != 'GameMode':
                d = s['default_value_id (LocalizedSettings.ValueIndex = ValueMappings.Id)']
                chk('registry', d is None or d in [v['id'] for v in s['values']], '%s %s default' % (t, s['name']))
            if s['kind'] == 'localized setting' and s['name'] == 'GameMode':
                gm_ids.setdefault(s['default_value_id (LocalizedSettings.ValueIndex = ValueMappings.Id)'], []).append(t)
            if s['kind'] == 'property' and s['values'] and s['default_value'] is not None:
                chk('registry', s['default_value'] in s['values'], '%s %s default %s not in %s' % (t, s['name'], s['default_value'], s['values']))
        for c in m['rules_classes'] or []:
            chk('registry', inv.execute("SELECT 1 FROM exports WHERE opath=? AND class='Class' LIMIT 1", (c,)).fetchone() is not None, c)
        if m['menu_visible']:
            chk('registry', any(t in x['supported_modes'] for x in R['maps'] if x.get('cooked')), t + ' has maps')
    for v, ts in gm_ids.items():
        chk('registry', isinstance(v, int) and len(ts) == 1, 'GameMode context value %s shared by %s' % (v, ts))
    for x in R['maps']:
        if x.get('cooked'):
            for t in x['supported_modes']: chk('registry', t in modes, '%s mode %s' % (x['internal_name'], t))
    L = F['loading_handoff.json']
    for mid, v in L['map_names (MapId -> display name used on the loading screen)'].items():
        if v['cooked']: chk('loading', bool(v['INT']), 'map %s name' % mid)
    for t, v in L['tips']['per_mode'].items():
        chk('loading', bool(v['tips_unique']) or t in ('SV',), t + ' tips')
    for sid, v in L['loadscreen_gfx_layout']['spinner_motif (sprite timelines + ring textures)'].items():
        for b in v['bitmaps']: chk('loading', os.path.exists(os.path.join(ROOT, b['png'])), b['png'])
    os.makedirs(LOGS, exist_ok=True)
    json.dump({'checks': res, 'failures': fails}, open(os.path.join(LOGS, 'validate_frontend_package.json'), 'w'), indent=1)
    for k, v in res.items(): print('%-12s %6d checks %4d failed' % (k, v[0], v[1]))
    tot = sum(v[0] for v in res.values()); bad = sum(v[1] for v in res.values())
    print('validate_frontend_package: %d checks, %d failures' % (tot, bad))
    for f in fails[:40]: print('  FAIL', f)
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
