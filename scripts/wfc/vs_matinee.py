"""Campaign matinee export (Integration 2026-10-18): every InterpData of a chapter with its groups and tracks, the actors each group
binds to (through the SeqAct_Interp that plays it) and the Kismet events that fire it - the data side of the campaign matinee
player. Read only (authored.db, effective values = authored + class defaults); writes manifests/next_map/<MAP>_matinee.json.
Schema and track coverage: docs/handoff/CAMPAIGN_MATINEE_SCHEMA.md. Campaign chapters only (refuses MP_ / UI_ maps).

  python vs_matinee.py <MAP> [...]
"""
import json, os, sys
from collections import Counter, OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from m03_common import write, map_out  # noqa: E402
from vs_common import is_campaign  # noqa: E402
from campaign_pawn_factories import build, fired_by  # noqa: E402

def curve(c):
    """FInterpCurve -> [{t, v, arrive, leave, mode}] (values as authored: UE units / degrees / unitless)"""
    return [OD([('t', p.get('InVal')), ('v', p.get('OutVal')), ('arrive', p.get('ArriveTangent')), ('leave', p.get('LeaveTangent')),
                ('mode', p.get('InterpMode'))]) for p in ((c or {}).get('Points') or [])]

# per track class: the decoded fields (effective values). A class not listed here is exported raw and counted as undecoded.
TRACKS = {
    'InterpTrackMove': lambda v: OD([('move_frame', v.get('MoveFrame')), ('rot_mode', v.get('RotMode')),
                                     ('use_quat_interpolation', v.get('bUseQuatInterpolation')), ('pos', curve(v.get('PosTrack'))),
                                     ('euler', curve(v.get('EulerTrack'))),
                                     ('lookup', [OD([('t', p.get('Time')), ('group', p.get('GroupName'))]) for p in ((v.get('LookupTrack') or {}).get('Points') or [])])]),
    'InterpTrackDirector': lambda v: OD([('cuts', [OD([('t', k.get('Time')), ('camera_group', k.get('TargetCamGroup')), ('transition', k.get('TransitionTime'))])
                                                   for k in v.get('CutTrack') or []])]),
    'InterpTrackSound': lambda v: OD([('keys', [OD([('t', k.get('Time')), ('cue', k.get('Sound')), ('volume', k.get('Volume')), ('pitch', k.get('Pitch'))])
                                                for k in v.get('Sounds') or []]), ('volume_pitch', curve(v.get('VectorTrack'))),
                                      ('continue_on_end', v.get('bContinueSoundOnMatineeEnd')), ('continue_on_skip', v.get('bContinueSoundOnMatineeSkip'))]),
    'InterpTrackEvent': lambda v: OD([('keys', [OD([('t', k.get('Time')), ('event', k.get('EventName'))]) for k in v.get('EventTrack') or []]),
                                      ('fire_forwards', v.get('bFireEventsWhenForwards')), ('fire_backwards', v.get('bFireEventsWhenBackwards')),
                                      ('fire_when_jumping_forwards', v.get('bFireEventsWhenJumpingForwards'))]),
    'InterpTrackToggle': lambda v: OD([('keys', [OD([('t', k.get('Time')), ('action', k.get('ToggleAction'))]) for k in v.get('ToggleTrack') or []]),
                                       ('fire_when_jumping_forwards', v.get('bFireEventsWhenJumpingForwards'))]),
    'InterpTrackAnimControl': lambda v: OD([('slot', v.get('SlotName')), ('keys', [OD([('t', k.get('StartTime')), ('anim', k.get('AnimSeqName')),
                                            ('start_offset', k.get('AnimStartOffset')), ('end_offset', k.get('AnimEndOffset')), ('rate', k.get('AnimPlayRate')),
                                            ('looping', k.get('bLooping')), ('reverse', k.get('bReverse'))]) for k in v.get('AnimSeqs') or []]),
                                            ('weight', curve(v.get('FloatTrack')))]),
    'InterpTrackFaceFX': lambda v: OD([('keys', [OD([('t', k.get('StartTime')), ('group', k.get('FaceFXGroupName')), ('anim', k.get('FaceFXSeqName'))])
                                                 for k in v.get('FaceFXSeqs') or []])]),
    'InterpTrackFloatProp': lambda v: OD([('property', v.get('PropertyName')), ('curve', curve(v.get('FloatTrack')))]),
    'InterpTrackVectorProp': lambda v: OD([('property', v.get('PropertyName')), ('curve', curve(v.get('VectorTrack')))]),
    'InterpTrackColorProp': lambda v: OD([('property', v.get('PropertyName')), ('curve', curve(v.get('VectorTrack')))]),
    'InterpTrackFloatMaterialParam': lambda v: OD([('param', v.get('ParamName')), ('materials', v.get('Materials') or v.get('Material')), ('curve', curve(v.get('FloatTrack')))]),
    'InterpTrackVectorMaterialParam': lambda v: OD([('param', v.get('ParamName')), ('materials', v.get('Materials') or v.get('Material')), ('curve', curve(v.get('VectorTrack')))]),
    'InterpTrackActorFloatMaterialParam': lambda v: OD([('param', v.get('ParamName')), ('curve', curve(v.get('FloatTrack')))]),
    'InterpTrackActorVectorMaterialParam': lambda v: OD([('param', v.get('ParamName')), ('curve', curve(v.get('VectorTrack')))]),
    'InterpTrackFade': lambda v: OD([('curve', curve(v.get('FloatTrack'))), ('persist_fade', v.get('bPersistFade'))]),
    'InterpTrackSlomo': lambda v: OD([('curve', curve(v.get('FloatTrack')))]),
    'InterpTrackColorScale': lambda v: OD([('curve', curve(v.get('VectorTrack')))]),
}
TRACKS['InterpTrackDialog'] = TRACKS['InterpTrackSound']

