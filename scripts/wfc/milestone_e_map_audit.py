"""Milestone E per-map completeness audit (brief section 12) -> manifests/maps/milestone_e_audit.json + docs/MILESTONE_E_MAP_AUDIT.md

  python milestone_e_map_audit.py

Consolidates the generated evidence (no re-export) for every MP map, per category, with an OPEN list of anything not resolved:
  geometry       completeness placed_meshes / bsp / actors missing from world.glb (structure audit)
  hidden         HiddenGame components marked extras.hidden_game in world.glb (not drawn)
  placeholders   world.glb primitives drawn with the WFC_Default fallback material (non-empty, not hidden)
  materials      Texture2D / TextureFlipBook references without an exported file (TextureCube: Rendering decodes faces)
  particles      map_fx particle templates in authored.db, mesh emitters' meshes exported
  fog / scenery  completeness fog / movers / moving_scenery status + counts
  collision      structure audit verdict; collision vs visible floor agreement; fall-through candidates
  nav            bot_nav anchors with an approach cell, connected pieces, air layer
  spawns         starts on reachable floor; 64-participant capacity (spawn_capacity.json)
Runtime rendering defects come from Rendering's capture audit (none reported after the flipbook fix, 2026-10-06).
"""
import glob, json, os, sys, time
from collections import OrderedDict as OD, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import VS, read_glb  # noqa: E402
import authored as A  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))

def J(p, d=None):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d

def world_checks(path):
    j, b = read_glb(path)
    mats = j.get('materials') or []
    hidden = sum(1 for n in j['nodes'] if (n.get('extras') or {}).get('hidden_game'))
    ph = Counter()
    for n in j['nodes']:
        if 'mesh' not in n or (n.get('extras') or {}).get('hidden_game'): continue
        for p in j['meshes'][n['mesh']]['primitives']:
            m = mats[p['material']] if p.get('material') is not None else {}
            if not (m.get('extras') or {}).get('wfc_material') and 'indices' in p and j['accessors'][p['indices']]['count'] >= 3:
                ph[(n.get('extras') or {}).get('mesh') or n.get('name')] += 1
    return hidden, dict(ph)

def smsections_any(mesh):
    import smsections, objtree
    for (pk,) in objtree.inv().execute("SELECT package FROM exports WHERE opath = ? AND class = 'StaticMesh' ORDER BY serial_size DESC", (mesh,)).fetchall()[:3]:
        try:
            r = smsections.sections(pk, mesh)
            if r: return r
        except Exception: pass
    return None

