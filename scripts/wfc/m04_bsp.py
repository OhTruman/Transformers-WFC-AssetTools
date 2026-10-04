"""MP_IAC_Streets BSP audit (M04).

Two independent views of the cooked BSP, compared:
  A. bsp.py node polygons (what vs_map.py triangulated into world.glb / collision.glb)
  B. the cooked render partition: every ModelComponent's FModelElement list (material, node indices, lightmap
     reference type) - layout after the Rendering lane's build_lighting.parse_model_component (read-only reference),
     re-implemented here.
Accounting: every node with >= 3 vertices is either rendered by exactly one element, or carries PF_INVISIBLE /
PF_PORTAL (non-rendered), or is listed as unaccounted. Per surface: flags, material, normal, collision relevance.
Output: AssetTools/manifests/streets_bsp_audit.json
"""
import json, os, struct, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, bsp  # noqa: E402
from m03_common import write, CONF, HIGH, PART, UNK, map_arg, map_out, map_levels, bsp_level  # noqa: E402
from vs_common import VS  # noqa: E402

MAP = map_arg()                      # positional map name (default MP_IAC_Streets)
LV_ = map_levels(MAP)
LEVELS = LV_['all']
FLAG_NAMES = {0x1: 'Invisible', 0x2: 'Masked', 0x4: 'Translucent', 0x8: 'NotSolid', 0x10: 'Environment', 0x20: 'Semisolid',
              0x40: 'BeveledEdges', 0x80: 'Portal?0x80', 0x100: 'TwoSided', 0x200: 'UE3 flag 0x200 (name UNKNOWN; not UE2 Cutout)', 0x400: 'UE3 flag 0x400 (name UNKNOWN; not UE2 FakeBackdrop)',
              0x800: 'UE3 flag 0x800 (name UNKNOWN; not UE2 Mirror)', 0x1000: 'Unused1000', 0x2000: 'NoSmooth', 0x8000: 'NoBounce?', 0x10000: 'BrightCorners',
              0x40000: 'Unused40000', 0x80000: 'SpecialLit', 0x100000: 'Flat?', 0x400000: 'NoImpact?',
              0x1000000: 'Unused1000000', 0x4000000: 'Portal', 0x8000000: 'Mirror?', 0x10000000: 'Unused',
              0x40000000: 'Selected?', 0x80000000: 'Memorized?'}

def flags(f):
    return [n for b, n in sorted(FLAG_NAMES.items()) if f & b]

def parse_model_component(p, t, model_idx):
    key = struct.pack('>i', model_idx)
    a = t.find(key, 0, 16)
    if a < 4: return None
    o = a + 4
    ne = struct.unpack_from('>i', t, o)[0]; o += 4
    els = []
    for _ in range(ne):
        _pad, comp, mat, nn = struct.unpack_from('>iiii', t, o); o += 16
        nodes = list(struct.unpack_from('>%dH' % nn, t, o)); o += 2 * nn
        ns = struct.unpack_from('>i', t, o)[0]; o += 4 + 4 * ns
        ni = struct.unpack_from('>i', t, o)[0]; o += 4 + 16 * ni
        lt = struct.unpack_from('>i', t, o)[0]; o += 4
        lm = None
        if lt == 2:
            ng = struct.unpack_from('>i', t, o)[0]; o += 4 + 16 * ng + 4
            co = []
            for _c in range(3):
                ref = struct.unpack_from('>i', t, o)[0]
                co.append(p.object_path(ref) if ref > 0 else None); o += 20
            o += 16
            lm = co
        elif lt != 0:
            raise ValueError('lightmap type %d' % lt)
        ng2 = struct.unpack_from('>i', t, o)[0]; o += 4 + 16 * ng2
        els.append({'material': (p.object_path(mat) if mat > 0 else p.full_path(mat)) if mat else None,
                    'nodes': nodes, 'shadowmaps': ns, 'irrelevant_lights': ni, 'lightmap_type': lt, 'lightmap_textures': lm})
    return els

