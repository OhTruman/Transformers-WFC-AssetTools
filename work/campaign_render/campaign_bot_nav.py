"""Campaign bot nav for Gameplay's BotNav loader (Gameplay 2026-10-23: the D5_OME campaign boot), per chapter, from the ORIGINAL cooked
NavigationCell mesh (out/campaign_render/<CH>/navmesh.json, campaign_collision.py) and the chapter's cooked TnReachSpecs, with the
Escalation converter's rules (work/playtest_20261023/escalation_bot_nav.py / _v3.py):
  cells   one per original NavigationCell (ids = navmesh.json ids): vertices / centroid, clearance_m / headroom_m = authored MaxPathSize
          Radius / Height (PROVISIONAL), flags.vehicle_capable (>= 4.4 m), flags.blocked_at_start; edges start / end / normal / neighbors.
          The polygons sit at pawn-centre height as authored (measured +1.75 m on the Escalation maps).
  links   every cooked TnReachSpec of the chapter's level packages, start / end at the specs' actors (a NavigationCell directly, any other
          actor by the cell under its location, <= 34 m below), typed from reachFlags + actor class: walk / drop_down (walk-off <= 6 m) /
          jump_up / double_jump_up (R_JUMP) / special (R_SPECIAL or a lift / mover / jump pad / teleporter, with launch props) / UNKNOWN;
          executable_as per link.
  anchors TnCampaignPlayerStart (kind player_start), Checkpoint (checkpoint), TnTacticalPathNode (tactical; also listed as cover),
          PathNode (path_node), AirPathNode (air_path_node: location only, cell usually none: for a later air nav).
Coverage (bot_nav_coverage.json): pieces (edges + links, undirected), each player start / checkpoint cell in the main piece, and directed
reach player start <-> checkpoints over executable links (blocked-at-start cells applied).

    python campaign_bot_nav.py <CH>        -> out/campaign_render/<CH>/bot_nav.json + bot_nav_coverage.json
"""
import json, math, os, sqlite3, sys
from collections import OrderedDict as OD, Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'work', 'playtest_20261023')); sys.path.insert(0, HERE)
import escalation_bot_nav as V2  # noqa: E402  (find_cell, y_at, area_xz, ue_dir_to_gltf, VEH_R)
import campaign_render as CR  # noqa: E402
DB = sqlite3.connect(os.path.join(AT, 'manifests', 'authored.db')); INV = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
R_FLY, R_JUMP, R_SPECIAL, R_PROSCRIBED, R_PLAYERONLY = 2, 8, 32, 128, 512
WALKOFF_M, JMAX = 6.0, 5.0
SPECIAL_CLS = ('JumpPad', 'Lift', 'Teleport', 'Mover', 'Elevator', 'Ladder')
LAUNCH_KEYS = ('JumpVelocity', 'JumpTarget', 'JumpZ', 'DesiredDestination', 'URL', 'LiftTrigger', 'MyLift', 'LiftTag', 'JumpTime')
ANCHOR_KIND = OD([('TnCampaignPlayerStart', 'player_start'), ('PlayerStart', 'player_start'), ('Checkpoint', 'checkpoint'),
                  ('TnTacticalPathNode', 'tactical'), ('PathNode', 'path_node'), ('AirPathNode', 'air_path_node'),
                  ('MoverPathNode', 'mover_path_node')])   # RE 2026-10-23: lift-based path nodes (A1's intro elevator); ride with their Base mover

def g(v): return [round(0.01 * v['X'], 4), round(0.01 * v['Z'], 4), round(0.01 * v['Y'], 4)]
def obj(op):
    r = DB.execute('select class, props from objects where opath=?', (op,)).fetchone()
    return (r[0], json.loads(r[1] or '{}')) if r else (None, {})

