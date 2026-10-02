"""Native FMOD sound extraction for WFC SoundNodeWaveEx objects.

Why this exists: umodel 1590 exports dialog (WL_DX_*) and music (WL_MX_*)
waves as zero-filled .unk files.  In this build the FSB4 payload is stored
inside the export at a 0x8000-aligned offset (zero padding before it); the
export's last 8 bytes are big-endian (absolute_offset, size) of that payload.
umodel reads from the start of the padding instead.

For every unique SoundNodeWaveEx (deduplicated by original object path, same
owner assignment as extract.py) we locate the FSB4 blob and write
ExtractedAssets/content/<srcpkg>/<groups>/<name>.fsb, then (optionally) WAV
via vgmstream.  Mapping -> AssetTools/manifests/extracted/audio_native.jsonl
"""
import json, os, struct, subprocess, sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, extract  # noqa: E402

def locate_fsb(pkg, e):
    d = pkg.data[e['serial_offset']:e['serial_offset'] + e['serial_size']]
    if len(d) >= 8:
        off, size = struct.unpack('>ii', d[-8:])
        if 0 < size and 0 <= off < len(pkg.data) and pkg.data[off:off + 4] == b'FSB4':
            return pkg.data[off:off + size], 'tail_offset'
    i = d.find(b'FSB4')
    if i >= 0:
        # FSB4 header: 'FSB4', numsamples, shdrsize, datasize, ... (little-endian)
        shdr, dsize = struct.unpack_from('<ii', d, i + 8)
        return d[i:i + 48 + shdr + dsize], 'inline_scan'
    return None, 'no_fsb4'

def do_package(args):
    pkgname, objs = args
    pkg = ue3pkg.Package(os.path.join(extract.COOKED, pkgname + '.xxx'))
    want = {o[0].lower(): o for o in objs}
    recs = []
    for i, e in enumerate(pkg.exports):
        if pkg.class_name(e) not in ('SoundNodeWaveEx', 'SoundNodeWave'): continue
        op = pkg.object_path(i + 1)
        o = want.pop(op.lower(), None)
        if o is None: continue
        blob, how = locate_fsb(pkg, e)
        rel = op.replace('.', '/') + '.fsb'
        rec = {'phase': 'audio_native', 'source_package': pkgname, 'object_path': op, 'class': o[1],
               'name': e['name'], 'method': how}
        if blob:
            dst = os.path.join(extract.OUT, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as f: f.write(blob)
            unk = dst[:-4] + '.unk'
            if os.path.exists(unk): os.remove(unk)
            rec['output'] = 'content/' + rel; rec['bytes'] = len(blob)
        recs.append(rec)
    for op, o in want.items():
        recs.append({'phase': 'audio_native', 'source_package': pkgname, 'object_path': o[0],
                     'class': o[1], 'name': o[2], 'method': 'not_found_in_owner'})
    return recs

def main():
    plan = extract.plan('audio')
    recs = []
    with ProcessPoolExecutor() as ex:
        for r in ex.map(do_package, sorted(plan.items()), chunksize=4):
            recs += r
    os.makedirs(os.path.join(extract.MANI, 'extracted'), exist_ok=True)
    with open(os.path.join(extract.MANI, 'extracted', 'audio_native.jsonl'), 'w') as f:
        for r in recs: f.write(json.dumps(r) + '\n')
    from collections import Counter
    print('audio objects:', len(recs), Counter(r['method'] for r in recs))
    if '--no-wav' not in sys.argv:
        extract.convert_wav(max(1, (os.cpu_count() or 4) - 4))

if __name__ == '__main__':
    main()
