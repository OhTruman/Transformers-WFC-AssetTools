"""Campaign starts / walk-graph report (Integration 2026-10-17, backlog 5): per chapter, the starts vs_gameplay found (campaign player
starts + checkpoints), grounded vs airborne (vs_validate's ground check, reported only in campaign mode), the structure audit's walk
graph (area, starts on reachable floor) and pickups on reachable floor. Read only; writes
manifests/next_map/campaign_starts_report.json and prints a markdown table.

Triage of every start / pickup off the walk graph (Integration: real level data vs audit limits):
  airborne_by_design  start whose navigation reach specs are all reachFlags 2 (stock UE3 EReachSpecFlags R_FLY, flying-only paths;
                      PROVISIONAL: the enum is engine-native, not in the RE script decomp) -> real level data
  on_mover            a mover (InterpActor / StaticInterpActor / KActor ...) within 8 m horizontally and 0-30 m below -> audit limit:
                      the walk graph has no mover collision (lift / platform pose)
  no_floor_below      start with no collision layer within 30 m below its cell -> UNKNOWN (missing collision, streaming, or airborne)
  unclassified        none of the above -> the conservative walk rule (no jump / transform / vehicle) or a floor the flood
                      does not connect; needs a per-actor look

  python campaign_starts_report.py
"""
import json, math, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from campaign_summary import CHAPTERS, AT, VSR  # noqa: E402
import authored as A  # noqa: E402

def fly_only(M):
    """start / checkpoint actor -> True when every reach spec in its PathList is reachFlags 2 (R_FLY)"""
    out = {}
    for c in ('TnCampaignPlayerStart', 'Checkpoint'):
        for r in A.find(M + '%.TheWorld.PersistentLevel.%', c):
            fl = {((A.get(p) or {}).get('props') or {}).get('reachFlags') for p in (r['props'] or {}).get('PathList') or []}
            out[r['opath'].rsplit('.', 1)[-1]] = fl == {2}
    return out

def triage(M, g, ps):
    props = json.load(open(os.path.join(VSR, 'Maps', M, 'props.json'), encoding='utf-8'))['props']
    movers = [(p['class'], p['actor'], p['gltf_matrix'][12:15]) for p in props if p['class'] != 'StaticMeshCollectionActor' and p.get('gltf_matrix')]
    fly = fly_only(M); diag = {d['actor']: d for d in ps.get('starts_off_walk_graph_diagnosis') or []}
    off_starts = set(ps.get('starts_without_floor_below') or []) | set(diag)
    off_picks = set(((ps.get('placement_checks') or {}).get('pickups') or {}).get('not_on_walk_graph') or [])
    items = [('start', s) for s in g.get('player_starts') or [] if s['actor'] in off_starts]
    items += [('pickup', p) for p in g.get('pickups') or [] if isinstance(p, dict) and p.get('actor') in off_picks]
    out = []
    for kind, x in items:
        L = x['location_gltf']
        mv = sorted((math.hypot(t[0] - L[0], t[2] - L[2]), c, a, round(t[1] - L[1], 1)) for c, a, t in movers
                    if math.hypot(t[0] - L[0], t[2] - L[2]) < 8 and -30 < t[1] - L[1] < 3)
        below = [q - L[1] for q in (diag.get(x['actor']) or {}).get('collision_layers_here', [])]
        if kind == 'start' and fly.get(x['actor']): cat = 'airborne_by_design'
        elif mv: cat = 'on_mover'
        elif kind == 'start' and not any(-30 < d <= 0 for d in below): cat = 'no_floor_below'
        else: cat = 'unclassified'
        out.append({'kind': kind, 'actor': x['actor'], 'class': x.get('class') or x.get('start_kind'), 'sublevel': x.get('sublevel'),
                    'category': cat, 'mover': {'class': mv[0][1], 'actor': mv[0][2], 'dy_m': mv[0][3]} if mv else None})
    return out

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
        n = d.get('player_starts', 0); gr = d.get('grounded', 0); tri = triage(M, g, ps)
        rows.append({'map': M, 'starts': len(kinds), 'campaign_player_starts': kinds.count('campaign_player_start'),
                     'checkpoints': kinds.count('checkpoint'),
                     'ground_check': {'checked': n, 'grounded': gr, 'airborne': n - gr,
                                      'grounded_on_collision_only': d.get('grounded_on_collision_only'), 'median_drop_m': d.get('median_drop_m')},
                     'starts_on_reachable_floor': ps.get('starts_on_reachable_floor'), 'starts_without_floor_below': ps.get('starts_without_floor_below'),
                     'walk_graph_area_m2': ps.get('walk_graph_area_m2'), 'connected_from_any_start': ps.get('connected_from_any_start'),
                     'pickups': pk.get('count'), 'pickups_on_reachable_floor': pk.get('on_walkable_reachable_floor'),
                     'pickups_not_on_walk_graph': pk.get('not_on_walk_graph'), 'structure_audit': (sa.get('verdict') or {}).get('status')
                     if isinstance(sa.get('verdict'), dict) else sa.get('status'),
                     'off_walk_graph_triage': {k: dict(Counter(t['category'] for t in tri if t['kind'] == k)) for k in ('start', 'pickup')},
                     'off_walk_graph': tri})
    out = os.path.join(AT, 'manifests', 'next_map', 'campaign_starts_report.json')
    json.dump({'generated_by': 'AssetTools/scripts/wfc/campaign_starts_report.py', 'chapters': rows}, open(out, 'w', encoding='utf-8'), indent=1)
    print('| chapter | starts (campaign + checkpoint) | ground check grounded / airborne | starts on reachable floor | walk graph m2 | pickups on reachable floor | audit |')
    print('|---|---|---|---|---|---|---|')
    for r in rows:
        print('| %s | %d (%d + %d) | %d / %d | %s / %d | %s | %s / %s | %s |' % (
            r['map'], r['starts'], r['campaign_player_starts'], r['checkpoints'], r['ground_check']['grounded'], r['ground_check']['airborne'],
            r['starts_on_reachable_floor'], r['starts'], '{:,.0f}'.format(r['walk_graph_area_m2'] or 0), r['pickups_on_reachable_floor'], r['pickups'],
            r['structure_audit']))
    for r in rows:
        print(r['map'], json.dumps(r['off_walk_graph_triage']))
    print(out)

if __name__ == '__main__':
    main()
