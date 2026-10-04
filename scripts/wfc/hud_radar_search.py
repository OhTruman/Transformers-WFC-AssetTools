"""Systematic search for any multiplayer minimap / radar / compass / blip content (positive or negative evidence).

Searches, case-insensitively, for radar|minimap|mini_map|compass|blip|scanner|overhead|tactical map|map display|mapicon|worldmap:
  1. cooked object paths and class names (inventory.db exports, all packages)
  2. every GFx movie: exports, sprite labels, instance names, text fields, ActionScript constant-pool strings
  3. every localization file (INT + FRA), every ini key/value
  4. extracted file names under ExtractedAssets/content (png/gltf/mat)
  5. RE script decompilation (read-only) function / variable names
Writes manifests/hud/minimap_radar_search.json.  python hud_radar_search.py
"""
import glob, json, os, re, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, gfxscan, fe_frontend as FE  # noqa: E402
from vs_common import ROOT  # noqa: E402

RX = re.compile(r'radar|minimap|mini_map|compass|blip|scanner|overhead|tacticalmap|tactical_map|mapdisplay|map_display|mapicon|worldmap', re.I)
OUT = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests', 'hud'))
DECOMP = r'F:/Transformers Rebuild/RE-Workspace/work/script/decomp'

def main():
    hits = defaultdict(list)
    inv = objtree.inv()
    for opath, cls in inv.execute('SELECT DISTINCT opath, class FROM exports'):
        if RX.search(opath.rsplit('.', 1)[-1]) or RX.search(cls): hits['cooked_objects'].append({'object': opath, 'class': cls})
    for p in sorted(glob.glob(os.path.join(ROOT, 'content', 'UI_*', '*.gfx'))):
        s = gfxscan.scan(p); k = os.path.relpath(p, ROOT).replace(os.sep, '/')
        for v in s['exports'].values():
            if RX.search(v): hits['gfx_exports'].append({'movie': k, 'export': v})
        for sid, sp in s['sprites'].items():
            for l in sp['labels']:
                if RX.search(l['label']): hits['gfx_labels'].append({'movie': k, 'sprite': sid, 'label': l['label']})
            for pl in sp['places']:
                if RX.search(pl.get('name') or ''): hits['gfx_instances'].append({'movie': k, 'sprite': sid, 'name': pl['name']})
        for a in s['action_strings']:
            for x in a['strings']:
                if RX.search(x): hits['gfx_strings'].append({'movie': k, 'string': x})
        for t in s['text_fields'].values():
            if RX.search(json.dumps(t)): hits['gfx_text'].append({'movie': k, 'field': t})
    for base in (FE.INT, FE.FRA, FE.INI):
        for f in glob.glob(os.path.join(base, '*.*')):
            for i, l in enumerate(open(f, encoding='utf-8', errors='replace')):
                if RX.search(l): hits['config_and_localization'].append({'file': os.path.relpath(f, ROOT).replace(os.sep, '/'), 'line': i + 1, 'text': l.strip()[:200]})
    for p in glob.glob(os.path.join(ROOT, 'content', '**', '*.*'), recursive=True):
        if RX.search(os.path.basename(p)): hits['extracted_files'].append(os.path.relpath(p, ROOT).replace(os.sep, '/'))
    if os.path.isdir(DECOMP):
        for f in glob.glob(os.path.join(DECOMP, '*.txt')):
            for l in open(f, encoding='utf-8', errors='replace'):
                if l.startswith('function') and RX.search(l): hits['script_functions'].append(l.strip()[:160])
            if RX.search(os.path.basename(f)): hits['script_classes'].append(os.path.basename(f))
    os.makedirs(OUT, exist_ok=True)
    summary = {k: len(v) for k, v in hits.items()}
    conclusion = ('NO multiplayer minimap / radar / compass / blip content exists in the shipped data. Hits are unrelated: ambient sound '
                  'cues and waves (scanner probes, ships overhead), campaign props (hospital scanner, ENV_IAC_HoloMap mapOverhead_STAT), a '
                  'laser-scanner FX, engine Volume.Encompasses* functions, and GameLobby_GFX mc_mapDisplay (the lobby map preview). '
                  'Enemy awareness in MP is the canvas objective-marker system: Orbital Recon killstreaks add TnBuffSeeEnemyObjectiveMarkers '
                  '(team buff). [TransGame.TnRadarTargetTracker] _MaxDistance=20000 is a config section for a class with no cooked export '
                  '(no script, no data) - UNKNOWN, not a radar widget. CONFIRMED negative for RE / Rendering / Frontend.')
    json.dump({'generated_by': 'AssetTools/scripts/wfc/hud_radar_search.py', 'pattern': RX.pattern, 'conclusion': conclusion, 'hit_counts': summary,
               'hits': {k: v[:300] for k, v in hits.items()}}, open(os.path.join(OUT, 'minimap_radar_search.json'), 'w', encoding='utf-8'), indent=1)
    print(summary)

if __name__ == '__main__':
    main()
