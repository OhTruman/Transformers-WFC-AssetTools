"""Campaign pawn-factory manifest (Integration 2026-10-17): every SeqAct_TnPawnFactory of a chapter with what it spawns, where, for
which faction, which Kismet event fires it, and its sublevel - the data Gameplay's campaign spawn system needs after streaming and
Kismet. Read only (authored.db); writes manifests/next_map/<MAP>_pawn_factories.json.

Per action:
  factory          the ActorFactory object: class (TnActorFactoryAI / TnActorFactoryOmegaBatteryDestructible ...), effective props:
                   AiCharacterDefinitionTemplate (the character archetype), FactionTeam, StartingFormOverride, AlertToPlayer,
                   PawnClass / ControllerClass / TeamIndex (class defaults)
  spawn points     SpawnPoints property + objects linked to the "Spawn Point" variable link, with class and location (UE)
  spawn count      the "Spawn Count" SeqVar_Int (else SpawnCount), MaxNumSpawnedInWorld
  outputs          output links (All Pawns Spawned / Killed ...) and the "Spawned" variable name
  fired_by         walking the Kismet graph backwards from the "Spawn Actor" input (input index 0) to the nearest events
                   (SeqEvent_* / TnSeqEvent_*: class, EventName / Originator), at most DEPTH ops deep; the direct upstream ops too
  character vars   TnSeqVar_Character objects linked to the action (if any)

  python campaign_pawn_factories.py <MAP> [...]
"""
import json, os, sys
from collections import Counter, defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from m03_common import write, map_out  # noqa: E402
from vs_common import VS  # noqa: E402

DEPTH = 12
SKIP = ('ObjPosX', 'ObjPosY', 'DrawWidth', 'DrawHeight', 'InputLinks', 'OutputLinks', 'VariableLinks', 'EventLinks', 'ParentSequence')

def levels(M):
    return json.load(open(os.path.join(VS, 'Maps', M, 'map.json'), encoding='utf-8'))['sublevels']

def loc(o):
    v = A.values(o) or {}; L = v.get('Location')
    return [L.get('X'), L.get('Y'), L.get('Z')] if isinstance(L, dict) else None

def build(M):
    lvs = levels(M); ops = {}
    for lv in lvs:
        for o in A.find(lv + '.TheWorld.PersistentLevel.%'):
            p = o.get('props') or {}
            if 'OutputLinks' in p or 'InputLinks' in p or o['class'].startswith(('SeqEvent', 'TnSeqEvent', 'SeqAct', 'TnSeqAct', 'Sequence')):
                ops[o['opath']] = o
    back = defaultdict(list)                       # dst -> [(src, output desc, input index)]
    for src, o in ops.items():
        for ol in (o['props'] or {}).get('OutputLinks') or []:
            for l in ol.get('Links') or []:
                if l.get('LinkedOp'): back[l['LinkedOp']].append((src, ol.get('LinkDesc'), l.get('InputLinkIdx', 0)))
    return lvs, ops, back

def event_rec(o):
    v = A.values(o['opath']) or {}
    return {'event': o['opath'], 'class': o['class'], 'EventName': v.get('EventName'), 'Originator': v.get('Originator'),
            'ObjComment': v.get('ObjComment'), 'MaxTriggerCount': v.get('MaxTriggerCount')}

def fired_by(op, ops, back):
    direct = [{'op': s, 'class': ops[s]['class'] if s in ops else None, 'output': d} for s, d, i in back.get(op, []) if i == 0]
    seen = {op}; q = deque((s, 1) for s, d, i in back.get(op, []) if i == 0); events = []
    while q:
        cur, depth = q.popleft()
        if cur in seen: continue
        seen.add(cur); o = ops.get(cur)
        if not o: continue
        if o['class'].startswith(('SeqEvent', 'TnSeqEvent')): events.append(dict(event_rec(o), depth=depth)); continue
        if depth < DEPTH:
            for s, d, i in back.get(cur, []): q.append((s, depth + 1))
    return direct, events

