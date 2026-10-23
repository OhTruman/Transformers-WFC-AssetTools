"""Gameplay #18 / Integration 2026-10-23: authored pawn collision standing above the visible floor (simple hulls larger than their meshes,
BlockingVolume tops), the inverse of Seed #13. Read-only.

    python hull_float_audit.py <MAP>        -> work/playtest_20261023/hull_float/<MAP>.json

Per collision_pawn.glb node of kind prop_simple or a volume class (BSP / per-poly props are the visual surface itself):
  1. its walkable top: every triangle with |normal.y| >= WALK_NY (0.7, bot_nav's rule) rasterised on a 1 m XZ grid (cell centres),
     keeping the TOPMOST hull height per cell (where a robot stands);
  2. a vertical probe against world.glb (visible render geometry; nodes tagged hidden_game left out; triangles over HUGE_M2 or spanning
     more than 128 m in X or Z kept out of the grid: the Streets sky-dome / backdrop guard): visual surfaces within (+0.05, +0.6] m above
     the sample mean the hull is under a visible skin there (not floating); otherwise gap = sample height - the highest visual surface at
     or below +0.05 m (no visual below: gap = null, 'no_visual_below');
  3. only where robots STAND: the map's bot_nav.json cells rasterised on the same grid; each nav sample is attributed to the audited
     node whose walkable top lies within the nav cell's recorded height range +- 0.4 m (the highest such); nav on BSP / per-poly surfaces is the render geometry itself (skipped);
     unreachable hull tops and hull tops under another walked surface are not reported;
  4. per sample: 'raised' 0.5 m < gap < 5 m (standing above the visible floor: Gameplay #18), 'large' gap >= 5 m (overhang edge or
     catwalk: Gameplay's probable false positives, list only), 'no_visual_below' (UNKNOWN: no visual surface under the sample in the grid).
     Per node: reachable samples, m^2 of each class, raised gap median / max; walkable = raised >= 1 m^2.
"""
import json, os, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
import map_structure_audit as MSA  # noqa: E402
VSM = r'F:\Transformers Rebuild\ExtractedAssets\VerticalSlice\Maps'
G = 2.0            # visual grid cell (m)
S = 1.0            # sample spacing (m)
SPAN_MAX = 128.0   # backdrop guard (m)
FLOAT_M, COVER_M, EPS = 0.5, 0.6, 0.05
VOLUME_KINDS = ('BlockingVolume', 'TnBlockingVolume', 'TnForcedDirVolume', 'DynamicBlockingVolume')

def tri_ny(T):
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); ln = np.linalg.norm(n, axis=1)
    return np.abs(n[:, 1]) / np.maximum(ln, 1e-12), ln / 2

def raster_top(T):
    """walkable tris -> {(ix, iz): topmost y} at cell centres (ix + 0.5) * S"""
    ny, area = tri_ny(T); T = T[(ny >= MSA.WALK_NY) & (area > 1e-6)]
    top = {}
    for t in T:
        x0, x1 = t[:, 0].min(), t[:, 0].max(); z0, z1 = t[:, 2].min(), t[:, 2].max()
        ix = np.arange(np.floor(x0 / S - 0.5), np.ceil(x1 / S - 0.5) + 1); iz = np.arange(np.floor(z0 / S - 0.5), np.ceil(z1 / S - 0.5) + 1)
        if len(ix) * len(iz) > 4_000_000: continue
        X, Z = np.meshgrid((ix + 0.5) * S, (iz + 0.5) * S); X = X.ravel(); Z = Z.ravel()
        y = bary_y(t, X, Z)
        ok = ~np.isnan(y)
        for a, b, h in zip(np.floor(X[ok] / S).astype(int), np.floor(Z[ok] / S).astype(int), y[ok]):
            if h > top.get((a, b), -1e18): top[(a, b)] = h
    return top

def bary_y(t, X, Z):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
    d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
    if abs(d) < 1e-12: return np.full(len(X), np.nan)
    l1 = ((bz - cz) * (X - cx) + (cx - bx) * (Z - cz)) / d; l2 = ((cz - az) * (X - cx) + (ax - cx) * (Z - cz)) / d; l3 = 1 - l1 - l2
    e = -1e-6
    y = l1 * ay + l2 * by + l3 * cy
    return np.where((l1 >= e) & (l2 >= e) & (l3 >= e), y, np.nan)

