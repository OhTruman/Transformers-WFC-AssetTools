"""DLC map render data (Integration go 2026-10-23): the per-map steps of Rendering's tools/render/build_render_data.ps1 (lightmap atlases,
build_lighting, build_materials with the same extra-material lists through the head's matc.py, fog, lens flares, beast probes, movers,
map FX, render index, scene float props) for a DLC map, reading the DLC sources (dlc_render_step.py) and writing the MP layout into
AssetTools/out/dlc_render/<MAP>/ (as Rebuild/work/render/<MAP> for the shipped maps). build_hud / build_anim_choosers are global (not per
map) and are not rerun. Every step runs bounded (run_bounded 6 GB); a step's status lands in <out>/_status/<step>.json; ok steps skip.
    source work/dlc/dlc_env.sh; python dlc_render.py <MAP> [--force]
"""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
PY = os.path.join(AT, 'bin', 'py', 'python.exe'); RB = os.path.join(AT, 'scripts', 'wfc', 'run_bounded.py')
UMODEL = os.path.join(AT, 'bin', 'umodel', 'umodel_64.exe'); STEP = os.path.join(HERE, 'dlc_render_step.py')
TOOLS = r'F:/Transformers Rebuild/Rebuild/tools/render'

def capture(mod, *args):
    r = subprocess.run([PY, STEP, mod] + list(args), capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]

def lines(f): return [l.strip() for l in open(os.path.join(TOOLS, f), encoding='utf-8') if l.strip()]

def run_step(out, name, mod, *args):
    st = os.path.join(out, '_status'); os.makedirs(st, exist_ok=True); sf = os.path.join(st, name + '.json')
    if '--force' not in sys.argv and os.path.exists(sf) and json.load(open(sf, encoding='utf-8')).get('ok'): return True
    t0 = time.time(); log = os.path.join(st, name + '.log')
    r = subprocess.run([PY, RB, '--cap-gb', '6', '--log', log, STEP, mod] + list(args), stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = r.returncode == 0
    json.dump({'step': name, 'ok': ok, 'rc': r.returncode, 'seconds': round(time.time() - t0, 1)}, open(sf, 'w', encoding='utf-8'))
    print('  %-14s %s (%.0fs)' % (name, 'ok' if ok else 'FAIL rc %d (%s)' % (r.returncode, log), time.time() - t0), flush=True)
    return ok

def main(M):
    if any(os.path.exists(p) for p in __import__('glob').glob(r'F:/Transformers Rebuild/*/work/PERF_HOLD')): sys.exit('PERF_HOLD present')
    out = os.path.join(AT, 'out', 'dlc_render', M); um = os.path.join(AT, 'out', 'dlc_render', '_umodel'); os.makedirs(out, exist_ok=True); os.makedirs(um, exist_ok=True)
    ck = os.environ['WFC_COOKED_DIR']
    # 1. lightmap atlases (_LM package + inline in ART), umodel against the DLC cooked dir
    def plist(what):
        r = subprocess.run([PY, os.path.join(HERE, 'ue3obj_list.py'), what, M], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return [x for x in r.stdout.split() if x]
    for lp in plist('lm'):
        subprocess.run([UMODEL, '-export', '-path=%s' % ck, '-game=trans', '-out=%s' % um, '-png', lp], capture_output=True)
    lv = plist('levels'); print('  lightmap packages / levels:', plist('lm'), lv, flush=True)
    inline = capture('build_lighting.py', '--list-inline', M)
    inline = [x for l in inline for x in l.split()]
    if inline:
        # batches of 100 -obj (hundreds in one command line exceed Windows' limit and umodel never ran: Fortress 3 atlases missing)
        for pk in lv:
            for k in range(0, len(inline), 100):
                subprocess.run([UMODEL, '-export', '-path=%s' % ck, '-game=trans', '-out=%s' % um, '-png', pk] + ['-obj=%s' % o for o in inline[k:k + 100]], capture_output=True)
    ok = run_step(out, 'lighting', 'build_lighting.py', M, out, um)
    # 3. materials: the same lists build_render_data.ps1 passes
    chars = capture('character_materials.py'); scene = capture('scene_materials.py', M); weapons = capture('weapon_materials.py')
    fxlib = [l for l in capture('build_map_fx.py', '--list-materials', M) if '.' in l and ' ' not in l]
    defrag = capture('energy_death_materials.py', '--list'); abil = capture('ability_render_assets.py', '--materials')
    trans = capture('transforming_materials.py', M); flare = capture('build_lens_flares.py', '--materials', M)
    extra = chars + ['WEP_IonBlaster_p.WEP_IonBlaster_MATINST'] + weapons + lines('fx_materials.txt') + lines('ui_materials.txt') + scene + fxlib + defrag + abil + trans + flare
    ok &= run_step(out, 'materials', 'build_materials.py', M, out, *list(dict.fromkeys(extra)))
    for name, mod in (('fog', 'build_fog_volumes.py'), ('lens_flares', 'build_lens_flares.py'), ('beast', 'beast_probes.py'), ('movers', 'build_movers.py'),
                      ('map_fx', 'build_map_fx.py'), ('render_index', 'build_render_index.py'), ('floatprops', 'build_scene_floatprops.py')):
        ok &= run_step(out, name, mod, M, out)
    print(M, 'render data', 'OK' if ok else 'with failures', '->', out)

if __name__ == '__main__':
    main(sys.argv[1])
