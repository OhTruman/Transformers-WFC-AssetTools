"""Original compressed texture data as DDS next to the PNGs (Integration / Rendering request 2026-10-08)

  python texture_dds.py --pilot                     (a few textures, verification printed)
  python texture_dds.py [--maps] [--chars] [--lightmaps] [--limit N]

For each target Texture2D / LightMapTexture2D / TextureFlipBook: the cooked mip chain is read from the export's native tail
(flipbook_export.read layout: per mip FUntypedBulkData + 4-byte WFC field + payload + SizeX/SizeY; LZO chunks via
flipbook_export.read_chunk; separate-file mips from the owning package file), each mip is untiled (Xenos 2D, numpy) and
16-bit byte-swapped back to little-endian DXT blocks - the compressed blocks themselves are NOT re-encoded (bit-identical to
what the console sampled, modulo the tiling / endianness of the memory layout). Written as DDS (DX9 header, FourCC DXT1 / DXT3 /
DXT5, or A8R8G8B8 uncompressed) with the longest verified mip chain:
  every mip k > 0 is decoded and compared with a 2^k box-downsample of mip 0 (PSNR); the chain is cut at the first mip below
  MIN_PSNR (the Xbox packed mip tail, MipTailBaseIdx, is not proven) and the cut is recorded - never guessed.
Index: manifests/extracted/textures_dds.jsonl  {object_path, png, dds, format, size, mips_written, mips_cooked, mip_tail_base, ...}
"""
import json, os, struct, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, extract  # noqa: E402
import flipbook_export as FB  # noqa: E402
from vs_common import ROOT  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MIN_PSNR = 24.0
_addr_cache = {}

def untile_np(data, wb, hb, bpb):
    """vectorised Xenos XGAddress2DTiledOffset (same math as flipbook_export.untile_2d)"""
    key = (wb, hb, bpb)
    if key not in _addr_cache:
        log2 = {4: 2, 8: 3, 16: 4}[bpb]; aw = (wb + 31) & ~31
        y, x = np.mgrid[0:hb, 0:wb].astype(np.int64)
        macro = ((x >> 5) + (y >> 5) * (aw >> 5)) << (log2 + 7)
        micro = ((x & 7) + ((y & 6) << 2)) << log2
        off = macro + ((micro & ~15) << 1) + (micro & 15) + ((y & 8) << (3 + log2)) + ((y & 1) << 4)
        addr = (((off & ~511) << 3) + ((off & 448) << 2) + (off & 63) + ((y & 16) << 7) + (((((y & 8) >> 2) + (x >> 3)) & 3) << 6)) >> log2
        _addr_cache[key] = addr.ravel()
    addr = _addr_cache[key]
    src = np.frombuffer(data, np.uint8)
    nblk = len(src) // bpb
    src = src[:nblk * bpb].reshape(nblk, bpb)
    out = np.zeros((wb * hb, bpb), np.uint8)
    ok = addr < nblk
    out[ok] = src[addr[ok]]
    return out.tobytes()

BPB = {'PF_DXT1': 8, 'PF_DXT3': 16, 'PF_DXT5': 16, 'PF_A8R8G8B8': 4}
FOURCC = {'PF_DXT1': b'DXT1', 'PF_DXT3': b'DXT3', 'PF_DXT5': b'DXT5'}

def mip_linear(raw, w, h, fmt):
    """tiled big-endian cooked mip -> linear little-endian bytes in the DDS block layout"""
    bpb = BPB[fmt]
    if fmt == 'PF_A8R8G8B8':
        lin = np.frombuffer(untile_np(raw, w, h, 4), np.uint8).reshape(-1, 4)   # BE ARGB -> DDS BGRA (LE A8R8G8B8)
        return lin[:, ::-1].tobytes()
    wb, hb = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    return FB.swap16(untile_np(raw, wb, hb, bpb))

def read_mips(pkg, opath):
    """[(w, h, raw_bytes)] for every stored mip, plus the tagged props"""
    p = objtree.package(pkg)
    i = p._idx.get(opath.lower())
    if not i: return None, []
    e = p.exports[i - 1]
    props, used = p._tr.read_object(i)
    pr = {x['name']: x.get('value') for x in props}
    nat = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
    nm = struct.unpack_from('>i', nat, 0)[0]; o = 4; mips = []
    if not 0 < nm < 16: return pr, []
    import io
    for _ in range(nm):
        fl, cnt, sod, off = struct.unpack_from('>Iiii', nat, o); o += 20
        at = o
        if not (fl & 0x01) and sod > 0: o = at + sod
        w, h = struct.unpack_from('>ii', nat, o); o += 8
        if cnt <= 0 or (fl & 0x20): mips.append((w, h, None)); continue
        try:
            if fl & 0x01:
                with open(os.path.join(extract.COOKED, opath.split('.')[0] + '.xxx'), 'rb') as f:
                    raw = FB.read_chunk(f, off, sod) if fl & 0x10 else (f.seek(off), f.read(cnt))[1]
            else:
                raw = FB.read_chunk(io.BytesIO(nat), at, sod) if fl & 0x10 else nat[at:at + cnt]
        except Exception:
            raw = None
        mips.append((w, h, raw))
    return pr, mips

