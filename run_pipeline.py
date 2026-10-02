"""One command: Game Dump (read-only) -> ExtractedAssets + AssetTools/manifests.

    AssetTools\\bin\\py\\python.exe AssetTools\\run_pipeline.py            # everything
    AssetTools\\bin\\py\\python.exe AssetTools\\run_pipeline.py --skip movies
    AssetTools\\bin\\py\\python.exe AssetTools\\run_pipeline.py --only build_db maps

Steps are idempotent; umodel runs with -nooverwrite.  Tool binaries are
fetched by setup_tools.ps1 into AssetTools/bin.
"""
import argparse, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
S = os.path.join(HERE, 'scripts', 'wfc')
STEPS = [
    ('inventory', [PY, os.path.join(S, 'inventory.py')]),
    ('extract',   [PY, os.path.join(S, 'extract.py'), 'textures', 'static_meshes', 'skeletal_meshes',
                   'materials', 'animations', 'audio', 'ui', 'facefx']),
    ('sounds',    [PY, os.path.join(S, 'sounds.py')]),          # native FSB fix + WAV
    ('build_db',  [PY, os.path.join(S, 'build_db.py')]),
    ('anims',     [PY, os.path.join(S, 'psa2gltf.py')]),
    ('build_db2', [PY, os.path.join(S, 'build_db.py')]),        # pick up .anim.gltf outputs
    ('maps',      [PY, os.path.join(S, 'maps.py')]),
    ('config',    [PY, os.path.join(S, 'coalesced.py')]),
    ('movies',    [PY, os.path.join(S, 'movies.py')]),
    ('high_value', [PY, os.path.join(S, 'high_value.py')]),
    # vertical slice: Optimus + Ion Blaster + MP_IAC_Streets, then programmatic validation
    # (vs_lightmap.py stays manual: it joins against props.json, which vs_map reads lightmaps.json to build)
    ('vs_map',       [PY, os.path.join(S, 'vs_map.py'), 'MP_IAC_Streets']),
    ('vs_collision', [PY, os.path.join(S, 'vs_collision.py')]),      # vs_map resets collision.glb
    ('vs_physics',   [PY, os.path.join(S, 'vs_physics.py'), 'MP_IAC_Streets']),  # needs authored.db; collision_pawn/weapon.glb
    ('vs_mapfx',     [PY, os.path.join(S, 'vs_mapfx.py'), 'MP_IAC_Streets']),
    ('vs_audio',     [PY, os.path.join(S, 'vs_audio.py'), 'MP_IAC_Streets']),    # needs manifests/authored.db
    ('vs_lighting',  [PY, os.path.join(S, 'vs_lighting.py'), 'MP_IAC_Streets']), # needs manifests/authored.db
    ('vs_postprocess', [PY, os.path.join(S, 'vs_postprocess.py'), 'MP_IAC_Streets']),  # needs manifests/authored.db
    ('vs_gameplay',  [PY, os.path.join(S, 'vs_gameplay.py'), 'MP_IAC_Streets']),  # needs manifests/authored.db + config
    ('vs_navigation', [PY, os.path.join(S, 'vs_navigation.py'), 'MP_IAC_Streets']),  # needs manifests/authored.db
    ('vs_materials', [PY, os.path.join(S, 'vs_materials.py'), 'MP_IAC_Streets']),  # needs manifests/authored.db (after vs_mapfx)
    ('vs_character', [PY, os.path.join(S, 'vs_character.py')]),
    ('vs_weapon',    [PY, os.path.join(S, 'vs_weapon.py')]),
    ('vs_validate',  [PY, os.path.join(S, 'vs_validate.py')]),
    ('vs_evidence',  [PY, os.path.join(S, 'vs_evidence.py')]),       # targeted authored-evidence manifest
    ('vs_character_materials', [PY, os.path.join(S, 'vs_character_materials.py')]),  # Optimus material handoff
    ('vs_evidence2', [PY, os.path.join(S, 'vs_evidence2.py')]),      # pass-2 manifest (needs the steps above)
    # vs_props.py (props_authored.json) is a checkpointed, validated pass kept OUT of the pipeline on request
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*'); ap.add_argument('--skip', nargs='*', default=[])
    a = ap.parse_args()
    t0 = time.time()
    for name, cmd in STEPS:
        if a.only and name not in a.only: continue
        if name in a.skip: continue
        print('==> %s' % name, flush=True); t = time.time()
        r = subprocess.run(cmd)
        print('<== %s rc=%d %.0fs' % (name, r.returncode, time.time() - t), flush=True)
        if r.returncode: sys.exit(r.returncode)
    print('pipeline done in %.0fs' % (time.time() - t0))

if __name__ == '__main__':
    main()
