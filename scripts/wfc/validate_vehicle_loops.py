"""Validator for manifests/vehicle_audio_loops.json (re-reads every FSB4 header from the cooked packages).

Checks:
  bank_exists            package + export index resolve and the export carries an FSB4 bank
  sample_index_resolves  sample_index < numsamples of that bank
  rate_from_header       sample_rate == header deffreq;  total_samples == header lengthsamples;  channels == numchannels
  loop_flag_not_inferred loop_enabled_in_sample_header == (LOOP_NORMAL|LOOP_BIDI bit in the header mode)
  loop_order             loopstart < loopend for every wave whose header enables a loop (and for all full-range data)
  loop_within_length     loopend <= total_samples - 1
  times_match            loopstart_s / loopend_s / loop_duration_s / total_duration_s == samples / rate
  no_loop_listed         waves without a header loop flag are explicitly loop_enabled_in_sample_header=false
  start_end_not_looped   waves used only by START/END/ONESHOT slots are classified LOOPED only if a WaveEvent of
                         their own cue has bLooping=true (never because a related engine cue loops)
  cue_loop_not_used      header loop seconds never equal the cue-root LoopStart/LoopEnd floats
  census                 recomputes the census numbers quoted in the manifest
Exit code 1 on any failure.  python validate_vehicle_loops.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, sounds, fsb4  # noqa: E402

MANI = os.path.join(HERE, '..', '..', 'manifests', 'vehicle_audio_loops.json')

def census(pkgs):
    n = custom = flagged = 0
    for pk in pkgs:
        p = objtree.package(pk)
        for e in p.exports:
            if p.class_name(e) not in ('SoundNodeWaveEx', 'SoundNodeWave'): continue
            blob, _ = sounds.locate_fsb(p, e)
            if not blob: continue
            for s in fsb4.parse(blob)['samples']:
                n += 1
                custom += not (s['loopstart'] == 0 and s['loopend'] == s['lengthsamples'] - 1)
                flagged += any(f.startswith('LOOP') for f in s['mode_flags'])
    return n, custom, flagged

def main():
    m = json.load(open(MANI, encoding='utf-8'))
    fails, checks = [], 0
    def ok(cond, msg):
        nonlocal checks
        checks += 1
        if not cond: fails.append(msg)
    for w, r in m['waves'].items():
        b = r.get('fsb_bank')
        ok(b is not None, '%s: no bank' % w)
        if not b: continue
        p = objtree.package(b['source_package'])
        ok(0 < b['export_index'] <= len(p.exports) and p.object_path(b['export_index']).lower() == w.lower(),
           '%s: export index %s does not resolve' % (w, b['export_index']))
        blob, _ = sounds.locate_fsb(p, p.exports[b['export_index'] - 1])
        ok(blob is not None and blob[:4] == b'FSB4', '%s: bank missing / not FSB4' % w)
        h = fsb4.parse(blob)
        ok(r['sample_index'] < h['numsamples'], '%s: sample index out of range' % w)
        s = h['samples'][r['sample_index']]
        ok(r['sample_rate'] == s['deffreq'], '%s: rate mismatch' % w)
        ok(r['total_samples'] == s['lengthsamples'], '%s: length mismatch' % w)
        ok(r['channels'] == s['numchannels'], '%s: channel mismatch' % w)
        L = r['loop']
        hdr_loop = any(f in ('LOOP_NORMAL', 'LOOP_BIDI') for f in s['mode_flags'])
        ok(L['loop_enabled_in_sample_header'] == hdr_loop, '%s: loop flag not from header' % w)
        ok(L['loopstart_sample'] == s['loopstart'] and L['loopend_sample'] == s['loopend'], '%s: loop points differ from header' % w)
        ok(L['loopstart_sample'] < L['loopend_sample'], '%s: loopstart >= loopend' % w)
        ok(L['loopend_sample'] <= r['total_samples'] - 1, '%s: loopend beyond sample count' % w)
        sr = r['sample_rate']
        for k, v in (('loopstart_s', L['loopstart_sample'] / sr), ('loopend_s', L['loopend_sample'] / sr),
                     ('loop_duration_s', (L['loopend_sample'] - L['loopstart_sample'] + 1) / sr),):
            ok(abs(L[k] - v) < 1e-5, '%s: %s mismatch' % (w, k))
        ok(abs(r['total_duration_s'] - r['total_samples'] / sr) < 1e-5, '%s: duration mismatch' % w)
        if not hdr_loop:
            ok(L['loop_enabled_in_sample_header'] is False, '%s: no-loop wave not explicit' % w)
        uses = r.get('used_by', [])
        looped = any(u['wave_event_bLooping'] for u in uses)
        ok(('LOOPED' in r['classification']) == looped, '%s: classification not from its own WaveEvents' % w)
        if uses and all(u['role'] in ('START', 'END', 'ONESHOT') for u in uses):
            ok(not ('LOOPED' in r['classification']) or looped, '%s: start/end wave classified looping' % w)
    for sl in m['slots']:
        cl = sl.get('cue_root_LoopStart_LoopEnd (NOT the loop authority; Native RE: unused on this path)')
        if not cl: continue
        for we in sl.get('wave_events', []):
            for w in we['waves']:
                L = m['waves'][w]['loop']
                ok(not any(abs(L[k] - (cl.get(c) or -1)) < 1e-4 for k in ('loopstart_s', 'loopend_s') for c in ('LoopStart', 'LoopEnd')),
                   '%s: header loop seconds equal cue-root LoopStart/LoopEnd' % w)
    c = m['census']
    n, custom, flagged = census(c['packages'])
    ok(n == c['fsb4_samples'] and custom == c['with_custom_loop_range'] and flagged == c['with_LOOP_mode_flag'],
       'census mismatch: %s/%s/%s' % (n, custom, flagged))
    print('vehicle_audio_loops: %d checks, %d failures, %d waves' % (checks, len(fails), len(m['waves'])))
    for f in fails: print('  FAIL', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
