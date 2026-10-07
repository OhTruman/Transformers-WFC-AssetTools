"""Spawn capacity per MP map for large offline matches -> manifests/maps/spawn_capacity.json

  python map_spawn_capacity.py [participants=33]

Authored data only (gameplay.json: TnTeamPlayerStart / TnFreeForAllPlayerStart, TnSpawnCluster team assignment) plus bot_nav
coverage (anchor on nav / approach cell). The original game capped versus at MaxPlayers=10 (Xe-TransGame.ini), so any count
above that is a PC ADAPTATION: this manifest only reports how far the authored spawn points go and which fallback pools exist.
"""
import json, os, sys, time, glob
from collections import Counter, OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import VS  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 33

def main():
    maps = OD()
    for D in sorted(glob.glob(os.path.join(VS, 'Maps', 'MP_*'))):
        M = os.path.basename(D)
        g = json.load(open(os.path.join(D, 'gameplay.json'), encoding='utf-8'))
        nav_p = os.path.join(D, 'bot_nav.json')
        nav = {a['actor']: a for a in json.load(open(nav_p, encoding='utf-8'))['anchors']} if os.path.exists(nav_p) else {}
        team_of = {}
        for c in g.get('spawn_clusters') or []:
            for m in c.get('members') or []:
                for t in c.get('teams') or []: team_of[m if isinstance(m, str) else m.get('actor')] = t
        starts = g.get('player_starts') or []
        per_team = Counter(); ffa = 0; on_nav = 0; one_way = 0
        for p in starts:
            a = nav.get(p['actor']) or {}
            if a.get('approach_cell') is not None: on_nav += 1
            if a.get('one_way_into_core'): one_way += 1
            if p['class'] == 'TnFreeForAllPlayerStart': ffa += 1
            else: per_team[team_of.get(p['actor'], (g.get('validation') or {}).get('team_split') and 'unclustered')] += 1
        team_counts = dict(per_team) or (g.get('validation') or {}).get('team_split') or {}
        per_side = N // 2 + N % 2
        sides = {k: v for k, v in team_counts.items() if k and k.startswith('TNTG_')}
        maps[M] = OD([
            ('team_starts', team_counts), ('ffa_starts', ffa), ('spawn_clusters', len(g.get('spawn_clusters') or [])),
            ('starts_with_nav_approach', on_nav), ('starts_total', len(starts)), ('one_way_spawn_starts', one_way),
            ('team_mode_ok_for_%d' % N, bool(sides) and len(sides) >= 2 and min(sides.values()) >= per_side),
            ('ffa_ok_for_%d' % N, ffa >= N),
            ('ffa_fallback_pool (FFA + team starts)', ffa + sum(team_counts.values())),
        ])
    out = OD([('generated_by', 'AssetTools/scripts/wfc/map_spawn_capacity.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('participants', N),
              ('original_limit', 'MaxPlayers=10 (Xe-TransGame.ini, versus); 4 on Escalation (co-op). Larger matches are a PC ADAPTATION'),
              ('rule_note', 'team mode needs >= ceil(N/2) team starts per side for a simultaneous first spawn; FFA needs N FFA starts '
                            'or a fallback pool (team starts are authored spawn points too) / staggered spawning'),
              ('maps', maps)])
    json.dump(out, open(os.path.join(AT, 'manifests', 'maps', 'spawn_capacity.json'), 'w', encoding='utf-8'), indent=1)
    for M, x in maps.items(): print(M, json.dumps(x))

if __name__ == '__main__':
    main()
