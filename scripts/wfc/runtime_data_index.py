"""Where every generated runtime file lives -> manifests/RUNTIME_DATA_INDEX.json (for Gameplay / Rendering / Frontend / Integration)

ExtractedAssets is local (never pushed); this index is in git and lists, per consumer-facing category, the directory, the
per-item files present on this machine, and the AssetTools manifest + generator that describe them.
"""
import json, os, sys, time
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import ROOT, VS  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))

def listing(d, want=None):
    if not os.path.isdir(d): return {}
    out = OrderedDict()
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        if not os.path.isdir(p): continue
        files = sorted(f for f in os.listdir(p) if os.path.isfile(os.path.join(p, f)) and (not want or f.endswith(want)))
        out[name] = files
    return out

def main():
    maps = listing(os.path.join(VS, 'Maps'))
    out = OrderedDict([
        ('generated_by', 'AssetTools/scripts/wfc/runtime_data_index.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
        ('root', 'F:/Transformers Rebuild/ExtractedAssets (local only; all paths below are relative to it)'),
        ('characters', {'dir': 'VerticalSlice/Characters/<ChassisId>', 'contract': 'robot.glb, vehicle.glb, character.json, textures/',
                        'stable_id': 'RE chassis UniqueId (Car2, Truck4, ...); Optimus = slice folder kept for Gameplay',
                        'index': 'AssetTools/manifests/mp_content/character_export_index.json', 'generator': 'scripts/wfc/vs_roster_export.py --all',
                        'items': listing(os.path.join(VS, 'Characters'), '.json')}),
        ('weapons', {'dir': 'VerticalSlice/Weapons/<ProviderId>', 'contract': 'weapon.glb, weapon.json (IonBlaster: slice weapon.* kept, generic weapon_mp.*)',
                     'stable_id': 'TnDataProvider_Weapon UniqueId', 'index': 'AssetTools/manifests/mp_content/weapon_export_index.json',
                     'generator': 'scripts/wfc/vs_weapon_export.py --all', 'items': listing(os.path.join(VS, 'Weapons'), '.json')}),
        ('maps', {'dir': 'VerticalSlice/Maps/<MAP>', 'renderer_reads': ['world.glb', 'props.json', 'map.json', 'render_index.json',
                                                                       'lightmaps.json + lightmaps/', 'vertex_lightmaps.json', 'postprocess.json + postprocess_clut*.png'],
                  'per_map_manifests': 'AssetTools/manifests/maps/<MAP>/{completeness, structure_audit, render_index_generic, map_complete}.json; '
                                       'manifests/next_map/<MAP>_*.json (Streets: manifests/streets_*.json)',
                  'readiness': 'AssetTools/manifests/maps/readiness_matrix.json + docs/MAP_READINESS_MATRIX.md',
                  'generator': 'scripts/wfc/run_map_pipeline.py <MAP> (Streets: CLAUDE.md order; render_index = m04_complete.py)',
                  'items': OrderedDict((k, v) for k, v in maps.items() if k.startswith('MP_'))}),
        ('menu_scenes', {'dir': 'VerticalSlice/Maps/UI_<Scene>', 'index': 'AssetTools/manifests/frontend_package/ui_scenes.json',
                         'generator': 'scripts/wfc/ui_scenes.py (after the map stages per family)',
                         'items': OrderedDict((k, v) for k, v in maps.items() if k.startswith('UI_'))}),
        ('movies', {'dir': 'movies', 'contract': '<FMV>.mkv + <FMV>.subtitles.json', 'catalogue': 'AssetTools/manifests/frontend_package/extras.json',
                    'items': sorted(f for f in os.listdir(os.path.join(ROOT, 'movies')))[:200] if os.path.isdir(os.path.join(ROOT, 'movies')) else []}),
        ('frontend', {'package': 'AssetTools/manifests/frontend_package/*.json', 'hud': 'AssetTools/manifests/hud/hud_package.json',
                      'roster': 'AssetTools/manifests/mp_content/roster_package.json', 'content_root': 'content/<Package>/...'}),
        ('config', {'dir': 'config', 'contract': 'Coalesced_{ini,int,FRA}/... decoded ini / localization'})])
    json.dump(out, open(os.path.join(AT, 'manifests', 'RUNTIME_DATA_INDEX.json'), 'w', encoding='utf-8'), indent=1)
    print({k: len(v['items']) for k, v in out.items() if isinstance(v, dict) and 'items' in v})

if __name__ == '__main__':
    main()
