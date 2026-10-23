"""Campaign HD / material coverage (Integration 2026-10-23, scoping only; read-only, generates no textures).

Per chapter (manifests/campaign/<ch>_assets.json groups.textures items, Texture2D only; light maps are their own group, not here):
  - hd_D:  has a row in the shipped colour pack D (out/hd/push_full_snap_20261016_b0-31/pack/hd_index.json, by object_path);
  - m6:    has an M6 PBR row (out/hd/push_m6/pack/hd_pbr_index.json, by tex);
  - shared_with_mp: the texture is also cooked into an MP map package (inventory.db), i.e. MP HD work already applies to it;
  - gap: extracted, Texture2D, no pack D row. Source size = the extracted PNG's IHDR (width x height).
Materials: a chapter material (manifests/campaign/render_materials/<CH>.json chapter set is not stored, so inventory.db) is 'covered'
when every Texture2D it references (authored.db refs from the material and its expressions) has a pack D row.
Gap size estimate (PROVISIONAL): pack D's own ratio, median over its rows of DDS bytes / source texels, by format family
(colour / normal / other as recorded in the row's 'class'), applied to the gap's source texels.
Writes work/campaign_hd/hd_coverage.json and prints the per-chapter table.
"""
import json, os, sqlite3, struct, statistics
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
EA = r'F:\Transformers Rebuild\ExtractedAssets'
PACK_D = os.path.join(AT, 'out', 'hd', 'push_full_snap_20261016_b0-31', 'pack', 'hd_index.json')
M6 = os.path.join(AT, 'out', 'hd', 'push_m6', 'pack', 'hd_pbr_index.json')
CH = ['a1', 'a2', 'a3', 'a4', 'a5', 'd1', 'd2', 'd3a', 'd3b', 'd5']
CVS = os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice', 'Maps')

def png_size(obj):
    p = os.path.join(EA, 'content', *obj.split('.')) + '.png'
    try:
        with open(p, 'rb') as f: h = f.read(24)
        return struct.unpack('>II', h[16:24]) if h[12:16] == b'IHDR' else None
    except OSError: return None

