"""FMOD FSB4 bank header reader (WFC Xbox 360 SoundNodeWaveEx payloads), read-only.

Each cooked SoundNodeWaveEx carries one FSB4 bank (sounds.locate_fsb). Layout (little-endian):
  main header (48 bytes)
    0  'FSB4'            4  i32 numsamples      8  i32 shdrsize (all sample headers)   12 i32 datasize
    16 u32 version       20 u32 mode (bank flags)   24 8 x 00                          32 16-byte hash
  sample header i (starts at 48, u16 size each):
    0  u16 size          2  char name[30]
    32 u32 lengthsamples (PCM sample frames)     36 u32 lengthcompressedbytes
    40 u32 loopstart     44 u32 loopend   (sample frames, inclusive end)
    48 u32 mode (FSOUND_* sample flags)          52 i32 deffreq (Hz)
    56 u16 defvol        58 i16 defpan    60 u16 defpri    62 u16 numchannels
    64 f32 mindistance   68 f32 maxdistance
    72 ... size-72 bytes: codec-specific tail (kept raw; not decoded)
Sample mode flags used here: 0x1 LOOP_OFF, 0x2 LOOP_NORMAL, 0x4 LOOP_BIDI, 0x20 MONO, 0x40 STEREO, 0x100000 3D,
0x2000 2D, 0x1000000 XMA.
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, sounds  # noqa: E402

FLAGS = {0x1: 'LOOP_OFF', 0x2: 'LOOP_NORMAL', 0x4: 'LOOP_BIDI', 0x8: '8BITS', 0x10: '16BITS', 0x20: 'MONO', 0x40: 'STEREO',
         0x80: 'UNSIGNED', 0x100: 'SIGNED', 0x200: 'MPEG', 0x1000: 'HW3D', 0x2000: '2D', 0x100000: '3D',
         0x400000: 'IMAADPCM', 0x800000: 'VAG', 0x1000000: 'XMA', 0x2000000: 'GCADPCM', 0x4000000: 'MULTICHANNEL',
         0x8000000: 'OGG/CELT', 0x10000000: 'MPEG_LAYER3'}

def flag_names(m):
    return [n for b, n in sorted(FLAGS.items()) if m & b]

def parse(blob):
    if blob[:4] != b'FSB4': raise ValueError('not FSB4')
    ns, shdr, dsize, ver, bmode = struct.unpack_from('<iiiII', blob, 4)
    out = {'magic': 'FSB4', 'numsamples': ns, 'shdrsize': shdr, 'datasize': dsize, 'version_raw': '0x%08X' % ver,
           'bank_mode_raw': '0x%08X' % bmode, 'hash_hex': blob[32:48].hex(), 'samples': []}
    i = 48
    for k in range(ns):
        size = struct.unpack_from('<H', blob, i)[0]
        h = blob[i:i + size]
        name = h[2:32].split(b'\0')[0].decode('latin-1')
        ls, lc, lst, lend, mode, freq = struct.unpack_from('<IIIIIi', h, 32)
        dv, dp, dpri, nch = struct.unpack_from('<HhHH', h, 56)
        mind, maxd = struct.unpack_from('<ff', h, 64)
        out['samples'].append({
            'index': k, 'header_offset_in_bank': i, 'header_size': size, 'name': name,
            'lengthsamples': ls, 'lengthcompressedbytes': lc, 'loopstart': lst, 'loopend': lend,
            'mode_raw': '0x%08X' % mode, 'mode_flags': flag_names(mode), 'deffreq': freq, 'defvol': dv, 'defpan': dp,
            'defpri': dpri, 'numchannels': nch, 'mindistance': mind, 'maxdistance': maxd,
            'raw_header_hex': h.hex(),
            'field_offsets_in_sample_header': {'lengthsamples': 32, 'lengthcompressedbytes': 36, 'loopstart': 40, 'loopend': 44,
                                               'mode': 48, 'deffreq': 52, 'numchannels': 62},
            'undecoded_tail_hex (offset 72..size)': h[72:].hex()})
        i += size
    return out

def bank_for(wave, prefer=()):
    """(package, export index, blob, method) of the cooked wave; prefers the given packages."""
    inv = objtree.inv()
    rows = [r[0] for r in inv.execute('SELECT package FROM exports WHERE opath=? ORDER BY serial_size DESC', (wave,)).fetchall()]
    pk = next((p for p in prefer if p in rows), rows[0] if rows else None)
    if not pk: return None, None, None, 'not cooked'
    p = objtree.package(pk); idx = p._idx[wave.lower()]; e = p.exports[idx - 1]
    blob, how = sounds.locate_fsb(p, e)
    return pk, idx, blob, how
