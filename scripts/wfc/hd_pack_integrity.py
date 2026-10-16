"""Integrity pass over an HD pack snapshot (Integration 2026-10-16, after a size question on Tubes_Road): for every index row the file
exists, its size equals the row's `bytes`, the DDS header agrees with the row (width / height / format / full mip chain) and the size
equals the size computed from (format, size, mips); files on disk under pack/content that no row names; duplicate dds paths.
sha256 of every file goes into the report (the snapshot's fingerprint).

  python hd_pack_integrity.py <snapshot dir> [--no-hash]   -> <snapshot>/integrity.json, exit 1 on any failure
Also called by the snapshot writer (hd_full_push.py snapshot) before it reports a snapshot as frozen.
"""
import hashlib, json, os, struct, sys, time
from collections import Counter, OrderedDict as OD

BPP = {'PF_DXT1': 4, 'PF_DXT5': 8, 'PF_A8R8G8B8': 32}
DX10 = {71: 'PF_DXT1', 72: 'PF_DXT1', 77: 'PF_DXT5', 78: 'PF_DXT5', 87: 'PF_A8R8G8B8', 91: 'PF_A8R8G8B8', 28: 'PF_A8R8G8B8', 29: 'PF_A8R8G8B8'}

def header(p):
    b = open(p, 'rb').read(148)
    if b[:4] != b'DDS ': return None
    h, w, _, _, mips = struct.unpack('<5I', b[12:32]); flags, four, bits = struct.unpack('<I4sI', b[80:92])
    hdr = 128
    if four == b'DX10': fmt = DX10.get(struct.unpack('<I', b[128:132])[0], 'DXGI_%d' % struct.unpack('<I', b[128:132])[0]); hdr = 148
    elif four == b'DXT1': fmt = 'PF_DXT1'
    elif four in (b'DXT5', b'DXT4'): fmt = 'PF_DXT5'
    elif flags & 0x40 and bits == 32: fmt = 'PF_A8R8G8B8'
    else: fmt = '?%s/%d' % (four, bits)
    return w, h, max(1, mips), fmt, hdr

def expected(w, h, mips, fmt, hdr):
    n = 0
    for _ in range(mips):
        if fmt in ('PF_DXT1', 'PF_DXT5'): n += max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * (8 if fmt == 'PF_DXT1' else 16)
        else: n += w * h * BPP[fmt] // 8
        w, h = max(1, w // 2), max(1, h // 2)
    return n + hdr

def check(snap, do_hash=True):
    pack = os.path.join(snap, 'pack'); idx = json.load(open(os.path.join(pack, 'hd_index.json'), encoding='utf-8'))
    rows = idx['rows']; fails = []; recs = []; seen = set()
    dup = [k for k, v in Counter(r['dds'].lower() for r in rows).items() if v > 1]
    if dup: fails += ['duplicate dds path: ' + d for d in dup]
    for r in rows:
        p = os.path.join(pack, r['dds']); seen.add(os.path.normcase(os.path.normpath(p)))
        if not os.path.exists(p): fails.append('missing: ' + r['dds']); continue
        sz = os.path.getsize(p); hd = header(p); rec = OD([('dds', r['dds']), ('bytes', sz)])
        if sz != r['bytes']: fails.append('size %d != index %d: %s' % (sz, r['bytes'], r['dds']))
        if not hd: fails.append('not a DDS: ' + r['dds'])
        else:
            w, h, mips, fmt, hdr = hd
            full = max(w, h).bit_length()
            if [w, h] != list(r['size']): fails.append('header %dx%d != index %s: %s' % (w, h, r['size'], r['dds']))
            if fmt != r['format']: fails.append('header %s != index %s: %s' % (fmt, r['format'], r['dds']))
            if mips != full: fails.append('mips %d != full chain %d: %s' % (mips, full, r['dds']))
            if fmt in BPP and sz != expected(w, h, mips, fmt, hdr): fails.append('size %d != computed %d (%s %dx%d %d mips): %s' % (sz, expected(w, h, mips, fmt, hdr), fmt, w, h, mips, r['dds']))
        if do_hash: rec['sha256'] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
        recs.append(rec)
    extra = []
    for d, _, fs in os.walk(os.path.join(pack, 'content')):
        for f in fs:
            q = os.path.normcase(os.path.normpath(os.path.join(d, f)))
            if q not in seen: extra.append(os.path.relpath(os.path.join(d, f), pack).replace(os.sep, '/'))
    fails += ['not in index: ' + e for e in extra]
    rep = OD([('snapshot', snap), ('checked', time.strftime('%Y-%m-%d %H:%M')), ('generated_by', 'AssetTools/scripts/wfc/hd_pack_integrity.py'),
              ('rows', len(rows)), ('bytes', sum(r['bytes'] for r in rows)), ('formats', dict(Counter(r['format'] for r in rows))),
              ('failures', fails), ('status', 'PASS' if not fails else 'FAIL'), ('files', recs)])
    json.dump(rep, open(os.path.join(snap, 'integrity.json'), 'w', encoding='utf-8'), indent=1)
    print(rep['status'], len(rows), 'rows', round(rep['bytes'] / 2 ** 30, 2), 'GiB', len(fails), 'failures', fails[:10], flush=True)
    return not fails

if __name__ == '__main__':
    sys.exit(0 if check(sys.argv[1], '--no-hash' not in sys.argv) else 1)
