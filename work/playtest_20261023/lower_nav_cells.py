"""Lower a BotNav file's ORIGINAL NavigationCell polygons from pawn-centre height to the floor (Gameplay 2026-10-23: its off-mesh test is
findCell(pos, 0 m), and the authored cells sit ~1.75 m above the floor, so perched horde pawns never got a cell).

Per cell (every cell without flags.versus_only): a vertical trace from its centroid down to the pawn collision (the highest walkable-slope
collision triangle at or below centroid + 0.3 m, within 4 m below) gives floor_offset_m. All vertices, edge start / end points and the
centroid shift down by it (the polygon stays planar). No floor found: the map's median offset (flagged floor_traced false). Kept for reference:
authored_vertices_gltf, pawn_centre_y (the authored centroid height), floor_offset_m. Every link endpoint is traced the same way (offset
recorded as from_floor_offset_m / to_floor_offset_m), so floor-level points (versus cells) move by ~0. Runs on the file in place, idempotent
(cells that already carry authored_vertices_gltf are recomputed from it).

    python lower_nav_cells.py <bot_nav json> <collision_pawn.glb> [<collision_pawn.glb> ...]
"""
import json, os, statistics, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc')); sys.path.insert(0, HERE)
import map_structure_audit as MSA  # noqa: E402
from hull_float_audit import bary_y, tri_ny  # noqa: E402
G, UP, DOWN, SPAN_MAX = 2.0, 0.3, 4.0, 128.0

def grid_of(glbs):
    tris = []
    for p in glbs:
        for j, n, mat, T, agree, det in MSA.node_tris(p):
            if not len(T): continue
            ny, area = tri_ny(T)
            span = np.maximum(T[:, :, 0].max(1) - T[:, :, 0].min(1), T[:, :, 2].max(1) - T[:, :, 2].min(1))
            k = (ny >= 0.3) & (area <= MSA.HUGE_M2) & (span <= SPAN_MAX) & (area > 1e-8)
            if k.any(): tris.append(T[k].astype('f8'))
    V = np.concatenate(tris) if tris else np.zeros((0, 3, 3))
    grid = defaultdict(list)
    lo = np.floor(V[:, :, [0, 2]].min(1) / G).astype(int); hi = np.floor(V[:, :, [0, 2]].max(1) / G).astype(int)
    for i in range(len(V)):
        for a in range(lo[i, 0], hi[i, 0] + 1):
            for b in range(lo[i, 1], hi[i, 1] + 1): grid[(a, b)].append(i)
    return V, grid

def floor_at(V, grid, p):
    cand = grid.get((int(np.floor(p[0] / G)), int(np.floor(p[2] / G))))
    if not cand: return None
    best = None
    for i in cand:
        y = bary_y(V[i], np.array([p[0]]), np.array([p[2]]))[0]
        if not np.isnan(y) and p[1] - DOWN <= y <= p[1] + UP and (best is None or y > best): best = y
    return best

def main(path, glbs):
    nav = json.load(open(path, encoding='utf-8')); V, grid = grid_of(glbs)
    offs, traced = {}, 0
    orig = [c for c in nav['cells'] if not (c.get('flags') or {}).get('versus_only')]
    for c in orig:
        verts = c.get('authored_vertices_gltf') or c['vertices_gltf']
        cy = c.get('pawn_centre_y', c['centroid_gltf'][1]) if 'authored_vertices_gltf' in c else c['centroid_gltf'][1]
        cen = [c['centroid_gltf'][0], cy, c['centroid_gltf'][2]]
        f = floor_at(V, grid, cen)
        if f is not None: offs[c['id']] = cy - f; traced += 1
    med = statistics.median(offs.values()) if offs else 1.75
    for c in orig:
        verts = c.get('authored_vertices_gltf') or c['vertices_gltf']
        cy = c.get('pawn_centre_y', c['centroid_gltf'][1]) if 'authored_vertices_gltf' in c else c['centroid_gltf'][1]
        d = offs.get(c['id'], med)
        c['authored_vertices_gltf'] = verts; c['pawn_centre_y'] = round(cy, 4); c['floor_offset_m'] = round(d, 3)
        c.setdefault('flags', {})['floor_traced'] = c['id'] in offs
        c['vertices_gltf'] = [[v[0], round(v[1] - d, 4), v[2]] for v in verts]
        c['centroid_gltf'] = [c['centroid_gltf'][0], round(cy - d, 4), c['centroid_gltf'][2]]
        for e in c.get('edges') or []:
            for k in ('start', 'end'):
                if k + '_authored' not in e: e[k + '_authored'] = e[k]
                e[k] = [e[k + '_authored'][0], round(e[k + '_authored'][1] - d, 4), e[k + '_authored'][2]]
        ys = [v[1] for v in c['vertices_gltf']]
        if 'height_range_m' in c: c['height_range_m'] = [round(min(ys), 3), round(max(ys), 3)]
    lt = 0
    for l in nav.get('links') or []:
        for k in ('from', 'to'):
            a = l.get(k + '_gltf_authored') or l.get(k + '_gltf')
            if not a: continue
            l[k + '_gltf_authored'] = a
            f = floor_at(V, grid, a)
            d = (a[1] - f) if f is not None else 0.0
            if f is not None: lt += 1
            l[k + '_gltf'] = [a[0], round(a[1] - d, 4), a[2]]; l[k + '_floor_offset_m'] = round(d, 3)
        if 'rise_m' in l and l.get('from_gltf') and l.get('to_gltf'): l['rise_m'] = round(l['to_gltf'][1] - l['from_gltf'][1], 2)
    nav.setdefault('parameters', {})['cell_height'] = ('original cells lowered to the floor: per-cell ground trace against the pawn collision '
                                                      '(median offset %.2f m, %d / %d traced; untraced use the median); authored heights kept '
                                                      'in authored_vertices_gltf / pawn_centre_y' % (med, traced, len(orig)))
    json.dump(nav, open(path, 'w', encoding='utf-8'), separators=(',', ':'))
    o = sorted(offs.values())
    print(os.path.basename(os.path.dirname(path)) or path, 'cells', len(orig), 'traced', traced, 'median offset', round(med, 2),
          'p10/p90', (round(o[len(o) // 10], 2), round(o[9 * len(o) // 10], 2)) if o else None, '| link endpoints traced', lt)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
