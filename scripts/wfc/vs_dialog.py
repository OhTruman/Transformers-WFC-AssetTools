"""Campaign dialog manifest (Integration 2026-10-18; design in Rebuild/docs/handoff/CAMPAIGN_AUDIO_DIALOG.md): per chapter, every
SeqAct_Conversation with its lines (cue -> wave -> INT subtitles + duration, FRA twin), speaker, FaceFX animation, ducking preset and the
Kismet events that fire it; every HmAnimNotify_Dialog cooked into the chapter with its anim and SoundEvent; and the dialog rules the
data holds (HmSoundEvent priority / group, HmSoundEventDialogGroup limits and retrigger delays). Read only; writes
manifests/next_map/<MAP>_dialog.json. Schema: docs/handoff/CAMPAIGN_DIALOG_SCHEMA.md. Campaign chapters only.

Needs work/dialog/subtitles.json (dialog_subtitles.py: per-language Duration + Subtitles from the cooked packages).

  python vs_dialog.py <MAP> [...]
"""
import glob, json, os, re, sqlite3, sys
from collections import Counter, OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from m03_common import write, map_out  # noqa: E402
from vs_common import is_campaign, ROOT  # noqa: E402
from campaign_pawn_factories import build, fired_by  # noqa: E402
from vs_matinee import var_targets  # noqa: E402

AT = os.path.dirname(os.path.dirname(HERE))
_SUB = None; _FX = None

def subtitles():
    global _SUB
    if _SUB is None: _SUB = json.load(open(os.path.join(AT, 'work', 'dialog', 'subtitles.json'), encoding='utf-8'))['waves']
    return _SUB

def facefx_index():
    """FaceFX animation name -> [(.fxa file, group)] over the 22 actor files (fxa_parse)"""
    global _FX
    if _FX is None:
        sys.path.insert(0, os.path.join(AT, 'work', 'fxa')); import fxa_parse as P
        _FX = {}
        for f in sorted(glob.glob(os.path.join(P.EA, '**', '*.fxa'), recursive=True)):
            try:
                for a in P.parse_anims(f)[2]: _FX.setdefault(a['name'], []).append((os.path.relpath(f, P.EA).replace('\\', '/'), a.get('group')))
            except Exception: pass
    return _FX

def waves_of(cue):
    """cue -> ([(<bank>.<wave>, wav path, DialogCharacter of the enclosing SoundNodeWaveEvent)], root params). A dialog cue's root holds
    one SoundNodeWaveEvent per DialogCharacter; the speaker's dialog character selects the wave (HM_Engine.SeqAct_Conversation
    .CheckSoundCueForErrors)."""
    out = []
    def walk(t, dc=None):
        if isinstance(t, dict):
            if t.get('class') == 'SoundNodeWaveEvent': dc = (t.get('params') or {}).get('DialogCharacter') or dc
            if t.get('wav'):
                rel = t['wav'].replace('\\', '/'); parts = rel.split('/')
                out.append(('%s.%s' % (parts[-2], os.path.splitext(parts[-1])[0]), rel, dc))
            elif t.get('class') in ('SoundNodeWaveEx', 'SoundNodeWave') and '.' in (t.get('node') or ''):
                # wave in the cue but not extracted to ExtractedAssets: keep it (subtitles / duration still come from the cook)
                out.append((t['node'], None, dc))
            for v in t.values(): walk(v, dc)
        elif isinstance(t, list):
            for v in t: walk(v, dc)
    root = {}
    try:
        t = A.cue(cue); walk(t); root = ((t or {}).get('tree') or {}).get('params') or {}
    except Exception: pass
    seen = set(); return [x for x in out if not (x[0] in seen or seen.add(x[0]))], root