def chapter(M):
    lvs, ops, back = build(M)
    acts = sorted(o for o, x in ops.items() if x['class'] == 'SeqAct_TnPawnFactory')
    out = []
    for a in acts:
        p = ops[a]['props'] or {}; v = A.values(a) or {}
        f = p.get('Factory'); fv = A.values(f) if f else {}
        fac = {'object': f, 'class': (A.get(f) or {}).get('class') if f else None,
               **{k: fv.get(k) for k in ('AiCharacterDefinitionTemplate', 'FactionTeam', 'StartingFormOverride', 'AlertToPlayer',
                                         'PlaySpawnAnimation', 'PawnClass', 'ControllerClass', 'TeamIndex', 'NewActorClass',
                                         'Sentry', 'Blueprint', 'StaticMesh', 'ParticleSystem', 'DamageRadius', 'DamageAmount', 'Health', 'Fuse',
                                         'LocalLinearVelocity', 'InitialVelocity') if k in fv}}
        # one archetype field per factory kind: AI character definition, sentry turret definition, destructible blueprint, debris mesh,
        # particle system, or 'RollerMine' (the roller-mine factory has only damage / velocity parameters)
        fac['archetype'] = next((fv[k] for k in ('AiCharacterDefinitionTemplate', 'Sentry', 'Blueprint', 'StaticMesh', 'ParticleSystem') if fv.get(k)),
                                'RollerMine' if fac['class'] == 'TnActorFactoryRollerMine' else None)
        sp = list(p.get('SpawnPoints') or []); count = None; spawned_var = None; charvars = []
        for vl in p.get('VariableLinks') or []:
            for lv_ in vl.get('LinkedVariables') or []:
                g = A.get(lv_) or {}; gv = g.get('props') or {}
                if vl.get('LinkDesc') == 'Spawn Point' and gv.get('ObjValue') and gv['ObjValue'] not in sp: sp.append(gv['ObjValue'])
                if vl.get('LinkDesc') == 'Spawn Count': count = gv.get('IntValue', 0)
                if vl.get('LinkDesc') == 'Spawned': spawned_var = gv.get('VarName')
                if g.get('class') == 'TnSeqVar_Character': charvars.append({'var': lv_, **{k: x for k, x in gv.items() if k not in SKIP}})
        direct, events = fired_by(a, ops, back)
        out.append({'action': a, 'sublevel': a.split('.')[0], 'sequence': p.get('ParentSequence'), 'comment': v.get('ObjComment'),
                    'factory': fac,
                    'spawn_points': [{'object': s, 'class': (A.get(s) or {}).get('class'), 'location_ue': loc(s)} for s in sp],
                    'spawn_count': count if count is not None else v.get('SpawnCount'), 'max_spawned_in_world': v.get('MaxNumSpawnedInWorld'),
                    'outputs': [{'output': ol.get('LinkDesc'), 'to': [l.get('LinkedOp') for l in ol.get('Links') or []]}
                                for ol in p.get('OutputLinks') or [] if ol.get('Links')],
                    'spawned_variable': spawned_var, 'character_variables': charvars,
                    'fired_by_direct': direct, 'fired_by_events': events})
    nvar = sum(1 for o in ops.values() if o['class'] == 'TnSeqVar_Character')
    nvar_all = sum(1 for lv in lvs for _ in A.find(lv + '.TheWorld.PersistentLevel.%', 'TnSeqVar_Character'))
    rep = {'map': M, 'generated_by': 'AssetTools/scripts/wfc/campaign_pawn_factories.py',
           'source': 'manifests/authored.db (Kismet ops of every exported sublevel)',
           'counts': {'pawn_factories': len(out),
                      'by_factory_class': dict(Counter(x['factory']['class'] for x in out)),
                      'by_archetype': dict(Counter((x['factory'].get('archetype') or '-').rsplit('.', 1)[-1] for x in out).most_common()),
                      'by_faction': dict(Counter((x['factory'].get('FactionTeam') or '-').rsplit('.', 1)[-1] for x in out)),
                      'with_spawn_points': sum(1 for x in out if x['spawn_points']),
                      'with_firing_event': sum(1 for x in out if x['fired_by_events']),
                      'with_direct_input': sum(1 for x in out if x['fired_by_direct']),
                      'TnSeqVar_Character_in_levels': nvar_all, 'TnSeqVar_Character_linked_to_factories': sum(len(x['character_variables']) for x in out)},
           'pawn_factories': out}
    write(map_out(M, 'streets_pawn_factories.json'), rep)
    print(M, json.dumps({k: v for k, v in rep['counts'].items() if k != 'by_archetype'}), flush=True)
    return rep

if __name__ == '__main__':
    for M in sys.argv[1:]: chapter(M)
