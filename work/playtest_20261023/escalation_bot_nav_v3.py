"""Escalation bot nav v3 (Gameplay / Integration 2026-10-23), on top of v2 (escalation_bot_nav.py: the original NavigationCell mesh in
Gameplay's BotNav schema, ids = escalation_navmesh ids):
  1. links TYPED from the cooked TnReachSpec, not by rise: start / end = the reach spec's actors (their own locations, not cell
     centroids). kind:
       special         reachFlags R_SPECIAL, or a start actor that is a jump pad / lift / mover / teleporter: the actor's class and launch
                       props (JumpVelocity / JumpTarget / DesiredDestination / ... where authored) are carried; Gameplay costs it out
       jump_up / double_jump_up   R_JUMP (rise > jump_up_max_m: double)
       drop_down       R_WALK falling more than 1 m with a horizontal span <= WALKOFF_M (a walk-off fall)
       walk            R_WALK otherwise (level / ramps)
       UNKNOWN         an R_WALK fall wider than WALKOFF_M (not executable as walk or fall; kept for the record, Gameplay skips it)
     executable_as = walk / fall / jump / special / UNKNOWN.
  2. MERGE (Gameplay chose b): cells of the shipped versus nav (overlay_20261023g) where no original cell lies under the centroid
     (+-1.5 m) are appended after the original ids with flags.versus_only = true; their edge neighbours among themselves are kept (remapped),
     an edge neighbour that is an overlapping versus cell becomes a two-way walk link to the original cell under it; versus links between
     merged cells are kept. Original ids stay first and unchanged (blockers / unlocks index them).
  3. coverage with start-blocked cells applied and executable links only (walk / fall / jump): every TnTeamPlayerStart reaches every
     TnSurvivalGenerator's cell; every on-mesh spawn point reaches the player starts, and the reverse.

    python escalation_bot_nav_v3.py <MAP>      -> manifests/maps/<MAP>/bot_nav_escalation.json (+ coverage / blockers unchanged ids)
"""
import json, math, os, sqlite3, sys
from collections import OrderedDict as OD, Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import escalation_bot_nav as V2  # noqa: E402
DB = sqlite3.connect(os.path.join(AT, 'manifests', 'authored.db'))
R_WALK, R_FLY, R_JUMP, R_SPECIAL, R_PROSCRIBED, R_PLAYERONLY = 1, 2, 8, 32, 128, 512
WALKOFF_M = 6.0
SPECIAL_CLS = ('JumpPad', 'Lift', 'Teleport', 'Mover', 'Elevator', 'LiftCenter', 'LiftExit', 'Ladder')
LAUNCH_KEYS = ('JumpVelocity', 'JumpTarget', 'JumpZ', 'DesiredDestination', 'URL', 'LiftTrigger', 'MyLift', 'LiftTag', 'JumpTime')
PKGS = {'MP_ESC_BrokenHope': ('MP_ESC_BrokenHope_Base_m', 'MP_ESC_BrokenHope_ART_m'), 'MP_ESC_Remnant': ('MP_ESC_Remnant_BASE_m', 'MP_ESC_Remnant_ART_m')}
VERSUS = os.path.join(AT, 'work', 'overlay_20261023g', 'VerticalSlice', 'Maps')

def obj(op):
    r = DB.execute('select class, props from objects where opath=?', (op,)).fetchone()
    return (r[0], json.loads(r[1] or '{}')) if r else (None, {})

def g(v): return [round(0.01 * v['X'], 4), round(0.01 * v['Z'], 4), round(0.01 * v['Y'], 4)]

