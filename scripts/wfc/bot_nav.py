"""Bot navigation reconstructed from a map's pawn collision -> Maps/<MAP>/bot_nav.json + bot_nav.glb (debug mesh)

  python bot_nav.py <MAP>        (run under run_bounded.py)

PC ADAPTATION. WFC versus maps ship no bot navigation: their only nav data is TnReachSpec between player starts / pickups /
objective factories (RE notes/data/mp_navigation_audit.json, AssetTools navigation.json). The original Escalation maps carry
NavigationCell (convex polygon, _Edges{Start, End, Normal, Neighbor, Border}) + PathNode / TnTacticalPathNode; this output
follows that cell schema so versus and Escalation nav can be consumed alike (RE MP note addendum 1; Gameplay format request).

Method (glTF metres, Y-up; UE cm given alongside):
1. collision_pawn.glb triangles (oversized > HUGE_M2 kept out of every grid: Streets sky-dome memory incident).
2. Layered 1 m height grid of walkable surfaces (normal.y >= WALK_NY) [map_structure_audit.Layers].
3. Obstruction samples: every non-walkable triangle is point-sampled (0.5 m) into per-cell height lists; walkable surfaces
   above a floor count as ceilings. A floor cell is open at radius 0 if nothing occupies (h + STEP, h + AGENT_HEIGHT].
4. Connectivity: 4-neighbour cells with |dh| <= STEP and both open. Per-cell clearance radius = BFS distance (m) to the
   nearest non-open / missing cell on the connected layer (chessboard-free Manhattan approximation, conservative).
5. Cells with clearance >= MIN_RADIUS are merged greedily into axis-aligned rectangles per layer (|dh| <= MERGE_DH inside a
   rectangle) -> convex polygons. Each polygon: vertices (corner heights from its cells), min clearance radius, flags
   (vehicle_capable: clearance >= VEHICLE_RADIUS and open to VEHICLE_HEIGHT), edges with neighbour polygon or border.
6. Off-mesh links between non-connected layers in adjacent cells: jump_up (rise <= chassis JumpHeight, authored per chassis
   acrobatics), drop_down (fall <= MAX_DROP).
7. Cover hints: open boundary cells next to an obstruction of height >= COVER_LOW (half) / COVER_FULL (full) with its normal.
8. Anchors: player starts, pickups, objectives (gameplay.json actor names) snapped to their polygon.
Every parameter is written into the JSON header with its provenance (CONFIRMED authored / PROVISIONAL).
"""
import json, math, os, sys, time
from collections import Counter, defaultdict, deque
from collections import OrderedDict as OD
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import VS, GLB  # noqa: E402
import map_structure_audit as MSA  # noqa: E402
import authored as A  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
CELL = MSA.CELL
WALK_NY = MSA.WALK_NY
HUGE_M2 = MSA.HUGE_M2

class _Rec(dict):
    def __setitem__(self, k, v):
        super().__setitem__(k, v); self.new.append(k)

class SlopeLayers(MSA.Layers):
    """MSA.Layers + the walkable surface normal.y per sample (ramps may rise CELL * tan(slope) between cells)"""
    def __init__(self):
        super().__init__(); self.t = _Rec(); self.t.new = []; self.ny = {}
    def add_tris(self, T, tag):
        e1 = T[:, 1] - T[:, 0]; e2 = T[:, 2] - T[:, 0]
        nrm = np.cross(e1, e2); ln = np.linalg.norm(nrm, axis=1)
        ny = np.abs(nrm[:, 1]) / np.maximum(ln, 1e-12)
        for t, y in zip(T, ny):
            self.t.new = []
            super().add_tris(t[None], tag)
            for key in self.t.new: self.ny[key] = float(y)