def main():
    cap = (J(os.path.join(AT, 'manifests', 'maps', 'spawn_capacity.json'), {}) or {})
    assets = None
    maps = OD()
    for D in sorted(glob.glob(os.path.join(VS, 'Maps', 'MP_*'))):
        M = os.path.basename(D)
        comp = (J(os.path.join(AT, 'manifests', 'maps', M, 'completeness.json'), {}) or {}).get('checks') or {}
        sa = J(os.path.join(AT, 'manifests', 'maps', M, 'structure_audit.json'), {}) or {}
        st = lambda k: (comp.get(k) or {}).get('status')
        hidden, ph = world_checks(os.path.join(D, 'world.glb'))
        ma = (J(os.path.join(D, 'materials_authored.json'), {}) or {}).get('materials') or {}
        unbound = sorted({x['texture'] for v in ma.values() for x in (v.get('textures') or {}).values()
                          if isinstance(x, dict) and not x.get('file') and x.get('class') in ('Texture2D', 'TextureFlipBook')})
        fx = J(os.path.join(D, 'map_fx.json'), {}) or {}
        tmpl = set()
        ps_ = fx.get('particle_systems') or {}
        tmpl.update(ps_.keys() if isinstance(ps_, dict) else [x.get('particle_system') for x in ps_ if isinstance(x, dict)])
        for x in fx.get('particle_components') or []:
            t = x.get('template') or x.get('particle_system') if isinstance(x, dict) else None
            if isinstance(t, str): tmpl.add(t)
        tmpl.discard(None)
        fx_missing = sorted(t for t in tmpl if (A.get(t) or {}).get('class') != 'ParticleSystem')
        nav = J(os.path.join(D, 'bot_nav.json'), {}) or {}
        ns = nav.get('stats') or {}
        air = (J(os.path.join(D, 'bot_nav_air.json'), {}) or {}).get('stats') or {}
        ps = sa.get('playable_space') or {}
        cv = sa.get('collision_vs_visible') or {}
        acts = sa.get('actors') or {}
        cm = ((cap.get('maps') or {}).get(M) or {})
        rec = OD([
            ('geometry', OD([('placed_meshes', st('placed_meshes')), ('bsp', st('bsp')),
                             ('missing_mesh', ((comp.get('placed_meshes') or {}).get('evidence') or {}).get('missing_mesh')),
                             ('actors_missing_from_world_glb', len(acts.get('non_collection_actors_missing_from_world_glb') or []) +
                                                               len(acts.get('mode_gated_missing_from_world_glb') or []))])),
            ('hidden_game_marked', hidden), ('placeholder_primitives', ph),
            ('materials', OD([('status', st('materials')), ('unbound_textures', unbound)])),
            ('particles', OD([('status', st('particles')), ('map_fx', st('map_fx')), ('templates', len(tmpl)), ('templates_missing', fx_missing)])),
            ('fog', st('fog')), ('movers', st('movers')), ('moving_scenery', st('moving_scenery')),
            ('collision', OD([('structure_audit', (sa.get('verdict') or {}).get('status')),
                              ('agreement_pct_excluding_volume_tops', cv.get('agreement_pct_excluding_volume_tops')),
                              ('fall_through_candidates', next((v for k, v in cv.items() if k.startswith('visible_floor_cells_next_to_walk_graph_without_collision')), None))])),
            ('nav', OD([('anchors', ns.get('anchors')), ('anchors_with_approach', ns.get('anchors_with_main_approach_cell')),
                        ('cells', ns.get('cells')), ('pieces', ns.get('components')), ('links', ns.get('links')),
                        ('air_free_voxels', air.get('free_voxels'))])),
            ('spawns', OD([('starts', ps.get('player_starts')), ('starts_on_reachable_floor', ps.get('starts_on_reachable_floor')),
                           ('team_first_spawn_ok_64', cm.get('team_mode_ok_for_64')), ('pool', cm.get('ffa_fallback_pool (FFA + team starts)'))])),
        ])
        open_ = []
        if rec['geometry']['missing_mesh']: open_.append('missing meshes: %s' % rec['geometry']['missing_mesh'])
        if rec['geometry']['actors_missing_from_world_glb']: open_.append('actors missing from world.glb')
        # authentic: every non-empty cooked section of the mesh has a null material (engine DefaultMaterial in the original, RE)
        authentic = {}
        for mesh_ in list(ph):
            r_ = smsections_any(mesh_)
            if r_ and all(x['material'] is None for x in r_ if x['num_triangles']): authentic[mesh_] = ph.pop(mesh_)
        rec['placeholder_primitives'] = ph
        rec['null_material_sections_authentic (engine DefaultMaterial)'] = authentic
        if ph: open_.append('placeholder (WFC_Default) primitives: %s' % ph)
        if unbound: open_.append('unbound textures: %s' % unbound[:5])
        if fx_missing: open_.append('particle templates missing: %s' % fx_missing[:5])
        if rec['collision']['structure_audit'] not in (None, 'PASS'): open_.append('structure audit %s' % rec['collision']['structure_audit'])
        if ns.get('anchors') and ns.get('anchors_with_approach') != ns.get('anchors') and ns.get('anchors_with_main_approach_cell') != ns.get('anchors'):
            open_.append('nav: %s / %s anchors reachable' % (ns.get('anchors_with_main_approach_cell'), ns.get('anchors')))
        if ps.get('player_starts') and ps.get('starts_on_reachable_floor') != ps.get('player_starts'): open_.append('starts off reachable floor')
        if cm and cm.get('team_mode_ok_for_64') is False and M.startswith(('MP_IAC', 'MP_UND', 'MP_KON', 'MP_ORB')):
            open_.append('64-player team first-spawn short (Gameplay spawn rule; PC ADAPTATION)')
        rec['open'] = open_
        maps[M] = rec
    out = OD([('generated_by', 'AssetTools/scripts/wfc/milestone_e_map_audit.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('scope', 'Milestone E brief section 12: per-map completeness from generated evidence; runtime defects per Rendering capture audit'),
              ('maps', maps), ('open_total', sum(len(v['open']) for v in maps.values()))])
    json.dump(out, open(os.path.join(AT, 'manifests', 'maps', 'milestone_e_audit.json'), 'w', encoding='utf-8'), indent=1, default=str)
    L = ['# Milestone E map completeness audit', '',
         '*Generated by `scripts/wfc/milestone_e_map_audit.py` (%s). Do not edit; rerun the generator. Evidence: '
         '`manifests/maps/milestone_e_audit.json`.*' % out['generated'], '',
         '| map | geometry | hidden marked | placeholders | unbound tex | FX templates | fog | movers | collision | nav anchors | starts on floor | 64 team spawn | open |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for M, r in maps.items():
        L.append('| %s | %s | %d | %d | %d | %d (%d missing) | %s | %s | %s | %s / %s | %s / %s | %s | %s |' % (
            M, r['geometry']['placed_meshes'], r['hidden_game_marked'], sum(r['placeholder_primitives'].values()), len(r['materials']['unbound_textures']),
            r['particles']['templates'], len(r['particles']['templates_missing']), r['fog'], r['movers'], r['collision']['structure_audit'],
            r['nav']['anchors_with_approach'], r['nav']['anchors'], r['spawns']['starts_on_reachable_floor'], r['spawns']['starts'],
            r['spawns']['team_first_spawn_ok_64'], '; '.join(r['open']) or '-'))
    open(os.path.join(AT, 'docs', 'MILESTONE_E_MAP_AUDIT.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('open items:', out['open_total'])
    for M, r in maps.items(): print(M, r['open'])

if __name__ == '__main__':
    main()
