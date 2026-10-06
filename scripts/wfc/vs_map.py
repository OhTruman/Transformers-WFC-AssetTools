"""Vertical slice: one multiplayer map -> ExtractedAssets/VerticalSlice/Maps/<Map>/

  world.glb        BSP geometry (per-material primitives) + every placed static mesh
                   instanced as glTF nodes (meshes embedded once), PBR-approx materials
  collision.glb    blocking volumes (convex hulls) + solid BSP
  map.json         summary, sub-levels, coordinate convention, file list
  props.json       every placed mesh: object, mesh asset, glTF file, UE + glTF transforms
  collision.json   volumes with world-space polygons, collision flags of props
  spawnpoints.json player starts / pickups / objectives / spawn clusters (+ props)
  lights.json      light actors (if any)
  materials.json   resolved material descriptions used by this map
"""
import json, os, re, sys
from collections import Counter, defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, props, extract, bsp, materials, smsections  # noqa: E402
from vs_common import *  # noqa: E402,F401

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
GAMEPLAY = re.compile(r'(PlayerStart|PickupFactory|CapturePoint|DominationPoint|BombPlantPoint|KingOfTheHill|'
                      r'SpawnCluster|SpawnPoint|ForcedDir|Objective|PlayerSpawn|RespawnHelper|TriggerVolume|Flag)', re.I)
VOLUME = re.compile(r'(Volume|KingOfTheHillZone)$')

def sublevels():
    """Levels of MAP: every cooked <MAP>_*_m package, plus every package named by a LevelStreaming* object of those levels
    (authored.db) - catches shared streamed levels such as MP_IAC_Global_Art_m / GLB_Audio_m that do not carry the map prefix."""
    names = [os.path.splitext(n)[0] for n in os.listdir(extract.COOKED)]
    lv = {n for n in names if n.lower().startswith(MAP.lower() + '_') and n.lower().endswith('_m')}
    try:
        import authored as _A
        cooked = {n.lower(): n for n in names}
        for p in list(lv):
            for (o,) in _A.con().execute("SELECT opath FROM objects WHERE opath >= ? AND opath < ? AND class LIKE 'LevelStreaming%'",
                                         (p + '.', p + '/')).fetchall():
                v = _A.values(o)
                pk = [v.get('PackageName')] + [x.get('LevelName') for x in v.get('Levels') or [] if isinstance(x, dict)]
                lv |= {cooked[x.lower()] for x in pk if x and x.lower() in cooked}
    except Exception:
        pass
    return sorted(lv)

class Level:
    def __init__(self, name):
        self.name = name
        self.p = ue3pkg.Package(os.path.join(extract.COOKED, name + '.xxx'))
        self.pr = props.PropReader(self.p)
        self.cls = [self.p.class_name(e) for e in self.p.exports]
        self.children = defaultdict(list)
        for i, e in enumerate(self.p.exports):
            self.children[e['outer']].append(i + 1)
        self.path_index = {self.p.object_path(i + 1).lower(): i + 1 for i in range(len(self.p.exports))}
        self._c = {}
        self.level = next((i + 1 for i, c in enumerate(self.cls) if c == 'Level'), None)

    def own(self, i):
        if i not in self._c:
            try: self._c[i] = props.props_dict(self.pr.read_object(i)[0])
            except Exception: self._c[i] = None
        return self._c[i]

    def P(self, i, depth=0):
        own = self.own(i)
        if own is None: return {}
        a = self.p.exports[i - 1]['archetype']
        if a > 0 and depth < 8:
            m = dict(self.P(a, depth + 1)); m.update(own); return m
        return own

    def idx(self, ref):
        return self.path_index.get((ref or '').lower())

    def actors(self):
        return [a for a in self.children.get(self.level, []) if not self.cls[a - 1].endswith('Component')]

def ref(v): return v.get('ref') if isinstance(v, dict) else None

