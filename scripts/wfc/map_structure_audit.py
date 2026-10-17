"""Structural / visual completeness audit for any exported map (generic map pipeline; not a file-count check).

  python map_structure_audit.py <MAP>      -> manifests/maps/<MAP>/structure_audit.json

Works only on the exported layers (world.glb, collision_pawn.glb, props.json, lightmaps.json, gameplay.json), so it audits
what a consumer will load, with the Streets lessons built in:
* collection-actor transforms: every StaticMeshCollectionActor component node in world.glb must equal props.json gltf_matrix
  (the Streets bug was the native CachedParentToWorld being ignored);
* mirrored instances (det < 0): glTF requires the renderer to flip winding; we check the exported geometry is consistent with
  that rule (geometric normal of transformed triangles vs transformed vertex normals);
* walkable space: upward-facing collision triangles are rasterised into a layered 1 m height grid, then flood-filled from the
  player starts with a conservative walk rule (step <= STEP_M between neighbour cells). Pickups / objectives / spawns must sit on
  reachable floor; render floor and collision floor are compared cell by cell (invisible floors / fall-through floors);
* oversized triangles (sky dome, light planes, > HUGE_M2) are kept out of the grids (Streets memory incident); run under
  run_bounded.py.
"""
import json, math, os, sys
from collections import Counter, defaultdict, deque
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import VS, read_glb, accessor, is_campaign  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
# WFC_AUDIT_CELL: layer-grid cell size (default 1 m, unchanged for MP). Campaign chapters use a coarser cell to stay under the job cap
# (A1 / A3 / D2 / D3B reached 10 GB at 1 m); the cell size is recorded in the output's method.cell_m
CELL = float(os.environ.get('WFC_AUDIT_CELL') or 1.0)          # m
STEP_M = 1.25       # walk rule: max height change between neighbour cells (conservative; robots also jump / transform)
WALK_NY = 0.7       # walkable if normal.y >= 0.7 (~45 deg)
HUGE_M2 = 20000.0   # triangles larger than this never enter the grids
MAX_LAYERS = 48     # per-cell layer cap (memory guard; Gorge gate shafts stack > 12 floors in one cell)

def node_tris(path, want_normals=False):
    """yield (node, prim material, world tris (n,3,3), normal agreement for mirrored check)"""
    j, bins = read_glb(path)
    for n in j['nodes']:
        if 'mesh' not in n: continue
        M = np.array(n['matrix']).reshape(4, 4).T if 'matrix' in n else np.eye(4)
        for p in j['meshes'][n['mesh']]['primitives']:
            P = accessor(j, bins, p['attributes']['POSITION']).astype('f8')
            I = accessor(j, bins, p['indices']).astype('i8') if 'indices' in p else np.arange(len(P))
            I = I.reshape(-1, 3)
            W = (np.c_[P, np.ones(len(P))] @ M.T)[:, :3]
            agree = None
            if want_normals and 'NORMAL' in p['attributes'] and len(I):
                N = accessor(j, bins, p['attributes']['NORMAL']).astype('f8')
                NW = N @ np.linalg.inv(M[:3, :3])   # = (M^-T n)^T
                T = W[I]
                g = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
                d = (g * NW[I].mean(1)).sum(1)
                agree = (int((d > 0).sum()), int((d < 0).sum()))
            yield j, n, p.get('material'), W[I], agree, float(np.linalg.det(M[:3, :3]))

