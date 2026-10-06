"""Authored navigation (UE3 path network) of a map, from manifests/authored.db (authored.py).

Streets (and other MP maps without bots) carries no PathNodes / cover / NavigationCells / TnTactical data:
its navigation graph is the editor-built path network between the NavigationPoints that gameplay already
needs (player starts, pickup + objective factories).  Edges are ReachSpecs owned by their Start node
(NavigationPoint.PathList[] -> TnReachSpec {Start, End{Nav,Guid}, Distance, CollisionRadius/Height,
MaxCollisionRadius, reachFlags}).

Output: ExtractedAssets/VerticalSlice/Maps/<MAP>/navigation.json  (+ navigation.glb: POINTS = nodes, LINES = edges, glTF metres)
  nodes      every NavigationPoint actor in the map's packages with class, transform, MaxPathSize, out-degree
  edges      every ReachSpec: start, end, distance, flags (decoded), collision size
  analysis   flag/size histograms, distance check vs Euclidean, symmetry, connected components,
             reachability between starts / pickups / objectives, nav-point classes without edges
  python vs_navigation.py [MAP]
"""
import json, os, re, sys
from collections import Counter, defaultdict, deque
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, typed_props as tp  # noqa: E402
from vs_common import VS, GLB, ue_points_to_gltf  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
REACH = [(1, 'R_WALK'), (2, 'R_FLY'), (4, 'R_SWIM'), (8, 'R_JUMP'), (16, 'R_DOOR'), (32, 'R_SPECIAL'), (64, 'R_LADDER'),
         (128, 'R_PROSCRIBED'), (256, 'R_FORCED'), (512, 'R_PLAYERONLY')]       # UE3 ReachSpec.reachFlags (stock enum)

def flags(v): return [n for b, n in REACH if v & b] + (['0x%x' % (v & ~0x3ff)] if v & ~0x3ff else [])

def is_navpoint(cls_path):
    t, seen = tp.resolve_type(cls_path), 0
    while t and seen < 30:
        if t.endswith('.NavigationPoint'): return True
        t = tp.resolve_type((tp.schema()['types'].get(t) or {}).get('super')); seen += 1
    return False

def loc(v): return np.array([float((v.get('Location') or {}).get(a, 0.0)) for a in 'XYZ'])

from vs_common import map_sublevels  # noqa: E402