def var_targets(var, seq_vars, depth=0):
    """a Kismet variable -> (bound objects, how). Unresolvable kinds are reported, not guessed."""
    g = A.get(var) or {}; c = g.get('class') or ''; p = A.values(var) or {}
    if c == 'SeqVar_Object':
        if p.get('ObjValue'): return [p['ObjValue']], 'object'
        # empty in the authored data: filled at runtime, typically by a pawn factory's "Spawned" output -> name the writers
        out = []; written = []
        # the variable may be wired into a sub-sequence's variable link; inside, a SeqVar_External with that label is the same
        # variable, so its writers count too (e.g. A2 "AirRaid" -> Air_Raid sequence)
        cands = [var]
        for src, prop in A.refs_to(var):
            g2 = A.get(src) or {}
            if prop != 'VariableLinks' or g2.get('class') != 'Sequence': continue
            for vl in (g2.get('props') or {}).get('VariableLinks') or []:
                if var not in (vl.get('LinkedVariables') or []): continue
                for e in A.find(src + '.%', 'SeqVar_External'):
                    ev = A.values(e['opath']) or {}
                    if (ev.get('ExtVarName') or ev.get('VariableLabel')) == vl.get('LinkDesc') and ev.get('ParentSequence') == src: cands.append(e['opath'])
        for cv, (src, prop) in ((cv, r) for cv in cands for r in A.refs_to(cv)):
            g2 = A.get(src) or {}; c2 = g2.get('class') or ''
            if prop != 'VariableLinks' or c2 == 'Sequence': continue
            for vl in (g2.get('props') or {}).get('VariableLinks') or []:
                if cv not in (vl.get('LinkedVariables') or []): continue
                if 'PawnFactory' in c2 and vl.get('LinkDesc') in ('Spawned', 'Spawned List'):
                    f = (g2.get('props') or {}).get('Factory'); fv = A.values(f) if f else {}
                    arch = next((fv[k] for k in ('AiCharacterDefinitionTemplate', 'Sentry', 'Blueprint') if fv.get(k)), None)
                    out.append('SPAWNED_BY:%s%s' % (src, (' (%s)' % arch) if arch else ''))
                elif vl.get('bWriteable') or 'SeqEvent' in c2:
                    # any other op that writes it (writeable link, or an event's Instigator / Originator output)
                    written.append('WRITTEN_BY:%s [%s.%s]' % (src, c2, vl.get('LinkDesc')))
        if out: return out + written, 'runtime_spawned'
        return written, 'runtime_written' if written else 'object_empty'
    if c == 'SeqVar_ObjectList': return list(p.get('ObjList') or []), 'object_list'
    if c == 'SeqVar_Player': return ['PLAYER' + ('' if p.get('bAllPlayers', True) else ':%s' % p.get('PlayerIdx', 0))], 'player'
    if c == 'TnSeqVar_Character':
        # a character slot, not a placed actor: the runtime binds the pawn of this character definition (ChassisTypePathName)
        return (['CHARACTER:' + p['ChassisTypePathName']] if p.get('ChassisTypePathName') else []), 'character'
    if c == 'SeqVar_Named':
        hits = [v for v in seq_vars.get(p.get('FindVarName'), []) if v != var]
        out = []
        for h in hits: out += var_targets(h, seq_vars, depth + 1)[0] if depth < 8 else []
        return out, 'named:%s' % p.get('FindVarName') + ('' if hits else ' (no variable with that VarName in the exported levels)')
    if c == 'SeqVar_External':
        # the parent sequence's variable link named ExtVarName carries the variable(s) from the enclosing sequence
        seq = p.get('ParentSequence'); sp = (A.get(seq) or {}).get('props') or {}; out = []
        for vl in sp.get('VariableLinks') or []:
            if vl.get('LinkDesc') == (p.get('ExtVarName') or p.get('VariableLabel')):   # this cook stores the name as VariableLabel
                for x in vl.get('LinkedVariables') or []: out += var_targets(x, seq_vars, depth + 1)[0] if depth < 8 else []
        return out, 'external:%s' % (p.get('ExtVarName') or p.get('VariableLabel'))
    return [], 'unresolved:%s' % c