def params():
    pawn = A.values('TransGame.Default__TnPlayerPawn') or {}
    cyl = A.values('TransGame.Default__TnPlayerPawn.CollisionCylinder') or {}
    wi = A.values('Engine.Default__WorldInfo') or {}
    jumps = {}
    cdir = os.path.join(VS, 'Characters')
    for cid in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        f = os.path.join(cdir, cid, 'character.json')
        if not os.path.exists(f): continue
        ac = ((json.load(open(f, encoding='utf-8')).get('stats') or {}).get('acrobatics') or {}).get('values') or {}
        if ac: jumps[cid] = {'JumpHeight_cm': ac.get('JumpHeight'), 'DoubleJumpHeight_cm': ac.get('DoubleJumpHeight'),
                             'HoverJumpHeight_cm': ac.get('HoverJumpHeight')}
    jh = [v['JumpHeight_cm'] for v in jumps.values() if v.get('JumpHeight_cm')]
    P = OD()
    P['cell_m'] = (CELL, 'grid resolution (tool parameter)')
    P['walkable_normal_y'] = (WALK_NY, 'CONFIRMED (RE STEPUP_LEDGE 2026-10-01): robot FormMovementCapabilities.WalkableFloorZ 0.7')
    P['step_m'] = (0.37, 'CONFIRMED (RE): MaxStepHeight 35 + MAXSTEPHEIGHTFUDGE 2 UU = step-up / step-down snap; neighbour cells may '
                         'additionally rise by CELL * tan(slope) on walkable ramps')
    P['agent_radius_default_m'] = (cyl.get('CollisionRadius', 175.0) / 100, 'CONFIRMED: TnPlayerPawn CollisionCylinder.CollisionRadius (cm)')
    P['agent_height_m'] = (2 * cyl.get('CollisionHeight', 200.0) / 100, 'CONFIRMED: 2 x TnPlayerPawn CollisionCylinder.CollisionHeight (half-height, cm)')
    P['min_radius_m'] = (1.0, 'polygons keep cells whose clearance >= this; per-chassis filtering uses polygon clearance_m (Rebuild robot radii 1.40-2.00 m)')
    P['vehicle_radius_m'] = (4.40, 'CONFIRMED: versus TnReachSpec CollisionRadius 440 cm (RE mp_navigation_audit). Vehicles move by RB hover '
                                   'physics, not walker rules (RE, HIGH): vehicle_capable is a clearance flag only, a separate vehicle layer')
    P['vehicle_height_m'] = (4.00, 'CONFIRMED: versus TnReachSpec CollisionHeight 400 cm')
    P['jump_up_max_m'] = ((max(jh) / 100) if jh else 5.0, 'CONFIRMED: jump apex = acrobatics JumpHeight (max over chassis, cm; RE: MaxJumpHeight = '
                                                          'JumpHeight, frame-rate independent); per-chassis values in chassis_jump')
    P['double_jump_note'] = ('DoubleJumpHeight per chassis in chassis_jump; links record rise so the runtime can choose', '')
    P['max_drop_m'] = (34.0, 'CONFIRMED (RE): robot MovementCapabilities.MaxFallHeight 3400 UU (AI / pathing limit)')
    P['merge_dh_m'] = (0.35, 'tool parameter: max height spread inside one polygon')
    P['cover_low_m'] = (1.0, 'PROVISIONAL cover hint thresholds (no cover system in WFC versus data)')
    P['cover_full_m'] = (2.5, 'PROVISIONAL')
    P['gravity_z_cm_s2'] = (wi.get('DefaultGravityZ'), 'CONFIRMED: Engine.Default__WorldInfo.DefaultGravityZ (= Xe-TransGame.ini)')
    P['pawn_JumpZ_note'] = (pawn.get('JumpZ'), 'TnPlayerPawn.JumpZ is NOT the jump used in MP (RE: JumpZ derived from JumpHeight, sqrt(2*2940*500) = 1714.6)')
    P['pawn_GroundSpeed'] = (pawn.get('GroundSpeed'), 'CONFIRMED: TnPlayerPawn.GroundSpeed')
    return P, jumps

def obstruction(path, layers):
    """per cell: sorted array of occupied heights (non-walkable triangle samples + walkable surfaces)"""
    occ = defaultdict(list); dropped = 0
    for j, n, mat, T, agree, det in MSA.node_tris(path):
        if not len(T): continue
        e1 = T[:, 1] - T[:, 0]; e2 = T[:, 2] - T[:, 0]
        nrm = np.cross(e1, e2); ln = np.linalg.norm(nrm, axis=1); area = ln / 2
        dropped += int((area > HUGE_M2).sum())
        ny = np.abs(nrm[:, 1]) / np.maximum(ln, 1e-12)
        for t, a, y in zip(T, area, ny):
            if a > HUGE_M2 or a < 1e-6 or y >= WALK_NY: continue
            k = max(2, int(math.ceil(math.sqrt(a) / 0.5)) + 1)
            u, v = np.meshgrid(np.linspace(0, 1, k), np.linspace(0, 1, k)); m = (u + v) <= 1
            u = u[m]; v = v[m]
            Pp = t[0] + np.outer(u, t[1] - t[0]) + np.outer(v, t[2] - t[0])
            for x, h, z in Pp:
                occ[(int(math.floor(x / CELL)), int(math.floor(z / CELL)))].append(h)
    for k, L in layers.c.items(): occ[k].extend(L)
    return {k: np.unique(np.round(np.array(v), 2)) for k, v in occ.items()}, dropped

