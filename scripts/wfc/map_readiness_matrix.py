"""Runtime-readiness matrix for every cooked multiplayer map -> manifests/maps/readiness_matrix.json + docs/MAP_READINESS_MATRIX.md

  python map_readiness_matrix.py

Columns: GEOMETRY COLLISION LIGHTING MATERIALS FX MOVERS PICKUPS MODE_ACTORS AUDIO NAVIGATION READY_FOR_RUNTIME.
Each cell = one verdict from the vocabulary below + the evidence it was derived from (pipeline outputs only):
  COMPLETE AUTHORED DATA EXTRACTED   every authored record for the area is exported and validated
  EXTRACTION DEFECT                  AssetTools data is missing / failed validation (AssetTools must fix)
  RENDERER MUST SIMULATE             data complete; the renderer has to apply / simulate it (owner RENDERING)
  GAMEPLAY MUST SIMULATE             data complete; runtime behaviour belongs to Gameplay / Systems
  UNKNOWN                            not determinable from authored data
A cell may carry a second verdict (e.g. data COMPLETE + RENDERER MUST SIMULATE) in `consumer_action`.
`consumer_observations` (optional, read-only) compares what a consumer currently loads with the data: the Rendering lane's
work/render/<MAP>/lighting.json (vertex lightmap samples, CLUT). Timestamped; never used for the verdicts.
"""
import json, os, sys, time
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import VS  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MANI = os.path.join(AT, 'manifests')
REND = os.path.normpath(os.path.join(AT, '..', 'Rebuild-Rendering', 'work', 'render'))
GEN = 'AssetTools/scripts/wfc/map_readiness_matrix.py'
OK, DEF, RND, GPL, UNK = ('COMPLETE AUTHORED DATA EXTRACTED', 'EXTRACTION DEFECT', 'RENDERER MUST SIMULATE',
                          'GAMEPLAY MUST SIMULATE', 'UNKNOWN')

def J(p, d=None):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d

def cell(verdict, evidence, action=None):
    c = OrderedDict([('verdict', verdict), ('evidence', evidence)])
    if action: c['consumer_action'] = action
    return c

