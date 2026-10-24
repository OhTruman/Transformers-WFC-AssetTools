"""Escalation (co-op horde) data for Gameplay's spec (GAMEPLAY_ESCALATION_SPEC.md; Integration go 2026-10-18). Read-only.

  A  manifests/maps/<MAP>/escalation_geometry.json  per TnSurvivalGenerator: location, PowerLevels / DrainRate, activation-volume
     polygons; its Kismet event outputs (RE export notes/data/escalation/<MAP>.json, 'downstream') with every target resolved:
     (zones[].spawn_points, Gameplay 2026-10-23: the zone's authored PossibleSpawnPoints in array order -> TnSurvivalSpawnPoint actor,
     class, location, yaw, nav anchor, authored props); weapon_pickups (Gameplay E2b 2026-10-23): every TnWeaponPickupFactory / plain
     TnPickupFactory of the level packages with InventoryType, RespawnTime, the pickup mesh / effect components resolved to their assets,
     nav anchor, yaw, and the generators whose Kismet events target it
     volumes -> physics.json polygons + collision flags, NavigationCells -> ids into the navmesh, transforming actors -> object paths of
     manifests/maps/mp_transforming_actors.json, pickup factories / nodes / emitters -> location + authored class props.
  B  manifests/maps/<MAP>/escalation_navmesh.json   the ORIGINAL cooked NavigationCell mesh (bot_nav cell schema + the original actor
     ids), with blocked_at_start = the cooked bBlocked flag and the generators whose event turns each cell on; TnTacticalPathNode and
     PathNode with ids, location and their authored properties.
  D  manifests/escalation/survival_weapon_data.json per weapon class: its MultiplayerData / PlayerData / AiData / SurvivalData objects;
     the *_SV_WEPDATA objects decoded in full and diffed against the class's MultiplayerData (else PlayerData) object.
UE -> glTF: v_gltf = 0.01 * (x, z, y).
"""
import json, os, sqlite3, sys
from collections import OrderedDict as OD, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(ROOT)
DB = sqlite3.connect(os.path.join(ROOT, 'manifests', 'authored.db'))
VS = os.path.join(TR, 'ExtractedAssets', 'VerticalSlice', 'Maps')
RE = os.path.join(TR, 'RE-Workspace', 'notes', 'data', 'escalation')
MAPS = {'MP_ESC_BrokenHope': ('MP_ESC_BrokenHope_Base_m', 'MP_ESC_BrokenHope_ART_m'),
        'MP_ESC_Remnant': ('MP_ESC_Remnant_BASE_m', 'MP_ESC_Remnant_ART_m')}

# opt-in DLC mode (2026-10-23): `--maps M1,M2` builds A / B for those maps only (level packages via the cooked lookup, which honours
# WFC_COOKED_DIR), with the DLC authored.db attached behind the base one (WFC_AUTHORED_EXTRA_DB), physics.json from WFC_VS_ROOT and the
# transforming actors from manifests/maps/<MAP>/transforming_actors_gameplay.json; part D (base-wide weapon data) is not rerun.
# Without --maps: unchanged.
DLC_MAPS = sys.argv[sys.argv.index('--maps') + 1].split(',') if '--maps' in sys.argv else None
if DLC_MAPS:
    from m03_common import map_levels
    MAPS = {m: tuple(x for x in (map_levels(m)['base'], map_levels(m)['art']) if x) for m in DLC_MAPS}
    if os.environ.get('WFC_VS_ROOT'): VS = os.path.join(os.environ['WFC_VS_ROOT'], 'Maps')
    if os.environ.get('WFC_AUTHORED_EXTRA_DB'):
        DB.execute('ATTACH DATABASE ? AS xdb', (os.environ['WFC_AUTHORED_EXTRA_DB'],))
        for _t in ('objects', 'refs'):
            DB.execute('CREATE TEMP VIEW %s AS SELECT * FROM main.%s UNION ALL SELECT * FROM xdb.%s' % (_t, _t, _t))

def g(v): return [round(0.01 * v['X'], 4), round(0.01 * v['Z'], 4), round(0.01 * v['Y'], 4)]
def ue(v): return [v['X'], v['Y'], v['Z']]
def short(o): return o.rsplit('.', 1)[-1] if o else o