class Layers:
    """layered height grid: cell -> sorted list of (height, source tag)"""
    def __init__(self): self.c = defaultdict(list); self.t = {}; self.dropped = 0
    def add_tris(self, T, tag):
        e1 = T[:, 1] - T[:, 0]; e2 = T[:, 2] - T[:, 0]
        nrm = np.cross(e1, e2); ln = np.linalg.norm(nrm, axis=1); area = ln / 2
        ny = np.abs(nrm[:, 1]) / np.maximum(ln, 1e-12)
        keep = (ny >= WALK_NY) & (area <= HUGE_M2) & (area > 1e-6)
        self.dropped += int(((area > HUGE_M2)).sum())
        for t in T[keep]:
            x0, z0 = math.floor(t[:, 0].min() / CELL), math.floor(t[:, 2].min() / CELL)
            x1, z1 = math.floor(t[:, 0].max() / CELL), math.floor(t[:, 2].max() / CELL)
            xs = (np.arange(x0, x1 + 1) + 0.5) * CELL; zs = (np.arange(z0, z1 + 1) + 0.5) * CELL
            X, Z = np.meshgrid(xs, zs); X = X.ravel(); Z = Z.ravel()
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
            d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
            if abs(d) < 1e-12: continue
            w0 = ((bz - cz) * (X - cx) + (cx - bx) * (Z - cz)) / d
            w1 = ((cz - az) * (X - cx) + (ax - cx) * (Z - cz)) / d
            w2 = 1 - w0 - w1
            ins = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            if not ins.any():   # thin triangle smaller than a cell: sample its centroid
                X = np.array([t[:, 0].mean()]); Z = np.array([t[:, 2].mean()]); w0 = w1 = w2 = np.array([1 / 3]); ins = np.array([True])
            H = w0 * ay + w1 * by + w2 * cy
            for x, z, h in zip(X[ins], Z[ins], H[ins]):
                k = (int(math.floor(x / CELL)), int(math.floor(z / CELL)))
                L = self.c[k]
                if any(abs(h - q) < 0.3 for q in L): continue
                if len(L) < MAX_LAYERS: L.append(float(h)); self.t[(k, float(h))] = tag
    def near(self, k, h, tol):
        return [q for q in self.c.get(k, ()) if abs(q - h) <= tol]

def flood(col, seeds):
    seen = set(); dq = deque()
    for k, h in seeds:
        if (k, h) not in seen: seen.add((k, h)); dq.append((k, h))
    while dq:
        (x, z), h = dq.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = (x + dx, z + dz)
            for q in col.c.get(k, ()):
                if abs(q - h) <= STEP_M and (k, q) not in seen:
                    seen.add((k, q)); dq.append((k, q))
    return seen

