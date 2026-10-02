"""Bink 1 (.bik) movies -> MKV (H.264 CRF18 + every audio track as FLAC) via ffmpeg.

WFC movies carry many mono binkaudio tracks (channel/language layout not yet
identified), so all tracks are preserved 1:1 in MKV rather than downmixed.
Subtitle cue lists (Movies/*.txt: start_ms,end_ms,key) are converted to JSON,
with text resolved from the decoded Subtitles.int localization when present.
Output: ExtractedAssets/movies/
"""
import json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'Game Dump', 'TransGame', 'Movies')
OUT = os.path.join(ROOT, 'ExtractedAssets', 'movies')
FF = os.path.join(ROOT, 'AssetTools', 'bin', 'ffmpeg', 'ffmpeg.exe')
SUBS = os.path.join(ROOT, 'ExtractedAssets', 'config', 'Coalesced_int.json')

def convert(name):
    src = os.path.join(SRC, name)
    dst = os.path.join(OUT, os.path.splitext(name)[0].strip() + '.mkv')
    if os.path.exists(dst): return name, 0, 'exists'
    cmd = [FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-map', '0',
           '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
           '-c:a', 'flac', '-threads', '4', dst]
    p = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    return name, p.returncode, p.stderr[-300:]

def subtitles():
    lines = {}
    if os.path.exists(SUBS):
        data = json.load(open(SUBS, encoding='utf-8'))
        for f, secs in data.items():
            for k, v in secs.get('Subtitles', {}).items():
                lines[k] = v[0]
    for n in os.listdir(SRC):
        if not n.lower().endswith('.txt'): continue
        cues = []
        for line in open(os.path.join(SRC, n), encoding='latin-1'):
            m = re.match(r'\s*(\d+)\s*,\s*(\d+)\s*,\s*(\S+)', line)
            if m:
                cues.append({'start_ms': int(m.group(1)), 'end_ms': int(m.group(2)), 'key': m.group(3),
                             'text_int': lines.get(m.group(3))})
        json.dump(cues, open(os.path.join(OUT, os.path.splitext(n)[0] + '.subtitles.json'), 'w'), indent=1)

def main():
    os.makedirs(OUT, exist_ok=True)
    subtitles()
    names = sorted(n for n in os.listdir(SRC) if n.lower().endswith('.bik'))
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(convert, names))
    fails = [r for r in res if r[1] != 0]
    json.dump({'movies': len(names), 'failed': fails}, open(os.path.join(ROOT, 'AssetTools', 'manifests',
              'extracted', 'movies_status.json'), 'w'), indent=1)
    print('movies: %d, failed %d' % (len(names), len(fails)))

if __name__ == '__main__':
    main()
