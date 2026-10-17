"""DRY RUN of Rendering's per-map render-data pipeline (Rebuild/tools/render/build_render_data.ps1) on campaign A1 (Integration 2026-10-18).

Scope: A1_IAC_Base_m + its two largest streaming sublevels (A1_IAC_Intr1_Art_m 40 MB, A1_IAC_Strts0_Design_m 29 MB).
Rendering's scripts are imported read-only (no bytecode). Everything is written under work/campaign_render_dryrun/:
  render/A1_IAC/   the step outputs (the ps1's <out>)       umodel_out/   umodel PNG exports (the ps1's shared umodel_out)
Redirections, per module after import: VS_MAPS -> AssetTools/work/campaign_pilot/VerticalSlice/Maps (A1 is not in ExtractedAssets),
VS -> .../campaign_pilot/VerticalSlice, map_packages / map_lm_packages -> the three packages above. Nothing else is patched: any other
MP-layout assumption shows up as a failure, which is the point. One step per process:
  python driver.py <step>   steps: lm_umodel inline_umodel lighting materials fog beast movers map_fx render_index floatprops hud anim
"""
import contextlib, io, json, os, runpy, subprocess, sys, time, traceback
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(ROOT)
TOOLS = os.path.join(TR, 'Rebuild', 'tools', 'render'); sys.path.insert(0, TOOLS)
MAP = 'A1_IAC'
LEVELS = ['A1_IAC_Intr1_Art_m', 'A1_IAC_Strts0_Design_m', 'A1_IAC_Base_m']
OUT = os.path.join(HERE, 'render', MAP); UM = os.path.join(HERE, 'umodel_out')
VSROOT = os.path.join(ROOT, 'work', 'campaign_pilot', 'VerticalSlice'); VSMAPS = os.path.join(VSROOT, 'Maps')
UMODEL = os.path.join(ROOT, 'bin', 'umodel', 'umodel_64.exe')
COOKED = os.path.join(TR, 'Game Dump', 'TransGame', 'CookedXenon')
os.makedirs(OUT, exist_ok=True); os.makedirs(UM, exist_ok=True)

import ue3obj  # noqa: E402
_cooked = {f.lower(): f for f in os.listdir(COOKED)}
def map_packages(mapname):
    pkgs = [_cooked[(l + '.xxx').lower()] for l in LEVELS if (l + '.xxx').lower() in _cooked]
    return pkgs, _cooked[(LEVELS[-1] + '.xxx').lower()]
def map_lm_packages(mapname):
    pkgs, _ = map_packages(mapname)
    return [_cooked[p.lower().replace('.xxx', '_lm.xxx')] for p in pkgs if p.lower().replace('.xxx', '_lm.xxx') in _cooked]
ue3obj.VS_MAPS = VSMAPS; ue3obj.map_packages = map_packages; ue3obj.map_lm_packages = map_lm_packages

def load(name):
    import importlib
    m = importlib.import_module(name)
    for k, v in (('VS_MAPS', VSMAPS), ('VS', VSROOT), ('map_packages', map_packages), ('map_lm_packages', map_lm_packages)):
        if hasattr(m, k): setattr(m, k, v)
    return m

def capture(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): fn()
    return [l for l in buf.getvalue().splitlines() if l.strip()]

def run_main(name, argv):
    m = load(name); sys.argv = [name + '.py'] + argv
    if hasattr(m, 'main'): m.main()
    else: runpy.run_path(os.path.join(TOOLS, name + '.py'), run_name='__main__')

def umodel(pkg, objs=()):
    cmd = [UMODEL, '-export', '-path=' + COOKED.replace('\\', '/'), '-game=trans', '-out=' + UM, '-png', pkg] + ['-obj=' + o for o in objs]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode

