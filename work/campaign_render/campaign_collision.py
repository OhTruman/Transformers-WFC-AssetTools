"""Campaign collision + nav inputs for Gameplay's runtime (Integration 2026-10-23), per chapter, beside the render data.

    python campaign_collision.py <CH>

Per sublevel (out/campaign_render/<CH>/<dir>/, dir = the level name without _m):
  collision_pawn.glb / collision_weapon.glb  the chapter files' nodes of that level: BSP by its BSPCollision_<level> node name; volumes by
                      physics.json volumes (actor + sublevel; a name repeated across levels is matched by its first vertex); props by
                      (actor, mesh, gltf matrix) against physics.json props. No-loss check: every chapter node lands in exactly one level
  physics.json        the chapter physics.json filtered to that level (meshes: only those the level's props use; chapter-wide settings as is)
  gameplay.json       the persistent unit only: the WHOLE chapter gameplay.json (the World reads start points / pickups / map state
                      from the map dir)
Per chapter (out/campaign_render/<CH>/):
  navigation.json     the chapter's path nodes + reach specs (copy of the campaign VerticalSlice navigation.json)
  navmesh.json        the ORIGINAL cooked NavigationCell mesh + TnTacticalPathNode / PathNode (escalation_data.navmesh, the
                      escalation_navmesh.json schema: bot_nav cell schema + original actor ids, blocked_at_start, setup toggles)
Read-only on every input.
"""
import json, os, shutil, sys
from collections import Counter, OrderedDict as OD, defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc')); sys.path.insert(0, HERE)
from vs_common import GLB, read_glb, accessor  # noqa: E402
import campaign_render as CR  # noqa: E402
CVS = os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice', 'Maps')

def mkey(m): return tuple(np.round(np.array(m, float), 3)) if m else None

def main(ch):
    D = os.path.join(CVS, ch); R = os.path.join(CR.OUTR, ch); levels = CR.chapter_levels(ch)
    ph = json.load(open(os.path.join(D, 'physics.json'), encoding='utf-8'))
    prop_lv = defaultdict(set)
    for p in ph['props']: prop_lv[(p['actor'], p['mesh'], mkey(p.get('gltf_matrix')))].add(p['sublevel'])
    vol_lv = defaultdict(list)
    for v in ph['volumes']: vol_lv[v['actor']].append(v)
    split = {}
    for gname in ('collision_pawn.glb', 'collision_weapon.glb'):
        if os.path.exists(os.path.join(D, gname)): split[gname] = split_glb(D, R, ch, levels, gname, prop_lv, vol_lv)
    why = split['collision_pawn.glb']['why']; assign = split['collision_pawn.glb']['assign']
    out = {}
    for lv in levels:
        od = os.path.join(R, CR.outname(lv))
        if not os.path.isdir(od): continue
        sp = CR.filt(ph, lv, levels)
        used = {p['mesh'] for p in sp.get('props') or []}
        sp['meshes'] = {k: v for k, v in (ph.get('meshes') or {}).items() if k in used}
        sp.update(sublevel=lv, split_from='physics.json')
        json.dump(sp, open(os.path.join(od, 'physics.json'), 'w', encoding='utf-8'), indent=1, default=str)
        out[CR.outname(lv)] = OD([('collision_nodes', split['collision_pawn.glb']['per_level'].get(lv, 0)),
                                  ('weapon_collision_nodes', (split.get('collision_weapon.glb') or {}).get('per_level', {}).get(lv, 0)),
                                  ('props', len(sp.get('props') or [])), ('volumes', len(sp.get('volumes') or [])),
                                  ('collision_bytes', os.path.getsize(os.path.join(od, 'collision_pawn.glb')) if os.path.exists(os.path.join(od, 'collision_pawn.glb')) else 0),
                                  ('weapon_collision_bytes', os.path.getsize(os.path.join(od, 'collision_weapon.glb')) if os.path.exists(os.path.join(od, 'collision_weapon.glb')) else 0),
                                  ('physics_bytes', os.path.getsize(os.path.join(od, 'physics.json')))])
    # gameplay.json: the World reads it from the map dir (start points, pickup factories, match spawn data, map state); for a chapter that is
    # the persistent unit, so the persistent unit gets the WHOLE chapter file (its records span the sublevels; one map state per World)
    pers = next((l for l in levels if l.lower().endswith('_base_m')), None)
    if pers and os.path.isdir(os.path.join(R, CR.outname(pers))) and os.path.exists(os.path.join(D, 'gameplay.json')):
        shutil.copyfile(os.path.join(D, 'gameplay.json'), os.path.join(R, CR.outname(pers), 'gameplay.json'))
    _rest(ch, D, R, levels, assign, why, out, split)

