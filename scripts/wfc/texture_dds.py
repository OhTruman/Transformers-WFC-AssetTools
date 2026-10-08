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
Verification is memory-bounded: each level is compared with a 2x box-downsample of the previous accepted level on a centred
crop of at most 128 x 128 px (only those blocks are decoded).
Index: manifests/extracted/textures_dds.jsonl  {object_path, png, dds, format, size, mips_written, mips_cooked, mip_tail_base, ...}
"""
import json, os, re, struct, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, extract  # noqa: E402
import flipbook_export as FB  # noqa: E402
from vs_common import ROOT  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
RESUME = '--resume' in sys.argv
OUT_ROOT = os.path.join(AT, 'out', 'dds')   # mirror tree: out/dds/<path of the PNG relative to ExtractedAssets>.dds (Integration)
MIN_PSNR = 24.0
_addr_cache = {}

def untile_np(data, wb, hb, bpb):
    """vectorised Xenos XGAddress2DTiledOffset (same math as flipbook_export.untile_2d)"""
    key = (wb, hb, bpb)
    if key not in _addr_cache:
        log2 = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}[bpb]; aw = (wb + 31) & ~31
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

BPB = {'PF_DXT1': 8, 'PF_DXT3': 16, 'PF_DXT5': 16, 'PF_A8R8G8B8': 4, 'PF_G8': 1}
FOURCC = {'PF_DXT1': b'DXT1', 'PF_DXT3': b'DXT3', 'PF_DXT5': b'DXT5'}

def mip_linear(raw, w, h, fmt):
    """tiled big-endian cooked mip -> linear little-endian bytes in the DDS block layout"""
    bpb = BPB[fmt]
    if fmt == 'PF_A8R8G8B8':
        lin = np.frombuffer(untile_np(raw, w, h, 4), np.uint8).reshape(-1, 4)   # BE ARGB -> DDS BGRA (LE A8R8G8B8)
        return lin[:, ::-1].tobytes()
    if fmt == 'PF_G8':
        return untile_np(raw, w, h, 1)                                          # 8-bit luminance, no byte order
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

def tail_tile(raw, tw, th, fmt):
    """the packed-tail surface of the tail-base mip as a (rows, cols, bpb) block array: width = the tail-base level's block
    width aligned to 32, height 32 blocks (Xenos tiles are 32 x 32 blocks; a 256 x 16 tail base is 64 x 32 blocks)"""
    bpb = BPB[fmt]
    cols = max(32, ((max(1, tw // 4) + 31) // 32) * 32); rows = max(32, ((max(1, th // 4) + 31) // 32) * 32)
    return np.frombuffer(mip_linear(raw, cols * 4, rows * 4, fmt), np.uint8).reshape(rows, cols, bpb)

def packed_offset_blocks(tw, th, t):
    """Xenos packed mip tail position of packed level t inside the tail tile (Xenia GetPackedTileOffset; verified on
    fbook_sinewave / FloorTrim_02_SPEC: t0 -> (4,0), t1 -> (2,0) blocks for square tails)"""
    lw, lh = max(tw - 1, 0).bit_length(), max(th - 1, 0).bit_length()
    o = 16 >> t
    return (0, o // 4) if lw > lh else (o // 4, 0)

def packed_base_position(tile, w, h, fmt, png_rel):
    """whole texture inside the packed tail (MipTailBaseIdx 0): position of the base level in the tail tile, in blocks.
    Observed (exact match with umodel PNGs, 2026-10-08): min side < 16 -> origin; 16 x 32 / 32 x 16 / 64 x 16 / 16 x 128 -> the Xenia
    packed offset (16 px along the short axis); 16 x 16 -> origin for some pages, (8, 0) for others (no rule found). So the
    candidates are tried against the PNG when there is one; without an exact match the rule is used and marked PROVISIONAL."""
    bw, bh = max(1, w // 4), max(1, h // 4)
    rule = (0, 0) if min(w, h) < 16 else packed_offset_blocks(w, h, 0)
    if png_rel and os.path.exists(os.path.join(ROOT, png_rel)):
        from PIL import Image
        q = np.asarray(Image.open(os.path.join(ROOT, png_rel)).convert('RGB')).astype(np.int16)
        for c in dict.fromkeys([rule, (0, 0), packed_offset_blocks(w, h, 0), (8, 0), (0, 8)]):
            blk = tile[c[1]:c[1] + bh, c[0]:c[0] + bw]
            if blk.shape[:2] != (bh, bw): continue
            img = _decode_linear(np.ascontiguousarray(blk).tobytes(), w, h, fmt)[..., :3].astype(np.int16)
            if img.shape == q.shape and not np.abs(img - q).max():
                return c[0], c[1], 'exact RGB match with the umodel PNG'
    return rule[0], rule[1], 'PROVISIONAL rule (no exact PNG match)'

def dxt5_alpha(lin):
    """BC3 alpha per texel (blocks x 16): a0 > a1 -> 8-step ramp, else 6-step ramp + 0 + 255; 3-bit LE indices"""
    b = np.frombuffer(lin, np.uint8).reshape(-1, 16).astype(np.int32)
    a0, a1 = b[:, 0], b[:, 1]
    i = np.arange(1, 7)[None, :]
    ramp8 = ((7 - i) * a0[:, None] + i * a1[:, None]) // 7
    ramp6 = ((5 - i[:, :4]) * a0[:, None] + i[:, :4] * a1[:, None]) // 5
    pal6 = np.concatenate([ramp6, np.zeros((len(b), 1), np.int32), np.full((len(b), 1), 255, np.int32)], 1)
    pal = np.where((a0 > a1)[:, None], ramp8, pal6)
    pal = np.concatenate([a0[:, None], a1[:, None], pal], 1)
    bits = sum(b[:, 2 + k].astype(np.int64) << (8 * k) for k in range(6))
    idx = np.stack([(bits >> (3 * t)) & 7 for t in range(16)], 1)
    return np.take_along_axis(pal, idx.astype(np.int64), 1)

def alpha_all_zero(lin, w, h, fmt):
    if fmt == 'PF_A8R8G8B8': return not any(lin[3::4])
    return not dxt5_alpha(lin).any()

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
    elif fmt == 'PF_G8': pf = struct.pack('<II4sIIIII', 32, 0x20000, b'\0\0\0\0', 8, 0xFF, 0, 0, 0)   # DDPF_LUMINANCE L8
    else: pf = struct.pack('<II4sIIIII', 32, 0x41, b'\0\0\0\0', 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    caps = struct.pack('<IIIII', 0x1000 | 0x400000 | 0x8, 0, 0, 0, 0)
    return hdr + pf + caps + b''.join(levels)

def _decode_linear(lin, w, h, fmt):
    """decode LINEAR little-endian blocks (DDS layout) to RGBA via the flipbook decoder (which expects tiled BE input):
    re-encode as identity-tiled by decoding directly with the same block decoder"""
    if fmt == 'PF_A8R8G8B8':
        a = np.frombuffer(lin, np.uint8).reshape(h, w, 4); return a[..., [2, 1, 0, 3]]
    if fmt == 'PF_G8':
        g = np.frombuffer(lin, np.uint8).reshape(h, w); return np.stack([g, g, g, np.full_like(g, 255)], -1)
    wb, hb = max(1, w // 4), max(1, h // 4)
    if fmt == 'PF_DXT1':
        px = FB.dxt_color(np.frombuffer(lin, np.uint8).reshape(-1, 8))
    else:
        b = np.frombuffer(lin, np.uint8).reshape(-1, 16); px = FB.dxt_color(b[:, 8:], alpha1bit=False)
    return px.reshape(hb, wb, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(hb * 4, wb * 4, 4)[:h, :w].astype(np.uint8)

def _evict():
    """drop cached packages AND collect: objtree.package sets p._tr = TypedReader(p) (a reference cycle), so the decompressed
    package bytes are only freed by the cycle collector - without gc.collect() ~380 MB per level package accumulates"""
    import gc
    objtree.package.cache_clear(); gc.collect()

def crop_blocks(lin, w, h, fmt, x0, y0, cw, ch):
    """decode only the pixel region [x0, x0+cw) x [y0, y0+ch) (block aligned) of a LINEAR level (memory-bounded verification)"""
    if fmt == 'PF_A8R8G8B8':
        a = np.frombuffer(lin, np.uint8).reshape(h, w, 4)[y0:y0 + ch, x0:x0 + cw]; return a[..., [2, 1, 0, 3]]
    if fmt == 'PF_G8':
        g = np.frombuffer(lin, np.uint8).reshape(h, w)[y0:y0 + ch, x0:x0 + cw]; return np.stack([g, g, g, np.full_like(g, 255)], -1)
    bpb = BPB[fmt]; wb = max(1, w // 4)
    blk = np.frombuffer(lin, np.uint8).reshape(-1, wb, bpb)[y0 // 4:(y0 + ch) // 4, x0 // 4:(x0 + cw) // 4]
    return _decode_linear(np.ascontiguousarray(blk).tobytes(), cw, ch, fmt)

def verify_pair(prev, pw, ph, cur, w, h, fmt):
    """compare level k (cur) with a 2x box-downsample of level k-1 (prev) on a centred crop <= 128x128 px"""
    cw, ch = min(w, 128) // 4 * 4, min(h, 128) // 4 * 4
    if cw < 4 or ch < 4: return True, 99.0, 1.0
    x0, y0 = (w - cw) // 2 // 4 * 4, (h - ch) // 2 // 4 * 4
    c = crop_blocks(cur, w, h, fmt, x0, y0, cw, ch).astype(np.float32)
    pv = crop_blocks(prev, pw, ph, fmt, 2 * x0, 2 * y0, 2 * cw, 2 * ch).astype(np.float32)
    return accept(c, box_down(pv, 1))

def export(opath, png_rel, out_rel=None):
    inv = objtree.inv()
    rows = inv.execute("SELECT package FROM exports WHERE opath = ? COLLATE NOCASE ORDER BY serial_size DESC", (opath,)).fetchall()
    # the copy with the largest STORED top mip wins (lightmap level copies can lack their top mips)
    # own package first (small, holds the full chain when cooked standalone); level-package copies only if needed (memory)
    own = opath.split('.')[0].lower()
    seen_ = []
    for (p_,) in rows:                    # rows: largest serialized copy first
        if p_ not in seen_: seen_.append(p_)
    order = sorted(seen_, key=lambda p_: 0 if p_.lower() in (own, own + '_lm') else 1)   # stable: own package, then by size
    cands = []
    for pkg in order[:4]:
        try: pr_, mips_ = read_mips(pkg, opath)
        except MemoryError: _evict(); continue
        except Exception: continue
        finally:
            if objtree.package.cache_info().currsize > 1: _evict()
        f_ = next((k for k, m in enumerate(mips_) if m[2]), None)
        if f_ is not None:
            cands.append((f_, -sum(1 for m in mips_ if m[2]), pkg, pr_, mips_))
            if f_ == 0 and all(m[2] for m in mips_[:max(1, (pr_.get('MipTailBaseIdx') or len(mips_)) + 1)]):
                break                    # full chain down to the tail stored here: no need to open other copies
    cands.sort(key=lambda x: (x[0], x[1]))
    for _f, _n, pkg, pr, mips in cands[:1]:
        fmt = (pr or {}).get('Format')
        if fmt not in BPB: return {'object_path': opath, 'status': 'unsupported format %s' % fmt}
        first = next((k for k, m in enumerate(mips) if m[2]), None)
        if first is None: continue
        w0, h0, raw0 = mips[first]
        base_src = None
        tb0 = pr.get('MipTailBaseIdx')
        if fmt in FOURCC and tb0 is not None and first >= tb0 and mips[tb0][2]:
            # the top stored level is itself inside the Xbox packed mip tail (e.g. 1024x64 lightmaps whose top stored mip is
            # 256x16): take it from the tail tile at its packed position, like the lower packed levels
            tile = tail_tile(mips[tb0][2], mips[tb0][0], mips[tb0][1], fmt)
            if first == tb0 == 0:
                bx, by, base_src = packed_base_position(tile, w0, h0, fmt, png_rel)
            else:
                bx, by = packed_offset_blocks(mips[tb0][0], mips[tb0][1], first - tb0)
            levels = [np.ascontiguousarray(tile[by:by + max(1, h0 // 4), bx:bx + max(1, w0 // 4)]).tobytes()]
        else:
            levels = [mip_linear(raw0, w0, h0, fmt)]
        verified, cut = [{'mip': first, 'psnr': 99.0, 'corr': 1.0, 'packed': False}], None
        pw_, ph_ = w0, h0
        tb = pr.get('MipTailBaseIdx')
        tail = None
        if fmt in FOURCC and tb is not None and first <= tb < len(mips) and mips[tb][2]:
            tw, th = mips[tb][0], mips[tb][1]
            tail = (tw, th, tail_tile(mips[tb][2], tw, th, fmt))
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
            else:
                if not raw: cut = 'mip %d has no stored data (not cooked)' % k; break
                if w < 4 or h < 4: cut = 'mip %d (%dx%d) below one DXT block: chain stops at 4x4' % (k, w, h); break
                try:
                    lin = mip_linear(raw, w, h, fmt)
                except Exception as ex:
                    cut = 'mip %d decode error %s' % (k, ex); break
            ok, s_, c_ = verify_pair(levels[-1], pw_, ph_, lin, w, h, fmt)
            if not ok: cut = 'mip %d rejected (PSNR %.1f, corr %.3f vs downsampled mip %d)%s' % (k, s_, c_, k - 1, ' [packed]' if packed else ''); break
            levels.append(lin); verified.append({'mip': k, 'psnr': s_, 'corr': c_, 'packed': packed}); pw_, ph_ = w, h
        out_rel = out_rel or (os.path.splitext(png_rel)[0] + '.dds')
        out = os.path.join(OUT_ROOT, out_rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'wb').write(dds_bytes(fmt, w0, h0, levels))
        return {'object_path': opath, 'status': 'ok', 'png': png_rel, 'dds': out_rel.replace(os.sep, '/'), 'format': fmt,
                'read_from': pkg, 'size': [w0, h0], 'top_stored_mip': first, 'mips_cooked': len(mips),
                'mips_written': len(levels), 'mip_tail_base': pr.get('MipTailBaseIdx'), 'mip_verification': verified,
                'chain_cut': cut, 'srgb': pr.get('SRGB', True), 'lod_group': pr.get('LODGroup'),
                'address_xy': [pr.get('AddressX'), pr.get('AddressY')],
                **({'packed_base_offset_blocks': [bx, by], 'packed_base_offset_source': base_src} if base_src else {}),
                # A8R8G8B8 whose cooked alpha is 0 everywhere (Scaleform GFx pages, LowHealthScanline): kept verbatim; umodel's PNG
                # for these is RGB (opaque), so a PNG compare differs in alpha only
                **({'alpha_all_zero': alpha_all_zero(levels[0], w0, h0, fmt)} if fmt in ('PF_A8R8G8B8', 'PF_DXT5') else {})}
    return {'object_path': opath, 'status': 'no stored mip data in any cooked copy'}

def pilot():
    tests = ['ENV_AllShader_p.Textures.Pixel_4_Mask', 'ENV_NEU_Variation_p.fbook_sinewave_CLR']
    A = {a['object_path']: a for a in json.load(open(os.path.join(AT, 'manifests', 'assets.json'), encoding='utf-8'))['assets']}
    import random
    pool = [o for o, a in A.items() if a.get('class') == 'Texture2D' and any(x.endswith('.png') for x in a.get('extracted') or [])]
    random.seed(7); tests += random.sample(pool, 6)
    for t in tests:
        png = next((x for x in (A.get(t) or {}).get('extracted') or [] if x.endswith('.png')), 'content/' + t.replace('.', '/') + '.png')
        r = export(t, png, out_rel='_pilot/' + t.replace('.', '_') + '.dds')
        print(json.dumps({k: r.get(k) for k in ('object_path', 'status', 'format', 'size', 'mips_cooked', 'mips_written', 'mip_tail_base',
                                                'chain_cut')}), [(v['mip'], v['psnr'], v['corr'], v['packed']) for v in r.get('mip_verification') or []])

def targets():
    A = json.load(open(os.path.join(AT, 'manifests', 'assets.json'), encoding='utf-8'))['assets']
    A = [(a['object_path'], a.get('class'), a.get('extracted')) for a in A if a.get('class') in ('Texture2D', 'TextureFlipBook')]
    out = []
    for op_, cls_, ext_ in A:
        png = next((x for x in ext_ or [] if x.endswith('.png') and os.path.exists(os.path.join(ROOT, x))), None)
        if png: out.append((op_, png))
    del A
    fb = os.path.join(AT, 'manifests', 'audit', 'flipbooks.json')
    if os.path.exists(fb):
        have = {o for o, _ in out}
        for o, v in (json.load(open(fb, encoding='utf-8')).get('textures') or {}).items():
            if v.get('file') and o not in have and os.path.exists(os.path.join(ROOT, v['file'])): out.append((o, v['file']))
    import glob
    for d in sorted(glob.glob(os.path.join(ROOT, 'VerticalSlice', 'Maps', '*'))):
        names = {}
        for fn in ('lightmaps.json', 'lightmaps_destructibles.json'):
            pth = os.path.join(d, fn)
            if not os.path.exists(pth): continue
            j = json.load(open(pth, encoding='utf-8'))
            for r in (j.get('props') or []) + (j.get('components') or []):
                for c in r.get('coeffs') or [r.get('atlas')]:
                    if c: names[c] = r.get('atlas_package')
        inv = objtree.inv()
        for c, pk in sorted(names.items()):
            png = os.path.join(d, 'lightmaps', c + '.png')
            if not (pk and os.path.exists(png)): continue
            # real object path: <level>_LM.<name>, case varies between cooked copies (MP_ESC_BrokenHope_BASE_m_LM / _Base_m_LM)
            root = pk.lower()[:-3] if pk.lower().endswith('_lm') else pk.lower()
            hit = next((o for (o,) in inv.execute("SELECT DISTINCT opath FROM exports WHERE opath LIKE ? AND class = 'LightMapTexture2D'",
                                                     ('%.' + c,)).fetchall() if o.lower().startswith(root)), None)
            out.append((hit or (pk + '.' + c), os.path.relpath(png, ROOT).replace(os.sep, '/')))
        # pages with a PNG in lightmaps/ but no lightmaps*.json reference (Streets BSP ModelComponent pages)
        M = os.path.basename(d); have = {o.split('.')[-1] for o, _ in out}
        for png in sorted(glob.glob(os.path.join(d, 'lightmaps', 'LightMapTexture2D_*.png'))):
            c = os.path.basename(png)[:-4]
            if c in have: continue
            hit = next((o for (o,) in inv.execute("SELECT DISTINCT opath FROM exports WHERE opath LIKE ? AND class = 'LightMapTexture2D'",
                                                     ('%.' + c,)).fetchall() if o.lower().startswith(M.lower())), None)
            if hit: out.append((hit, os.path.relpath(png, ROOT).replace(os.sep, '/')))
    # BSP (ModelComponent) lightmap pages of the generic maps (manifests/next_map/<MAP>_bsp_audit.json); no PNG was ever written for
    # most of them, so the DDS is their only export (png None, mip_verification from the cooked chain only)
    have = {o for o, _ in out}
    for f in sorted(glob.glob(os.path.join(AT, 'manifests', 'next_map', 'MP_*_bsp_audit.json'))):
        M = os.path.basename(f)[:-len('_bsp_audit.json')]
        for o in sorted(set(re.findall(r'"([A-Za-z0-9_]+_LM\.LightMapTexture2D_\d+)"', open(f, encoding='utf-8').read()))):
            if o in have: continue
            png = 'VerticalSlice/Maps/%s/lightmaps/%s.png' % (M, o.split('.')[-1])
            out.append((o, png if os.path.exists(os.path.join(ROOT, png)) else None)); have.add(o)
    # assets.json maps some distinct objects to one PNG (umodel name collisions: EditorTextureSet_*, ThumbnailTexture, same-named
    # TEXSET members). The object whose own path matches the PNG keeps the mirrored .dds; every other one gets a .dds named by its
    # own object path, so no object's DDS is another object's texture.
    by_png = {}
    for o, png in out:
        if png: by_png.setdefault(png, []).append(o)
    BSP_MAPS = sorted({os.path.basename(f)[:-len('_bsp_audit.json')] for f in glob.glob(os.path.join(AT, 'manifests', 'next_map', 'MP_*_bsp_audit.json'))},
                      key=len, reverse=True)
    res = []
    for o, png in out:
        if png is None:
            res.append((o, None, 'VerticalSlice/Maps/%s/lightmaps/%s.dds' % (next(M for M in BSP_MAPS if o.lower().startswith(M.lower())),
                                                                             o.split('.')[-1]), False)); continue
        mirror = os.path.splitext(png)[0] + '.dds'
        if len(by_png[png]) > 1 and not mirror.lower().endswith(('/' + o.replace('.', '/') + '.dds').lower()):
            mirror = 'content/' + o.replace('.', '/') + '.dds'
        res.append((o, png, mirror, len(by_png[png]) > 1))
    return res

def _work(item):
    o, png, out_rel, _shared = item
    try:
        if objtree.package.cache_info().currsize > 1: _evict()   # working-set guard (6 GB job cap)
        r = export(o, png, out_rel=out_rel)
        if _shared and png and out_rel != os.path.splitext(png)[0] + '.dds':
            r['png_is_other_object'] = True      # assets.json maps this object to another object's PNG; the .dds is this object's
        return r
    except MemoryError:
        _evict(); return {'object_path': o, 'png': png, 'status': 'error MemoryError (skipped)'}
    except BaseException as ex:          # native (pyo3) panics are not picklable: report as text, never break the pool
        return {'object_path': o, 'png': png, 'status': 'error %s' % str(ex)[:120]}

def bulk(limit=None, workers=2):
    from concurrent.futures import ProcessPoolExecutor
    from collections import Counter
    items = targets()
    items.sort(key=lambda x: x[0].split('.')[0])   # group by own package: consecutive textures reuse the cached package
    if limit: items = items[:limit]
    idx = os.path.join(AT, 'manifests', 'extracted', 'textures_dds.jsonl')
    os.makedirs(os.path.dirname(idx), exist_ok=True)
    done = {}
    if RESUME and os.path.exists(idx):        # keep finished rows (status ok and the .dds on disk); redo the rest
        for l in open(idx, encoding='utf-8'):
            try: r = json.loads(l)
            except Exception: continue
            if r.get('status') == 'ok' and os.path.exists(os.path.join(OUT_ROOT, r.get('dds', '~'))): done[r['object_path']] = r
        want = {x[0]: x for x in items}
        # redo rows written to another path, and every member of a shared-PNG group (a member may have overwritten the file)
        done = {o: r for o, r in done.items() if o in want and r['dds'] == want[o][2] and not want[o][3]}
        items = [x for x in items if x[0] not in done]
        for r in done.values():                  # rows written before the alpha flag existed: read the top level back from the .dds
            if r['format'] in ('PF_A8R8G8B8', 'PF_DXT5') and 'alpha_all_zero' not in r:
                w, h = r['size']; n = (max(1, w // 4) * max(1, h // 4) * 16) if r['format'] == 'PF_DXT5' else w * h * 4
                with open(os.path.join(OUT_ROOT, r['dds']), 'rb') as f: f.seek(128); lin = f.read(n)
                if r['format'] == 'PF_A8R8G8B8': r['alpha_all_zero'] = not any(lin[3::4])
                else: r['alpha_all_zero'] = alpha_all_zero(lin, w, h, r['format'])
    st = Counter(); fmts = Counter(); mipn = Counter(); t0 = time.time()
    import gc; gc.collect()
    ex = ProcessPoolExecutor(workers) if workers > 0 else None
    it = ex.map(_work, items, chunksize=8) if ex else map(_work, items)
    with open(idx, 'w', encoding='utf-8') as f:
        for r in done.values():
            f.write(json.dumps(r, default=str) + chr(10)); st['ok'] += 1; fmts[r['format']] += 1; mipn[r['mips_written']] += 1
        for k, r in enumerate(it):
            r['png'] = r.get('png') or items[k][1]
            f.write(json.dumps(r, default=str) + chr(10))
            st[r['status'] if r['status'] == 'ok' else r['status'][:40]] += 1
            if r['status'] == 'ok': fmts[r['format']] += 1; mipn[r['mips_written']] += 1
            if k % 500 == 0: print(k, len(items), dict(st), round(time.time() - t0), flush=True)
    if ex: ex.shutdown()
    summ = {'generated_by': 'AssetTools/scripts/wfc/texture_dds.py', 'generated': time.strftime('%Y-%m-%d %H:%M'),
            'out_root': 'AssetTools/out/dds/<path of the PNG relative to ExtractedAssets>.dds',
            'index': 'AssetTools/manifests/extracted/textures_dds.jsonl (local)', 'targets': len(items) + len(done), 'status': dict(st),
            'formats': dict(fmts), 'mips_written_histogram': dict(sorted(mipn.items())), 'seconds': round(time.time() - t0)}
    json.dump(summ, open(os.path.join(AT, 'manifests', 'audit', 'textures_dds_summary.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps(summ))

if __name__ == '__main__':
    if '--pilot' in sys.argv: pilot()
    elif '--bulk' in sys.argv:
        lim = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
        bulk(lim, workers=int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 2)
