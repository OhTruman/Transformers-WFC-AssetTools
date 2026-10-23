"""INT subtitle sidecars for every campaign chapter (Systems 2026-10-23): authored.db keeps one row per object path, so a localized
SoundNodeWave(Ex) cooked into both a _LOC_int and a _LOC_FRA package is indexed with only one copy; where that copy is FRA, Systems'
generator saw only French. For each chapter: every SoundNodeWave / SoundNodeWaveEx whose authored row comes from a *_LOC_FRA package
while an export of the same path exists in one of the chapter's *_LOC_int packages; Subtitles + Duration read from the cooked INT copy
(Rendering's ue3obj.Repo, imported read-only). Writes manifests/campaign/<ch>_loc_int_subtitles.json ({waves: {opath: {package,
Subtitles, Duration}}}, the d5_loc_int_subtitles.json layout).
"""
import json, os, sqlite3, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(AT)
sys.path.insert(0, os.path.join(TR, 'Rebuild', 'tools', 'render'))
from ue3obj import Repo  # noqa: E402
CVS = os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice', 'Maps')

def main():
    inv = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db')); db = sqlite3.connect(os.path.join(AT, 'manifests', 'authored.db'))
    cooked = {f.lower(): f for f in os.listdir(os.path.join(TR, 'Game Dump', 'TransGame', 'CookedXenon'))}
    summary = {}
    for ch in sorted(os.listdir(CVS)):
        subs = json.load(open(os.path.join(CVS, ch, 'map.json'), encoding='utf-8'))['sublevels']
        ints = [s + '_LOC_int' for s in subs if (s + '_LOC_int.xxx').lower() in cooked]
        found = {}
        for pk in ints:
            for (o,) in inv.execute("select opath from exports where package=? and class in ('SoundNodeWave','SoundNodeWaveEx')", (pk,)):
                r = db.execute('select package from objects where opath=?', (o,)).fetchone()
                if r and r[0].lower().endswith('_loc_fra') and o not in found: found[o] = pk
        waves = {}
        by_pkg = {}
        for o, pk in found.items(): by_pkg.setdefault(pk, []).append(o)
        for pk, objs in by_pkg.items():
            rp = Repo([cooked[(pk + '.xxx').lower()]])
            for o in objs:
                d = rp.obj(o) or {}
                waves[o] = {'package': pk, 'Subtitles': d.get('Subtitles'), 'Duration': d.get('Duration')}
        name = ch.split('_')[0].lower()
        json.dump({'generated_by': 'AssetTools/work/campaign_hd/loc_int_subtitles.py (cooked _LOC_int read; authored.db kept the FRA copy)',
                   'chapter': ch, 'waves': waves}, open(os.path.join(AT, 'manifests', 'campaign', '%s_loc_int_subtitles.json' % name), 'w', encoding='utf-8'),
                  indent=1, ensure_ascii=False)
        summary[ch] = {'int_packages': len(ints), 'fra_only_rows_with_int_copy': len(found), 'with_subtitles': sum(1 for w in waves.values() if w['Subtitles'])}
        print(ch, summary[ch], flush=True)

if __name__ == '__main__':
    main()
