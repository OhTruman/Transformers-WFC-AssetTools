"""Deduplicated, parallel asset extraction via UE Viewer (umodel) + vgmstream.

Cooked WFC packages embed copies of shared objects.  Each export's outer chain
preserves the ORIGINAL source package (e.g. TR_Optimus_ROBO_p.RB_Optimus_A_SKELMESH),
so we de-duplicate on (object path, class), assign every unique object to one
owner package, and ask umodel to export only those objects from it.

Output tree (ExtractedAssets/content) follows umodel -uncook -groups, i.e.
<original package>/<group>/<object>.<ext>, preserving original naming.
Every run appends to AssetTools/manifests/extracted/<phase>.jsonl mapping
object -> output file(s).

Usage:
  python extract.py [phase ...] [--limit-packages N] [--jobs N] [--only-pkg NAME]
Phases: textures static_meshes skeletal_meshes materials animations audio ui facefx wav
"""
import argparse, json, os, re, sqlite3, subprocess, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TOOLS = os.path.join(ROOT, 'AssetTools')
# opt-in overrides (DLC 2026-10-23: the DLC packs are a second read-only cooked source; unset = the Game Dump / ExtractedAssets /
# manifests as always): WFC_COOKED_DIR = the cooked package dir, WFC_EXTRACT_OUT = the umodel content root, WFC_MANI_DIR = manifests
COOKED = os.environ.get('WFC_COOKED_DIR') or os.path.join(ROOT, 'Game Dump', 'TransGame', 'CookedXenon')
ROOT_EA_DEFAULT = os.path.join(ROOT, 'ExtractedAssets', 'content')   # the base content root (shared slice data stays here)
OUT = os.environ.get('WFC_EXTRACT_OUT') or ROOT_EA_DEFAULT
MANI = os.environ.get('WFC_MANI_DIR') or os.path.join(TOOLS, 'manifests')
LOGS = os.path.join(TOOLS, 'logs')
UMODEL = os.path.join(TOOLS, 'bin', 'umodel', 'umodel_64.exe')
VGM = os.path.join(TOOLS, 'bin', 'vgmstream', 'vgmstream-cli.exe')

PHASES = {
    # phase: (classes, umodel options)
    'textures':        (['Texture2D', 'TextureCube'], ['-png', '-nolightmap']),
    'static_meshes':   (['StaticMesh', 'FracturedStaticMesh'], ['-gltf', '-png']),
    'skeletal_meshes': (['SkeletalMesh'], ['-gltf', '-png']),
    'materials':       (['Material', 'MaterialInstanceConstant', 'MaterialInstanceTimeVarying'], ['-png', '-nolightmap']),
    'animations':      (['AnimSet'], ['-nomesh', '-nostat', '-notex']),          # ActorX .psa
    'audio':           (['SoundNodeWaveEx', 'SoundNodeWave'], ['-sounds', '-nomesh', '-nostat', '-notex', '-noanim']),
    'ui':              (['GFxMovieInfo', 'SwfMovie', 'Font'], ['-3rdparty', '-png']),
    'facefx':          (['FaceFXAsset', 'FaceFXAnimSet'], ['-3rdparty', '-nomesh', '-nostat', '-notex', '-noanim']),
}
EXPORT_RE = re.compile(r'^Exporting (\S+) (\S+) to (.+)$')

def db():
    return sqlite3.connect(os.path.join(MANI, 'inventory.db'))

