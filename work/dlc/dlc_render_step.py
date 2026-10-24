"""Run one Rendering tools/render module (read-only import from the integration checkout) against the DLC sources: ue3obj.COOKED -> the
DLC cooked dir (base packages still resolve: AssetTools' ue3pkg falls back to the Game Dump when WFC_COOKED_DIR is set), ue3obj.CONTENT
-> the DLC umodel content root; ue3obj.VS_MAPS follows WFC_VS_ROOT (work/dlc_maps/VerticalSlice). Source dlc_env.sh first.
    python dlc_render_step.py <module.py> [args...]      (prints the module's stdout; exit code = the module's)
"""
import os, runpy, sys
TOOLS = r'F:/Transformers Rebuild/Rebuild/tools/render'
sys.path.insert(0, TOOLS)
import ue3obj  # noqa: E402
ue3obj.COOKED = os.environ['WFC_COOKED_DIR'].replace('\\', '/')
ue3obj.CONTENT = os.environ['WFC_EXTRACT_OUT'].replace('\\', '/')
# base-game packages stay visible (Rendering 2026-10-23: 30 "no master material" per DLC map - the masters are base-game objects and
# build_materials finds their holders by listing COOKED): listing the DLC dir returns DLC + base names (ue3pkg already falls back to the
# base dir for a base package), and a umodel call naming a base-only package gets its absolute path (umodel resolves by its -path dir)
BASE = r'F:/Transformers Rebuild/Game Dump/TransGame/CookedXenon'
_norm = lambda p: os.path.normcase(os.path.normpath(str(p)))
_dlc_names = set(os.listdir(ue3obj.COOKED))
_listdir = os.listdir
def _listdir_union(path='.'):
    names = _listdir(path)
    return sorted(set(names) | set(_listdir(BASE))) if _norm(path) == _norm(ue3obj.COOKED) else names
os.listdir = _listdir_union
import subprocess  # noqa: E402
_Popen_init = subprocess.Popen.__init__
def _popen_init(self, args, *a, **k):
    if isinstance(args, (list, tuple)) and any(isinstance(x, str) and x.startswith('-path=') for x in args):
        args = [os.path.join(BASE, x) if isinstance(x, str) and x.lower().endswith('.xxx') and os.sep not in x and '/' not in x
                and x not in _dlc_names and os.path.exists(os.path.join(BASE, x)) else x for x in args]
    _Popen_init(self, args, *a, **k)
subprocess.Popen.__init__ = _popen_init
mod = sys.argv[1]
sys.argv = [os.path.join(TOOLS, mod)] + sys.argv[2:]
runpy.run_path(os.path.join(TOOLS, mod), run_name='__main__')
