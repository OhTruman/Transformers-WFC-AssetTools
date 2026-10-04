"""Cross-map summary of the generic map pipeline: one row per shipped multiplayer map.

  python map_pipeline_summary.py      -> manifests/maps/pipeline_summary.json

Reads only pipeline outputs (manifests/maps/<MAP>/{completeness,structure_audit}.json, the per-map probe, map.json) and the
frontend registry (cooked flag). Maps whose BASE package is not in the Game Dump are listed as NOT COOKED.
"""
import json, os, sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from m03_common import map_levels  # noqa: E402
from vs_common import VS  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MANI = os.path.join(AT, 'manifests')

def J(p, d=None):
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else d

def main():
    reg = J(os.path.join(MANI, 'frontend_package', 'mp_registry.json'), {})
    rows = OrderedDict()
    for m in reg.get('maps', []):
        internal = m['internal_name']
        name = internal[:-len('_BASE_m')] if internal.lower().endswith('_base_m') else internal
        lv = map_levels(name)
        comp = J(os.path.join(MANI, 'maps', name, 'completeness.json'), {})
        sa = J(os.path.join(MANI, 'maps', name, 'structure_audit.json'), {})
        mj = J(os.path.join(VS, 'Maps', name, 'map.json'), {})
        probe = J(os.path.join(MANI, 'next_map', name + '_probe.json'), {})
        checks = comp.get('checks') or {}
        nonok = {k: v['status'] for k, v in checks.items() if v['status'] not in ('COMPLETE', 'EXPORTED', 'AUTHORED', 'PASS', 'NONE')}
        ps = sa.get('playable_space') or {}
        rows[name] = OrderedDict([
            ('display_name', (m.get('display_name') or {}).get('INT')), ('modes', m.get('supported_modes')),
            ('cooked_in_dump', bool(lv['base'])),
            ('pipeline', 'NOT COOKED - not shipped in this dump' if not lv['base'] else
                         ('Streets-specific order (CLAUDE.md); generic run used as cross-check' if name == 'MP_IAC_Streets' else
                          ('OK' if comp else 'NOT RUN'))),
            ('status', comp.get('status')), ('checks_not_ok', nonok or None),
            ('sublevels', mj.get('sublevels')), ('placed_props', mj.get('placed_props')),
            ('bsp_triangles', sum((v or {}).get('render_triangles') or 0 for v in (mj.get('bsp') or {}).values()) if mj else None),
            ('structure_audit', (sa.get('verdict') or {}).get('status')),
            ('smca_transform_mismatch', (sa.get('transforms') or {}).get('smca_world_glb_matrix_mismatch')),
            ('mirrored_winding', (sa.get('mirrored_instances') or {}).get('verdict')),
            ('player_starts_on_walk_graph', '%s/%s' % (ps.get('starts_on_reachable_floor'), ps.get('player_starts')) if ps else None),
            ('pickups_objectives_on_floor', {k: '%d/%d' % (v['on_walkable_reachable_floor'], v['count']) for k, v in (ps.get('placement_checks') or {}).items()} or None),
            ('collision_floor_agreement_pct', (sa.get('collision_vs_visible') or {}).get('agreement_pct_excluding_volume_tops')),
            ('lightmap_binding_ok', (sa.get('lightmaps') or {}).get('binding_ok')),
            ('blockers_by_owner', comp.get('blockers_by_owner')),
            ('peak_stage_memory_gb', probe.get('peak_memory_gb (max over final runs)'))])
    cooked = [k for k, v in rows.items() if v['cooked_in_dump']]
    out = OrderedDict([('generated_by', 'AssetTools/scripts/wfc/map_pipeline_summary.py'),
                       ('pipeline', 'scripts/wfc/run_map_pipeline.py <MAP> (25 stages, run_bounded 6 GB cap, lock-guarded)'),
                       ('counts', {'registry_maps': len(rows), 'cooked': len(cooked),
                                   'generic_pipeline_ok': sum(1 for k in cooked if rows[k]['pipeline'] == 'OK'),
                                   'structure_audit_pass': sum(1 for k in cooked if rows[k]['structure_audit'] == 'PASS'),
                                   'not_cooked': [k for k, v in rows.items() if not v['cooked_in_dump']]}),
                       ('maps', rows)])
    os.makedirs(os.path.join(MANI, 'maps'), exist_ok=True)
    json.dump(out, open(os.path.join(MANI, 'maps', 'pipeline_summary.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(json.dumps(out['counts']))
    for k, v in rows.items():
        print(k, v['pipeline'][:20], v['status'], v['checks_not_ok'], v['structure_audit'], v['player_starts_on_walk_graph'], v['collision_floor_agreement_pct'])

if __name__ == '__main__':
    main()