def main():
    subs = map_sublevels(MAP, A)   # name prefix + streamed sublevels (map.json)
    nodes, edges = {}, []
    guid_of, pending_guid = {}, []
    for sub in subs:
        lvl = sub + '.TheWorld.PersistentLevel'
        for r in A.children(lvl):
            if not is_navpoint(r['class_path']): continue
            v = A.values(r['opath'])
            L = loc(v)
            if v.get('NavGuid'): guid_of[tuple(v['NavGuid'][k] for k in 'ABCD')] = r['opath']
            nodes[r['opath']] = {'node': r['opath'].rsplit('.', 1)[-1], 'class': r['class'], 'sublevel': sub,
                                 'location_ue': L.round(3).tolist(), 'location_gltf': ue_points_to_gltf([L])[0].round(4).tolist(),
                                 'max_path_size': v.get('MaxPathSize'), 'path_list': len(v.get('PathList') or []),
                                 'flags': {k: v[k] for k in ('bBlocked', 'bOneWayPath', 'bNeverUseStrafing', 'bAlwaysUseStrafing', 'bForceNoStrafing',
                                                             'bAutoBuilt', 'bSpecialMove', 'bNoAutoConnect', 'bNotBased', 'bPathsChanged',
                                                             'bDestinationOnly', 'bSourceOnly', 'bSpecialForced', 'bMustBeReachable',
                                                             'bCanWalkOnToReach', 'bBuildLongPaths', 'bBlockedForVehicles', 'bPreferredVehiclePath',
                                                             'bMakeSourceOnly', 'bMayCausePain', 'bVehicleDestination', 'bHasCrossLevelPaths')
                                           if k in v and v[k]},
                                 'extra_cost': v.get('ExtraCost'), 'fear_cost': v.get('FearCost')}
            for rs in v.get('PathList') or []:
                if not rs: continue
                o = A.get(rs); sv = A.values(rs)
                end_ref = sv.get('End') or {}
                end = end_ref.get('Nav') if isinstance(end_ref, dict) else end_ref
                if not end and isinstance(end_ref, dict) and end_ref.get('Guid'):
                    pending_guid.append((len(edges), end_ref['Guid']))   # cross-level FActorReference: Guid only
                edges.append({'spec': rs.rsplit('.', 1)[-1], 'class': o['class'] if o else None, 'start': r['opath'], 'end': end,
                              'distance': sv.get('Distance'), 'reach_flags': sv.get('reachFlags', 0), 'flags': flags(int(sv.get('reachFlags', 0))),
                              'collision_radius': sv.get('CollisionRadius'), 'collision_height': sv.get('CollisionHeight'),
                              'max_collision_radius': sv.get('MaxCollisionRadius'), 'forced_path_size': sv.get('ForcedPathSizeName'),
                              'other': {k: x for k, x in (o['props'] or {}).items()
                                        if k not in ('Start', 'End', 'Distance', 'reachFlags', 'CollisionRadius', 'CollisionHeight', 'MaxCollisionRadius')}})
    # cross-level reach specs store End as {Guid} only (UE3 FActorReference across levels): resolve through NavigationPoint.NavGuid
    for i, g in pending_guid:
        tgt = guid_of.get(tuple(g.get(k) for k in 'ABCD'))
        if tgt: edges[i]['end'] = tgt; edges[i]['end_resolved_by'] = 'NavGuid (cross-level reference)'
    # ------------------------------------------------------------------ analysis
    adj = defaultdict(set); und = defaultdict(set)
    bad_end, dist_err = [], []
    for e in edges:
        if e['end'] not in nodes: bad_end.append(e['spec']); continue
        adj[e['start']].add(e['end']); und[e['start']].add(e['end']); und[e['end']].add(e['start'])
        eu = float(np.linalg.norm(np.array(nodes[e['end']]['location_ue']) - np.array(nodes[e['start']]['location_ue'])))
        e['euclidean'] = round(eu, 2)
        if e['distance'] is not None: dist_err.append(abs(e['distance'] - eu))
    pairs = {(e['start'], e['end']) for e in edges if e['end'] in nodes}
    sym = sum(1 for a, b in pairs if (b, a) in pairs)
    # components (undirected)
    seen, comps = set(), []
    for n in nodes:
        if n in seen: continue
        q, comp = deque([n]), []
        seen.add(n)
        while q:
            x = q.popleft(); comp.append(x)
            for y in sorted(und[x]):   # sorted: deterministic component member order (set iteration follows PYTHONHASHSEED)
                if y not in seen: seen.add(y); q.append(y)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    for i, c in enumerate(comps):
        for n in c: nodes[n]['component'] = i
    def reach_from(src):
        s, q = {src}, deque([src])
        while q:
            x = q.popleft()
            for y in adj[x]:
                if y not in s: s.add(y); q.append(y)
        return s
    big = set(comps[0]) if comps else set()
    starts = [n for n in nodes if 'PlayerStart' in nodes[n]['class']]
    goals = [n for n in nodes if re.search('Pickup|Objective|Flag|Bomb', nodes[n]['class'])]
    reach_ok = 0
    for s in starts:
        R = reach_from(s)
        reach_ok += all(g in R for g in goals)
    for n, d in nodes.items(): d['out_degree'] = len(adj[n]); d['in_degree'] = sum(1 for e in edges if e['end'] == n)
    analysis = {'nodes': len(nodes), 'edges': len(edges), 'node_classes': dict(Counter(d['class'] for d in nodes.values())),
                'navpoint_classes_without_edges': dict(Counter(d['class'] for d in nodes.values() if d['out_degree'] == 0 and d['in_degree'] == 0)),
                'edge_classes': dict(Counter(e['class'] for e in edges)), 'reach_flags': dict(Counter('|'.join(e['flags']) for e in edges)),
                'collision_sizes': dict(Counter('r%s h%s' % (e['collision_radius'], e['collision_height']) for e in edges)),
                'max_path_sizes': dict(Counter(json.dumps(d['max_path_size'], sort_keys=True) for d in nodes.values())),
                'edge_distance_ue': {'min': min(e['distance'] for e in edges), 'median': float(np.median([e['distance'] for e in edges])),
                                     'max': max(e['distance'] for e in edges)} if edges else None,
                'distance_vs_euclidean_abs_err': {'max': round(max(dist_err), 3), 'median': round(float(np.median(dist_err)), 3)} if dist_err else None,
                'edges_with_unresolved_end': len(bad_end), 'directed_pairs': len(pairs), 'bidirectional_pairs': sym,
                'components': [len(c) for c in comps], 'largest_component_classes': dict(Counter(nodes[n]['class'] for n in comps[0])) if comps else {},
                'isolated_nodes': [nodes[n]['node'] for c in comps if len(c) == 1 for n in c],
                'starts_reaching_every_pickup_and_objective_factory': '%d/%d' % (reach_ok, len(starts))}
    out = {'map': MAP, 'source': 'manifests/authored.db (NavigationPoint.PathList -> TnReachSpec)',
           'reach_flag_legend': {n: b for b, n in REACH}, 'analysis': analysis,
           'nodes': sorted(nodes.values(), key=lambda d: (d['class'], d['node'])), 'edges': edges, 'notes': [
               'No PathNode / cover / NavigationCell / TnTactical* objects exist in any Streets package: the map has no AI tactical '
               'data (WFC MP has no bots on Streets). Other MP maps (e.g. MP_ESC_BrokenHope) do carry TnTactical data.',
               'The graph is UE3\'s editor-built path network over the gameplay NavigationPoints. reachFlags names are the stock UE3 '
               'ReachSpec enum (HIGH CONFIDENCE for this licensee build); TnReachSpec default ForcedPathSizeName = "Vehicle".',
               'Objective points (flag capture, bomb plant, domination, KOTH) own no ReachSpecs; they only receive one-way edges '
               '(destination-only), which accounts for the 10 one-way pairs.',
               "Every edge is <= 3385 UU, just under the nav points' authored MaxConnectionDistance 3400: with no intermediate "
               'PathNodes the editor only linked gameplay nav points within ~34 m, so the network is fragmented into islands. '
               'It is NOT a usable whole-map AI navigation graph; any bot/AI navigation for Streets must be generated, not recovered.',
               'Path sizes (Radius/Height UU) seen on nodes/edges: 250/300, 440/400, 750/800, 1210/850. The size-class table (WFC scout '
               'PathSizes) is editor-only and not in the cook: the stock Engine.Default__Scout table (Human 48/80 ... Vehicle 260/120) '
               'does not match, so size names are UNKNOWN.']}
    # ------------------------------------------------------------------ glb
    g = GLB('AssetTools vs_navigation (%s)' % MAP)
    order = list(nodes); idx = {n: i for i, n in enumerate(order)}
    P = np.array([nodes[n]['location_gltf'] for n in order], 'f4')
    I = np.array([[idx[e['start']], idx[e['end']]] for e in edges if e['end'] in idx], 'u4').ravel()
    pa = g.acc(P, 'VEC3', True, 34962)
    m = g.mesh('nav', [{'attributes': {'POSITION': pa}, 'mode': 0}, {'attributes': {'POSITION': pa}, 'indices': g.acc(I, 'SCALAR', target=34963), 'mode': 1}])
    g.node({'name': 'navigation', 'mesh': m, 'extras': {'nodes': [nodes[n]['node'] for n in order]}})
    g.write(os.path.join(OUT, 'navigation.glb'))
    path = os.path.join(OUT, 'navigation.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(analysis, default=str)[:2500]); print('->', path)

if __name__ == '__main__':
    main()
