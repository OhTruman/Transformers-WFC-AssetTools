"""Decode WFC Coalesced.{ini,int,FRA} -> readable .ini text + JSON.

Format (big-endian): int32 file_count, then per file two FStrings:
(relative ini path, whole ini text).  String bytes are XOR-obfuscated with a
fixed 61-byte key (recovered by index-of-coincidence/autocorrelation: peaks
at multiples of 61, then per-column frequency analysis).  The key phase
differs per string, so it is recovered per string by maximising printable
ratio; every decoded string is verified (>= 99% printable) or flagged.

Output: ExtractedAssets/config/<bundle>/<ini path>  and  <bundle>.json
"""
import json, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DUMP = os.path.join(ROOT, 'Game Dump', 'TransGame')
OUT = os.path.join(ROOT, 'ExtractedAssets', 'config')
KEY = b'cvnas;dwepo2345098]qw]{}p2039458pseasdfzcvvp;aseiurwefsdcfszd'
BUNDLES = [os.path.join(DUMP, 'Config', 'Xenon', 'Cooked', 'Coalesced.ini'),
           os.path.join(DUMP, 'Localization', 'Cooked', 'Xenon', 'Coalesced.int'),
           os.path.join(DUMP, 'Localization', 'Cooked', 'Xenon', 'Coalesced.FRA')]

def printable(b):
    return sum(1 for x in b if 32 <= x < 127 or x in (9, 10, 13) or x >= 0xA0) / max(1, len(b))

def xor(b, off):
    K = len(KEY)
    return bytes(x ^ KEY[(i + off) % K] for i, x in enumerate(b))

COMMON = set(b' etaoinsrlcdumhpgbfywETAOINSRLCDUMHPGBFYW0123456789=[]()._,\\/\r\n"')

def likelihood(b):
    return sum(2 if x in COMMON else (1 if 32 <= x < 127 else -3) for x in b)

def decode_string(raw, wide):
    # terminator(s) are stored un-obfuscated
    term = 2 if wide else 1
    if raw[-term:] == b'\0' * term:
        raw = raw[:-term]
    sample = raw[:4000]
    if wide:   # score only the low bytes of UTF-16BE code units
        best = max(range(len(KEY)), key=lambda o: likelihood(xor(sample, o)[1::2]))
    else:
        best = max(range(len(KEY)), key=lambda o: likelihood(xor(sample, o)))
    plain = xor(raw, best)
    if wide:
        text = plain.decode('utf-16-be', 'replace')
        ok = printable(text.encode('latin-1', 'replace')) >= 0.99
    else:
        text = plain.decode('latin-1')
        ok = printable(plain) >= 0.99
    return text.rstrip('\0'), best, ok

def parse_ini(text):
    sections, cur = {}, None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(';'): continue
        m = re.match(r'^\[(.+)\]$', s)
        if m:
            cur = sections.setdefault(m.group(1), {}); continue
        if cur is None or '=' not in s: continue
        k, v = s.split('=', 1)
        cur.setdefault(k, []).append(v)
    return sections

def main():
    report = []
    for path in BUNDLES:
        d = open(path, 'rb').read()
        bundle = os.path.basename(path).replace('.', '_')
        header = struct.unpack_from('>i', d, 0)[0]; p = 4     # not a pair count; read to EOF
        files, bad = {}, []
        n = 0
        while p < len(d):
            n += 1
            vals = []
            for _ in range(2):
                L = struct.unpack_from('>i', d, p)[0]; p += 4
                wide = L < 0; size = -2 * L if wide else L
                text, off, ok = decode_string(d[p:p + size], wide); p += size
                vals.append((text, ok))
            (name, ok1), (body, ok2) = vals
            if not (ok1 and ok2): bad.append(name)
            rel = name.replace('..\\', '').replace('\\', '/').lstrip('./')
            dst = os.path.join(OUT, bundle, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'w', encoding='utf-8', newline='').write(body)
            files[rel] = parse_ini(body)
        json.dump(files, open(os.path.join(OUT, bundle + '.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        report.append({'bundle': os.path.relpath(path, ROOT), 'files': n, 'consumed': p == len(d), 'header_int': header,
                       'unverified': bad, 'names': sorted(files)})
        print('%s: %d files, fully consumed=%s, unverified=%d' % (bundle, n, p == len(d), len(bad)))
    json.dump(report, open(os.path.join(ROOT, 'AssetTools', 'manifests', 'config_report.json'), 'w'), indent=1)

if __name__ == '__main__':
    main()
