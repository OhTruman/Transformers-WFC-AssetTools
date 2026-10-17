"""Gate for the campaign pickup change (Integration 2026-10-17): vs_pickups (manifests; originals restored) and vs_gameplay (into
empty scratch WFC_VS_ROOTs, so ExtractedAssets is never written) on the 10 MP maps with the committed (old) and working-tree (new)
code; outputs hashed without the 'generated' stamp.   python pickupfix_proof.py -> work/pickupfix/proof.json"""
import hashlib, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.dirname(os.path.dirname(HERE)); MANI = os.path.join(AT, 'manifests')
OUT = os.path.join(AT, 'work', 'pickupfix')
MAPS = ['MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_IAC_Streets', 'MP_KON_Molten',
        'MP_ORB_Debris', 'MP_UND_Complex', 'MP_UND_Gorge']
STAGES = ['vs_pickups.py', 'vs_gameplay.py']
def mouts(m):
    if m == 'MP_IAC_Streets': return [os.path.join(MANI, f) for f in ('streets_pickup_factories.json', 'streets_pickup_fx.json')]
    return [os.path.join(MANI, 'next_map', '%s_%s' % (m, f)) for f in ('pickup_factories.json', 'pickup_fx.json')]
def sha(p):
    if not os.path.exists(p): return None
    d = json.load(open(p, encoding='utf-8'))
    if isinstance(d, dict): d.pop('generated', None)
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
def run(script, m, env, log):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'run_bounded.py'), '--cap-gb', '10', '--log', log, '--', os.path.join(HERE, script), m],
                       cwd=AT, capture_output=True, text=True, env=env)
    if r.returncode == 75: sys.exit('PERF_HOLD')
    return r.returncode
def main():
    bak = os.path.join(OUT, 'orig'); res = {}
    for m in MAPS:
        for p in mouts(m):
            b = os.path.join(bak, os.path.relpath(p, MANI))
            if os.path.exists(p) and not os.path.exists(b): os.makedirs(os.path.dirname(b), exist_ok=True); shutil.copy2(p, b)
    cur = {s: open(os.path.join(HERE, s), encoding='utf-8').read() for s in STAGES}
    try:
        for tag in ('old', 'new'):
            for s in STAGES:
                src = cur[s] if tag == 'new' else subprocess.run(['git', 'show', 'HEAD:scripts/wfc/' + s], cwd=AT, capture_output=True, text=True, encoding='utf-8').stdout
                open(os.path.join(HERE, s), 'w', encoding='utf-8', newline='').write(src)
            for m in MAPS:
                base = {k: v for k, v in os.environ.items() if k != 'WFC_VS_ROOT'}
                rc1 = run('vs_pickups.py', m, base, os.path.join(OUT, '%s_%s_pickups.log' % (tag, m)))
                root = os.path.join(OUT, 'vs_' + tag); os.makedirs(os.path.join(root, 'Maps', m), exist_ok=True)
                rc2 = run('vs_gameplay.py', m, dict(base, WFC_VS_ROOT=root), os.path.join(OUT, '%s_%s_gameplay.log' % (tag, m)))
                res.setdefault(m, {})[tag] = {'rc': [rc1, rc2], 'sha': {**{os.path.relpath(p, MANI): sha(p) for p in mouts(m)},
                                                                       'gameplay.json': sha(os.path.join(root, 'Maps', m, 'gameplay.json'))}}
                print(tag, m, res[m][tag]['rc'], flush=True)
    finally:
        for s in STAGES: open(os.path.join(HERE, s), 'w', encoding='utf-8', newline='').write(cur[s])
        for m in MAPS:
            for p in mouts(m):
                b = os.path.join(bak, os.path.relpath(p, MANI))
                if os.path.exists(b): shutil.copy2(b, p)
    same = {m: res[m]['old'] == res[m]['new'] for m in res}
    json.dump({'results': res, 'identical': same}, open(os.path.join(OUT, 'proof.json'), 'w'), indent=1)
    print('identical per map:', same, flush=True)
if __name__ == '__main__':
    main()
