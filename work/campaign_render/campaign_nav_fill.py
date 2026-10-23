"""Fill a campaign chapter's off-nav start / checkpoint areas from the collision (Integration 2026-10-23, A1_IAC: the level start and
three checkpoints have no original NavigationCell below them). Cells from AssetTools' reconstructed nav (bot_nav.py on the chapter pawn
collision, seeded at the off-nav anchors' floor) are merged where no original cell covers them, flagged flags.campaign_fill and appended
after the original ids (unchanged), joined to the original cells by walk links where their edges meet. A checkpoint that resolved to a cell
far below (airborne) keeps that drop as a typed link: drop_down, executable_as 'fall', flag airborne_drop. RE decides whether the
opening is scripted (matinee / flight); where the original drives the squad, the fill is not meant to be used.

    python campaign_nav_fill.py <CH> prepare     -> out/campaign_render/<CH>/_fill_input/{collision_pawn.glb, physics.json, gameplay.json}
    (run bot_nav.py <CH> --overlay <_fill_input> --out <_fill_out> with WFC_VS_ROOT = the campaign VerticalSlice, under run_bounded)
    python campaign_nav_fill.py <CH> merge       -> merges <_fill_out>/bot_nav.json into out/campaign_render/<CH>/bot_nav.json
"""
import json, math, os, shutil, sys
from collections import Counter, OrderedDict as OD, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'work', 'playtest_20261023')); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
import escalation_bot_nav as V2  # noqa: E402
import lower_nav_cells as LNC  # noqa: E402
import campaign_render as CR  # noqa: E402
CVS = os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice', 'Maps')
DEEP = 400.0
FILL_RADIUS_M = 60.0

def floor_below(V, grid, p, drop=DEEP):
    best = None
    for gx in (math.floor(p[0] / LNC.G),):
        cand = grid.get((int(gx), int(math.floor(p[2] / LNC.G))))
        if not cand: return None
        import numpy as np
        for i in cand:
            y = LNC.bary_y(V[i], np.array([p[0]]), np.array([p[2]]))[0]
            if not np.isnan(y) and p[1] - drop <= y <= p[1] + 0.3 and (best is None or y > best): best = y
    return best

