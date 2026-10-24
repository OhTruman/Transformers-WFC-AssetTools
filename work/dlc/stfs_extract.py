"""Xbox 360 STFS (LIVE / PIRS / CON) package extractor for the WFC DLC packs (Integration / user 2026-10-23, docs: Rebuild/docs/DLC_PLAN.md).
Source is READ-ONLY (F:/Transformers Rebuild/4156084C/00000002/<package>); output goes to AssetTools/work/dlc/<name>/files/... + manifest.json.

Format (Free60 STFS): metadata header (display name at 0x411, UTF-16BE; header size at 0x340), volume descriptor at 0x379
(block separation 0x37B, file-table block count u16 LE 0x37C, file-table first block u24 LE 0x37E, allocated blocks u32 BE 0x395).
Data block b -> backing block = b + hash tables before it (one per 0xAA data blocks, one per 0x70E4, one per 0x4AF768), each table
1 or 2 blocks (the table-size shift); file offset = backing << 12 + ((header size + 0xFFF) & 0xF000).
File-table entry (0x40): name[0x28], flags 0x28 (bit 7 directory, bit 6 consecutive blocks, low 6 bits name length), block count
u24 LE 0x29, first block u24 LE 0x2F, parent dir index s16 BE 0x32, size u32 BE 0x34.
Self-validation instead of trusting one reading of the spec:
  - the table-size shift is the one (0 or 1) under which the file table parses to plausible entries;
  - a non-consecutive file follows the level-0 hash-table chain, and every step is accepted only if the hash entry's SHA-1 equals
    the SHA-1 of the data block it describes (both table copies are tried);
  - every extracted file is checked for the UE3 package magic (0x9E2A83C1, either byte order) where the extension is a package.
    python stfs_extract.py <package file> <out name> [--list]
"""
import hashlib, json, os, struct, sys
from collections import Counter, OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__))
UE3 = (b'\x9e\x2a\x83\xc1', b'\xc1\x83\x2a\x9e')
PKG_EXT = ('.xxx', '.upk', '.umap', '.u')

