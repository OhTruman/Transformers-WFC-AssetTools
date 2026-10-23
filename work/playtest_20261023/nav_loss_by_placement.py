"""Nav regression diagnosis: walkable nav area (bot_nav cells, 1 m raster) inside each switched placement's XZ footprint, live vs adapted,
plus the placement's per-poly surface stats (upward walkable area of its render triangles vs its simple hull's). Read-only.
    python nav_loss_by_placement.py <MAP>
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc')); sys.path.insert(0, HERE)
import map_structure_audit as MSA  # noqa: E402
from hull_float_audit import nav_raster  # noqa: E402
VSM = r'F:\Transformers Rebuild\ExtractedAssets\VerticalSlice\Maps'

def walk_area(T):
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); ln = np.linalg.norm(n, axis=1); ny = n[:, 1] / np.maximum(ln, 1e-12)
    return float((ln[ny >= MSA.WALK_NY] / 2).sum()), float((ln[ny <= -MSA.WALK_NY] / 2).sum())

def main(mp):
    D = os.path.join(VSM, mp); A = os.path.join(AT, 'out', 'pc_adapt', mp)
    navL, navA = nav_raster(D), nav_raster(A)
    live = {}
    for j, n, mat, T, agree, det in MSA.node_tris(os.path.join(D, 'collision_pawn.glb')):
        ex = n.get('extras') or {}
        live.setdefault((n.get('name'), ex.get('mesh'), json.dumps(n.get('matrix'))), []).append(T)
    rows = []
    for j, n, mat, T, agree, det in MSA.node_tris(os.path.join(A, 'collision_pawn.glb')):
        ex = n.get('extras') or {}
        if 'hull stands' not in str(ex.get('pc_adaptation')): continue
        k = (n.get('name'), ex.get('mesh'), json.dumps(n.get('matrix')))
        H = np.concatenate(live.get(k, [np.zeros((0, 3, 3))]))
        P = T.reshape(-1, 3); lo, hi = P.min(0), P.max(0)
        cells = [(a, b) for a in range(int(np.floor(lo[0])), int(np.ceil(hi[0]))) for b in range(int(np.floor(lo[2])), int(np.ceil(hi[2])))]
        inside = lambda nav: sum(1 for c in cells if any(r[0] - 1.0 <= hi[1] + 0.5 and r[1] + 1.0 >= lo[1] - 0.5 for r in nav.get(c, ())))
        up_p, dn_p = walk_area(T); up_h, _ = walk_area(H) if len(H) else (0.0, 0.0)
        rows.append({'actor': k[0], 'mesh': (k[1] or '').split('.')[-1], 'det': round(det, 3), 'nav_m2_live': inside(navL), 'nav_m2_adapted': inside(navA),
                     'poly_up_walkable_m2': round(up_p), 'poly_down_facing_walkable_m2': round(dn_p), 'hull_up_walkable_m2': round(up_h)})
    rows.sort(key=lambda r: r['nav_m2_adapted'] - r['nav_m2_live'])
    json.dump(rows, open(os.path.join(HERE, 'nav_loss_%s.json' % mp), 'w', encoding='utf-8'), indent=1)
    print(mp, 'switched placements', len(rows), 'nav m2 live', sum(r['nav_m2_live'] for r in rows), 'adapted', sum(r['nav_m2_adapted'] for r in rows))
    for r in rows[:12]: print('  ', r)

if __name__ == '__main__':
    main(sys.argv[1])
