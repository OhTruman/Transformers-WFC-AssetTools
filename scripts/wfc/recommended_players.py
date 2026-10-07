"""Map-aware recommended match sizes for Extended matches (PC ADAPTATION, user decision 2026-10-07) -> manifests/maps/recommended_players.json

  python recommended_players.py [--busy 2.5] [--zone-weight 0.75]

The original versus game capped matches at MaxPlayers=10 (5 v 5). For larger offline matches each versus map gets a default
Bot Settings size derived from authored data, tunable through the parameters below (all inputs written per map):

  A        walkable area of the largest connected bot_nav piece (m^2)             [bot_nav.json]
  Z        spawn clusters (TnSpawnCluster) = authored combat / spawn zones          [gameplay.json]
  S_team   authored team starts on the smaller side; S_ffa authored FFA starts    [spawn_capacity.json]
  d_ref    original density = 10 players / mean A of the larger half of the versus maps
  area_term   = busy * d_ref * A / 2                (players per side at original density x busy factor)
  zone_term   = zone_weight * Z                     (players per side the authored zone layout supports)
  perSide     = clamp(round((area_term + zone_term) / 2), 5, min(32, floor(S_team / 2)))   (human included)
  ffa         = clamp(round(1.5 * perSide), 8, min(64, round(1.5 * S_ffa)))
Spawn caps keep at least half of the authored starts free for the spawn picker. Users can still raise to 32 v 32 / FFA 64.
"""
import glob, json, os, sys, time
from collections import OrderedDict as OD, defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import VS  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
BUSY = float(sys.argv[sys.argv.index('--busy') + 1]) if '--busy' in sys.argv else 2.5
ZW = float(sys.argv[sys.argv.index('--zone-weight') + 1]) if '--zone-weight' in sys.argv else 0.75

def largest_piece_area(nav):
    cells = nav['cells']; und = defaultdict(set)
    for c in cells:
        for e in c['edges']:
            for nb in e['neighbors']: und[c['id']].add(nb['cell']); und[nb['cell']].add(c['id'])
    seen, best = set(), 0.0
    for c in cells:
        if c['id'] in seen: continue
        P = {c['id']}; dq = deque([c['id']])
        while dq:
            u = dq.popleft()
            for v in und[u]:
                if v not in P: P.add(v); dq.append(v)
        seen |= P; best = max(best, sum(cells[i]['area_m2'] for i in P))
    return best

def main():
    cap = json.load(open(os.path.join(AT, 'manifests', 'maps', 'spawn_capacity.json'), encoding='utf-8'))['maps']
    rows = OD()
    for D in sorted(glob.glob(os.path.join(VS, 'Maps', 'MP_*'))):
        M = os.path.basename(D)
        if M.startswith('MP_ESC'): continue     # Escalation is 4-player co-op, not a versus map
        g = json.load(open(os.path.join(D, 'gameplay.json'), encoding='utf-8'))
        nav = json.load(open(os.path.join(D, 'bot_nav.json'), encoding='utf-8'))
        sides = [v for k, v in cap[M]['team_starts'].items() if k.startswith('TNTG')]
        rows[M] = {'A': largest_piece_area(nav), 'Z': len(g.get('spawn_clusters') or []), 'S_team': min(sides) if sides else 0,
                   'S_ffa': cap[M]['ffa_starts'], 'info': g.get('map_info') or {}}
    big = sorted((r['A'] for r in rows.values()), reverse=True)[:max(1, len(rows) // 2)]
    d_ref = 10.0 / (sum(big) / len(big))
    maps = OD()
    for M, r in rows.items():
        area_term = BUSY * d_ref * r['A'] / 2
        zone_term = ZW * r['Z']
        cap_side = min(32, r['S_team'] // 2)
        per = max(5, min(cap_side, int(round((area_term + zone_term) / 2))))
        ffa = max(8, min(64, int(round(1.5 * r['S_ffa'])), int(round(1.5 * per))))
        info = r['info']
        key = str(info.get('MapId') or M)
        maps[key] = OD([
            ('map', info.get('MapFilename') or M), ('mapName', M),
            ('perSide', per), ('ffa', ffa), ('modes', OD()),
            ('inputs', OD([('walkable_area_m2_largest_piece', round(r['A'])), ('spawn_clusters', r['Z']),
                           ('team_starts_min_side', r['S_team']), ('ffa_starts', r['S_ffa'])])),
            ('terms', OD([('area_term', round(area_term, 2)), ('zone_term', round(zone_term, 2)), ('cap_per_side', cap_side),
                          ('cap_ffa', min(64, int(round(1.5 * r['S_ffa']))))])),
        ])
    out = OD([('generated_by', 'AssetTools/scripts/wfc/recommended_players.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('status', 'PC ADAPTATION (user decision 2026-10-07: map-aware Extended match size; original MaxPlayers=10)'),
              ('schema', {'key': 'MapId (string; gameplay.json map_info.MapId)', 'map': 'MapFilename', 'mapName': 'AssetTools map folder',
                          'perSide': 'recommended players per side incl. the human (team modes)', 'ffa': 'recommended FFA total incl. the human',
                          'modes': '{ModeTag: {perSide?, ffa?}} per-mode overrides; empty = same for every mode (no authored per-mode sizes)'}),
              ('parameters', OD([('busy_factor', BUSY), ('zone_weight', ZW), ('d_ref_players_per_m2', d_ref),
                                 ('d_ref_basis', '10 players / mean largest-piece area of the larger half of the versus maps')])),
              ('formula', 'perSide = clamp(round((busy*d_ref*A/2 + zone_weight*Z)/2), 5, min(32, floor(S_team/2))); '
                          'ffa = clamp(round(1.5*perSide), 8, min(64, round(1.5*S_ffa)))'),
              ('maps', maps)])
    json.dump(out, open(os.path.join(AT, 'manifests', 'maps', 'recommended_players.json'), 'w', encoding='utf-8'), indent=1)
    for k, v in maps.items():
        print('%-5s %-15s perSide %2d ffa %2d | A %6d Z %2d S_team %2d S_ffa %2d | area %.1f zone %.1f cap %d' % (
            k, v['mapName'], v['perSide'], v['ffa'], v['inputs']['walkable_area_m2_largest_piece'], v['inputs']['spawn_clusters'],
            v['inputs']['team_starts_min_side'], v['inputs']['ffa_starts'], v['terms']['area_term'], v['terms']['zone_term'], v['terms']['cap_per_side']))

if __name__ == '__main__':
    main()
