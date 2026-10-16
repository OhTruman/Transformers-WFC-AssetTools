"""Proof that the campaign changes leave the MP outputs unchanged (Integration 2026-10-16): run validate_smca_transforms and vs_validate
for the 10 MP maps (run_bounded, hold-aware), hash what they write, then restore the original files (the canonical manifests stay as
they were). Also hashes ExtractedAssets/VerticalSlice/Maps/MP_* (read only; the validators must not write there).

  python campaign_mp_proof.py before|after      -> work/campaign_pilot/mp_proof/<tag>.json
  python campaign_mp_proof.py compare           -> prints per file: identical / identical except 'generated' / DIFFERENT
"""
import hashlib, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.dirname(os.path.dirname(HERE)); MANI = os.path.join(AT, 'manifests')
EA_MAPS = os.path.join(os.path.dirname(AT), 'ExtractedAssets', 'VerticalSlice', 'Maps')
OUT = os.path.join(AT, 'work', 'campaign_pilot', 'mp_proof')
MAPS = ['MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_IAC_Streets', 'MP_KON_Molten',
        'MP_ORB_Debris', 'MP_UND_Complex', 'MP_UND_Gorge']

def outputs(m):
    if m == 'MP_IAC_Streets':
        return [os.path.join(MANI, f) for f in ('streets_transform_validation.json', 'streets_transform_fix_audit.json',
                                                 'vertical_slice_validation.json', 'vertical_slice.json')]
    return [os.path.join(MANI, 'next_map', m + s) for s in ('_transform_validation.json', '_transform_audit.json', '_validation.json')]

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest() if os.path.exists(p) else None
def sha_norm(p):
    if not os.path.exists(p): return None
    d = json.load(open(p, encoding='utf-8'))
    if isinstance(d, dict): d.pop('generated', None)
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()

def run(tag):
    os.makedirs(OUT, exist_ok=True); bak = os.path.join(OUT, 'orig'); res = {'files': {}, 'rc': {}, 'extracted_maps': {}}
    for m in MAPS:
        for p in outputs(m):
            b = os.path.join(bak, os.path.relpath(p, MANI))
            if os.path.exists(p) and not os.path.exists(b): os.makedirs(os.path.dirname(b), exist_ok=True); shutil.copy2(p, b)
    try:
        for m in MAPS:
            for cmd in (['validate_smca_transforms.py'] + ([] if m == 'MP_IAC_Streets' else ['--map', m]), ['vs_validate.py', m]):
                r = subprocess.run([sys.executable, os.path.join(HERE, 'run_bounded.py'), '--cap-gb', '6', '--log',
                                    os.path.join(OUT, '%s_%s_%s.log' % (tag, m, cmd[0][:-3])), '--', os.path.join(HERE, cmd[0])] + cmd[1:],
                                   cwd=AT, capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != 'WFC_VS_ROOT'})
                if r.returncode == 75: sys.exit('PERF_HOLD: stopped, originals restored')
                res['rc']['%s %s' % (m, cmd[0])] = r.returncode
            for p in outputs(m): res['files'][os.path.relpath(p, MANI)] = {'sha256': sha(p), 'sha256_without_generated': sha_norm(p)}
            print(m, 'done', flush=True)
    finally:
        for m in MAPS:
            for p in outputs(m):
                b = os.path.join(bak, os.path.relpath(p, MANI))
                if os.path.exists(b): shutil.copy2(b, p)
    for d, _, fs in os.walk(EA_MAPS):
        if os.path.relpath(d, EA_MAPS).split(os.sep)[0] in MAPS:
            for f in fs: res['extracted_maps'][os.path.relpath(os.path.join(d, f), EA_MAPS)] = sha(os.path.join(d, f))
    json.dump(res, open(os.path.join(OUT, tag + '.json'), 'w'), indent=1)
    print(tag, len(res['files']), 'validator outputs,', len(res['extracted_maps']), 'ExtractedAssets MP files hashed', flush=True)

def compare():
    a, b = (json.load(open(os.path.join(OUT, t + '.json'))) for t in ('before', 'after'))
    n = {'identical': 0, "identical except 'generated'": 0, 'DIFFERENT': 0}
    for f in sorted(a['files']):
        x, y = a['files'][f], b['files'].get(f, {})
        k = 'identical' if x['sha256'] == y.get('sha256') else "identical except 'generated'" if x['sha256_without_generated'] == y.get('sha256_without_generated') else 'DIFFERENT'
        n[k] += 1; print('%-30s %s' % (k, f))
    print('rc equal:', a['rc'] == b['rc']); print('ExtractedAssets MP files identical:', a['extracted_maps'] == b['extracted_maps'], len(a['extracted_maps']))
    print(n)

if __name__ == '__main__':
    compare() if sys.argv[1] == 'compare' else run(sys.argv[1])