def plan(phase, only_pkg=None):
    """Return {package: [(object_path, class, name)]} covering every unique object once."""
    classes, _ = PHASES[phase]
    con = db()
    q = 'SELECT package, opath, class, name, serial_size FROM exports WHERE class IN (%s)' % ','.join('?' * len(classes))
    rows = con.execute(q, classes).fetchall()
    existing = {os.path.splitext(n)[0] for n in os.listdir(COOKED)}
    cands = defaultdict(list)                     # (path,class) -> [(pkg,size,name)]
    for pkg, path, cls, name, size in rows:
        cands[(path, cls)].append((pkg, size, name))
    pkg_load = defaultdict(int)
    for key, lst in cands.items():
        for pkg, _, _ in lst:
            pkg_load[pkg] += 1
    assign = defaultdict(list)
    for (path, cls), lst in sorted(cands.items()):
        orig = path.split('.', 1)[0]
        best = max(lst, key=lambda c: c[1])[1]
        # 1) original source package when it exists and holds a full-size copy
        own = [c for c in lst if c[0] == orig and c[1] >= best]
        # 2) otherwise the full-size copy in the package that covers most objects
        pick = own[0] if own else max((c for c in lst if c[1] >= best), key=lambda c: pkg_load[c[0]])
        assign[pick[0]].append((path, cls, pick[2]))
    if only_pkg:
        assign = {k: v for k, v in assign.items() if k == only_pkg}
    return dict(assign)

def _invoke(phase, pkg, names, tag):
    """One umodel run. Names without spaces go in a response file as -obj=;
    a name containing spaces (unsupported by -obj parsing) is passed alone as
    the positional <object> argument."""
    _, opts = PHASES[phase]
    logdir = os.path.join(LOGS, phase); os.makedirs(logdir, exist_ok=True)
    base = ['-export', '-path=%s' % COOKED, '-game=trans', '-out=%s' % OUT,
            '-uncook', '-groups', '-nooverwrite'] + opts
    if len(names) == 1 and ' ' in names[0]:
        cmd = [UMODEL] + base + [pkg + '.xxx', names[0]]
    else:
        resp = os.path.join(logdir, '%s%s.resp' % (pkg, tag))
        with open(resp, 'w', encoding='utf-8') as f:
            f.write('\n'.join(['-export', '-path="%s"' % COOKED, '-game=trans', '-out="%s"' % OUT,
                               '-uncook', '-groups', '-nooverwrite'] + opts + [pkg + '.xxx'] +
                              ['-obj=%s' % n for n in names]) + '\n')
        cmd = [UMODEL, '@' + resp]
    p = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    return p.returncode, p.stdout + p.stderr

def run_umodel(phase, pkg, objs):
    logdir = os.path.join(LOGS, phase); os.makedirs(logdir, exist_ok=True)
    names = sorted({o[2] for o in objs})
    plain = [n for n in names if ' ' not in n]
    spaced = [n for n in names if ' ' in n]
    t = time.time()
    rc, log = _invoke(phase, pkg, plain, '') if plain else (0, '')
    if rc != 0 and len(plain) > 1:
        # umodel aborts the whole run on one bad -obj; retry one object at a time
        log += '\n### batch failed (rc=%d); retrying individually\n' % rc
        rc = 0
        for n in plain:
            r, l = _invoke(phase, pkg, [n], '_single')
            log += l
            if r != 0: rc = r
    for n in spaced:
        r, l = _invoke(phase, pkg, [n], '_spaced')
        log += l
        if r != 0: rc = r
    with open(os.path.join(logdir, pkg + '.log'), 'w', encoding='utf-8') as f:
        f.write(log)
    p = type('R', (), {'returncode': rc})
    by_path = {o[0].lower(): o for o in objs}
    by_name = defaultdict(list)
    for o in objs:
        by_name[o[2]].append(o)
    records, seen = [], set()
    for line in log.splitlines():
        m = EXPORT_RE.match(line.strip())
        if not m: continue
        ucls, name, dest = m.groups()
        cls = ucls[:-1] if ucls.endswith('3') and ucls[:-1] in ('SkeletalMesh', 'StaticMesh', 'Material') else ucls
        dest = os.path.normpath(dest)
        rel = os.path.relpath(dest, OUT).replace(os.sep, '/')
        # -uncook -groups => <srcpkg>/<group...>/<name>.<ext> == object path
        dotted = os.path.splitext(rel)[0].replace('/', '.').lower()
        o = by_path.get(dotted)
        if o is None:
            cand = [x for x in by_name.get(name, []) if x[1] == cls and x[0] not in seen]
            o = cand[0] if len(cand) == 1 else None
        records.append({'phase': phase, 'source_package': pkg, 'object_path': o[0] if o else None,
                        'class': cls, 'name': name, 'output': 'content/' + rel, 'requested': o is not None})
        if o: seen.add(o[0])
    missing = [o[0] for o in objs if o[0] not in seen]
    warns = sorted({l.strip() for l in log.splitlines() if l.startswith(('WARNING', 'ERROR', '*** ')) })
    return {'package': pkg, 'requested': len(objs), 'exported': len(seen), 'missing': missing,
            'records': records, 'returncode': p.returncode, 'seconds': round(time.time() - t, 2),
            'warnings': warns[:50]}

