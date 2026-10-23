"""Playtest 2026-10-23 #10 / #13 (MP_IAC_Seed): collision vs visible geometry, read-only.

#10 oversized vertical collision near the central hole: pawn-collision nodes (collision_pawn.glb) whose top rises well above the same
    actor's visible mesh (world.glb, matched by node name), plus tall blocking volumes (physics.json).
#13 clip-in on cylindrical props: nodes whose collision footprint is inset from the visible mesh (the visual extends beyond the hull).
Writes seed_collision.json here (every candidate with both AABBs, glTF metres, and the source object).
"""
import json, os, sys, re
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'wfc'))
import map_structure_audit as MSA  # noqa: E402
VS = r'F:\Transformers Rebuild\ExtractedAssets\VerticalSlice\Maps\MP_IAC_Seed'

def boxes(path):
    out = {}
    for j, n, mat, T, agree, det in MSA.node_tris(path):
        if not len(T): continue
        P = T.reshape(-1, 3); nm = n.get('name') or ''
        lo, hi = P.min(0), P.max(0)
        if nm in out: lo, hi = np.minimum(lo, out[nm][0]), np.maximum(hi, out[nm][1])
        out[nm] = (lo, hi)
    return out

def key(nm):
    """actor-level key shared by world.glb and collision node names (strip component / LOD suffixes)"""
    return re.sub(r'(_SMC|_LOD\d+|_\d+_col|_col\w*|#\d+)$', '', nm)

def main():
    col = boxes(os.path.join(VS, 'collision_pawn.glb'))
    vis = boxes(os.path.join(VS, 'world.glb'))
    vis_k = {}
    for nm, b in vis.items(): vis_k.setdefault(key(nm), []).append(b)
    g = json.load(open(os.path.join(VS, 'gameplay.json'), encoding='utf-8'))
    pts = np.array([e['location_gltf'] for e in (g.get('player_starts') or []) + (g.get('pickups') or []) if e.get('location_gltf')])
    centre = pts.mean(0)
    rows_tall, rows_inset, unmatched_tall = [], [], []
    for nm, (lo, hi) in col.items():
        size = hi - lo
        vb = vis_k.get(key(nm)) or vis_k.get(nm)
        rec = {'node': nm, 'col_aabb': [lo.round(2).tolist(), hi.round(2).tolist()], 'col_height_m': round(float(size[1]), 2),
               'dist_from_centre_xz_m': round(float(np.hypot(*(((lo + hi) / 2 - centre)[[0, 2]]))), 1)}
        if vb:
            vlo = np.min([b[0] for b in vb], 0); vhi = np.max([b[1] for b in vb], 0)
            rec.update({'vis_aabb': [vlo.round(2).tolist(), vhi.round(2).tolist()], 'vis_height_m': round(float((vhi - vlo)[1]), 2),
                        'col_top_above_vis_top_m': round(float(hi[1] - vhi[1]), 2)})
            if hi[1] - vhi[1] > 3.0 and size[1] > 6.0: rows_tall.append(rec)
            inset = [round(float(lo[i] - vlo[i]), 2) for i in (0, 2)] + [round(float(vhi[i] - hi[i]), 2) for i in (0, 2)]
            if max(inset) > 0.4 and 1.0 < max(size[0], size[2]) < 20.0:
                rec['footprint_inset_m (x-, z-, x+, z+)'] = inset; rows_inset.append(dict(rec))
        elif size[1] > 15.0:
            unmatched_tall.append(rec)
    vols = []
    for v in json.load(open(os.path.join(VS, 'physics.json'), encoding='utf-8')).get('volumes') or []:
        if not v.get('blocks_pawn') or not v.get('polygons_gltf'): continue
        P = np.array([p for poly in v['polygons_gltf'] for p in poly]); lo, hi = P.min(0), P.max(0)
        if hi[1] - lo[1] > 15.0:
            vols.append({'actor': v['actor'], 'class': v['class'], 'aabb': [lo.round(2).tolist(), hi.round(2).tolist()],
                         'height_m': round(float(hi[1] - lo[1]), 2),
                         'dist_from_centre_xz_m': round(float(np.hypot(*(((lo + hi) / 2 - centre)[[0, 2]]))), 1)})
    out = {'map': 'MP_IAC_Seed', 'centre_gltf (mean of starts + pickups)': centre.round(2).tolist(),
           'collision_taller_than_visual': sorted(rows_tall, key=lambda r: r['dist_from_centre_xz_m']),
           'tall_collision_without_visual_match': sorted(unmatched_tall, key=lambda r: r['dist_from_centre_xz_m']),
           'tall_pawn_blocking_volumes': sorted(vols, key=lambda r: r['dist_from_centre_xz_m']),
           'collision_inset_from_visual': sorted(rows_inset, key=lambda r: -max(r['footprint_inset_m (x-, z-, x+, z+)']))}
    json.dump(out, open(os.path.join(HERE, 'seed_collision.json'), 'w', encoding='utf-8'), indent=1)
    print('centre', out['centre_gltf (mean of starts + pickups)'], '| collision nodes', len(col), 'visual nodes', len(vis))
    for k in ('collision_taller_than_visual', 'tall_collision_without_visual_match', 'tall_pawn_blocking_volumes', 'collision_inset_from_visual'):
        print('==', k, len(out[k]))
        for r in out[k][:8]: print('  ', {x: r[x] for x in r if x not in ('col_aabb', 'vis_aabb', 'aabb')})

if __name__ == '__main__':
    main()
