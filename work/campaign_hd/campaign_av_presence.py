"""Campaign audio / FMV / dialog presence per chapter (Integration 2026-10-23), against CAMPAIGN_DATA_INDEX sources. Read-only.

Re-verifies ON DISK (not the manifest flags) what manifests/campaign/<ch>_assets.json lists:
  sound waves: each wave's .wav in content/<pkg>, and its INT / FRA twins (content/_LOC/<lang>/<pkg> or content/<pkg>_<LANG>; the
               rule of campaign_chapter_assets.py); bytes of what exists; waves with no playable file anywhere;
  sound cues:  count, cues whose waves lack a file (manifest);
  dialog:      manifests/next_map/<CH>_dialog.json counts (conversations, lines, lines without wave, subtitle / FaceFX coverage);
  FaceFX:      assets extracted (content/<pkg>/<name>.* present);
  FMV:         each chapter movie: the Game Dump .bik (bytes) and ExtractedAssets/movies/<name>.mkv (+ .subtitles.json) present / bytes.
Writes work/campaign_hd/campaign_av_presence.json and prints a per-chapter table.
"""
import glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(AT)
CONTENT = os.path.join(TR, 'ExtractedAssets', 'content'); MOV = os.path.join(TR, 'ExtractedAssets', 'movies')
CH = ['a1', 'a2', 'a3', 'a4', 'a5', 'd1', 'd2', 'd3a', 'd3b', 'd5']

def wav_paths(obj):
    pkg, *parts = obj.split('.'); parts[-1] += '.wav'
    return {'plain': [os.path.join(CONTENT, pkg, *parts)],
            'int': [os.path.join(CONTENT, '_LOC', 'int', pkg, *parts), os.path.join(CONTENT, pkg + '_INT', *parts)],
            'fra': [os.path.join(CONTENT, '_LOC', 'FRA', pkg, *parts), os.path.join(CONTENT, pkg + '_FRA', *parts)]}

def size(paths):
    for p in paths:
        if os.path.exists(p): return os.path.getsize(p)
    return None

def main():
    out = {}
    for ch in CH:
        a = json.load(open(os.path.join(AT, 'manifests', 'campaign', ch + '_assets.json'), encoding='utf-8'))
        w = a['groups']['sound_waves']['items']; c = a['groups']['sound_cues']
        wr = {'waves': len(w), 'plain': 0, 'int': 0, 'fra': 0, 'bytes': 0, 'no_file_anywhere': [], 'int_without_fra': [], 'manifest_disagrees': []}
        for x in w:
            got = {k: size(v) for k, v in wav_paths(x['object']).items()}
            for k, v in got.items():
                if v is not None: wr[k] += 1; wr['bytes'] += v
            if all(v is None for v in got.values()): wr['no_file_anywhere'].append(x['object'])
            if got['int'] is not None and got['fra'] is None: wr['int_without_fra'].append(x['object'])
            mf = x.get('files') or {}
            if any(bool(mf.get(k)) != (got[k] is not None) for k in ('plain', 'int', 'fra')): wr['manifest_disagrees'].append(x['object'])
        ff = a['groups']['facefx']['items']
        ffx = [x['object'] for x in ff if not glob.glob(os.path.join(CONTENT, *x['object'].split('.')) + '.*')]
        dl = a.get('dialog') or {}
        mv = {}
        for name, m in (a.get('movies') or {}).items():
            bik = os.path.join(TR, m['source']) if m.get('source') else None
            mkv = os.path.join(MOV, name + '.mkv'); sub = os.path.join(MOV, name + '.subtitles.json')
            mv[name] = {'duration_s': m.get('duration_s'), 'bik_bytes': os.path.getsize(bik) if bik and os.path.exists(bik) else None,
                        'mkv_bytes': os.path.getsize(mkv) if os.path.exists(mkv) else None, 'subtitles_json': os.path.exists(sub)}
        out[ch] = {'chapter': a.get('chapter'), 'sound_waves': wr, 'sound_cues': {'count': c['summary']['count'],
                   'cues_with_waves_without_file': len(c['summary'].get('waves_without_file') or [])},
                   'facefx': {'count': len(ff), 'not_on_disk': ffx}, 'dialog': {'source': dl.get('source'), 'counts': dl.get('counts')}, 'movies': mv}
    json.dump({'generated_by': 'AssetTools/work/campaign_hd/campaign_av_presence.py', 'chapters': out},
              open(os.path.join(HERE, 'campaign_av_presence.json'), 'w', encoding='utf-8'), indent=1)
    for ch, r in out.items():
        s = r['sound_waves']; d = (r['dialog']['counts'] or {})
        mv = r['movies']; mkv = sum(1 for m in mv.values() if m['mkv_bytes']); mb = sum(m['mkv_bytes'] or 0 for m in mv.values())
        print('%-4s waves %4d plain %4d int %4d fra %4d (%.1f MB) no-file %d int-w/o-fra %d manifest-disagree %d | cues %4d | facefx %d missing %d | '
              'dialog conv %s lines %s no-wave %s no-subs %s | fmv %d/%d mkv (%.0f MB) subs %d' % (
                  ch, s['waves'], s['plain'], s['int'], s['fra'], s['bytes'] / 1e6, len(s['no_file_anywhere']), len(s['int_without_fra']),
                  len(s['manifest_disagrees']), r['sound_cues']['count'], r['facefx']['count'], len(r['facefx']['not_on_disk']),
                  d.get('conversations'), d.get('lines'), d.get('lines_without_wave'), d.get('waves_without_subtitles'),
                  mkv, len(mv), mb / 1e6, sum(1 for m in mv.values() if m['subtitles_json'])))

if __name__ == '__main__':
    main()
