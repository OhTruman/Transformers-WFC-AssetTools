"""Export TextureFlipBook sheets that umodel skips -> ExtractedAssets/content/<pkg>/<name>.png (+ index registration)

  python flipbook_export.py [object_path ...]      (default: every TextureFlipBook in the inventory without a PNG)

Format (verified on ENV_NEU_Variation_p.fbook_sinewave_CLR, Rendering report 2026-10-06):
* tagged props: SizeX / SizeY / Format (PF_DXT1 / PF_DXT5 / PF_A8R8G8B8), HorizontalImages / VerticalImages / FrameRate;
* native tail: int32 BE NumMips, then per mip FUntypedBulkData {u32 flags, i32 ElementCount, i32 SizeOnDisk, i32 OffsetInFile}
  + a 4-byte WFC field + [inline payload when not in a separate file] + i32 SizeX + i32 SizeY. Flag 0x20 = unused mip (no data). Flag 0x01 = stored in a separate file (the owning
  package file on disk, absolute offset), 0x10 = LZO-compressed.
* compressed payload = UE3 compressed chunk: tag 0x9E2A83C1, BlockSize, CompressedSize, UncompressedSize, then per-block
  (CompressedSize, UncompressedSize) pairs and the LZO1X blocks (all big-endian on Xbox 360).
* pixel data is Xenos 2D-tiled with 16-bit big-endian words (DXT blocks / A8R8G8B8 texels).
Only mip 0 is exported (the whole sheet; the material's FlipBookSample selects the cell). Never overwrites existing files.
"""
import json, os, struct, sys, time
from collections import OrderedDict as OD
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, extract  # noqa: E402
from vs_common import ROOT  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
CHUNK_TAG = 0x9E2A83C1

def lzo1x_decompress(src, out_len):
    """pure-python LZO1X-1 decompressor (minilzo lzo1x_decompress semantics)"""
    dst = bytearray(); ip = 0; n = len(src)
    def lit(cnt):
        nonlocal ip
        dst.extend(src[ip:ip + cnt]); ip += cnt
    def copy_match(dist, cnt):
        p = len(dst) - dist
        if p < 0: raise ValueError('lzo: lookbehind overrun')
        for k in range(cnt): dst.append(dst[p + k])
    t = src[ip]
    state = 0
    if t > 17:
        ip += 1; lit(t - 17); state = 4 if t - 17 >= 4 else t - 17
    while ip < n:
        t = src[ip]; ip += 1
        if t < 16:
            if state == 0:
                ln = t
                if ln == 0:
                    while src[ip] == 0: ln += 255; ip += 1
                    ln += 15 + src[ip]; ip += 1
                lit(ln + 3); state = 4; continue
            if state == 4:   # M1 after a long literal run
                dist = (1 + 0x0800) + (t >> 2) + (src[ip] << 2); ip += 1
                copy_match(dist, 3)
            else:
                dist = 1 + (t >> 2) + (src[ip] << 2); ip += 1
                copy_match(dist, 2)
        elif t >= 64:
            dist = 1 + ((t >> 2) & 7) + (src[ip] << 3); ip += 1
            copy_match(dist, (t >> 5) - 1 + 2)
        elif t >= 32:
            ln = t & 31
            if ln == 0:
                while src[ip] == 0: ln += 255; ip += 1
                ln += 31 + src[ip]; ip += 1
            dist = 1 + ((src[ip] | (src[ip + 1] << 8)) >> 2); d0 = src[ip]; ip += 2
            copy_match(dist, ln + 2); t = d0
        else:   # 16..31
            ln = t & 7
            if ln == 0:
                while src[ip] == 0: ln += 255; ip += 1
                ln += 7 + src[ip]; ip += 1
            dist = ((t & 8) << 11) + ((src[ip] | (src[ip + 1] << 8)) >> 2); d0 = src[ip]; ip += 2
            if dist == 0: break     # end of stream
            copy_match(dist + 0x4000, ln + 2); t = d0
        s = t & 3                   # trailing literals encoded in the low bits of the last match byte
        if s: lit(s)
        state = s
    if len(dst) != out_len: raise ValueError('lzo: size %d != %d' % (len(dst), out_len))
    return bytes(dst)