def prepare(ch):
    R = os.path.join(CR.OUTR, ch); D = os.path.join(CVS, ch); I = os.path.join(R, '_fill_input'); os.makedirs(I, exist_ok=True)
    nav = json.load(open(os.path.join(R, 'bot_nav.json'), encoding='utf-8'))
    V, grid = LNC.grid_of([os.path.join(D, 'collision_pawn.glb')])
    seeds = []
    # anchors on a lift (within 30 m of a MoverPathNode; RE: A1's start is on the intro elevator) are not filled from the static
    # collision: they ride the mover (on_mover + the mover path nodes as anchors with their Base)
    import sqlite3
    db = sqlite3.connect(os.path.join(AT, 'manifests', 'authored.db')); inv = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
    levels = CR.chapter_levels(ch); ph_ = ','.join('?' * len(levels)); movers = []
    for (op,) in inv.execute("select opath from exports where package in (%s) and class='MoverPathNode'" % ph_, levels):
        if op.count('.') != 3: continue
        r = db.execute('select props from objects where opath=?', (op,)).fetchone(); q = json.loads((r[0] if r else None) or '{}'); L = q.get('Location')
        if L: movers.append({'actor': op.rsplit('.', 1)[-1], 'class': 'MoverPathNode', 'kind': 'mover_path_node', 'level': op.split('.')[0],
                             'location_gltf': [round(0.01 * L['X'], 4), round(0.01 * L['Z'], 4), round(0.01 * L['Y'], 4)], 'cell': None,
                             'approach_cell': None, 'base': q.get('Base')})
    have = {a['actor'] for a in nav['anchors']}
    for m in movers:
        if m['actor'] not in have: nav['anchors'].append(m)
    json.dump(nav, open(os.path.join(R, 'bot_nav.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    for a in nav['anchors']:
        if a['kind'] in ('player_start', 'checkpoint') and a['cell'] is None and any(
                math.dist(a['location_gltf'], m['location_gltf']) < 30.0 for m in movers):
            a['on_mover'] = True
    json.dump(nav, open(os.path.join(R, 'bot_nav.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    for a in nav['anchors']:
        if a.get('on_mover'): continue
        if a['kind'] in ('player_start', 'checkpoint') and (a['cell'] is None or a.get('airborne_drop_m')):
            f = floor_below(V, grid, a['location_gltf'])
            seeds.append(OD([('actor', a['actor']), ('class', a['class']), ('kind', a['kind']), ('anchor_location_gltf', a['location_gltf']),
                             ('floor_y', round(f, 3) if f is not None else None),
                             ('location_gltf', [a['location_gltf'][0], round(f + 0.3, 3), a['location_gltf'][2]] if f is not None else None)]))
    for f in ('collision_pawn.glb', 'physics.json'): shutil.copyfile(os.path.join(D, f), os.path.join(I, f))
    # ONE bot_nav run per seed (A3_COR: two starts 1.8 km apart made a single run's working set exceed the 6 GB cap): <I>_<k>/gameplay.json
    # holds that seed only (collision / physics fall back to the chapter's VerticalSlice dir, the same files), output <R>/_fill_out_<k>.
    # The shared <I>/gameplay.json gets no starts, so run_chapters.sh's single fill run is skipped; merge() reads every _fill_out_<k>.
    import glob, subprocess
    for old in glob.glob(os.path.join(R, '_fill_out_*')): shutil.rmtree(old, ignore_errors=True)
    g0 = {'map': ch, 'note': 'synthetic; the fill runs per seed in _fill_input_<k> (campaign_nav_fill.py)', 'player_starts': [], 'pickups': [], 'objectives': {}}
    json.dump(g0, open(os.path.join(I, 'gameplay.json'), 'w', encoding='utf-8'), indent=1)
    runs = []
    for k, s in enumerate(x for x in seeds if x['location_gltf']):
        Ik = os.path.join(R, '_fill_input_%d' % k); Ok = os.path.join(R, '_fill_out_%d' % k); os.makedirs(Ik, exist_ok=True); os.makedirs(Ok, exist_ok=True)
        json.dump({'map': ch, 'note': 'synthetic: one off-nav seed (campaign_nav_fill.py)', 'pickups': [], 'objectives': {},
                   'player_starts': [{'actor': s['actor'], 'class': s['class'], 'location_gltf': s['location_gltf']}]},
                  open(os.path.join(Ik, 'gameplay.json'), 'w', encoding='utf-8'), indent=1)
        log = os.path.join(R, '_fill_out_%d.log' % k)
        r = subprocess.run([sys.executable, os.path.join(AT, 'scripts', 'wfc', 'run_bounded.py'), '--cap-gb', '6', '--log', log,
                            os.path.join(AT, 'scripts', 'wfc', 'bot_nav.py'), ch, '--overlay', Ik, '--out', Ok], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', WFC_VS_ROOT=os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice')))
        runs.append(OD([('seed', s['actor']), ('rc', r.returncode), ('out', os.path.relpath(Ok, R).replace(os.sep, '/'))]))
    json.dump({'seeds': seeds, 'runs': runs}, open(os.path.join(I, 'fill_seeds.json'), 'w', encoding='utf-8'), indent=1)
    for s in seeds: print(s['actor'], s['kind'], 'anchor y', s['anchor_location_gltf'][1], 'floor', s['floor_y'])
    print('fill runs', runs)

def merge(ch):
    R = os.path.join(CR.OUTR, ch); I = os.path.join(R, '_fill_input'); FO = os.path.join(R, '_fill_out')
    nav = json.load(open(os.path.join(R, 'bot_nav.json'), encoding='utf-8'))
    # every fill output (per-seed _fill_out_<k>, and the older single _fill_out) combined, ids renumbered: cells, edge neighbours, links
    import glob
    fill = {'cells': [], 'links': []}
    for fp in [os.path.join(FO, 'bot_nav.json')] + sorted(glob.glob(os.path.join(R, '_fill_out_*', 'bot_nav.json'))):
        if not os.path.exists(fp) or (fp.startswith(FO + os.sep) and glob.glob(os.path.join(R, '_fill_out_*', 'bot_nav.json'))): continue
        f = json.load(open(fp, encoding='utf-8')); off = len(fill['cells'])
        for c in f['cells']:
            c = dict(c, id=c['id'] + off)
            c['edges'] = [dict(e, neighbors=[dict(nb, cell=nb['cell'] + off) for nb in e.get('neighbors') or [] if nb.get('cell') is not None])
                          for e in c.get('edges') or []]
            fill['cells'].append(c)
        for l in f.get('links') or []:
            fill['links'].append(dict(l, from_cell=l['from_cell'] + off, to_cell=l['to_cell'] + off))
    cells = [c for c in nav['cells'] if not ((c.get('flags') or {}).get('campaign_fill') or (c.get('flags') or {}).get('mover_attached'))]; n0 = len(cells)
    links = [l for l in nav['links'] if l.get('source') not in ('campaign fill', 'campaign fill bridge', 'airborne drop', 'mover attach')]
    def under_orig(p):
        h = V2.find_cell(cells[:n0], p, up=1.0, drop=1.0); return h[0] if h else None
    # the fill covers the off-nav start / checkpoint AREAS only: cells within FILL_RADIUS_M (horizontal) of a seed (A2_KON: unbounded, the
    # per-seed runs flooded 7,321 cells over a chapter with 2,170 original cells)
    sp = os.path.join(I, 'fill_seeds.json')
    seeds = [x['location_gltf'] for x in (json.load(open(sp, encoding='utf-8')).get('seeds') or []) if x.get('location_gltf')] if os.path.exists(sp) else []
    near = lambda p: any(math.hypot(p[0] - q[0], p[2] - q[2]) <= FILL_RADIUS_M and abs(p[1] - q[1]) <= 15.0 for q in seeds)
    merged = {}
    for c in fill['cells']:
        if near(c['centroid_gltf']) and under_orig(c['centroid_gltf']) is None: merged[c['id']] = n0 + len(merged)
    for fid, nid in merged.items():
        c = dict(fill['cells'][fid]); c['id'] = nid; c['actor'] = 'campaign_fill_%d' % fid
        c['flags'] = dict(c.get('flags') or {}, campaign_fill=True, blocked_at_start=False)
        c['edges'] = [dict(e, neighbors=[{'cell': merged[nb['cell']]} for nb in e.get('neighbors') or [] if nb.get('cell') in merged]) for e in c.get('edges') or []]
        cells.append(c)
    kinds = Counter()
    for l in fill.get('links') or []:
        if l['from_cell'] in merged and l['to_cell'] in merged:
            links.append(OD([('kind', l['kind']), ('executable_as', 'jump' if 'jump' in l['kind'] else 'fall'), ('from_cell', merged[l['from_cell']]),
                             ('to_cell', merged[l['to_cell']]), ('rise_m', l.get('rise_m')), ('from_gltf', l['from_gltf']), ('to_gltf', l['to_gltf']),
                             ('forms', l.get('forms') or ['robot']), ('source', 'campaign fill')])); kinds['fill_' + l['kind']] += 1
    seen = {(l['from_cell'], l['to_cell'], l['kind']) for l in links}; bridges = 0
    for fid, nid in merged.items():
        for e in fill['cells'][fid].get('edges') or []:
            for nb in e.get('neighbors') or []:
                if nb.get('cell') in merged: continue
                oc = under_orig(fill['cells'][nb['cell']]['centroid_gltf'])
                if oc is None: continue
                for f_, t_ in ((nid, oc), (oc, nid)):
                    if (f_, t_, 'walk') in seen: continue
                    seen.add((f_, t_, 'walk')); bridges += 1
                    a_, b_ = cells[f_]['centroid_gltf'], cells[t_]['centroid_gltf']
                    links.append(OD([('kind', 'walk'), ('executable_as', 'walk'), ('from_cell', f_), ('to_cell', t_), ('rise_m', round(b_[1] - a_[1], 2)),
                                     ('from_gltf', a_), ('to_gltf', b_), ('forms', ['robot']), ('source', 'campaign fill bridge')]))
    # mover-attached cells (Integration / RE 2026-10-23: A1's start is the intro lift): one 2 x 2 m cell per MoverPathNode at its floor
    # (node height - 1.75 m, the measured pawn-centre offset, PROVISIONAL), flags.mover_attached + mover_base (the InterpActor it rides),
    # joined to the nearest static cells within 10 m by 'special' links (executable_as special: Gameplay's lift handling)
    statics = len(cells); nmov = 0
    for a in nav['anchors']:
        if a.get('kind') != 'mover_path_node' or not a.get('location_gltf'): continue
        x, y, z = a['location_gltf']; y -= 1.75; h = 1.0
        V = [[x - h, y, z - h], [x + h, y, z - h], [x + h, y, z + h], [x - h, y, z + h]]
        cid = len(cells)
        cells.append(OD([('id', cid), ('actor', a['actor']), ('vertices_gltf', V), ('centroid_gltf', [x, y, z]), ('area_m2', 4.0),
                         ('height_range_m', [round(y, 3), round(y, 3)]), ('clearance_m', 1.0), ('clearance_max_m', 1.0), ('headroom_m', 4.0),
                         ('flags', OD([('vehicle_capable', False), ('mover_attached', True), ('mover_base', a.get('base')), ('blocked_at_start', False)])),
                         ('edges', [OD([('start', V[k]), ('end', V[(k + 1) % 4]), ('normal', [0, 0, 0]), ('neighbors', []), ('border', True)]) for k in range(4)])]))
        a['cell'] = a['approach_cell'] = cid; nmov += 1
        near = sorted((math.hypot(c['centroid_gltf'][0] - x, c['centroid_gltf'][2] - z), c['id']) for c in cells[:statics]
                      if abs(c['centroid_gltf'][1] - y) < 6.0 and math.hypot(c['centroid_gltf'][0] - x, c['centroid_gltf'][2] - z) <= 10.0)[:2]
        for d, oc in near:
            for f_, t_ in ((cid, oc), (oc, cid)):
                links.append(OD([('kind', 'special'), ('executable_as', 'special'), ('from_cell', f_), ('to_cell', t_),
                                 ('rise_m', round(cells[t_]['centroid_gltf'][1] - cells[f_]['centroid_gltf'][1], 2)),
                                 ('from_gltf', cells[f_]['centroid_gltf']), ('to_gltf', cells[t_]['centroid_gltf']), ('forms', ['robot']),
                                 ('special_actor_class', 'MoverPathNode'), ('mover_base', a.get('base')), ('source', 'mover attach')]))
    for a in nav['anchors']:
        if a.get('on_mover'):
            m = min(((math.dist(a['location_gltf'], c['centroid_gltf']), c['id']) for c in cells[statics:]), default=None)
            if m: a['cell'] = a['approach_cell'] = m[1]; a['resolved_by'] = 'mover-attached cell'
    # re-anchor the off-nav start / checkpoints over the merged cells; airborne drops become typed links
    air = 0
    for a in nav['anchors']:
        if a['kind'] not in ('player_start', 'checkpoint'): continue
        if a['cell'] is None and not a.get('on_mover'):
            h = V2.find_cell(cells, a['location_gltf'], up=2.0, drop=DEEP)
            if h: a['cell'] = a['approach_cell'] = h[0]; a['resolved_by'] = 'campaign fill' if h[0] >= n0 else 'original cell below'
        if a.get('airborne_drop_m') and a['cell'] is not None:
            top = V2.find_cell(cells[n0:], a['location_gltf'], up=2.0, drop=8.0) if len(cells) > n0 else None
            if top and top[0] != a['cell']:
                links.append(OD([('kind', 'drop_down'), ('executable_as', 'fall'), ('from_cell', top[0]), ('to_cell', a['cell']),
                                 ('rise_m', -a['airborne_drop_m']), ('from_gltf', a['location_gltf']), ('to_gltf', cells[a['cell']]['centroid_gltf']),
                                 ('forms', ['robot']), ('airborne_drop', True), ('source', 'airborne drop')])); air += 1
    nav['cells'] = cells; nav['links'] = links
    nav['stats'] = OD(nav['stats'], cells=len(cells), campaign_fill_cells=len(merged), mover_attached_cells=nmov, links=len(links))
    nav['parameters']['campaign_fill'] = ('cells of bot_nav.py on the chapter collision seeded at the off-nav start / checkpoints, where no original '
                                          'cell covers them (flags.campaign_fill, ids after the originals); RE decides where the opening is scripted')
    json.dump(nav, open(os.path.join(R, 'bot_nav.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    pid, npieces = V2.pieces(cells, links)
    main_piece = Counter(pid.values()).most_common(1)[0][0]
    rows = [(a['actor'], a.get('tag'), a['cell'], pid.get(a['cell']) == main_piece if a['cell'] is not None else None, a.get('resolved_by'))
            for a in nav['anchors'] if a['kind'] in ('player_start', 'checkpoint')]
    rep = OD([('chapter', ch), ('mover_attached_cells', nmov), ('fill_cells_merged', len(merged)), ('fill_cells_total', len(fill['cells'])), ('bridges', bridges),
              ('fill_links', dict(kinds)), ('airborne_drop_links', air), ('pieces', npieces),
              ('start_and_checkpoints_on_nav', '%d / %d' % (sum(1 for r in rows if r[2] is not None), len(rows))),
              ('in_main_piece', '%d / %d' % (sum(1 for r in rows if r[3]), len(rows))),
              ('off_nav_or_outside_main', [r for r in rows if not r[3]])])
    json.dump(rep, open(os.path.join(R, 'nav_fill_report.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(rep)[:1500])

if __name__ == '__main__':
    {'prepare': prepare, 'merge': merge}[sys.argv[2]](sys.argv[1])
