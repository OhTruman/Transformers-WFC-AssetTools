"""FROZEN package overlay push_overlay_20261023h (supersedes push_overlay_20261023g; Integration 2026-10-23): overlay g unchanged
(sha-checked against its FROZEN.json) except collision_pawn.glb + physics.json of the maps whose pawn collision held light cards
(BrokenHope 1, Remnant 22, Berth 1, Molten 8, Debris 20, Complex 12 placements; work/playtest_20261023/drop_light_cards.py), taken from
out/pc_adapt/_candidates/lightcards. Each file must name exactly one keep / xpr row of the live slim list. Refuses to run once FROZEN.json exists.
"""
import datetime, hashlib, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
G = os.path.join(AT, 'work', 'overlay_20261023g'); C = os.path.join(AT, 'out', 'pc_adapt', '_candidates', 'lightcards')
TSV = os.path.join(AT, 'out', 'package', 'slim_files.tsv')
MAPS = ('MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_KON_Molten', 'MP_ORB_Debris', 'MP_UND_Complex')
REPL = {'VerticalSlice/Maps/%s/%s' % (m, f): os.path.join(C, 'VerticalSlice', 'Maps', m, f) for m in MAPS for f in ('collision_pawn.glb', 'physics.json')}

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def main():
    if os.path.exists(os.path.join(HERE, 'FROZEN.json')): sys.exit('FROZEN.json exists: this overlay is frozen')
    rows = {}
    for ln in open(TSV, 'rb').read().decode('utf-8').splitlines()[1:]:
        f = ln.split('\t')
        if len(f) >= 4 and f[3] in ('keep', 'xpr'): rows.setdefault(f[1], []).append(f)
    base = json.load(open(os.path.join(G, 'FROZEN.json'), encoding='utf-8')); out = []
    for f in base['files']:
        if f['path'] in REPL: src, origin = REPL[f['path']], 'light cards out of pawn collision'
        else:
            src, origin = os.path.join(G, *f['path'].split('/')), 'overlay g'
            if os.path.getsize(src) != int(f['bytes']) or sha(src) != f['sha256'].lower(): sys.exit('overlay g file changed: ' + f['path'])
        if len(rows.get('ExtractedAssets/' + f['path'], [])) != 1: sys.exit('no single slim row: ' + f['path'])
        dst = os.path.join(HERE, *f['path'].split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst)
        out.append({'path': f['path'], 'bytes': os.path.getsize(dst), 'sha256': sha(dst), 'origin': origin})
    if sum(1 for x in out if x['path'] in REPL) != len(REPL): sys.exit('not every replacement applied')
    commit = subprocess.run(['git', '-C', AT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    json.dump({'frozen': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'name': 'push_overlay_20261023h', 'commit': commit,
               'supersedes': 'push_overlay_20261023g',
               'note': 'FROZEN overlay for build_slim --overlay and Gameplay WFC_OVERLAY_ROOT: overlay g unchanged except the pawn collision / physics '
                       'of 6 maps with light cards (64 placements) removed from pawn collision (PC adaptation; Remnant perch exit). Never rewritten.',
               'files': out}, open(os.path.join(HERE, 'FROZEN.json'), 'w', encoding='utf-8'), indent=1)
    print(len(out), 'files', sum(f['bytes'] for f in out), 'bytes; replaced', len(REPL))

if __name__ == '__main__':
    main()
