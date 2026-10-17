"""Campaign starts / walk-graph report (Integration 2026-10-17, backlog 5): per chapter, the starts vs_gameplay found (campaign player
starts + checkpoints), grounded vs airborne (vs_validate's ground check, reported only in campaign mode), the structure audit's walk
graph (area, starts on reachable floor) and pickups on reachable floor. Read only; writes
manifests/next_map/campaign_starts_report.json and prints a markdown table.

  python campaign_starts_report.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from campaign_summary import CHAPTERS, AT, VSR  # noqa: E402

def main():
    rows = []
    for M in CHAPTERS:
        g = json.load(open(os.path.join(VSR, 'Maps', M, 'gameplay.json'), encoding='utf-8'))
        kinds = [s.get('start_kind') for s in g.get('player_starts') or []]
        val = json.load(open(os.path.join(AT, 'manifests', 'next_map', M + '_validation.json'), encoding='utf-8'))
        chk = next((c for c in val['checks'] if c['check'].startswith('player starts have ground')), {})
        d = chk.get('detail') or {}
        sa = json.load(open(os.path.join(AT, 'manifests', 'maps', M, 'structure_audit.json'), encoding='utf-8'))
        ps = sa.get('playable_space') or {}; pk = (ps.get('placement_checks') or {}).get('pickups') or {}
        n = d.get('player_starts', 0); gr = d.get('grounded', 0)
        rows.append({'map': M, 'starts': len(kinds), 'campaign_player_starts': kinds.count('campaign_player_start'),
                     'checkpoints': kinds.count('checkpoint'),
                     'ground_check': {'checked': n, 'grounded': gr, 'airborne': n - gr,
                                      'grounded_on_collision_only': d.get('grounded_on_collision_only'), 'median_drop_m': d.get('median_drop_m')},
                     'starts_on_reachable_floor': ps.get('starts_on_reachable_floor'), 'starts_without_floor_below': ps.get('starts_without_floor_below'),
                     'walk_graph_area_m2': ps.get('walk_graph_area_m2'), 'connected_from_any_start': ps.get('connected_from_any_start'),
                     'pickups': pk.get('count'), 'pickups_on_reachable_floor': pk.get('on_walkable_reachable_floor'),
                     'pickups_not_on_walk_graph': pk.get('not_on_walk_graph'), 'structure_audit': (sa.get('verdict') or {}).get('status')
                     if isinstance(sa.get('verdict'), dict) else sa.get('status')})
    out = os.path.join(AT, 'manifests', 'next_map', 'campaign_starts_report.json')
    json.dump({'generated_by': 'AssetTools/scripts/wfc/campaign_starts_report.py', 'chapters': rows}, open(out, 'w', encoding='utf-8'), indent=1)
    print('| chapter | starts (campaign + checkpoint) | ground check grounded / airborne | starts on reachable floor | walk graph m2 | pickups on reachable floor | audit |')
    print('|---|---|---|---|---|---|---|')
    for r in rows:
        print('| %s | %d (%d + %d) | %d / %d | %s / %d | %s | %s / %s | %s |' % (
            r['map'], r['starts'], r['campaign_player_starts'], r['checkpoints'], r['ground_check']['grounded'], r['ground_check']['airborne'],
            r['starts_on_reachable_floor'], r['starts'], '{:,.0f}'.format(r['walk_graph_area_m2'] or 0), r['pickups_on_reachable_floor'], r['pickups'],
            r['structure_audit']))
    print(out)

if __name__ == '__main__':
    main()
