"""Authored ambient-audio setup of a map, from manifests/authored.db (authored.py).

Output: ExtractedAssets/VerticalSlice/Maps/<MAP>/audio.json
  emitters.point   AmbientSound actors       (AudioComponent.SoundCue, location, tag, DrawScale)
  emitters.volume  HmAmbientSoundVolumeEmitter (cue, box: Location/Rotation/DrawScale3D, class Radius)
  emitters.line    HmAmbientSoundLineEmitter   (cue, Location/Rotation/DrawScale3D, class LineLength)
  zones            Kismet: SeqEvent_Touch(TriggerVolume) -> SeqAct_AmbientAudioZone -> SeqAct_Reverb preset
                   + sub-sequence START/STOP -> SeqAct_PlayPlayerPositionalSound one-shot pools;
                   trigger polygons (glTF) joined from collision.json
  reverb_presets   SoundConfig.SoundMixerProperties: MixerPresets timing/priority + MASTER_WET DSP
                   (Reverb I3DL2-style params, Echo, filters) for every preset the map uses
  categories       SoundCategories used by the map's cues (volume, IsMusic, DSPEffectConfig raw int)
  cues             full SoundCue graphs (node tree, root attenuation/category, waves with WAV paths)
  music            world-info music/audio objects of each sublevel
Every value is authored data (CONFIRMED) unless an entry's 'confidence' says otherwise.
  python vs_audio.py [MAP]
"""
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from vs_common import VS, ue_to_gltf_matrix, ue_actor_matrix, ue_points_to_gltf  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
UURAD = 360.0 / 65536.0

def v3(v, keys=('X', 'Y', 'Z'), d=0.0):
    return [float((v or {}).get(k, d)) for k in keys] if isinstance(v, dict) else (list(v) if v else [d, d, d])

def xf(p):
    loc = v3(p.get('Location')); rot = v3(p.get('Rotation'), ('Pitch', 'Yaw', 'Roll'))
    ds = float(p.get('DrawScale', 1.0)); ds3 = v3(p.get('DrawScale3D'), d=1.0)
    M = ue_actor_matrix(loc, rot, ds, ds3)
    return {'location_ue': loc, 'rotation_ue': rot, 'yaw_deg': round(rot[1] * UURAD, 3), 'draw_scale': ds,
            'draw_scale_3d': ds3, 'location_gltf': ue_points_to_gltf([loc])[0].round(4).tolist(),
            'ue_matrix': M.tolist(), 'gltf_matrix': ue_to_gltf_matrix(M)}

def short(o): return o.rsplit('.', 1)[-1] if o else o

def _tris(polys):
    import numpy as np
    return [(np.array(p[0]), np.array(p[k]), np.array(p[k + 1])) for p in polys for k in range(1, len(p) - 1)]

def point_in_volume(T, o):
    """ray-crossing parity on 3 skewed rays, majority vote (works for non-convex trigger brushes)"""
    import numpy as np
    votes = 0
    for d in (np.array([0.577, 0.613, 0.539]), np.array([-0.31, 0.72, -0.62]), np.array([0.83, -0.41, 0.37])):
        c = 0
        for v0, v1, v2 in T:
            e1 = v1 - v0; e2 = v2 - v0; h = np.cross(d, e2); a = e1.dot(h)
            if abs(a) < 1e-12: continue
            f = 1 / a; sv = o - v0; u = f * sv.dot(h)
            if u < 0 or u > 1: continue
            q = np.cross(sv, e1); v = f * d.dot(q)
            if v < 0 or u + v > 1: continue
            if f * e2.dot(q) > 1e-6: c += 1
        votes += c % 2
    return votes >= 2

from vs_common import map_sublevels  # noqa: E402

