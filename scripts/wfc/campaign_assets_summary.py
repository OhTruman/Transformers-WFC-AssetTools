"""Campaign-wide summary of manifests/campaign/<ch>_assets.json (campaign_chapter_assets.py).
Writes manifests/campaign/summary.json + work/handoff/CAMPAIGN_ASSETS_SUMMARY.md (tables; prose sections are appended by hand).
"""
import json, os, sys
from collections import Counter, OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CH = ['A1_IAC', 'A2_KON', 'A3_COR', 'A4_ORB', 'A5_TRY', 'D1_ORB', 'D2_COR', 'D3A_IAC', 'D3B_IAC', 'D5_OME']

def main():
    rows, union, mats, fx_partial = OD(), {}, {}, {}
    for ch in CH:
        m = json.load(open(os.path.join(ROOT, 'manifests', 'campaign', ch.split('_')[0].lower() + '_assets.json'), encoding='utf-8'))
        g = m['groups']; S = lambda k: g[k]['summary']
        k = Counter()
        for cc in ((m.get('kismet') or {}).get('counts_by_level') or {}).values(): k.update(cc)
        mc = (m.get('matinee') or {}).get('counts') or {}
        lacks = m['dump_lacks']
        dump_gaps = (len(lacks['levels_in_streaming_not_cooked']) +
                     len(lacks['imports_unresolved (content: no export with that path in any dumped package)']) +
                     len(lacks['imports_resolved_only_in_other_packages (object -> packages that export it)']) +
                     len(lacks['sound_waves_without_file']))
        tr = S('materials')['translator']
        rows[ch] = OD([
            ('levels', m['levels']['count']), ('companions_lm_int_fra', [m['companion_packages'][x] for x in ('lightmaps', 'loc_int', 'loc_fra')]),
            ('deps', len(m['package_dependencies'])), ('objects', m['totals']['distinct_objects']),
            ('mb', round(m['totals']['bytes_distinct_objects'] / 1e6, 1)),
            ('static_meshes', S('static_meshes')['count']), ('skeletal_meshes', S('skeletal_meshes')['count']),
            ('textures', S('textures')['count']), ('textures_not_extracted', len(S('textures')['not_extracted'])),
            ('cues', S('sound_cues')['count']), ('waves', S('sound_waves')['count']),
            ('anim_sets', S('anim_sets')['count']), ('anim_sets_psa_only', len(S('anim_sets')['not_extracted'])),
            ('materials', S('materials')['count']), ('translated', tr.get('translated', 0)), ('candidate', tr.get('candidate', 0)),
            ('missing', tr.get('missing', 0)), ('translator_error', tr.get('translator_error', 0)),
            ('fx', S('fx_templates')['count']), ('fx_partial', S('fx_templates')['pstream'].get('PARTIAL', 0)),
            ('kismet_sequences', k.get('Sequence', 0)), ('matinees', mc.get('interp_data')),
            ('matinee_live_without_actor', mc.get('unbound_groups_live_without_actor')),
            ('ai_factories', ((m.get('ai') or {}).get('counts') or {}).get('pawn_factories')),
            ('conversations', ((m.get('dialog') or {}).get('counts') or {}).get('conversations')),
            ('objectives', ((m.get('objectives') or {}).get('counts') or {}).get('bank_keys')),
            ('checkpoints', len(m['checkpoints'])), ('fmv', sorted(m['movies'])), ('dump_gaps', dump_gaps)])
        for grp, v in g.items():
            for it in v['items']:
                u = union.setdefault(grp, {})
                u[it['object']] = max(u.get(it['object'], 0), it['bytes'])
                if grp == 'materials': mats.setdefault(it['object'], OD([('status', it['translator']), ('master', it.get('master')), ('chapters', [])]))['chapters'].append(ch)
                if grp == 'fx_templates' and it.get('pstream') == 'PARTIAL': fx_partial.setdefault(it['object'], []).append(ch)
    tot = OD((k, sum(r[k] for r in rows.values())) for k in ('levels', 'objects', 'static_meshes', 'skeletal_meshes', 'textures',
                                                          'cues', 'waves', 'anim_sets', 'materials', 'fx', 'kismet_sequences', 'matinees',
                                                          'ai_factories', 'conversations', 'objectives', 'checkpoints', 'dump_gaps'))
    tot['mb_sum'] = round(sum(r['mb'] for r in rows.values()), 1)
    distinct = OD((g, OD([('count', len(u)), ('mb', round(sum(u.values()) / 1e6, 1))])) for g, u in union.items())
    mstat = Counter(v['status'] for v in mats.values())
    out = OD([('generated_by', 'AssetTools/scripts/wfc/campaign_assets_summary.py'), ('chapters', rows), ('sum_over_chapters', tot),
              ('distinct_across_campaign', distinct), ('materials_distinct_status', dict(mstat)),
              ('materials_missing_masters', sorted({v['master'] for v in mats.values() if v['status'] == 'missing'})),
              ('materials_candidate_masters', sorted({v['master'] for v in mats.values() if v['status'] == 'candidate'})),
              ('materials', mats), ('fx_partial', fx_partial)])
    json.dump(out, open(os.path.join(ROOT, 'manifests', 'campaign', 'summary.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k in ('sum_over_chapters', 'distinct_across_campaign', 'materials_distinct_status')}, indent=1))
    print('missing masters', len(out['materials_missing_masters']), 'candidate masters', len(out['materials_candidate_masters']), 'fx partial', fx_partial)
    # table
    hdr = ['chapter', 'levels (+LM/INT/FRA)', 'deps', 'objects / MB', 'meshes st / sk', 'textures (not extr.)', 'cues / waves',
           'anim sets (psa-only)', 'materials tr / cand / miss', 'FX (PARTIAL)', 'Kismet seq / matinees (live w/o actor)',
           'AI / conv / obj / ckpt', 'FMV', 'dump gaps']
    L = ['| ' + ' | '.join(hdr) + ' |', '|' + '---|' * len(hdr)]
    for ch, r in rows.items():
        L.append('| ' + ' | '.join(str(x) for x in [
            ch, '%d (%s)' % (r['levels'], '/'.join(map(str, r['companions_lm_int_fra']))), r['deps'], '%s / %s' % (format(r['objects'], ','), r['mb']),
            '%d / %d' % (r['static_meshes'], r['skeletal_meshes']), '%s (%d)' % (format(r['textures'], ','), r['textures_not_extracted']),
            '%s / %s' % (format(r['cues'], ','), format(r['waves'], ',')), '%d (%d)' % (r['anim_sets'], r['anim_sets_psa_only']),
            '%d / %d / %d' % (r['translated'], r['candidate'], r['missing']), '%d (%d)' % (r['fx'], r['fx_partial']),
            '%d / %s (%s)' % (r['kismet_sequences'], r['matinees'], r['matinee_live_without_actor']),
            '%s / %s / %s / %d' % (r['ai_factories'], r['conversations'], r['objectives'], r['checkpoints']),
            ', '.join(x.replace('FMV_', '') for x in r['fmv']) or '-', r['dump_gaps']]) + ' |')
    open(os.path.join(ROOT, 'work', 'campaign_assets', 'summary_table.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')

if __name__ == '__main__':
    main()
