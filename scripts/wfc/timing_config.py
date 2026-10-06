"""Original frame-rate / frame-pacing / tick settings from the cooked Xbox 360 config -> manifests/config/timing_config.json

  python timing_config.py

Source: TransGame/Config/Xenon/Cooked/Coalesced.ini (decoded by coalesced.py to ExtractedAssets/config/Coalesced_ini/...).
The shipping runtime config is Xe-TransEngine.ini / Xe-TransGame.ini (TransEngineUnitTesting.ini is the unit-test variant,
reported separately for comparison). Every value is quoted verbatim with its [section] and file (CONFIRMED: authored config).
Semantics are stock UE3 (UEngine / UGameEngine / UNetDriver); how WFC's native code applies them is RE's call.
"""
import json, os, re, sys, time
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coalesced as C  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
CFG = os.path.join(C.OUT, 'Coalesced_ini', 'TransGame', 'Config', 'Xenon', 'Cooked')
FILES = ['Xe-TransEngine.ini', 'Xe-TransGame.ini', 'Xe-TransUI.ini', 'TransEngineUnitTesting.ini']
KEY = re.compile(r'(FrameRate|FPS|VSync|SyncInterval|PresentInterval|FrameThreadLag|DeltaTime|TimeStep|TickRate|ClientRate|'
                 r'TimeDilation|MaxSubsteps|PhysicsTimestep|bUseFixed|GPUFrame|RenderThread|FramePacing|TickInterval)', re.I)
STOCK = {  # stock UE3 meaning (labelled as such; not WFC-proven)
    'bSmoothFrameRate': 'UEngine: clamp/smooth the game frame rate between Min/MaxSmoothedFrameRate (UGameEngine::GetMaxTickRate)',
    'MinSmoothedFrameRate': 'UEngine: lower bound of the smoothed tick rate (Hz)',
    'MaxSmoothedFrameRate': 'UEngine: upper bound of the smoothed tick rate (Hz) - effectively the frame cap when smoothing is on',
    'MinDesiredFrameRate': 'UEngine: target used by detail/LOD scaling (e.g. particle / distance scaling), not a cap',
    'OneFrameThreadLag': 'render thread may lag the game thread by one frame',
    'NetServerMaxTickRate': 'UNetDriver: server tick cap (Hz)',
    'MaxClientRate': 'UNetDriver: max bytes/sec per client',
    'MaximumPIEFrameRate': 'editor Play-In-Editor cap (not used by the game)',
}

def main():
    out = OrderedDict([('generated_by', 'AssetTools/scripts/wfc/timing_config.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
                       ('source', 'Game Dump/TransGame/Config/Xenon/Cooked/Coalesced.ini (Xbox 360 cooked config, decoded)'),
                       ('stock_ue3_semantics (not WFC-proven)', STOCK), ('files', OrderedDict())])
    for fn in FILES:
        p = os.path.join(CFG, fn)
        if not os.path.exists(p): continue
        sec = C.parse_ini(open(p, encoding='utf-8', errors='replace').read())
        hits = OrderedDict()
        for s, kv in sec.items():
            m = OrderedDict((k, v if len(v) > 1 else v[0]) for k, v in kv.items() if KEY.search(k))
            if m: hits[s] = m
        out['files'][fn] = hits
    eng = out['files'].get('Xe-TransEngine.ini', {})
    pick = lambda k: next(((s, v[k]) for s, v in eng.items() if k in v), (None, None))
    out['summary (shipping Xe-TransEngine.ini)'] = OrderedDict(
        (k, {'section': pick(k)[0], 'value': pick(k)[1]}) for k in ('bSmoothFrameRate', 'MinSmoothedFrameRate', 'MaxSmoothedFrameRate',
                                                                  'MinDesiredFrameRate', 'OneFrameThreadLag', 'NetServerMaxTickRate'))
    out['pc_adaptation_note'] = ('Original Xbox 360 game: smoothed tick between 15 and 30 Hz (30 fps target). Any PC frame limiter above '
                                 '30 fps (e.g. 60 / 120 / 144 / uncapped) is a PC ADAPTATION; gameplay code that assumed <= 30 Hz '
                                 'ticks (fixed-step physics, animation, timers) should be checked under higher rates.')
    os.makedirs(os.path.join(AT, 'manifests', 'config'), exist_ok=True)
    json.dump(out, open(os.path.join(AT, 'manifests', 'config', 'timing_config.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(out['summary (shipping Xe-TransEngine.ini)'], indent=1))
    for fn, h in out['files'].items(): print(fn, {s: list(v) for s, v in h.items()})

if __name__ == '__main__':
    main()