def nav_raster(D):
    """bot_nav cells -> {(ix, iz): [(lo, hi), ...]}: the cell's recorded height range (height_range_m; cells are stored flat, so on
    slopes the polygon height alone can sit ~1 m off the collision surface) on the sample grid"""
    out = defaultdict(list)
    for c in json.load(open(os.path.join(D, 'bot_nav.json'), encoding='utf-8'))['cells']:
        P = np.array(c['vertices_gltf'], float)
        if len(P) < 3: continue
        hr = c.get('height_range_m') or [P[:, 1].min(), P[:, 1].max()]
        rng = (min(hr[0], P[:, 1].min()), max(hr[1], P[:, 1].max()))
        for k in range(1, len(P) - 1):
            t = np.array([P[0], P[k], P[k + 1]])
            ix = np.arange(np.floor(t[:, 0].min() / S - 0.5), np.ceil(t[:, 0].max() / S - 0.5) + 1)
            iz = np.arange(np.floor(t[:, 2].min() / S - 0.5), np.ceil(t[:, 2].max() / S - 0.5) + 1)
            X, Z = np.meshgrid((ix + 0.5) * S, (iz + 0.5) * S); X = X.ravel(); Z = Z.ravel()
            y = bary_y(t, X, Z); ok = ~np.isnan(y)
            for a, b in zip(np.floor(X[ok] / S).astype(int), np.floor(Z[ok] / S).astype(int)): out[(a, b)].append(rng)
    return out