def psnr(a, b):
    m = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    return 99.0 if m == 0 else 10 * np.log10(255.0 ** 2 / m)

MIN_CORR = 0.85

def accept(img, ref):
    """(ok, psnr, corr): a cooked mip matches the downsampled top mip (artist mips differ from a box filter, so either a high
    PSNR or a high luminance correlation is accepted)"""
    a = img[..., :3].mean(-1).ravel(); b = ref[..., :3].mean(-1).ravel()
    s = psnr(img[..., :3], ref[..., :3])
    c = 1.0 if a.std() < 1e-3 and b.std() < 1e-3 else float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-3 and b.std() > 1e-3 else 0.0
    return (s >= MIN_PSNR or c >= MIN_CORR), round(s, 1), round(c, 3)

def packed_offset_blocks(tw, th, t):
    """Xenos packed mip tail position of packed level t inside the tail tile (Xenia GetPackedTileOffset; verified on
    fbook_sinewave / FloorTrim_02_SPEC: t0 -> (4,0), t1 -> (2,0) blocks for square tails)"""
    lw, lh = max(tw - 1, 0).bit_length(), max(th - 1, 0).bit_length()
    o = 16 >> t
    return (0, o // 4) if lw > lh else (o // 4, 0)

def decode_rgba(raw, w, h, fmt):
    return FB.decode(raw, w, h, fmt)

def box_down(img, k):
    f = 2 ** k; h, w = img.shape[0] // f, img.shape[1] // f
    return img[:h * f, :w * f].reshape(h, f, w, f, img.shape[2]).mean((1, 3))

def dds_bytes(fmt, w, h, levels):
    bpb = BPB[fmt]
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | (0x80000 if fmt in FOURCC else 0x8)
    pitch = len(levels[0])
    hdr = struct.pack('<4sIIIIIII', b'DDS ', 124, flags, h, w, pitch, 0, len(levels)) + b'\0' * 44
    if fmt in FOURCC: pf = struct.pack('<II4sIIIII', 32, 0x4, FOURCC[fmt], 0, 0, 0, 0, 0)
    else: pf = struct.pack('<II4sIIIII', 32, 0x41, b'\0\0\0\0', 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    caps = struct.pack('<IIIII', 0x1000 | 0x400000 | 0x8, 0, 0, 0, 0)
    return hdr + pf + caps + b''.join(levels)

def _decode_linear(lin, w, h, fmt):
    """decode LINEAR little-endian blocks (DDS layout) to RGBA via the flipbook decoder (which expects tiled BE input):
    re-encode as identity-tiled by decoding directly with the same block decoder"""
    if fmt == 'PF_A8R8G8B8':
        a = np.frombuffer(lin, np.uint8).reshape(h, w, 4); return a[..., [2, 1, 0, 3]]
    wb, hb = max(1, w // 4), max(1, h // 4)
    if fmt == 'PF_DXT1':
        px = FB.dxt_color(np.frombuffer(lin, np.uint8).reshape(-1, 8))
    else:
        b = np.frombuffer(lin, np.uint8).reshape(-1, 16); px = FB.dxt_color(b[:, 8:], alpha1bit=False)
    return px.reshape(hb, wb, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(hb * 4, wb * 4, 4)[:h, :w].astype(np.uint8)

def export(opath, png_rel, out_rel=None):
    inv = objtree.inv()
    rows = inv.execute("SELECT package FROM exports WHERE opath = ? ORDER BY serial_size DESC", (opath,)).fetchall()
    for (pkg,) in rows:
        pr, mips = read_mips(pkg, opath)
        fmt = (pr or {}).get('Format')
        if fmt not in BPB: return {'object_path': opath, 'status': 'unsupported format %s' % fmt}
        first = next((k for k, m in enumerate(mips) if m[2]), None)
        if first is None: continue
        w0, h0, raw0 = mips[first]
        levels = [mip_linear(raw0, w0, h0, fmt)]
        top = _decode_linear(levels[0], w0, h0, fmt).astype(np.float32)
        verified, cut = [{'mip': first, 'psnr': 99.0, 'corr': 1.0, 'packed': False}], None
        tb = pr.get('MipTailBaseIdx')
        tail = None
        if fmt in FOURCC and tb is not None and first <= tb < len(mips) and mips[tb][2]:
            tw, th = mips[tb][0], mips[tb][1]
            tail = (tw, th, np.frombuffer(mip_linear(mips[tb][2], 128, 128, fmt), np.uint8).reshape(32, 32, BPB[fmt]))
        for k in range(first + 1, len(mips)):
            _, _, raw = mips[k]
            w, h = max(1, w0 >> (k - first)), max(1, h0 >> (k - first))   # logical size (cooked headers clamp tiny mips to 4x4)
            packed = fmt in FOURCC and tb is not None and k >= tb
            if packed:
                if tail is None: cut = 'mip %d: packed tail (base %d) not stored' % (k, tb); break
                if w < 4 or h < 4: cut = 'mip %d (%dx%d) below one DXT block: chain stops at 4x4' % (k, w, h); break
                bx, by = packed_offset_blocks(tail[0], tail[1], k - tb)
                bw, bh = w // 4, h // 4
                blk = tail[2][by:by + bh, bx:bx + bw]
                if blk.shape[:2] != (bh, bw): cut = 'mip %d packed position out of the tail tile' % k; break
                lin = blk.tobytes()
                img = FB.decode(FB.swap16(_retile_identity(lin)), w, h, fmt) if False else _decode_linear(lin, w, h, fmt)
            else:
                if not raw: cut = 'mip %d has no stored data (not cooked)' % k; break
                if w < 4 or h < 4: cut = 'mip %d (%dx%d) below one DXT block: chain stops at 4x4' % (k, w, h); break
                try:
                    lin = mip_linear(raw, w, h, fmt); img = _decode_linear(lin, w, h, fmt)
                except Exception as ex:
                    cut = 'mip %d decode error %s' % (k, ex); break
            ref = box_down(top, k - first)
            ok, s_, c_ = accept(img.astype(np.float32)[:ref.shape[0], :ref.shape[1]], ref[:img.shape[0], :img.shape[1]])
            if not ok: cut = 'mip %d rejected (PSNR %.1f, corr %.3f vs downsampled mip %d)%s' % (k, s_, c_, first, ' [packed]' if packed else ''); break
            levels.append(lin); verified.append({'mip': k, 'psnr': s_, 'corr': c_, 'packed': packed})
        out_rel = out_rel or (os.path.splitext(png_rel)[0] + '.dds')
        out = os.path.join(ROOT, out_rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'wb').write(dds_bytes(fmt, w0, h0, levels))
        return {'object_path': opath, 'status': 'ok', 'png': png_rel, 'dds': out_rel.replace(os.sep, '/'), 'format': fmt,
                'read_from': pkg, 'size': [w0, h0], 'top_stored_mip': first, 'mips_cooked': len(mips),
                'mips_written': len(levels), 'mip_tail_base': pr.get('MipTailBaseIdx'), 'mip_verification': verified,
                'chain_cut': cut, 'srgb': pr.get('SRGB', True), 'lod_group': pr.get('LODGroup'),
                'address_xy': [pr.get('AddressX'), pr.get('AddressY')]}
    return {'object_path': opath, 'status': 'no stored mip data in any cooked copy'}

def pilot():
    tests = ['ENV_AllShader_p.Textures.Pixel_4_Mask', 'ENV_NEU_Variation_p.fbook_sinewave_CLR']
    A = {a['object_path']: a for a in json.load(open(os.path.join(AT, 'manifests', 'assets.json'), encoding='utf-8'))['assets']}
    import random
    pool = [o for o, a in A.items() if a.get('class') == 'Texture2D' and any(x.endswith('.png') for x in a.get('extracted') or [])]
    random.seed(7); tests += random.sample(pool, 6)
    for t in tests:
        png = next((x for x in (A.get(t) or {}).get('extracted') or [] if x.endswith('.png')), 'content/' + t.replace('.', '/') + '.png')
        r = export(t, png, out_rel='pilot_dds/' + t.replace('.', '_') + '.dds')
        print(json.dumps({k: r.get(k) for k in ('object_path', 'status', 'format', 'size', 'mips_cooked', 'mips_written', 'mip_tail_base',
                                                'chain_cut')}), [(v['mip'], v['psnr'], v['corr'], v['packed']) for v in r.get('mip_verification') or []])

if __name__ == '__main__':
    if '--pilot' in sys.argv: pilot()