def main(mp):
    M = os.path.join(AT, 'manifests', 'maps', mp)
    v2 = json.load(open(os.path.join(M, 'bot_nav_escalation.json'), encoding='utf-8'))     # v2 cells (original mesh), anchors
    nm = json.load(open(os.path.join(M, 'escalation_navmesh.json'), encoding='utf-8'))
    geo = json.load(open(os.path.join(M, 'escalation_geometry.json'), encoding='utf-8'))
    cells = [c for c in v2['cells'] if not c.get('flags', {}).get('versus_only')]               # originals only (rerun-safe)
    n0 = len(cells); by_actor = {c['actor']: c['id'] for c in cells}
    jmax = v2['parameters'].get('jump_up_max_m') or 5.0
    # ---- 2. merge versus cells
    vs = json.load(open(os.path.join(VERSUS, mp, 'bot_nav.json'), encoding='utf-8'))
    def under_orig(p, up=1.5, drop=1.5):
        h = V2.find_cell(cells[:n0], p, up=up, drop=drop); return h[0] if h else None
    merged = {}
    for c in vs['cells']:
        if under_orig(c['centroid_gltf']) is None: merged[c['id']] = n0 + len(merged)
    for vid, nid in merged.items():
        c = dict(vs['cells'][vid]); c['id'] = nid; c['actor'] = 'versus_cell_%d' % vid
        c['flags'] = dict(c.get('flags') or {}, versus_only=True, blocked_at_start=False)
        edges = []
        for e in c.get('edges') or []:
            nbs = [{'cell': merged[nb['cell']]} for nb in e.get('neighbors') or [] if nb.get('cell') in merged]
            edges.append(dict(e, neighbors=nbs))
        c['edges'] = edges; cells.append(c)
    # ---- 1. typed links from the reach specs
    loc_cache = {}
    def resolve(op):
        name = op.rsplit('.', 1)[-1]
        cls, p = obj(op)
        L = p.get('Location')
        pos = g(L) if L else None
        if name in by_actor: cid = by_actor[name]; pos = pos or cells[cid]['centroid_gltf']
        else:
            h = V2.find_cell(cells, pos, up=2.0, drop=34.0) if pos else None; cid = h[0] if h else None
        return cid, pos, cls, p
    links, seen, kinds, skipped = [], set(), Counter(), 0
    for pkg in PKGS[mp]:
        for (q_,) in DB.execute("select props from objects where package=? and class='TnReachSpec'", (pkg,)):
            q = json.loads(q_ or '{}'); fl = q.get('reachFlags') or 0
            if fl & (R_PROSCRIBED | R_PLAYERONLY) or (fl & R_FLY and not fl & ~R_FLY): skipped += 1; continue
            st, en = q.get('Start'), (q.get('End') or {}).get('Nav')
            if not st or not en: continue
            fa, pa, ca, sp = resolve(st); to, pb, cb, ep = resolve(en)
            if fa is None or to is None or fa == to or pa is None or pb is None: continue
            rise = pb[1] - pa[1]; span = math.hypot(pb[0] - pa[0], pb[2] - pa[2])
            special_actor = next((x for x in (ca, cb) if x and any(s in x for s in SPECIAL_CLS)), None)
            launch = {k: v for k, v in sp.items() if k in LAUNCH_KEYS} if special_actor == ca else {k: v for k, v in ep.items() if k in LAUNCH_KEYS}
            if fl & R_SPECIAL or special_actor: kind, ex = 'special', 'special'
            elif fl & R_JUMP: kind, ex = ('double_jump_up' if rise > jmax else 'jump_up'), 'jump'
            elif rise < -1.0: kind, ex = (('drop_down', 'fall') if span <= WALKOFF_M else ('UNKNOWN', 'UNKNOWN'))
            else: kind, ex = 'walk', 'walk'
            key = (fa, to, kind)
            if key in seen: continue
            seen.add(key); kinds[kind] += 1
            rec = OD([('kind', kind), ('executable_as', ex), ('from_cell', fa), ('to_cell', to), ('rise_m', round(rise, 2)), ('span_m', round(span, 2)),
                      ('from_gltf', pa), ('to_gltf', pb), ('forms', ['robot'] + (['vehicle'] if (q.get('CollisionRadius') or 0) / 100.0 >= V2.VEH_R else [])),
                      ('reach_start', st.rsplit('.', 1)[-1]), ('reach_start_class', ca), ('reach_end', en.rsplit('.', 1)[-1]), ('reach_end_class', cb),
                      ('reach_flags', fl)])
            if kind == 'special': rec['special_actor_class'] = special_actor; rec['launch'] = launch
            links.append(rec)
    # versus links among merged cells, and walk links merged <-> original
    for l in vs.get('links') or []:
        if l['from_cell'] in merged and l['to_cell'] in merged:
            links.append(OD([('kind', l['kind']), ('executable_as', 'jump' if 'jump' in l['kind'] else 'fall'), ('from_cell', merged[l['from_cell']]),
                             ('to_cell', merged[l['to_cell']]), ('rise_m', l.get('rise_m')), ('from_gltf', l['from_gltf']), ('to_gltf', l['to_gltf']),
                             ('forms', l.get('forms') or ['robot']), ('source', 'versus nav link (merged cells)')])); kinds['versus_' + l['kind']] += 1
    bridge = 0
    for vid, nid in merged.items():
        for e in vs['cells'][vid].get('edges') or []:
            for nb in e.get('neighbors') or []:
                if nb.get('cell') in merged: continue
                oc = under_orig(vs['cells'][nb['cell']]['centroid_gltf'])
                if oc is None: continue
                a_, b_ = cells[nid]['centroid_gltf'], cells[oc]['centroid_gltf']
                for f_, t_, pa, pb in ((nid, oc, a_, b_), (oc, nid, b_, a_)):
                    if (f_, t_, 'walk') in seen: continue
                    seen.add((f_, t_, 'walk')); bridge += 1
                    links.append(OD([('kind', 'walk'), ('executable_as', 'walk'), ('from_cell', f_), ('to_cell', t_), ('rise_m', round(pb[1] - pa[1], 2)),
                                     ('from_gltf', pa), ('to_gltf', pb), ('forms', ['robot']), ('source', 'merge bridge (versus cell edge -> original cell)')]))
    # anchors re-snapped over all cells (originals win: find_cell takes the highest; spawn points keep their authored anchor)
    anchors = []
    for a in v2['anchors']:
        if a.get('kind') == 'survival_spawn_point': anchors.append(a); continue
        h = V2.find_cell(cells, a['location_gltf']); anchors.append(dict(a, cell=h[0] if h else None, approach_cell=h[0] if h else None))
    # ---- 3. coverage: blocked cells removed, executable links only
    blocked = {c['id'] for c in cells if c['flags'].get('blocked_at_start')}
    fwd = defaultdict(set)
    for c in cells:
        if c['id'] in blocked: continue
        for e in c['edges']:
            for nb in e['neighbors']:
                if nb['cell'] not in blocked: fwd[c['id']].add(nb['cell']); fwd[nb['cell']].add(c['id'])
    for l in links:
        if l['executable_as'] in ('walk', 'fall', 'jump') and l['from_cell'] not in blocked and l['to_cell'] not in blocked: fwd[l['from_cell']].add(l['to_cell'])
    def reach(s0):
        out, st = {s0}, [s0]
        while st:
            v = st.pop()
            for w in fwd[v]:
                if w not in out: out.add(w); st.append(w)
        return out
    starts = [a for a in anchors if a.get('class') == 'TnTeamPlayerStart' or a.get('kind') == 'player_start']
    gens = []
    for gn in geo['generators']:
        h = V2.find_cell(cells, gn['location_gltf'], up=3.0, drop=8.0); gens.append((gn['generator'], h[0] if h else None))
    start_cells = {a['cell'] for a in starts if a.get('cell') is not None}
    from_starts = set().union(*[reach(c) for c in start_cells]) if start_cells else set()
    cov = json.load(open(os.path.join(M, 'escalation_nav_coverage.json'), encoding='utf-8'))
    pts = []
    for p in cov['points']:
        c = p.get('anchor_cell')
        r = reach(c) if c is not None and c not in blocked else set()
        pts.append(dict(p, v3_reaches_starts=bool(r & start_cells) if c is not None else None, v3_reached_from_starts=c in from_starts if c is not None else None,
                        v3_cell_blocked_at_start=c in blocked if c is not None else None))
    summ = OD([('cells_original', n0), ('cells_merged_versus_only', len(merged)), ('links', len(links)), ('link_kinds', dict(kinds)),
               ('merge_bridges', bridge), ('reach_specs_skipped', skipped),
               ('player_starts', len(starts)), ('player_starts_on_nav', sum(1 for a in starts if a.get('cell') is not None)),
               ('player_starts_on_blocked_cell', sum(1 for a in starts if a.get('cell') in blocked)),
               ('generators_reached_from_starts (blocked applied, executable links)', '%d / %d' % (sum(1 for _, c in gens if c in from_starts), len(gens))),
               ('generators_without_cell', [gname for gname, c in gens if c is None]),
               ('on_mesh_spawn_points', sum(1 for p in pts if p['on_nav_mesh'])),
               ('spawn_points_reaching_starts (blocked applied, executable)', sum(1 for p in pts if p['on_nav_mesh'] and p['v3_reaches_starts'])),
               ('spawn_points_reached_from_starts', sum(1 for p in pts if p['on_nav_mesh'] and p['v3_reached_from_starts'])),
               ('spawn_points_on_blocked_cells', sum(1 for p in pts if p['on_nav_mesh'] and p['v3_cell_blocked_at_start'])),
               ('note', 'spawn points behind start-blocked cells become reachable when their generator opens them (escalation_nav_blockers.json)')])
    out = OD(v2)
    out['generated_by'] = 'AssetTools/work/playtest_20261023/escalation_bot_nav_v3.py'
    out['parameters'] = OD(v2['parameters'], links='typed from the cooked TnReachSpec (see generated_by docstring); walk-off limit %.1f m' % WALKOFF_M,
                          merge='overlay_20261023g versus cells with no original cell under them (flags.versus_only)')
    out['stats'] = OD(v2['stats'], cells=len(cells), versus_only_cells=len(merged), links=len(links))
    out['cells'] = cells; out['links'] = links; out['anchors'] = anchors
    json.dump(out, open(os.path.join(M, 'bot_nav_escalation.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    json.dump(OD([('map', mp), ('summary_v2', cov['summary']), ('summary_v3', summ), ('generators', [{'generator': a, 'cell': b, 'reached_from_starts': b in from_starts} for a, b in gens]),
                  ('points', pts)]), open(os.path.join(M, 'escalation_nav_coverage.json'), 'w', encoding='utf-8'), indent=1)
    print(mp, json.dumps(summ))
    big = sorted((l for l in links if l.get('span_m') and l['span_m'] > 20), key=lambda l: -l['span_m'])[:5]
    for l in big: print('   wide link', l['kind'], l['from_cell'], '->', l['to_cell'], 'span', l['span_m'], 'rise', l['rise_m'], l['reach_start_class'], '->', l['reach_end_class'], 'flags', l['reach_flags'])

if __name__ == '__main__':
    main(sys.argv[1])
