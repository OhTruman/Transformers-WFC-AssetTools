"""Jet / air navigation layer reconstructed from pawn collision -> Maps/<MAP>/bot_nav_air.json   (run after bot_nav.py)

  python bot_nav_air.py <MAP>        (run under run_bounded.py)

PC ADAPTATION (WFC versus maps ship no air nav; Escalation's AirPathNode / TnTacticalAirPathNode are the original analogue).
Method (glTF metres, Y-up):
1. Region = bot_nav anchors' bounds + XZ margin, from the lowest ground cell to AIR_CEIL_M above the highest anchor.
2. Every collision_pawn triangle (oversized > HUGE_M2 excluded, as in bot_nav) is point-sampled at <= VOX/2 into occupied voxels;
   occupancy is dilated by ceil(AIR_RADIUS / VOX) voxels (clearance for the flying vehicle).
3. Free voxels are flood-filled (6-neighbour) from the voxels directly above playable ground cells; unreachable pockets are
   dropped. Free space is stored as per-column vertical spans [x, z, y0, y1] (voxel indices) for compact A* lookup.
4. Takeoff / landing links: every bot_nav cell whose centroid column is free from ground + AIR_LIFT_M upward gets a link to the
   voxel above it (direction both: takeoff = transform to vehicle and lift; landing = descend and transform).
5. Anchors (bot_nav anchors) that have no ground approach cell get an air_approach voxel (nearest free voxel within 12 m).
Parameters (PROVISIONAL unless marked) are written to the header.
"""
import json, math, os, sys, time
from collections import deque, defaultdict
from collections import OrderedDict as OD
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import VS  # noqa: E402
import map_structure_audit as MSA  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_ORB_Debris'
OUT = os.path.join(VS, 'Maps', MAP)
VOX = 2.0
P = OD([
    ('voxel_m', (VOX, 'tool parameter')),
    ('air_radius_m', (4.4, 'vehicle radius from versus TnReachSpec CollisionRadius 440 cm (CONFIRMED); jets fly RB physics (RE) - PROVISIONAL use')),
    ('air_ceiling_above_anchors_m', (60.0, 'PROVISIONAL: no authored flight ceiling found for versus maps')),
    ('xz_margin_m', (60.0, 'region margin around anchors')),
    ('air_lift_m', (8.0, 'PROVISIONAL: clear height above a ground cell required for a takeoff / landing link')),
    ('air_approach_radius_m', (20.0, 'PROVISIONAL: max distance from an anchor to its air approach voxel')),
])

