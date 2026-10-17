"""Level streaming of a map (campaign chapters): which sublevel every world.glb node belongs to, and the authored streaming states that
load / show the sublevels. Separate file, so world.glb and the MP outputs stay byte-identical.

Authored model (authored DB; RE decomp Engine.LevelStreamingState, TransGame.TnWorldInfo, Engine.Checkpoint):
  - the persistent level (<MAP>_BASE_m) lists its sublevels as LevelStreamingKismet objects (PackageName)
  - High Moon's LevelStreamingState objects are named sets {Levels: [{LevelName, LevelVisible}]}; TnWorldInfo.StreamingStates lists
    them and InitialStreamingState picks the start state; a Checkpoint carries the StreamingState it restores
  - Kismet SeqAct_SetStreamingState (StreamingState) switches state, usually fired by a SeqEvent_RemoteEvent; SeqAct_FlushLevelStreaming
    blocks until loads finish
  - CINE sublevels (*_CINE_*): hidden outside their matinee (tagged; the matinees they hold are listed). PROVISIONAL: the visibility
    switch for these comes from the states / Kismet above, the tag is the export-side default
Output: <VS>/Maps/<MAP>/streaming.json

  python vs_streaming.py <MAP>
"""
import json, os, re, sys
from collections import Counter, OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from vs_common import VS, read_glb  # noqa: E402
from m03_common import map_levels  # noqa: E402

def kind(lv):
    n = lv.lower()
    for k, pats in (('cine', ('_cine',)), ('audio', ('_audio', '_aud_', 'audio_m', '_aud_m')), ('music', ('_music',)),
                    ('design', ('_design', '_dsn', '_vig')), ('art', ('_art',))):
        if any(p in n for p in pats): return k
    return 'base' if n.endswith('_base_m') else 'other'

def triggers(op):
    """remote events (EventName) and other ops whose OutputLinks fire `op` (one hop)"""
    out = []
    for src, prop in A.refs_to(op):
        if prop != 'OutputLinks': continue
        g = A.get(src) or {}
        out.append(OD([('op', src), ('class', g.get('class')), ('event_name', ((g.get('props') or {}).get('EventName')))]))
    return out

