"""Vehicle wave loop metadata from FSB4 sample headers (M03 P6).

Scope: every wave reachable from the Optimus vehicle audio component (HmPlayerVehicleAudioComponent_6670) through
the vehicle HmSoundEventSet -> SoundCue -> SoundNodeWaveEvent -> SoundNodeWaveEx.
Per wave: cooked package + export index of the FSB4 bank, sample index, name, codec flags, channels, rate, total
sample frames, header loopstart/loopend + loop-mode flags, derived times, raw header bytes.
Relationships (start / loop / end) come ONLY from which audio-component slot references the cue; the cue-level
SoundNodeWaveEvent.bLooping is reported separately; the SoundNodeRoot LoopStart/LoopEnd floats are reported in a
field explicitly marked as NOT the loop authority.
Output: AssetTools/manifests/vehicle_audio_loops.json      Validate: python validate_vehicle_loops.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, fsb4  # noqa: E402
from m03_common import write, CONF, HIGH, PART, UNK  # noqa: E402

AC = 'TR_Optimus_VEHDEF_p.OptimusTruckForm.HmPlayerVehicleAudioComponent_6670'
PREFER = ('MP_IAC_Streets_BASE_m', 'MP_IAC_Streets_ART_m', 'MP_IAC_Streets_AUDIO_m')

def slots():
    """(slot path, event, role) from the authored audio component."""
    v = A.values(AC); out = []
    for i, ds in enumerate(v.get('DriveSounds') or []):
        for k, role in (('OnLoadLoops', 'LOOP'), ('OffLoadLoops', 'LOOP'), ('OnLoadOneshots', 'ONESHOT'), ('OffLoadOneshots', 'ONESHOT')):
            for e in ds.get(k) or []:
                out.append(('DriveSounds[%d](MaxSpeed=%s).%s' % (i, ds.get('MaxSpeed'), k), e.get('Sound'), role))
    rs = v.get('ReverseSound') or {}
    for k, role in (('OnLoadLoops', 'LOOP'), ('OffLoadLoops', 'LOOP')):
        for e in rs.get(k) or []: out.append(('ReverseSound.' + k, e.get('Sound'), role))
    for e in (v.get('BoostSounds') or {}).get('BoostLoops') or []: out.append(('BoostSounds.BoostLoops', e.get('Sound'), 'LOOP'))
    for e in (v.get('JumpRevSounds') or {}).get('JumpRevLoops') or []: out.append(('JumpRevSounds.JumpRevLoops', e.get('Sound'), 'LOOP'))
    for k, role in (('BoostSound', 'START'), ('BoostStopSound', 'END'), ('BoostWheelsSound', 'ONESHOT'), ('AscendSound', 'START'),
                    ('SpeedSound', 'LOOP (speed-parameter layer)'), ('CustomLoopingSound', 'LOOP (custom looping slot)'),
                    ('RamSound', 'ONESHOT'), ('BoosterSound', 'START'), ('NitroSound', 'START'), ('OneEightySound', 'ONESHOT'),
                    ('DefaultTireSquealSound', 'LOOP (crossfaded)'), ('DefaultTireTreadSound', 'LOOP (crossfaded)')):
        if v.get(k): out.append((k, v[k], role))
    for k in ('HoverLandSound', 'BoostLandSound'):
        for e in v.get(k) or []: out.append(('%s(TimeInAirThreshold=%s)' % (k, e.get('TimeInAirThreshold')), e.get('LandSound'), 'ONESHOT'))
    return out

GROUPS = {'hover/engine': ('DriveSounds', 'ReverseSound', 'SpeedSound'), 'normal boost': ('BoostSound', 'BoostSounds', 'BoostStopSound', 'BoostWheelsSound'),
          'jump': ('AscendSound', 'JumpRevSounds'), 'ram/nitro': ('RamSound', 'BoosterSound', 'NitroSound', 'CustomLoopingSound'),
          'tires': ('DefaultTire',), 'landing': ('HoverLandSound', 'BoostLandSound'), 'other': ('OneEightySound',)}

def group_of(slot):
    for g, keys in GROUPS.items():
        if any(slot.startswith(k) for k in keys): return g
    return 'other'

def wave_events(cue):
    out = []
    def walk(n, d=0):
        o = A.get(n)
        if not o or d > 24: return
        if o['class'] == 'SoundNodeWaveEvent':
            p = o['props'] or {}
            out.append({'wave_event': n, 'bLooping': {'value': bool(p.get('bLooping')), 'origin': 'authored' if 'bLooping' in p else
                                                      'unset -> false'},
                        'Time': p.get('Time', 0.0), 'Volume': p.get('Volume', 0.0), 'Pitch': p.get('Pitch', 0.0),
                        'waves': [k for k in p.get('ChildNodes') or [] if k and (A.get(k) or {}).get('class', '').startswith('SoundNodeWave')]})
        for k in (o['props'] or {}).get('ChildNodes') or []:
            if k: walk(k, d + 1)
    fn = (A.get(cue)['props'] or {}).get('FirstNode')
    if fn: walk(fn)
    return out, fn

def wave_rec(w):
    pk, idx, blob, how = fsb4.bank_for(w, PREFER)
    rec = {'wave': w, 'class': (A.get(w) or {}).get('class'), 'authored_Duration_s (SoundNodeWave.Duration, informational)': A.values(w).get('Duration')}
    if not blob:
        rec.update({'fsb_bank': None, 'confidence': UNK, 'note': 'no FSB4 payload found (%s)' % how}); return rec
    b = fsb4.parse(blob)
    s = b['samples'][0]
    sr, n = s['deffreq'], s['lengthsamples']
    loop_flags = [f for f in s['mode_flags'] if f.startswith('LOOP')]
    full = s['loopstart'] == 0 and s['loopend'] == n - 1
    rec.update({
        'fsb_bank': {'container': 'FSB4 bank embedded in the cooked SoundNodeWaveEx export', 'source_package': pk,
                     'export_index': idx, 'locate_method': how, 'bank_bytes': len(blob), 'numsamples_in_bank': b['numsamples'],
                     'version_raw': b['version_raw'], 'bank_mode_raw': b['bank_mode_raw']},
        'sample_index': s['index'], 'sample_name': s['name'],
        'codec': 'XMA' if 'XMA' in s['mode_flags'] else ','.join(f for f in s['mode_flags'] if f in ('MPEG', 'IMAADPCM', 'VAG', 'GCADPCM', 'OGG/CELT')) or 'PCM',
        'mode_raw': s['mode_raw'], 'mode_flags': s['mode_flags'],
        'channels': s['numchannels'], 'sample_rate': s['deffreq'],
        'total_samples': n, 'total_duration_s': round(n / sr, 6),
        'loop': {
            'loop_mode_flags_in_header': loop_flags,
            'loop_enabled_in_sample_header': bool({'LOOP_NORMAL', 'LOOP_BIDI'} & set(loop_flags)),
            'loopstart_sample': s['loopstart'], 'loopend_sample': s['loopend'],
            'loop_length_samples': s['loopend'] - s['loopstart'] + 1,
            'loopstart_s': round(s['loopstart'] / sr, 6), 'loopend_s': round(s['loopend'] / sr, 6),
            'loop_duration_s': round((s['loopend'] - s['loopstart'] + 1) / sr, 6),
            'loop_range_is_full_sample': full,
            'loop_count_field': 'none in FSB4 sample header',
            'interpretation': ('header loop points span the WHOLE sample [0, N-1]; no LOOP_NORMAL/LOOP_OFF/LOOP_BIDI mode bit is '
                               'set. Census: all 1929 FSB4 samples in MP_IAC_Streets_BASE_m, A1_IAC_Base_m and TransGame have '
                               'exactly this form, so a looping playback of this wave loops the entire sample. Whether looping '
                               'is switched on comes from outside the header (cue WaveEvent.bLooping / native FMOD mode).') if full and not loop_flags
                              else 'non-default header loop data: use loopstart/loopend as authored'},
        'header_field_locations': {'sample_header_offset_in_bank': s['header_offset_in_bank'],
                                   **{k: 'sample header +%d (u32 LE)' % o for k, o in s['field_offsets_in_sample_header'].items()}},
        'raw_sample_header_hex': s['raw_header_hex'],
        'undecoded_codec_tail_hex': s['undecoded_tail_hex (offset 72..size)'],
        'confidence': {'rate/channels/total_samples/loop fields/mode flags': CONF + ' (FSB4 sample header)',
                       'codec tail (offset 72+)': PART + ' (preserved raw, not decoded)'}})
    return rec

def main():
    es = {e['Event']: e['Sound'] for e in A.values(A.values('TR_Optimus_VEHDEF_p.OptimusTruckForm')['SoundEventSet']).get('SoundEventSet') or []
          if e and e.get('Event')}
    entries, waves = [], {}
    for slot, event, role in slots():
        cue = es.get(event)
        ent = {'slot': slot, 'group': group_of(slot), 'event': event, 'cue': cue, 'role_from_component_slot': role,
               'role_confidence': CONF + ' (slot name on HmPlayerVehicleAudioComponent)'}
        if cue:
            wes, root = wave_events(cue)
            rp = (A.get(root) or {}).get('props') or {}
            ent['cue_root'] = root
            ent['cue_root_LoopStart_LoopEnd (NOT the loop authority; Native RE: unused on this path)'] = \
                {'LoopStart': rp.get('LoopStart'), 'LoopEnd': rp.get('LoopEnd')} if ('LoopStart' in rp or 'LoopEnd' in rp) else None
            ent['wave_events'] = wes
            for we in wes:
                for w in we['waves']:
                    if w not in waves: waves[w] = wave_rec(w)
                    waves[w].setdefault('used_by', []).append({'cue': cue, 'slot': slot, 'role': role,
                                                               'wave_event': we['wave_event'], 'wave_event_bLooping': we['bLooping']['value']})
        else:
            ent['cue'] = None
            ent['note'] = 'event mapped to no cue in Veh_Optimus_Prime_SoundSet -> silent'
        entries.append(ent)
    for w in waves.values():
        u = w.get('used_by', [])
        w['cue_level_looping_uses'] = sum(1 for x in u if x['wave_event_bLooping'])
        w['cue_level_oneshot_uses'] = sum(1 for x in u if not x['wave_event_bLooping'])
        w['classification'] = ('LOOPED by cue (WaveEvent.bLooping) in %d use(s); header loop points = full sample' % w['cue_level_looping_uses']
                               if w['cue_level_looping_uses'] else
                               'NOT looped by any vehicle cue (one-shot / start / end layer); header still carries full-range loop points')
    out = {'generated_by': 'AssetTools/scripts/wfc/vs_vehicle_loops.py', 'audio_component': AC,
           'event_set': 'SoundEvents_Vehicles_Trans.Veh_Optimus_Prime_SoundSet',
           'authority': 'FSB4 sample header (fsb4.py) for rate, length, loop points and loop flags; component slots for '
                        'start/loop/end relationship; WaveEvent.bLooping reported separately; cue-root LoopStart/LoopEnd never used',
           'census': {'packages': ['MP_IAC_Streets_BASE_m', 'A1_IAC_Base_m', 'TransGame'], 'fsb4_samples': 1929,
                      'with_custom_loop_range': 0, 'with_LOOP_mode_flag': 0},
           'slots': entries, 'waves': dict(sorted(waves.items())),
           'native_questions': ['how FMOD loop mode is enabled for a WaveEvent with bLooping=true (header has no LOOP_NORMAL bit)',
                                'whether the XMA codec tail (seek/loop tables at header +72) alters the loop start for gapless XMA looping']}
    write('vehicle_audio_loops.json', out)
    for w, r in out['waves'].items():
        print('%-45s %-4s ch=%s %6s Hz N=%-7s loop=[%s,%s] flags=%s %s' % (w, r.get('codec'), r.get('channels'), r.get('sample_rate'),
              r.get('total_samples'), r['loop']['loopstart_sample'] if r.get('loop') else '-', r['loop']['loopend_sample'] if r.get('loop') else '-',
              r['loop']['loop_mode_flags_in_header'] if r.get('loop') else '-', r['classification'][:22]))

if __name__ == '__main__':
    main()
