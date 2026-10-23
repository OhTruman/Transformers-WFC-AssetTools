"""MP_IAC_Streets Kismet relationship audit + future HUD handoff (M04).

Kismet: every sequence object in the three levels' Main_Sequence trees (recursive), with
  inputs, output edges (op + input index), variable links resolved to placed actors (SeqVar_Object.ObjValue) and the
  authored parameters; plus a flat relationship table actor <- op <- trigger chain.
HUD: authored references needed later for a multiplayer HUD: HUD/scoreboard movies, objective marker types of every
  Streets objective class (marker materials, labels, colours), objective colours/sounds, pickup dialog/sounds,
  announcer set, Scaleform symbols related to objectives/score, radar/minimap search result.
Outputs: AssetTools/manifests/streets_kismet.json, AssetTools/manifests/future_hud_handoff.json
"""
import json, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree, gfxscan  # noqa: E402
from m03_common import write, field, CONF, HIGH, PART, UNK, map_arg, map_out, map_levels# noqa: E402
from vs_common import ROOT, is_campaign  # noqa: E402

MAP = map_arg()                      # positional map name (default MP_IAC_Streets)
CAMPAIGN = is_campaign(MAP)          # campaign-only export keys (seq_inputs / seq_outputs / inputs_disabled)
LV_ = map_levels(MAP)
LEVELS = LV_['all']
SKIP = ('InputLinks', 'OutputLinks', 'VariableLinks', 'ParentSequence', 'ObjPosX', 'ObjPosY', 'DrawWidth', 'DrawHeight',
        'EventLinks', 'MaxWidth', 'ObjInstanceVersion', 'SequenceObjects', 'DefaultViewX', 'DefaultViewY', 'DefaultViewZoom')

def node(o):
    r = A.get(o); p = r['props'] or {}
    outs = {ol.get('LinkDesc'): [{'op': l['LinkedOp'], 'input_index': l.get('InputLinkIdx', 0)} for l in ol.get('Links') or [] if l.get('LinkedOp')]
            for ol in p.get('OutputLinks') or []}
    var = {}
    for vl in p.get('VariableLinks') or []:
        lst = [x for x in vl.get('LinkedVariables') or [] if x]
        if lst:
            var[vl.get('LinkDesc')] = [{'variable': x, 'class': (A.get(x) or {}).get('class'),
                                        'value': ((A.get(x) or {}).get('props') or {}).get('ObjValue') or
                                                 {k: v for k, v in ((A.get(x) or {}).get('props') or {}).items() if k not in SKIP}} for x in lst]
    ins = [l.get('LinkDesc') for l in A.values(o).get('InputLinks') or []]
    rec = {'object': o, 'class': r['class'], 'authored': {k: v for k, v in p.items() if k not in SKIP},
           'inputs': ins, 'outputs': {k: v for k, v in outs.items() if v}, 'variables': var}
    if CAMPAIGN:
        # campaign VM (Gameplay / RE KISMET_VM_CORE_RE section 2, REVIEW K4): a sub-sequence's interface is the Sequence export's own
        # InputLinks / OutputLinks (array order = the input_index / k the parent's links use). Campaign maps only: MP outputs unchanged.
        if r['class'] == 'Sequence':
            if p.get('InputLinks'):
                rec['seq_inputs'] = [{'index': k, 'label': l.get('LinkDesc'), 'event': l.get('LinkedOp'), 'disabled': bool(l.get('bDisabled'))}
                                     for k, l in enumerate(p['InputLinks'])]
            if p.get('OutputLinks'):
                rec['seq_outputs'] = [{'index': k, 'label': l.get('LinkDesc'), 'finish': l.get('LinkedOp'),
                                       'links': [{'op': x.get('LinkedOp'), 'input_index': x.get('InputLinkIdx', 0)} for x in l.get('Links') or [] if x.get('LinkedOp')]}
                                      for k, l in enumerate(p['OutputLinks'])]
        dis = [k for k, l in enumerate(p.get('InputLinks') or []) if l.get('bDisabled')]
        if dis: rec['inputs_disabled'] = dis
    return rec

def walk(seq, acc):
    for o in (A.get(seq)['props'] or {}).get('SequenceObjects') or []:
        if not o or not A.get(o): continue
        n = node(o); acc.append(n)
        if n['class'] == 'Sequence': walk(o, acc)
    return acc

