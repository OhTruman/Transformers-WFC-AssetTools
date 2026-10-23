"""Nav input with toggleable blockers OPEN (Gameplay E2b, 2026-10-23): the shipping collision of a map (overlay_20261023e when it holds the
map, else live) minus the named volume nodes (BrokenHope's 7 DynamicBlockingVolumes the door generators turn off), so bot_nav builds
cells through the doorways; Gameplay blocks the cells under a volume while it is on. Nav input only (never shipped as collision).
After the nav build, 'cells' lists per volume the nav cells whose centroid lies inside that volume's convex polygons (+ 0.5 m pad).

    python nav_input_open.py build <MAP> <VOLUME> [...]     -> out/pc_adapt/<MAP>/nav_input_open/{collision_pawn.glb, physics.json}
    python nav_input_open.py cells <MAP> <NAV_DIR> <VOLUME> [...]   -> <NAV_DIR>/blocker_cells.json
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
from vs_common import ROOT, GLB, read_glb, accessor  # noqa: E402
OVE = os.path.join(AT, 'work', 'overlay_20261023e', 'VerticalSlice', 'Maps')

def base(mp):
    o = os.path.join(OVE, mp)
    return o if os.path.exists(os.path.join(o, 'collision_pawn.glb')) else os.path.join(ROOT, 'VerticalSlice', 'Maps', mp)

def build(mp, drop):
    B = base(mp); DST = os.path.join(AT, 'out', 'pc_adapt', mp, 'nav_input_open')
    bj, bbin = read_glb(os.path.join(B, 'collision_pawn.glb')); g = GLB('AssetTools nav_input_open (%s minus %d volumes)' % (mp, len(drop)))
    cache, n, d = {}, 0, 0
    for node in bj['nodes']:
        mi = node.get('mesh')
        if mi is None: continue
        if node.get('name') in drop: d += 1; continue
        if mi not in cache:
            prims = []
            for pr in bj['meshes'][mi]['primitives']:
                P = accessor(bj, bbin, pr['attributes']['POSITION']).astype('f4'); p2 = {'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)}}
                if 'indices' in pr: p2['indices'] = g.acc(accessor(bj, bbin, pr['indices']).astype('u4'), 'SCALAR', target=34963)
                prims.append(p2)
            cache[mi] = g.mesh(bj['meshes'][mi].get('name', ''), prims)
        g.node(dict(node, mesh=cache[mi])); n += 1
    os.makedirs(DST, exist_ok=True); g.write(os.path.join(DST, 'collision_pawn.glb'))
    ph = json.load(open(os.path.join(B, 'physics.json'), encoding='utf-8'))
    ph['volumes'] = [v for v in ph['volumes'] if v['actor'] not in drop]
    ph['nav_input_note'] = 'nav build input only: shipping collision minus %s (toggleable blockers open)' % sorted(drop)
    json.dump(ph, open(os.path.join(DST, 'physics.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(mp, 'base', B, 'nodes', n, 'dropped', d, '->', DST)

def cells(mp, navdir, vols):
    ph = json.load(open(os.path.join(base(mp), 'physics.json'), encoding='utf-8')); V = {v['actor']: v for v in ph['volumes']}
    nav = json.load(open(os.path.join(navdir, 'bot_nav.json'), encoding='utf-8'))
    out = {}
    for name in vols:
        polys = [np.array(p, float) for p in V[name]['polygons_gltf']]; C = np.concatenate(polys).mean(0); planes = []
        for p in polys:
            nrm = np.cross(p[1] - p[0], p[2] - p[0]); ln = np.linalg.norm(nrm)
            if ln < 1e-9: continue
            nrm /= ln
            if np.dot(nrm, p[0] - C) < 0: nrm = -nrm
            planes.append((nrm, p[0]))
        inside = lambda x: all(np.dot(nn, x - o) <= 0.5 for nn, o in planes)
        hit = [c['id'] for c in nav['cells'] if inside(np.array(c['centroid_gltf'], float) + [0, 0.5, 0])]
        out[name] = {'cells': hit, 'area_m2': round(sum(c['area_m2'] for c in nav['cells'] if c['id'] in set(hit)), 1)}
        print(name, len(hit), 'cells', out[name]['area_m2'], 'm2')
    json.dump({'map': mp, 'nav': os.path.relpath(os.path.join(navdir, 'bot_nav.json'), AT).replace(os.sep, '/'),
               'rule': 'cell centroid (+0.5 m up) inside the volume convex polygons with 0.5 m pad (PROVISIONAL: convex-hull test)', 'volumes': out},
              open(os.path.join(navdir, 'blocker_cells.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'build': build(a[1], set(a[2:]))
    else: cells(a[1], a[2], a[3:])