def main():
    D = json.load(open(PACK_D, encoding='utf-8'))['rows']; M = json.load(open(M6, encoding='utf-8'))['rows']
    d_by = {r['object_path'].lower(): r for r in D}
    m_by = defaultdict(list)
    for r in M: m_by[r['tex'].lower()].append(r['role'])
    ratio = defaultdict(list)
    for r in D:
        s = png_size(r['object_path'])
        if s and s[0] * s[1]: ratio[r.get('class', 'other')].append(r['bytes'] / (s[0] * s[1]))
    ratio_med = {k: statistics.median(v) for k, v in ratio.items()}
    inv = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db')); db = sqlite3.connect(os.path.join(AT, 'manifests', 'authored.db'))
    mp_tex = {r[0].lower() for r in inv.execute("select distinct opath from exports where package like 'MP_%' and class='Texture2D'")}
    # material -> Texture2D refs in one pass (refs from the material itself or from its expressions one level down)
    mat_tex = defaultdict(set)
    for src, dst in db.execute("select src, dst from refs where dst_class='Texture2D'"):
        mat_tex[src].add(dst); mat_tex[src.rsplit('.', 1)[0]].add(dst)
    out, allgap = {}, {}
    for ch in CH:
        a = json.load(open(os.path.join(AT, 'manifests', 'campaign', ch + '_assets.json'), encoding='utf-8'))
        items = [t for t in a['groups']['textures']['items'] if t['class'] == 'Texture2D']
        c = Counter(); gap = []
        for t in items:
            o = t['object'].lower(); hd = o in d_by
            c['texture2d'] += 1; c['hd_D'] += hd; c['m6'] += o in m_by; c['shared_with_mp'] += o in mp_tex
            c['not_extracted'] += not t.get('extracted')
            if not hd and t.get('extracted'):
                s = png_size(t['object'])
                gap.append({'object': t['object'], 'cooked_bytes': t['bytes'], 'size': list(s) if s else None, 'shared_with_mp': o in mp_tex,
                            'normal_like': any(x in o for x in ('_norm', 'normx', 'normy', '_nrm'))})
        # materials
        cv = json.load(open(os.path.join(CVS, a['chapter'] if a.get('chapter') in os.listdir(CVS) else ch.upper(), 'map.json'), encoding='utf-8')) \
            if os.path.isdir(os.path.join(CVS, str(a.get('chapter')))) else None
        subs = cv['sublevels'] if cv else []
        mats = {r[0] for r in inv.execute("select distinct opath from exports where package in (%s) and class in ('Material','MaterialInstanceConstant','MaterialInstanceTimeVarying')" % ','.join('?' * len(subs)), subs)} if subs else set()
        mc = Counter()
        for m in mats:
            tx = mat_tex.get(m, set())
            if not tx: mc['no_texture'] += 1; continue
            mc['with_textures'] += 1; mc['all_hd_D'] += all(t.lower() in d_by for t in tx); mc['some_hd_D'] += any(t.lower() in d_by for t in tx)
        for g in gap: allgap.setdefault(g['object'].lower(), dict(g, chapters=[]))['chapters'].append(ch)
        texels = sum(g['size'][0] * g['size'][1] for g in gap if g['size'])
        out[ch] = {'chapter': a.get('chapter'), 'textures': dict(c), 'gap': len(gap), 'gap_campaign_only': sum(not g['shared_with_mp'] for g in gap),
                   'gap_source_megatexels': round(texels / 1e6, 2), 'materials': dict(mc, total=len(mats)),
                   'gap_items': sorted(gap, key=lambda g: -(g['size'][0] * g['size'][1] if g['size'] else 0))}
    tot_tex = sum(g['size'][0] * g['size'][1] for g in allgap.values() if g['size'])
    est = sum(g['size'][0] * g['size'][1] * ratio_med.get('normal' if g['normal_like'] else 'colour', statistics.median([x for v in ratio.values() for x in v]))
              for g in allgap.values() if g['size'])
    summary = {'pack_D_rows': len(D), 'm6_rows': len(M), 'pack_D_bytes_per_source_texel_median': {k: round(v, 3) for k, v in ratio_med.items()},
               'distinct_gap_textures': len(allgap), 'distinct_gap_campaign_only': sum(not g['shared_with_mp'] for g in allgap.values()),
               'distinct_gap_no_png': sum(1 for g in allgap.values() if not g['size']),
               'distinct_gap_source_megatexels': round(tot_tex / 1e6, 1), 'estimated_hd_bytes (PROVISIONAL, pack D ratio)': int(est),
               'gap_resolution_histogram': dict(Counter('%dx%d' % tuple(g['size']) if g['size'] else 'no png' for g in allgap.values()).most_common(12))}
    json.dump({'generated_by': 'AssetTools/work/campaign_hd/hd_coverage.py', 'summary': summary, 'chapters': out,
               'distinct_gap': sorted(allgap.values(), key=lambda g: g['object'])}, open(os.path.join(HERE, 'hd_coverage.json'), 'w', encoding='utf-8'), indent=1)
    for ch, r in out.items():
        print('%-4s %-8s tex %4d hdD %4d m6 %3d mp-shared %4d gap %4d (campaign-only %4d, %6.1f Mtexel) | mats %4d with-tex %4d all-hd %4d some-hd %4d' % (
            ch, r['chapter'], r['textures']['texture2d'], r['textures']['hd_D'], r['textures']['m6'], r['textures']['shared_with_mp'], r['gap'],
            r['gap_campaign_only'], r['gap_source_megatexels'], r['materials'].get('total', 0), r['materials'].get('with_textures', 0),
            r['materials'].get('all_hd_D', 0), r['materials'].get('some_hd_D', 0)))
    print(json.dumps(summary, indent=1))

if __name__ == '__main__':
    main()