def main(M):
    md = os.path.join(VS, 'Maps', M); mj = json.load(open(os.path.join(md, 'map.json'), encoding='utf-8'))
    base = map_levels(M)['base']; subs = mj['sublevels']
    lsk = {(o['props'] or {}).get('PackageName', '').lower(): o['opath'] for o in A.find(base + '.TheWorld.%', 'LevelStreamingKismet')}
    wi = next((o for o in A.find(base + '.TheWorld.PersistentLevel.%') if o['class'] in ('TnWorldInfo', 'WorldInfo')), None)
    wp = (wi or {}).get('props') or {}
    states = OD()
    for sp in wp.get('StreamingStates') or [o['opath'] for o in A.find(base + '.%', 'LevelStreamingState')]:
        g = A.get(sp) or {}
        states[sp] = OD([('name', sp.rsplit('.', 1)[-1]), ('levels', [OD([('level', x.get('LevelName')), ('visible', x.get('LevelVisible'))])
                                                                      for x in (g.get('props') or {}).get('Levels') or []]),
                         ('checkpoints', []), ('set_by', [])])
    for s in states:
        for src, prop in A.refs_to(s):
            c = (A.get(src) or {}).get('class')
            if c == 'Checkpoint': states[s]['checkpoints'].append(src)
            elif c == 'SeqAct_SetStreamingState': states[s]['set_by'].append(OD([('action', src), ('triggered_by', triggers(src))]))
    # world.glb node -> sublevel (SMCA nodes by component path; actor nodes by actor name through props.json; BSP_<level>)
    props = json.load(open(os.path.join(md, 'props.json'), encoding='utf-8'))['props']
    by_comp = {p['component']: p['sublevel'] for p in props if p.get('component')}
    by_actor = {}
    for p in props: by_actor.setdefault(p['actor'], set()).add(p['sublevel'])
    g, _ = read_glb(os.path.join(md, 'world.glb')); nodes = OD(); amb = 0
    for i, n in enumerate(g['nodes']):
        x = n.get('extras') or {}; nm = n.get('name') or 'node_%d' % i
        if x.get('kind') and nm.startswith('BSP_'): lv = nm[4:]
        elif x.get('component') in by_comp: lv = by_comp[x['component']]
        elif x.get('component'): lv = x['component'].split('.')[0]
        elif len(by_actor.get(x.get('actor'), ())) == 1: lv = next(iter(by_actor[x['actor']]))
        else: lv = sorted(by_actor.get(x.get('actor'), ())) or None; amb += 1
        nodes['%d:%s' % (i, nm)] = lv
    per = Counter(v for v in nodes.values() if isinstance(v, str))
    interp = Counter(o['opath'].split('.')[0] for o in A.find(M + '%', 'SeqAct_Interp'))
    initial = wp.get('InitialStreamingState')
    sl = OD()
    for lv in subs:
        k = kind(lv)
        sl[lv] = OD([('kind', k), ('streaming_object', lsk.get(lv.lower())), ('persistent', lv.lower() == (base or '').lower()),
                     ('world_glb_nodes', per.get(lv, 0)),
                     ('in_states', [states[s]['name'] for s in states if any((l['level'] or '').lower() == lv.lower() for l in states[s]['levels'])]),
                     ('in_initial_state', bool(initial and any((l['level'] or '').lower() == lv.lower() for l in states.get(initial, {}).get('levels', [])))),
                     ('hidden_outside_matinee', k == 'cine'), ('matinees_in_level', interp.get(lv, 0)),
                     # RE (CAMPAIGN_STREAMING_RE.md, b68e7aa): an in-place checkpoint restart reloads every level that is NOT
                     # bIsFullyStatic; fully-static levels in the checkpoint's state are kept
                     ('fully_static', bool(((A.get(lsk.get(lv.lower())) or {}).get('props') or {}).get('bIsFullyStatic')) if lsk.get(lv.lower()) else None)])
    # checkpoint -> the StreamingState it restores (start-from-checkpoint and restart use it instead of InitialStreamingState; RE b68e7aa)
    cps = []
    for o in sorted(A.find(base + '.TheWorld.PersistentLevel.%', 'Checkpoint'), key=lambda o: o['opath']):
        if o['opath'].count('.') != 3: continue
        v = A.values(o['opath']) or {}
        cps.append(OD([('checkpoint', o['opath']), ('tag', v.get('Tag')), ('display_order', v.get('DisplayOrder')),
                       ('streaming_state', v.get('StreamingState')),
                       ('streaming_state_name', (v.get('StreamingState') or '').rsplit('.', 1)[-1] or None),
                       ('auxilliary_spawn_points', v.get('AuxilliarySpawnPoints') or [])]))
    out = OD([('map', M), ('generated_by', 'AssetTools/scripts/wfc/vs_streaming.py'),
              ('sources', 'authored DB (LevelStreamingKismet, LevelStreamingState, TnWorldInfo, Checkpoint, SeqAct_SetStreamingState); '
                          'RE decomp Engine.LevelStreamingState, TransGame.TnWorldInfo, Engine.Checkpoint (StreamingState)'),
              ('persistent_level', base), ('initial_state', initial), ('sublevels', sl), ('states', list(states.values())),
              ('flush_actions', len(A.find(base + '.%', 'SeqAct_FlushLevelStreaming'))), ('checkpoints', cps),
              ('node_sublevel', nodes), ('nodes_ambiguous_or_unassigned', amb)])
    json.dump(out, open(os.path.join(md, 'streaming.json'), 'w', encoding='utf-8'), indent=1)
    print(M, len(sl), 'sublevels', len(states), 'states, initial', initial, '|', len(nodes), 'nodes tagged,', amb, 'ambiguous/unassigned', flush=True)

if __name__ == '__main__':
    main(sys.argv[1])