def row(M):
    D = os.path.join(VS, 'Maps', M)
    comp = J(os.path.join(MANI, 'maps', M, 'completeness.json'), {}); ch = comp.get('checks') or {}
    sa = J(os.path.join(MANI, 'maps', M, 'structure_audit.json'), {})
    ri = J(os.path.join(D, 'render_index.json'), {})
    vl = J(os.path.join(D, 'vertex_lightmaps.json'), {})
    lm = J(os.path.join(D, 'lightmaps.json'), {}); pp = J(os.path.join(D, 'postprocess.json'), {})
    st = lambda k: (ch.get(k) or {}).get('status')
    ev = lambda k: (ch.get(k) or {}).get('evidence')
    r = OrderedDict()
    tr = sa.get('transforms') or {}
    geo_ok = st('bsp') == 'COMPLETE' and st('placed_meshes') == 'COMPLETE' and tr.get('smca_world_glb_matrix_mismatch') == 0 \
        and (sa.get('mirrored_instances') or {}).get('verdict') == 'CONSISTENT'
    r['GEOMETRY'] = cell(OK if geo_ok else DEF, {'bsp': (ev('bsp_alignment') or {}).get('verdict') if isinstance(ev('bsp_alignment'), dict) else st('bsp'),
                                                 'placed': ev('placed_meshes'), 'smca_mismatch': tr.get('smca_world_glb_matrix_mismatch'),
                                                 'mirrored_winding': (sa.get('mirrored_instances') or {}).get('verdict'),
                                                 'skyline_props_outside_play': (ev('skyline_background_geometry') or {}).get('props_outside_playable_bounds_plus_50m')})
    ps = sa.get('playable_space') or {}; cv = sa.get('collision_vs_visible') or {}
    unexpl = [e for e in cv.get('blocking_gaps_explained') or [] if e.get('reason') == 'UNEXPLAINED']
    col_ok = ps.get('starts_on_reachable_floor') == ps.get('player_starts') and not unexpl and st('collision') == 'COMPLETE'
    r['COLLISION'] = cell(OK if col_ok and st('kill_volumes') == 'COMPLETE' else DEF, {'starts_on_walk_graph': '%s/%s' % (ps.get('starts_on_reachable_floor'), ps.get('player_starts')),
                                                  'pickups_objectives_on_floor': ps.get('placement_checks'), 'floor_agreement_pct': cv.get('agreement_pct_excluding_volume_tops'),
                                                  'unexplained_gaps': len(unexpl), 'kill_z_ue': ps.get('kill_z_ue'),
                                                  'hazard_volumes': ev('kill_volumes')},
                          GPL + ': apply KillZ + pain / kill volumes (manifests/maps/%s/hazard_volumes.json)' % M if (ev('kill_volumes') or {}).get('hazard_volumes') else None)
    vs = (vl.get('stats') or {})
    vfail = sum((vs.get('decode_failures') or {}).values())
    lmo = (sa.get('lightmaps') or {}).get('binding_ok')
    vol = [v for v in (ev('postprocess') or {}).get('volumes') or [] if v.get('clut')]
    lit_ok = bool(vl) and lmo and vfail == 0 and st('lights') == 'COMPLETE' and st('fog') in ('COMPLETE', 'NONE') and st('postprocess') == 'COMPLETE'
    acts = ['apply per-vertex baked light from vertex_lightmaps.json (%d LMT_1D components; sample 4th byte %s)' %
            (vs.get('components') or 0, vs.get('fourth_byte'))] if vs.get('components') else []
    if vol: acts.append('apply the PostProcessVolume colour grade (%s; covers %s player starts) - no WorldInfo CLUT' %
                        (', '.join(v['clut'] for v in vol), vol[0]['player_starts_inside']) if not (ev('postprocess') or {}).get('world_clut')
                        else 'world CLUT %s plus volume grade %s' % ((ev('postprocess') or {}).get('world_clut'), ', '.join(v['clut'] for v in vol)))
    r['LIGHTING'] = cell(OK if lit_ok else DEF, {'texture_lightmaps': (sa.get('lightmaps') or {}).get('world_glb_nodes_with_lm_atlas'),
                                                 'lightmap_binding_ok': lmo, 'vertex_lightmaps': vs.get('components'),
                                                 'vertex_count_check': vs.get('vertex_count_check'), 'lights': (ev('lights') or {}).get('lights'),
                                                 'fog': ev('fog'), 'world_clut': (ev('postprocess') or {}).get('world_clut'),
                                                 'volume_grades': [{k: v.get(k) for k in ('volume', 'clut', 'player_starts_inside', 'scene_tone')} for v in vol]},
                         (RND + ': ' + '; '.join(acts)) if acts else None)
    mats = ev('materials') or {}; df = ev('bsp_default_material_faces') or {}
    r['MATERIALS'] = cell(OK if st('materials') == 'COMPLETE' else DEF,
                          {'materials': mats.get('count'), 'missing': mats.get('missing'), 'mic': (ev('material_instances') or {}).get('by_class'),
                           'default_material_faces_visible_in_play': df.get('visible_in_play')},
                          RND + ': %s authored DefaultMaterial BSP faces visible in play (authored, not a defect)' % df.get('visible_in_play')
                          if df.get('visible_in_play') else None)
    r['FX'] = cell(OK if st('map_fx') in ('EXPORTED', 'NONE') else DEF, {'particles': (ev('map_fx') or {}).get('particle_components'),
                                                                        'decals': (ev('decals') or {}).get('decals'),
                                                                        'pickup_fx': ((ri.get('pickup_fx_components') or {}).get('count'))},
                   RND + ': simulate particle systems (decoded module streams), project decals')
    r['MOVERS'] = cell(OK, {'movers': (ev('movers') or {}).get('count'), 'physics': (ev('movers') or {}).get('physics'),
                            'matinee': (ev('movers') or {}).get('matinee'),
                            'missing_from_world_glb': (sa.get('actors') or {}).get('non_collection_actors_missing_from_world_glb')},
                       GPL + ': PHYS_Rotating / Matinee runtime')
    rv = ri.get('validation') or {}
    r['PICKUPS'] = cell(OK if ri and not rv.get('missing') else DEF, {'factories': (ev('pickups') or {}).get('by_class'),
                                                                      'render_index_pickup_visuals': rv.get('pickup_visuals'),
                                                                      'render_index_present': bool(ri)},
                        GPL + ': pickup state machines (respawn, availability)')
    r['MODE_ACTORS'] = cell(OK if ri.get('mode_visual_state') is not None else DEF,
                            {'classes': list((ri.get('mode_visual_state') or {}).keys()), 'tdm_hidden': (ri.get('tdm_render_state') or {}).get('count'),
                             'renderables': rv.get('counts')}, GPL + ': mode gating per mode_visual_state')
    au = ev('audio_emitters') or {}
    r['AUDIO'] = cell(OK if st('audio_emitters') == 'COMPLETE' else DEF, {'emitters': au, 'zones_reverb': ev('zones_reverb')},
                      GPL + ' (Systems): ambient zones / reverb via Kismet SeqAct_AmbientAudioZone / SeqAct_Reverb')
    nv = ev('navigation') or {}
    r['NAVIGATION'] = cell(OK if st('navigation') == 'COMPLETE' else DEF, nv,
                           UNK + ': original-AI bots need tactical data the MP maps do not author (ReachSpec graph only)')
    defects = [k for k, v in r.items() if v['verdict'] == DEF]
    r['READY_FOR_RUNTIME'] = cell('DATA COMPLETE' if not defects else 'NOT READY: ' + ', '.join(defects),
                                  {'extraction_defects': defects, 'consumer_actions': {k: v['consumer_action'] for k, v in r.items() if v.get('consumer_action')}})
    obs = None
    lj = os.path.join(REND, M, 'lighting.json')
    if os.path.exists(lj):
        L = J(lj, {})
        c = L.get('lightmap_type_counts') or {}
        obs = {'source': 'Rebuild-Rendering/work/render/%s/lighting.json (read-only, %s)' % (M, time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(lj)))),
               'vertex_components': len(c.get('vertex_components') or []), 'vertex_samples_loaded': len(L.get('vertex_lightmaps') or {}),
               'clut_loaded': bool((L.get('postprocess') or {}).get('clut'))}
        obs['gaps'] = [g for g in (
            'vertex lightmaps: %d of %d components have samples (AssetTools vertex_lightmaps.json has %d)' %
            (obs['vertex_samples_loaded'], obs['vertex_components'], vs.get('components') or 0) if obs['vertex_samples_loaded'] < obs['vertex_components'] else None,
            'colour grade: no CLUT loaded although the map authors %s' % ', '.join(v['clut'] for v in vol) if vol and not obs['clut_loaded'] else None) if g]
    return r, obs