def scalar_props(d):
    out = {}
    for k, v in d.items():
        if isinstance(v, (int, float, str, bool)) and k not in ('CreationTime',): out[k] = v
        elif isinstance(v, dict) and 'ref' in v: out[k] = v['ref']
        elif isinstance(v, list) and len(v) in (3, 4) and all(isinstance(x, (int, float)) for x in v): out[k] = v
    return out

def actor_matrix(d):
    return ue_actor_matrix(d.get('Location', (0, 0, 0)), d.get('Rotation', (0, 0, 0)), d.get('DrawScale', 1.0),
                           d.get('DrawScale3D', (1, 1, 1)), d.get('PrePivot', (0, 0, 0)))

def cooked_shape(v):
    """effective authored values (authored.values) -> the cooked-property shapes vs_map reads (refs, xyz / pyr tuples)."""
    out = {}
    xyz = lambda d, ks: [d.get(k, 0) for k in ks] if isinstance(d, dict) else d
    if isinstance(v.get('StaticMesh'), str): out['StaticMesh'] = {'ref': v['StaticMesh']}
    if v.get('Scale') is not None: out['Scale'] = v['Scale']
    if v.get('Scale3D') is not None: out['Scale3D'] = xyz(v['Scale3D'], 'XYZ')
    if v.get('Translation') is not None: out['Translation'] = xyz(v['Translation'], 'XYZ')
    if v.get('Rotation') is not None: out['Rotation'] = xyz(v['Rotation'], ('Pitch', 'Yaw', 'Roll'))
    if isinstance(v.get('Materials'), list): out['Materials'] = [{'ref': m} if isinstance(m, str) else None for m in v['Materials']]
    return out

def component_matrix(c):
    s = c.get('Scale', 1.0); s3 = c.get('Scale3D', (1, 1, 1))
    return ue_scale([s * x for x in s3]) @ ue_rot(*c.get('Rotation', (0, 0, 0))) @ ue_trans(c.get('Translation', (0, 0, 0)))

# --------------------------------------------------------------------------------- main
VREMAP = {}

