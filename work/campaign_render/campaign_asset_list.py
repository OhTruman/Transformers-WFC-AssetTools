"""Campaign assets OUTSIDE out/campaign_render (Systems / Integration 2026-10-23, for slim_files.tsv): every file the campaign data
references that does not live in a chapter's render tree, with size, existence and who references it. Read only. Sources:
  - out/campaign_characters/** (bodies, AI weapons, destructibles; every file) and out/campaign_anims/** (converted anim sets; every file)
  - file paths named inside: those character / weapon / destructible JSONs, each chapter's matinee_skeletal.json / destructibles.json,
    manifests/next_map/<CH>_dialog.json (dialog waves) and <CH>_matinee.json (sound / FX refs)
  - a referenced .gltf brings its buffers and images (its own uri entries)
Path strings resolve as: 'content/...' -> ExtractedAssets/content/...; 'AssetTools/...' / 'out/...' / 'work/...' -> AssetTools/....
Writes manifests/campaign/campaign_assets_outside_render.tsv (path relative to F:/Transformers Rebuild, bytes, exists, kind, chapters,
first_referenced_by) + .json summary.
"""
import json, os, re, sys
from collections import Counter, OrderedDict as OD, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(AT)
EA = os.path.join(TR, 'ExtractedAssets')
CHS = ['D5_OME', 'A1_IAC', 'A2_KON', 'A3_COR', 'A4_ORB', 'A5_TRY', 'D1_ORB', 'D2_COR', 'D3A_IAC', 'D3B_IAC']
PATH = re.compile(r'^(?:content|AssetTools|out|work|ExtractedAssets)/[^\s"]+\.[A-Za-z0-9]{2,5}$')

def resolve(s):
    if s.startswith('ExtractedAssets/'): return os.path.join(TR, *s.split('/'))
    if s.startswith('content/'): return os.path.join(EA, *s.split('/'))
    if s.startswith('AssetTools/'): return os.path.join(TR, *s.split('/'))
    return os.path.join(AT, *s.split('/'))

def strings(v):
    if isinstance(v, str): yield v
    elif isinstance(v, dict):
        for k, x in v.items(): yield from strings(x)
    elif isinstance(v, list):
        for x in v: yield from strings(x)

def rel(p): return os.path.relpath(p, TR).replace(os.sep, '/')

def main():
    files = OD(); refs = defaultdict(set); first = {}
    def add(p, by, ch=None):
        p = os.path.normpath(p)
        if p not in files: files[p] = None; first[p] = by
        if ch: refs[p].add(ch)
    def scan_json(path, ch=None):
        try: d = json.load(open(path, encoding='utf-8'))
        except Exception: return
        for s in strings(d):
            if PATH.match(s):
                p = resolve(s)
                if os.sep + 'campaign_render' + os.sep in p: continue
                add(p, rel(path), ch)
    # 1. our own campaign trees, every file
    for root in (os.path.join(AT, 'out', 'campaign_characters'), os.path.join(AT, 'out', 'campaign_anims')):
        for r, _, fs in os.walk(root):
            for f in fs:
                p = os.path.join(r, f); add(p, 'tree:' + rel(root))
                if f.endswith('.json') and root.endswith('campaign_characters'): scan_json(p)
    # 2. chapter references
    chars = json.load(open(os.path.join(AT, 'work', 'campaign_characters', 'roster.json'), encoding='utf-8'))['templates']
    for ch in CHS:
        for f in (os.path.join(AT, 'out', 'campaign_render', ch, 'matinee_skeletal.json'), os.path.join(AT, 'out', 'campaign_render', ch, 'destructibles.json'),
                  os.path.join(AT, 'manifests', 'next_map', ch + '_dialog.json'), os.path.join(AT, 'manifests', 'next_map', ch + '_matinee.json')):
            if os.path.exists(f): scan_json(f, ch)
        for t in chars:
            if ch in t.get('chapters', []):
                d = os.path.join(AT, 'out', 'campaign_characters', t['id'])
                for r, _, fs in os.walk(d):
                    for x in fs: add(os.path.join(r, x), 'character:' + t['id'], ch)
    # 3. glTF dependencies
    for p in list(files):
        if p.endswith('.gltf') and os.path.exists(p):
            try: g = json.load(open(p, encoding='utf-8'))
            except Exception: continue
            for k in ('buffers', 'images'):
                for b in g.get(k) or []:
                    u = b.get('uri')
                    if u and not u.startswith('data:'): add(os.path.join(os.path.dirname(p), *u.split('/')), rel(p), None)
    rows, kinds = [], Counter()
    for p in files:
        ex = os.path.exists(p); b = os.path.getsize(p) if ex else 0
        r = rel(p); kind = ('campaign_characters' if '/campaign_characters/' in r else 'campaign_anims' if '/campaign_anims/' in r
                            else 'extracted_content' if r.startswith('ExtractedAssets/') else 'assettools_other')
        kinds[kind] += b
        rows.append((r, b, ex, kind, ','.join(c for c in CHS if c in refs[p]), first[p]))
    os.makedirs(os.path.join(AT, 'manifests', 'campaign'), exist_ok=True)
    with open(os.path.join(AT, 'manifests', 'campaign', 'campaign_assets_outside_render.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('path\tbytes\texists\tkind\tchapters\tfirst_referenced_by\n')
        for r in sorted(rows): f.write('\t'.join(str(x) for x in r) + '\n')
    summ = OD([('generated_by', 'AssetTools/work/campaign_render/campaign_asset_list.py'), ('files', len(rows)),
               ('missing', [r[0] for r in rows if not r[2]][:200]), ('missing_count', sum(1 for r in rows if not r[2])),
               ('bytes_by_kind', OD(kinds.most_common())), ('bytes_total', sum(kinds.values()))])
    json.dump(summ, open(os.path.join(AT, 'manifests', 'campaign', 'campaign_assets_outside_render.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps({k: v for k, v in summ.items() if k != 'missing'}), summ['missing'][:8])

if __name__ == '__main__':
    main()