def read_chunk(f, off, size_on_disk):
    f.seek(off); hdr = f.read(16)
    tag, bs, csz, usz = struct.unpack('>4I', hdr)
    if tag != CHUNK_TAG: raise ValueError('not a compressed chunk')
    nb = (usz + bs - 1) // bs
    pairs = [struct.unpack('>2I', f.read(8)) for _ in range(nb)]
    out = bytearray()
    for c, u in pairs: out += lzo1x_decompress(f.read(c), u)
    return bytes(out)

def untile_2d(data, w_blocks, h_blocks, bpb):
    """Xenos XGAddress2DTiledOffset over blocks (bpb bytes per block) -> linear"""
    log2 = {4: 2, 8: 3, 16: 4}[bpb]
    aw = (w_blocks + 31) & ~31
    out = bytearray(w_blocks * h_blocks * bpb)
    for y in range(h_blocks):
        for x in range(w_blocks):
            macro = ((x >> 5) + (y >> 5) * (aw >> 5)) << (log2 + 7)
            micro = ((x & 7) + ((y & 6) << 2)) << log2
            off = macro + ((micro & ~15) << 1) + (micro & 15) + ((y & 8) << (3 + log2)) + ((y & 1) << 4)
            addr = (((off & ~511) << 3) + ((off & 448) << 2) + (off & 63) + ((y & 16) << 7) +
                    (((((y & 8) >> 2) + (x >> 3)) & 3) << 6)) >> log2
            s = addr * bpb; d = (y * w_blocks + x) * bpb
            if s + bpb <= len(data): out[d:d + bpb] = data[s:s + bpb]
    return bytes(out)

def swap16(b): a = np.frombuffer(b, '>u2'); return a.astype('<u2').tobytes()

def rgb565(c):
    r = (c >> 11) & 31; g = (c >> 5) & 63; b = c & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.int32)

