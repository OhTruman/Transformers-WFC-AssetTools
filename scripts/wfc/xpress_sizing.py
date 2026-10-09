"""Lossless size of package candidates under the Windows Compression API XPRESS_HUFF (the codec Rendering's .xpr loader uses)

  python xpress_sizing.py [--ext .glb,.bin,.gltf,.json,.dds,.fsb,.png] [--roots ExtractedAssets,AssetTools/out/dds]

Per extension: files, raw bytes, compressed bytes (cabinet.dll CreateCompressor(COMPRESS_ALGORITHM_XPRESS_HUFF), buffer mode,
one call per file), ratio, and decompression throughput measured on every file (Decompress into a preallocated buffer, round
trip checked byte for byte). Nothing is written next to the inputs; result -> manifests/audit/xpress_sizing.json.
"""
import ctypes, json, os, sys, time
from collections import OrderedDict as OD
from ctypes import wintypes as W

HERE = os.path.dirname(os.path.abspath(__file__))
AT = os.path.normpath(os.path.join(HERE, '..', '..'))
REB = os.path.dirname(AT)
XPRESS_HUFF = 4
cab = ctypes.WinDLL('cabinet.dll')
H = ctypes.c_void_p
for fn, args in (('CreateCompressor', [W.DWORD, ctypes.c_void_p, ctypes.POINTER(H)]), ('CreateDecompressor', [W.DWORD, ctypes.c_void_p, ctypes.POINTER(H)]),
                 ('Compress', [H, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]),
                 ('Decompress', [H, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)])):
    getattr(cab, fn).argtypes = args; getattr(cab, fn).restype = W.BOOL

def handles():
    c, d = H(), H()
    if not cab.CreateCompressor(XPRESS_HUFF, None, ctypes.byref(c)) or not cab.CreateDecompressor(XPRESS_HUFF, None, ctypes.byref(d)):
        raise OSError(ctypes.get_last_error())
    return c, d

def roundtrip(c, d, data):
    n = ctypes.c_size_t(0)
    cab.Compress(c, data, len(data), None, 0, ctypes.byref(n))          # query size
    out = ctypes.create_string_buffer(max(n.value, 64))
    if not cab.Compress(c, data, len(data), out, len(out), ctypes.byref(n)): raise OSError('Compress failed')
    comp = out.raw[:n.value]
    back = ctypes.create_string_buffer(max(len(data), 1)); m = ctypes.c_size_t(0)
    t = time.perf_counter()
    if not cab.Decompress(d, comp, len(comp), back, len(back), ctypes.byref(m)): raise OSError('Decompress failed')
    dt = time.perf_counter() - t
    if back.raw[:m.value] != data: raise ValueError('round trip mismatch')
    return len(comp), dt

def main():
    exts = (sys.argv[sys.argv.index('--ext') + 1] if '--ext' in sys.argv else '.glb,.bin,.gltf,.json,.dds,.fsb,.png').lower().split(',')
    roots = (sys.argv[sys.argv.index('--roots') + 1] if '--roots' in sys.argv else 'ExtractedAssets,AssetTools/out/dds').split(',')
    c, d = handles()
    acc = OD((e, OD([('files', 0), ('raw', 0), ('xpress', 0), ('decomp_s', 0.0)])) for e in exts)
    big = OD()
    t0 = time.time()
    for r in roots:
        for dp, _, fn in os.walk(os.path.join(REB, r)):
            for nm in fn:
                e = os.path.splitext(nm)[1].lower()
                if e not in acc: continue
                p = os.path.join(dp, nm); data = open(p, 'rb').read()
                if not data: continue
                cs, dt = roundtrip(c, d, data)
                a = acc[e]; a['files'] += 1; a['raw'] += len(data); a['xpress'] += cs; a['decomp_s'] += dt
                k = '%s:%s' % (r, e); b = big.setdefault(k, [0, 0]); b[0] += len(data); b[1] += cs
        print(r, 'done %.0fs' % (time.time() - t0), flush=True)
    G = 1024 ** 3
    rows = OD()
    for e, a in acc.items():
        if not a['files']: continue
        rows[e] = OD([('files', a['files']), ('raw_GB', round(a['raw'] / G, 3)), ('xpress_huff_GB', round(a['xpress'] / G, 3)),
                      ('ratio', round(a['xpress'] / a['raw'], 3)), ('decompress_MB_s', round(a['raw'] / 2 ** 20 / max(a['decomp_s'], 1e-9)))])
    out = OD([('generated_by', 'AssetTools/scripts/wfc/xpress_sizing.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('codec', 'Windows Compression API COMPRESS_ALGORITHM_XPRESS_HUFF (cabinet.dll), buffer mode, one call per file; round trip verified'),
              ('roots', roots), ('by_extension', rows),
              ('by_root_and_extension_GB', OD((k, [round(v[0] / G, 3), round(v[1] / G, 3)]) for k, v in big.items()))])
    json.dump(out, open(os.path.join(AT, 'manifests', 'audit', 'xpress_sizing.json'), 'w', encoding='utf-8'), indent=1)
    for e, r_ in rows.items(): print(e, dict(r_))

if __name__ == '__main__':
    main()
