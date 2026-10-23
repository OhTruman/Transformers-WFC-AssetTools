"""Escalation bot nav from the ORIGINAL cooked NavigationCell mesh (Gameplay / Integration 2026-10-23: 34 of 61 Remnant and 30 of 58
BrokenHope TnSurvivalSpawnPoints are off the reconstructed bot nav; the original horde walks off its perches on this mesh).

    python escalation_bot_nav.py <MAP>      MP_ESC_BrokenHope / MP_ESC_Remnant

Input  manifests/maps/<MAP>/escalation_navmesh.json (escalation_data.py B), escalation_geometry.json (spawn points), the shipped
       bot_nav.json anchors (player starts / pickups / objectives) for kinds and locations.
Output manifests/maps/<MAP>/bot_nav_escalation.json   Gameplay BotNav schema (cells: vertices_gltf, centroid_gltf, clearance_m,
                                                      headroom_m, flags.vehicle_capable, edges start / end / normal / neighbors; links;
                                                      anchors), one cell per original NavigationCell (same ids as escalation_navmesh)
       manifests/maps/<MAP>/escalation_nav_blockers.json  the original's own gating: cells blocked at start (cooked bBlocked or turned off
                                                      by PreGameplaySetup) and, per TnSurvivalGenerator, the cells its events turn on
       manifests/maps/<MAP>/escalation_nav_coverage.json  per spawn point: its authored nav_anchor cell and a geometric findCell test
Clearance / headroom: the cell's authored MaxPathSize Radius / Height (cm -> m), PROVISIONAL (UE3 MaxPathSize is the largest
reachspec-able size through the cell, used here as the clearance the loader filters on); vehicle_capable = clearance >= bot_nav's
vehicle_radius_m (4.4, CONFIRMED). Links (Gameplay 2026-10-23: perches were islands without them): every cooked TnReachSpec of the map's packages
(start / end = a NavigationCell directly, or any other actor resolved to the cell under its location) becomes a BotNav link; kind by height (end higher than
jump_up_max_m -> double_jump_up, higher than 1 m -> jump_up, else drop_down: the loader's non-jump move, so level R_WALK specs map there,
PROVISIONAL); R_PROSCRIBED / R_PLAYERONLY / R_FLY-only specs are skipped; forms: robot, + vehicle when the spec's CollisionRadius >=
vehicle_radius_m. Connectivity (loader rule: portals + links, undirected) is reported in escalation_nav_coverage.json.
"""
import json, os, sys
from collections import OrderedDict as OD, defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
VSM = r'F:\Transformers Rebuild\ExtractedAssets\VerticalSlice\Maps'
VEH_R = 4.4

def ue_dir_to_gltf(v): return [v[0], v[2], v[1]]

def area_xz(V):
    x = np.array([p[0] for p in V]); z = np.array([p[2] for p in V])
    return float(abs(np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1))) / 2)

def y_at(V, x, z):
    """height of the cell's fan triangulation at (x, z), or None if outside"""
    for k in range(1, len(V) - 1):
        a, b, c = V[0], V[k], V[k + 1]
        d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
        if abs(d) < 1e-12: continue
        l1 = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / d; l2 = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / d; l3 = 1 - l1 - l2
        if min(l1, l2, l3) >= -1e-4: return l1 * a[1] + l2 * b[1] + l3 * c[1]
    return None

def find_cell(cells, p, up=2.0, drop=8.0):
    """the highest cell under p within [p.y - drop, p.y + up] (Gameplay findCell semantics: 2 m radius / 8 m drop, approximated in height)"""
    best = None
    for c in cells:
        V = c['vertices_gltf']
        xs = [q[0] for q in V]; zs = [q[2] for q in V]
        if not (min(xs) - 1e-3 <= p[0] <= max(xs) + 1e-3 and min(zs) - 1e-3 <= p[2] <= max(zs) + 1e-3): continue
        y = y_at(V, p[0], p[2])
        if y is not None and p[1] - drop <= y <= p[1] + up and (best is None or y > best[1]): best = (c['id'], y)
    return best

