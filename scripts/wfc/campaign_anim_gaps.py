"""Close the campaign 'psa-only anim sets' gap (Integration 2026-10-18).

Cause: these AnimSets share their object name with an AnimSet in another package (TR_LightSmall_ANM_p.VIG_Run_ANIM vs
TR_LightMedium_ANM_p.VIG_Run_ANIM, ...). assets.json lists both .psa files for the record and psa2gltf.main converts the first one
only, so this package's own .psa was never converted. Here each one is converted with psa2gltf.convert (same conventions, rest pose
from the AnimSet's preview skeletal mesh) into AssetTools/out/campaign_anims/<pkg>/<name>.anim.gltf (+ .bin); ExtractedAssets is not
written. An AnimSet with no .psa is reported with its cooked state.
Writes manifests/campaign/anim_gaps.json.
"""
import json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import extract  # noqa: E402
import psa2gltf  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EAROOT = os.path.dirname(extract.OUT)
OUT = os.path.join(ROOT, 'out', 'campaign_anims')

def main():
    gaps = json.load(open(os.path.join(ROOT, 'work', 'campaign_assets', 'gaps.json'), encoding='utf-8'))['anim_sets']
    assets = json.load(open(os.path.join(extract.MANI, 'assets.json'), encoding='utf-8'))['assets']
    mesh_gl = {a['object_path']: next((o for o in a['extracted'] if o.endswith('.gltf')), None)
               for a in assets if a['class'] == 'SkeletalMesh'}
    rec = {a['object_path']: a for a in assets if a['class'] == 'AnimSet'}
    db = sqlite3.connect(os.path.join(ROOT, 'manifests', 'authored.db'))
    rows = []
    for opath in sorted(gaps):
        pkg, name = opath.split('.', 1)
        a = rec.get(opath) or {}
        psa = next((o for o in a.get('extracted', []) if o.endswith('.psa') and o.split('/')[1] == pkg), None)
        row = {'object': opath, 'chapters': gaps[opath]}
        if not psa:
            p = db.execute('select props from objects where opath=?', (opath,)).fetchone()
            props = json.loads(p[0]) if p and p[0] else {}
            row.update({'status': 'no_animation_data', 'cooked_properties': sorted(props),
                        'note': 'cooked AnimSet carries TrackBoneNames only: no Sequences property and no AnimSequence exports under it, '
                                'so there is nothing to convert'})
            rows.append(row); print(row['status'], opath); continue
        mesh = a.get('preview_skeletal_mesh')
        if not mesh_gl.get(mesh):
            mesh = next((m for m in a.get('compatible_skeletal_meshes', []) if mesh_gl.get(m)), None)
        mg = os.path.join(EAROOT, mesh_gl[mesh]) if mesh and mesh_gl.get(mesh) else None
        os.makedirs(os.path.join(OUT, pkg), exist_ok=True)
        r = psa2gltf.convert((os.path.join(EAROOT, psa), mg, os.path.join(OUT, pkg, name.split('.')[-1])))
        r['output'] = os.path.relpath(os.path.join(OUT, pkg, name.split('.')[-1] + '.anim.gltf'), ROOT).replace(os.sep, '/')
        g = json.load(open(os.path.join(ROOT, r['output']), encoding='utf-8'))
        row.update({'status': 'converted', 'psa': psa, 'rest_mesh': mesh, **r,
                    'sequence_names': [s['name'] for s in g['extras']['sequences']]})
        rows.append(row); print(row['status'], opath, r['bones'], 'bones', r['sequences'], 'sequences')
    json.dump({'generated_by': 'AssetTools/scripts/wfc/campaign_anim_gaps.py', 'anim_sets': rows},
              open(os.path.join(ROOT, 'manifests', 'campaign', 'anim_gaps.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    main()
