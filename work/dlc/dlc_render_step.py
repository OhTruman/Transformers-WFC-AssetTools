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
mod = sys.argv[1]
sys.argv = [os.path.join(TOOLS, mod)] + sys.argv[2:]
runpy.run_path(os.path.join(TOOLS, mod), run_name='__main__')