def step(s):
    if s == 'lm_umodel':
        return {pk: umodel(pk) for pk in map_lm_packages(MAP)}
    if s == 'inline_umodel':
        bl = load('build_lighting'); sys.argv = ['build_lighting.py', '--list-inline', MAP]
        inline = [x for x in ' '.join(capture(bl.main)).split() if x]
        res = {'inline_objects': len(inline),
               'as_ps1 (every object to every package)': {pk: umodel(pk, inline) for pk in map_packages(MAP)[0]} if inline else {}}
        # dry-run workaround: umodel aborts at the first -obj missing from the package, so pass each package only its own objects
        import sqlite3
        inv = sqlite3.connect(os.path.join(ROOT, 'manifests', 'inventory.db'))
        per = {}
        for pk in map_packages(MAP)[0]:
            names = {r[0].lower() for r in inv.execute("select name from exports where package=? and class='LightMapTexture2D'", (pk[:-4],))}
            own = [o for o in inline if o.lower() in names]
            per[pk] = {'objects': len(own), 'rc': umodel(pk, own) if own else None}
        res['per_package (workaround)'] = per
        res['objects_in_no_level_package'] = len([o for o in inline if not any(
            o.lower() in {r[0].lower() for r in inv.execute("select name from exports where package=? and class='LightMapTexture2D'", (pk[:-4],))}
            for pk in map_packages(MAP)[0])])
        return res
    if s == 'lighting': return run_main('build_lighting', [MAP, OUT, UM])
    if s == 'materials':
        rd = lambda f: [l.strip() for l in open(os.path.join(TOOLS, f), encoding='utf-8') if l.strip()]
        chars = capture(lambda: runpy.run_path(os.path.join(TOOLS, 'character_materials.py'), run_name='__main__'))
        sys.argv = ['scene_materials.py', MAP]; scene = capture(lambda: run_main('scene_materials', [MAP]))
        weapons = capture(lambda: runpy.run_path(os.path.join(TOOLS, 'weapon_materials.py'), run_name='__main__'))
        sys.argv = ['build_map_fx.py', '--list-materials', MAP]
        fxlib = [l for l in capture(lambda: run_main('build_map_fx', ['--list-materials', MAP])) if '.' in l and ' ' not in l]
        sys.argv = ['energy_death_materials.py', '--list']
        defrag = capture(lambda: runpy.run_path(os.path.join(TOOLS, 'energy_death_materials.py'), run_name='__main__'))
        sys.argv = ['ability_render_assets.py', '--materials']
        abil = capture(lambda: runpy.run_path(os.path.join(TOOLS, 'ability_render_assets.py'), run_name='__main__'))
        extra = chars + ['WEP_IonBlaster_p.WEP_IonBlaster_MATINST'] + weapons + rd('fx_materials.txt') + rd('ui_materials.txt') + scene + fxlib + defrag + abil
        json.dump({'chars': len(chars), 'weapons': len(weapons), 'scene': len(scene), 'fxlib': len(fxlib), 'defrag': len(defrag),
                   'abil': len(abil), 'extra_total': len(extra)}, open(os.path.join(HERE, 'materials_extra_counts.json'), 'w'))
        return run_main('build_materials', [MAP, OUT] + extra)
    if s == 'fog': return run_main('build_fog_volumes', [MAP, OUT])
    if s == 'beast': return run_main('beast_probes', [MAP, OUT])
    if s == 'movers': return run_main('build_movers', [MAP, OUT])
    if s == 'map_fx': return run_main('build_map_fx', [MAP, OUT])
    if s == 'render_index': return run_main('build_render_index', [MAP, OUT])
    if s == 'floatprops': return run_main('build_scene_floatprops', [MAP, OUT])
    if s == 'hud': return run_main('build_hud', [os.path.dirname(OUT)])
    if s == 'anim': return run_main('build_anim_choosers', [os.path.dirname(OUT)])
    raise SystemExit('unknown step ' + s)

if __name__ == '__main__':
    s = sys.argv[1]; t0 = time.time(); res = {'step': s}
    try:
        r = step(s); res.update({'status': 'ok', 'result': r})
    except SystemExit as e:
        res.update({'status': 'ok' if not e.code else 'exit %s' % e.code})
    except Exception as e:
        res.update({'status': 'FAILED', 'error': '%s: %s' % (type(e).__name__, e), 'traceback': traceback.format_exc()[-2500:]})
    res['seconds'] = round(time.time() - t0, 1)
    os.makedirs(os.path.join(HERE, 'steps'), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, 'steps', s + '.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k != 'traceback'}, default=str)[:1500])
