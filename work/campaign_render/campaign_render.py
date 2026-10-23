"""Campaign render data with Rendering's merged pipeline (Rebuild/tools/render at integration cb80e4ea or later; Integration 2026-10-23).
Per streaming sublevel (the original's streaming model): each sublevel of a chapter is run as its own "map".

  python campaign_render.py prep <CH>              sublevel folders get their inputs: map.json (sublevels = [the level]) and the chapter's
                                                   props / props_authored / postprocess / light_probes FILTERED to that level (a split,
                                                   no duplication); world.glb / map_fx.json / render_index.json are already there
                                                   (split_sublevels.py)
  python campaign_render.py step <CH> <SUB> <step> one step, one process (call it under run_bounded)
  python campaign_render.py chapter <CH>           every sublevel x step, each under run_bounded (6 GB), sequential, resumable: a step
                                                   whose status file says ok is skipped; exits 75 on a PERF_HOLD file
  python campaign_render.py report <CH>            sizes / failures / gap list -> out/campaign_render/<CH>/report.json + .md

Inputs : VS_MAPS -> work/campaign_pilot/VerticalSlice/Maps/<CH>/sublevels (each <SUB> folder is a map); VS -> the campaign VerticalSlice;
         map_packages(<SUB>) -> [<SUB>.xxx] with the chapter's persistent level as persistent; map_lm_packages -> its _LM package.
Outputs: out/campaign_render/<CH>/<SUB>/ (the ps1's <out>) + world.glb (copied from the split input); umodel exports in
         out/campaign_render/<CH>/_umodel. Rendering's scripts are imported read-only (no bytecode); nothing is written outside AssetTools.
Material extras: the ps1's MP lists (roster characters, MP weapons, energy death, abilities, transforming actors, lens flares) are MP
         content; the campaign counterparts come from manifests/campaign/render_materials/<CH>.txt (+ fx_materials / ui_materials / the
         sublevel's particle library / scene actors, as in the ps1). build_materials compiles only what is cooked into the level.
"""
import contextlib, glob, io, json, os, runpy, shutil, subprocess, sys, time, traceback
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(AT)
TOOLS = os.path.join(TR, 'Rebuild', 'tools', 'render')
CVS = os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice')
OUTR = os.path.join(AT, 'out', 'campaign_render')
UMODEL = os.path.join(AT, 'bin', 'umodel', 'umodel_64.exe')
COOKED = os.path.join(TR, 'Game Dump', 'TransGame', 'CookedXenon')
PY = os.path.join(AT, 'bin', 'py', 'python.exe'); RB = os.path.join(AT, 'scripts', 'wfc', 'run_bounded.py')
STEPS = ['lm_umodel', 'inline_umodel', 'lighting', 'materials', 'fog', 'beast', 'movers', 'map_fx', 'render_index', 'floatprops']
FILTERED = ('props.json', 'props_authored.json', 'postprocess.json', 'light_probes.json')

def chapter_levels(ch): return json.load(open(os.path.join(CVS, 'Maps', ch, 'map.json'), encoding='utf-8'))['sublevels']

# ---------------------------------------------------------------- prep
def filt(v, lv, levels):
    """keep the parts of a chapter-wide value that belong to level lv: lists of records by their sublevel / package-prefixed path,
    dicts keyed by level names by key; everything else (chapter-wide settings) as is"""
    def rec_level(r):
        if not isinstance(r, dict): return None
        if r.get('sublevel') in levels: return r['sublevel']
        for k in ('actor', 'component', 'volume', 'owner', 'object', 'world_info'):
            x = r.get(k)
            if isinstance(x, str) and x.split('.')[0] in levels: return x.split('.')[0]
        return None
    if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
        tags = [rec_level(x) for x in v]
        return [x for x, t in zip(v, tags) if t == lv] if any(tags) else v
    if isinstance(v, dict):
        if v and set(v) <= set(levels): return {k: x for k, x in v.items() if k == lv}
        return {k: filt(x, lv, levels) for k, x in v.items()}
    return v

