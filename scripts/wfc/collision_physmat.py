"""Per-triangle PhysicalMaterial for the MP weapon collision world (package 7; Integration + Systems 2026-10-18).

collision_weapon.glb (ExtractedAssets, zero-extent traces = weapon / hitscan; vs_physics.py) stays untouched. This writes a sibling
AssetTools/manifests/maps/<MAP>/collision_weapon_physmat.json:
  { map, glb, glb_sha256, engine_default_physmat, physmats: ["", ...] (0 = none / engine default),
    meshes: { "<glb mesh index>": { name, kind, source_mesh / level / volume, triangles, runs: [[first_tri, count, physmat_index, rule]] } },
    node_overrides: { "<glb node index>": physmat_index }   (component PhysMaterialOverride, which wins in UE3; none authored so far),
    unresolved: [ {mesh, run, rule} ] -> these triangles get the engine default (DefaultPhysMaterialName) }
Every triangle of every mesh is covered by exactly one run (checked). Rules (the `rule` field per run):
  section_material      per-poly mesh: the section material's PhysMaterial through the MIC parent chain (physics.json sections)
  body_setup            simple hull: the StaticMesh BodySetup's PhysMaterial
  first_material        simple hull without a BodySetup PhysMaterial, owner IsA StaticMeshActor: the first material slot WITH a
                        PhysMaterial (CONFIRMED, RE CAMPAIGN_PROVISIONALS_CLOSED_RE.md a509740, resolver 0x82C88168). Applied as a NODE
                        OVERRIDE, because the fallback depends on the owner class, not the mesh
  hull_default          simple hull without a BodySetup PhysMaterial whose owner is NOT a StaticMeshActor (StaticMeshCollectionActor
                        members, movers ...): no fallback -> engine default (CONFIRMED, same source). The mesh-level run for such hulls
  bsp_surface_material  BSP: the surface material's PhysMaterial; triangle order replayed from vs_map's polygon walk and checked
                        position-for-position against the shipped BSPCollision mesh
  volume                blocking volume: the volume's own PhysMaterial if authored, else none
  none                  nothing authored -> engine default
Reads physics.json (vs_physics), the cooked level BSP (vs_map's reader), authored.db. Read only on ExtractedAssets.

  python collision_physmat.py [--world pawn|weapon] <MAP> [...]
Campaign chapters (Integration 2026-10-18): run with WFC_VS_ROOT = the campaign VerticalSlice; both worlds (pawn = non-zero-extent
movement traces, weapon = zero-extent). Output name collision_<world>_physmat.json (MP default world = weapon, unchanged).
"""
import hashlib, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from vs_common import VS, ROOT, read_glb, load_gltf, accessor, ue_points_to_gltf  # noqa: E402
import authored as A  # noqa: E402

AT = os.path.dirname(os.path.dirname(HERE))

def bsp_order(level_name, mats_physmat):
    """replay vs_map's BSP collision triangles for one level -> list of (n_tris, physmat, material) runs + all positions"""
    import bsp
    from vs_map import Level
    L = Level(level_name)
    models = [i + 1 for i, c in enumerate(L.cls) if c == 'Model' and L.p.exports[i]['outer'] == L.level]
    best = None
    for mi in models:
        try:
            M = bsp.read_model(L.p, mi)
            if best is None or len(M['nodes']) > len(best[1]['nodes']): best = (mi, M)
        except Exception: pass
    if not best: return [], np.zeros((0, 3))
    mi, M = best; runs = []; pts_all = []
    for si, pts, node in bsp.polygons(M):
        s = M['surfs'][si]; flags = int(s['PolyFlags'])
        if flags & bsp.PF_NOTSOLID: continue
        mref = int(s['Material'])
        mpath = (L.p.object_path(mref) if mref > 0 else L.p.full_path(mref)) if mref else None
        normal = M['vectors'][int(s['vNormal'])]
        gp = ue_points_to_gltf(pts); gn = ue_points_to_gltf([normal])[0] * 100
        tris = [(0, k, k + 1) for k in range(1, len(pts) - 1)]
        a, b, c = gp[0], gp[1], gp[2]
        if np.dot(np.cross(b - a, c - a), gn) < 0: tris = [(t[0], t[2], t[1]) for t in tris]
        pm = mats_physmat.get(mpath) if mpath else None
        if runs and runs[-1][1] == pm and runs[-1][2] == mpath: runs[-1][0] += len(tris)
        else: runs.append([len(tris), pm, mpath])
        for t in tris: pts_all.append(gp[list(t)])
    return runs, (np.array(pts_all, 'f4').reshape(-1, 3) if pts_all else np.zeros((0, 3)))

