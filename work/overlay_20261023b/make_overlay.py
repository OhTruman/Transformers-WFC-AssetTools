"""FROZEN package overlay push_overlay_20261023b: push_overlay_20261023 (87 files, unchanged, sha-checked against its FROZEN.json)
plus the Seed bot navigation rebuilt on the PC-adapted collision (bot_nav.py / bot_nav_air.py --overlay out/pc_adapt/MP_IAC_Seed
--out out/pc_adapt/MP_IAC_Seed; Gameplay's BOTTEST found the original nav and the adapted collision disagree near the central hole).
Same ExtractedAssets-relative layout; build_slim --overlay / Gameplay WFC_OVERLAY_ROOT. Refuses to run once FROZEN.json exists.
"""
import datetime, hashlib, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
BASE = os.path.join(AT, 'work', 'overlay_20261023')
SEED = os.path.join(AT, 'out', 'pc_adapt', 'MP_IAC_Seed')
ADD = {'VerticalSlice/Maps/MP_IAC_Seed/' + f: os.path.join(SEED, f) for f in ('bot_nav.json', 'bot_nav.glb', 'bot_nav_air.json')}

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def main():
    if os.path.exists(os.path.join(HERE, 'FROZEN.json')): sys.exit('FROZEN.json exists: this overlay is frozen')
    base = json.load(open(os.path.join(BASE, 'FROZEN.json'), encoding='utf-8'))
    files = []
    for f in base['files']:
        src = os.path.join(BASE, *f['path'].split('/'))
        if os.path.getsize(src) != int(f['bytes']) or sha(src) != f['sha256'].lower(): sys.exit('base overlay file changed: ' + f['path'])
        files.append((f['path'], src, f.get('origin', base['name'])))
    files += [(rel, src, 'seed_pc_adapt nav (bot_nav / bot_nav_air on the adapted collision)') for rel, src in ADD.items()]
    out = []
    for rel, src, origin in files:
        dst = os.path.join(HERE, *rel.split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst)
        out.append({'path': rel, 'bytes': os.path.getsize(dst), 'sha256': sha(dst), 'origin': origin})
    commit = subprocess.run(['git', '-C', AT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    fz = {'frozen': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'name': 'push_overlay_20261023b', 'commit': commit,
          'supersedes': base['name'],
          'note': 'FROZEN overlay for build_slim --overlay and Gameplay WFC_OVERLAY_ROOT: push_overlay_20261023 (87 files, unchanged) + '
                  'Seed bot_nav.json / bot_nav.glb / bot_nav_air.json rebuilt on the PC-adapted collision. Never rewritten.', 'files': out}
    json.dump(fz, open(os.path.join(HERE, 'FROZEN.json'), 'w', encoding='utf-8'), indent=1)
    print(len(out), 'files', sum(f['bytes'] for f in out), 'bytes; commit', commit)

if __name__ == '__main__':
    main()
