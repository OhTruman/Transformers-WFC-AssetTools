"""Authored multiplayer gameplay setup of a map, from manifests/authored.db (authored.py) + Coalesced config.

Output: ExtractedAssets/VerticalSlice/Maps/<MAP>/gameplay.json
  modes        map's CompatibleGameTypes (TransLevels.ini MapInfo) joined with TnOnlineGameSettings<TAG> (game class,
               lobby, min players, time limits), playlist names/ids (TransPlaylists.ini), rule-class config
  player_starts  team / free-for-all starts with Team, transform; spawn_clusters with members + faction-neutral modes
  pickups      factories: inventory class, respawn, payload from the inventory CDO, effects (particle templates)
  objectives   flags, flag capture points, bomb + plant points, domination points, King-of-the-Hill zones:
               effective tuning, required game rule, objective volume (polygons from collision.json)
  kismet       gameplay sequence graph (events, conditions, actions, variables) + mode-dependent visibility,
               matinee tracks (sky beam)
  other        CameraActor, StaticInterpActors, asset references
Values are authored data (CONFIRMED) unless an item says otherwise.
  python vs_gameplay.py [MAP]
"""
import json, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, extract  # noqa: E402
from vs_common import VS, ue_actor_matrix, ue_to_gltf_matrix, ue_points_to_gltf, is_campaign  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
CFG = os.path.join(os.path.dirname(extract.OUT), 'config', 'Coalesced_ini', 'TransGame', 'Config', 'Xenon', 'Cooked')
NOISE = re.compile(r'^(b[A-Z]|Net|Remote|Role|Tick|Draw|Physics|Collision|Supported|Message|Components|Custom|Mass|Buoyancy|Time$|RB|Pre|'
                   r'Visibility|Ambient|Sound|ActorIndex|ReplicatedCollisionPreset|PathRenderingClass|MaxConnectionDistance|NavGuid|'
                   r'CylinderComponent|GoodSprite|BadSprite|Sprite|Arrow|CreationTime|Layer|Group$|nextNavigationPoint|previousPath|'
                   r'visitedWeight|bestPathWeight|NetworkID|PathList|EnclosingVolumes|VolumeList|Velocity|Rotation$|Location$|'
                   r'DrawScale|LifeSpan|LastRenderTime|Owner|Instigator|Base$|DesiredRotation|CachedParentToWorld)')

def ini(fname):
    out, sec = defaultdict(list), None
    p = os.path.join(CFG, fname)
    if not os.path.exists(p): return out
    for l in open(p, encoding='utf-8', errors='replace'):
        l = l.rstrip('\n'); m = re.match(r'^\[(.+)\]\s*$', l)
        if m: sec = m.group(1); continue
        if sec and '=' in l and not l.lstrip().startswith(';'):
            k, v = l.split('=', 1); out[sec].append((k.strip(), v.strip()))
    return out

def vals(sec, key): return [v for k, v in sec if k == key]

def xf(v):
    loc = [float((v.get('Location') or {}).get(a, 0.0)) for a in 'XYZ']
    rot = [int((v.get('Rotation') or {}).get(a, 0)) for a in ('Pitch', 'Yaw', 'Roll')]
    ds3 = [float((v.get('DrawScale3D') or {}).get(a, 1.0)) for a in 'XYZ']
    M = ue_actor_matrix(loc, rot, float(v.get('DrawScale', 1.0)), ds3)
    return {'location_ue': loc, 'rotation_ue': rot, 'yaw_deg': round(rot[1] * 360.0 / 65536.0, 3),
            'location_gltf': ue_points_to_gltf([loc])[0].round(4).tolist(), 'gltf_matrix': ue_to_gltf_matrix(M)}

def clean(v): return {k: x for k, x in v.items() if not NOISE.match(k)}

from vs_common import map_sublevels  # noqa: E402