# hand-written reading of the Streets graph (validated M04); every other map gets the generated summary below
STREETS_SUMMARY = {
    'map startup': 'BASE SeqEvent_GameplayStarted -> SeqAct_ActivateRemoteEvent "StartBeam" -> SkyBeam subsequence '
                   'SeqEvent_RemoteEvent "StartBeam" -> SeqAct_Interp (bLooping, InterpData 9.0 s) on the SkyBeam '
                   'StaticInterpActors; same start -> SeqCond_GameRuleActive (EXT / CTF) -> SeqAct_ToggleHidden UnHide '
                   'of the 4 objective-base InterpActors',
    'audio': 'AUDIO level: SeqEvent_Touch on TriggerVolumes -> SeqAct_AmbientAudioZone -> SeqAct_Reverb (mixer presets); '
             'AUTO_ROOM_* subsequences: SeqAct_PlayPlayerPositionalSound (random delay) - see audio_ops',
    'not present': 'no Kismet on movers other than SkyBeam, signs, doors, particles, destructibles or pickups'}

def generated_summary(allnodes, rel, audio, startup):
    """data-driven summary for any map: what starts at load, which actor classes Kismet drives, audio ops."""
    drives = defaultdict(Counter)
    for r in rel: drives[r['class']][r['linked_actor_class']] += 1
    return {'startup_events': Counter(x['class'] for x in startup),
            'ops_with_actor_links (op class -> linked actor classes)': {k: dict(v) for k, v in sorted(drives.items())},
            'matinee_ops': sum(1 for n in allnodes.values() if n['class'] == 'SeqAct_Interp'),
            'mode_conditions': sum(1 for n in allnodes.values() if n['class'] == 'SeqCond_GameRuleActive'),
            'audio_ops': dict(Counter(x['class'] for x in audio)),
            'note': 'generated from the authored graph (m04_kismet.generated_summary); trigger chains per op in actor_relationships'}

def kismet():
    lv_nodes = {}
    for lv in LEVELS:
        ms = lv + '.TheWorld.PersistentLevel.Main_Sequence'
        lv_nodes[lv] = walk(ms, [node(ms)]) if A.get(ms) else []
    allnodes = {n['object']: n for v in lv_nodes.values() for n in v}
    # incoming edges
    inc = defaultdict(list)
    for n in allnodes.values():
        for desc, ls in n['outputs'].items():
            for l in ls: inc[l['op']].append({'from': n['object'], 'from_class': n['class'], 'output': desc, 'input_index': l['input_index']})
    for o, n in allnodes.items(): n['incoming'] = inc.get(o, [])
    # relationships: every op with an actor variable, with the trigger chain walked back to an event
    def chain(o, depth=0, seen=None):
        seen = seen or set()
        if o in seen or depth > 12: return []
        seen.add(o)
        n = allnodes.get(o)
        if not n: return []
        if n['class'].startswith('SeqEvent'):
            return [[{'event': n['class'], 'object': o, 'authored': n['authored']}]]
        out = []
        for e in n['incoming']:
            for c in chain(e['from'], depth + 1, seen) or [[]]:
                tgt = allnodes.get(o)
                inp = tgt['inputs'][e['input_index']] if tgt and e['input_index'] < len(tgt['inputs']) else e['input_index']
                out.append(c + [{'op': e['from'], 'class': e['from_class'], 'output': e['output'], 'to_input': inp}])
        if not out and n['class'] == 'Sequence': out = [[{'note': 'subsequence'}]]
        return out
    rel = []
    for o, n in allnodes.items():
        for desc, vs in n['variables'].items():
            for v in vs:
                val = v['value']
                if isinstance(val, str) and '.PersistentLevel.' in val:
                    rel.append({'op': o, 'class': n['class'], 'variable_link': desc, 'linked_actor': val,
                                'linked_actor_class': (A.get(val) or {}).get('class'), 'authored_params': n['authored'],
                                'trigger_chains': chain(o)})
    # sounds / audio ops without actor links
    audio = [{'op': o, 'class': n['class'], 'authored': n['authored'], 'trigger_chains': chain(o)}
             for o, n in allnodes.items() if n['class'] in ('SeqAct_PlayPlayerPositionalSound', 'SeqAct_AmbientAudioZone', 'SeqAct_Reverb',
                                                           'SeqAct_PlaySound', 'SeqAct_Mixer')]
    startup = [{'event': o, 'class': n['class'], 'outputs': n['outputs']} for o, n in allnodes.items()
               if n['class'] in ('SeqEvent_GameplayStarted', 'SeqEvent_LevelLoaded', 'SeqEvent_LevelStartup', 'SeqEvent_SequenceActivated')]
    return {'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/m04_kismet.py',
            'counts': {lv: dict(Counter(n['class'] for n in v)) for lv, v in lv_nodes.items()},
            'startup_events': startup, 'actor_relationships': rel, 'audio_ops': audio,
            'summary': STREETS_SUMMARY if MAP == 'MP_IAC_Streets' else generated_summary(allnodes, rel, audio, startup),
            'levels': lv_nodes, 'confidence': CONF + ' (graph = authored links); runtime semantics of each SeqAct are engine/native'}

