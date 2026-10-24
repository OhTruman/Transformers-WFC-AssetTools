"""Rendering's build_campaign_pp.py (read-only import) on a DLC MP map -> out/dlc_render/<MAP>/postprocess_volumes.json + pp/<lut>.png
(Rendering 2026-10-23: District's power outage swaps PostProcessVolume_4388 on / 3052 off). Source dlc_env.sh first.

The tool reads a campaign chapter.json (units) and ONE authored DB. Here: a chapter.json for the map (every package of the map is a
unit, dir = package name) under work/dlc/pp_chapters, and the DB = the DLC authored.db with the base one attached behind a temp
'objects' view (the volumes are DLC rows; Engine.Default__PostProcessVolume / Default__WorldInfo exist only in the base DB).
COOKED / umodel patching for the LUT decode: dlc_render_step.py.
    python dlc_pp.py <MAP>
"""
import json, os, runpy, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
DLC_DB = os.path.join(AT, 'manifests', 'dlc', 'authored.db'); BASE_DB = os.path.join(AT, 'manifests', 'authored.db')
m = sys.argv[1]
with sqlite3.connect(DLC_DB) as d:
    pkgs = [r[0] for r in d.execute("select distinct package from objects where package=? or package like ? escape '\\' order by 1",
                                    (m, m + '\\_%'))]
cdir = os.path.join(HERE, 'pp_chapters', m); os.makedirs(cdir, exist_ok=True)
json.dump({'persistent_level': m, 'persistent_dir': m, 'sublevels': [{'level': p, 'dir': p} for p in pkgs if p != m],
           'note': 'AssetTools work/dlc/dlc_pp.py: a DLC MP map as a build_campaign_pp chapter (units = its packages)'},
          open(os.path.join(cdir, 'chapter.json'), 'w', encoding='utf-8'), indent=1)
os.environ['WFC_CAMPAIGN_ROOT'] = os.path.join(HERE, 'pp_chapters'); os.environ['WFC_AUTHORED_DB'] = DLC_DB

_connect = sqlite3.connect
def connect(db, *a, **k):
    c = _connect('file:%s?mode=ro' % DLC_DB.replace('\\', '/'), uri=True)
    c.execute("attach database 'file:%s?mode=ro' as b" % BASE_DB.replace('\\', '/'))   # URI attach: the connection is uri=True
    c.execute('create temp view objects as select * from main.objects union all select * from b.objects')
    return c
sqlite3.connect = connect
out = os.path.join(AT, 'out', 'dlc_render', m)
sys.argv = [os.path.join(HERE, 'dlc_render_step.py'), 'build_campaign_pp.py', m, out]
runpy.run_path(sys.argv[0], run_name='__main__')
print(m, 'units', len(pkgs), '->', out)