import sqlite3
DBA = sqlite3.connect(os.path.join(AT, 'manifests', 'authored.db'))
R_FLY, R_PROSCRIBED, R_PLAYERONLY = 2, 128, 512

def pieces(cells, links):
    """connected pieces over edge neighbours + links (undirected), the BotNav loader's rule"""
    adj = defaultdict(set)
    for c in cells:
        for e in c['edges']:
            for nb in e['neighbors']: adj[c['id']].add(nb['cell']); adj[nb['cell']].add(c['id'])
    for l in links: adj[l['from_cell']].add(l['to_cell']); adj[l['to_cell']].add(l['from_cell'])
    pid, n = {}, 0
    for c in cells:
        if c['id'] in pid: continue
        st = [c['id']]; pid[c['id']] = n
        while st:
            v = st.pop()
            for w in adj[v]:
                if w not in pid: pid[w] = n; st.append(w)
        n += 1
    return pid, n

def main(mp):
    M = os.path.join(AT, 'manifests', 'maps', mp)
    nm = json.load(open(os.path.join(M, 'escalation_navmesh.json'), encoding='utf-8'))
    geo = json.load(open(os.path.join(M, 'escalation_geometry.json'), encoding='utf-8'))
    shipped = json.load(open(os.path.join(VSM, mp, 'bot_nav.json'), encoding='utf-8'))
    by_actor = {c['actor']: c['id'] for c in nm['cells']}
    cells = []
    for c in nm['cells']:
        V = c['vertices_gltf']; mps = c.get('max_path_size') or {}
        r = (mps.get('Radius') or 0) / 100.0; h = (mps.get('Height') or 0) / 100.0; ys = [q[1] for q in V]
        edges = [OD([('start', e['start_gltf']), ('end', e['end_gltf']), ('normal', ue_dir_to_gltf(e['normal_ue'])),
                     ('neighbors', [{'cell': nb['cell']} for nb in e.get('neighbors') or [] if nb.get('cell') is not None]), ('border', e.get('border'))])
                 for e in c.get('edges') or []]
        cells.append(OD([('id', c['id']), ('actor', c['actor']), ('vertices_gltf', V), ('centroid_gltf', c['centroid_gltf']),
                         ('area_m2', round(area_xz(V), 2)), ('height_range_m', [round(min(ys), 3), round(max(ys), 3)]),
                         ('clearance_m', round(r, 2)), ('clearance_max_m', round(r, 2)), ('headroom_m', round(h, 2)),
                         ('flags', OD([('vehicle_capable', r >= VEH_R), ('tactical', c.get('tactical')), ('blocked_at_start', c.get('blocked_at_start'))])),
                         ('edges', edges)]))
    P = shipped.get('parameters') or {}
    jmax = ((P.get('jump_up_max_m') or {}).get('value') or 5.0)
    node_loc = {}
    for cls, lst in (nm.get('nodes') or {}).items():
        for nd in lst: node_loc[nd['actor']] = nd.get('location_gltf')
    links, skipped, seen = [], 0, set()
    pk = {'MP_ESC_BrokenHope': ('MP_ESC_BrokenHope_Base_m', 'MP_ESC_BrokenHope_ART_m'), 'MP_ESC_Remnant': ('MP_ESC_Remnant_BASE_m', 'MP_ESC_Remnant_ART_m')}[mp]
    loc_cache = {}
    def cell_of(op):
        """a reach spec endpoint -> cell id: a NavigationCell directly, any other actor (path node, spawn point, pickup ...) by the cell
        under its location (up to the 34 m MaxFallHeight below)"""
        name = op.rsplit('.', 1)[-1]
        if name in by_actor: return by_actor[name]
        if op not in loc_cache:
            r = DBA.execute('select props from objects where opath=?', (op,)).fetchone()
            L = (json.loads(r[0] or '{}').get('Location') if r else None)
            h = find_cell(cells, [0.01 * L['X'], 0.01 * L['Z'], 0.01 * L['Y']], up=2.0, drop=34.0) if L else None
            loc_cache[op] = h[0] if h else None
        return loc_cache[op]
    for pkg in pk:
        for (q_,) in DBA.execute("select props from objects where package=? and class='TnReachSpec'", (pkg,)):
            q = json.loads(q_ or '{}'); fl = q.get('reachFlags') or 0
            if fl & (R_PROSCRIBED | R_PLAYERONLY) or (fl & R_FLY and not fl & ~R_FLY): skipped += 1; continue
            st, en = q.get('Start'), (q.get('End') or {}).get('Nav')
            if not st or not en: continue
            fa, to = cell_of(st), cell_of(en)
            if fa is None or to is None or fa == to or (fa, to) in seen: continue
            seen.add((fa, to))
            a_ = cells[fa]['centroid_gltf']; b_ = cells[to]['centroid_gltf']; dy = b_[1] - a_[1]
            kind = 'double_jump_up' if dy > jmax else ('jump_up' if dy > 1.0 else 'drop_down')
            forms = ['robot'] + (['vehicle'] if (q.get('CollisionRadius') or 0) / 100.0 >= VEH_R else [])
            links.append(OD([('kind', kind), ('from_cell', fa), ('to_cell', to), ('rise_m', round(dy, 2)), ('from_gltf', a_), ('to_gltf', b_),
                             ('forms', forms), ('reach_start', st.rsplit('.', 1)[-1]), ('reach_end', en.rsplit('.', 1)[-1]), ('reach_flags', fl)]))
    anchors = []
    for a in shipped.get('anchors') or []:
        hit = find_cell(cells, a['location_gltf'])
        anchors.append(OD([('actor', a['actor']), ('class', a.get('class')), ('kind', a.get('kind')), ('location_gltf', a['location_gltf']),
                           ('cell', hit[0] if hit else None), ('approach_cell', hit[0] if hit else None)]))
    cov = []
    for z in geo['zones']:
        for k, sp in enumerate(z.get('spawn_points') or []):
            anc = by_actor.get(sp.get('nav_anchor')); hit = find_cell(cells, sp['location_gltf'])
            anchors.append(OD([('actor', sp['actor']), ('class', sp.get('class')), ('kind', 'survival_spawn_point'), ('location_gltf', sp['location_gltf']),
                               ('cell', anc if anc is not None else (hit[0] if hit else None)), ('approach_cell', anc if anc is not None else (hit[0] if hit else None)),
                               ('zone', z['zone'])]))
            cov.append(OD([('zone', z['zone']), ('k', k), ('actor', sp['actor']), ('location_gltf', sp['location_gltf']), ('on_nav_mesh', sp.get('on_nav_mesh')),
                           ('nav_anchor', sp.get('nav_anchor')), ('anchor_cell', anc), ('anchor_cell_blocked_at_start', cells[anc]['flags']['blocked_at_start'] if anc is not None else None),
                           ('findcell', hit[0] if hit else None), ('findcell_height_gap_m', round(sp['location_gltf'][1] - hit[1], 2) if hit else None)]))
    out = OD([('map', mp), ('generated_by', 'AssetTools/work/playtest_20261023/escalation_bot_nav.py'), ('status', 'Escalation nav (GameModeTag ESC only)'),
              ('source', 'the ORIGINAL cooked NavigationCell mesh (manifests/maps/%s/escalation_navmesh.json); cell ids = its ids' % mp),
              ('units', 'gltf metres Y-up'), ('parameters', OD([('clearance', 'MaxPathSize.Radius / 100 (PROVISIONAL)'), ('headroom', 'MaxPathSize.Height / 100 (PROVISIONAL)'),
                                                                ('vehicle_radius_m', VEH_R), ('jump_up_max_m', jmax),
                                                                ('links', 'cooked TnReachSpec per cell PathList (see docstring); skipped R_PROSCRIBED / R_PLAYERONLY / fly-only: %d' % skipped)])),
              ('stats', OD([('cells', len(cells)), ('blocked_at_start', sum(1 for c in cells if c['flags']['blocked_at_start'])),
                            ('vehicle_capable_cells', sum(1 for c in cells if c['flags']['vehicle_capable'])), ('walkable_area_m2', round(sum(c['area_m2'] for c in cells))),
                            ('anchors', len(anchors)), ('anchors_on_nav', sum(1 for a in anchors if a['cell'] is not None))])),
              ('cells', cells), ('links', links), ('cover', []), ('anchors', anchors), ('waypoints', [])])
    json.dump(out, open(os.path.join(M, 'bot_nav_escalation.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    gens = defaultdict(list)
    for c in nm['cells']:
        for gname in c.get('enabled_by_generators') or []: gens[gname].append(c['id'])
    bl = OD([('map', mp), ('source', 'escalation_navmesh.json blocked_at_start / enabled_by_generators (original Kismet: SeqAct_Toggle Turn On / PreGameplaySetup Turn Off)'),
             ('blocked_at_start', sorted(c['id'] for c in cells if c['flags']['blocked_at_start'])),
             ('opened_by_generator', OD((k, sorted(v)) for k, v in sorted(gens.items()))),
             ('blocked_by_setup', OD((c['actor'], c['blocked_by_setup']) for c in nm['cells'] if c.get('blocked_by_setup')))])
    json.dump(bl, open(os.path.join(M, 'escalation_nav_blockers.json'), 'w', encoding='utf-8'), indent=1)
    pid, npieces = pieces(cells, links); pid0, np0 = pieces(cells, [])
    from collections import Counter
    main_piece = Counter(pid.values()).most_common(1)[0][0]
    for cv in cov:
        cv['piece'] = pid.get(cv['anchor_cell']) if cv['anchor_cell'] is not None else None
        cv['in_main_piece'] = cv['piece'] == main_piece if cv['piece'] is not None else None
    fwd = defaultdict(set)                                   # directed: edge neighbours both ways, links from -> to
    for c in cells:
        for e in c['edges']:
            for nb in e['neighbors']: fwd[c['id']].add(nb['cell']); fwd[nb['cell']].add(c['id'])
    for l in links: fwd[l['from_cell']].add(l['to_cell'])
    goals = {a['cell'] for a in anchors if a.get('kind') == 'player_start' and a.get('cell') is not None}
    def reaches(s0):
        seenr, st = {s0}, [s0]
        while st:
            v = st.pop()
            if v in goals: return True
            for w in fwd[v]:
                if w not in seenr: seenr.add(w); st.append(w)
        return False
    for cv in cov: cv['reaches_player_starts (directed)'] = reaches(cv['anchor_cell']) if cv['anchor_cell'] is not None and goals else None
    summ = OD([('pieces_before_blocking (edges + links)', npieces), ('pieces_edges_only', np0),
               ('player_start_cells', len(goals)),
               ('on_nav_mesh_points_reaching_player_starts (directed, before blocking)', sum(1 for c in cov if c['on_nav_mesh'] and c['reaches_player_starts (directed)'])),
               ('main_piece_cells', sum(1 for v in pid.values() if v == main_piece)), ('links', len(links)),
               ('on_nav_mesh_points_in_main_piece', sum(1 for c in cov if c['on_nav_mesh'] and c['in_main_piece'])),
               ('spawn_points', len(cov)), ('on_nav_mesh_true', sum(1 for c in cov if c['on_nav_mesh'])),
               ('anchor_cell_found', sum(1 for c in cov if c['anchor_cell'] is not None)),
               ('on_nav_mesh_true_and_anchor_cell', sum(1 for c in cov if c['on_nav_mesh'] and c['anchor_cell'] is not None)),
               ('findcell_hit', sum(1 for c in cov if c['findcell'] is not None)),
               ('anchor_blocked_at_start', sum(1 for c in cov if c['anchor_cell_blocked_at_start']))])
    json.dump(OD([('map', mp), ('summary', summ), ('points', cov)]), open(os.path.join(M, 'escalation_nav_coverage.json'), 'w', encoding='utf-8'), indent=1)
    print(mp, json.dumps(out['stats']), '| coverage', json.dumps(summ))

if __name__ == '__main__':
    main(sys.argv[1])
