"""Gate for the m05 / structure-audit grid change (Integration 2026-10-16): run m05_bsp_default_faces.py and map_structure_audit.py on
the 10 MP maps with the committed (old) code and the working-tree (new) code, hash every output they write, restore the originals.
ExtractedAssets is only read (the stages write AssetTools manifests).   python gridfix_proof.py  -> work/gridfix/proof.json
"""
import hashlib, json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.dirname(os.path.dirname(HERE)); MANI = os.path.join(AT, 'manifests')
OUT = os.path.join(AT, 'work', 'gridfix'); os.makedirs(OUT, exist_ok=True)
MAPS = ['MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_IAC_Streets', 'MP_KON_Molten',
        'MP_ORB_Debris', 'MP_UND_Complex', 'MP_UND_Gorge']
STAGES = ['m05_bsp_default_faces.py', 'map_structure_audit.py']
def outputs(m):
    a = ['streets_bsp_default_faces.json'] if m == 'MP_IAC_Streets' else ['next_map/%s_bsp_default_faces.json' % m]
    return [os.path.join(MANI, x) for x in a] + [os.path.join(MANI, 'maps', m, f) for f in ('structure_audit.json', 'hazard_volumes.json')]
def sha(p):
    if not os.path.exists(p): return None
    d = json.load(open(p, encoding='utf-8'))
    if isinstance(d, dict): d.pop('generated', None)
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
def main():
    bak = os.path.join(OUT, 'orig'); res = {}
    for m in MAPS:
        for p in outputs(m):
            b = os.path.join(bak, os.path.relpath(p, MANI))
            if os.path.exists(p) and not os.path.exists(b): os.makedirs(os.path.dirname(b), exist_ok=True); shutil.copy2(p, b)
    cur = {s: open(os.path.join(HERE, s), encoding='utf-8').read() for s in STAGES}
    try:
        for tag in ('old', 'new'):
            if tag == 'old':
                for s in STAGES: open(os.path.join(HERE, s), 'w', encoding='utf-8', newline='').write(
                    subprocess.run(['git', 'show', 'HEAD:scripts/wfc/' + s], cwd=AT, capture_output=True, text=True, encoding='utf-8').stdout)
            else:
                for s in STAGES: open(os.path.join(HERE, s), 'w', encoding='utf-8', newline='').write(cur[s])
            for m in MAPS:
                for s in STAGES:
                    t0 = time.time()
                    r = subprocess.run([sys.executable, os.path.join(HERE, 'run_bounded.py'), '--cap-gb', '10', '--log',
                                        os.path.join(OUT, '%s_%s_%s.log' % (tag, m, s[:-3])), '--', os.path.join(HERE, s), m],
                                       cwd=AT, capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != 'WFC_VS_ROOT'})
                    if r.returncode == 75: sys.exit('PERF_HOLD')
                    res.setdefault(m, {}).setdefault(tag, {})[s] = {'rc': r.returncode, 'wall_s': round(time.time() - t0, 1)}
                res[m][tag]['sha'] = {os.path.relpath(p, MANI): sha(p) for p in outputs(m)}
                print(tag, m, res[m][tag], flush=True)
    finally:
        for s in STAGES: open(os.path.join(HERE, s), 'w', encoding='utf-8', newline='').write(cur[s])
        for m in MAPS:
            for p in outputs(m):
                b = os.path.join(bak, os.path.relpath(p, MANI))
                if os.path.exists(b): shutil.copy2(b, p)
    same = {m: res[m]['old']['sha'] == res[m]['new']['sha'] for m in res}
    json.dump({'results': res, 'identical_except_generated': same}, open(os.path.join(OUT, 'proof.json'), 'w'), indent=1)
    print('identical per map:', same, flush=True)
if __name__ == '__main__':
    main()