def run_phase(phase, jobs, limit=None, only_pkg=None):
    assign = plan(phase, only_pkg)
    items = sorted(assign.items(), key=lambda kv: -len(kv[1]))
    if limit: items = items[:limit]
    total = sum(len(v) for _, v in items)
    print('[%s] %d unique objects across %d owner packages' % (phase, total, len(items)), flush=True)
    os.makedirs(os.path.join(MANI, 'extracted'), exist_ok=True)
    out_map = open(os.path.join(MANI, 'extracted', phase + '.jsonl'), 'w', encoding='utf-8')
    status = []
    t0 = time.time(); done = 0
    with ThreadPoolExecutor(jobs) as ex:
        futs = {ex.submit(run_umodel, phase, pkg, objs): pkg for pkg, objs in items}
        for fut in as_completed(futs):
            r = fut.result(); done += 1
            for rec in r.pop('records'):
                out_map.write(json.dumps(rec) + '\n')
            status.append(r)
            if done % 50 == 0 or done == len(items):
                print('  %d/%d packages, %.0fs' % (done, len(items), time.time() - t0), flush=True)
    out_map.close()
    exported = sum(s['exported'] for s in status)
    summary = {'phase': phase, 'unique_objects': total, 'exported': exported,
               'missing': total - exported, 'packages': len(items), 'seconds': round(time.time() - t0, 1),
               'failed_packages': [s['package'] for s in status if s['returncode'] != 0],
               'status': sorted(status, key=lambda s: s['package'])}
    json.dump(summary, open(os.path.join(MANI, 'extracted', phase + '_status.json'), 'w'), indent=1)
    print('[%s] exported %d/%d in %.0fs; umodel non-zero exits: %d' % (
        phase, exported, total, time.time() - t0, len(summary['failed_packages'])), flush=True)

def convert_wav(jobs):
    """FSB4 (XMA2 inside) -> WAV via vgmstream, written beside the .fsb."""
    fsbs = []
    for dp, _, fn in os.walk(OUT):
        fsbs += [os.path.join(dp, n) for n in fn if n.lower().endswith('.fsb')]
    print('[wav] %d fsb files' % len(fsbs), flush=True)
    def one(f):
        w = f[:-4] + '.wav'
        if os.path.exists(w): return (f, 0, 'exists')
        p = subprocess.run([VGM, '-o', w, f], capture_output=True, text=True, errors='replace')
        return (f, p.returncode, (p.stderr or '').strip()[-200:])
    res = []
    with ThreadPoolExecutor(jobs) as ex:
        for r in ex.map(one, fsbs): res.append(r)
    fails = [r for r in res if r[1] != 0]
    json.dump({'fsb': len(fsbs), 'failed': [{'file': os.path.relpath(f, OUT), 'err': e} for f, c, e in fails]},
              open(os.path.join(MANI, 'extracted', 'wav_status.json'), 'w'), indent=1)
    print('[wav] converted %d, failed %d' % (len(res) - len(fails), len(fails)), flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('phases', nargs='*', default=list(PHASES) + ['wav'])
    ap.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 4) - 4))
    ap.add_argument('--limit-packages', type=int)
    ap.add_argument('--only-pkg')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for ph in a.phases:
        if ph == 'wav': convert_wav(a.jobs)
        else: run_phase(ph, a.jobs, a.limit_packages, a.only_pkg)

if __name__ == '__main__':
    main()
