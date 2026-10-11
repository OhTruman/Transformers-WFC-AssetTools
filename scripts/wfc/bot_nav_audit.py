"""Nav-gap audit over bot_nav outputs (Gameplay request 2026-10-10: Streets FFA 64 stuck reports).

  python bot_nav_audit.py <dry_dir> [--out manifests/bot_nav/nav_gap_audit.json]

For every map with <dry_dir>/<MAP>/bot_nav.json (+ bot_nav_pruned.json from `bot_nav.py --debug`):
- player starts / pickups / objectives that are off the mesh, only one-way into the core, or need an approach cell;
- walkable regions dropped from the nav (pruned groups >= MIN_AREA m2): why (unreached = no way in; one_way = way in, no way
  back = a trap), entry sources, kept cells right next to them (a missed connection candidate), anchors standing on them;
- stats against the shipped bot_nav.json next to the inputs (cells / area / links / components).
Nothing here is invented: every row comes from the nav outputs and the map's gameplay.json anchors.
"""
import json, os, sys
from collections import OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import VS  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MIN_AREA = 200.0

def near_kept(g, cells, pad=3.0, dy=1.5):
    a, b = g['bbox_min_gltf'], g['bbox_max_gltf']
    n = 0
    for c in cells:
        x, y, z = c['centroid_gltf']
        if a[0] - pad <= x <= b[0] + pad and a[2] - pad <= z <= b[2] + pad and a[1] - dy <= y <= b[1] + dy: n += 1
    return n

def anchors_on(g, anchors, dy=4.0):
    a, b = g['bbox_min_gltf'], g['bbox_max_gltf']; out = []
    for an in anchors:
        x, y, z = an['location_gltf']
        if a[0] - 1 <= x <= b[0] + 1 and a[2] - 1 <= z <= b[2] + 1 and a[1] - 0.5 <= y <= b[1] + dy: out.append(an['actor'])
    return out

def reachspec_check(m, d):
    """ground truth: every original walking TnReachSpec (navigation.json, R_WALK without R_JUMP / R_SPECIAL / R_LADDER /
    R_FLY / R_PROSCRIBED) must have a nav path from its start anchor's cell to its end anchor's cell (neighbour edges + links,
    shortest path over cell centroids). Missing = regression; detour = nav path / ReachSpec distance."""
    import heapq, math
    nf = os.path.join(VS, 'Maps', m, 'navigation.json')
    if not os.path.exists(nf): return None
    nav = json.load(open(nf, encoding='utf-8'))
    cell = {a['actor']: (a['cell'] if a['cell'] is not None else a.get('approach_cell')) for a in d['anchors']}
    C = {c['id']: c['centroid_gltf'] for c in d['cells']}
    # navigation points that are not gameplay anchors (PathNode / TnTactical* on Escalation-derived maps): snap by location to
    # the cell whose rectangle contains it, floor 0-4 m below the point (nav points sit ~ half a pawn above the floor)
    def snap(L):
        best = None
        for c in d['cells']:
            V = c['vertices_gltf']; xs = [v[0] for v in V]; zs = [v[2] for v in V]
            if min(xs) - 0.5 <= L[0] <= max(xs) + 0.5 and min(zs) - 0.5 <= L[2] <= max(zs) + 0.5:
                dy = L[1] - c['centroid_gltf'][1]
                if -1.0 <= dy <= 4.0 and (best is None or abs(dy) < best[0]): best = (abs(dy), c['id'])
        return best[1] if best else None
    for x in nav.get('nodes') or []:
        if cell.get(x['node']) is None and x.get('location_gltf'): cell[x['node']] = snap(x['location_gltf'])
    adj = {c['id']: set() for c in d['cells']}
    for c in d['cells']:
        for e in c['edges']:
            for nb in e['neighbors']: adj[c['id']].add(nb['cell'])
    for l in d['links']: adj[l['from_cell']].add(l['to_cell'])
    def path_len(s, t):
        if s == t: return 0.0
        dist = {s: 0.0}; pq = [(0.0, s)]
        while pq:
            du, u = heapq.heappop(pq)
            if u == t: return du
            if du > dist.get(u, 1e18): continue
            for v in adj.get(u, ()):
                w = du + math.dist(C[u], C[v])
                if w < dist.get(v, 1e18): dist[v] = w; heapq.heappush(pq, (w, v))
        return None
    bad_flags = {'R_JUMP', 'R_SPECIAL', 'R_LADDER', 'R_FLY', 'R_PROSCRIBED', 'R_SWIM'}
    rows = []; ok = 0; n = 0; unk = 0
    for e in nav.get('edges') or []:
        fl = set(e.get('flags') or [])
        if 'R_WALK' not in fl or fl & bad_flags: continue
        a_, b_ = e['start'].split('.')[-1], e['end'].split('.')[-1]; n += 1
        if cell.get(a_) is None or cell.get(b_) is None: unk += 1; rows.append(OD([('spec', e['spec']), ('start', a_), ('end', b_), ('issue', 'anchor_not_on_nav')])); continue
        L = path_len(cell[a_], cell[b_]); rd = e['distance'] / 100.0
        if L is None: rows.append(OD([('spec', e['spec']), ('start', a_), ('end', b_), ('reachspec_m', round(rd, 1)), ('issue', 'no_nav_path')]))
        else:
            ok += 1
            if L > 2.5 * rd + 20: rows.append(OD([('spec', e['spec']), ('start', a_), ('end', b_), ('reachspec_m', round(rd, 1)), ('nav_m', round(L, 1)), ('issue', 'detour')]))
    return OD([('walking_reachspecs', n), ('with_nav_path', ok), ('anchor_not_on_nav', unk),
               ('missing', sum(1 for r in rows if r['issue'] == 'no_nav_path')), ('detours_over_2_5x', sum(1 for r in rows if r['issue'] == 'detour')),
               ('rows', rows)])

