"""FROZEN package overlay push_overlay_20261023c (supersedes push_overlay_20261023b): the 85 push_gltf_wfcmat_20261016 files (unchanged,
sha-checked against work/gltf_wfcmat/FROZEN.json) + the PC-adapted pawn collision and nav of every versus map with an out/pc_adapt/<MAP>
adaptation (Gameplay #18 raised simple hulls -> per-poly; Seed also #10 / #13): VerticalSlice/Maps/<MAP>/{collision_pawn.glb,
physics.json, bot_nav.json, bot_nav.glb, bot_nav_air.json}. Each file must name exactly one keep / xpr row of the live slim list.
build_slim --overlay / Gameplay WFC_OVERLAY_ROOT. Refuses to run once FROZEN.json exists.
"""
import datetime, hashlib, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
BASE = os.path.join(AT, 'work', 'gltf_wfcmat')
PCA = os.path.join(AT, 'out', 'pc_adapt')
FILES = ('collision_pawn.glb', 'physics.json', 'bot_nav.json', 'bot_nav.glb', 'bot_nav_air.json')
TSV = os.path.join(AT, 'out', 'package', 'slim_files.tsv')

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def main():
    if os.path.exists(os.path.join(HERE, 'FROZEN.json')): sys.exit('FROZEN.json exists: this overlay is frozen')
    rows = {}
    for ln in open(TSV, 'rb').read().decode('utf-8').splitlines()[1:]:
        f = ln.split('\t')
        if len(f) >= 4 and f[3] in ('keep', 'xpr'): rows.setdefault(f[1], []).append(f)
    base = json.load(open(os.path.join(BASE, 'FROZEN.json'), encoding='utf-8'))
    files = []
    for f in base['files']:
        src = os.path.join(BASE, *f['path'].split('/'))
        if os.path.getsize(src) != int(f['bytes']) or sha(src) != f['sha256'].lower(): sys.exit('base overlay file changed: ' + f['path'])
        files.append((f['path'], src, base['name']))
    maps = sorted(m for m in os.listdir(PCA) if m.startswith('MP_') and all(os.path.exists(os.path.join(PCA, m, x)) for x in FILES))
    for m in maps:
        for x in FILES: files.append(('VerticalSlice/Maps/%s/%s' % (m, x), os.path.join(PCA, m, x), 'pc_adapt %s' % m))
    bad = [rel for rel, _, _ in files if len(rows.get('ExtractedAssets/' + rel, [])) != 1]
    if bad: sys.exit('files without exactly one slim row: %s' % bad)
    out = []
    for rel, src, origin in files:
        dst = os.path.join(HERE, *rel.split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst)
        out.append({'path': rel, 'bytes': os.path.getsize(dst), 'sha256': sha(dst), 'origin': origin})
    commit = subprocess.run(['git', '-C', AT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    fz = {'frozen': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'name': 'push_overlay_20261023c', 'commit': commit,
          'supersedes': 'push_overlay_20261023b', 'maps': maps,
          'note': 'FROZEN overlay for build_slim --overlay and Gameplay WFC_OVERLAY_ROOT: push_gltf_wfcmat_20261016 (85, unchanged) + PC-adapted '
                  'pawn collision / physics / bot nav of %d versus maps (divergence notes in each physics.json pc_adaptation and '
                  'out/pc_adapt/<MAP>/pc_adapt_manifest.json). Never rewritten.' % len(maps), 'files': out}
    json.dump(fz, open(os.path.join(HERE, 'FROZEN.json'), 'w', encoding='utf-8'), indent=1)
    print(len(out), 'files', sum(f['bytes'] for f in out), 'bytes; maps', len(maps), maps)

if __name__ == '__main__':
    main()
