"""Campaign / frontend movies for the in-engine FMV player (Integration 2026-10-18; RE FMV_PLAYBACK_RE.md): every shipped Bink 1 .bik in
Game Dump/TransGame/Movies (read in place) -> AssetTools/out/movies/<name>.webm (VP9 CRF 30 + every audio track as Opus, labelled by
source index since RE could not map them) + <name>.subtitles.json from the .txt sidecar + manifest.json.

Sidecar: line 1 = ticks per second (100), then `start,end,KEY` rows. Times are converted to ms with that header (FMV_a1intro: last end
9000 ticks = 90.0 s of a 94.1 s movie). Text: [Subtitles] of Subtitles.int / Subtitles.fra (decoded Coalesced, ExtractedAssets/config).

CPU discipline (Integration): ffmpeg -threads 4 at below-normal priority, one movie at a time. Hold-aware: a PERF_HOLD before a movie ->
exit 76; a hold during an encode -> ffmpeg killed, partial file deleted, exit 76 (the cmd wrapper waits 60 s hold-free and reruns; done
movies are skipped via the manifest). ExtractedAssets is not written (its earlier H.264 set in movies/ stays as it is).

  python movies_webm.py [name ...]
"""
import glob, hashlib, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from run_bounded import active_holds  # noqa: E402

AT = os.path.dirname(os.path.dirname(HERE)); REB = os.path.dirname(AT)
SRC = os.path.join(REB, 'Game Dump', 'TransGame', 'Movies')
OUT = os.path.join(AT, 'out', 'movies')
FF = os.path.join(AT, 'bin', 'ffmpeg', 'ffmpeg.exe'); FP = os.path.join(AT, 'bin', 'ffmpeg', 'ffprobe.exe')
EA_CONFIG = os.path.join(REB, 'ExtractedAssets', 'config')
BELOW_NORMAL = 0x00004000
MAN = os.path.join(OUT, 'manifest.json')

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def probe(p, count=False):
    args = [FP, '-v', 'error', '-show_entries', 'format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels'
            + (',nb_read_packets' if count else '') + ':stream_tags=title', '-of', 'json'] + (['-count_packets'] if count else []) + [p]
    return json.loads(subprocess.run(args, capture_output=True, text=True).stdout or '{}')

def subtitles_tables():
    out = {}
    for lang in ('int', 'FRA'):
        d = json.load(open(os.path.join(EA_CONFIG, 'Coalesced_%s.json' % lang), encoding='utf-8'))
        f = next(v for k, v in d.items() if k.lower().endswith('/subtitles.' + lang.lower()))
        out[lang] = f.get('Subtitles') or {}
    return out

def sidecar(txt, tables):
    lines = [l.strip() for l in open(txt, encoding='latin-1').read().splitlines() if l.strip()]
    if not lines: return None
    ticks = float(lines[0]); rows = []
    for l in lines[1:]:
        p = l.split(',')
        if len(p) < 3: continue
        key = p[2].strip(); ti = tables['int'].get(key); tf = tables['FRA'].get(key)
        rows.append({'start_ms': round(float(p[0]) * 1000 / ticks), 'end_ms': round(float(p[1]) * 1000 / ticks), 'key': key,
                     'text_int': ti[0] if ti else None, 'text_fra': tf[0] if tf else None})
    return {'ticks_per_second': ticks, 'lines': rows, 'keys_without_int_text': [r['key'] for r in rows if not r['text_int']]}