def audit_level(lv):
    p = objtree.package(lv)
    level = next((i + 1 for i, e in enumerate(p.exports) if p.class_name(e) == 'Level'), None)
    models = [i + 1 for i, e in enumerate(p.exports) if p.class_name(e) == 'Model' and e['outer'] == level]
    best = None
    for mi in models:
        try:
            M = bsp.read_model(p, mi)
            if best is None or len(M['nodes']) > len(best[1]['nodes']): best = (mi, M)
        except Exception:
            pass
    if not best or not len(best[1]['nodes']):
        return {'level': lv, 'model_exports': [p.object_path(m) for m in models], 'nodes': 0,
                'note': 'level Model has no BSP nodes (no BSP geometry in this sublevel)'}
    mi, M = best
    nodes, surfs = M['nodes'], M['surfs']
    poly_nodes = [i for i in range(len(nodes)) if int(nodes[i]['NumVertices']) >= 3]
    # elements
    pr = p._tr
    elements, unparsed = [], []
    for i, ex in enumerate(p.exports):
        if p.class_name(ex) != 'ModelComponent' or ex['outer'] != level: continue
        _, used = pr.read_object(i + 1)
        tail = p.data[ex['serial_offset'] + used - 8:ex['serial_offset'] + ex['serial_size']]
        try: els = parse_model_component(p, tail, mi)
        except Exception as x: els = None
        if els is None: unparsed.append(p.object_path(i + 1)); continue
        for k, el in enumerate(els):
            el['component'] = p.object_path(i + 1); el['element'] = k
            elements.append(el)
    owner = defaultdict(list)
    for ei, el in enumerate(elements):
        for n in el['nodes']: owner[n].append(ei)
    acc = Counter(); unacc = []
    surf_stats = defaultdict(lambda: {'nodes': 0, 'triangles': 0})
    for n in poly_nodes:
        s = surfs[int(nodes[n]['iSurf'])]; f = int(s['PolyFlags'])
        k = int(nodes[n]['NumVertices'])
        st = surf_stats[int(nodes[n]['iSurf'])]; st['nodes'] += 1; st['triangles'] += k - 2
        if len(owner[n]) == 1: acc['rendered_by_one_element'] += 1
        elif len(owner[n]) > 1: acc['rendered_by_multiple_elements'] += 1
        elif f & (bsp.PF_INVISIBLE | bsp.PF_PORTAL): acc['not_rendered_invisible_or_portal'] += 1
        else: acc['UNACCOUNTED'] += 1; unacc.append(n)
    tri_render = sum(int(nodes[n]['NumVertices']) - 2 for n in poly_nodes if owner[n])
    tri_all = sum(int(nodes[n]['NumVertices']) - 2 for n in poly_nodes)
    surf_recs = []
    for si, st in sorted(surf_stats.items()):
        s = surfs[si]; f = int(s['PolyFlags'])
        mat = int(s['Material'])
        act = int(s['Actor'])
        surf_recs.append({'surface': si, 'material': (p.object_path(mat) if isinstance(mat, int) and mat > 0 else
                                                      (p.full_path(mat) if isinstance(mat, int) and mat < 0 else mat)),
                          'brush_actor': p.object_path(act) if act > 0 else None, 'lighting_channels_raw': int(s['LightingChannels']), 'shadow_map_scale': float(s['ShadowMapScale']), 'poly_flags_raw': '0x%08X' % f, 'poly_flags': flags(f), 'nodes': st['nodes'], 'triangles': st['triangles'],
                          'collision': not bool(f & 0x8), 'rendered': not bool(f & (bsp.PF_INVISIBLE | bsp.PF_PORTAL))})
    elc = Counter(e['lightmap_type'] for e in elements)
    return {'level': lv, 'model': p.object_path(mi), 'points': len(M['points']), 'vectors': len(M['vectors']),
            'nodes': len(nodes), 'polygon_nodes': len(poly_nodes), 'surfaces': len(surfs),
            'triangles_all_polygon_nodes': tri_all, 'triangles_in_render_elements': tri_render,
            'model_components': len({e['component'] for e in elements}) + len(unparsed), 'unparsed_model_components': unparsed,
            'render_elements': len(elements),
            'elements_by_lightmap_type': {('texture lightmap (2)' if k == 2 else 'none (0) - no static light interactions'): v
                                          for k, v in elc.items()},
            'node_accounting': dict(acc), 'unaccounted_nodes': unacc,
            'materials': dict(Counter(e['material'] for e in elements)),
            'surfaces_detail': surf_recs,
            'elements': [{'component': e['component'], 'element': e['element'], 'material': e['material'], 'nodes': len(e['nodes']),
                          'lightmap_type': e['lightmap_type'], 'lightmap_textures': e['lightmap_textures'],
                          'shadowmaps': e['shadowmaps'], 'irrelevant_lights': e['irrelevant_lights']} for e in elements]}

def main():
    out = {'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/m04_bsp.py', 'levels': {lv: audit_level(lv) for lv in LEVELS}}
    mj = json.load(open(os.path.join(VS, 'Maps', MAP, 'map.json'), encoding='utf-8'))
    out['current_rebuild_export (map.json bsp)'] = mj.get('bsp')
    if MAP == 'MP_IAC_Streets':
        BL = bsp_level(MAP, LV_)
        a = out['levels'][BL]
        exp_tris = (mj.get('bsp') or {}).get(BL, {}).get('render_triangles')
    else:   # sum over every level carrying BSP (Seed: own ART + streamed MP_IAC_Global_Art_m; Debris: streamed MP_ORB_Art_m)
        ls = [v for v in out['levels'].values() if isinstance(v, dict) and v.get('triangles_in_render_elements') is not None]
        a = {'triangles_in_render_elements': sum(v['triangles_in_render_elements'] for v in ls),
             'triangles_all_polygon_nodes': sum(v.get('triangles_all_polygon_nodes') or 0 for v in ls),
             'unaccounted_nodes': [n for v in ls for n in v.get('unaccounted_nodes') or []]}
        exp_tris = sum((v or {}).get('render_triangles') or 0 for v in (mj.get('bsp') or {}).values())
    out['comparison'] = {
        'authored_render_triangles': a['triangles_in_render_elements'], 'authored_polygon_node_triangles': a['triangles_all_polygon_nodes'],
        'world_glb_bsp_triangles': exp_tris,
        'difference': (exp_tris - a['triangles_in_render_elements']) if exp_tris is not None else None,
        'unaccounted_nodes': len(a['unaccounted_nodes']),
        'verdict': None}
    c = out['comparison']
    c['verdict'] = ('BSP COMPLETE: every polygon node is rendered by a cooked element or is invisible/portal; the exported '
                    'triangle count equals the authored render triangles' if c['unaccounted_nodes'] == 0 and c['difference'] == 0
                    else 'BSP DIFFERENCE - see unaccounted_nodes / difference')
    write(map_out(MAP, 'streets_bsp_audit.json'), out)
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, dict))})
                      for k, v in out['levels'].items()}, indent=0)[:2500])
    print(json.dumps(c, indent=0))

if __name__ == '__main__':
    main()