def links_into(d, box):
    x0, x1, z0, z1, ymax = box
    return [l for l in d['links'] if x0 <= l['to_gltf'][0] <= x1 and z0 <= l['to_gltf'][2] <= z1 and l['to_gltf'][1] <= ymax]

def audit_map(dry, m):
    d = json.load(open(os.path.join(dry, m, 'bot_nav.json'), encoding='utf-8'))
    pp = os.path.join(dry, m, 'bot_nav_pruned.json'); G = json.load(open(pp, encoding='utf-8')) if os.path.exists(pp) else []
    shipped = os.path.join(VS, 'Maps', m, 'bot_nav.json')
    s0 = json.load(open(shipped, encoding='utf-8'))['stats'] if os.path.exists(shipped) else {}
    an = d['anchors']
    bad = [OD([('actor', a['actor']), ('kind', a['kind']), ('location_gltf', [round(v, 2) for v in a['location_gltf']]),
               ('issue', 'off_mesh' if a['cell'] is None else 'one_way_into_core' if a.get('one_way_into_core') else 'approach_cell_only'),
               ('note', a.get('approach_note'))])
           for a in an if a['cell'] is None or a.get('one_way_into_core') or a.get('approach_note')]
    groups = []
    for g in G:
        if g['area_m2'] < MIN_AREA: continue
        on = anchors_on(g, an)
        groups.append(OD([('why', g['why']), ('area_m2', g['area_m2']), ('cells', g['cells']),
                          ('bbox_min_gltf', g['bbox_min_gltf']), ('bbox_max_gltf', g['bbox_max_gltf']),
                          ('max_clearance_m', g['max_clearance_m']), ('links_in', g['links_in']), ('links_out', g['links_out']),
                          ('entry_sources_gltf', g.get('entry_sources_gltf', [])[:8]),
                          ('kept_cells_adjacent', near_kept(g, d['cells'])), ('anchors_on_it', on)]))
    st = d['stats']
    keys = ('cells', 'walkable_area_m2', 'links', 'components', 'one_way_cells_dropped', 'anchors', 'anchors_on_nav',
            'anchors_with_main_approach_cell', 'core_cells (two-way reachable incl. links)')
    return OD([('map', m), ('stats_new', OD((k, st.get(k)) for k in keys)), ('stats_shipped', OD((k, s0.get(k)) for k in keys)),
               ('forced_dir_volumes_blocking', st.get('forced_dir_volumes_blocking')),
               ('anchor_issues', bad),
               ('reachspec_ground_truth', reachspec_check(m, d)),
               ('links_below_y_minus_735', len([l for l in d['links'] if l['to_gltf'][1] < -735])) if m == 'MP_IAC_Streets' else ('links_below_y_minus_735', None),
               ('streets_north_pit_links', len(links_into(d, (110, 150, -280, -266, -735)))) if m == 'MP_IAC_Streets' else ('streets_north_pit_links', None),
               ('traps_one_way', [g for g in groups if g['why'] == 'one_way']),
               ('unreached_next_to_nav', [g for g in groups if g['why'] == 'unreached' and g['kept_cells_adjacent']]),
               ('unreached_with_anchors', [g for g in groups if g['why'] == 'unreached' and g['anchors_on_it']]),
               ('unreached_other_count', sum(1 for g in groups if g['why'] == 'unreached' and not g['kept_cells_adjacent'] and not g['anchors_on_it']))])

def main():
    dry = sys.argv[1]
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else os.path.join(AT, 'manifests', 'bot_nav', 'nav_gap_audit.json')
    maps = sorted(m for m in os.listdir(dry) if os.path.exists(os.path.join(dry, m, 'bot_nav.json')))
    res = OD([('generated_by', 'AssetTools/scripts/wfc/bot_nav_audit.py'), ('source', os.path.relpath(dry, AT).replace(os.sep, '/')),
              ('min_area_m2', MIN_AREA), ('maps', [audit_map(dry, m) for m in maps])])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, 'w', encoding='utf-8'), indent=1)
    for r in res['maps']:
        a, b = r['stats_shipped'], r['stats_new']
        print('%-18s cells %5s -> %5s  area %7s -> %7s  comps %3s -> %3s  anchor issues %d  traps %d  unreached-next-to-nav %d  unreached-with-anchors %d'
              % (r['map'], a.get('cells'), b.get('cells'), a.get('walkable_area_m2'), b.get('walkable_area_m2'), a.get('components'),
                 b.get('components'), len(r['anchor_issues']), len(r['traps_one_way']), len(r['unreached_next_to_nav']),
                 len(r['unreached_with_anchors'])))
        rs = r['reachspec_ground_truth']
        if rs: print('    reachspecs walk %d  nav path %d  missing %d  detours %d  anchor off nav %d' % (rs['walking_reachspecs'], rs['with_nav_path'], rs['missing'], rs['detours_over_2_5x'], rs['anchor_not_on_nav']))
    print('wrote', out)

if __name__ == '__main__':
    main()