def prep(ch):
    D = os.path.join(CVS, 'Maps', ch); S = os.path.join(D, 'sublevels'); levels = chapter_levels(ch)
    src = {f: json.load(open(os.path.join(D, f), encoding='utf-8')) for f in FILTERED if os.path.exists(os.path.join(D, f))}
    mj = json.load(open(os.path.join(D, 'map.json'), encoding='utf-8'))
    n = 0
    for lv in sorted(os.listdir(S)):
        od = os.path.join(S, lv)
        if not os.path.isdir(od) or lv not in levels: continue
        m = dict(filt(mj, lv, levels), map=lv, sublevels=[lv], chapter=ch, split_from='map.json')
        json.dump(m, open(os.path.join(od, 'map.json'), 'w', encoding='utf-8'), indent=1)
        for f, d in src.items():
            x = dict(filt(d, lv, levels), sublevel=lv, split_from=f) if isinstance(d, dict) else d
            json.dump(x, open(os.path.join(od, f), 'w', encoding='utf-8'), indent=1)
        n += 1
    print(ch, 'prepared', n, 'sublevel folders under', S)

# ---------------------------------------------------------------- one step
def step(ch, sub, s):
    sys.path.insert(0, TOOLS)
    S = os.path.join(CVS, 'Maps', ch, 'sublevels'); OUT = os.path.join(OUTR, ch, sub); UM = os.path.join(OUTR, ch, '_umodel')
    os.makedirs(OUT, exist_ok=True); os.makedirs(UM, exist_ok=True)
    cooked = {f.lower(): f for f in os.listdir(COOKED)}
    pers = next((l for l in chapter_levels(ch) if l.lower().endswith('_base_m') or l.lower() == ch.lower() + '_m'), sub)
    def map_packages(mapname):
        p = [cooked[(sub + '.xxx').lower()]] if (sub + '.xxx').lower() in cooked else []
        return p, cooked.get((pers + '.xxx').lower(), p[0] if p else None)
    def map_lm_packages(mapname):
        k = (sub + '_LM.xxx').lower(); return [cooked[k]] if k in cooked else []
    import ue3obj
    ue3obj.VS_MAPS = S; ue3obj.map_packages = map_packages; ue3obj.map_lm_packages = map_lm_packages
    def load(name):
        import importlib
        mod = importlib.import_module(name)
        for k, v in (('VS_MAPS', S), ('VS', CVS), ('map_packages', map_packages), ('map_lm_packages', map_lm_packages)):
            if hasattr(mod, k): setattr(mod, k, v)
        return mod
    def capture(fn):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): fn()
        return [l for l in buf.getvalue().splitlines() if l.strip()]
    def run_main(name, argv):
        m = load(name); sys.argv = [name + '.py'] + argv
        if hasattr(m, 'main'): m.main()
        else: runpy.run_path(os.path.join(TOOLS, name + '.py'), run_name='__main__')
    def umodel(pkg, objs=()):
        r = subprocess.run([UMODEL, '-export', '-path=' + COOKED.replace('\\', '/'), '-game=trans', '-out=' + UM, '-png', pkg] + ['-obj=' + o for o in objs],
                           capture_output=True, text=True)
        return r.returncode
    res = {}
    if s == 'lm_umodel':
        res = {pk: umodel(pk) for pk in map_lm_packages(sub)}
    elif s == 'inline_umodel':
        il = json.load(open(os.path.join(AT, 'work', 'campaign_render_dryrun', 'inline_lightmaps.json'), encoding='utf-8'))['per_package'].get(ch, {})
        own = il.get(sub, [])
        res = {'objects': len(own), 'rc': umodel(map_packages(sub)[0][0], own) if own and map_packages(sub)[0] else None}
    elif s == 'lighting': run_main('build_lighting', [sub, OUT, UM])
    elif s == 'materials':
        rd = lambda f: [l.strip() for l in open(f, encoding='utf-8') if l.strip()]
        sys.argv = ['scene_materials.py', sub]; scene = capture(lambda: run_main('scene_materials', [sub]))
        fxlib = [l for l in capture(lambda: run_main('build_map_fx', ['--list-materials', sub])) if '.' in l and ' ' not in l]
        extra = rd(os.path.join(AT, 'manifests', 'campaign', 'render_materials', ch + '.txt')) + rd(os.path.join(TOOLS, 'fx_materials.txt')) + \
                rd(os.path.join(TOOLS, 'ui_materials.txt')) + scene + fxlib
        res = {'extra_list_entries': len(extra), 'campaign_list': len(rd(os.path.join(AT, 'manifests', 'campaign', 'render_materials', ch + '.txt'))),
               'fxlib': len(fxlib), 'scene': len(scene)}
        # build_materials reads world.glb from VS/Maps/<map> (not VS_MAPS): redirect that one read to the sublevel folder. Its M72 fallback
        # scans VS/Maps for MP_* maps; the campaign tree has none, so materials cooked only elsewhere stay missing (reported as gaps)
        bm = load('build_materials'); _gj = bm.glb_json
        wrong = os.path.normcase(os.path.normpath(os.path.join(CVS, 'Maps', sub)))
        bm.glb_json = lambda p, _gj=_gj: _gj(os.path.join(S, sub, os.path.basename(p)) if os.path.normcase(os.path.normpath(os.path.dirname(p))) == wrong else p)
        sys.argv = ['build_materials.py', sub, OUT] + list(dict.fromkeys(extra)); bm.main()
    elif s == 'fog': run_main('build_fog_volumes', [sub, OUT])
    elif s == 'beast': run_main('beast_probes', [sub, OUT])
    elif s == 'movers': run_main('build_movers', [sub, OUT])
    elif s == 'map_fx': run_main('build_map_fx', [sub, OUT])
    elif s == 'render_index': run_main('build_render_index', [sub, OUT])
    elif s == 'floatprops': run_main('build_scene_floatprops', [sub, OUT])
    else: raise SystemExit('unknown step ' + s)
    return res