def run(M, world='weapon'):
    md = os.path.join(VS, 'Maps', M); gp = os.path.join(md, 'collision_%s.glb' % world)
    j, bins = read_glb(gp); sha = hashlib.sha256(open(gp, 'rb').read()).hexdigest()
    phys = json.load(open(os.path.join(md, 'physics.json'), encoding='utf-8'))
    default = (A.values('Engine.Default__Engine') or {}).get('DefaultPhysMaterialName')
    table = ['']; ix = {'': 0}
    def pidx(p):
        p = p or ''
        if p not in ix: ix[p] = len(table); table.append(p)
        return ix[p]
    mesh_src = {}
    for ni, n in enumerate(j['nodes']):
        if 'mesh' in n: mesh_src.setdefault(n['mesh'], (n.get('name'), n.get('extras') or {}))
    vols = {v['actor']: v for v in phys.get('volumes') or []}
    out = {}; unresolved = []; bsp_checks = {}; hull_fm = {}
    for mi, m in enumerate(j['meshes']):
        pr = m['primitives'][0]
        P = accessor(j, bins, pr['attributes']['POSITION'])
        ntri = (j['accessors'][pr['indices']]['count'] if 'indices' in pr else len(P)) // 3
        nm, ex = mesh_src.get(mi, (m.get('name'), {})); kind = ex.get('kind', ''); runs = []; rec = {'name': m.get('name'), 'kind': kind, 'triangles': ntri}
        if m.get('name', '').startswith('BSPCollision_'):
            lv = m['name'][len('BSPCollision_'):]
            rr, pts = bsp_order(lv, phys.get('bsp_material_physmats') or {})
            Pm = P.astype('f4') if 'indices' not in pr else P[accessor(j, bins, pr['indices'])].astype('f4')
            ok = len(pts) == len(Pm) and (len(pts) == 0 or float(np.abs(pts - Pm).max()) < 1e-3)
            bsp_checks[lv] = {'replayed_triangles': len(pts) // 3, 'glb_triangles': ntri, 'positions_match': ok}
            first = 0
            for n_, pm, mat in rr:
                runs.append([first, n_, pidx(pm), 'bsp_surface_material' if pm else 'none']); first += n_
                if not pm: unresolved.append({'mesh': mi, 'first_tri': first - n_, 'count': n_, 'rule': 'bsp_surface_material', 'material': mat})
            rec['level'] = lv
        elif kind in vols or m.get('name') in vols:
            v = vols.get(m.get('name')) or vols.get(kind); pm = (v or {}).get('phys_material')
            pm = pm if pm and pm != 'None' else None
            runs.append([0, ntri, pidx(pm), 'volume' if pm else 'none']); rec['volume'] = m.get('name')
            if not pm: unresolved.append({'mesh': mi, 'first_tri': 0, 'count': ntri, 'rule': 'volume', 'volume': m.get('name')})
        elif kind in ('prop_simple', 'prop_per_poly'):
            src = phys['meshes'].get(ex.get('mesh')) or {}; rec['source_mesh'] = ex.get('mesh')
            secs = src.get('sections') or []
            if kind == 'prop_simple':
                bs = (src.get('simple') or {}).get('phys_material')
                if bs: runs.append([0, ntri, pidx(bs), 'body_setup'])
                else:
                    # mesh-level run = the non-StaticMeshActor result (engine default); StaticMeshActor owners get first_material via
                    # node_overrides (below)
                    fm = next((s.get('phys_material') for s in secs if s.get('phys_material')), None)
                    runs.append([0, ntri, 0, 'hull_default'])
                    rec['first_material_physmat'] = fm
                    hull_fm[mi] = fm
            else:
                # replay vs_physics: the umodel glTF's primitives in order, skipping sections with EnableCollision false; a primitive's
                # material index is the section index
                gl = next((p.get('gltf') for p in phys.get('props') or [] if p.get('mesh') == ex.get('mesh') and p.get('gltf')), None)
                en = {s['index']: s.get('enable_collision', True) for s in secs}; sec = {s['index']: s for s in secs}
                first = 0
                if gl and os.path.exists(os.path.join(ROOT, gl)):
                    gg, gb = load_gltf(os.path.join(ROOT, gl))
                    for prm in gg['meshes'][0]['primitives']:
                        k = prm.get('material', 0)
                        if not en.get(k, True) or 'indices' not in prm: continue
                        if not len(accessor(gg, gb, prm['attributes']['POSITION'])): continue
                        n_ = gg['accessors'][prm['indices']]['count'] // 3
                        s = sec.get(k) or {}; pm = s.get('phys_material')
                        rule = 'section_material' if pm else ('none' if s else 'none (section not decoded in physics.json)')
                        runs.append([first, n_, pidx(pm), rule])
                        if not pm: unresolved.append({'mesh': mi, 'first_tri': first, 'count': n_, 'rule': rule, 'material': s.get('material'), 'source_mesh': ex.get('mesh')})
                        first += n_
        elif kind == '':
            runs.append([0, ntri, 0, 'unreferenced (no node uses this mesh)'])
        else:
            runs.append([0, ntri, 0, 'none']); unresolved.append({'mesh': mi, 'first_tri': 0, 'count': ntri, 'rule': 'unknown kind ' + kind})
        cov = sum(r[1] for r in runs)
        rec['runs'] = runs; rec['coverage_ok'] = cov == ntri
        if cov != ntri: rec['coverage'] = cov
        out[str(mi)] = rec
    overrides = {}; override_rules = {}
    # owner class of each prop node (props.json: actor -> class) and IsA StaticMeshActor through the authored class chain
    pj = os.path.join(md, 'props.json')
    owner = {p['actor']: (p['class'], p.get('component')) for p in json.load(open(pj, encoding='utf-8'))['props']} if os.path.exists(pj) else {}
    isa_cache = {}
    def isa_sma(actor):
        cls, comp = owner.get(actor, (None, None))
        if cls not in isa_cache:
            chain = A.chain(comp.rsplit('.', 1)[0]) if comp and cls != 'StaticMeshCollectionActor' else []
            isa_cache[cls] = any(c.get('class') == 'StaticMeshActor' for c in chain or []) or cls == 'StaticMeshActor'
        return isa_cache[cls], cls
    by_owner = {}
    for ni, n in enumerate(j['nodes']):
        ex = n.get('extras') or {}
        if not ex.get('mesh'): continue
        done = False
        for p in phys.get('props') or []:
            if p.get('actor') == n.get('name') and p.get('mesh') == ex['mesh'] and (p.get('flags') or {}).get('PhysMaterialOverride'):
                overrides[str(ni)] = pidx(p['flags']['PhysMaterialOverride']); override_rules[str(ni)] = 'component_override'; done = True; break
        if done or n.get('mesh') not in hull_fm: continue
        sma, cls = isa_sma(n.get('name'))
        ntri = out[str(n['mesh'])]['triangles']; fm = hull_fm[n['mesh']]
        key = '%s (%s)' % (cls, 'IsA StaticMeshActor' if sma else 'not a StaticMeshActor')
        b = by_owner.setdefault(key, {'nodes': 0, 'triangles': 0, 'with_first_material': 0}); b['nodes'] += 1; b['triangles'] += ntri
        if sma and fm:
            overrides[str(ni)] = pidx(fm); override_rules[str(ni)] = 'first_material'; b['with_first_material'] += 1
        else:
            unresolved.append({'node': ni, 'mesh': n['mesh'], 'first_tri': 0, 'count': ntri, 'rule': 'hull_default', 'owner_class': cls,
                               'first_material_physmat_not_applied': fm})
    rep = {'map': M, 'generated_by': 'AssetTools/scripts/wfc/collision_physmat.py', 'glb': os.path.relpath(gp, os.path.dirname(AT)).replace(os.sep, '/'),
           'glb_sha256': sha, 'engine_default_physmat': default, 'physmats': table, 'meshes': out, 'node_overrides': overrides, 'node_override_rules': override_rules,
           'hull_nodes_by_owner_class': by_owner,
           'unresolved': unresolved,
           'checks': {'meshes': len(out), 'coverage_ok': sum(1 for r in out.values() if r['coverage_ok']), 'bsp': bsp_checks,
                      'triangles': sum(r['triangles'] for r in out.values()),
                      'triangles_unresolved': sum(u['count'] for u in unresolved if 'node' not in u),        # per mesh (runs)
                      'hull_default_node_triangles': sum(u['count'] for u in unresolved if 'node' in u),   # per placed node (instanced)
                      'runs_by_rule': {}}}
    for r in out.values():
        for x in r['runs']: rep['checks']['runs_by_rule'][x[3]] = rep['checks']['runs_by_rule'].get(x[3], 0) + x[1]
    od = os.path.join(AT, 'manifests', 'maps', M); os.makedirs(od, exist_ok=True)
    json.dump(rep, open(os.path.join(od, 'collision_%s_physmat.json' % world), 'w', encoding='utf-8'), indent=1)
    c = rep['checks']; print(M, json.dumps({k: c[k] for k in ('meshes', 'coverage_ok', 'triangles', 'triangles_unresolved', 'runs_by_rule')}),
                             'bsp', {k: (v['positions_match'], v['replayed_triangles'], v['glb_triangles']) for k, v in c['bsp'].items()}, 'physmats', len(table) - 1, flush=True)

if __name__ == '__main__':
    args = sys.argv[1:]; world = 'weapon'
    if args and args[0].startswith('--world'):
        world = args[0].split('=', 1)[1] if '=' in args[0] else args[1]; args = args[1:] if '=' in args[0] else args[2:]
    for M in args: run(M, world)