def level_objects(pkgs, cls):
    out = {}
    for pk in pkgs:
        for o, c, p in DB.execute('select opath, class, props from objects where package=? and class=?', (pk, cls)):
            if o.count('.') == 3: out[short(o)] = (o, json.loads(p or '{}'))
    return out

def setup_toggles(pkgs, max_depth=8):
    """cells toggled at match setup: walk forward from every SeqEvent_PreGameplaySetup through OutputLinks (up to max_depth ops);
    for each SeqAct_Toggle reached, its input name (Turn On / Turn Off / Toggle) and its Target object variables' ObjValue
    (RE MP_ESCALATION_RE.md section 7.5: BrokenHope's door / bridge cells are turned off this way at setup)"""
    def props(o):
        r = DB.execute('select class, props from objects where opath=?', (o,)).fetchone()
        return (r[0], json.loads(r[1] or '{}')) if r else (None, {})
    off, on = defaultdict(set), defaultdict(set)
    for pk in pkgs:
        for ev, in DB.execute("select opath from objects where package=? and class='SeqEvent_PreGameplaySetup'", (pk,)):
            frontier, seen = [(ev, None, 0)], set()
            while frontier:
                op, idx, dep = frontier.pop()
                if (op, idx) in seen or dep > max_depth: continue
                seen.add((op, idx)); cls, p = props(op)
                if cls == 'SeqAct_Toggle' and idx is not None:
                    name = ((p.get('InputLinks') or [{}] * (idx + 1))[idx] or {}).get('LinkDesc')
                    tg = [short((props(v)[1] or {}).get('ObjValue')) for vl in p.get('VariableLinks') or [] if vl.get('LinkDesc') == 'Target'
                          for v in vl.get('LinkedVariables') or []]
                    for t in tg:
                        if t and t.startswith('NavigationCell'):
                            (off if name == 'Turn Off' else on)[t].add('%s -> %s (%s)' % (short(ev), short(op), name))
                for ol in p.get('OutputLinks') or []:
                    for ln in ol.get('Links') or []:
                        if ln.get('LinkedOp'): frontier.append((ln['LinkedOp'], ln.get('InputLinkIdx', 0), dep + 1))
    return off, on

def spawn_points(pkgs, zone):
    """a TnSurvivalZoneVolume's authored PossibleSpawnPoints (array order) resolved to their actors (CONFIRMED cooked data);
    yaw: Rotation.Yaw in UE units (65536 = 360 deg, about UE +Z, 0 = facing +X) and in degrees"""
    for pk in pkgs:
        r = DB.execute('select props from objects where opath=?', (pk + '.TheWorld.PersistentLevel.' + zone,)).fetchone()
        if not r: continue
        sp = json.loads(r[0] or '{}').get('PossibleSpawnPoints') or []
        if isinstance(sp, str): sp = json.loads(sp)
        out = []
        for o in sp:
            row = DB.execute('select class, props from objects where opath=?', (o,)).fetchone()
            if not row: out.append(OD([('actor', short(o)), ('object', o), ('resolved', False)])); continue
            q = json.loads(row[1] or '{}'); rot = q.get('Rotation') or {}; yaw = rot.get('Yaw', 0)
            out.append(OD([('actor', short(o)), ('class', row[0]), ('object', o),
                           ('location_gltf', g(q['Location']) if q.get('Location') else None),
                           ('location_ue', ue(q['Location']) if q.get('Location') else None),
                           ('yaw_ue', yaw), ('yaw_deg', round(yaw * 360.0 / 65536.0, 3)), ('rotation_ue', rot or None),
                           ('nav_anchor', short((q.get('StaticAnchor') or {}).get('Nav'))), ('on_nav_mesh', q.get('OnNavMesh')),
                           ('props', {k: v for k, v in q.items() if k not in ('Location', 'Rotation', 'StaticAnchor', 'OnNavMesh', 'Components',
                                                                              'CollisionComponent', 'CylinderComponent', 'Base', 'NavGuid')})]))
        return out
    return None

