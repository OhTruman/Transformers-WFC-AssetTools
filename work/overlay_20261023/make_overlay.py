"""Combined FROZEN package overlay (Integration 2026-10-23): build_slim takes one --overlay folder, and the 2026-10-16 overlay
(work/gltf_wfcmat, FROZEN) is never rewritten. This folder carries its 85 files unchanged (sha-checked against its FROZEN.json) plus
the Seed PC adaptation (out/pc_adapt/MP_IAC_Seed: collision_pawn.glb, physics.json) at their ExtractedAssets-relative paths.
Refuses to run once FROZEN.json exists here.
"""
import datetime, hashlib, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
BASE = os.path.join(AT, 'work', 'gltf_wfcmat')
ADD = {'VerticalSlice/Maps/MP_IAC_Seed/collision_pawn.glb': os.path.join(AT, 'out', 'pc_adapt', 'MP_IAC_Seed', 'collision_pawn.glb'),
       'VerticalSlice/Maps/MP_IAC_Seed/physics.json': os.path.join(AT, 'out', 'pc_adapt', 'MP_IAC_Seed', 'physics.json')}

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def main():
    if os.path.exists(os.path.join(HERE, 'FROZEN.json')): sys.exit('FROZEN.json exists: this overlay is frozen')
    base = json.load(open(os.path.join(BASE, 'FROZEN.json'), encoding='utf-8'))
    files = []
    for f in base['files']:
        src = os.path.join(BASE, f['path'])
        if os.path.getsize(src) != int(f['bytes']) or sha(src) != f['sha256'].lower(): sys.exit('base overlay file changed: ' + f['path'])
        files.append((f['path'], src, 'push_gltf_wfcmat_20261016'))
    files += [(rel, src, 'seed_pc_adapt (playtest 2026-10-23 #10/#13)') for rel, src in ADD.items()]
    out = []
    for rel, src, origin in files:
        dst = os.path.join(HERE, *rel.split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst)
        out.append({'path': rel, 'bytes': os.path.getsize(dst), 'sha256': sha(dst), 'origin': origin})
    commit = subprocess.run(['git', '-C', AT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    fz = {'frozen': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'name': 'push_overlay_20261023', 'commit': commit,
          'note': 'FROZEN overlay for build_slim --overlay: push_gltf_wfcmat_20261016 (85 files, unchanged) + Seed PC adaptation '
                  '(BlockingVolume_9745 dropped, per-poly pawn collision on 40 meshes; divergence note in physics.json pc_adaptation). '
                  'Never rewritten (make_overlay.py refuses while this file exists).', 'files': out}
    json.dump(fz, open(os.path.join(HERE, 'FROZEN.json'), 'w', encoding='utf-8'), indent=1)
    print(len(out), 'files', sum(f['bytes'] for f in out), 'bytes; commit', commit)

if __name__ == '__main__':
    main()
