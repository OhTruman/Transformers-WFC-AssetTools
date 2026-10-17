"""DRY RUN of Rendering's material translator (Rebuild/tools/render/matc.py, imported read-only) over the campaign materials that
manifests/campaign/summary.json marks 'missing' or 'candidate' (Integration 2026-10-18: size the campaign material work).

Nothing is written outside this directory:
- no .pyc (sys.dont_write_bytecode);
- the texture resolver is a stub that never exports or decodes (texture files are irrelevant to whether the graph compiles);
- results go to work/matc_dryrun/<ch>.json.

Each material is compiled once, in the first chapter that loads it, with a Repo over that chapter's level packages (+ the same fallback
packages build_materials.py uses). Control: a sample of materials already 'translated' in the MP sets is compiled too and must succeed.
python dryrun.py <CH>
"""
import json, os, re, sys, time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), 'Rebuild', 'tools', 'render'))
import matc  # noqa: E402
from ue3obj import Repo, COOKED  # noqa: E402

FALLBACK = ['TransGame.xxx', 'TR_AllShader_p.xxx', 'UI_GFxHud_p.xxx']   # as build_materials.py

class StubTex:
    def __init__(self, repo): self.R = repo
    def __call__(self, path):
        if not path: return None
        return {'object': path, 'file': None, 'class': self.R.cls(path), 'srgb': True, 'dry_run': True}

def classify(err):
    if err is None: return 'clean', None
    m = re.search(r'unsupported expression (\w+)', err)
    if m: return 'new_node', m.group(1)
    if 'ShaderCode' in err: return 'shadercode', None
    if 'no master material' in err: return 'no_master', None
    if 'missing function' in err or 'no output pin' in err: return 'function', None
    if 'unresolved expression' in err or 'missing input' in err: return 'graph_ref', None
    return 'other', None

def main(ch):
    s = json.load(open(os.path.join(ROOT, 'manifests', 'campaign', 'summary.json'), encoding='utf-8'))
    order = list(s['chapters'])
    todo = sorted(k for k, v in s['materials'].items() if v['status'] in ('missing', 'candidate') and v['chapters'][0] == ch)
    ctrl = sorted(k for k, v in s['materials'].items() if v['status'] == 'translated' and v['chapters'][0] == ch)[:30]
    cj = json.load(open(os.path.join(ROOT, 'manifests', 'campaign', ch.split('_')[0].lower() + '_assets.json'), encoding='utf-8'))
    cooked = {f.lower(): f for f in os.listdir(COOKED)}
    pk = [cooked[(l + '.xxx').lower()] for l in cj['levels']['per_level'] if (l + '.xxx').lower() in cooked]
    t0 = time.time()
    R = Repo(pk, fallback=FALLBACK)
    tr = StubTex(R)
    res = {}
    for mp in todo + ctrl:
        try:
            mc = matc.MatCompiler(R, mp, tr)
            glsl, info = mc.build()
            err = None; notes = getattr(mc, 'notes', [])
        except Exception as ex:
            err = '%s: %s' % (type(ex).__name__, ex); notes = []
        kind, node = classify(err)
        res[mp] = {'status_before': s['materials'][mp]['status'], 'master': s['materials'][mp]['master'], 'control': mp in ctrl,
                   'result': kind, 'node': node, 'error': err, 'notes': [n for n in notes if not n.startswith('texture not found')][:8]}
    out = {'chapter': ch, 'packages': pk, 'fallback': FALLBACK, 'seconds': round(time.time() - t0, 1),
           'compiled': len(todo), 'control': len(ctrl), 'results': res}
    json.dump(out, open(os.path.join(HERE, ch + '.json'), 'w', encoding='utf-8'), indent=1)
    from collections import Counter
    print(ch, 'todo', len(todo), Counter(r['result'] for k, r in res.items() if not r['control']),
          'control', Counter(r['result'] for r in res.values() if r['control']), '%.0fs' % (time.time() - t0))

if __name__ == '__main__':
    main(sys.argv[1])
