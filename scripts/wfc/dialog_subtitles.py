"""Per-language dialog wave table (Integration 2026-10-18): Duration + Subtitles of every localized SoundNodeWaveEx, read straight
from the cooked packages, INT and FRA separately. authored.db keeps one row per wave path, and the twins share that path, so the row
holds whichever language was parsed last (often FRA).

Sources: the bank packages WL_*_INT / WL_*_FRA and the map localisation packages <map>_LOC_int / _LOC_FRA (the cook copies waves
into both; a wave can live in only one of them). Read only; writes work/dialog/subtitles.json:
  {"<bank>.<wave>": {"INT": {"duration", "subtitles": [{t, text, use}], "sources": [pkg...]}, "FRA": {...}}}
Copies that disagree within one language are counted in "conflicts" (first source kept).

  python dialog_subtitles.py
"""
import json, os, sqlite3, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ue3pkg, typed_props as tp, extract  # noqa: E402

AT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(AT, 'work', 'dialog'); os.makedirs(OUT, exist_ok=True)

def lang_of(pkg):
    u = pkg.upper()
    if u.endswith(('_INT', '_LOC_INT')): return 'INT'
    if u.endswith(('_FRA', '_LOC_FRA')): return 'FRA'
    return None

def main():
    inv = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
    rows = inv.execute("SELECT package, idx, opath FROM exports WHERE class = 'SoundNodeWaveEx' AND "
                       "(package LIKE '%\\_INT' ESCAPE '\\' OR package LIKE '%\\_FRA' ESCAPE '\\' OR package LIKE '%\\_LOC\\_int' ESCAPE '\\' "
                       "OR package LIKE '%\\_LOC\\_FRA' ESCAPE '\\') ORDER BY package, idx").fetchall()
    by_pkg = {}
    for pkg, idx, opath in rows:
        if lang_of(pkg): by_pkg.setdefault(pkg, []).append((idx, opath))
    table = {}; stats = Counter(); conflicts = Counter(); errors = []
    for n, (pkg, items) in enumerate(sorted(by_pkg.items()), 1):
        lang = lang_of(pkg)
        try:
            p = ue3pkg.Package(os.path.join(extract.COOKED, pkg + '.xxx')); r = tp.TypedReader(p)
        except Exception as ex:
            errors.append({'package': pkg, 'error': str(ex)[:120]}); continue
        for idx, opath in items:
            # bank packages name the outer WL_X_INT / WL_X_FRA; map LOC copies keep the bank name -> key on <bank>.<wave>
            outer, wave = opath.split('.', 1)[0], opath.rsplit('.', 1)[-1]
            bank = outer[:-4] if outer.upper().endswith(('_INT', '_FRA')) else outer
            try:
                tags, _ = r.read_object(idx); d = tp.simplify(tp.to_dict(tags))
            except Exception as ex:
                stats['read_errors'] += 1; continue
            rec = {'duration': d.get('Duration'),
                   'subtitles': [{'t': s.get('Time'), 'text': s.get('Text'), 'use': s.get('UseSubtitles')} for s in d.get('Subtitles') or []]}
            key = '%s.%s' % (bank, wave); slot = table.setdefault(key, {})
            if lang in slot:
                if (slot[lang]['duration'], slot[lang]['subtitles']) != (rec['duration'], rec['subtitles']): conflicts[lang] += 1
                slot[lang]['sources'].append(pkg)
            else:
                rec['sources'] = [pkg]; slot[lang] = rec; stats['waves_' + lang] += 1
        if n % 50 == 0: print(n, '/', len(by_pkg), 'packages', flush=True)
    rep = {'generated_by': 'AssetTools/scripts/wfc/dialog_subtitles.py', 'packages': len(by_pkg), 'stats': dict(stats),
           'conflicts_within_language': dict(conflicts), 'package_errors': errors, 'waves': table}
    json.dump(rep, open(os.path.join(OUT, 'subtitles.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    both = sum(1 for v in table.values() if 'INT' in v and 'FRA' in v)
    print(json.dumps({'packages': len(by_pkg), 'waves': len(table), 'with_both': both, **stats, 'conflicts': dict(conflicts), 'package_errors': len(errors)}))

if __name__ == '__main__':
    main()
