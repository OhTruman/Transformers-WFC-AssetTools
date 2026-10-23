"""Stage a refresh of the package slim list (Integration 2026-10-18; Systems adopts it at the package step).

Reads AssetTools/out/package/slim_files.tsv (read-only; never modified) and writes beside it slim_files.refresh.tsv:
same header, same row order, same columns and line endings; for every keep / xpr row the bytes column is re-measured from the source
file on disk; rows whose source is gone are kept unchanged and reported (nothing is removed); ADD lists rows to append.
Report: work/handoff/SLIM_REFRESH.json + .md (rows changed / added / missing, totals before / after, render-file mtimes measured).
Rerun at the head (after the last render regen) to re-measure.
"""
import datetime, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(ROOT)
TSV = os.path.join(ROOT, 'out', 'package', 'slim_files.tsv')
OUT = os.path.join(ROOT, 'out', 'package', 'slim_files.refresh.tsv')
# rows the audit found missing from the list and Systems confirmed as real gaps (PACKAGE7_SLIM_AUDIT.md resolution): pc_strings.int is
# already appended to the live tsv (2026-10-18); the other 25 need no row (build_slim adds them / case match / runtime user file)
# package 7 head deed7f1a (Integration 2026-10-18): Rendering's loader reads <map>/lens_flares.json next to materials_glsl.json
ADD = [('Transformers Rebuild/Rebuild/work/render/%s/lens_flares.json' % m, 'Rebuild/work/render/%s/lens_flares.json' % m, 'keep')
       for m in ('MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_ORB_Debris', 'MP_UND_Gorge')]
# Gameplay e33a2c85 (Integration 2026-10-23): read through frontendDataFile like pc_strings.int
ADD.append(('Transformers Rebuild/Rebuild/data/frontend/bot_skill.json', 'Rebuild/data/frontend/bot_skill.json', 'keep'))

# Escalation horde runtime packaging (Integration 2026-10-23): every file under these AssetTools dirs ships, same dest form
ADD_DIRS = ['AssetTools/out/escalation_characters',
            'AssetTools/out/campaign_anims']   # the boss tank's robot set glTF (converted .psa) lives here; Integration 2026-10-23
for _d in ADD_DIRS:
    for _r, _, _fs in os.walk(os.path.join(TR, _d)):
        for _f in sorted(_fs):
            _src = os.path.relpath(os.path.join(_r, _f), TR).replace(os.sep, '/')
            ADD.append(('Transformers Rebuild/' + _src, _src, 'keep'))

def main():
    raw = open(TSV, 'rb').read().decode('utf-8')
    # the live file mixes endings: the generated rows end CRLF, the 11 rows AssetTools appended on 2026-10-18 (10 physmat +
    # pc_strings.int) end LF. Parse both; write the dominant ending throughout.
    n_crlf = raw.count('\r\n'); n_lf_only = raw.count('\n') - n_crlf
    nl = '\r\n' if n_crlf >= n_lf_only else '\n'
    lines = raw.splitlines()
    trailing = raw.endswith('\n')
    head, rows = lines[0], lines[1:]
    out, changed, missing = [head], [], []
    tot_before = tot_after = 0
    for ln in rows:
        f = ln.split('\t')
        if len(f) >= 4 and f[3] in ('keep', 'xpr') and f[2].isdigit():
            b = int(f[2]); tot_before += b
            src = os.path.join(TR, f[1])
            if os.path.exists(src):
                n = os.path.getsize(src)
                if n != b:
                    changed.append({'source': f[1], 'before': b, 'after': n, 'delta': n - b,
                                    'mtime': datetime.datetime.fromtimestamp(os.path.getmtime(src)).strftime('%Y-%m-%d %H:%M')})
                    f[2] = str(n)
                tot_after += n
            else:
                missing.append(f[1]); tot_after += b
        out.append('\t'.join(f))
    have = {ln.split('\t')[1] for ln in rows if '\t' in ln}
    added = []
    for dest, src, action in ADD:
        if src in have: continue
        n = os.path.getsize(os.path.join(TR, src)); out.append('\t'.join([dest, src, str(n), action, ''])); added.append(src)
        tot_after += n
    open(OUT, 'wb').write((nl.join(out) + (nl if trailing else '')).encode('utf-8'))
    rep = {'generated_by': 'AssetTools/scripts/wfc/slim_refresh.py', 'measured': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
           'live_tsv': 'AssetTools/out/package/slim_files.tsv (unchanged)', 'refresh_tsv': 'AssetTools/out/package/slim_files.refresh.tsv',
           'rows': len(rows), 'rows_out': len(out) - 1,
           'line_endings': {'live_crlf_rows': n_crlf, 'live_lf_only_rows': n_lf_only,
                            'refresh_written_with': 'CRLF' if nl == '\r\n' else 'LF'}, 'rows_changed': len(changed), 'rows_added': added, 'rows_source_missing': missing,
           'keep_bytes_before': tot_before, 'keep_bytes_after': tot_after, 'delta_bytes': tot_after - tot_before,
           'changed': sorted(changed, key=lambda x: x['source'])}
    json.dump(rep, open(os.path.join(ROOT, 'work', 'handoff', 'SLIM_REFRESH.json'), 'w', encoding='utf-8'), indent=1)
    md = ['# Slim list refresh (staged; Systems adopts at the package step)', '',
          'Measured %s. Live `out/package/slim_files.tsv` untouched; refreshed copy `out/package/slim_files.refresh.tsv` (same rows, '
          'order, columns, line endings; only the bytes column of keep / xpr rows re-measured). Generator `scripts/wfc/slim_refresh.py` '
          '(rerun at the head).' % rep['measured'], '',
          '| | value |', '|---|---|', '| rows | %d -> %d |' % (len(rows), len(out) - 1), '| rows with a changed byte count | %d |' % len(changed),
          '| rows added | %d |' % len(added),
          '| line endings | live: %d CRLF + %d LF-only rows (the LF ones are AssetTools appends of 2026-10-18); refresh: all %s |' % (
              n_crlf, n_lf_only, 'CRLF' if nl == '\r\n' else 'LF'), '| rows whose source is missing (kept) | %d |' % len(missing),
          '| keep / xpr bytes | %s -> %s (%+d) |' % (format(tot_before, ','), format(tot_after, ','), tot_after - tot_before), '',
          '## Changed rows', '', '| source | before | after | delta | file mtime |', '|---|---|---|---|---|']
    md += ['| `%s` | %s | %s | %+d | %s |' % (c['source'], format(c['before'], ','), format(c['after'], ','), c['delta'], c['mtime']) for c in rep['changed']]
    if missing: md += ['', '## Sources missing (rows kept)', ''] + ['- `%s`' % m for m in missing]
    open(os.path.join(ROOT, 'work', 'handoff', 'SLIM_REFRESH.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    print(json.dumps({k: v for k, v in rep.items() if k != 'changed'}))

if __name__ == '__main__':
    main()