def dxt_color(blocks, alpha1bit=True):
    c0 = blocks[:, 0].astype(np.uint32) | (blocks[:, 1].astype(np.uint32) << 8)
    c1 = blocks[:, 2].astype(np.uint32) | (blocks[:, 3].astype(np.uint32) << 8)
    idx = blocks[:, 4].astype(np.uint32) | (blocks[:, 5].astype(np.uint32) << 8) | (blocks[:, 6].astype(np.uint32) << 16) | (blocks[:, 7].astype(np.uint32) << 24)
    p0 = rgb565(c0); p1 = rgb565(c1)
    four = (c0 > c1) | (not alpha1bit)
    p2 = np.where(four[:, None], (2 * p0 + p1) // 3, (p0 + p1) // 2)
    p3 = np.where(four[:, None], (p0 + 2 * p1) // 3, 0)
    a3 = np.where(four, 255, 0)
    pal = np.stack([np.c_[p0, np.full(len(p0), 255)], np.c_[p1, np.full(len(p0), 255)], np.c_[p2, np.full(len(p0), 255)], np.c_[p3, a3]], 1)
    sel = np.stack([(idx >> (2 * k)) & 3 for k in range(16)], 1)
    return np.take_along_axis(pal, sel[:, :, None].repeat(4, 2), 1)   # (n, 16, 4)

def decode(data, w, h, fmt):
    if fmt == 'PF_DXT1':
        wb, hb = max(1, w // 4), max(1, h // 4); lin = swap16(untile_2d(data, wb, hb, 8))
        px = dxt_color(np.frombuffer(lin, np.uint8).reshape(-1, 8))
    elif fmt in ('PF_DXT5', 'PF_DXT3'):
        wb, hb = max(1, w // 4), max(1, h // 4); lin = np.frombuffer(swap16(untile_2d(data, wb, hb, 16)), np.uint8).reshape(-1, 16)
        px = dxt_color(lin[:, 8:], alpha1bit=False)
        if fmt == 'PF_DXT5':
            a0 = lin[:, 0].astype(np.int32); a1 = lin[:, 1].astype(np.int32)
            bits = sum(lin[:, 2 + k].astype(np.uint64) << np.uint64(8 * k) for k in range(6))
            sel = np.stack([((bits >> np.uint64(3 * k)) & np.uint64(7)).astype(np.int32) for k in range(16)], 1)
            pal = np.stack([a0, a1] + [np.where(a0 > a1, ((7 - k) * a0 + k * a1) // 7, ((5 - k) * a0 + k * a1) // 5) for k in range(1, 7)], 1)
            pal[:, 6] = np.where(a0 > a1, pal[:, 6], 0); pal[:, 7] = np.where(a0 > a1, pal[:, 7], 255)
            px[:, :, 3] = np.take_along_axis(pal, sel, 1)
    elif fmt == 'PF_A8R8G8B8':
        lin = np.frombuffer(untile_2d(data, w, h, 4), np.uint8).reshape(h, w, 4)   # big-endian ARGB
        return np.stack([lin[..., 1], lin[..., 2], lin[..., 3], lin[..., 0]], -1).astype(np.uint8)
    else:
        raise ValueError('unsupported format ' + fmt)
    img = px.reshape(hb, wb, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(hb * 4, wb * 4, 4)
    return img[:h, :w].astype(np.uint8)

def mip0(pkg, opath):
    p = objtree.package(pkg)
    for i, e in enumerate(p.exports, 1):
        if p.object_path(i) != opath: continue
        props, used = p._tr.read_object(i)
        pr = {x['name']: x.get('value') for x in props}
        nat = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
        nm = struct.unpack_from('>i', nat, 0)[0]; o = 4; w, h = pr['SizeX'], pr['SizeY']
        for mi in range(nm):        # first mip that carries data (0x20 = unused placeholder mip, count 0)
            fl, cnt, sod, off = struct.unpack_from('>Iiii', nat, o); o += 16 + 4   # + a 4-byte field (hash) on WFC mips
            payload_at = o
            if not (fl & 0x01) and sod > 0: o = payload_at + sod
            mw, mh = struct.unpack_from('>ii', nat, o); o += 8
            if cnt > 0 and not (fl & 0x20): break
        else:
            raise ValueError('no mip with data')
        if fl & 0x01:   # separate file = the owning package file on disk
            src = os.path.join(extract.COOKED, opath.split('.')[0] + '.xxx')
            with open(src, 'rb') as f:
                raw = read_chunk(f, off, sod) if fl & 0x10 else (f.seek(off), f.read(cnt))[1]
        else:
            import io
            raw = read_chunk(io.BytesIO(nat), payload_at, sod) if fl & 0x10 else nat[payload_at:payload_at + cnt]
        pr = dict(pr, SizeX=mw, SizeY=mh)
        return pr, raw, {'flags': fl, 'mip_index': mi, 'num_mips': nm, 'element_count': cnt, 'size_on_disk': sod, 'offset': off}
    return None, None, None

def main():
    from PIL import Image
    inv = objtree.inv()
    if len(sys.argv) > 1: targets = sys.argv[1:]
    else:
        targets = [o for (o,) in inv.execute("SELECT DISTINCT opath FROM exports WHERE class = 'TextureFlipBook'").fetchall()]
    res = OD(); aj = os.path.join(AT, 'manifests', 'assets.json'); A = json.load(open(aj, encoding='utf-8')); byop = {a['object_path']: a for a in A['assets']}
    for opath in sorted(targets):
        rel = 'content/' + opath.replace('.', '/') + '.png'; out = os.path.join(ROOT, rel)
        if os.path.exists(out): res[opath] = {'status': 'exists', 'file': rel}; continue
        rows = inv.execute("SELECT package FROM exports WHERE opath = ? AND class = 'TextureFlipBook' ORDER BY serial_size ASC", (opath,)).fetchall()
        err = None
        for (pkg,) in rows:
            try:
                pr, raw, bulk = mip0(pkg, opath)
                if raw is None: continue
                img = decode(raw, pr['SizeX'], pr['SizeY'], pr.get('Format'))
                os.makedirs(os.path.dirname(out), exist_ok=True); Image.fromarray(img, 'RGBA').save(out)
                res[opath] = OD([('status', 'exported'), ('file', rel), ('read_from', pkg), ('format', pr.get('Format')),
                                 ('size', [pr['SizeX'], pr['SizeY']]), ('cells', [pr.get('HorizontalImages'), pr.get('VerticalImages')]),
                                 ('frame_rate', pr.get('FrameRate')), ('bulk', bulk)])
                a = byop.get(opath)
                if a is not None and rel not in (a.get('extracted') or []): a['extracted'] = (a.get('extracted') or []) + [rel]
                err = None; break
            except Exception as ex:
                err = '%s: %s' % (pkg, ex)
        if opath not in res: res[opath] = {'status': 'failed', 'error': err}
        print(opath, res[opath]['status'], res[opath].get('error') or '')
    json.dump(A, open(aj, 'w', encoding='utf-8'))
    json.dump(OD([('generated_by', 'AssetTools/scripts/wfc/flipbook_export.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
                   ('textures', res)]), open(os.path.join(AT, 'manifests', 'audit', 'flipbooks.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    main()
