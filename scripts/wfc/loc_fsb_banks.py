"""Original localized sound banks (FSB4) for content/_LOC/<twin>/<group>/<name>.wav, kept like content/'s .fsb

  python loc_fsb_banks.py [--limit N] [--workers N]     stage + verify -> AssetTools/out/loc_fsb/<twin>/<group>/<name>.fsb
  python loc_fsb_banks.py --install                     copy the verified staged banks beside the WAVs in ExtractedAssets

vs_loc_twins.py decoded each localized SoundNodeWave's FSB4 bank to WAV and deleted the bank. This walks the same packages in
the same order (sorted *_int / *_FRA packages, first copy of each canonical path per twin wins, so the bank is the one the WAV
came from), writes the bank, and proves identity twice:
  fsb_md5_matches_loc_twins   md5 of the bank == fsb_md5 recorded by vs_loc_twins (manifests/audio/loc_twins.json)
  wav_redecode_identical      vgmstream r2117 (AssetTools/bin/vgmstream, same tool) decode of the bank == the existing WAV, byte for byte
Only banks passing both are installed. Manifest: manifests/audio/loc_fsb.json.
"""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, sounds, extract  # noqa: E402
from vs_common import ROOT  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
VGM = os.path.join(AT, 'bin', 'vgmstream', 'vgmstream-cli.exe')
STAGE = os.path.join(AT, 'out', 'loc_fsb')
LOC = os.path.join(ROOT, 'content', '_LOC')
MAN = os.path.join(AT, 'manifests', 'audio', 'loc_fsb.json')
GEN = 'AssetTools/scripts/wfc/loc_fsb_banks.py'

def md5(b): return hashlib.md5(b).hexdigest()

def collect(limit=None):
    """(twin, canonical path) -> bank bytes, exactly as vs_loc_twins picks them"""
    pk = sorted(n[:-4] for n in os.listdir(extract.COOKED) if n.endswith('.xxx') and
                (n.lower().endswith('_int.xxx') or n.lower().endswith('_fra.xxx')))
    seen = set(); n = 0
    for name in pk:
        twin = 'FRA' if name.lower().endswith('fra') else 'int'
        p = ue3pkg.Package(os.path.join(extract.COOKED, name + '.xxx'))
        for i, e in enumerate(p.exports):
            if p.class_name(e) not in ('SoundNodeWave', 'SoundNodeWaveEx'): continue
            g0, n0 = p.object_path(i + 1).split('.', 1)
            op = re.sub(r'_(INT|FRA)$', '', g0, flags=re.I) + '.' + n0
            if (twin, op) in seen: continue
            try: blob, _ = sounds.locate_fsb(p, e)
            except Exception: continue
            if not blob: continue
            seen.add((twin, op)); n += 1
            yield twin, op, name, blob
            if limit and n >= limit: return

def verify(item):
    twin, op, pkg, blob = item
    g, nm = op.split('.', 1)
    rel = '%s/%s/%s' % (twin, g, nm)          # same naming as vs_loc_twins' WAV (dots in the name stay in the file name)
    fsb = os.path.join(STAGE, rel + '.fsb'); os.makedirs(os.path.dirname(fsb), exist_ok=True)
    open(fsb, 'wb').write(blob)
    wav = os.path.join(LOC, twin, g, nm + '.wav')
    r = OrderedDict([('twin', twin), ('object_path', op), ('package', pkg), ('fsb', 'content/_LOC/%s.fsb' % rel), ('fsb_bytes', len(blob)),
                     ('fsb_md5', md5(blob)), ('wav', os.path.relpath(wav, ROOT).replace(os.sep, '/') if os.path.exists(wav) else None)])
    if r['wav']:
        fd, tmp = tempfile.mkstemp(suffix='.wav'); os.close(fd)
        try:
            subprocess.run([VGM, '-o', tmp, fsb], capture_output=True)
            r['wav_redecode_identical'] = os.path.getsize(tmp) == os.path.getsize(wav) and md5(open(tmp, 'rb').read()) == md5(open(wav, 'rb').read())
        finally:
            os.remove(tmp)
    return r

def stage(limit, workers):
    lt = json.load(open(os.path.join(AT, 'manifests', 'audio', 'loc_twins.json'), encoding='utf-8'))['waves']
    rows = []; st = Counter(); t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        for k, r in enumerate(ex.map(verify, collect(limit))):
            ref = (lt.get(r['object_path']) or {}).get(r['twin']) or {}
            r['fsb_md5_matches_loc_twins'] = bool(ref) and r['fsb_md5'].startswith(ref.get('fsb_md5') or '~')
            r['verified'] = bool(r.get('wav_redecode_identical')) and r['fsb_md5_matches_loc_twins']
            st['verified' if r['verified'] else 'NOT verified'] += 1
            rows.append(r)
            if k % 1000 == 0: print(k, dict(st), '%.0fs' % (time.time() - t0), flush=True)
    out = OrderedDict([('generated_by', GEN), ('generated', time.strftime('%Y-%m-%d %H:%M')),
                       ('decoder', 'vgmstream-cli r2117 (AssetTools/bin/vgmstream), same build that wrote the _LOC WAVs'),
                       ('layout', 'content/_LOC/<twin>/<group>/<name>.fsb beside the .wav; twin = int | FRA'),
                       ('installed', False), ('stats', dict(st)),
                       ('bytes', OrderedDict((t, sum(r['fsb_bytes'] for r in rows if r['twin'] == t)) for t in ('int', 'FRA'))),
                       ('banks', rows)])
    json.dump(out, open(MAN, 'w', encoding='utf-8'), indent=1)
    print(json.dumps({k: out[k] for k in ('stats', 'bytes')}))

def install():
    m = json.load(open(MAN, encoding='utf-8')); n = 0; skipped = []
    for r in m['banks']:
        if not r['verified']: skipped.append(r['fsb']); continue
        src = os.path.join(STAGE, r['fsb'][len('content/_LOC/'):]); dst = os.path.join(ROOT, r['fsb'])
        if os.path.exists(dst) and md5(open(dst, 'rb').read()) == r['fsb_md5']: continue
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst); n += 1
    m['installed'] = True; m['installed_at'] = time.strftime('%Y-%m-%d %H:%M'); m['not_installed (unverified)'] = skipped
    json.dump(m, open(MAN, 'w', encoding='utf-8'), indent=1)
    print('installed', n, 'skipped unverified', len(skipped))

if __name__ == '__main__':
    if '--install' in sys.argv: install()
    else:
        stage(int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None,
              int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 4)
