"""Minimal UE3 package header reader for Transformers: War for Cybertron (Xbox 360).

Format facts established by inspection (see AssetTools/docs/FORMAT_NOTES.md):
  - big-endian, tag 0x9E2A83C1, FileVersion 511, LicenseeVersion 144
  - extra int32 after version (constant 0x4BDCFCC0 in every package seen)
  - EngineVersion 3428, CookerVersion 113
  - PKG_StoreCompressed (0x02000000) packages carry a chunk table; chunks are
    UE3 "compressed chunk" blocks (tag 0x9E2A83C1 + blocksize + sizes + blocks).
"""
import struct

TAG = 0x9E2A83C1
PKG_STORE_COMPRESSED = 0x02000000
PKG_CONTAINS_MAP = 0x00020000
PKG_COOKED = 0x00000008

class Reader:
    def __init__(self, data, pos=0, endian='>'):
        self.d, self.p, self.e = data, pos, endian
    def u32(self):
        v = struct.unpack_from(self.e + 'I', self.d, self.p)[0]; self.p += 4; return v
    def i32(self):
        v = struct.unpack_from(self.e + 'i', self.d, self.p)[0]; self.p += 4; return v
    def u64(self):
        v = struct.unpack_from(self.e + 'Q', self.d, self.p)[0]; self.p += 8; return v
    def raw(self, n):
        v = self.d[self.p:self.p + n]; self.p += n; return v
    def fstring(self):
        n = self.i32()
        if n == 0:
            return ''
        if n < 0:  # UTF-16
            s = self.raw(-n * 2).decode('utf-16-be' if self.e == '>' else 'utf-16-le', 'replace')
        else:
            s = self.raw(n).decode('latin-1')
        return s.rstrip('\0')

def read_summary(data):
    r = Reader(data)
    tag = r.u32()
    if tag != TAG:
        raise ValueError('not a UE3 package (tag %08X)' % tag)
    ver = r.u32()
    s = {'file_version': ver & 0xFFFF, 'licensee_version': ver >> 16}
    s['game_extra'] = '%08X' % r.u32()           # WFC-specific field
    s['header_size'] = r.i32()
    s['folder_name'] = r.fstring()
    s['package_flags'] = r.u32()
    s['name_count'] = r.i32(); s['name_offset'] = r.i32()
    s['export_count'] = r.i32(); s['export_offset'] = r.i32()
    s['import_count'] = r.i32(); s['import_offset'] = r.i32()
    s['depends_offset'] = r.i32()
    s['guid'] = r.raw(16).hex()
    gens = r.i32()
    s['generations'] = [(r.i32(), r.i32(), r.i32()) for _ in range(max(0, min(gens, 64)))]
    s['engine_version'] = r.i32()
    s['cooker_version'] = r.i32()
    s['compression_flags'] = r.u32()
    n = r.i32()
    chunks = []
    for _ in range(max(0, min(n, 100000))):
        chunks.append({'uncomp_offset': r.i32(), 'uncomp_size': r.i32(),
                       'comp_offset': r.i32(), 'comp_size': r.i32()})
    s['chunks'] = chunks
    s['summary_end'] = r.p
    return s


# --------------------------------------------------------------------------
# Decompression (LZO1X blocks inside UE3 compressed chunks)

COMPRESS_ZLIB, COMPRESS_LZO, COMPRESS_LZX = 1, 2, 4

def _decode_block(buf, usize, flags):
    if flags & COMPRESS_LZO:
        from lzallright import LZOCompressor
        return LZOCompressor.decompress(buf, output_size_hint=usize)
    if flags & COMPRESS_ZLIB:
        import zlib
        return zlib.decompress(buf)
    raise NotImplementedError('compression flags %d' % flags)

def decompress(data, summary=None):
    """Return a fully uncompressed package image (bytes)."""
    s = summary or read_summary(data)
    if not s['chunks']:
        return data
    total = max(c['uncomp_offset'] + c['uncomp_size'] for c in s['chunks'])
    out = bytearray(total)
    first = min(c['uncomp_offset'] for c in s['chunks'])
    out[:first] = data[:first]
    for c in s['chunks']:
        o = c['comp_offset']
        tag, bs, cs, us = struct.unpack_from('>IIII', data, o)
        if tag != TAG:
            raise ValueError('bad chunk tag at %X' % o)
        n = (us + bs - 1) // bs
        blocks = [struct.unpack_from('>II', data, o + 16 + 8 * i) for i in range(n)]
        p = o + 16 + 8 * n
        w = c['uncomp_offset']
        for bcs, bus in blocks:
            dec = _decode_block(data[p:p + bcs], bus, s['compression_flags'])
            # each block sits at its DECLARED uncompressed offset (RE 2026-10-23, DLC MP_ESC_Tranquillity_AUDIO_m: one block of the
            # shipped cook decodes 26,428 bytes short; advancing by len(dec) shifted the rest of the chunk). A block whose decoded
            # length differs from its declared size is recorded in SHORT_BLOCKS; packages without one decompress exactly as before.
            if len(dec) != bus: SHORT_BLOCKS.append({'chunk_uncomp_offset': c['uncomp_offset'], 'block_uncomp_offset': w, 'declared': bus, 'decoded': len(dec)})
            out[w:w + min(len(dec), bus)] = dec[:bus]
            w += bus; p += bcs
    return bytes(out)