def wave_rec(key, rel, dc=None):
    s = subtitles().get(key) or {}; it = s.get('INT') or {}; fr = s.get('FRA') or {}
    name = key.split('.', 1)[1]; m = re.match(r'(?:DX|VO)_([A-Z0-9]+)_', name)
    fx = facefx_index().get(name) or []
    # language twins: content/_LOC/<lang>/<bank>/<wave>.wav (the runtime reads these first). Derived from the wave key when the cue tree
    # has no merged content/<bank>/ path (52 waves: twins exist, merged copy absent)
    base = rel.split('content/', 1)[-1] if rel else '%s/%s.wav' % tuple(key.split('.', 1))
    loc = lambda lang: ('content/_LOC/%s/%s' % (lang, base)) if os.path.exists(os.path.join(ROOT, 'content', '_LOC', lang, base)) else None
    return OD([('wave', key), ('dialog_character', dc), ('speaker_code', m.group(1) if m else None),
               ('speaker_facefx_actor', fx[0][0].rsplit('/', 1)[-1].replace('_FaceFX.fxa', '').replace('RB_', '') if fx else None),
               ('duration', it.get('duration')), ('subtitles', it.get('subtitles')),
               ('duration_fra', fr.get('duration')), ('subtitles_fra', fr.get('subtitles')),
               ('wav', rel), ('wav_int', loc('int')), ('wav_fra', loc('FRA')),
               ('facefx', [OD([('fxa', f), ('group', g), ('anim', name)]) for f, g in fx]),
               ('subtitle_source', 'INT' if it else ('FRA only' if fr else 'none')),
               ('wav_extracted', bool(rel or loc('int') or loc('FRA'))), ('merged_wav_missing', not rel)])

