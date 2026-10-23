"""Post-pass (Rendering / Integration 2026-10-23): no build-machine paths into the campaign render tree. In every JSON of every unit dir of
a chapter, a string that points under out/campaign_render/<CH>/ becomes relative to its unit: the old <SUB>_m dir names are mapped to the
new names (the level name without _m); a path into another unit or _umodel becomes ../<dir>/... Paths into ExtractedAssets / the Game
Dump are left as Rendering's MP data has them. Idempotent; run after any regeneration.

    python relpaths.py <CH> [...]
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUTR = os.path.join(AT, 'out', 'campaign_render')

def outname(d): return d[:-2] if d.endswith('_m') else d

def chapter(ch):
    R = os.path.join(OUTR, ch)
    root = os.path.normpath(R).replace(os.sep, '/').lower() + '/'
    units = [d for d in sorted(os.listdir(R)) if os.path.isdir(os.path.join(R, d)) and not d.startswith('_')]
    total = {'files_rewritten': 0, 'strings_rewritten': 0, 'left_absolute_into_render_tree': 0}
    for u in units:
        od = os.path.join(R, u); cnt = [0]
        def fix(v):
            if isinstance(v, str):
                t = v.replace(chr(92), '/')
                if t.lower().startswith(root):
                    rest = t[len(root):].split('/', 1)
                    d = outname(rest[0]); tail = rest[1] if len(rest) > 1 else ''
                    cnt[0] += 1
                    return tail if d == u else '../%s/%s' % (d, tail)
                return v
            if isinstance(v, list): return [fix(x) for x in v]
            if isinstance(v, dict): return {k: fix(x) for k, x in v.items()}
            return v
        for f in sorted(os.listdir(od)):
            fp = os.path.join(od, f)
            if not f.endswith('.json') or not os.path.isfile(fp): continue
            raw = open(fp, encoding='utf-8').read()
            if 'campaign_render' not in raw: continue
            before = cnt[0]; d = json.loads(raw); d2 = fix(d)
            if cnt[0] > before:
                json.dump(d2, open(fp + '.tmp', 'w', encoding='utf-8'), indent=0 if f == 'lighting.json' else 1)
                os.replace(fp + '.tmp', fp); total['files_rewritten'] += 1
        total['strings_rewritten'] += cnt[0]
        for f in os.listdir(od):
            fp = os.path.join(od, f)
            if f.endswith('.json') and os.path.isfile(fp):
                t = open(fp, encoding='utf-8').read().replace('\\\\', '/').lower()
                total['left_absolute_into_render_tree'] += t.count(root)
    print(ch, total)
    return total

if __name__ == '__main__':
    for c in sys.argv[1:]: chapter(c)