def chapter(M):
    if not is_campaign(M): sys.exit('vs_matinee: campaign chapters only (%s is MP / UI)' % M)
    lvs, ops, back = build(M)
    seq_vars = {}
    for lv in lvs:
        for o in A.find(lv + '.TheWorld.PersistentLevel.%'):
            if 'SeqVar' in o['class'] and (o.get('props') or {}).get('VarName'): seq_vars.setdefault(o['props']['VarName'], []).append(o['opath'])
    players = {}                                                 # InterpData -> [SeqAct_Interp records]
    for a, o in ops.items():
        if o['class'] != 'SeqAct_Interp' and not o['class'].endswith('SeqAct_Interp'): continue
        p = o['props'] or {}; v = A.values(a) or {}; data = None; binds = OD()
        for vl in p.get('VariableLinks') or []:
            lv_ = vl.get('LinkedVariables') or []
            if vl.get('LinkDesc') == 'Data':
                for x in lv_:
                    g = A.get(x) or {}
                    data = x if g.get('class') == 'InterpData' else ((g.get('props') or {}).get('ObjValue') or data)
                continue
            objs, how = [], []
            for x in lv_:
                t, h = var_targets(x, seq_vars); objs += t; how.append(h)
            binds[vl.get('LinkDesc')] = OD([('actors', objs), ('via', how)])
        direct, events = fired_by(a, ops, back)
        players.setdefault(data, []).append(OD([('action', a), ('class', o['class']), ('comment', v.get('ObjComment')),
                                                 ('looping', v.get('bLooping')), ('play_rate', v.get('PlayRate')), ('rewind_on_play', v.get('bRewindOnPlay')),
                                                 ('no_reset_on_rewind', v.get('bNoResetOnRewind')), ('rewind_if_already_playing', v.get('bRewindIfAlreadyPlaying')),
                                                 ('force_start_position', v.get('bForceStartPos')), ('force_start_time', v.get('ForceStartPosition')),
                                                 ('skippable', v.get('bIsSkippable')), ('group_bindings', binds),
                                                 ('fired_by_direct', direct), ('fired_by_events', events)]))
    datas = sorted({o['opath'] for lv in lvs for o in A.find(lv + '.TheWorld.PersistentLevel.%', 'InterpData')})
    out = []; tc = Counter(); undecoded = Counter(); unknown_keys = Counter(); unbound = 0; gstates = Counter(); ngroups = 0; ndir = 0; unres = Counter()
    for d in datas:
        dv = A.values(d) or {}; groups = []
        pl = players.get(d, [])
        for gp in dv.get('InterpGroups') or []:
            gg = A.get(gp) or {}; gv = A.values(gp) or {}; ngroups += 1
            name = gv.get('GroupName'); ndir += gg.get('class') == 'InterpGroupDirector'
            tracks = []
            for tp in gv.get('InterpTracks') or []:
                tg = A.get(tp) or {}; tv = A.values(tp) or {}; c = tg.get('class'); tc[c] += 1
                rec = OD([('track', tp.rsplit('.', 1)[-1]), ('class', c), ('title', tv.get('TrackTitle')), ('disabled', bool(tv.get('bDisableTrack')))])
                if c in TRACKS: rec.update(TRACKS[c](tv))
                else:
                    undecoded[c] += 1; rec['raw'] = {k: x for k, x in (tg.get('props') or {}).items()}
                tracks.append(rec)
            bound = OD((x['action'], x['group_bindings'].get(name)) for x in pl if name in x['group_bindings'])
            gstate = ('director' if gg.get('class') == 'InterpGroupDirector' else 'bound' if any((b or {}).get('actors') for b in bound.values())
                      else 'empty_link' if bound and not any((b or {}).get('via') for b in bound.values()) else 'no_link' if not bound else 'unresolved')
            acts = [a for b in bound.values() for a in (b or {}).get('actors', [])]
            if gstate == 'bound' and all(a.startswith(('SPAWNED_BY:', 'WRITTEN_BY:', 'CHARACTER:', 'PLAYER')) for a in acts):
                gstate = 'bound_runtime'          # resolved to who fills it at runtime (spawn / Kismet write / character / player)
            gstates[gstate] += 1
            if gg.get('class') != 'InterpGroupDirector' and not any((b or {}).get('actors') for b in bound.values()): unbound += 1
            for b in bound.values():
                for h in (b or {}).get('via', []):
                    if h.startswith('unresolved'): unres[h] += 1
            groups.append(OD([('name', name), ('class', gg.get('class')), ('binding', gstate), ('bound', bound), ('tracks', tracks)]))
        out.append(OD([('interp_data', d), ('sublevel', d.split('.')[0]), ('length', dv.get('InterpLength')), ('path_building', dv.get('bShouldBakeAndPrune')),
                       ('played_by', pl), ('groups', groups)]))
    orphan = [x['action'] for k, v in players.items() if k not in set(datas) for x in v]
    rep = OD([('map', M), ('generated_by', 'AssetTools/scripts/wfc/vs_matinee.py'),
              ('source', 'manifests/authored.db, effective values (authored + class defaults); schema docs/handoff/CAMPAIGN_MATINEE_SCHEMA.md'),
              ('counts', OD([('interp_data', len(out)), ('played', sum(1 for x in out if x['played_by'])), ('not_played_by_any_seqact_interp', sum(1 for x in out if not x['played_by'])),
                             ('seqact_interp', sum(len(v) for v in players.values())), ('seqact_interp_without_data_in_levels', len(orphan)),
                             ('groups', ngroups), ('director_groups', ndir), ('groups_without_bound_actor', unbound), ('group_binding', dict(gstates)),
                             ('tracks_by_class', OD(tc.most_common())), ('undecoded_track_classes', dict(undecoded)), ('unresolved_bindings', dict(unres))])),
              ('matinees', out)])
    write(map_out(M, 'streets_matinee.json'), rep)
    print(M, json.dumps({k: v for k, v in rep['counts'].items() if k != 'tracks_by_class'}), flush=True)
    return rep

if __name__ == '__main__':
    for M in sys.argv[1:]: chapter(M)