def chapter(M):
    if not is_campaign(M): sys.exit('vs_dialog: campaign chapters only (%s is MP / UI)' % M)
    lvs, ops, back = build(M)
    seq_vars = {}
    for lv in lvs:
        for o in A.find(lv + '.TheWorld.PersistentLevel.%'):
            if 'SeqVar' in o['class'] and (o.get('props') or {}).get('VarName'): seq_vars.setdefault(o['props']['VarName'], []).append(o['opath'])
    convs = []; st = Counter()
    for a in sorted(o for o, x in ops.items() if x['class'] == 'SeqAct_Conversation'):
        v = A.values(a) or {}; p = ops[a]['props'] or {}; lines = []
        vls = p.get('VariableLinks') or []
        def bind(j):
            # line i: VariableLinks[2i] = speaking actor, [2i+1] = face target (HM_Engine.SeqAct_Conversation.CheckForErrors)
            if j >= len(vls): return None
            objs, how = [], []
            for x in vls[j].get('LinkedVariables') or []:
                t, h = var_targets(x, seq_vars); objs += t; how.append(h)
            return OD([('link', vls[j].get('LinkDesc')), ('actors', objs), ('via', how)])
        for i, ln in enumerate(v.get('Lines') or []):
            cue = ln.get('SoundCue'); wl, root = waves_of(cue) if cue else ([], {})
            ws = [wave_rec(k, r, dc) for k, r, dc in wl]
            spk = bind(2 * i); st['lines_speaker_bound'] += bool(spk and spk['actors'])
            st['lines'] += 1; st['lines_without_wave'] += not ws
            for w in ws: st['waves_subtitle_' + w['subtitle_source']] += 1; st['waves_with_facefx'] += bool(w['facefx'])
            lines.append(OD([('index', i), ('cue', cue), ('post_delay', ln.get('PostDelayTime')), ('speaker', spk), ('face', bind(2 * i + 1)),
                             ('cue_category', root.get('Category')), ('cue_secondary_category', root.get('SecondaryCategory')),
                             ('cue_play_mixer_preset', root.get('PlayMixerPreset')), ('cue_volume', root.get('Volume')), ('waves', ws)]))
        direct, events = fired_by(a, ops, back)
        convs.append(OD([('action', a), ('sublevel', a.split('.')[0]), ('comment', v.get('ObjComment')),
                         ('ducking_mixer_preset', v.get('DuckingMixerPreset')),
                         ('ducking', (A.values(v['DuckingMixerPreset']) or {}) if v.get('DuckingMixerPreset') else None),
                         ('outputs', [OD([('output', ol.get('LinkDesc')), ('to', [l.get('LinkedOp') for l in ol.get('Links') or []])])
                                      for ol in p.get('OutputLinks') or [] if ol.get('Links')]),
                         ('lines', lines), ('fired_by_direct', direct), ('fired_by_events', events)]))
    # anim notifies cooked into this chapter's packages: the copies share the original's object path -> parsed original
    inv = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
    pk = set(lvs) | {r[0] for lv in lvs for r in inv.execute("SELECT package FROM packages WHERE package LIKE ?", (lv + '_LOC%',))}
    nrows = [r for p_ in pk for r in inv.execute("SELECT package, opath FROM exports WHERE class = 'HmAnimNotify_Dialog' AND package = ?", (p_,))]
    notifies = OD(); unmatched = []; events_used = Counter()
    seq_cache = {}
    for pkg, op in sorted(nrows):
        if op in notifies: notifies[op]['cooked_in'].append(pkg); continue
        g = A.get(op)
        if not g: unmatched.append({'package': pkg, 'notify': op}); continue
        nv = A.values(op) or {}; seq = op.rsplit('.', 1)[0]
        if seq not in seq_cache: seq_cache[seq] = A.values(seq) or {}
        sv = seq_cache[seq]; key = next((n for n in sv.get('Notifies') or [] if n.get('Notify') == op), {})
        ev = nv.get('SoundEvent'); events_used[ev] += 1
        notifies[op] = OD([('notify', op), ('anim_set', op.split('.')[1] if op.count('.') >= 3 else None), ('anim_sequence', sv.get('SequenceName') or seq.rsplit('.', 1)[-1]),
                           ('time', key.get('Time')), ('sound_event', ev), ('min_weight', nv.get('MinWeight')), ('cooked_in', [pkg])])
    # rules: every SoundEvent used + their dialog groups up the parent chain
    rules = OD(); groups = OD()
    def group(gp):
        while gp and gp not in groups:
            gv = A.values(gp) or {}
            groups[gp] = OD([('instance_limit', gv.get('InstanceLimit')), ('retrigger_delay_min', gv.get('ReTriggerDelayMin')),
                             ('retrigger_delay_max', gv.get('ReTriggerDelayMax')), ('initial_chance_to_play', gv.get('InitialChanceToPlay')),
                             ('parent', gv.get('ParentDialogGroup')), ('other', {k: x for k, x in gv.items() if k not in (
                                 'InstanceLimit', 'ReTriggerDelayMin', 'ReTriggerDelayMax', 'InitialChanceToPlay', 'ParentDialogGroup', 'ObjName')})])
            gp = gv.get('ParentDialogGroup')
    for ev in sorted(e for e in events_used if e):
        evv = A.values(ev) or {}
        rules[ev] = OD([('dialog_priority', evv.get('DialogPriority')), ('dialog_group', evv.get('DialogGroup')), ('notifies', events_used[ev]),
                        ('other', {k: x for k, x in evv.items() if k not in ('DialogPriority', 'DialogGroup', 'ObjName')})])
        group(evv.get('DialogGroup'))
    mgr = [OD([('object', o['opath']), ('values', A.values(o['opath']) or {})]) for lv in lvs for o in A.find(lv + '.TheWorld.PersistentLevel.%', 'HmDialogEventManager')]
    rep = OD([('map', M), ('generated_by', 'AssetTools/scripts/wfc/vs_dialog.py'),
              ('source', 'manifests/authored.db (effective values); work/dialog/subtitles.json (per-language cooked waves); FaceFX .fxa; schema docs/handoff/CAMPAIGN_DIALOG_SCHEMA.md'),
              ('counts', OD([('conversations', len(convs)), ('lines', st['lines']), ('lines_without_wave', st['lines_without_wave']), ('lines_speaker_bound', st['lines_speaker_bound']),
                             ('waves_with_int_subtitles', st['waves_subtitle_INT']), ('waves_fra_only', st['waves_subtitle_FRA only']),
                             ('waves_without_subtitles', st['waves_subtitle_none']), ('waves_with_facefx', st['waves_with_facefx']),
                             ('conversations_with_firing_event', sum(1 for c in convs if c['fired_by_events'])),
                             ('anim_notify_copies', len(nrows)), ('anim_notifies_distinct', len(notifies)), ('anim_notifies_unmatched', len(unmatched)),
                             ('sound_events', len(rules)), ('dialog_groups', len(groups)), ('dialog_event_managers', len(mgr))])),
              ('conversations', convs), ('anim_notifies', list(notifies.values())), ('anim_notifies_unmatched', unmatched),
              ('sound_event_rules', rules), ('dialog_groups', groups), ('dialog_event_managers', mgr)])
    write(map_out(M, 'streets_dialog.json'), rep)
    print(M, json.dumps(rep['counts']), flush=True)
    return rep

if __name__ == '__main__':
    for M in sys.argv[1:]: chapter(M)