def main():
    subs = map_sublevels(MAP, A)   # name prefix + streamed sublevels (map.json)
    out = {'map': MAP, 'source': 'manifests/authored.db', 'sublevels': subs, 'emitters': {'point': [], 'volume': [], 'line': []},
           'zones': [], 'reverb_presets': {}, 'categories': {}, 'cues': {}, 'music': {}, 'notes': []}
    cues = set()
    # ------------------------------------------------------------------ emitters
    for sub in subs:
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'AmbientSound'):
            p = r['props'] or {}; ac = A.values(p.get('AudioComponent')) if p.get('AudioComponent') else {}
            e = dict(actor=short(r['opath']), sublevel=sub, tag=p.get('Tag'), cue=ac.get('SoundCue'),
                     audio_component={k: ac.get(k) for k in ('bAutoPlay', 'VolumeMultiplier', 'PitchMultiplier', 'bAllowSpatialization',
                                                              'bUseOwnerLocation', 'FadeInTargetVolume') if k in ac},
                     auto_play=A.values(r['opath']).get('bAutoPlay', True), **xf(p))
            out['emitters']['point'].append(e); cues.add(e['cue'])
        for cls, kind, size_prop in (('HmAmbientSoundVolumeEmitter', 'volume', 'Radius'), ('HmAmbientSoundLineEmitter', 'line', 'LineLength')):
            for r in A.find(sub + '.TheWorld.PersistentLevel.%', cls):
                v = A.values(r['opath']); p = r['props'] or {}
                e = dict(actor=short(r['opath']), sublevel=sub, tag=v.get('Tag'), cue=v.get('SoundCue'),
                         **{size_prop.lower(): v.get(size_prop)}, **xf(p))
                if kind == 'volume':
                    e['box_half_extents_ue_inferred'] = [round(v.get('Radius', 0) * s * e['draw_scale'], 2) for s in e['draw_scale_3d']]
                else:
                    e['line_length_ue_inferred'] = round(v.get('LineLength', 0) * e['draw_scale_3d'][0] * e['draw_scale'], 2)
                out['emitters'][kind].append(e); cues.add(e['cue'])
    out['notes'].append('INFERRED: volume emitter box half-extents = Radius x DrawScale x DrawScale3D (actor-local, rotated by Rotation); '
                        'line emitter length = LineLength x DrawScale3D.X along the actor X axis. The class defaults (Radius 500, '
                        'LineLength 500) and per-actor scales are CONFIRMED; the native sampling of the sound along the shape is not.')
    # ------------------------------------------------------------------ kismet zones
    vols = {}
    cpath = os.path.join(OUT, 'collision.json')
    if os.path.exists(cpath):
        for v in json.load(open(cpath, encoding='utf-8'))['volumes']:
            vols[(v['sublevel'], v['actor'])] = v
    def seq_input_labels(seq):
        """Sequence.InputLinks[i].LinkedOp -> SeqEvent_SequenceActivated.InputLabel"""
        s = A.get(seq) or {}; labels = []
        for il in (s.get('props') or {}).get('InputLinks') or []:
            ev = A.get(il.get('LinkedOp')) if il.get('LinkedOp') else None
            labels.append(((ev or {}).get('props') or {}).get('InputLabel') or il.get('LinkDesc'))
        return labels
    def pool(seq):
        items = []
        for o in (A.get(seq)['props'].get('SequenceObjects') or []):
            r = A.get(o)
            if r and r['class'] == 'SeqAct_PlayPlayerPositionalSound':
                v = A.values(o)
                items.append({'action': short(o), 'cue': v.get('SoundToPlay'), 'looping': v.get('Looping'),
                              'delay_min': v.get('DelayMin'), 'delay_max': v.get('DelayMax'),
                              'distance_min': v.get('DistanceMin'), 'distance_max': v.get('DistanceMax'),
                              'comment': v.get('ObjComment'),
                              'other': {k: x for k, x in (r['props'] or {}).items()
                                        if k not in ('SoundToPlay', 'DelayMin', 'DelayMax', 'InputLinks', 'OutputLinks',
                                                     'VariableLinks', 'ParentSequence', 'ObjComment', 'ObjPosX', 'ObjPosY',
                                                     'DrawWidth', 'DrawHeight', 'ObjName')}})
                cues.add(v.get('SoundToPlay'))
        return items
    for sub in subs:
        for ev in A.find(sub + '.TheWorld.PersistentLevel.Main_Sequence.%', 'SeqEvent_Touch'):
            p = A.values(ev['opath']); orig = p.get('Originator')
            z = {'event': short(ev['opath']), 'sublevel': sub, 'comment': p.get('ObjComment'), 'trigger_volume': short(orig),
                 'trigger': {k: p.get(k) for k in ('bLocalPlayerOnly', 'bClientSideOnly', 'bForceOverlapping', 'MaxTriggerCount',
                                                   'ReTriggerDelay', 'IgnoredClassProximityTypes', 'ClassProximityTypes')}}
            ov = A.values(orig) if orig else {}
            z['trigger_volume_location_ue'] = v3(ov.get('Location'))
            vol = vols.get((sub, short(orig)))
            z['trigger_polygons_gltf'] = vol['polygons_gltf'] if vol else None
            z['on_touched'] = []; z['on_untouched'] = []
            for ol in p.get('OutputLinks') or []:
                key = 'on_touched' if ol.get('LinkDesc') == 'Touched' else 'on_untouched'
                for ln in ol.get('Links') or []:
                    tgt = ln.get('LinkedOp'); tr = A.get(tgt) or {}
                    step = {'op': short(tgt), 'class': tr.get('class'), 'input': ln.get('InputLinkIdx', 0)}
                    if tr.get('class') == 'SeqAct_AmbientAudioZone':
                        zp = A.values(tgt); step['num_scenes'] = zp.get('NumScenes')
                        step['outputs'] = {}
                        for zl in zp.get('OutputLinks') or []:
                            acts = []
                            for l2 in zl.get('Links') or []:
                                t2 = l2.get('LinkedOp'); r2 = A.get(t2) or {}
                                a = {'op': short(t2), 'class': r2.get('class'), 'input': l2.get('InputLinkIdx', 0)}
                                if r2.get('class') == 'SeqAct_Reverb':
                                    rp = A.values(t2); pn = A.values(rp.get('ReverbMixerPreset')) if rp.get('ReverbMixerPreset') else {}
                                    a['reverb_preset'] = pn.get('PresetName'); a['comment'] = rp.get('ObjComment')
                                    z.setdefault('reverb_preset', a['reverb_preset'])
                                elif r2.get('class') == 'Sequence':
                                    labels = seq_input_labels(t2)
                                    a['sequence'] = short(t2)
                                    a['sequence_input'] = labels[a['input']] if a['input'] < len(labels) else a['input']
                                    z.setdefault('one_shot_pool_sequence', short(t2))
                                    if 'one_shot_pool' not in z: z['one_shot_pool'] = pool(t2)
                                acts.append(a)
                            step['outputs'][zl.get('LinkDesc')] = acts
                    z[key].append(step)
            out['zones'].append(z)
    out['notes'].append('Zone flow (CONFIRMED links): touching the TriggerVolume fires SeqAct_AmbientAudioZone.Enter; its "Scene 0 Begun" '
                        'output activates the reverb mixer preset and STARTs the zone\'s one-shot pool sub-sequence, "Scene 0 Ended" STOPs '
                        'it. Nothing fires at level load. INFERRED (native SeqAct_AmbientAudioZone): entering a new zone ends the '
                        'previously active zone scene, so exactly one zone/reverb is active and the player starts with none until '
                        'they touch a zone volume.')
    # ------------------------------------------------------------------ mixer config
    mx = (A.get('SoundConfig.SoundMixerProperties') or {}).get('props') or {}
    presets = {m['Name']: m for m in mx.get('MixerPresets') or []}
    cats = {c['Name']: c for c in mx.get('SoundCategories') or []}
    used = sorted({z.get('reverb_preset') for z in out['zones'] if z.get('reverb_preset')} |
                  {n for n in presets if n.startswith('REVERB_TRANS_' + MAP.upper().replace('MP_IAC_', 'MP_'))})
    for n in used:
        dsp = {c: next((d for d in cats[c].get('DSPPresets') or [] if d['Name'] == n), None) for c in cats}
        out['reverb_presets'][n] = {'mixer_preset': presets.get(n), 'used_by_zone': [z['comment'] for z in out['zones'] if z.get('reverb_preset') == n],
                                    'dsp_by_category': {c: d for c, d in dsp.items() if d}}
    out['notes'].append('Reverb presets are SoundMixerProperties MixerPresets (Priority, FadeIn/Out, Duration) whose DSP values live in '
                        'SoundCategories[MASTER_WET].DSPPresets[name] (Reverb = FMOD Ex I3DL2-style fields: Room/RoomHF mB, DecayTime s, '
                        'Reflections/Level mB, delays s, Diffusion/Density %, HFReference Hz; Echo Delay ms). DSPEffectConfig is a raw '
                        'int per category (MASTER_WET 280); bit meaning INFERRED: 8 LowPass (DX_WET_LOPASS=8), 280 = LowPass+Echo+Reverb?')
    # ------------------------------------------------------------------ cues + categories
    for c in sorted(x for x in cues if x):
        g = A.cue(c); out['cues'][c] = g
        cat = g.get('category')
        if cat and cat in cats and cat not in out['categories']:
            cc = cats[cat]
            out['categories'][cat] = {'Volume': cc.get('Volume'), 'IsMusic': cc.get('IsMusic'), 'DSPEffectConfig': cc.get('DSPEffectConfig'),
                                      'Default_DSP': next((d for d in cc.get('DSPPresets') or [] if d['Name'] == 'Default'), None),
                                      'preset_count': len(cc.get('DSPPresets') or [])}
    for c in ('MASTER_WET', 'MASTER_DRY', 'Master'):
        if c in cats and c not in out['categories']:
            out['categories'][c] = {'Volume': cats[c].get('Volume'), 'DSPEffectConfig': cats[c].get('DSPEffectConfig'),
                                    'Default_DSP': next((d for d in cats[c].get('DSPPresets') or [] if d['Name'] == 'Default'), None)}
    out['sound_group_category_mappings'] = (A.get('HM_Engine.Default__SoundMixerProperties') or {}).get('props', {}).get('SoundGroupCategoryMappings')
    # ------------------------------------------------------------------ music / world audio
    for sub in subs:
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'TnWorldInfo'):
            p = r['props'] or {}
            mp = A.values(p['_MusicPlayer']) if p.get('_MusicPlayer') else {}
            out['music'][sub] = {'world_info': short(r['opath']),
                                 'audio_props': {k: v for k, v in p.items() if re.search('Music|Audio|Sound|Announcer|Reverb|Ambient', k)},
                                 'music_player_effective': mp}
    # ------------------------------------------------------------------ validation: player start -> zone
    sp = os.path.join(OUT, 'spawnpoints.json')
    if os.path.exists(sp):
        import numpy as np
        Z = [(z['comment'], _tris(z['trigger_polygons_gltf'])) for z in out['zones'] if z.get('trigger_polygons_gltf')]
        rows = []
        for st in json.load(open(sp, encoding='utf-8')).get('points', []):
            if 'PlayerStart' not in str(st.get('class', '')): continue
            zs = [n for n, T in Z if point_in_volume(T, np.array(st['location_gltf']))]
            rows.append({'actor': st.get('actor'), 'class': st.get('class'), 'zones': zs})
        out['player_start_zones'] = {'starts': len(rows), 'in_one_zone': sum(1 for r in rows if len(r['zones']) == 1),
                                     'in_none': sum(1 for r in rows if not r['zones']), 'in_several': sum(1 for r in rows if len(r['zones']) > 1),
                                     'by_zone': dict(Counter((r['zones'] or ['NONE'])[0] for r in rows)), 'starts_detail': rows}
        out['notes'].append('Initial zone (HIGH CONFIDENCE): the touch events set bForceOverlapping, so a player spawning inside a zone '
                            'volume enters that zone immediately; starts outside every volume begin with no zone/reverb until they '
                            'cross one (player_start_zones).')
    out['counts'] = {'point': len(out['emitters']['point']), 'volume': len(out['emitters']['volume']), 'line': len(out['emitters']['line']),
                     'zones': len(out['zones']), 'reverb_presets': len(out['reverb_presets']), 'cues': len(out['cues']),
                     'waves': sum(len(g.get('waves') or []) for g in out['cues'].values()),
                     'waves_with_wav': sum(1 for g in out['cues'].values() for w in g.get('waves') or [] if w.get('wav')),
                     'missing_cues': [c for c, g in out['cues'].items() if g.get('missing')]}
    path = os.path.join(OUT, 'audio.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['counts']), '->', path)

if __name__ == '__main__':
    main()
