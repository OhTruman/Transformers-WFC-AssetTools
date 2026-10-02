"""Decode cooked Xbox 360 Texture3D (volume) textures, e.g. colour-grading CLUTs.

Ported (read-only reference) from the Rendering agent's tools/render/xbox_texture.py, which follows
xenia's src/xenia/gpu/texture_address.h Tiled3D addressing; layout re-validated here (smoothness and
monotonicity of the decoded MP_Streets_CLUT, see vs_postprocess.py).

Native tail after the tagged props of a Texture3D (WFC 511/144): bulk header
[u32 flags][i32 count][i32 size][i32 offset][i32 extra] (20 bytes) then the top mip, big-endian A8R8G8B8,
Xenos 3D-tiled.  SizeX/Y/Z come from the tags (default 32).
"""
import numpy as np

def _tiled_combine(oib, bank, pipe, ylsb):
    return ((ylsb << 4) | (pipe << 6) | (bank << 11) | (oib & 0b1111) | (((oib >> 4) & 1) << 5) |
            (((oib >> 5) & 0b111) << 8) | ((oib >> 8) << 12))

def tiled3d_offset(x, y, z, pitch_aligned, height_aligned, bpb_log2):
    outer = ((((z >> 2) * (height_aligned >> 4) + (y >> 4)) * (pitch_aligned >> 5)) + (x >> 5)) << 7
    inner = ((z & 3) << 5) | (((y >> 1) & 3) << 3) | (x & 7)
    oib = (outer | inner) << bpb_log2
    bank = ((y >> 3) ^ (z >> 2)) & 1
    pipe = ((x >> 3) & 3) ^ (bank << 1)
    return _tiled_combine(oib, bank, pipe, y & 1)

def decode_volume_argb8(data, sx, sy, sz):
    """big-endian A8R8G8B8 tiled volume -> uint8 array [z][y][x][RGBA]"""
    pa, ha = (sx + 31) & ~31, (sy + 31) & ~31
    out = np.zeros((sz, sy, sx, 4), 'u1')
    for z in range(sz):
        for y in range(sy):
            for x in range(sx):
                o = tiled3d_offset(x, y, z, pa, ha, 2)
                a, r, g, b = data[o:o + 4]
                out[z, y, x] = (r, g, b, a)
    return out

def decode_texture3d(pkg, opath):
    """(volume [z][y][x][RGBA], info) for a Texture3D export in package object `pkg` (objtree.package)."""
    i = pkg._idx[opath.lower()]; e = pkg.exports[i - 1]
    tags, used = pkg._tr.read_object(i)
    import typed_props as tp
    d = tp.to_dict(tags)
    sx, sy, sz = d.get('SizeX', 32), d.get('SizeY', 32), d.get('SizeZ', 32)
    tail = pkg.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
    vol = decode_volume_argb8(tail[20:20 + sx * sy * sz * 4], sx, sy, sz)
    return vol, {'size': [sx, sy, sz], 'format': d.get('Format'), 'srgb_tag': d.get('SRGB'), 'tail_bytes': len(tail)}