def encode(src, dst, n_audio):
    tmp = dst + '.part.webm'
    cmd = [FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-map', '0:v:0']
    for i in range(n_audio): cmd += ['-map', '0:a:%d' % i]
    cmd += ['-c:v', 'libvpx-vp9', '-crf', '30', '-b:v', '0', '-row-mt', '1', '-threads', '4', '-deadline', 'good', '-cpu-used', '2']
    if n_audio:
        cmd += ['-c:a', 'libopus', '-b:a', '96k']
        for i in range(n_audio): cmd += ['-metadata:s:a:%d' % i, 'title=track_%d' % i]
    cmd += [tmp]
    p = subprocess.Popen(cmd, creationflags=BELOW_NORMAL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    while p.poll() is None:
        time.sleep(1.0)
        if active_holds():
            p.kill(); p.wait()
            if os.path.exists(tmp): os.remove(tmp)
            return 'held'
    err = p.stderr.read().decode('utf-8', 'replace')[-400:]
    if p.returncode != 0:
        if os.path.exists(tmp): os.remove(tmp)
        return 'ffmpeg rc %d: %s' % (p.returncode, err)
    os.replace(tmp, dst); return 'ok'

def main(names):
    os.makedirs(OUT, exist_ok=True)
    man = json.load(open(MAN, encoding='utf-8')) if os.path.exists(MAN) else {'generated_by': 'AssetTools/scripts/wfc/movies_webm.py', 'movies': {}}
    tables = subtitles_tables()
    srcs = sorted(glob.glob(os.path.join(SRC, '*.bik')))
    if names: srcs = [s for s in srcs if os.path.basename(s)[:-4].strip() in names]
    for src in srcs:
        raw = os.path.basename(src)[:-4]; name = raw.strip()          # 'FMV_a5otext_ESN ' -> trimmed output name (RE: trim names)
        if man['movies'].get(name, {}).get('status') == 'ok': continue
        if active_holds(): json.dump(man, open(MAN, 'w', encoding='utf-8'), indent=1); print('PERF_HOLD before', name); sys.exit(76)
        t0 = time.time()
        ps = probe(src, count=True); st = ps.get('streams', [])
        v = next((s for s in st if s.get('codec_type') == 'video'), {}); aud = [s for s in st if s.get('codec_type') == 'audio']
        dst = os.path.join(OUT, name + '.webm')
        r = encode(src, dst, len(aud))
        if r == 'held': json.dump(man, open(MAN, 'w', encoding='utf-8'), indent=1); print('PERF_HOLD during', name, '- killed, will redo'); sys.exit(76)
        rec = {'source': os.path.relpath(src, REB).replace('\\', '/'), 'source_name_raw': raw, 'source_sha256': sha(src),
               'source_duration_s': float(ps.get('format', {}).get('duration') or 0), 'source_frames': int(v.get('nb_read_packets') or 0),
               'source_fps': v.get('r_frame_rate'), 'width': v.get('width'), 'height': v.get('height'),
               'source_audio_tracks': [{'index': k, 'source_stream': s.get('index'), 'codec': s.get('codec_name'), 'sample_rate': s.get('sample_rate'),
                                        'channels': s.get('channels'), 'label': 'track_%d' % k} for k, s in enumerate(aud)],
               'status': r}
        if r == 'ok':
            po = probe(dst, count=True); so = po.get('streams', [])
            vo = next((s for s in so if s.get('codec_type') == 'video'), {})
            rec.update({'output': os.path.relpath(dst, AT).replace('\\', '/'), 'output_sha256': sha(dst), 'output_bytes': os.path.getsize(dst),
                        'output_duration_s': float(po.get('format', {}).get('duration') or 0), 'output_frames': int(vo.get('nb_read_packets') or 0),
                        'output_fps': vo.get('r_frame_rate'), 'output_audio_tracks': sum(1 for s in so if s.get('codec_type') == 'audio'),
                        'codec': 'VP9 CRF 30 / Opus 96k mono per track'})
            rec['check'] = {'frames_equal': rec['output_frames'] == rec['source_frames'],
                            'duration_delta_s': round(rec['output_duration_s'] - rec['source_duration_s'], 3),
                            'audio_tracks_equal': rec['output_audio_tracks'] == len(aud)}
        txt = os.path.join(SRC, raw + '.txt')
        if os.path.exists(txt):
            sub = sidecar(txt, tables)
            if sub:
                sp = os.path.join(OUT, name + '.subtitles.json')
                json.dump({'movie': name, 'source': os.path.relpath(txt, REB).replace('\\', '/'), **sub}, open(sp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
                rec['subtitles'] = {'file': os.path.relpath(sp, AT).replace('\\', '/'), 'lines': len(sub['lines']), 'ticks_per_second': sub['ticks_per_second'],
                                    'keys_without_int_text': sub['keys_without_int_text']}
        rec['wall_s'] = round(time.time() - t0, 1)
        man['movies'][name] = rec; json.dump(man, open(MAN, 'w', encoding='utf-8'), indent=1)
        print(name, r, rec.get('check'), rec['wall_s'], 's', flush=True)
    done = [m for m in man['movies'].values() if m.get('status') == 'ok']
    man['summary'] = {'movies': len(man['movies']), 'ok': len(done), 'frames_equal': sum(1 for m in done if m['check']['frames_equal']),
                      'audio_tracks_equal': sum(1 for m in done if m['check']['audio_tracks_equal']),
                      'with_subtitles': sum(1 for m in man['movies'].values() if m.get('subtitles'))}
    json.dump(man, open(MAN, 'w', encoding='utf-8'), indent=1); print('summary', man['summary'])

if __name__ == '__main__':
    main(sys.argv[1:])