def seed_for(col, pos, below=3.0, above=1.0):
    k = (int(math.floor(pos[0] / CELL)), int(math.floor(pos[2] / CELL)))
    best = None
    for kk in [k] + [(k[0] + a, k[1] + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b]:
        for q in col.c.get(kk, ()):
            if pos[1] - below <= q <= pos[1] + above and (best is None or q > best[1]): best = (kk, q)
    return best

def main():
    MAP = sys.argv[1]
    D = os.path.join(VS, 'Maps', MAP)
    J = lambda f: json.load(open(os.path.join(D, f), encoding='utf-8'))
    props = J('props.json')['props']; gp = J('gameplay.json'); lm = J('lightmaps.json') if os.path.exists(os.path.join(D, 'lightmaps.json')) else {}
    out = {'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/map_structure_audit.py',
           'method': {'cell_m': CELL, 'walk_step_m': STEP_M, 'walkable_normal_y': WALK_NY, 'huge_triangle_m2': HUGE_M2,
                      'note': 'walk graph is conservative (no jumping / vehicle form / jump pads): unreachable != unplayable'}}

    # ---- world.glb pass: transforms, mirrored winding, materials, lightmaps, render floor
    vis = Layers(); nodes = Counter(); mirrored = Counter(); default_mat = Counter(); default_area = defaultdict(float)
    smca_mismatch = []; lm_nodes = 0; lm_nodes_uv2 = 0; byname = {}
    pm = {}
    for p in props:
        if p['class'] == 'StaticMeshCollectionActor': pm[p['component']] = p   # full path: streamed levels reuse short names
    mat_names = None
    seen_nodes = set()
    for j, n, mi, T, agree, det in node_tris(os.path.join(D, 'world.glb'), want_normals=True):
        if mat_names is None: mat_names = [m.get('extras', {}).get('wfc_material', m.get('name')) for m in j.get('materials', [])]
        ex = n.get('extras', {}); nid = id(n)
        kind = 'bsp' if ex.get('kind') == 'bsp' else (ex.get('class') or 'other')
        if nid not in seen_nodes:
            seen_nodes.add(nid); nodes[kind] += 1; byname.setdefault(n['name'], n)
            if ex.get('lm_atlas'):
                lm_nodes += 1
                if all('TEXCOORD_1' in pr['attributes'] for pr in j['meshes'][n['mesh']]['primitives']): lm_nodes_uv2 += 1
            if ex.get('class') == 'StaticMeshCollectionActor':
                src = pm.get(ex.get('component') or '')
                if src is None or not np.allclose(np.array(n['matrix']), np.array(src['gltf_matrix']), atol=1e-4):
                    smca_mismatch.append(n['name'])
        if agree is not None:
            mirrored['mirrored' if det < 0 else 'normal'] += 1
            key = 'det<0' if det < 0 else 'det>0'
            mirrored[key + ' tris normal-agree'] += agree[0]; mirrored[key + ' tris normal-oppose'] += agree[1]
        mname = mat_names[mi] if mi is not None and mat_names else None
        if mi is None or (mname or '').endswith('DefaultMaterial'):
            e1 = T[:, 1] - T[:, 0]; e2 = T[:, 2] - T[:, 0]
            default_mat[kind] += len(T); default_area[kind] += float(np.linalg.norm(np.cross(e1, e2), axis=1).sum() / 2)
        vis.add_tris(T, 'BSP' if kind == 'bsp' else (ex.get('mesh') or kind))

    # ---- collision pass
    col = Layers(); col_nodes = Counter(); col_by_actor = Counter(); col_pairs = []
    for j, n, mi, T, agree, det in node_tris(os.path.join(D, 'collision_pawn.glb')):
        col_nodes[(n.get('extras') or {}).get('kind', n['name'].rsplit('_', 1)[0])] += 0
        col_by_actor[n['name']] += 1; col_pairs.append((n['name'], (n.get('extras') or {}).get('mesh')))
        col.add_tris(T, n['name'].rsplit('_', 1)[0] if not n['name'].startswith('BSP') else 'BSP')
    skel_col = None
    if is_campaign(MAP):
        # campaign only (Integration 2026-10-17, decision A; MP outputs unchanged): skeletal world actors block through their
        # PhysicsAsset bodies, which collision_pawn.glb does not carry -> add them to the walk-graph collision at the reference pose
        import skel_collision as K
        import authored as AU
        skel_col = {'actors': 0, 'with_collision': 0, 'boxes': 0, 'skipped': Counter(), 'undecoded': Counter(), 'bones_missing': []}
        for lv in json.load(open(os.path.join(D, 'map.json'), encoding='utf-8'))['sublevels']:
            for r in AU.find(lv + '.TheWorld.PersistentLevel.%', 'TnTransformingWorldActor'):
                if r['opath'].count('.') != 3: continue
                T, info = K.actor_tris(r['opath']); skel_col['actors'] += 1
                if info.get('skipped'): skel_col['skipped'][info['skipped']] += 1
                skel_col['undecoded'].update(info['undecoded'])
                if info.get('bones_missing'): skel_col['bones_missing'].append({'actor': info['actor'], 'bones': info['bones_missing']})
                if len(T):
                    skel_col['with_collision'] += 1; skel_col['boxes'] += info['boxes']
                    col.add_tris(T, 'TnTransformingWorldActor')
        skel_col['skipped'] = dict(skel_col['skipped']); skel_col['undecoded'] = dict(skel_col['undecoded'])
    # props that block but have no collision node, and vice versa
    blocking = Counter(p['actor'] for p in props if p.get('block'))
    nonblocking = Counter(p['actor'] for p in props if not p.get('block'))
    missing_col = {a: c - col_by_actor.get(a, 0) for a, c in blocking.items() if col_by_actor.get(a, 0) < c}
    # explain each gap from physics.json (vs_physics per-component pawn channel: simple / per_poly / none, oversize skip)
    phys = {q['component']: q for q in (J('physics.json').get('props') or []) if q.get('component')}
    phys_stats = ((J('physics.json').get('stats') or {}).get('glb') or {}).get('pawn') or {}
    phys_meshes = J('physics.json').get('meshes') or {}
    phys_actor = {}
    for q in (J('physics.json').get('props') or []): phys_actor.setdefault((q['actor'], q.get('mesh')), q)
    col_mesh = Counter((n_, m_) for n_, m_ in col_pairs)
    blk_mesh = Counter((p['actor'], p['mesh']) for p in props if p.get('block'))
    explained = []
    for (act, mesh), c in blk_mesh.items():
        have = col_mesh.get((act, mesh), 0)
        if have >= c: continue
        comps = [p for p in props if p['actor'] == act and p['mesh'] == mesh and p.get('block')]
        chan = [(p, phys.get(p.get('component') or '') or phys_actor.get((act, mesh), {})) for p in comps]
        expected = sum(1 for _, q in chan if q.get('pawn') in ('simple', 'per_poly'))
        surplus = max(0, expected - have)   # components that should have a collision node but do not
        for p, q in chan:
            ch = q.get('pawn')
            if ch in ('simple', 'per_poly'):
                if surplus == 0: continue         # this group's collision-bearing components are all present
                surplus -= 1
                ovs, mg = phys_stats.get('props_oversize_skipped') or 0, phys_stats.get('props_missing_geometry') or 0
                secs = (phys_meshes.get(mesh) or {}).get('sections') or []
                if mesh is None:
                    reason = 'component has no StaticMesh (none authored, even through its archetype) -> no geometry to collide with'
                elif ch == 'per_poly' and secs and not any(x.get('enable_collision') for x in secs):
                    reason = 'per-poly but every section has EnableCollision=false (authored) -> no collision geometry, as in UE3'
                else: reason = (('%s collision expected but vs_physics wrote no node: physics.json pawn stats oversize_skipped=%d '
                           '(>2 km shells), missing_geometry=%d (render mesh / hull not available)') % (ch, ovs, mg)) if (ovs or mg) else 'UNEXPLAINED'
            else:
                reason = 'mesh has no simple collision and no per-poly flag -> no pawn collision in UE3 either'
            explained.append({'actor': act, 'component': (p.get('component') or '').rsplit('.', 1)[-1], 'mesh': mesh, 'pawn_channel': ch,
                              'gltf_translation_m': [round(x, 1) for x in p['gltf_matrix'][12:15]], 'reason': reason})
    col_only = {a: c for a, c in col_by_actor.items() if a not in blocking and not a.startswith(('BlockingVolume', 'TnTransformerBlockingVolume', 'BSPCollision'))}

    # ---- walkable reachability from player starts
    starts = gp.get('player_starts', [])
    seeds = []; unseeded = []
    for s in starts:
        sd = seed_for(col, s['location_gltf'])
        (seeds.append(sd) if sd else unseeded.append(s['actor']))
    reach = flood(col, seeds)
    reach_cells = {k for k, _ in reach}
    def on_reachable(pos, below=4.0, above=1.5):
        sd = seed_for(col, pos, below, above)
        return bool(sd and sd in reach)
    placed = {}
    for grp in ('pickups', 'objectives'):
        xs = gp.get(grp) or []
        if isinstance(xs, dict): xs = [y for v in xs.values() for y in (v if isinstance(v, list) else [])]
        xs = [x for x in xs if isinstance(x, dict) and x.get('location_gltf')]
        bad = [x['actor'] for x in xs if not on_reachable(x['location_gltf'])]
        placed[grp] = {'count': len(xs), 'on_walkable_reachable_floor': len(xs) - len(bad), 'not_on_walk_graph': bad}
    starts_ok = [s for s in starts if seed_for(col, s['location_gltf']) in reach]
    # floor agreement on the reachable layer
    invisible = Counter(); agree_n = 0
    for (k, h) in reach:
        if vis.near(k, h, 0.35): agree_n += 1
        else: invisible[col.t.get((k, h), '?')] += 1
    xs_r = [k[0] for k in reach_cells] or [0]; zs_r = [k[1] for k in reach_cells] or [0]
    # visible floors next to reachable floor with no collision (fall-through risk): neighbour of a reachable cell at a similar height
    ft_cells = []
    for (k, h) in reach:
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            kk = (k[0] + dx, k[1] + dz)
            for q in vis.c.get(kk, ()):
                if abs(q - h) <= STEP_M and not col.near(kk, q, 0.35):
                    ft_cells.append((kk, round(q, 2)))
    ft_cells = sorted(set(ft_cells))
    ft_by_src = Counter(vis.t.get((kk, q)) or vis.t.get((kk, next((x for x in vis.c[kk] if round(x, 2) == q), q)), '?') for kk, q in ft_cells)
    nonblocking_meshes = Counter(p['mesh'] for p in props if not p.get('block'))
    # starts with no floor in reach: report the nearest collision / visible floor heights below them
    start_diag = []
    for s_ in starts:
        if seed_for(col, s_['location_gltf']) in reach: continue
        k = (int(math.floor(s_['location_gltf'][0] / CELL)), int(math.floor(s_['location_gltf'][2] / CELL)))
        start_diag.append({'actor': s_['actor'], 'location_gltf': s_['location_gltf'],
                           'collision_layers_here': sorted(round(q, 2) for q in col.c.get(k, ())),
                           'visible_layers_here': sorted(round(q, 2) for q in vis.c.get(k, ())),
                           'collision_sources': sorted({col.t.get((k, q)) for q in col.c.get(k, ())} - {None})})
    bbox = None
    if reach:
        hs = [h for _, h in reach]
        bbox = {'x_m': [min(xs_r) * CELL, (max(xs_r) + 1) * CELL], 'z_m': [min(zs_r) * CELL, (max(zs_r) + 1) * CELL],
                'floor_height_m': [round(min(hs), 2), round(max(hs), 2)]}
    kz = [v.get('KillZ') for v in (J('physics.json').get('world') or {}).values() if isinstance(v, dict) and v.get('KillZ') is not None]

    # ---- movers / hidden / mode-gated actors present in world.glb
    movers = [p for p in props if p['class'] != 'StaticMeshCollectionActor']
    movers_missing = [p['actor'] for p in movers if p['actor'] not in byname]
    mdv = gp.get('mode_dependent_visibility') or []
    gated = [t['actor'] for r in mdv for t in r.get('targets', [])]
    gated_missing = [a for a in gated if a not in byname]

    # ---- lightmaps
    lmp = lm.get('props', [])
    out['transforms'] = {'smca_nodes_checked': sum(1 for p in props if p['class'] == 'StaticMeshCollectionActor'),
                         'smca_world_glb_matrix_mismatch': len(smca_mismatch), 'examples': smca_mismatch[:10],
                         'rule': 'world.glb node matrix == props.json gltf_matrix (component S*R*T x native CachedParentToWorld; Streets lesson)'}
    out['mirrored_instances'] = {'primitive_instances': dict(mirrored),
                                 'verdict': 'CONSISTENT' if mirrored['det<0 tris normal-oppose'] >= mirrored['det<0 tris normal-agree'] and
                                 mirrored['det>0 tris normal-agree'] >= mirrored['det>0 tris normal-oppose'] else 'CHECK',
                                 'rule': 'for det<0 nodes the transformed winding opposes the transformed normals; a glTF renderer must flip the '
                                         'front face (glTF 2.0 spec 3.7.4). Exported data is consistent when det<0 tris mostly oppose and det>0 '
                                         'tris mostly agree.'}
    if skel_col is not None: out['skeletal_world_actor_collision'] = skel_col   # campaign only (MP output keys unchanged)
    out['playable_space'] = {'player_starts': len(starts), 'starts_on_reachable_floor': len(starts_ok), 'starts_without_floor_below': unseeded, 'starts_off_walk_graph_diagnosis': start_diag,
                             'walk_graph_cells': len(reach_cells), 'walk_graph_layers': len(reach), 'walk_graph_area_m2': round(len(reach) * CELL * CELL, 1),
                             'connected_from_any_start': True, 'bounds': bbox, 'kill_z_ue': kz,
                             'placement_checks': placed}
    out['collision_vs_visible'] = {
        'reachable_floor_cells_with_visible_floor': agree_n,
        'reachable_floor_cells_without_visible_floor (invisible floor) by collision source': dict(invisible.most_common()),
        'agreement_pct': round(100.0 * agree_n / max(1, agree_n + sum(invisible.values())), 2),
        'agreement_pct_excluding_volume_tops': round(100.0 * agree_n / max(1, agree_n + sum(v for k, v in invisible.items()
                                                       if not k.endswith('BlockingVolume'))), 2),
        'visible_floor_cells_next_to_walk_graph_without_collision (fall-through candidates)': len(ft_cells),
        'fall_through_candidates_by_visible_source (top 25)': dict(ft_by_src.most_common(25)),
        'non_blocking_props_by_mesh (authored bCollideActors/bBlockActors false)': dict(nonblocking_meshes.most_common()),
        'fall_through_examples_gltf': [[(c[0] + 0.5) * CELL, q, (c[1] + 0.5) * CELL] for c, q in ft_cells[:20]],
        'blocking_props_without_collision_node': missing_col, 'blocking_gaps_explained': explained, 'collision_nodes_without_blocking_prop': col_only,
        'collision_node_kinds': dict(Counter(n.rsplit('_', 1)[0] for n in col_by_actor)),
        'oversized_triangles_excluded': {'world': vis.dropped, 'collision': col.dropped}}
    out['materials'] = {'default_material_triangles_by_kind': dict(default_mat), 'default_material_area_m2_by_kind': {k: round(v, 1) for k, v in default_area.items()},
                        'note': 'BSP faces with DefaultMaterial and their in-play visibility: manifests/next_map/<MAP>_bsp_default_faces.json (Streets: '
                                'streets_bsp_default_faces.json)'}
    out['lightmaps'] = {'lightmaps_json_props': len(lmp), 'world_glb_nodes_with_lm_atlas': lm_nodes, 'of_which_have_TEXCOORD_1': lm_nodes_uv2,
                        'atlases_used': len(lm.get('atlases_used') or []), 'atlases_without_png': lm.get('atlases_without_png'),
                        'binding_ok': lm_nodes == lm_nodes_uv2}
    out['actors'] = {'world_glb_nodes_by_kind': dict(nodes), 'non_collection_actors': len(movers), 'non_collection_actors_missing_from_world_glb': movers_missing,
                     'mode_gated_targets': len(gated), 'mode_gated_missing_from_world_glb': gated_missing}
    fails = []
    if smca_mismatch: fails.append('SMCA transform mismatch')
    if out['mirrored_instances']['verdict'] != 'CONSISTENT': fails.append('mirrored winding')
    if len(starts_ok) != len(starts): fails.append('player starts off walk graph')
    if movers_missing or gated_missing: fails.append('actors missing from world.glb')
    if not out['lightmaps']['binding_ok']: fails.append('lightmap uv binding')
    if any(e['reason'] == 'UNEXPLAINED' for e in explained): fails.append('unexplained collision gap')
    out['verdict'] = {'status': 'PASS' if not fails else 'ATTENTION', 'failures': fails}
    od = os.path.join(AT, 'manifests', 'maps', MAP); os.makedirs(od, exist_ok=True)
    json.dump(out, open(os.path.join(od, 'structure_audit.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps({k: out[k] for k in ('transforms', 'mirrored_instances', 'playable_space', 'lightmaps', 'verdict')}, default=str)[:3000])
    print(json.dumps({k: v for k, v in out['collision_vs_visible'].items() if 'examples' not in k}, default=str)[:2000])

if __name__ == '__main__':
    main()
