"""FROZEN package overlay push_overlay_20261023d (supersedes push_overlay_20261023c; Integration 2026-10-23 after Gameplay's three-arm
test): the 85 push_gltf_wfcmat_20261016 files (unchanged) + for all 10 versus maps the PC-adapted collision_pawn.glb / physics.json
(out/pc_adapt/<MAP>), but the REBUILT bot nav only where it tested better: BrokenHope and Remnant (Integration), and Seed (its original nav
no longer fits its adapted collision: off-mesh 25 %; the rebuilt one 3.2 %; candidate v3 under test). Every other map keeps the shipped
nav (no nav files in the overlay). Each file must name exactly one keep / xpr row of the live slim list. Refuses to run once FROZEN.json
exists.

    python make_overlay.py            freeze push_overlay_20261023d here
    python make_overlay.py candidate  (no freeze) out/pc_adapt/_candidates/seed_nav_v3: an overlay-layout root with Seed's collision +
                                      the v3 nav (out/pc_adapt/MP_IAC_Seed/nav_v3), for Gameplay's A/B via WFC_OVERLAY_ROOT
"""
import datetime, hashlib, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
BASE = os.path.join(AT, 'work', 'gltf_wfcmat'); PCA = os.path.join(AT, 'out', 'pc_adapt')
TSV = os.path.join(AT, 'out', 'package', 'slim_files.tsv')
MAPS = ['MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_IAC_Streets', 'MP_KON_Molten',
        'MP_ORB_Debris', 'MP_UND_Complex', 'MP_UND_Gorge']
COLL = ('collision_pawn.glb', 'physics.json'); NAV = ('bot_nav.json', 'bot_nav.glb', 'bot_nav_air.json')
NAV_MAPS = {'MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Seed'}

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def copy_all(files, root):
    out = []
    for rel, src, origin in files:
        dst = os.path.join(root, *rel.split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst)
        out.append({'path': rel, 'bytes': os.path.getsize(dst), 'sha256': sha(dst), 'origin': origin})
    return out

def candidate():
    root = os.path.join(PCA, '_candidates', 'seed_nav_v3'); m = 'MP_IAC_Seed'
    files = [('VerticalSlice/Maps/%s/%s' % (m, x), os.path.join(PCA, m, x), 'pc_adapt collision') for x in COLL]
    files += [('VerticalSlice/Maps/%s/%s' % (m, x), os.path.join(PCA, m, 'nav_v3', x), 'seed nav v3 (shipped collision + #13 hulls)') for x in NAV]
    out = copy_all(files, root)
    json.dump({'name': 'candidate seed_nav_v3 (not frozen, not for packaging)', 'files': out}, open(os.path.join(root, 'CANDIDATE.json'), 'w', encoding='utf-8'), indent=1)
    print('candidate', root, len(out), 'files')

def main():
    if os.path.exists(os.path.join(HERE, 'FROZEN.json')): sys.exit('FROZEN.json exists: this overlay is frozen')
    rows = {}
    for ln in open(TSV, 'rb').read().decode('utf-8').splitlines()[1:]:
        f = ln.split('\t')
        if len(f) >= 4 and f[3] in ('keep', 'xpr'): rows.setdefault(f[1], []).append(f)
    base = json.load(open(os.path.join(BASE, 'FROZEN.json'), encoding='utf-8')); files = []
    for f in base['files']:
        src = os.path.join(BASE, *f['path'].split('/'))
        if os.path.getsize(src) != int(f['bytes']) or sha(src) != f['sha256'].lower(): sys.exit('base overlay file changed: ' + f['path'])
        files.append((f['path'], src, base['name']))
    for m in MAPS:
        for x in COLL + (NAV if m in NAV_MAPS else ()):
            files.append(('VerticalSlice/Maps/%s/%s' % (m, x), os.path.join(PCA, m, x), 'pc_adapt %s' % m))
    bad = [rel for rel, _, _ in files if len(rows.get('ExtractedAssets/' + rel, [])) != 1]
    if bad: sys.exit('files without exactly one slim row: %s' % bad)
    out = copy_all(files, HERE)
    commit = subprocess.run(['git', '-C', AT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    fz = {'frozen': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'name': 'push_overlay_20261023d', 'commit': commit,
          'supersedes': 'push_overlay_20261023c', 'maps_collision': MAPS, 'maps_rebuilt_nav': sorted(NAV_MAPS),
          'note': 'FROZEN overlay for build_slim --overlay and Gameplay WFC_OVERLAY_ROOT: push_gltf_wfcmat_20261016 (85, unchanged) + PC-adapted '
                  'pawn collision / physics of the 10 versus maps; rebuilt bot nav only for BrokenHope, Remnant and Seed (Gameplay three-arm '
                  'test, Integration 2026-10-23); every other map keeps its shipped nav. Never rewritten.', 'files': out}
    json.dump(fz, open(os.path.join(HERE, 'FROZEN.json'), 'w', encoding='utf-8'), indent=1)
    print(len(out), 'files', sum(f['bytes'] for f in out), 'bytes; nav maps', sorted(NAV_MAPS))

if __name__ == '__main__':
    candidate() if sys.argv[1:] == ['candidate'] else main()
