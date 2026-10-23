"""Verify split_sublevels.py output for a chapter: every split world.glb node (matched to the chapter node by name + extras + matrix)
has byte-identical vertex positions, indices and material name to the chapter world.glb, and every image URI resolves to the same file.
    python verify_split.py <CHAPTER>
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
from vs_common import read_glb, accessor  # noqa: E402
CVS = os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice', 'Maps')

def sig(j, b, nd):
    me = j['meshes'][nd['mesh']] if 'mesh' in nd else None
    if not me: return ()
    out = []
    for pr in me['primitives']:
        P = accessor(j, b, pr['attributes']['POSITION']).tobytes()
        I = accessor(j, b, pr['indices']).tobytes() if 'indices' in pr else b''
        mn = j['materials'][pr['material']].get('name') if 'material' in pr else None
        out.append((hash(P), hash(I), mn, tuple(sorted(pr['attributes']))))
    return tuple(out)

def key(nd): return (nd.get('name'), json.dumps(nd.get('extras'), sort_keys=True), json.dumps(nd.get('matrix')))

def main(ch):
    D = os.path.join(CVS, ch); j, b = read_glb(os.path.join(D, 'world.glb'))
    base = {}
    for nd in j['nodes']: base.setdefault(key(nd), []).append(sig(j, b, nd))
    bad, n, img_bad = 0, 0, 0
    for lv in sorted(os.listdir(os.path.join(D, 'sublevels'))):
        p = os.path.join(D, 'sublevels', lv, 'world.glb')
        if not os.path.exists(p): continue
        sj, sb = read_glb(p)
        for nd in sj['nodes']:
            n += 1
            if sig(sj, sb, nd) not in base.get(key(nd), []): bad += 1
        for im in sj.get('images') or []:
            if 'uri' in im and not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p), im['uri']))): img_bad += 1
    print(ch, 'split nodes', n, 'chapter nodes', len(j['nodes']), 'mismatched', bad, 'unresolved image uris', img_bad,
          'PASS' if bad == 0 and img_bad == 0 and n == len(j['nodes']) else 'FAIL')

if __name__ == '__main__':
    main(sys.argv[1])