def hud():
    d = A.con()
    th = 'TransGame.Default__TnHUD'
    obj_classes = ['TnGameObjectivePickupFactoryFlag', 'TnGameObjectivePickupFactoryBomb', 'TnFlagCapturePoint', 'TnBombPlantPoint',
                   'TnDominationPoint', 'TnKingOfTheHillZone', 'TnAmmoCratePickupFactory', 'TnHealthPickupFactory', 'TnOverShieldPickupFactory']
    objs = {}
    for c in obj_classes:
        r = d.execute('SELECT opath FROM objects WHERE opath LIKE ? AND class=?', ('%.Default__' + c, c)).fetchone()
        if not r: continue
        cdo = r[0]; v = A.values(cdo)
        mt = v.get('MarkerType')
        mcdo = None
        if mt:
            pk, nm = mt.split('.'); mcdo = '%s.Default__%s' % (pk, nm)
        objs[c] = {'cdo': cdo, 'instances_in_streets': d.execute('SELECT COUNT(*) FROM objects WHERE class=? AND package LIKE ?', (c, MAP + '%')).fetchone()[0],
                   **{k: field(cdo, k) for k in ('MarkerType', 'MarkerString', 'MessageClass', 'RequiredGameRuleClass', 'CaptureColor', 'NeutralColor',
                                                 'NeutralSound', 'ContestedSound', 'CapturedSoundAutobotSound', 'CapturedSoundDecepticonSound',
                                                 'ZoneChangeSound', 'DetonateSound', 'CaptureTime', 'ScoreInterval', 'ScoreAmount') if k in v},
                   'marker_setup': A.values(mcdo) if mcdo and A.get(mcdo) else None}
    gfx = os.path.join(ROOT, 'content/UI_GFxHud_p/Hud_GFX.gfx')
    ex = gfxscan.scan(gfx)['exports'] if os.path.exists(gfx) else {}
    rx = re.compile(r'objective|flag|bomb|domin|hill|score|team|capture|marker|pickup|ammo|health|shield|radar|map|timer|announce|kill', re.I)
    sym = sorted(v for v in ex.values() if rx.search(v))
    radar = d.execute("SELECT opath, class FROM objects WHERE opath LIKE '%Radar%' OR opath LIKE '%Minimap%' OR opath LIKE '%MiniMap%' LIMIT 20").fetchall()
    wi = next((o for (o,) in A.con().execute("SELECT opath FROM objects WHERE opath >= ? AND opath < ? AND class='TnWorldInfo'",
               (LV_['base'] + '.TheWorld.PersistentLevel.', LV_['base'] + '.TheWorld.PersistentLevel/')).fetchall() if o.count('.') == 3), None)
    pick = {}
    for inv in ('TransGame.Default__TnAmmoCratePickup', 'TransGame.Default__TnHealthPickup', 'TransGame.Default__TnOverShieldPickup'):
        v = A.values(inv); pick[inv] = {k: v.get(k) for k in ('PickupSound', 'PickupObtainedDialog')}
    return {'generated_by': 'AssetTools/scripts/wfc/m04_kismet.py', 'scope': 'authored references only; the HUD is not built here',
            'hud_movies': {k: field(th, k) for k in ('HudMovie', 'DefaultHudMovie', 'ScoreboardMovie')},
            'hud_callbacks (TnHUD CDO)': {k: v for k, v in A.values(th).items() if k.endswith('CallBack') or k.endswith('Callback')},
            'temporary_observer_classes': A.values(th).get('TemporaryObserverClasses'),
            'objective_classes': objs,
            'announcer': field(wi, 'AnnouncerSoundEventSet'),
            'pickup_feedback': pick,
            'hud_gfx_symbols_matching_objective_score_terms': sym,
            'marker_material_package': 'UI_HudMarkers_p (marker materials referenced by the marker types above)',
            'radar_minimap_assets': radar or 'none found in authored.db (no radar/minimap object names)',
            'confidence': CONF}

def main():
    k = kismet(); write(map_out(MAP, 'streets_kismet.json'), k)
    h = hud(); write(map_out(MAP, 'future_hud_handoff.json'), h)
    print(k['counts'], len(k['actor_relationships']), len(k['audio_ops']))
    print({c: (v['instances_in_streets'], (v.get('MarkerType') or {}).get('value')) for c, v in h['objective_classes'].items()},
          len(h['hud_gfx_symbols_matching_objective_score_terms']), h['radar_minimap_assets'] if isinstance(h['radar_minimap_assets'], str) else len(h['radar_minimap_assets']))

if __name__ == '__main__':
    main()