def main():
    subs = map_sublevels(MAP, A)   # name prefix + streamed sublevels (map.json)
    base = next(s for s in subs if s.lower().endswith('_base_m'))
    lvl = base + '.TheWorld.PersistentLevel.'
    out = {'map': MAP, 'gameplay_level': base, 'source': 'manifests/authored.db + Coalesced TransLevels/Xe-TransGame/TransPlaylists.ini',
           'notes': []}
    # ------------------------------------------------------------------ modes
    levels, game, pls = ini('TransLevels.ini'), ini('Xe-TransGame.ini'), ini('TransPlaylists.ini')
    mi = next((s for s in levels if s.lower().startswith(base.lower()) and 'MapInfo' in s), None)
    playlist = {}
    for s, kv in pls.items():
        if 'OnlinePlaylist' in s:
            tag = (vals(kv, 'GameModeTag') or [None])[0]
            playlist.setdefault(tag, []).append({'name': s.split()[0].replace('PlaylistData', ''), 'playlist_id': (vals(kv, 'PlaylistId') or [None])[0],
                                                 'visible': (vals(kv, 'VisibleInMenu') or [None])[0]})
    modes = []
    for tag in vals(levels.get(mi, []), 'CompatibleGameTypes'):
        gs = game.get('TransGame.TnOnlineGameSettings' + tag, [])
        modes.append({'tag': tag, 'playlists': playlist.get(tag, []), 'game_class': (vals(gs, 'GameClass') or [None])[0],
                      'lobby_game_class': (vals(gs, 'LobbyGameClass') or [None])[0],
                      'min_players': (vals(gs, 'NumRequiredPlayers') or [None])[0], 'time_limits_s': [int(x) for x in vals(gs, 'TimeLimits')]})
    out['map_info'] = {'section': mi, **{k: v for k, v in levels.get(mi, []) if k != 'CompatibleGameTypes'}}
    out['modes'] = modes
    out['game_rules_config'] = {s.split('.')[-1]: dict(kv) for s, kv in game.items() if s.startswith('TransGame.TnGameRules_')}
    out['game_classes'] = {}
    for c in ('TnVersusGame', 'TnFreeForAllGame', 'TnTeamGame', 'TnMultiplayerGame'):
        rows = [r for r in A.find('%.Default__' + c) if r['class'] == c]
        if rows:
            v = A.values(rows[0]['opath'])
            out['game_classes'][c] = {k: v.get(k) for k in ('DefaultPawnClass', 'MaxPlayers', 'MaxPlayersAllowed', 'MaxSpectators', 'MaxIdleTime',
                                                            'TeamHandler', 'SpawnHelper', 'RespawnHelper', '_SpawnPointManager', 'GameReplicationInfoClass') if k in v}
            out['game_classes'][c]['config'] = dict(game.get('TransContent.' + c, []))
    # ------------------------------------------------------------------ actors
    vols = {}
    cp = os.path.join(OUT, 'collision.json')
    if os.path.exists(cp):
        for v in json.load(open(cp, encoding='utf-8'))['volumes']: vols[v['actor']] = v['polygons_gltf']
    def actors(cls): return sorted(A.find(lvl + '%', cls), key=lambda r: r['opath'])
    def rec(r, keys=None):
        v = A.values(r['opath'])
        d = {'actor': r['opath'].rsplit('.', 1)[-1], 'class': r['class'], **xf(v),
             'authored': clean({k: x for k, x in (r['props'] or {}).items()})}
        d['effective'] = {k: v.get(k) for k in keys if k in v} if keys else clean(v)
        ov = v.get('ObjectiveVolume')
        if ov:
            d['objective_volume'] = ov.rsplit('.', 1)[-1]; d['objective_volume_polygons_gltf'] = vols.get(ov.rsplit('.', 1)[-1])
        return d
    # starts + clusters
    starts = [rec(r, ['Team', 'TeamNum']) for c in ('TnTeamPlayerStart', 'TnFreeForAllPlayerStart') for r in actors(c)]
    clusters = []
    member_of = defaultdict(list)
    for r in actors('TnSpawnCluster'):
        v = A.values(r['opath']); mem = [m.rsplit('.', 1)[-1] for m in v.get('SpawnPoints') or [] if m]
        for m in mem: member_of[m].append(r['opath'].rsplit('.', 1)[-1])
        c = rec(r, ['FactionNeutralGameTypes']); c['members'] = mem
        c['center_ue'] = [v.get('_CenterPoint', {}).get(a) for a in 'XYZ']
        clusters.append(c)
    for s in starts:
        s['clusters'] = member_of.get(s['actor'], [])
        if s['class'] == 'TnTeamPlayerStart' and not s['effective'].get('Team'):
            s['effective']['Team'] = 'TNTG_Autobots'          # unset ByteProperty = enum value 0 (ETnTeamGameTeam)
            s['team_from_enum_default'] = True
    team_of = {s['actor']: s['effective'].get('Team') for s in starts}
    for c in clusters:
        c['teams'] = dict(Counter(team_of.get(m) for m in c['members']))
    orphans = [s for s in starts if s['class'] == 'TnTeamPlayerStart' and not s['clusters']] if clusters else []   # Escalation maps: no clusters
    for o in orphans:
        import numpy as np
        best = min(clusters, key=lambda c: float(np.linalg.norm(np.array(o['location_ue']) - np.array(c['center_ue'], float))))
        o['nearest_cluster'] = {'cluster': best['actor'], 'members': len(best['members']), 'teams': best['teams'],
                                'distance_ue': round(float(np.linalg.norm(np.array(o['location_ue']) - np.array(best['center_ue'], float))), 1),
                                'note': 'INFERRED authoring omission: unclustered team start next to the only 4-member same-team cluster'}
    out['player_starts'] = starts
    out['spawn_clusters'] = clusters
    # pickups
    pk = []
    # campaign chapters (vs_common.is_campaign): pickup factories sit in the design sublevels, not the persistent level, and most
    # are weapon factories (TnWeaponPickupFactory / TnPickupFactory); MP maps keep the original BASE-level, three-class set
    camp = is_campaign(MAP)
    pclasses = ('TnAmmoCratePickupFactory', 'TnHealthPickupFactory', 'TnOverShieldPickupFactory') +                (('TnWeaponPickupFactory', 'TnPickupFactory') if camp else ())
    def pick_actors(c):
        if not camp: return actors(c)
        return sorted((r for lv in subs for r in A.find(lv + '.TheWorld.PersistentLevel.%', c)), key=lambda r: r['opath'])
    for c in pclasses:
        for r in pick_actors(c):
            d = rec(r, ['InventoryType', 'RespawnTime', 'ShouldDisplayHighlightFx', 'TeamNum'])
            v = A.values(r['opath']); inv = v.get('InventoryType')
            if inv:
                cdo = inv.rsplit('.', 1)[0] + '.Default__' + inv.rsplit('.', 1)[1]
                iv = A.values(cdo)
                d['inventory'] = {'class': inv, 'cdo': cdo, 'payload': {k: iv.get(k) for k in iv if re.search(
                    r'Health|Ammo|Shield|Amount|Duration|Valid|Pickup(Sound|ObtainedDialog)|Respawn|Desireability|Dropped', k)}}
            d['effects'] = {k: A.values(v[k]).get('Template') for k in ('PickupEffect', 'CustomPickupEffect') if v.get(k)}
            if camp:
                d['sublevel'] = r['opath'].split('.')[0]
                if v.get('PickupMesh'):
                    mv = A.values(v['PickupMesh'])
                    d['pickup_mesh'] = {'component': v['PickupMesh'], 'mesh': mv.get('SkeletalMesh') or mv.get('StaticMesh')}
            pk.append(d)
    out['pickups'] = pk
    # objectives
    obj = {}
    for c in ('TnGameObjectivePickupFactoryFlag', 'TnFlagCapturePoint', 'TnGameObjectivePickupFactoryBomb', 'TnBombPlantPoint',
              'TnDominationPoint', 'TnKingOfTheHillZone'):
        lst = []
        for r in actors(c):
            d = rec(r)
            v = A.values(r['opath'])
            if v.get('SpawnModifier'):
                sm = A.values(v['SpawnModifier'])
                d['spawn_modifier_rules'] = [{'rule': x, 'class': (A.get(x) or {}).get('class'), 'props': clean(A.values(x))} for x in sm.get('Rules') or []]
            if v.get('PickupEffect'): d['effect_template'] = A.values(v['PickupEffect']).get('Template')
            dti = v.get('DefenderTeamIndex', 0)        # unset byte anywhere in the chain = 0
            d['defender_team'] = {0: 'TNTG_Autobots (team 0)', 1: 'TNTG_Decepticons (team 1)', 255: 'neutral (255)'}.get(dti, dti)
            if 'DefenderTeamIndex' not in v: d['defender_team_from_byte_default'] = True
            lst.append(d)
        obj[c] = lst
    out['objectives'] = obj
    # kismet
    def node(o):
        r = A.get(o); p = r['props'] or {}
        outs = {ol.get('LinkDesc'): [{'op': l['LinkedOp'].rsplit('.', 1)[-1], 'input': l.get('InputLinkIdx', 0)} for l in ol.get('Links') or [] if l.get('LinkedOp')]
                for ol in p.get('OutputLinks') or []}
        varl = {vl.get('LinkDesc'): [x.rsplit('.', 1)[-1] for x in vl.get('LinkedVariables') or [] if x] for vl in p.get('VariableLinks') or [] if vl.get('LinkedVariables')}
        keep = {k: x for k, x in p.items() if k not in ('InputLinks', 'OutputLinks', 'VariableLinks', 'ParentSequence', 'ObjPosX', 'ObjPosY',
                                                         'DrawWidth', 'DrawHeight', 'EventLinks', 'MaxWidth', 'ObjInstanceVersion', 'SequenceObjects')}
        ins = [l.get('LinkDesc') for l in A.values(o).get('InputLinks') or []]
        return {'object': o.rsplit('.', 1)[-1], 'class': r['class'], 'props': keep, 'inputs': ins, 'outputs': outs, 'variables': varl}
    def walk(seq):
        nodes = []
        for o in (A.get(seq)['props'].get('SequenceObjects') or []):
            if not o: continue
            n = node(o)
            if n['class'] == 'Sequence': n['children'] = walk(o)
            nodes.append(n)
        return nodes
    ks = {}
    for sub in subs:
        ms = sub + '.TheWorld.PersistentLevel.Main_Sequence'
        if A.get(ms) and sub == base: ks[sub] = walk(ms)
    out['kismet'] = ks
    # mode-dependent visibility (derived from the graph above)
    vis = []
    flat = {}
    def collect(ns):
        for n in ns:
            flat[n['object']] = n
            collect(n.get('children', []))
    collect(ks.get(base, []))
    for n in flat.values():
        if n['class'] == 'SeqCond_GameRuleActive':
            for l in n['outputs'].get('True', []):
                t = flat.get(l['op'])
                if t and t['class'] == 'SeqAct_ToggleHidden':
                    targets = [flat[x]['props'].get('ObjValue') for x in t['variables'].get('Target', []) if x in flat]
                    vis.append({'rule': n['props'].get('GameRule'), 'mode_comment': n['props'].get('ObjComment'),
                                'action': t['inputs'][l['input']] if l['input'] < len(t['inputs']) else l['input'],
                                'targets': [{'actor': x.rsplit('.', 1)[-1], 'mesh': A.values(A.values(x).get('StaticMeshComponent')).get('StaticMesh') if A.values(x).get('StaticMeshComponent') else None,
                                             'initially_hidden': A.values(x).get('bHidden', False), **xf(A.values(x))} for x in targets if x]})
    out['mode_dependent_visibility'] = vis
    # matinee tracks
    mats = []
    for n in flat.values():
        if n['class'] == 'SeqAct_Interp':
            data = [x for x in n['variables'].get('Data', [])]
            for dn in data:
                dobj = next((o for o in A.find(lvl + 'Main_Sequence.%' + dn) if o['class'] == 'InterpData'), None)
                if not dobj: continue
                dv = A.values(dobj['opath'])
                groups = []
                for g in dv.get('InterpGroups') or []:
                    gv = A.values(g)
                    groups.append({'group': gv.get('GroupName'), 'tracks': [{'class': (A.get(t) or {}).get('class'),
                                   'props': {k: x for k, x in A.values(t).items() if k in ('PosTrack', 'EulerTrack', 'LookupTrack', 'MoveFrame', 'RotMode', 'bUseQuatInterpolation')}}
                                   for t in gv.get('InterpTracks') or []]})
                actors_ = [flat[x]['props'].get('ObjValue') for vn, xs in n['variables'].items() if vn != 'Data' for x in xs if x in flat]
                mats.append({'action': n['object'], 'looping': n['props'].get('bLooping', False), 'length_s': dv.get('InterpLength'),
                             'groups': groups, 'actors': [{'actor': a.rsplit('.', 1)[-1], 'mesh': A.values(A.values(a).get('StaticMeshComponent')).get('StaticMesh') if A.values(a).get('StaticMeshComponent') else None, **xf(A.values(a))} for a in actors_ if a]})
    out['matinee'] = mats
    # other actors
    out['other'] = {'camera_actors': [rec(r, ['FOVAngle', 'AspectRatio', 'bConstrainAspectRatio']) for r in actors('CameraActor')],
                    'static_interp_actors': [rec(r) for s in subs for r in A.find(s + '.TheWorld.PersistentLevel.%', 'StaticInterpActor')],
                    'asset_references': {k: x for k, x in A.values(actors('TnAssetReferencesMultiplayer')[0]['opath']).items()
                                         if isinstance(x, list)} if actors('TnAssetReferencesMultiplayer') else None}
    # ------------------------------------------------------------------ validation + stats
    team_starts = [s for s in starts if s['class'] == 'TnTeamPlayerStart']
    val = {'team_starts': len(team_starts), 'ffa_starts': len(starts) - len(team_starts),
           'team_split': dict(Counter(s['effective'].get('Team') for s in team_starts)),
           'team_starts_in_a_cluster': sum(1 for s in team_starts if s['clusters']),
           'ffa_starts_in_a_cluster': sum(1 for s in starts if s['class'] != 'TnTeamPlayerStart' and s['clusters']),
           'starts_in_several_clusters': sum(1 for s in starts if len(s['clusters']) > 1),
           'cluster_sizes': dict(Counter(len(c['members']) for c in clusters)),
           'objective_volumes_with_geometry': sum(1 for lst in obj.values() for o in lst if o.get('objective_volume_polygons_gltf')),
           'objective_volumes_total': sum(1 for lst in obj.values() for o in lst if o.get('objective_volume')),
           'pickups': dict(Counter(p['class'] for p in pk)),
           'respawn_times': dict(Counter((p['class'], p['effective'].get('RespawnTime')) for p in pk).most_common())}
    out['validation'] = {k: (v if not isinstance(v, dict) else {str(a): b for a, b in v.items()}) for k, v in val.items()}
    out['notes'] += [
        'Mode tags: TDM = "Civil War" playlist (Team Deathmatch), DM = Deathmatch, DOM = Conquest, CTF = Code of Power (single flag), '
        'EXT = Countdown to Extinction (bomb run), KOTH = Power Struggle. Objectives self-declare RequiredGameRuleClass '
        '(flag: TnGameRules_SingleFlagCTF, bomb: TnGameRules_ScoreBombingRun); DOM/KOTH actors are driven by their game managers (native).',
        'TnSpawnCluster.FactionNeutralGameTypes lists modes in which the cluster is used regardless of faction (TDM/KOTH/DOM); how the '
        'spawn manager scores clusters, and the SpawnModifier rules near objectives, are native (rule objects listed as authored).',
        'Pickup payloads: TnHealthPickup AddedHealth 50 (CDO); TnAmmoCratePickup refills ValidWeaponTypes Primary/Secondary/Vehicle '
        '(amount native); TnOverShieldPickup has no authored amount/duration (native).']
    path = os.path.join(OUT, 'gameplay.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['validation'], default=str)); print('->', path)

if __name__ == '__main__':
    main()
