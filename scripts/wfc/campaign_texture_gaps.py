"""Close the campaign 'textures without a PNG' gap (Integration 2026-10-18).

Inputs: work/campaign_assets/gaps.json (from the chapter manifests). For each texture:
  TextureCube           -> six faces decoded from the cooked Xbox data with Rendering's xbox_texture.decode_cube (the decoder
                           build_materials.py uses for its own cube maps; imported read-only, no bytecode written)
  Texture2D             -> top mip via xbox_texture.read_mip_chain / decode_mip (same path as build_materials.native_decode)
  TextureRenderTarget2D -> runtime-only (no pixels in the cook); recorded, nothing decoded
Writes AssetTools/out/campaign_textures/<pkg>/<group...>/<name>[_f0..5].png and manifests/campaign/texture_gaps.json.
ExtractedAssets is not written (read-only for this lane).
"""
import hashlib, json, os, sqlite3, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), 'Rebuild', 'tools', 'render'))
import xbox_texture  # noqa: E402
from ue3obj import Repo, COOKED  # noqa: E402
from PIL import Image  # noqa: E402

OUT = os.path.join(ROOT, 'out', 'campaign_textures')
INV = sqlite3.connect(os.path.join(ROOT, 'manifests', 'inventory.db'))
# UE3 TextureCube face order (FaceX/NegX/FaceY/NegY/FaceZ/NegZ), as decode_cube returns it
FACES = ['+X', '-X', '+Y', '-Y', '+Z', '-Z']

def best_package(opath):
    r = INV.execute('select package, serial_size from exports where opath=? order by serial_size desc limit 1', (opath,)).fetchone()
    return r

def main():
    gaps = json.load(open(os.path.join(ROOT, 'work', 'campaign_assets', 'gaps.json'), encoding='utf-8'))['textures']
    cooked = {f.lower(): f for f in os.listdir(COOKED)}
    rows = []
    for opath in sorted(gaps):
        pkg, size = best_package(opath)
        R = Repo([cooked[(pkg + '.xxx').lower()]])
        cls = R.cls(opath); o = R.obj(opath) or {}
        name = opath.split('.')[-1]; d = os.path.join(OUT, *opath.split('.')[:-1])
        row = {'object': opath, 'class': cls, 'chapters': gaps[opath], 'source_package': pkg, 'serial_size': size,
               'format': o.get('Format'), 'srgb': o.get('SRGB', True)}
        try:
            if cls == 'TextureRenderTarget2D':
                row.update({'status': 'runtime_only', 'note': 'render target: rendered at runtime (no pixel data in the cook)',
                            'size': [o.get('SizeX'), o.get('SizeY')]})
            elif cls == 'TextureCube':
                _, tail = R.native_tail(opath)
                edge = int(o.get('EdgeSize', 256))
                os.makedirs(d, exist_ok=True)
                files = []
                for k, img in enumerate(xbox_texture.decode_cube(tail, o.get('Format', 'PF_DXT1'), edge)):
                    fn = os.path.join(d, '%s_f%d.png' % (name, k)); Image.fromarray(img).save(fn); files.append(fn)
                row.update({'status': 'decoded', 'edge': edge, 'faces': [
                    {'face': FACES[k], 'file': os.path.relpath(f, ROOT).replace(os.sep, '/'),
                     'sha256': hashlib.sha256(open(f, 'rb').read()).hexdigest()} for k, f in enumerate(files)]})
            else:
                _, tail = R.native_tail(opath)
                mips, _ = xbox_texture.read_mip_chain(tail, 0)
                sx, sy, data = next(m for m in mips if m[2])
                os.makedirs(d, exist_ok=True)
                fn = os.path.join(d, name + '.png')
                Image.fromarray(xbox_texture.decode_mip(sx, sy, data, o.get('Format', 'PF_DXT1'))).save(fn)
                row.update({'status': 'decoded', 'size': [sx, sy], 'file': os.path.relpath(fn, ROOT).replace(os.sep, '/'),
                            'sha256': hashlib.sha256(open(fn, 'rb').read()).hexdigest()})
        except Exception as ex:
            row.update({'status': 'failed', 'error': '%s: %s' % (type(ex).__name__, ex)})
        rows.append(row)
        print(row['status'], cls, opath, row.get('error', ''))
    out = {'generated_by': 'AssetTools/scripts/wfc/campaign_texture_gaps.py',
           'decoder': 'Rebuild/tools/render/xbox_texture.py (Rendering; read-only import) - decode_cube / read_mip_chain / decode_mip',
           'face_order': FACES, 'textures': rows}
    json.dump(out, open(os.path.join(ROOT, 'manifests', 'campaign', 'texture_gaps.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    main()