def main():
    summ = J(os.path.join(MANI, 'maps', 'pipeline_summary.json'), {}).get('maps') or {}
    maps = [m for m, v in summ.items() if v.get('cooked_in_dump')] or sorted(d for d in os.listdir(os.path.join(VS, 'Maps')) if d.startswith('MP_'))
    rows, obs = OrderedDict(), OrderedDict()
    for M in maps:
        rows[M], o = row(M)
        if o: obs[M] = o
    cols = ['GEOMETRY', 'COLLISION', 'LIGHTING', 'MATERIALS', 'FX', 'MOVERS', 'PICKUPS', 'MODE_ACTORS', 'AUDIO', 'NAVIGATION', 'READY_FOR_RUNTIME']
    out = OrderedDict([('generated_by', GEN), ('generated', time.strftime('%Y-%m-%d %H:%M')), ('vocabulary', [OK, DEF, RND, GPL, UNK]),
                       ('data_root', 'ExtractedAssets/VerticalSlice/Maps/<MAP>/ (local, not pushed); manifests/maps/<MAP>/ and manifests/next_map/<MAP>_*'),
                       ('columns', cols), ('maps', rows), ('consumer_observations (read-only, not used for verdicts)', obs),
                       ('not_cooked', [m for m, v in summ.items() if not v.get('cooked_in_dump')])])
    json.dump(out, open(os.path.join(MANI, 'maps', 'readiness_matrix.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    short = {OK: 'DATA OK', DEF: 'DEFECT', RND: 'RENDERER', GPL: 'GAMEPLAY', UNK: 'UNKNOWN'}
    def tag(c):
        v = short.get(c['verdict'], c['verdict'])
        a = c.get('consumer_action') or ''
        return v + (' / ' + short.get(next((x for x in short if a.startswith(x)), ''), '') if a and v == 'DATA OK' else '')
    md = ['# Multiplayer map runtime-readiness matrix', '',
          '*Generated by `scripts/wfc/map_readiness_matrix.py` (%s) from pipeline outputs. Do not edit; rerun the generator.*' % out['generated'], '',
          '**Cell format:** `DATA OK` means complete authored data was extracted. `/ RENDERER` or `/ GAMEPLAY` names who must still '
          'apply or simulate it. `DEFECT` means AssetTools data is missing. The evidence and exact consumer actions are in '
          '`manifests/maps/readiness_matrix.json`.', '',
          '| MAP | ' + ' | '.join(cols) + ' |', '|' + '---|' * (len(cols) + 1)]
    for M, r in rows.items():
        md.append('| %s | %s |' % (M, ' | '.join(tag(r[c]) if c != 'READY_FOR_RUNTIME' else r[c]['verdict'] for c in cols)))
    md += ['', '## Consumer actions per map']
    for M, r in rows.items():
        acts = r['READY_FOR_RUNTIME']['evidence']['consumer_actions']
        md.append('* **%s:**' % M)
        md += ['  * %s: %s' % (k, v) for k, v in acts.items() if k in ('LIGHTING', 'MATERIALS')]
        if M in obs and obs[M]['gaps']:
            md.append('  * consumer observed (%s): %s' % (obs[M]['source'].split('(')[-1].rstrip(')'), '; '.join(obs[M]['gaps'])))
    md += ['', 'Not cooked in this dump (no data possible): ' + ', '.join(out['not_cooked'])]
    open(os.path.join(AT, 'docs', 'MAP_READINESS_MATRIX.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    for M, r in rows.items(): print(M, [tag(r[c]) for c in cols[:-1]], r['READY_FOR_RUNTIME']['verdict'])

if __name__ == '__main__':
    main()
