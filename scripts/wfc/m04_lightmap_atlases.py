"""Export every lightmap atlas (all 3 directional coefficients) referenced by lightmaps.json that has no PNG yet (never overwrites).

The _LM companion packages hold some LightMapTexture2D exports as stubs without mip data ("no valid mipmaps" in
umodel); the level package (MP_IAC_Streets_ART_m / _BASE_m) cooks a full copy. Tries the _LM package first, then the
level package. umodel output goes to a temp dir; only the missing PNG is copied into
ExtractedAssets/VerticalSlice/Maps/<MAP>/lightmaps/.
  python m04_lightmap_atlases.py [MAP]
"""
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract  # noqa: E402
from vs_common import VS  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP, 'lightmaps')
os.makedirs(OUT, exist_ok=True)

def main():
    lm = json.load(open(os.path.join(VS, 'Maps', MAP, 'lightmaps.json'), encoding='utf-8'))
    want = {}
    for x in lm['props']:
        for c in x.get('coeffs') or [x['atlas']]:        # all three directional coefficient atlases
            if not os.path.exists(os.path.join(OUT, c + '.png')):
                want[c] = x['atlas_package']
    if not want:
        print('all atlases present'); return
    tmp = tempfile.mkdtemp(prefix='lmatlas_')
    done = []
    for atlas, lmpkg in sorted(want.items()):
        level = lmpkg.replace('_LM', '').replace('_Base_m', '_BASE_m')
        for pkg in (lmpkg, level):
            subprocess.run([extract.UMODEL, '-export', '-path=%s' % extract.COOKED, '-game=trans', '-out=%s' % tmp, '-png',
                            pkg + '.xxx', '-obj=%s' % atlas], capture_output=True, timeout=300)
            src = os.path.join(tmp, pkg, 'LightMapTexture2D', atlas + '.png')
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(OUT, atlas + '.png'))
                done.append((atlas, pkg)); break
    shutil.rmtree(tmp, ignore_errors=True)
    print('exported:', done, 'still missing:', sorted(set(want) - {a for a, _ in done}))

if __name__ == '__main__':
    main()
