"""FROZEN package overlay push_overlay_20261023e (supersedes push_overlay_20261023d; Integration 2026-10-23 after Gameplay's Seed nav A/B:
stucks 0.84 / 0.96 vs 2.44 / 3.23 per bot-minute, failed searches 0.48 / 0.54 vs 1.21 / 4.75, 0 floating): overlay d's files unchanged
(sha-checked against its FROZEN.json) except Seed's bot_nav.json / bot_nav.glb / bot_nav_air.json, which come from the v3 nav
(out/pc_adapt/MP_IAC_Seed/nav_v3: built on the shipped Seed collision + the authored hulls of the 40 #13 placements). Each file must
name exactly one keep / xpr row of the live slim list. Refuses to run once FROZEN.json exists.
"""
import datetime, hashlib, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
D = os.path.join(AT, 'work', 'overlay_20261023d'); V3 = os.path.join(AT, 'out', 'pc_adapt', 'MP_IAC_Seed', 'nav_v3')
TSV = os.path.join(AT, 'out', 'package', 'slim_files.tsv')
SEED_NAV = {'VerticalSlice/Maps/MP_IAC_Seed/' + x: os.path.join(V3, x) for x in ('bot_nav.json', 'bot_nav.glb', 'bot_nav_air.json')}

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def main():
    if os.path.exists(os.path.join(HERE, 'FROZEN.json')): sys.exit('FROZEN.json exists: this overlay is frozen')
    rows = {}
    for ln in open(TSV, 'rb').read().decode('utf-8').splitlines()[1:]:
        f = ln.split('\t')
        if len(f) >= 4 and f[3] in ('keep', 'xpr'): rows.setdefault(f[1], []).append(f)
    base = json.load(open(os.path.join(D, 'FROZEN.json'), encoding='utf-8')); out = []
    for f in base['files']:
        if f['path'] in SEED_NAV: src, origin = SEED_NAV[f['path']], 'seed nav v3 (Gameplay A/B)'
        else:
            src, origin = os.path.join(D, *f['path'].split('/')), f.get('origin', base['name'])
            if os.path.getsize(src) != int(f['bytes']) or sha(src) != f['sha256'].lower(): sys.exit('overlay d file changed: ' + f['path'])
        if len(rows.get('ExtractedAssets/' + f['path'], [])) != 1: sys.exit('no single slim row: ' + f['path'])
        dst = os.path.join(HERE, *f['path'].split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst)
        out.append({'path': f['path'], 'bytes': os.path.getsize(dst), 'sha256': sha(dst), 'origin': origin})
    if sum(1 for x in out if x['path'] in SEED_NAV) != 3: sys.exit('Seed nav files not all replaced')
    commit = subprocess.run(['git', '-C', AT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    fz = {'frozen': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'name': 'push_overlay_20261023e', 'commit': commit,
          'supersedes': 'push_overlay_20261023d', 'maps_collision': base.get('maps_collision'), 'maps_rebuilt_nav': base.get('maps_rebuilt_nav'),
          'note': 'FROZEN overlay for build_slim --overlay and Gameplay WFC_OVERLAY_ROOT: overlay d unchanged except Seed bot nav = v3 (shipped '
                  'collision + #13 authored hulls; Gameplay NAVQ A/B). Never rewritten.', 'files': out}
    json.dump(fz, open(os.path.join(HERE, 'FROZEN.json'), 'w', encoding='utf-8'), indent=1)
    print(len(out), 'files', sum(f['bytes'] for f in out), 'bytes')

if __name__ == '__main__':
    main()