def step_cmd(ch, sub, s):
    stf = os.path.join(OUTR, ch, sub, '_status', s + '.json'); os.makedirs(os.path.dirname(stf), exist_ok=True)
    t0 = time.time(); rec = {'chapter': ch, 'sublevel': sub, 'step': s}
    try:
        rec['result'] = step(ch, sub, s); rec['ok'] = True
    except SystemExit as e:
        rec['ok'] = e.code in (None, 0); rec['exit'] = str(e.code)
    except Exception:
        rec['ok'] = False; rec['error'] = traceback.format_exc()[-3000:]
    rec['seconds'] = round(time.time() - t0, 1)
    json.dump(rec, open(stf, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps({k: rec[k] for k in rec if k != 'error'}, default=str)[:400]); sys.exit(0 if rec['ok'] else 1)

# ---------------------------------------------------------------- chapter loop
def chapter(ch):
    S = os.path.join(CVS, 'Maps', ch, 'sublevels')
    subs = [l for l in chapter_levels(ch) if os.path.isdir(os.path.join(S, l))]
    for sub in subs:
        od = os.path.join(OUTR, ch, sub); os.makedirs(od, exist_ok=True)
        if not os.path.exists(os.path.join(od, 'world.glb')): shutil.copyfile(os.path.join(S, sub, 'world.glb'), os.path.join(od, 'world.glb'))
        for s in STEPS:
            stf = os.path.join(od, '_status', s + '.json')
            if os.path.exists(stf) and json.load(open(stf, encoding='utf-8')).get('ok'): continue
            if glob.glob(os.path.join(TR, '*', 'work', 'PERF_HOLD')): print('PERF_HOLD present: stopping', flush=True); sys.exit(75)
            log = os.path.join(od, '_status', s + '.log'); os.makedirs(os.path.dirname(log), exist_ok=True)
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            r = subprocess.run([PY, RB, '--cap-gb', '6', '--log', log, os.path.abspath(__file__), 'step', ch, sub, s], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ok = os.path.exists(stf) and json.load(open(stf, encoding='utf-8')).get('ok')
            if not ok and not os.path.exists(stf):
                json.dump({'chapter': ch, 'sublevel': sub, 'step': s, 'ok': False, 'error': 'process ended without a status (rc %s; see %s)' % (r.returncode, log)},
                          open(stf, 'w', encoding='utf-8'), indent=1)
            print('%s %-34s %-13s %s' % (ch, sub, s, 'ok' if ok else 'FAIL rc %s' % r.returncode), flush=True)
    report(ch)

# ---------------------------------------------------------------- report
def report(ch):
    R = os.path.join(OUTR, ch); rows = {}; tot = 0
    for sub in sorted(d for d in os.listdir(R) if os.path.isdir(os.path.join(R, d)) and not d.startswith('_')):
        od = os.path.join(R, sub); sz = {}
        for f in ('world.glb', 'materials_glsl.json', 'lighting.json', 'map_fx_runtime.json', 'render_index.json', 'fog_volumes.json', 'movers.json'):
            if os.path.exists(os.path.join(od, f)): sz[f] = os.path.getsize(os.path.join(od, f))
        allb = sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(od) for f in fs if '_status' not in a); tot += allb
        st = {}
        for f in glob.glob(os.path.join(od, '_status', '*.json')):
            x = json.load(open(f, encoding='utf-8')); st[x['step']] = 'ok' if x.get('ok') else ('FAIL: ' + (x.get('error') or x.get('exit') or '')[-300:])
        gap = {}
        mg = os.path.join(od, 'materials_glsl.json')
        if os.path.exists(mg):
            m = json.load(open(mg, encoding='utf-8'))
            gap['materials_total'] = len(m); gap['materials_error'] = sorted(k for k, v in m.items() if (v or {}).get('error'))
            tex_missing = sorted({t.get('object') for v in m.values() for t in ((v or {}).get('info') or {}).get('textures') or []
                                  if t.get('file') and not os.path.exists(t['file'])} - {None})
            gap['textures_missing_file'] = tex_missing
        lj = os.path.join(od, 'lighting.json')
        if os.path.exists(lj):
            l = json.load(open(lj, encoding='utf-8'))
            gap['lights'] = len(l.get('lights') or []); gap['fogs'] = len(l.get('fogs') or [])
            gap['component_flags'] = len(l.get('component_flags') or {}); gap['lightmap_records'] = len(l.get('lightmaps') or l.get('records') or [])
        fv = os.path.join(od, 'fog_volumes.json')
        if os.path.exists(fv):
            try: gap['fog_volumes'] = len((json.load(open(fv, encoding='utf-8')) or {}).get('volumes') or [])
            except Exception: gap['fog_volumes'] = 'unreadable'
        rows[sub] = {'bytes_total': allb, 'files': sz, 'steps': st, 'gaps': gap}
    rep = {'chapter': ch, 'generated_by': 'AssetTools/work/campaign_render/campaign_render.py', 'bytes_total': tot, 'sublevels': rows,
           'failures': {s: {k: v for k, v in r['steps'].items() if v != 'ok'} for s, r in rows.items() if any(v != 'ok' for v in r['steps'].values())}}
    json.dump(rep, open(os.path.join(R, 'report.json'), 'w', encoding='utf-8'), indent=1)
    print(ch, 'sublevels', len(rows), 'MB', round(tot / 1e6, 1), 'with failures', len(rep['failures']))

if __name__ == '__main__':
    a = sys.argv[1:]
    {'prep': lambda: prep(a[1]), 'step': lambda: step_cmd(a[1], a[2], a[3]), 'chapter': lambda: chapter(a[1]), 'report': lambda: report(a[1])}[a[0]]()