def main():
    t0 = time.time()
    nav = json.load(open(os.path.join(OUT, 'bot_nav.json'), encoding='utf-8'))
    A = np.array([a['location_gltf'] for a in nav['anchors'] if a.get('location_gltf')])
    m = P['xz_margin_m'][0]
    gy = min(c['height_range_m'][0] for c in nav['cells']) if nav['cells'] else A[:, 1].min()
    lo = np.array([A[:, 0].min() - m, gy - VOX, A[:, 2].min() - m])
    hi = np.array([A[:, 0].max() + m, A[:, 1].max() + P['air_ceiling_above_anchors_m'][0], A[:, 2].max() + m])
    dims = np.ceil((hi - lo) / VOX).astype(int) + 1
    occ = np.zeros(dims, dtype=bool)
    dropped = 0
    for j, n, mat, T, agree, det in MSA.node_tris(os.path.join(OUT, 'collision_pawn.glb')):
        if not len(T): continue
        mn = T.min(1); mx = T.max(1)
        T = T[(mx >= lo).all(1) & (mn <= hi).all(1)]
        if not len(T): continue
        e1 = T[:, 1] - T[:, 0]; e2 = T[:, 2] - T[:, 0]; area = np.linalg.norm(np.cross(e1, e2), axis=1) / 2
        dropped += int((area > MSA.HUGE_M2).sum()); T = T[area <= MSA.HUGE_M2]
        for t in T:
            L = max(np.linalg.norm(t[1] - t[0]), np.linalg.norm(t[2] - t[0]), np.linalg.norm(t[2] - t[1]))
            k = max(2, int(math.ceil(L / (VOX / 2))) + 1)
            u, v = np.meshgrid(np.linspace(0, 1, k), np.linspace(0, 1, k)); msk = (u + v) <= 1
            pts = t[0] + np.outer(u[msk], t[1] - t[0]) + np.outer(v[msk], t[2] - t[0])
            idx = np.floor((pts - lo) / VOX).astype(int)
            ok = ((idx >= 0) & (idx < dims)).all(1); idx = idx[ok]
            occ[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    # dilate by the air radius
    r = int(math.ceil(P['air_radius_m'][0] / VOX))
    dil = occ.copy()
    for ax in range(3):
        cur = dil.copy()
        for s in range(1, r + 1):
            cur |= np.roll(dil, s, axis=ax) | np.roll(dil, -s, axis=ax)
        dil = cur
    free = ~dil
    # seeds: voxels above playable ground cells
    vidx = lambda p: tuple(np.floor((np.array(p) - lo) / VOX).astype(int))
    seeds = []
    lift = int(math.ceil(P['air_lift_m'][0] / VOX))
    takeoff = []
    for c in nav['cells']:
        x, y, z = c['centroid_gltf']
        i, jy, k = vidx([x, y, z])
        if not (0 <= i < dims[0] and 0 <= k < dims[2]): continue
        # rise from the ground voxel: no real geometry overhead (undilated occupancy), first free (dilated) voxel within
        # r + lift voxels is the takeoff / landing voxel
        top = None
        for q in range(jy + 1, min(dims[1], jy + 2 + r + lift)):
            if occ[i, q, k]: break
            if free[i, q, k]: top = q; break
        if top is not None:
            v = (i, top, k); seeds.append(v)
            takeoff.append({'cell': c['id'], 'air_voxel': list(map(int, v)), 'lift_m': round((top + 0.5) * VOX + lo[1] - y, 2)})
    reach = np.zeros(dims, dtype=bool); dq = deque()
    for s in seeds:
        if free[s] and not reach[s]: reach[s] = True; dq.append(s)
    while dq:
        x, y, z = dq.popleft()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            q = (x + dx, y + dy, z + dz)
            if 0 <= q[0] < dims[0] and 0 <= q[1] < dims[1] and 0 <= q[2] < dims[2] and free[q] and not reach[q]:
                reach[q] = True; dq.append(q)
    spans = []
    for i in range(dims[0]):
        for k in range(dims[2]):
            col = reach[i, :, k]
            if not col.any(): continue
            y = 0
            while y < dims[1]:
                if col[y]:
                    y0 = y
                    while y < dims[1] and col[y]: y += 1
                    spans.append([i, k, y0, y - 1])
                else: y += 1
    # air approach for anchors without a ground approach cell (or all objectives, for jets)
    rv = np.argwhere(reach)
    centres = lo + (rv + 0.5) * VOX
    approaches = []
    for a in nav['anchors']:
        if not a.get('location_gltf'): continue
        d = np.linalg.norm(centres - np.array(a['location_gltf']), axis=1) if len(centres) else np.array([])
        if len(d) and d.min() <= P['air_approach_radius_m'][0]:
            approaches.append({'actor': a['actor'], 'kind': a['kind'], 'ground_approach_cell': a.get('approach_cell'),
                               'air_voxel': list(map(int, rv[int(d.argmin())])), 'distance_m': round(float(d.min()), 2)})
    out = OD([
        ('map', MAP), ('generated_by', 'AssetTools/scripts/wfc/bot_nav_air.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
        ('status', 'PC ADAPTATION (no versus air nav shipped; Escalation AirPathNode is the original analogue)'),
        ('units', 'gltf metres, Y-up; voxel index (i, j, k) -> centre = origin + (index + 0.5) * voxel_m along (x, y, z)'),
        ('grid', {'origin_gltf': [round(float(v), 3) for v in lo], 'voxel_m': VOX, 'dims': [int(v) for v in dims]}),
        ('parameters', OD((k, {'value': v[0], 'source': v[1]}) for k, v in P.items())),
        ('free_spans', spans),
        ('free_spans_format', '[i, k, j0, j1]: voxels (i, j, k) for j0 <= j <= j1 are free and reachable (6-neighbour connectivity)'),
        ('takeoff_landing', takeoff), ('anchor_air_approach', approaches),
        ('stats', OD([('free_voxels', int(reach.sum())), ('spans', len(spans)), ('takeoff_links', len(takeoff)),
                      ('anchors_with_air_approach', len(approaches)), ('anchors', len(nav['anchors'])),
                      ('ground_unreachable_anchors_with_air_approach',
                       sum(1 for x in approaches if x['ground_approach_cell'] is None)),
                      ('ground_unreachable_anchors', sum(1 for a in nav['anchors'] if a.get('approach_cell') is None)),
                      ('oversized_triangles_excluded', dropped), ('seconds', round(time.time() - t0, 1))]))])
    json.dump(out, open(os.path.join(OUT, 'bot_nav_air.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    print(json.dumps(out['stats']))

if __name__ == '__main__':
    main()