def main(ch):
    R = os.path.join(CR.OUTR, ch); nm = json.load(open(os.path.join(R, 'navmesh.json'), encoding='utf-8'))
    levels = CR.chapter_levels(ch)
    cells = []
    for c in nm['cells']:
        V = c['vertices_gltf']; mps = c.get('max_path_size') or {}; r = (mps.get('Radius') or 0) / 100.0; h = (mps.get('Height') or 0) / 100.0
        ys = [q[1] for q in V]
        cells.append(OD([('id', c['id']), ('actor', c['actor']), ('vertices_gltf', V), ('centroid_gltf', c['centroid_gltf']),
                         ('area_m2', round(V2.area_xz(V), 2)), ('height_range_m', [round(min(ys), 3), round(max(ys), 3)]),
                         ('clearance_m', round(r, 2)), ('clearance_max_m', round(r, 2)), ('headroom_m', round(h, 2)),
                         ('flags', OD([('vehicle_capable', r >= V2.VEH_R), ('tactical', c.get('tactical')), ('blocked_at_start', c.get('blocked_at_start'))])),
                         ('edges', [OD([('start', e['start_gltf']), ('end', e['end_gltf']), ('normal', V2.ue_dir_to_gltf(e['normal_ue'])),
                                        ('neighbors', [{'cell': nb['cell']} for nb in e.get('neighbors') or [] if nb.get('cell') is not None]),
                                        ('border', e.get('border'))]) for e in c.get('edges') or []])]))
    by_actor = {c['actor']: c['id'] for c in cells}
    cache = {}
    def resolve(op):
        if op in cache: return cache[op]
        name = op.rsplit('.', 1)[-1]; cls, p = obj(op); L = p.get('Location'); pos = g(L) if L else None
        if name in by_actor: cid = by_actor[name]; pos = pos or cells[cid]['centroid_gltf']
        else:
            hh = V2.find_cell(cells, pos, up=2.0, drop=34.0) if pos else None; cid = hh[0] if hh else None
        cache[op] = (cid, pos, cls, p); return cache[op]
    links, seen, kinds, skipped = [], set(), Counter(), 0
    ph = ','.join('?' * len(levels))
    for (q_,) in DB.execute("select o.props from objects o where o.class='TnReachSpec' and o.package in (%s)" % ph, levels):
        q = json.loads(q_ or '{}'); fl = q.get('reachFlags') or 0
        if fl & (R_PROSCRIBED | R_PLAYERONLY) or (fl & R_FLY and not fl & ~R_FLY): skipped += 1; continue
        st, en = q.get('Start'), (q.get('End') or {}).get('Nav')
        if not st or not en: continue
        fa, pa, ca, sp = resolve(st); to, pb, cb, ep = resolve(en)
        if fa is None or to is None or fa == to or pa is None or pb is None: continue
        rise = pb[1] - pa[1]; span = math.hypot(pb[0] - pa[0], pb[2] - pa[2])
        sa = next((x for x in (ca, cb) if x and any(s in x for s in SPECIAL_CLS)), None)
        if fl & R_SPECIAL or sa: kind, ex = 'special', 'special'
        elif fl & R_JUMP: kind, ex = ('double_jump_up' if rise > JMAX else 'jump_up'), 'jump'
        elif rise < -1.0: kind, ex = (('drop_down', 'fall') if span <= WALKOFF_M else ('UNKNOWN', 'UNKNOWN'))
        else: kind, ex = 'walk', 'walk'
        if (fa, to, kind) in seen: continue
        seen.add((fa, to, kind)); kinds[kind] += 1
        rec = OD([('kind', kind), ('executable_as', ex), ('from_cell', fa), ('to_cell', to), ('rise_m', round(rise, 2)), ('span_m', round(span, 2)),
                  ('from_gltf', pa), ('to_gltf', pb), ('forms', ['robot'] + (['vehicle'] if (q.get('CollisionRadius') or 0) / 100.0 >= V2.VEH_R else [])),
                  ('reach_start', st.rsplit('.', 1)[-1]), ('reach_start_class', ca), ('reach_end', en.rsplit('.', 1)[-1]), ('reach_end_class', cb), ('reach_flags', fl)])
        if kind == 'special':
            rec['special_actor_class'] = sa; rec['launch'] = {k: v for k, v in (sp if sa == ca else ep).items() if k in LAUNCH_KEYS}
        links.append(rec)
    anchors, cover = [], []
    for cls, kind in ANCHOR_KIND.items():
        for (op,) in INV.execute("select opath from exports where package in (%s) and class=?" % ph, levels + [cls]):
            if op.count('.') != 3: continue
            c_, p = obj(op); L = p.get('Location')
            if not L: continue
            pos = g(L); hh = V2.find_cell(cells, pos, up=2.0, drop=8.0) if kind != 'air_path_node' else None
            drop_m = None
            if hh is None and kind in ('player_start', 'checkpoint'):
                # airborne starts / checkpoints (A1_IAC: the level opens mid-air, CAMPAIGN_BACKLOG item 5): the cell straight below
                land = V2.find_cell(cells, pos, up=2.0, drop=300.0)
                if land: hh = land; drop_m = round(pos[1] - land[1], 2)
            a = OD([('actor', op.rsplit('.', 1)[-1]), ('class', cls), ('kind', kind), ('level', op.split('.')[0]), ('location_gltf', pos),
                    ('cell', hh[0] if hh else None), ('approach_cell', hh[0] if hh else None)])
            if drop_m is not None: a['airborne_drop_m'] = drop_m
            if kind == 'mover_path_node':
                a['base'] = p.get('Base'); a['cell'] = a['approach_cell'] = None      # rides the mover: no static cell
            if kind == 'checkpoint':
                a['tag'] = p.get('Tag'); a['display_order'] = p.get('DisplayOrder'); a['streaming_state'] = p.get('StreamingState')
            anchors.append(a)
            if kind == 'tactical' and hh: cover.append(OD([('cell', hh[0]), ('at_gltf', pos), ('node', a['actor']), ('type', 'tactical_path_node')]))
    out = OD([('map', ch), ('generated_by', 'AssetTools/work/campaign_render/campaign_bot_nav.py'), ('status', 'campaign bot nav (original NavigationCell mesh)'),
              ('source', 'out/campaign_render/%s/navmesh.json + the chapter TnReachSpecs (authored.db)' % ch), ('units', 'gltf metres Y-up'),
              ('parameters', OD([('clearance', 'MaxPathSize.Radius / 100 (PROVISIONAL)'), ('headroom', 'MaxPathSize.Height / 100 (PROVISIONAL)'),
                                 ('vehicle_radius_m', V2.VEH_R), ('jump_up_max_m', JMAX), ('walkoff_m', WALKOFF_M),
                                 ('cell_height', 'as authored (pawn-centre height; measured +1.75 m above floor on the Escalation maps)')])),
              ('stats', OD([('cells', len(cells)), ('blocked_at_start', sum(1 for c in cells if c['flags']['blocked_at_start'])),
                            ('walkable_area_m2', round(sum(c['area_m2'] for c in cells))), ('links', len(links)), ('link_kinds', dict(kinds)),
                            ('reach_specs_skipped', skipped), ('anchors', len(anchors)), ('anchors_on_nav', sum(1 for a in anchors if a['cell'] is not None)),
                            ('cover', len(cover))])),
              ('cells', cells), ('links', links), ('cover', cover), ('anchors', anchors), ('waypoints', [])])
    json.dump(out, open(os.path.join(R, 'bot_nav.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    # coverage
    pid, npieces = V2.pieces(cells, links)
    main_piece = Counter(pid.values()).most_common(1)[0][0] if pid else None
    blocked = {c['id'] for c in cells if c['flags']['blocked_at_start']}
    fwd = defaultdict(set)
    for c in cells:
        if c['id'] in blocked: continue
        for e in c['edges']:
            for nb in e['neighbors']:
                if nb['cell'] not in blocked: fwd[c['id']].add(nb['cell']); fwd[nb['cell']].add(c['id'])
    for l in links:
        if l['executable_as'] in ('walk', 'fall', 'jump') and l['from_cell'] not in blocked and l['to_cell'] not in blocked: fwd[l['from_cell']].add(l['to_cell'])
    def reach(s0):
        o, st = {s0}, [s0]
        while st:
            v = st.pop()
            for w in fwd[v]:
                if w not in o: o.add(w); st.append(w)
        return o
    key = [a for a in anchors if a['kind'] in ('player_start', 'checkpoint')]
    rows = []
    for a in key:
        c = a['cell']; r = reach(c) if c is not None else set()
        rows.append(OD([('actor', a['actor']), ('kind', a['kind']), ('tag', a.get('tag')), ('cell', c), ('in_main_piece', pid.get(c) == main_piece if c is not None else None),
                        ('reaches', sorted(b['actor'] for b in key if b is not a and b['cell'] in r))]))
    cov = OD([('chapter', ch), ('pieces (edges + links, undirected)', npieces), ('main_piece_cells', sum(1 for v in pid.values() if v == main_piece)),
              ('cells', len(cells)), ('link_kinds', dict(kinds)),
              ('anchors_by_kind_on_nav', {k: '%d / %d' % (sum(1 for a in anchors if a['kind'] == k and a['cell'] is not None), sum(1 for a in anchors if a['kind'] == k))
                                          for k in sorted({a['kind'] for a in anchors})}),
              ('player_start_and_checkpoints', rows)])
    json.dump(cov, open(os.path.join(R, 'bot_nav_coverage.json'), 'w', encoding='utf-8'), indent=1)
    print(ch, json.dumps({k: v for k, v in cov.items() if k != 'player_start_and_checkpoints'}))
    for r_ in rows: print('  ', dict(r_))

if __name__ == '__main__':
    main(sys.argv[1])