def weapon_pickups(pkgs, targeted_by):
    """TnWeaponPickupFactory + TnPickupFactory actors of the level packages (CONFIRMED cooked data)"""
    def props(o):
        r = DB.execute('select class, props from objects where opath=?', (o,)).fetchone()
        return (r[0], json.loads(r[1] or '{}')) if r else (None, {})
    out = []
    for cls in ('TnWeaponPickupFactory', 'TnPickupFactory'):
        for name, (o, q) in sorted(level_objects(pkgs, cls).items(), key=lambda kv: int(kv[0].rsplit('_', 1)[1])):
            rot = q.get('Rotation') or {}; yaw = rot.get('Yaw', 0)
            mc, mp_ = props(q['PickupMesh']) if q.get('PickupMesh') else (None, {})
            ec, ep = props(q['PickupEffect']) if q.get('PickupEffect') else (None, {})
            out.append(OD([('actor', name), ('class', cls), ('object', o), ('inventory_type', q.get('InventoryType')),
                           ('mounted_weapon', 'Mounted' in str(q.get('InventoryType'))), ('respawn_time', q.get('RespawnTime')),
                           ('location_gltf', g(q['Location']) if q.get('Location') else None), ('location_ue', ue(q['Location']) if q.get('Location') else None),
                           ('yaw_ue', yaw), ('yaw_deg', round(yaw * 360.0 / 65536.0, 3)),
                           ('pickup_mesh', OD([('component', short(q.get('PickupMesh'))), ('class', mc),
                                               ('mesh', mp_.get('StaticMesh') or mp_.get('SkeletalMesh'))]) if q.get('PickupMesh') else None),
                           ('pickup_effect', OD([('component', short(q.get('PickupEffect'))), ('class', ec), ('template', ep.get('Template'))]) if q.get('PickupEffect') else None),
                           ('nav_anchor', short((q.get('StaticAnchor') or {}).get('Nav'))), ('targeted_by_generators', sorted(targeted_by.get(name, []))),
                           ('props', {k: v for k, v in q.items() if k not in ('Location', 'Rotation', 'StaticAnchor', 'PickupMesh', 'PickupEffect', 'Components',
                                                                              'CollisionComponent', 'CylinderComponent', 'Base', 'NavGuid', 'PathList')})]))
    return out

def navmesh(m, pkgs, enabled_by):
    cells = level_objects(pkgs, 'NavigationCell')
    # numeric suffix order; a name without one ('NavigationCell', A3_COR) sorts first (stable: ties keep their order, as before)
    ids = {k: i for i, k in enumerate(sorted(cells, key=lambda x: int(x.rsplit('_', 1)[1]) if '_' in x and x.rsplit('_', 1)[1].isdigit() else -1))}
    setup_off, setup_on = setup_toggles(pkgs)
    out = []
    for name in sorted(ids, key=ids.get):
        o, p = cells[name]
        edges = []
        for e in p.get('_Edges') or []:
            nb = short(((e.get('Neighbor') or {}).get('Nav')))
            edges.append(OD([('start_gltf', g(e['Start'])), ('end_gltf', g(e['End'])), ('start_ue', ue(e['Start'])), ('end_ue', ue(e['End'])),
                             ('normal_ue', ue(e['Normal'])), ('border', bool(e.get('Border'))),
                             ('neighbors', [OD([('cell', ids.get(nb)), ('actor', nb)])] if nb else [])]
                            + [(k, e[k]) for k in e if k not in ('Start', 'End', 'Normal', 'Neighbor', 'Border')]))
        V = [x['start_gltf'] for x in edges]
        out.append(OD([('id', ids[name]), ('actor', name), ('object', o),
                       ('vertices_gltf', V), ('vertices_ue', [x['start_ue'] for x in edges]),
                       ('centroid_gltf', [round(sum(c[i] for c in V) / len(V), 4) for i in range(3)] if V else None),
                       ('location_ue', ue(p['Location'])) if p.get('Location') else ('location_ue', None),
                       ('normal_ue', ue(p['_Normal'])) if p.get('_Normal') else ('normal_ue', None),
                       ('tactical', bool(p.get('_IsTacticalCell'))),
                       ('blocked_at_start', bool(p.get('bBlocked')) or name in setup_off),
                       ('blocked_cooked', bool(p.get('bBlocked'))),
                       ('blocked_by_setup', sorted(setup_off.get(name, []))),
                       ('enabled_by_setup', sorted(setup_on.get(name, []))),
                       ('enabled_by_generators', sorted(enabled_by.get(name, []))),
                       ('base', short(p.get('Base'))), ('nav_guid', p.get('NavGuid')), ('network_id', p.get('NetworkID')),
                       ('max_path_size', p.get('MaxPathSize')), ('path_list', [short(x) for x in p.get('PathList') or []]),
                       ('edges', edges)]))
    nodes = {}
    for cls in ('TnTacticalPathNode', 'PathNode'):
        objs = level_objects(pkgs, cls)
        nodes[cls] = [OD([('actor', k), ('object', o), ('location_gltf', g(p['Location']) if p.get('Location') else None),
                          ('location_ue', ue(p['Location']) if p.get('Location') else None),
                          ('path_list', [short(x) for x in p.get('PathList') or []]),
                          ('props', {kk: vv for kk, vv in p.items() if kk not in ('Location', 'PathList', 'CylinderComponent',
                                                                              'CollisionComponent', 'Components')})])
                      for k, (o, p) in sorted(objs.items(), key=lambda kv: int(kv[0].rsplit('_', 1)[1]))]
    return out, nodes, setup_off