SHORT_BLOCKS = []   # blocks whose decoded size != declared size (see decompress)


# --------------------------------------------------------------------------
# Tables

class Package:
    def __init__(self, path):
        import os as _os
        # opt-in DLC second source (2026-10-23): with WFC_COOKED_DIR set (the DLC cooked dir), a package that is not there is read
        # from the base Game Dump cooked dir (DLC maps reference base-owned objects); unset or file present: unchanged
        if not _os.path.exists(path) and _os.environ.get('WFC_COOKED_DIR'):
            alt = _os.path.join(r'F:/Transformers Rebuild/Game Dump/TransGame/CookedXenon', _os.path.basename(path))
            if _os.path.exists(alt): path = alt
        raw = open(path, 'rb').read()
        self.path = path
        import os as _os
        self.name = _os.path.splitext(_os.path.basename(path))[0]
        self.summary = read_summary(raw)
        self.compressed = bool(self.summary['chunks'])
        self.data = decompress(raw, self.summary)
        self._read_names(); self._read_imports(); self._read_exports()

    def _read_names(self):
        s = self.summary; r = Reader(self.data, s['name_offset'])
        self.names = []
        for _ in range(s['name_count']):
            self.names.append(r.fstring()); r.u64()

    def fname(self, r):
        i, num = r.i32(), r.i32()
        n = self.names[i] if 0 <= i < len(self.names) else '?%d' % i
        return n if num == 0 else '%s_%d' % (n, num - 1)

    def _read_imports(self):
        s = self.summary; r = Reader(self.data, s['import_offset'])
        self.imports = []
        for _ in range(s['import_count']):
            cp = self.fname(r); cn = self.fname(r); outer = r.i32(); on = self.fname(r)
            self.imports.append({'class_package': cp, 'class': cn, 'outer': outer, 'name': on})

    def _read_exports(self):
        s = self.summary; r = Reader(self.data, s['export_offset'])
        self.exports = []
        for _ in range(s['export_count']):
            e = {'class_index': r.i32(), 'super_index': r.i32(), 'outer': r.i32(),
                 'name': self.fname(r), 'archetype': r.i32(), 'object_flags': r.u64(),
                 'serial_size': r.i32(), 'serial_offset': r.i32()}
            # WFC (licensee >= 116): no ComponentMap; ExportFlags then a byte
            # flag; the NetObjectCount/Guid/PackageFlags tail is present only
            # when that flag is non-zero (matches UEViewer UnPackage3.cpp).
            e['export_flags'] = r.u32()
            if r.raw(1)[0]:
                nnet = r.i32(); r.p += nnet * 4
                r.p += 16 + 4
            self.exports.append(e)

    def obj_name(self, index):
        """Resolve a package index (>0 export, <0 import) to name."""
        if index > 0: return self.exports[index - 1]['name']
        if index < 0: return self.imports[-index - 1]['name']
        return None

    def class_name(self, e):
        ci = e['class_index']
        return 'Class' if ci == 0 else self.obj_name(ci)

    def full_path(self, index, _depth=0):
        if index == 0 or _depth > 64: return ''
        entry = self.exports[index - 1] if index > 0 else self.imports[-index - 1]
        parent = self.full_path(entry['outer'], _depth + 1)
        return parent + '.' + entry['name'] if parent else entry['name']

    def object_path(self, index):
        """Path including the ORIGINAL source package.

        Cooked copies live under a Package-class export flagged
        EF_ForcedExport (export_flags & 1) named after their source package.
        Anything else (incl. Package-class *groups*) is native to this file,
        so the file's own package name is prefixed."""
        path = self.full_path(index)
        if index > 0:
            root, depth = index, 0
            while self.exports[root - 1]['outer'] > 0 and depth < 64:
                root = self.exports[root - 1]['outer']; depth += 1
            r = self.exports[root - 1]
            if not (self.class_name(r) == 'Package' and r['export_flags'] & 1):
                return self.name + '.' + path
        return path

    def import_packages(self):
        """Top-level packages this package imports from (dependencies)."""
        return sorted({i['name'] for i in self.imports if i['outer'] == 0})