def main():
    t0 = time.time()
    P, jumps = params(); p = {k: v[0] for k, v in P.items()}
    pawn_glb = os.path.join(OUT, 'collision_pawn.glb')
    col = SlopeLayers()
    for j, n, mat, T, agree, det in MSA.node_tris(pawn_glb):
        if len(T): col.add_tris(T, 'collision')
    occ, dropped = obstruction(pawn_glb, col)
    STEP, H = p['step_m'], p['agent_height_m']
    # open floor samples
    nodes = {}
    for k, L in col.c.items():
        oc = occ.get(k, np.array([]))
        for h in L:
            above = oc[(oc > h + STEP) & (oc <= h + H)]
            nodes[(k, h)] = {'open': len(above) == 0,
                             'headroom': float(oc[oc > h + STEP].min() - h) if (oc > h + STEP).any() else 99.0}
    def rise_ok(a, b):
        ny = min(col.ny.get(a, 1.0), col.ny.get(b, 1.0))
        return abs(a[1] - b[1]) <= STEP + CELL * math.sqrt(max(0.0, 1 - ny * ny)) / max(ny, 1e-6)
    def nbrs(k, h):
        x, z = k
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            kk = (x + dx, z + dz)
            for q in col.c.get(kk, ()):
                if rise_ok((k, h), (kk, q)): yield (kk, q)
    # clearance radius: BFS from blocked / edge cells
    dist = {}
    dq = deque()
    for key, nd in nodes.items():
        if not nd['open']: continue
        ok = [nb for nb in nbrs(*key) if nodes.get(nb, {}).get('open')]
        if len(ok) < 4: dist[key] = 0; dq.append(key)
    while dq:
        key = dq.popleft()
        for nb in nbrs(*key):
            if nodes.get(nb, {}).get('open') and nb not in dist:
                dist[nb] = dist[key] + 1; dq.append(nb)
    for key, nd in nodes.items():
        nd['clear'] = (dist.get(key, 0) + 0.5) * CELL if nd['open'] else 0.0
    # rectangles per layer (greedy)
    good = {key for key, nd in nodes.items() if nd['open'] and nd['clear'] >= p['min_radius_m']}
    used = set(); polys = []
    cell_poly = {}
    by_k = defaultdict(list)
    for (k, h) in good: by_k[k].append(h)
    def at(k, h0):
        for q in by_k.get(k, ()):
            if abs(q - h0) <= p['merge_dh_m'] and (k, q) not in used: return q
        return None
    for (k, h) in sorted(good, key=lambda x: (x[0][1], x[0][0], x[1])):
        if (k, h) in used: continue
        x0, z0 = k; w = 1
        while at((x0 + w, z0), h) is not None and w < 64: w += 1
        d = 1
        while d < 64 and all(at((x0 + i, z0 + d), h) is not None for i in range(w)): d += 1
        cells = []
        for dz in range(d):
            for i in range(w):
                kk = (x0 + i, z0 + dz); q = at(kk, h); used.add((kk, q)); cells.append((kk, q))
        pid = len(polys)
        for c in cells: cell_poly[c] = pid
        hs = np.array([c[1] for c in cells])
        polys.append({'id': pid, 'x0': x0, 'z0': z0, 'w': w, 'd': d, 'cells': cells, 'h': float(hs.mean()),
                      'hmin': float(hs.min()), 'hmax': float(hs.max()),
                      'clearance_m': float(min(nodes[c]['clear'] for c in cells)),
                      'headroom_m': float(min(nodes[c]['headroom'] for c in cells))})
    # polygon adjacency (portals along shared sides)
    adj = defaultdict(lambda: defaultdict(list))
    for (k, h), pid in cell_poly.items():
        for nb in nbrs(k, h):
            q = cell_poly.get(nb)
            if q is not None and q != pid: adj[pid][q].append(((k, h), nb))
    def corner_h(pl, x, z):
        best = min(pl['cells'], key=lambda c: abs(c[0][0] + 0.5 - x) + abs(c[0][1] + 0.5 - z)); return best[1]
    def g2ue(v): return [round(v[0] * 100, 1), round(v[2] * 100, 1), round(v[1] * 100, 1)]
    cells_out = []
    for pl in polys:
        x0, z0, w, d = pl['x0'], pl['z0'], pl['w'], pl['d']
        corners = [(x0, z0), (x0 + w, z0), (x0 + w, z0 + d), (x0, z0 + d)]
        V = [[cx * CELL, corner_h(pl, cx, cz), cz * CELL] for cx, cz in corners]
        edges = []
        normals = [(0, 0, -1), (1, 0, 0), (0, 0, 1), (-1, 0, 0)]
        for ei in range(4):
            a, b = V[ei], V[(ei + 1) % 4]
            # neighbours touching this side
            side = []
            for q, pairs in adj[pl['id']].items():
                for (c1, c2) in pairs:
                    (x1, z1), (x2, z2) = c1[0], c2[0]
                    s = {(1, 0): 1, (-1, 0): 3, (0, 1): 2, (0, -1): 0}[(x2 - x1, z2 - z1)]
                    if s == ei: side.append(q)
            nb = sorted(Counter(side).items(), key=lambda x: -x[1])
            edges.append({'start': V[ei], 'end': b, 'normal': normals[ei],
                          'neighbors': [{'cell': q, 'shared_cells': n} for q, n in nb], 'border': not nb})
        vehicle = pl['clearance_m'] >= p['vehicle_radius_m'] and pl['headroom_m'] >= p['vehicle_height_m']
        cells_out.append(OD([('id', pl['id']), ('vertices_gltf', [[round(c, 3) for c in v] for v in V]),
                             ('vertices_ue', [g2ue(v) for v in V]),
                             ('centroid_gltf', [round((x0 + w / 2) * CELL, 3), round(pl['h'], 3), round((z0 + d / 2) * CELL, 3)]),
                             ('area_m2', w * d * CELL * CELL), ('height_range_m', [round(pl['hmin'], 3), round(pl['hmax'], 3)]),
                             ('clearance_m', round(pl['clearance_m'], 2)), ('headroom_m', round(pl['headroom_m'], 2)),
                             ('flags', {'vehicle_capable': vehicle}), ('edges', edges)]))
    # off-mesh links: adjacent cells on different, non-connected layers
    links = []; seen = set()
    for (k, h), pid in cell_poly.items():
        x, z = k
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            kk = (x + dx, z + dz)
            for q in by_k.get(kk, ()):
                pq = cell_poly.get((kk, q))
                if pq is None or pq == pid or rise_ok((k, h), (kk, q)): continue
                rise = q - h
                kind = 'jump_up' if 0 < rise <= p['jump_up_max_m'] else 'drop_down' if -p['max_drop_m'] <= rise < 0 else None
                if not kind or (pid, pq, kind) in seen: continue
                # landing headroom / no obstruction in the jump column of the source
                if kind == 'jump_up' and nodes[(k, h)]['headroom'] < rise + H: continue
                seen.add((pid, pq, kind))
                links.append({'kind': kind, 'from_cell': pid, 'to_cell': pq, 'rise_m': round(rise, 2),
                              'from_gltf': [(x + 0.5) * CELL, round(h, 3), (z + 0.5) * CELL],
                              'to_gltf': [(kk[0] + 0.5) * CELL, round(q, 3), (kk[1] + 0.5) * CELL],
                              'forms': ['robot'] if kind == 'jump_up' else ['robot', 'vehicle']})
    # cover hints: open cells next to a tall obstruction
    cover = []
    for (k, h), pid in cell_poly.items():
        x, z = k
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            kk = (x + dx, z + dz); oc = occ.get(kk, np.array([]))
            if any(rise_ok((k, h), (kk, q)) for q in col.c.get(kk, ())): continue
            wall = oc[(oc > h + 0.2) & (oc <= h + 6.0)]
            if not len(wall): continue
            top = float(wall.max() - h)
            if top >= p['cover_low_m']:
                cover.append({'cell': pid, 'at_gltf': [(x + 0.5) * CELL, round(h, 3), (z + 0.5) * CELL],
                              'normal_gltf': [-dx, 0, -dz], 'height_m': round(top, 2),
                              'type': 'full' if top >= p['cover_full_m'] else 'half'})
    # anchors
    g = json.load(open(os.path.join(OUT, 'gameplay.json'), encoding='utf-8'))
    ents = [(e, 'player_start') for e in g.get('player_starts') or []] + [(e, 'pickup') for e in g.get('pickups') or []]
    for cls, L in (g.get('objectives') or {}).items():
        for e in L or []: ents.append((e, 'objective:' + cls))
    anchors = []
    for e, kind in ents:
        loc = e.get('location_gltf')
        if not loc: continue
        s = MSA.seed_for(col, loc, below=4.0, above=1.5)
        pid = None
        if s:
            pid = cell_poly.get(s)
            if pid is None:   # nearest polygon cell within 3 m on a similar height
                best = None
                for (kk, q), pp in cell_poly.items():
                    dd = abs(kk[0] - s[0][0]) + abs(kk[1] - s[0][1])
                    if dd <= 3 and abs(q - s[1]) <= 1.0 and (best is None or dd < best[0]): best = (dd, pp)
                pid = best[1] if best else None
        anchors.append({'actor': e.get('actor'), 'class': e.get('class'), 'kind': kind, 'location_gltf': loc, 'cell': pid})
    # playable set: cells reachable from any anchor through neighbours and links (both directions for drop / jump pairs are
    # listed separately, so reachability follows link direction). Unreachable geometry (rooftops, out-of-bounds) is dropped.
    raw_cells = len(cells_out)
    out_l = defaultdict(list)
    for l in links: out_l[l['from_cell']].append(l['to_cell'])
    reach = set(); dq = deque(a['cell'] for a in anchors if a['cell'] is not None)
    reach.update(dq)
    while dq:
        u = dq.popleft()
        nxt = [nb['cell'] for e in cells_out[u]['edges'] for nb in e['neighbors']] + out_l.get(u, [])
        for v in nxt:
            if v not in reach: reach.add(v); dq.append(v)
    # ... and that can get back to an anchor (drop-only pits / under-map shells are not playable)
    rev = defaultdict(list)
    for c in cells_out:
        for e in c['edges']:
            for nb in e['neighbors']: rev[nb['cell']].append(c['id'])
    for l in links: rev[l['to_cell']].append(l['from_cell'])
    back = set(a['cell'] for a in anchors if a['cell'] is not None); dq = deque(back)
    while dq:
        u = dq.popleft()
        for v in rev.get(u, []):
            if v not in back: back.add(v); dq.append(v)
    one_way = len(reach - back)
    reach &= back
    remap = {old: new for new, old in enumerate(sorted(reach))}
    kept = []
    for c in cells_out:
        if c['id'] not in remap: continue
        c['id'] = remap[c['id']]
        for e in c['edges']:
            e['neighbors'] = [dict(nb, cell=remap[nb['cell']]) for nb in e['neighbors'] if nb['cell'] in remap]
            e['border'] = not e['neighbors']
        kept.append(c)
    cells_out = kept
    links = [dict(l, from_cell=remap[l['from_cell']], to_cell=remap[l['to_cell']]) for l in links
             if l['from_cell'] in remap and l['to_cell'] in remap]
    cover = [dict(c, cell=remap[c['cell']]) for c in cover if c['cell'] in remap]
    for a in anchors: a['cell'] = remap.get(a['cell']) if a['cell'] is not None else None
    # waypoint / portal graph
    wp_nodes = [{'id': c['id'], 'kind': 'cell', 'pos_gltf': c['centroid_gltf']} for c in cells_out]
    wp_edges = []
    for c in cells_out:
        for e in c['edges']:
            for nb in e['neighbors']:
                if c['id'] < nb['cell']:
                    mid = [(a + b) / 2 for a, b in zip(e['start'], e['end'])]
                    wp_edges.append({'a': c['id'], 'b': nb['cell'], 'portal_mid_gltf': [round(v, 3) for v in mid],
                                     'width_m': nb['shared_cells'] * CELL})
    for l in links: wp_edges.append({'a': l['from_cell'], 'b': l['to_cell'], 'link': l['kind'], 'directed': True})
    # connectivity summary
    comp = {}; ci = 0
    for c in cells_out:
        if c['id'] in comp: continue
        dq = deque([c['id']]); comp[c['id']] = ci
        while dq:
            u = dq.popleft()
            for e in cells_out[u]['edges']:
                for nb in e['neighbors']:
                    if nb['cell'] not in comp: comp[nb['cell']] = ci; dq.append(nb['cell'])
        ci += 1
    sizes = Counter(comp.values())
    main_comp = sizes.most_common(1)[0][0] if sizes else None
    anch_main = sum(1 for a in anchors if a['cell'] is not None and comp.get(a['cell']) == main_comp)
    out = OD([
        ('map', MAP), ('generated_by', 'AssetTools/scripts/wfc/bot_nav.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
        ('status', 'PC ADAPTATION (WFC versus maps ship no bot nav; reconstructed from collision_pawn.glb)'),
        ('units', 'gltf: metres, Y-up (Rebuild runtime space); ue: centimetres, Z-up'),
        ('ue_to_gltf', {'rule': 'v_gltf = 0.01 * (x, z, y)_UE', 'matrix_row_major': [[0.01, 0, 0, 0], [0, 0, 0.01, 0], [0, 0.01, 0, 0], [0, 0, 0, 1]]}),
        ('schema_reference', 'Escalation NavigationCell (_Edges{Start, End, Normal, Neighbor, Border}); RE MP note addendum 1'),
        ('parameters', OD((k, {'value': v[0], 'source': v[1]}) for k, v in P.items())), ('chassis_jump', jumps),
        ('stats', OD([('floor_samples', len(nodes)), ('cells_before_playable_prune', raw_cells), ('one_way_cells_dropped', one_way), ('open_samples', sum(1 for n in nodes.values() if n['open'])),
                      ('cells', len(cells_out)), ('walkable_area_m2', sum(c['area_m2'] for c in cells_out)),
                      ('vehicle_capable_cells', sum(1 for c in cells_out if c['flags']['vehicle_capable'])),
                      ('links', dict(Counter(l['kind'] for l in links))), ('cover_hints', dict(Counter(c['type'] for c in cover))),
                      ('components', len(sizes)), ('largest_component_cells', sizes[main_comp] if sizes else 0),
                      ('anchors', len(anchors)), ('anchors_on_nav', sum(1 for a in anchors if a['cell'] is not None)),
                      ('anchors_in_largest_component', anch_main), ('oversized_triangles_excluded', dropped),
                      ('seconds', round(time.time() - t0, 1))])),
        ('cells', cells_out), ('links', links), ('cover', cover), ('anchors', anchors),
        ('waypoints', {'nodes': wp_nodes, 'edges': wp_edges})])
    json.dump(out, open(os.path.join(OUT, 'bot_nav.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    # debug mesh: one primitive, polygons as quads (two triangles), coloured by vehicle flag via two primitives
    glb = GLB('AssetTools bot_nav debug')
    for flag in (False, True):
        V, I = [], []
        for c in cells_out:
            if c['flags']['vehicle_capable'] != flag: continue
            b = len(V); V += [[v[0], v[1] + 0.05, v[2]] for v in c['vertices_gltf']]; I += [b, b + 2, b + 1, b, b + 3, b + 2]
        if not V: continue
        mat = glb.j.setdefault('materials', []); mat.append({'name': 'vehicle' if flag else 'robot',
              'pbrMetallicRoughness': {'baseColorFactor': [0.2, 0.4, 1, 0.6] if flag else [0.2, 1, 0.3, 0.6]}, 'alphaMode': 'BLEND', 'doubleSided': True})
        mi = glb.mesh('nav_' + ('vehicle' if flag else 'robot'), [{'attributes': {'POSITION': glb.acc(np.array(V, 'f4'), 'VEC3', True, 34962)},
                       'indices': glb.acc(np.array(I, 'u4'), 'SCALAR', target=34963), 'material': len(mat) - 1}])
        glb.node({'name': 'bot_nav_' + ('vehicle' if flag else 'robot'), 'mesh': mi})
    glb.write(os.path.join(OUT, 'bot_nav.glb'))
    print(json.dumps(out['stats']))

if __name__ == '__main__':
    main()