def main(mp, diag=()):
    D = os.path.join(VSM, mp)
    nav = nav_raster(D)
    # ---- visual grid
    tris = []
    for j, n, mat, T, agree, det in MSA.node_tris(os.path.join(D, 'world.glb')):
        if (n.get('extras') or {}).get('hidden_game') or not len(T): continue
        ny, area = tri_ny(T)
        span = np.maximum(T[:, :, 0].max(1) - T[:, :, 0].min(1), T[:, :, 2].max(1) - T[:, :, 2].min(1))
        k = (ny > 0.05) & (area <= MSA.HUGE_M2) & (span <= SPAN_MAX) & (area > 1e-8)
        if k.any(): tris.append(T[k].astype('f4'))
    V = np.concatenate(tris) if tris else np.zeros((0, 3, 3), 'f4')
    grid = defaultdict(list)
    lo = np.floor(V[:, :, [0, 2]].min(1) / G).astype(int); hi = np.floor(V[:, :, [0, 2]].max(1) / G).astype(int)
    one = (lo == hi).all(1)
    for i, a, b in zip(np.nonzero(one)[0], lo[one, 0], lo[one, 1]): grid[(a, b)].append(i)
    for i in np.nonzero(~one)[0]:
        for a in range(lo[i, 0], hi[i, 0] + 1):
            for b in range(lo[i, 1], hi[i, 1] + 1): grid[(a, b)].append(i)
    # ---- collision nodes
    nodes = []
    for j, n, mat, T, agree, det in MSA.node_tris(os.path.join(D, 'collision_pawn.glb')):
        ex = n.get('extras') or {}; kind = ex.get('kind', '')
        if not (kind == 'prop_simple' or kind in VOLUME_KINDS) or not len(T): continue
        nodes.append((n.get('name'), ex.get('mesh'), n.get('matrix'), kind, T))
    # robots stand on the nav surface: attribute each nav sample to the audited node whose walkable top supplies it (within 0.4 m;
    # bot_nav cells sit ~0.1 m above the collision top); samples on BSP / per-poly surfaces are the render geometry itself (skipped)
    tops = defaultdict(list)
    node_top = []
    for idx, (name, mesh, matrix, kind, T) in enumerate(nodes):
        t = raster_top(T); node_top.append(t)
        for k, h in t.items(): tops[k].append((h, idx))
    per_node = defaultdict(dict)
    for k, rs in nav.items():
        cands = tops.get(k)
        if not cands: continue
        for lo_, hi_ in set(rs):
            inr = [c for c in cands if lo_ - 0.4 <= c[0] <= hi_ + 0.4]
            if inr:
                h, idx = max(inr, key=lambda c: c[0]); per_node[idx][k] = h
    rows = []
    for idx, top in per_node.items():
        name, mesh, matrix, kind, T = nodes[idx]
        if name in diag: print('DIAG', name, kind, mesh, 'standing samples', len(top))
        by_cell = defaultdict(list)
        for (a, b), h in top.items(): by_cell[(int(np.floor((a + 0.5) * S / G)), int(np.floor((b + 0.5) * S / G)))].append((a, b, h))
        gaps, nvb = [], 0
        for c, smp in by_cell.items():
            cand = grid.get(c)
            X = np.array([(a + 0.5) * S for a, b, h in smp]); Z = np.array([(b + 0.5) * S for a, b, h in smp]); H = np.array([h for a, b, h in smp])
            if not cand: gaps += [None] * len(smp); nvb += len(smp); continue
            Y = np.array([bary_y(V[i].astype('f8'), X, Z) for i in cand])          # (C, S)
            for s_ in range(len(smp)):
                ys = Y[:, s_]; ys = ys[~np.isnan(ys)]
                if ((ys > H[s_] + EPS) & (ys <= H[s_] + COVER_M)).any(): gaps.append(0.0); continue
                below = ys[ys <= H[s_] + EPS]
                if len(below): gaps.append(float(H[s_] - below.max()))
                else: gaps.append(None); nvb += 1
        raised = [g for g in gaps if g is not None and FLOAT_M < g < 5.0]; large = [g for g in gaps if g is not None and g >= 5.0]
        if name in diag: print('DIAG', name, 'gaps', sorted(round(g, 2) for g in gaps if g is not None)[-12:], 'nvb', nvb)
        if not (raised or large or nvb): continue
        Pw = T.reshape(-1, 3)
        rows.append({'actor': name, 'kind': kind, 'mesh': mesh, 'matrix': matrix, 'standing_samples': len(gaps),
                     'raised_m2': len(raised) * S * S, 'raised_fraction': round(len(raised) / len(gaps), 3),
                     'raised_gap_median_m': round(float(np.median(raised)), 2) if raised else None,
                     'raised_gap_max_m': round(max(raised), 2) if raised else None,
                     'large_gap_m2 (overhang / catwalk, list only)': len(large) * S * S, 'no_visual_below_m2 (UNKNOWN)': nvb * S * S,
                     'top_y_m': round(float(max(top.values())), 2), 'aabb_gltf': [Pw.min(0).round(2).tolist(), Pw.max(0).round(2).tolist()],
                     'walkable_raised': len(raised) >= 1})
    rows.sort(key=lambda r: (-r['raised_m2'], -r['large_gap_m2 (overhang / catwalk, list only)']))
    od = os.path.join(HERE, 'hull_float'); os.makedirs(od, exist_ok=True)
    out = {'map': mp, 'generated_by': 'AssetTools/work/playtest_20261023/hull_float_audit.py', 'rule': __doc__.split('\n\n', 1)[1].strip(),
           'visual_tris_in_grid': int(len(V)), 'collision_nodes_audited': len(nodes), 'nodes_floating': len(rows),
           'walkable_raised_nodes': sum(r['walkable_raised'] for r in rows),
           'by_kind_walkable_raised': {k: sum(1 for r in rows if r['kind'] == k and r['walkable_raised']) for k in sorted({r['kind'] for r in rows})},
           'rows': rows}
    json.dump(out, open(os.path.join(od, mp + '.json'), 'w', encoding='utf-8'), indent=1)
    print(mp, 'visual tris', len(V), 'audited', len(nodes), 'listed', len(rows), 'walkable raised', out['walkable_raised_nodes'], out['by_kind_walkable_raised'])
    for r in [r for r in rows if r['walkable_raised']][:8]:
        print('   %-34s %-30s %5.0f m2 gap med %s max %s' % (r['actor'], (r['mesh'] or r['kind']).split('.')[-1][:30], r['raised_m2'], r['raised_gap_median_m'], r['raised_gap_max_m']))

if __name__ == '__main__':
    main(sys.argv[1], tuple(a for a in sys.argv[2:]))