def main():
    A = materials.assets()
    # Baked-lightmap bindings (from vs_lightmap.py), keyed by component object path.
    lm_by_comp = {}
    _lmp = os.path.join(OUT, 'lightmaps.json')
    if os.path.exists(_lmp):
        for r in json.load(open(_lmp, encoding='utf-8')).get('props', []):
            if r.get('component'):
                lm_by_comp[r['component'].lower()] = r
    def lm_extras(extras, comp_ref):
        r = lm_by_comp.get((comp_ref or '').lower())
        if r:
            extras['lm_atlas'] = r['atlas']
            extras['lm_scale'] = r['coordScale']
            extras['lm_bias'] = r['coordBias']
            extras['lm_scalevec'] = r.get('scaleVec', [1.0, 1.0, 1.0])   # HDR coeff-0 scale
        return extras
    os.makedirs(OUT, exist_ok=True)
    glb = GLB('AssetTools vs_map (WFC %s)' % MAP)
    col = GLB('AssetTools vs_map collision')
    mat_cache, mats_used = {}, {}
    slot_source_by_key = {}
    _sec_cache = {}
    def find_sections(pkg, mop):
        """(package, sections) from the prop's own sublevel, else another package of this map
        (streamed sublevels reference meshes cooked into the persistent BASE package)."""
        k = (pkg, mop)
        if k not in _sec_cache:
            _sec_cache[k] = (None, None)
            if pkg and mop:
                for cand in [pkg] + [n for n in sublevels() if n != pkg]:
                    r = smsections.sections(cand, mop)
                    if r:
                        _sec_cache[k] = (cand, r); break
        return _sec_cache[k]
    def secmats(pkg, mop):
        r = find_sections(pkg, mop)[1]
        return [x['material'] for x in r] if r else None

    def material_index(g, opath, cache):
        key = opath or '<none>'
        if key in cache: return cache[key]
        r = materials.resolve(opath) if opath else {'roles': {}, 'blend_mode': 'BLEND_Opaque', 'two_sided': False}
        if opath: mats_used[opath] = r
        m = pbr_material((opath or 'WFC_Default').rsplit('.', 1)[-1], r.get('roles', {}), OUT,
                         extras={'wfc_material': opath, 'blend_mode': r.get('blend_mode')},
                         double_sided=r.get('two_sided', False), blend=BLEND.get(r.get('blend_mode'), 'OPAQUE'))
        cache[key] = g.material(key, bind_textures(g, m))
        return cache[key]

    levels = [Level(n) for n in sublevels()]
    global VREMAP
    _vr = os.path.join(OUT, 'vertex_remap.json')            # written by vs_vertex_remap.py (absent / empty on most maps)
    VREMAP = (json.load(open(_vr, encoding='utf-8')).get('meshes') or {}) if os.path.exists(_vr) else {}
    summary = {'map': MAP, 'sublevels': [], 'coordinate_system': 'glTF Y-up metres; v_gltf = 0.01*(x,z,y)_UE (umodel convention)'}
    props_out, spawns, lights, vols, decals, emitters, other = [], [], [], [], [], [], Counter()
    bsp_stats = {}
    mesh_cache = {}

    # ---------------- BSP
    for L in levels:
        models = [i + 1 for i, c in enumerate(L.cls) if c == 'Model' and L.p.exports[i]['outer'] == L.level]
        best = None
        for mi in models:
            try:
                M = bsp.read_model(L.p, mi)
                if best is None or len(M['nodes']) > len(best[1]['nodes']): best = (mi, M)
            except Exception as ex:
                bsp_stats.setdefault(L.name, {})['error'] = repr(ex)
        if not best or not len(best[1]['nodes']):
            bsp_stats[L.name] = {'nodes': 0}; continue
        mi, M = best
        by_mat = defaultdict(lambda: {'p': [], 'n': [], 'uv': []})
        col_tris = []
        skipped = Counter()
        for si, pts, node in bsp.polygons(M):
            s = M['surfs'][si]; flags = int(s['PolyFlags'])
            mref = int(s['Material'])
            mpath = (L.p.object_path(mref) if mref > 0 else L.p.full_path(mref)) if mref else None
            normal = M['vectors'][int(s['vNormal'])]
            base = M['points'][int(s['pBase'])]; tu = M['vectors'][int(s['vTextureU'])]; tv = M['vectors'][int(s['vTextureV'])]
            gp = ue_points_to_gltf(pts); gn = ue_points_to_gltf([normal])[0] * 100
            tris = [(0, k, k + 1) for k in range(1, len(pts) - 1)]
            a, b, c = gp[0], gp[1], gp[2]
            if np.dot(np.cross(b - a, c - a), gn) < 0: tris = [(t[0], t[2], t[1]) for t in tris]
            if not flags & bsp.PF_NOTSOLID:
                col_tris += [gp[list(t)] for t in tris]
            if flags & (bsp.PF_INVISIBLE | bsp.PF_PORTAL):
                skipped['invisible_or_portal'] += 1; continue
            uv = np.stack([((pts - base) @ tu) / 128.0, ((pts - base) @ tv) / 128.0], 1)
            bucket = by_mat[mpath]
            for t in tris:
                for k in t:
                    bucket['p'].append(gp[k]); bucket['n'].append(gn / (np.linalg.norm(gn) or 1)); bucket['uv'].append(uv[k])
        prims = []
        tri_total = 0
        for mpath, bk in by_mat.items():
            P = np.array(bk['p'], 'f4'); N = np.array(bk['n'], 'f4'); UV = np.array(bk['uv'], 'f4')
            idx = np.arange(len(P), dtype='u4')
            prims.append({'attributes': {'POSITION': glb.acc(P, 'VEC3', True, 34962), 'NORMAL': glb.acc(N, 'VEC3', target=34962),
                                         'TEXCOORD_0': glb.acc(UV, 'VEC2', target=34962)},
                          'indices': glb.acc(idx, 'SCALAR', target=34963), 'material': material_index(glb, mpath, mat_cache)})
            tri_total += len(P) // 3
        mesh = glb.mesh('BSP_' + L.name, prims)
        glb.node({'name': 'BSP_' + L.name, 'mesh': mesh, 'extras': {'source': L.p.object_path(mi), 'kind': 'bsp'}})
        if col_tris:
            CT_ = np.array(col_tris, 'f4').reshape(-1, 3)
            cm = col.mesh('BSPCollision_' + L.name, [{'attributes': {'POSITION': col.acc(CT_, 'VEC3', True, 34962)}}])
            col.node({'name': 'BSPCollision_' + L.name, 'mesh': cm, 'extras': {'kind': 'bsp_solid'}})
        bsp_stats[L.name] = {'model': L.p.object_path(mi), 'nodes': int(len(M['nodes'])), 'surfaces': int(len(M['surfs'])),
                             'points': int(len(M['points'])), 'render_triangles': int(tri_total),
                             'collision_triangles': len(col_tris), 'materials': len(by_mat), 'skipped_polys': dict(skipped),
                             'validation_issues': bsp.validate(M)}

    # ---------------- actors
    def mesh_node(mesh_op, overrides, ue_matrix, name, extras, pkg=None):
        a = A.get((mesh_op or '').lower())
        gl = next((o for o in (a or {}).get('extracted', []) if o.endswith('.gltf')), None) if a else None
        if not gl and a and mesh_op:   # authored.db 'extracted' can be stale for meshes extracted later: use the content path
            cand = os.path.join('content', *mesh_op.split('.')) + '.gltf'
            if os.path.exists(os.path.join(ROOT, cand)): gl = cand.replace(os.sep, '/')
        if not gl: return None, 'mesh not extracted'
        key = (mesh_op, tuple(overrides), pkg)
        if key not in mesh_cache:
            g, bins = load_gltf(os.path.join(ROOT, gl))
            # Section materials: authoritative = the FStaticMeshElement array of the copy cooked
            # into THIS map package (smsections.py).  umodel glTF names are short and ambiguous
            # (e.g. 4 packages define 'SideSupport_MATINST'), so the global assets.json guess is
            # only a fallback.
            src, secs = find_sections(pkg, mesh_op)
            if secs:
                slot_refs = [x['material'] for x in secs]
                slot_source_by_key[key] = 'cooked FStaticMeshElement (%s)' % src
            else:
                slot_refs = []
                for k, m in enumerate((a or {}).get('materials', []) or []):
                    slot_refs.append(m.get('ref') if isinstance(m, dict) else None)
                slot_source_by_key[key] = 'assets.json short-name resolution (fallback)'
            prims = []
            vrm = (VREMAP.get(mesh_op) or {}).get('primitives')
            for pi_, pr in enumerate(g['meshes'][0]['primitives']):
                at = pr['attributes']; attrs = {}
                if g['accessors'][at['POSITION']]['count'] == 0 or g['accessors'][pr['indices']]['count'] == 0:
                    continue                       # empty LOD section
                attrs['POSITION'] = glb.acc(accessor(g, bins, at['POSITION']).astype('f4'), 'VEC3', True, 34962)
                if 'NORMAL' in at: attrs['NORMAL'] = glb.acc(accessor(g, bins, at['NORMAL']).astype('f4'), 'VEC3', target=34962)
                if 'TEXCOORD_0' in at: attrs['TEXCOORD_0'] = glb.acc(accessor(g, bins, at['TEXCOORD_0']).astype('f4'), 'VEC2', target=34962)
                if 'TEXCOORD_1' in at: attrs['TEXCOORD_1'] = glb.acc(accessor(g, bins, at['TEXCOORD_1']).astype('f4'), 'VEC2', target=34962)  # lightmap UV
                if vrm and pi_ < len(vrm) and len(vrm[pi_]) == g['accessors'][at['POSITION']]['count']:
                    # cooked LOD0 vertex index per vertex (vertex_remap.json): only meshes whose glTF splits shared vertices
                    attrs['_WFC_SRCVERT'] = glb.acc(np.array(vrm[pi_], dtype='u4'), 'SCALAR', target=34962)
                ind = accessor(g, bins, pr['indices']).astype('u4')
                slot = pr.get('material', 0)
                mop = overrides[slot] if slot < len(overrides) and overrides[slot] else (slot_refs[slot] if slot < len(slot_refs) else None)
                prims.append({'attributes': attrs, 'indices': glb.acc(ind, 'SCALAR', target=34963),
                              'material': material_index(glb, mop, mat_cache)})
            if not prims:
                mesh_cache[key] = (None, gl)
            else:
                mesh_cache[key] = (glb.mesh(mesh_op.rsplit('.', 1)[-1], prims), gl)
        mi, gl = mesh_cache[key]
        if mi is None: return gl, 'mesh has no geometry'
        glb.node({'name': name, 'mesh': mi, 'matrix': ue_to_gltf_matrix(ue_matrix), 'extras': extras})
        return gl, None

    for L in levels:
        for a in L.actors():
            c = L.cls[a - 1]; nm = L.p.exports[a - 1]['name']
            d = L.P(a)
            loc = d.get('Location', [0, 0, 0])
            rec_base = {'sublevel': L.name, 'actor': nm, 'class': c}
            # static mesh actors (+ interp / destructible movers)
            comp_refs = [ref(d.get(k)) for k in ('StaticMeshComponent', 'CollisionComponent', 'SkeletalMeshComponent')]
            if c == 'StaticMeshCollectionActor':
                comps = [ref(x) for x in (d.get('StaticMeshComponents') or [])]
                e = L.p.exports[a - 1]
                _, used = L.pr.read_object(a)
                raw = L.p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
                mats = np.frombuffer(raw[:64 * len(comps)], '>f4').reshape(-1, 4, 4).astype('f8') if len(raw) >= 64 * len(comps) else None
                for k, cr in enumerate(comps):
                    ci = L.idx(cr)
                    cd = L.P(ci) if ci else {}
                    if not cd.get('StaticMesh') and isinstance(cr, str):
                        # component serialized without StaticMesh (Rust): mesh + Scale/Scale3D/Rotation/Translation live on the
                        # archetype chain -> fill the missing keys from the effective authored values
                        try:
                            import authored as AU
                            cd = {**cooked_shape(AU.values(cr) or {}), **cd}
                        except Exception: pass
                    mop = ref(cd.get('StaticMesh'))
                    ov = [ref(x) for x in (cd.get('Materials') or [])]
                    if mats is None: other['smca_without_matrices'] += 1; continue
                    # UE3 UPrimitiveComponent::SetTransformedToWorld (RE: 0x82DC3508): the component's own
                    # S(Scale*Scale3D) * R(Rotation) * T(Translation) is applied on top of the serialized
                    # CachedParentToWorld. In Streets the native matrices are pure rotation+translation; all
                    # per-instance (non-uniform / negative) scale lives in the component. Row-vector order.
                    M = component_matrix(cd) @ mats[k]
                    gl, err = mesh_node(mop, ov, M, '%s.%d' % (nm, k), lm_extras({'actor': nm, 'class': c, 'component': cr, 'mesh': mop}, cr), pkg=L.name)
                    props_out.append(dict(rec_base, component=cr, mesh=mop, gltf=gl, material_overrides=ov,
                                          ue_matrix=M.tolist(), gltf_matrix=ue_to_gltf_matrix(M), error=err, section_materials=secmats(L.name, mop),
                                          collide=cd.get('CollideActors', True), block=cd.get('BlockActors', True),
                                          transform_source='component S(Scale*Scale3D)*R*T x StaticMeshCollectionActor native CachedParentToWorld'))
                continue
            smc = ref(d.get('StaticMeshComponent')) or (ref(d.get('CollisionComponent')) if c in ('StaticMeshActor', 'InterpActor', 'StaticInterpActor') else None)
            if c in ('StaticMeshActor', 'InterpActor', 'StaticInterpActor', 'TnStaticDestructibleActor') or (smc and 'StaticMesh' in L.cls[(L.idx(smc) or 1) - 1]):
                ci = L.idx(smc) if smc else None
                cd = L.P(ci) if ci else {}
                mop = ref(cd.get('StaticMesh'))
                if not mop:
                    # destructibles / movers may hold the mesh elsewhere: search child components
                    for j in L.children.get(a, []):
                        if 'StaticMeshComponent' in L.cls[j - 1]:
                            cd = L.P(j); mop = ref(cd.get('StaticMesh'))
                            if mop: break
                if mop:
                    M = component_matrix(cd) @ actor_matrix(d)
                    ov = [ref(x) for x in (cd.get('Materials') or [])]
                    gl, err = mesh_node(mop, ov, M, nm, lm_extras({'actor': nm, 'class': c, 'mesh': mop}, smc), pkg=L.name)
                    props_out.append(dict(rec_base, mesh=mop, gltf=gl, material_overrides=ov, archetype=None,
                                          location_ue=loc, rotation_ue=d.get('Rotation', [0, 0, 0]),
                                          draw_scale=d.get('DrawScale', 1.0), draw_scale_3d=d.get('DrawScale3D', [1, 1, 1]),
                                          ue_matrix=M.tolist(), gltf_matrix=ue_to_gltf_matrix(M), error=err, section_materials=secmats(L.name, mop),
                                          dynamic=c in ('InterpActor', 'TnStaticDestructibleActor'),
                                          collide=cd.get('CollideActors', True), block=cd.get('BlockActors', True),
                                          transform_source='actor Location/Rotation/DrawScale x component'))
                    continue
            if 'Light' in c and c not in ('LightsVisibilitiesVolume',):
                lc = {}
                for k, v in d.items():
                    if isinstance(v, dict) and 'LightComponent' in str(v.get('class', '')):
                        li = L.idx(v['ref']); lc = L.P(li) if li else {}
                lights.append(dict(rec_base, location_ue=loc, location_gltf=ue_points_to_gltf([loc])[0].tolist(),
                                   rotation_ue=d.get('Rotation', [0, 0, 0]), light=scalar_props(lc)))
                continue
            if VOLUME.search(c) or c == 'BRUSH':
                # UE names are case-insensitive: the name table may spell it 'BRUSH'
                bref = next((v for k, v in d.items() if k.lower() == 'brush'), None)
                bi = L.idx(ref(bref))
                polys = []
                if bi:
                    try:
                        BM = bsp.read_model(L.p, bi)
                        Mw = actor_matrix(d)
                        for si, pts, node in bsp.polygons(BM):
                            w = (np.c_[pts, np.ones(len(pts))] @ Mw)[:, :3]
                            polys.append(ue_points_to_gltf(w).round(4).tolist())
                    except Exception as ex:
                        other['volume_parse_error'] += 1
                if c == 'BRUSH':
                    other['BRUSH (builder brushes; geometry lives in level BSP)'] += 1; continue
                blocking = 'Blocking' in c
                v = dict(rec_base, location_ue=loc, polygons_gltf=polys, polygon_count=len(polys),
                         blocking=blocking, props=scalar_props(d))
                vols.append(v)
                if polys and blocking:
                    tri = []
                    for poly in polys:
                        for k in range(1, len(poly) - 1): tri += [poly[0], poly[k], poly[k + 1]]
                    cm = col.mesh(nm, [{'attributes': {'POSITION': col.acc(np.array(tri, 'f4'), 'VEC3', True, 34962)}}])
                    col.node({'name': nm, 'mesh': cm, 'extras': {'kind': c}})
                if GAMEPLAY.search(c):
                    spawns.append(dict(rec_base, location_ue=loc, location_gltf=ue_points_to_gltf([loc])[0].tolist(),
                                       volume=True, props=scalar_props(d)))
                continue
            if GAMEPLAY.search(c):
                rot = d.get('Rotation', [0, 0, 0])
                spawns.append(dict(rec_base, location_ue=loc, location_gltf=ue_points_to_gltf([loc])[0].tolist(),
                                   rotation_ue=rot, yaw_deg=round(rot[1] * 360 / 65536.0, 3), props=scalar_props(d)))
                continue
            if c == 'DecalActor':
                dc = {}
                for k, v in d.items():
                    if isinstance(v, dict) and 'Decal' in str(v.get('class', '')):
                        di = L.idx(v['ref']); dc = L.P(di) if di else {}
                decals.append(dict(rec_base, location_ue=loc, rotation_ue=d.get('Rotation'),
                                   material=ref(dc.get('DecalMaterial')), width=dc.get('Width'), height=dc.get('Height')))
                continue
            if c == 'Emitter':
                pc = L.idx(ref(d.get('ParticleSystemComponent')))
                emitters.append(dict(rec_base, location_ue=loc, template=ref((L.P(pc) if pc else {}).get('Template'))))
                continue
            other[c] += 1

    glb.write(os.path.join(OUT, 'world.glb'))
    col.write(os.path.join(OUT, 'collision.glb'))
    json.dump({'map': MAP, 'count': len(props_out), 'props': props_out, 'decals': decals, 'emitters': emitters},
              open(os.path.join(OUT, 'props.json'), 'w'), indent=0)
    json.dump({'map': MAP, 'note': 'BSP solid surfaces are collision (collision.glb BSPCollision_*); volumes are convex hulls '
                                   'in glTF space; static-mesh collision: use render mesh where collide/block true '
                                   '(simple collision bodies not extracted)',
               'volumes': vols, 'prop_collision_flags': [{k: p.get(k) for k in ('actor', 'mesh', 'collide', 'block')} for p in props_out]},
              open(os.path.join(OUT, 'collision.json'), 'w'), indent=0)
    sp_counts = Counter(s['class'] for s in spawns)
    json.dump({'map': MAP, 'counts': dict(sp_counts), 'points': spawns}, open(os.path.join(OUT, 'spawnpoints.json'), 'w'), indent=0)
    json.dump({'map': MAP, 'count': len(lights), 'lights': lights,
               'note': 'static lighting is baked into lightmaps (not extracted); few/no dynamic light actors'},
              open(os.path.join(OUT, 'lights.json'), 'w'), indent=0)
    json.dump(mats_used, open(os.path.join(OUT, 'materials.json'), 'w'), indent=0, default=list)
    summary.update({'sublevels': [L.name for L in levels], 'bsp': bsp_stats,
                    'placed_props': len(props_out), 'unique_meshes': len(mesh_cache),
                    'props_missing_mesh': sum(1 for p in props_out if p.get('error')),
                    'spawn_and_gameplay_points': dict(sp_counts), 'volumes': len(vols), 'lights': len(lights),
                    'decals': len(decals), 'emitters': len(emitters), 'unhandled_actor_classes': dict(other),
                    'materials': len(mats_used),
                    'files': {k: k for k in ('world.glb', 'collision.glb', 'props.json', 'collision.json',
                                             'spawnpoints.json', 'lights.json', 'materials.json')}})
    json.dump(summary, open(os.path.join(OUT, 'map.json'), 'w'), indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != 'files'}, indent=1, default=str))

if __name__ == '__main__':
    main()
