"""Seed nav input (Integration 2026-10-23, item 2): the shipped nav's input (live collision_pawn.glb / physics.json, authored hulls) minus
BlockingVolume_9745, so the rebuilt Seed nav fits the shipped collision's volume drop without the per-poly thin-floor regression
(two-sided render floors read as ceilings by bot_nav's clearance model: Debris CanyonFloor_B_Destroy 554 -> 11 m2 of nav).
Writes out/pc_adapt/MP_IAC_Seed/nav_input/{collision_pawn.glb, physics.json} (nav build input only; never shipped). Read-only on
ExtractedAssets. Then: bot_nav.py / bot_nav_air.py MP_IAC_Seed --overlay <nav_input> --out out/pc_adapt/MP_IAC_Seed/nav_v2.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
from vs_common import ROOT, GLB, read_glb, accessor  # noqa: E402
LIVE = os.path.join(ROOT, 'VerticalSlice', 'Maps', 'MP_IAC_Seed'); DST = os.path.join(AT, 'out', 'pc_adapt', 'MP_IAC_Seed', 'nav_input')
DROP = {'BlockingVolume_9745'}

def union():
    """v3: the shipped Seed collision (out/pc_adapt/MP_IAC_Seed: 9745 dropped, per-poly placements) PLUS the authored simple hulls of the
    #13 placements (hull smaller than visual; not the #18 raised ones) (from the live file), so the nav sees the hull tops (no cracks / holes of broken render floors) and the larger
    visible surfaces past the small hulls (#13). Nav input only."""
    SH = os.path.join(AT, 'out', 'pc_adapt', 'MP_IAC_Seed')
    aj, abin = read_glb(os.path.join(SH, 'collision_pawn.glb')); lj, lbin = read_glb(os.path.join(LIVE, 'collision_pawn.glb'))
    sw = {(n.get('name'), (n.get('extras') or {}).get('mesh'), json.dumps(n.get('matrix'))) for n in aj['nodes']
          if 'hull smaller than visual' in str((n.get('extras') or {}).get('pc_adaptation'))}   # #13 only; #18 raised hulls stay out of the nav
    g = GLB('AssetTools seed_nav_input v3 (MP_IAC_Seed nav input: shipped collision + authored hulls of switched placements)')
    def copy(j, bn, node, cache):
        mi = node['mesh']
        if mi not in cache:
            prims = []
            for pr in j['meshes'][mi]['primitives']:
                P = accessor(j, bn, pr['attributes']['POSITION']).astype('f4'); p2 = {'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)}}
                if 'indices' in pr: p2['indices'] = g.acc(accessor(j, bn, pr['indices']).astype('u4'), 'SCALAR', target=34963)
                prims.append(p2)
            cache[mi] = g.mesh(j['meshes'][mi].get('name', ''), prims)
        g.node(dict(node, mesh=cache[mi]))
    ca, cl, n, h = {}, {}, 0, 0
    for node in aj['nodes']:
        if node.get('mesh') is not None: copy(aj, abin, node, ca); n += 1
    for node in lj['nodes']:
        ex = node.get('extras') or {}
        if node.get('mesh') is not None and ex.get('kind') == 'prop_simple' and (node.get('name'), ex.get('mesh'), json.dumps(node.get('matrix'))) in sw:
            copy(lj, lbin, node, cl); h += 1
    D3 = DST + '_v3'; os.makedirs(D3, exist_ok=True); g.write(os.path.join(D3, 'collision_pawn.glb'))
    ph = json.load(open(os.path.join(SH, 'physics.json'), encoding='utf-8')); ph['nav_input_note'] = 'nav build input only: shipped collision + authored hulls of switched placements'
    json.dump(ph, open(os.path.join(D3, 'physics.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print('shipped nodes', n, '+ authored hulls', h, 'of switched', len(sw), '->', D3)

def main():
    bj, bbin = read_glb(os.path.join(LIVE, 'collision_pawn.glb'))
    g = GLB('AssetTools seed_nav_input (MP_IAC_Seed nav input: live minus BlockingVolume_9745)'); copied = {}; n = d = 0
    for node in bj.get('nodes', []):
        mi = node.get('mesh')
        if mi is None: continue
        if node.get('name') in DROP: d += 1; continue
        if mi not in copied:
            prims = []
            for pr in bj['meshes'][mi]['primitives']:
                P = accessor(bj, bbin, pr['attributes']['POSITION']).astype('f4'); p2 = {'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)}}
                if 'indices' in pr: p2['indices'] = g.acc(accessor(bj, bbin, pr['indices']).astype('u4'), 'SCALAR', target=34963)
                prims.append(p2)
            copied[mi] = g.mesh(bj['meshes'][mi].get('name', ''), prims)
        g.node(dict(node, mesh=copied[mi])); n += 1
    os.makedirs(DST, exist_ok=True); g.write(os.path.join(DST, 'collision_pawn.glb'))
    ph = json.load(open(os.path.join(LIVE, 'physics.json'), encoding='utf-8'))
    ph['volumes'] = [v for v in ph['volumes'] if v['actor'] not in DROP]
    ph['nav_input_note'] = 'nav build input only: live collision minus BlockingVolume_9745 (authored hulls kept)'
    json.dump(ph, open(os.path.join(DST, 'physics.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print('nodes copied', n, 'dropped', d, '->', DST)

if __name__ == '__main__':
    union() if sys.argv[1:] == ['union'] else main()
