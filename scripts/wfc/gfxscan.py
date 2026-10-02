"""Minimal Scaleform GFX / SWF tag scanner (authored UI evidence, read-only).

Reads an extracted .gfx (GFX/CFX = Scaleform-signed SWF; CFX is zlib-compressed) and reports, per
character / sprite:
  * ExportAssets / SymbolClass names (linkage ids)        tag 56 / 76
  * DefineSprite timelines: frame count, FrameLabels      tag 39 / 43
  * PlaceObject2/3 instance names + character ids          tag 26 / 70 (+ matrix translation in twips)
  * DoAction / DoInitAction constant-pool strings          tag 12 / 59 (AS2 ActionConstantPool 0x88)
  * DefineBitsLossless / external image references (Scaleform tag 1000/1001 DefineExternalImage)
CLI: python gfxscan.py <file.gfx> [--grep REGEX] [--json out.json]
"""
import argparse, json, re, struct, zlib

def _rect_len(b, i):
    nbits = b[i] >> 3
    return (5 + 4 * nbits + 7) // 8

def _tags(b, i, end):
    while i + 2 <= end:
        h = struct.unpack_from('<H', b, i)[0]; i += 2
        code, ln = h >> 6, h & 0x3F
        if ln == 0x3F: ln = struct.unpack_from('<I', b, i)[0]; i += 4
        yield code, b[i:i + ln], i
        i += ln
        if code == 0: break

def _cstr(b, i):
    j = b.index(0, i); return b[i:j].decode('latin-1'), j + 1

def _matrix_translate(d, i):
    """SWF MATRIX bit record -> (tx, ty) twips, new offset."""
    bitpos = i * 8
    def bits(n):
        nonlocal bitpos
        v = 0
        for _ in range(n):
            v = (v << 1) | ((d[bitpos >> 3] >> (7 - (bitpos & 7))) & 1); bitpos += 1
        return v
    def sbits(n):
        v = bits(n); return v - (1 << n) if n and v & (1 << (n - 1)) else v
    if bits(1): n = bits(5); sbits(n); sbits(n)
    if bits(1): n = bits(5); sbits(n); sbits(n)
    n = bits(5); tx, ty = sbits(n), sbits(n)
    return (tx, ty), (bitpos + 7) // 8

def _consts(d):
    out, i = [], 0
    while i < len(d):
        op = d[i]; i += 1
        if op == 0: break
        if op >= 0x80:
            ln = struct.unpack_from('<H', d, i)[0]; i += 2
            if op == 0x88:
                n = struct.unpack_from('<H', d, i)[0]; j = i + 2
                for _ in range(n):
                    s, j = _cstr(d, j); out.append(s)
            i += ln
    return out

def _place(code, d):
    flags = d[0]; i = 1
    if code == 70: flags2 = d[1]; i = 2
    else: flags2 = 0
    depth = struct.unpack_from('<H', d, i)[0]; i += 2
    rec = {'depth': depth}
    if code == 70 and flags2 & 0x08: _, i = _cstr(d, i)      # class name
    if flags & 0x02: rec['char'] = struct.unpack_from('<H', d, i)[0]; i += 2
    if flags & 0x04:
        rec['translate_twips'], i = _matrix_translate(d, i)
    if flags & 0x08:   # color transform: skip using bit lengths
        bitpos = i * 8
        def bits(n):
            nonlocal bitpos
            v = 0
            for _ in range(n):
                v = (v << 1) | ((d[bitpos >> 3] >> (7 - (bitpos & 7))) & 1); bitpos += 1
            return v
        add, mul, n = bits(1), bits(1), bits(4)
        if mul: [bits(n) for _ in range(4)]
        if add: [bits(n) for _ in range(4)]
        i = (bitpos + 7) // 8
    if flags & 0x10: i += 2
    if flags & 0x20:
        rec['name'], i = _cstr(d, i)
    return rec

def scan(path):
    b = open(path, 'rb').read()
    sig = b[:3]
    if sig in (b'CFX', b'CWS'): b = b[:8] + zlib.decompress(b[8:])
    i = 8 + _rect_len(b, 8) + 4
    out = {'file': path, 'signature': sig.decode(), 'version': b[3], 'exports': {}, 'sprites': {}, 'root': {'labels': [], 'places': []},
           'action_strings': [], 'external_images': []}
    def walk(start, end, tgt, sprite_id=None):
        frame = 0
        for code, d, off in _tags(b, start, end):
            if code == 1: frame += 1
            elif code == 43: tgt['labels'].append({'frame': frame, 'label': _cstr(d, 0)[0]})
            elif code in (26, 70):
                try:
                    r = _place(code, d); r['frame'] = frame; tgt['places'].append(r)
                except Exception: pass
            elif code in (12, 59):
                body = d[2:] if code == 59 else d
                try: out['action_strings'].append({'sprite': sprite_id if code == 12 else struct.unpack_from('<H', d, 0)[0],
                                                   'init': code == 59, 'strings': _consts(body)})
                except Exception: pass
            elif code == 56:
                n = struct.unpack_from('<H', d, 0)[0]; j = 2
                for _ in range(n):
                    cid = struct.unpack_from('<H', d, j)[0]; nm, j = _cstr(d, j + 2); out['exports'][cid] = nm
            elif code == 39:
                sid, fc = struct.unpack_from('<HH', d, 0)
                s = {'frames': fc, 'labels': [], 'places': []}
                out['sprites'][sid] = s
                walk(off + 4, off + len(d), s, sid)
            elif code == 1009 or code == 1000:   # Scaleform DefineExternalImage(2)
                try:
                    cid = struct.unpack_from('<H', d, 0)[0]
                    names = re.findall(rb'[\x20-\x7e]{3,}', d[2:])
                    out['external_images'].append({'char': cid, 'tag': code, 'strings': [x.decode() for x in names]})
                except Exception: pass
        tgt.setdefault('frames_seen', frame)
    walk(i, len(b), out['root'])
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('gfx'); ap.add_argument('--grep'); ap.add_argument('--json')
    a = ap.parse_args(); s = scan(a.gfx)
    if a.json: json.dump(s, open(a.json, 'w'), indent=1)
    if a.grep:
        rx = re.compile(a.grep, re.I)
        for cid, nm in s['exports'].items():
            if rx.search(nm): print('export', cid, nm, s['sprites'].get(cid, {}).get('labels'))
        for sid, sp in s['sprites'].items():
            for pl in sp['places']:
                if rx.search(pl.get('name') or ''): print('place in sprite', sid, s['exports'].get(sid), pl)
            for lb in sp['labels']:
                if rx.search(lb['label']): print('label in sprite', sid, s['exports'].get(sid), lb)
        for pl in s['root']['places']:
            if rx.search(pl.get('name') or ''): print('root place', pl)
        for a2 in s['action_strings']:
            hits = [x for x in a2['strings'] if rx.search(x)]
            if hits: print('as', a2['sprite'], s['exports'].get(a2['sprite']), hits[:40])
        for e in s['external_images']:
            if any(rx.search(x) for x in e['strings']): print('img', e)
    else:
        print(json.dumps({'exports': len(s['exports']), 'sprites': len(s['sprites']), 'actions': len(s['action_strings'])}))