def main():
    os.makedirs(os.path.join(ROOT, 'manifests', 'escalation'), exist_ok=True)
    ta = json.load(open(os.path.join(ROOT, 'manifests', 'maps', 'mp_transforming_actors.json'), encoding='utf-8'))['actors']
    if DLC_MAPS:
        for m in DLC_MAPS:
            tf = os.path.join(ROOT, 'manifests', 'maps', m, 'transforming_actors_gameplay.json')
            if os.path.exists(tf): ta += json.load(open(tf, encoding='utf-8'))['actors']
    for m, pkgs in MAPS.items():
        re = json.load(open(os.path.join(RE, m + '.json'), encoding='utf-8'))
        phys = {v['actor']: v for v in json.load(open(os.path.join(VS, m, 'physics.json'), encoding='utf-8')).get('volumes') or []}
        tact = {short(a['object']): a['object'] for a in ta if a['map'] == m}
        # generator -> events -> actions; cell -> generators that turn it on
        by_gen = defaultdict(list); enabled_by = defaultdict(set)
        for e in re['events']:
            if e.get('originator'): by_gen[e['originator']].append(e)
        def resolve(t):
            kind = t.rsplit('_', 1)[0]
            r = OD([('target', t), ('class', kind)])
            if t in phys:
                v = phys[t]; r.update({'polygons_gltf': v.get('polygons_gltf'), 'blocks_pawn': v.get('blocks_pawn'),
                                       'blocks_weapon': v.get('blocks_weapon'), 'component_flags': v.get('component_flags')})
            elif kind == 'NavigationCell': r['navmesh_actor'] = t
            elif kind == 'TnTransformingWorldActor': r['transforming_actor'] = tact.get(t)
            else:
                row = next(((o, p) for pk in pkgs for o, p in DB.execute('select opath, props from objects where package=? and opath like ?',
                                                                       (pk, '%.PersistentLevel.' + t)) if o.count('.') == 3), None)
                if row:
                    p = json.loads(row[1] or '{}'); r['object'] = row[0]
                    if p.get('Location'): r['location_gltf'] = g(p['Location']); r['location_ue'] = ue(p['Location'])
                    r['props'] = {k: v for k, v in p.items() if k not in ('Location', 'Components', 'CollisionComponent', 'CylinderComponent')}
                else: r['resolved'] = False
            return r
        gens = []
        for gen in re['generators']:
            gid = gen['object']; av = short(gen.get('ActivationVolume'))
            evs = []
            for e in by_gen.get(gid, []):
                acts = []
                for s in e.get('downstream') or []:
                    if s.get('depth', 0) == 0: continue
                    tg = [x for v in (s.get('vars') or {}).values() for x in (v or [])]
                    if s['class'] == 'SeqAct_Toggle' and s.get('input') == 'Turn On':
                        for x in tg:
                            if x.startswith('NavigationCell'): enabled_by[x].add(gid)
                    acts.append(OD([('op', s['op']), ('class', s['class']), ('input', s.get('input')), ('via', s.get('via')),
                                    ('depth', s.get('depth')), ('comment', s.get('comment')),
                                    ('targets', [resolve(x) for x in tg if not x.startswith('SeqVar_')]),
                                    ('variable_targets', [x for x in tg if x.startswith('SeqVar_')])]))
                    # DLC --maps mode only (base outputs unchanged): RE 1104a86 'seq' = the op's sequence below Main_Sequence; short op names
                    # repeat across instanced sequences (District's five Door_Lasers copies)
                    if DLC_MAPS: acts[-1]['seq'] = s.get('seq')
                evs.append(OD([('event', e['event']), ('class', e['class']), ('outputs', e.get('outputs')), ('actions', acts)]))
                if DLC_MAPS: evs[-1]['seq'] = e.get('seq')
            v = phys.get(av) or {}
            gens.append(OD([('generator', gid), ('name_key', gen.get('LocalizedGeneratorNameKey')), ('power_levels', gen.get('PowerLevels')),
                            ('drain_rate', gen.get('DrainRate')), ('location_ue', ue(gen['Location'])), ('location_gltf', g(gen['Location'])),
                            ('activation_volume', av), ('activation_polygons_gltf', v.get('polygons_gltf')), ('events', evs)]))
        other = [OD([('event', e['event']), ('class', e['class']), ('originator', e.get('originator')), ('comment', e.get('comment')),
                     ('outputs', e.get('outputs'))]) for e in re['events'] if e.get('originator') not in {x['object'] for x in re['generators']}]
        tb = defaultdict(set)
        for gn in gens:
            for ev in gn['events']:
                for ac in ev['actions']:
                    for t in ac['targets']:
                        if 'PickupFactory' in t['target']: tb[t['target']].add(gn['generator'])
        wp = weapon_pickups(pkgs, tb)
        zones = [OD([('zone', short(z.get('object') or z.get('zone') or '')), ('polygons_gltf', (phys.get(short(z.get('object') or '')) or {}).get('polygons_gltf')),
                     ('re', z), ('spawn_points', spawn_points(pkgs, short(z.get('object') or z.get('zone') or '')))]) for z in re.get('zones') or []]
        A = OD([('map', m), ('generated_by', 'AssetTools/scripts/wfc/escalation_data.py'),
                ('sources', ['RE-Workspace/notes/data/escalation/%s.json (generators / events / zones, RE)' % m,
                             'ExtractedAssets/VerticalSlice/Maps/%s/physics.json (volume polygons)' % m, 'manifests/authored.db',
                             'manifests/maps/mp_transforming_actors.json']),
                ('units', 'gltf metres Y-up = 0.01 * (x, z, y)_UE'),
                ('counts', OD([('generators', len(gens)), ('generators_with_events', sum(1 for x in gens if x['events'])),
                               ('other_events', len(other)), ('zones', len(zones)),
                               ('zone_spawn_points', sum(len(z['spawn_points'] or []) for z in zones)), ('weapon_pickups', len(wp))])),
                ('generators', gens), ('other_events', other), ('zones', zones), ('weapon_pickups', wp)])
        json.dump(A, open(os.path.join(ROOT, 'manifests', 'maps', m, 'escalation_geometry.json'), 'w', encoding='utf-8'), indent=1)
        cells, nodes, setup_off = navmesh(m, pkgs, enabled_by)
        on = {k for k in enabled_by}; blocked = {c['actor'] for c in cells if c['blocked_at_start']}
        cooked = {c['actor'] for c in cells if c['blocked_cooked']}
        B = OD([('map', m), ('generated_by', 'AssetTools/scripts/wfc/escalation_data.py'),
                ('status', 'ORIGINAL cooked Escalation nav mesh (NavigationCell actors; Escalation NavigationCell schema, RE MP note addendum 1)'),
                ('units', 'gltf metres Y-up = 0.01 * (x, z, y)_UE; ue centimetres Z-up'),
                ('start_state', OD([
                    ('rule', 'blocked_at_start = cooked NavigationCell.bBlocked OR turned off by a SeqEvent_PreGameplaySetup chain '
                             '(SeqAct_Toggle "Turn Off" at match setup) - RE MP_ESCALATION_RE.md section 7.5, CONFIRMED. '
                             'enabled_by_generators = the generators whose event fires SeqAct_Toggle "Turn On" on the cell (RE export).'),
                    ('cells_blocked_at_start', len(blocked)), ('blocked_cooked', len(cooked)),
                    ('blocked_by_setup_only', len(blocked - cooked)), ('setup_turn_off_cells', len(setup_off)),
                    ('cells_turned_on_by_generators', len(on)), ('blocked_and_turned_on', len(on & blocked)),
                    ('turned_on_but_not_blocked', sorted(on - blocked)), ('blocked_but_never_turned_on', sorted(blocked - on))])),
                ('counts', OD([('cells', len(cells)), ('tactical_cells', sum(c['tactical'] for c in cells)),
                               ('TnTacticalPathNode', len(nodes['TnTacticalPathNode'])), ('PathNode', len(nodes['PathNode']))])),
                ('cells', cells), ('nodes', nodes)])
        json.dump(B, open(os.path.join(ROOT, 'manifests', 'maps', m, 'escalation_navmesh.json'), 'w', encoding='utf-8'), indent=1)
        print(m, 'A', A['counts'], 'B', B['counts'], 'blocked', len(blocked), 'on', len(on), 'on-not-blocked', len(on - blocked))
    # ---- D
    if DLC_MAPS: return                     # DLC mode: the base-wide weapon data is not rerun
    rows = []
    for o, p in DB.execute("select opath, props from objects where (opath like 'TransContent.Default__TnWeapon%' or opath like "
                           "'TransGame.Default__TnWeapon%') and opath not like '%.%.%' order by opath"):
        d = json.loads(p or '{}')
        rec = OD([('weapon_class', o.split('Default__', 1)[1]), ('cdo', o)] +
                 [(k, d.get(k)) for k in ('MultiplayerData', 'PlayerData', 'AiData', 'SurvivalData')])
        # RE MP_ESCALATION_RE.md section 7.4 (CONFIRMED): GetWeaponDataByType(4) = SurvivalData, no fallback inside; TnWeapon.GivenTo
        # falls back for a player pawn to type 1 = PlayerData (not MultiplayerData); AI holders always use AiData
        rec['escalation_player_data'] = d.get('SurvivalData') or d.get('PlayerData')
        rec['escalation_player_data_source'] = ('SurvivalData' if d.get('SurvivalData') else
                                                'PlayerData (GivenTo fallback)' if d.get('PlayerData') else 'none set on the class')
        rec['escalation_ai_data'] = d.get('AiData')
        if d.get('SurvivalData'):
            sv = DB.execute('select props from objects where opath=?', (d['SurvivalData'],)).fetchone()
            svp = json.loads(sv[0]) if sv and sv[0] else None
            base_o = d.get('PlayerData') or d.get('MultiplayerData')
            bp = DB.execute('select props from objects where opath=?', (base_o,)).fetchone() if base_o else None
            bpp = json.loads(bp[0]) if bp and bp[0] else {}
            rec['survival_data_values'] = svp
            rec['diff_vs'] = base_o
            rec['diff'] = {k: {'survival': (svp or {}).get(k), 'base': bpp.get(k)} for k in sorted(set(svp or {}) | set(bpp))
                           if (svp or {}).get(k) != bpp.get(k)} if svp is not None else None
        rows.append(rec)
    D = OD([('generated_by', 'AssetTools/scripts/wfc/escalation_data.py'),
            ('rule', 'Escalation asks for DesiredWeaponDataType 4 (SurvivalData) [RE MP_ESCALATION_RE.md section 1]. '
                     'GetWeaponDataByType(4) returns SurvivalData with no fallback inside; TnWeapon.GivenTo falls back for a player '
                     'pawn to type 1 = PlayerData (the campaign tuning, NOT MultiplayerData); AI holders always use AiData '
                     '[RE section 7.4, CONFIRMED]. escalation_player_data / escalation_ai_data apply that rule per class. '
                     'diff = SurvivalData vs PlayerData, tagged properties only (a field the SV object leaves unset inherits from '
                     'its archetype, so it appears as a difference with survival = null).'),
            ('counts', OD([('weapon_classes', len(rows)), ('with_survival_data', sum(1 for r in rows if r['SurvivalData'])),
                           ('player_data_fallback', sum(1 for r in rows if not r['SurvivalData'] and r['PlayerData'])),
                           ('no_player_data_at_all', sum(1 for r in rows if not r['SurvivalData'] and not r['PlayerData']))])),
            ('weapons', rows)])
    json.dump(D, open(os.path.join(ROOT, 'manifests', 'escalation', 'survival_weapon_data.json'), 'w', encoding='utf-8'), indent=1)
    print('D', D['counts'])

if __name__ == '__main__':
    main()
