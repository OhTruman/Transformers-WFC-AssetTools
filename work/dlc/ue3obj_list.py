"""helper for dlc_render.py (run through dlc_render_step.py? no: imported directly with the DLC constants): prints a map's lightmap
packages ('lm') or level packages ('levels') per Rendering's ue3obj, with COOKED pointed at the DLC cooked dir."""
import os, sys
sys.path.insert(0, r'F:/Transformers Rebuild/Rebuild/tools/render')
import ue3obj  # noqa: E402
ue3obj.COOKED = os.environ['WFC_COOKED_DIR'].replace('\\', '/')
what, M = sys.argv[1], sys.argv[2]
print(' '.join(ue3obj.map_lm_packages(M) if what == 'lm' else ue3obj.map_packages(M)[0]))
