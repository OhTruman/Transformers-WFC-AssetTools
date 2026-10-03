"""Summarize a second-map pipeline probe (stages run through run_bounded.py with logs in logs/<map>_probe or logs/gorge_probe).

Reads the run_bounded result lines (rc, wall time, peak job memory), the produced ExtractedAssets/VerticalSlice/Maps/<MAP>
files and the validators' reports; writes manifests/next_map/<MAP>_probe.json.
  python next_map_probe_summary.py MP_UND_Gorge logs/gorge_probe
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import VS  # noqa: E402

MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
ROOT_AT = os.path.normpath(os.path.join(HERE, '..', '..'))

def main():
    mp, logdir = sys.argv[1], sys.argv[2]
    rx = re.compile(r'run_bounded: rc=(-?\d+)\s+wall=([\d.]+)s\s+peak_job_memory=([\d.]+) GB\s+cap=([\d.]+) GB\s+cmd=(.*)')
    runs = []
    for f in sorted(glob.glob(os.path.join(ROOT_AT, logdir, '*.log')), key=os.path.getmtime):
        txt = open(f, encoding='utf-8', errors='replace').read()
        m = rx.search(txt)
        tail = [l for l in txt.strip().splitlines() if not l.startswith('run_bounded')][-1:] if txt.strip() else []
        runs.append({'log': os.path.relpath(f, ROOT_AT).replace(os.sep, '/'),
                     **({'rc': int(m.group(1)), 'wall_s': float(m.group(2)), 'peak_gb': float(m.group(3)), 'cap_gb': float(m.group(4)),
                         'cmd': m.group(5)} if m else {'note': 'no run_bounded line (stdout went to console)'}),
                     'last_line': tail[0][:300] if tail else None})
    out_dir = os.path.join(VS, 'Maps', mp)
    files = {os.path.relpath(p, out_dir).replace(os.sep, '/'): os.path.getsize(p)
             for p in glob.glob(os.path.join(out_dir, '**', '*'), recursive=True) if os.path.isfile(p)}
    rep = {}
    for n in (mp + '_validation.json', mp + '_transform_validation.json'):
        p = os.path.join(MANI, 'next_map', n)
        if os.path.exists(p):
            j = json.load(open(p, encoding='utf-8'))
            rep[n] = {'failures': j.get('failures') if not isinstance(j.get('failures'), list) else len(j['failures']),
                      'checks': len(j.get('checks', [])) if isinstance(j.get('checks'), list) else None, 'stats': j.get('stats')}
    last = {}
    for r in runs:
        if 'cmd' in r: last[r['cmd']] = r
    json.dump({'map': mp, 'generated_by': 'AssetTools/scripts/wfc/next_map_probe_summary.py',
               'stage_runs (chronological, incl. failed first attempts)': runs,
               'final_state_per_command': last,
               'peak_memory_gb (max over final runs)': max((r['peak_gb'] for r in last.values()), default=None),
               'outputs (ExtractedAssets/VerticalSlice/Maps/%s, bytes)' % mp: files,
               'validators': rep}, open(os.path.join(MANI, 'next_map', mp + '_probe.json'), 'w', encoding='utf-8'), indent=1)
    print('runs', len(runs), 'final', {k: v['rc'] for k, v in last.items()}, 'files', len(files))

if __name__ == '__main__':
    main()