class Stfs:
    def __init__(self, path):
        self.f = open(path, 'rb'); self.size = os.path.getsize(path)
        h = self.read(0, 0x971 + 0x100)
        self.magic = h[:4]
        if self.magic not in (b'LIVE', b'PIRS', b'CON '): raise SystemExit('not an STFS package: %r' % self.magic)
        self.header_size = struct.unpack_from('>I', h, 0x340)[0]
        self.display_name = h[0x411:0x411 + 0x80].decode('utf-16-be', 'replace').split('\x00')[0]
        self.title_id = struct.unpack_from('>I', h, 0x360)[0]
        self.content_type = struct.unpack_from('>I', h, 0x344)[0]
        vd = h[0x379:0x379 + 0x24]
        self.block_sep = vd[2]
        self.ft_blocks = struct.unpack_from('<H', vd, 3)[0]
        self.ft_first = vd[5] | (vd[6] << 8) | (vd[7] << 16)
        self.alloc_blocks = struct.unpack_from('>I', vd, 0x1C)[0]
        self.first = (self.header_size + 0xFFF) & 0xF000
        self.shift = None

    def read(self, off, n):
        self.f.seek(off); return self.f.read(n)

    def backing(self, b, shift):
        base = ((b + 0xAA) // 0xAA) << shift; ret = base + b
        if b > 0xAA:
            ret += ((b + 0x70E4) // 0x70E4) << shift
            if b > 0x70E4: ret += ((b + 0x4AF768) // 0x4AF768) << shift
        return ret

    def block_off(self, b, shift=None):
        return (self.backing(b, self.shift if shift is None else shift) << 12) + self.first

    def entries(self, shift):
        out = []
        for k in range(self.ft_blocks):
            blk = self.read(self.block_off(self.ft_first + k, shift), 0x1000)
            for i in range(0, 0x1000, 0x40):
                e = blk[i:i + 0x40]; fl = e[0x28]; nl = fl & 0x3F
                if nl == 0: continue
                name = e[:nl]
                out.append(OD([('name', name.decode('ascii', 'replace')), ('raw_ok', all(32 <= c < 127 for c in name)),
                               ('dir', bool(fl & 0x80)), ('consecutive', bool(fl & 0x40)),
                               ('blocks', e[0x29] | (e[0x2A] << 8) | (e[0x2B] << 16)), ('first', e[0x2F] | (e[0x30] << 8) | (e[0x31] << 16)),
                               ('parent', struct.unpack_from('>h', e, 0x32)[0]), ('size', struct.unpack_from('>I', e, 0x34)[0])]))
        return out

    def choose_shift(self):
        best = None
        for s in (0, 1):
            try: es = self.entries(s)
            except Exception: continue
            good = sum(1 for e in es if e['raw_ok'] and (e['dir'] or (e['size'] <= self.size and e['blocks'] <= self.alloc_blocks + 1)))
            if es and (best is None or good > best[1]): best = (s, good, len(es))
        if not best or best[1] == 0: raise SystemExit('file table unreadable under both table-size shifts')
        self.shift = best[0]
        return best

    def next_block(self, b, data_sha):
        """the level-0 hash entry for data block b (0x18 bytes: SHA-1, status, next block u24 BE); accepted only when its SHA-1 matches"""
        rec = b % 0xAA; grp = b - rec
        for copy in (0, 1):
            tbl = (self.backing(grp, self.shift) - (1 << self.shift) + copy) if self.shift else (self.backing(grp, 0) - 1)
            for cand in {tbl, tbl - 1, tbl + 1}:
                e = self.read((cand << 12) + self.first + rec * 0x18, 0x18)
                if e[:20] == data_sha: return (e[21] << 16) | (e[22] << 8) | e[23]
        return None

    def file_bytes(self, e):
        out = bytearray(); left = e['size']; b = e['first']; n = 0
        while left > 0:
            data = self.read(self.block_off(b), 0x1000)
            out += data[:min(left, 0x1000)]; left -= 0x1000; n += 1
            if left <= 0: break
            if e['consecutive']: b += 1
            else:
                nb = self.next_block(b, hashlib.sha1(data).digest())
                if nb is None: raise ValueError('hash chain unverified at block %d of %s' % (b, e['name']))
                b = nb
        return bytes(out)

def main(pkg, name, list_only=False):
    s = Stfs(pkg); shift, good, total = s.choose_shift()
    es = s.entries(shift)
    paths = {}
    def path_of(i):
        if i in paths: return paths[i]
        e = es[i]; p = e['name'] if e['parent'] in (-1, 0xFFFF) or e['parent'] < 0 or e['parent'] >= len(es) else path_of(e['parent']) + '/' + e['name']
        paths[i] = p; return p
    rows = []; kinds = Counter(); bad = []
    O = os.path.join(HERE, name)
    for i, e in enumerate(es):
        p = path_of(i)
        if e['dir']: continue
        ext = os.path.splitext(p)[1].lower(); kinds[ext or '(none)'] += 1
        row = OD([('path', p), ('size', e['size']), ('blocks', e['blocks']), ('consecutive', e['consecutive'])])
        if not list_only:
            try:
                d = s.file_bytes(e)
                if len(d) != e['size']: raise ValueError('size mismatch %d != %d' % (len(d), e['size']))
                if ext in PKG_EXT and d[:4] not in UE3: raise ValueError('no UE3 package magic: %r' % d[:4])
                dst = os.path.join(O, 'files', *p.split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, 'wb').write(d); row['sha1'] = hashlib.sha1(d).hexdigest()
            except Exception as x:
                row['error'] = repr(x)[:200]; bad.append(p)
        rows.append(row)
    man = OD([('source', pkg.replace(os.sep, '/')), ('source_read_only', True), ('magic', s.magic.decode()), ('display_name', s.display_name),
              ('title_id', '%08X' % s.title_id), ('content_type', '%08X' % s.content_type), ('header_size', s.header_size),
              ('table_size_shift', shift), ('file_table', OD([('blocks', s.ft_blocks), ('first', s.ft_first), ('entries', total), ('plausible', good)])),
              ('files', len(rows)), ('bytes', sum(r['size'] for r in rows)), ('by_extension', OD(kinds.most_common())), ('errors', bad), ('entries', rows)])
    os.makedirs(O, exist_ok=True)
    json.dump(man, open(os.path.join(O, 'manifest.json'), 'w', encoding='utf-8'), indent=1)
    print(s.display_name, '| shift', shift, '| files', len(rows), '| bytes', man['bytes'], '| errors', len(bad), '|', dict(kinds.most_common(8)))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], '--list' in sys.argv[3:])