def split_glb(D, R, ch, levels, gname, prop_lv, vol_lv):
    """split a chapter collision glb by level (BSP by node name, volumes by physics.json actor + sublevel / first vertex, props by actor /
    mesh / matrix); writes <unit>/<gname>; no-loss counts"""
    bj, bb = read_glb(os.path.join(D, gname))
    assign, why = {}, Counter()
    for i, n in enumerate(bj['nodes']):
        if n.get('mesh') is None: continue
        ex = n.get('extras') or {}; kind = ex.get('kind'); name = n.get('name') or ''
        lv = None
        if kind == 'bsp_solid' and name.startswith('BSPCollision_'): lv = name[len('BSPCollision_'):]; why['bsp'] += 1
        elif kind and kind.startswith('prop_'):
            s = prop_lv.get((name, ex.get('mesh'), mkey(n.get('matrix'))))
            if s and len(s) == 1: lv = next(iter(s)); why['prop'] += 1
        else:
            cands = vol_lv.get(name, [])
            if len(cands) == 1: lv = cands[0]['sublevel']; why['volume'] += 1
            elif cands:
                P0 = accessor(bj, bb, bj['meshes'][n['mesh']]['primitives'][0]['attributes']['POSITION'])[0]
                best = min(cands, key=lambda v: float(np.abs(np.array(v['polygons_gltf'][0][0], float) - P0).sum()))
                lv = best['sublevel']; why['volume_by_vertex'] += 1
        assign[i] = lv if lv in levels else None
        if assign[i] is None: why['unassigned'] += 1
    per_level = {}
    for lv in levels:
        od = os.path.join(R, CR.outname(lv))
        if not os.path.isdir(od): continue
        idx = [i for i, l in assign.items() if l == lv]; per_level[lv] = len(idx)
        g = GLB('AssetTools campaign_collision (%s %s %s)' % (ch, lv, gname)); cache = {}
        for i in idx:
            n = bj['nodes'][i]; mi = n['mesh']
            if mi not in cache:
                prims = []
                for pr in bj['meshes'][mi]['primitives']:
                    P = accessor(bj, bb, pr['attributes']['POSITION']).astype('f4'); p2 = {'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)}}
                    if 'indices' in pr: p2['indices'] = g.acc(accessor(bj, bb, pr['indices']).astype('u4'), 'SCALAR', target=34963)
                    prims.append(p2)
                cache[mi] = g.mesh(bj['meshes'][mi].get('name', ''), prims)
            g.node(dict(n, mesh=cache[mi]))
        g.write(os.path.join(od, gname))   # every unit gets the file, an empty valid glb when the level owns no such collision (the loader opens it)
    return {'assign': assign, 'why': why, 'per_level': per_level, 'nodes_total': len(assign), 'unassigned': why['unassigned']}

def _rest(ch, D, R, levels, assign, why, out, split):
    shutil.copyfile(os.path.join(D, 'navigation.json'), os.path.join(R, 'navigation.json'))
    import escalation_data as ED
    cells, nodes, setup_off = ED.navmesh(ch, levels, {})
    nm = {'chapter': ch, 'generated_by': 'AssetTools/work/campaign_render/campaign_collision.py (escalation_data.navmesh)',
          'schema': 'manifests/maps/<ESC map>/escalation_navmesh.json (bot_nav cell schema + original actor ids)', 'units': 'gltf metres Y-up = 0.01 * (x, z, y)_UE',
          'counts': {'cells': len(cells), 'blocked_at_start': sum(1 for c in cells if c['blocked_at_start']), **{k: len(v) for k, v in nodes.items()}},
          'cells': cells, 'nodes': nodes}
    json.dump(nm, open(os.path.join(R, 'navmesh.json'), 'w', encoding='utf-8'), indent=1)
    rep = {'chapter': ch, 'nodes_total': len(assign), 'assigned_by': dict(why), 'no_loss': why['unassigned'] == 0 and sum(v['collision_nodes'] for v in out.values()) == len(assign),
           'weapon_collision': {k: {'nodes_total': v['nodes_total'], 'unassigned': v['unassigned'], 'no_loss': v['unassigned'] == 0 and sum(v['per_level'].values()) == v['nodes_total']}
                                for k, v in split.items()},
           'gameplay_json': 'whole chapter file in the persistent unit (the World reads it from the map dir)',
           'sublevels': out, 'navmesh_counts': nm['counts'], 'navigation_nodes': len(json.load(open(os.path.join(R, 'navigation.json'), encoding='utf-8'))['nodes'])}
    json.dump(rep, open(os.path.join(R, 'collision_report.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(rep)[:900])

if __name__ == '__main__':
    main(sys.argv[1])
