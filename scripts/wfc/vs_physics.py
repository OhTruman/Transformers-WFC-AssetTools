"""Authored collision + physics setup of a map, from manifests/authored.db (authored.py) + cooked sections.

Outputs (ExtractedAssets/VerticalSlice/Maps/<MAP>/):
  physics.json         meshes (simple collision, flags, per-section EnableCollision + PhysMaterial), props (component
                       flags -> representation per trace type), volumes (per-trace blocking), physical materials,
                       world physics, movers/destructibles, slice character PhysicsAssets
  collision_pawn.glb   what blocks NON-ZERO-EXTENT traces (pawn/vehicle movement):
                       BSP solid + volumes with BlockNonZeroExtent + props with BlockActors&BlockNonZeroExtent,
                       each as its UE3 representation (simple hulls if UseSimpleBoxCollision and the mesh has
                       simple collision, else per-poly render geometry of sections with EnableCollision)
  collision_weapon.glb what blocks ZERO-EXTENT traces (hitscan/weapon line checks): same with BlockZeroExtent and
                       UseSimpleLineCollision
  (collision.glb from vs_collision.py is left unchanged for existing consumers.)

UE3 rules used (engine semantics; values CONFIRMED from data, rule HIGH CONFIDENCE):
  StaticMeshComponent line check: zero-extent -> simple if StaticMesh.UseSimpleLineCollision and BodySetup has
  geometry, else per-poly (kDOP over sections with EnableCollision); non-zero-extent -> same with
  UseSimpleBoxCollision. Rigid body -> UseSimpleRigidBodyCollision. A component participates only if
  CollideActors && BlockActors && Block{Zero,NonZero}Extent.
  python vs_physics.py [MAP]
"""
import json, os, re, sys
from collections import Counter, defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, smsections  # noqa: E402
from vs_common import ROOT, VS, GLB, read_glb, load_gltf, accessor, ue_points_to_gltf  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
OVERSIZE_DIAG_M = 2000.0
FLAGS = ('CollideActors', 'BlockActors', 'BlockZeroExtent', 'BlockNonZeroExtent', 'BlockRigidBody', 'BlockCameras',
         'bDisableAllRigidBody', 'RBChannel', 'PhysMaterialOverride', 'CanBlockCamera', 'bForceDirectLightMap')

def v3(d, keys=('X', 'Y', 'Z')): return np.array([float(d.get(k, 0.0)) for k in keys]) if isinstance(d, dict) else np.array(d, float)

def tm(m):
    """FMatrix (fixed row order, list of 16 or dict) -> 4x4 row-vector matrix (UE)."""
    if isinstance(m, dict): m = [m.get(k, 0.0) for k in sorted(m)]
    a = np.array(m, float).reshape(4, 4) if m is not None and len(m) == 16 else np.eye(4)
    return a

# ------------------------------------------------------------------ simple collision -> triangles (UE mesh space)
def box_tris(M, x, y, z):
    h = np.array([x, y, z]) / 2.0
    c = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], float) * h
    P = (np.c_[c, np.ones(8)] @ M)[:, :3]
    F = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return P, np.array(F)

def sphere_tris(M, r, length=0.0, seg=12, rings=6):
    pts, faces = [], []
    for i in range(rings + 1):
        th = np.pi * i / rings; zc = np.cos(th) * r + (length / 2 if i <= rings // 2 else -length / 2)
        for j in range(seg):
            ph = 2 * np.pi * j / seg; pts.append([np.sin(th) * np.cos(ph) * r, np.sin(th) * np.sin(ph) * r, zc])
    for i in range(rings):
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg; c, d = a + seg, b + seg
            faces += [(a, c, b), (b, c, d)]
    P = (np.c_[np.array(pts), np.ones(len(pts))] @ M)[:, :3]
    return P, np.array(faces)

def simple_geometry(agg):
    """KAggregateGeom -> (points UE, tris, summary)"""
    Ps, Fs, n = [], [], 0
    summ = {'convex': [], 'boxes': [], 'spheres': [], 'sphyls': []}
    for c in agg.get('ConvexElems') or []:
        V = np.array([v3(p) for p in c.get('VertexData') or []]); T = c.get('FaceTriData') or []
        if len(V) and len(T) >= 3:
            F = np.array(T[:len(T) // 3 * 3]).reshape(-1, 3)
            if F.max() < len(V):
                Ps.append(V); Fs.append(F + n); n += len(V)
        summ['convex'].append({'vertices': len(V), 'triangles': len(T) // 3,
                               'elem_box': c.get('ElemBox')})
    for b in agg.get('BoxElems') or []:
        P, F = box_tris(tm(b.get('TM')), b.get('X', 0), b.get('Y', 0), b.get('Z', 0)); Ps.append(P); Fs.append(F + n); n += len(P)
        summ['boxes'].append({k: b.get(k) for k in ('X', 'Y', 'Z')} | {'center_ue': tm(b.get('TM'))[3, :3].round(3).tolist()})
    for s in agg.get('SphereElems') or []:
        P, F = sphere_tris(tm(s.get('TM')), s.get('Radius', 0)); Ps.append(P); Fs.append(F + n); n += len(P)
        summ['spheres'].append({'radius': s.get('Radius'), 'center_ue': tm(s.get('TM'))[3, :3].round(3).tolist()})
    for s in agg.get('SphylElems') or []:
        P, F = sphere_tris(tm(s.get('TM')), s.get('Radius', 0), s.get('Length', 0)); Ps.append(P); Fs.append(F + n); n += len(P)
        summ['sphyls'].append({'radius': s.get('Radius'), 'length': s.get('Length'), 'center_ue': tm(s.get('TM'))[3, :3].round(3).tolist()})
    if not Ps: return None, None, summ
    return np.concatenate(Ps), np.concatenate(Fs), summ

# ------------------------------------------------------------------ physical materials
def phys_material(mat, depth=0):
    """material / MIC -> (PhysMaterial, the object that set it) walking the Parent chain"""
    if not mat or depth > 12: return None, None
    v = A.values(mat)
    if v.get('PhysMaterial'): return v['PhysMaterial'], mat
    return phys_material(v.get('Parent'), depth + 1)

from vs_common import map_sublevels  # noqa: E402

def main():
    subs = map_sublevels(MAP, A)   # name prefix + streamed sublevels (map.json)
    props = json.load(open(os.path.join(OUT, 'props.json'), encoding='utf-8'))['props']
    out = {'map': MAP, 'source': 'manifests/authored.db + cooked FStaticMeshElement sections', 'meshes': {}, 'props': [],
           'volumes': [], 'physical_materials': {}, 'world': {}, 'movers': [], 'destructibles': [], 'characters': {}, 'notes': []}
    pm_used = Counter()
    # ------------------------------------------------------------------ meshes
    def mesh_rec(mop, pkg):
        if mop in out['meshes']: return out['meshes'][mop]
        sm = A.get(mop) or {}; smv = A.values(mop)
        rec = {'mesh': mop, 'flags': {k: smv.get(k) for k in ('UseSimpleLineCollision', 'UseSimpleBoxCollision', 'UseSimpleRigidBodyCollision')},
               'flags_authored': sorted(k for k in (sm.get('props') or {}) if k.startswith('UseSimple')),
               'body_setup': smv.get('BodySetup'), 'simple': None, 'sections': []}
        bs = A.values(smv['BodySetup']) if smv.get('BodySetup') else {}
        P, F, summ = simple_geometry(bs.get('AggGeom') or {})
        rec['simple'] = {'elements': summ, 'has_geometry': P is not None, 'triangles': int(len(F)) if F is not None else 0,
                         'phys_material': bs.get('PhysMaterial'), 'body_setup_props': {k: v for k, v in bs.items() if k not in ('AggGeom',)}}
        rec['_simple_geom'] = (P, F)
        found = None
        for cand in [pkg] + [s for s in subs if s != pkg]:
            found = smsections.sections(cand, mop)
            if found: rec['sections_from'] = cand; break
        for s in found or []:
            pmat, pfrom = phys_material(s['material'])
            rec['sections'].append({'index': s['index'], 'material': s['material'], 'enable_collision': s['enable_collision'],
                                    'triangles': s['num_triangles'], 'phys_material': pmat, 'phys_material_from': pfrom})
        out['meshes'][mop] = rec
        return rec
    # ------------------------------------------------------------------ props
    for p in props:
        comp = p.get('component')
        if not comp:
            av = A.values(p['sublevel'] + '.TheWorld.PersistentLevel.' + p['actor'])
            comp = av.get('StaticMeshComponent') or av.get('CollisionComponent')
        cv = A.values(comp) if comp else {}
        m = mesh_rec(p['mesh'], p['sublevel']) if p.get('mesh') else None
        fl = {k: cv.get(k) for k in FLAGS if k in cv}
        coll = bool(cv.get('CollideActors')) and bool(cv.get('BlockActors'))
        simple = m and m['simple']['has_geometry']
        def rep(block_key, use_key):
            if not coll or not cv.get(block_key): return 'none'
            return 'simple' if (simple and m['flags'].get(use_key)) else 'per_poly'
        r = {'actor': p['actor'], 'sublevel': p['sublevel'], 'component': comp, 'mesh': p.get('mesh'), 'flags': fl,
             'pawn': rep('BlockNonZeroExtent', 'UseSimpleBoxCollision'), 'weapon': rep('BlockZeroExtent', 'UseSimpleLineCollision'),
             'rigid_body': ('simple' if simple and m['flags'].get('UseSimpleRigidBodyCollision') else 'per_poly')
                           if (coll and cv.get('BlockRigidBody') and not cv.get('bDisableAllRigidBody')) else 'none',
             'rb_collide_with': sorted(k for k, x in (cv.get('RBCollideWithChannels') or {}).items() if x is True),
             'gltf': p.get('gltf'), 'gltf_matrix': p.get('gltf_matrix')}
        if fl.get('PhysMaterialOverride'): pm_used[fl['PhysMaterialOverride']] += 1
        elif m:
            for s in m['sections']:
                if s['phys_material'] and s['enable_collision']: pm_used[s['phys_material']] += 1
        out['props'].append(r)
    # ------------------------------------------------------------------ volumes
    cj = json.load(open(os.path.join(OUT, 'collision.json'), encoding='utf-8'))
    vol_poly = {(v['sublevel'], v['actor']): v['polygons_gltf'] for v in cj['volumes']}
    for sub in subs:
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', None):
            if r['outer'] != sub + '.TheWorld.PersistentLevel' or not re.search(r'Volume$', r['class']): continue
            v = A.values(r['opath']); bc = A.values(v.get('CollisionComponent') or v.get('BrushComponent')) if (v.get('CollisionComponent') or v.get('BrushComponent')) else {}
            name = r['opath'].rsplit('.', 1)[-1]
            rec = {'actor': name, 'sublevel': sub, 'class': r['class'],
                   'actor_flags': {k: v.get(k) for k in ('bCollideActors', 'bBlockActors', 'bWorldGeometry', 'bBlockCamera', 'bPawnsOnly', 'bProjTarget') if k in v},
                   'component_flags': {k: bc.get(k) for k in ('CollideActors', 'BlockActors', 'BlockZeroExtent', 'BlockNonZeroExtent', 'BlockRigidBody', 'RBChannel') if k in bc},
                   'polygons_gltf': vol_poly.get((sub, name))}
            blocks = bool(v.get('bCollideActors', True)) and bool(v.get('bBlockActors')) and bool(bc.get('CollideActors')) and bool(bc.get('BlockActors'))
            rec['blocks_pawn'] = blocks and bool(bc.get('BlockNonZeroExtent'))
            rec['blocks_weapon'] = blocks and bool(bc.get('BlockZeroExtent'))
            extra = {k: x for k, x in (r['props'] or {}).items() if k not in ('Brush', 'BrushComponent', 'CollisionComponent', 'Components',
                     'Location', 'Rotation', 'DrawScale', 'DrawScale3D', 'PrePivot', 'Tag', 'Layer', 'Group', 'bHidden', 'CreationTime')}
            if extra: rec['authored'] = extra
            out['volumes'].append(rec)
    # ------------------------------------------------------------------ physical materials
    for pm in sorted(pm_used):
        e = A.values(pm); prop = A.values(e['PhysicalMaterialProperty']) if e.get('PhysicalMaterialProperty') else None
        out['physical_materials'][pm] = {'uses': pm_used[pm], 'props': e, 'property_object': prop,
                                         'property_class': (A.get(e['PhysicalMaterialProperty']) or {}).get('class') if e.get('PhysicalMaterialProperty') else None}
    # BSP surfaces (materials.json) -> phys materials
    mats = json.load(open(os.path.join(OUT, 'materials.json'), encoding='utf-8'))
    out['bsp_material_physmats'] = {m: phys_material(m)[0] for m in mats if m}
    # ------------------------------------------------------------------ world, movers, destructibles
    for sub in subs:
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'TnWorldInfo'):
            v = A.values(r['opath'])
            out['world'][sub] = {k: v[k] for k in v if re.search(r'Gravity|KillZ|StallZ|RBPhysics|Physics|MaxPhysicsSubsteps|bHighPriorityLoading|TimeDilation|bNoDefaultInventory|DefaultGravity', k)}
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'InterpActor'):
            v = A.values(r['opath']); c = A.values(v.get('StaticMeshComponent')) if v.get('StaticMeshComponent') else {}
            out['movers'].append({'actor': r['opath'], 'mesh': c.get('StaticMesh'), 'location_ue': v.get('Location'),
                                  'actor_flags': {k: v.get(k) for k in ('bCollideActors', 'bBlockActors', 'Physics', 'bStopOnEncroach', 'bNoEncroachCheck', 'bAlwaysEncroachCheck', 'bBlockedByInstigator') if k in v},
                                  'component_flags': {k: c.get(k) for k in FLAGS if k in c},
                                  'referenced_by': [s for s, _ in A.refs_to(r['opath'])][:8]})
        for r in A.find(sub + '.TheWorld.PersistentLevel.%', 'TnStaticDestructibleActor'):
            v = A.values(r['opath'])
            comps = [c for c in A.children(r['opath'])]
            out['destructibles'].append({'actor': r['opath'], 'props': {k: x for k, x in v.items() if not isinstance(x, (list,)) or len(x) < 40},
                                         'components': [{'object': c['opath'], 'class': c['class'], 'props': A.values(c['opath'])} for c in comps]})
    # ------------------------------------------------------------------ slice characters
    for name, pa in (('optimus_robot', 'TR_Optimus_ROBO_p.RB_Optimus_A_PHYSSYS'), ('optimus_vehicle', 'TR_Optimus_VEH_p.VH_Optimus_PHYSSYS')):
        pv = A.values(pa)
        bodies = []
        for b in pv.get('BodySetup') or []:
            bv = A.values(b); _, _, summ = simple_geometry(bv.get('AggGeom') or {})
            bodies.append({'bone': bv.get('BoneName'), 'fixed': bv.get('bFixed'), 'no_collision': bv.get('bNoCollision'),
                           'block_zero_extent': bv.get('bBlockZeroExtent'), 'block_non_zero_extent': bv.get('bBlockNonZeroExtent'),
                           'mass_scale': bv.get('MassScale'), 'phys_material': bv.get('PhysMaterial'), 'geometry': summ})
        cons = []
        for c in pv.get('ConstraintSetup') or []:
            cv = A.values(c)
            cons.append({k: cv.get(k) for k in ('JointName', 'ConstraintBone1', 'ConstraintBone2', 'bSwingLimited', 'bTwistLimited',
                                                 'Swing1LimitAngle', 'Swing2LimitAngle', 'TwistLimitAngle', 'LinearXSetup', 'LinearYSetup',
                                                 'LinearZSetup', 'bSwingLimitSoft', 'bTwistLimitSoft', 'SwingLimitStiffness', 'TwistLimitStiffness')})
        out['characters'][name] = {'physics_asset': pa, 'bodies': bodies, 'constraints': cons,
                                   'default_instance': {k: x for k, x in A.values(pv['DefaultInstance']).items()} if pv.get('DefaultInstance') else None}
    for c in out['characters'].values():
        c['physical_materials'] = {pm: A.values(pm) for pm in sorted({b['phys_material'] for b in c['bodies'] if b.get('phys_material')})}
    rd = A.values('TR_Optimus_ROBODEF_p.Optimus_ROBODEF')
    out['characters']['optimus_robot']['pawn_collision'] = {k: v for k, v in (rd.get('Collision') or {}).items() if k != 'RigidBodyMeshCache'}
    # ------------------------------------------------------------------ GLBs
    stats = {}
    for kind, vol_key, rep_key in (('pawn', 'blocks_pawn', 'pawn'), ('weapon', 'blocks_weapon', 'weapon')):
        g = GLB('AssetTools vs_physics %s collision (%s)' % (kind, MAP))
        bj, bbin = read_glb(os.path.join(OUT, 'collision_base.glb'))
        st = Counter()
        for node in bj.get('nodes', []):
            mi = node.get('mesh'); nm = bj['meshes'][mi].get('name', '') if mi is not None else ''
            if mi is None or not nm.startswith('BSPCollision_'): continue
            for pr in bj['meshes'][mi]['primitives']:
                P = accessor(bj, bbin, pr['attributes']['POSITION']).astype('f4')
                I = accessor(bj, bbin, pr['indices']).astype('u4') if 'indices' in pr else np.arange(len(P), dtype='u4')
                m = g.mesh(nm, [{'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)}, 'indices': g.acc(I, 'SCALAR', target=34963)}])
                g.node({'name': nm, 'mesh': m, 'extras': {'kind': 'bsp_solid'}}); st['bsp_tris'] += len(I) // 3
        for v in out['volumes']:
            if not v[vol_key] or not v['polygons_gltf']: continue
            tri = [t for poly in v['polygons_gltf'] for k in range(1, len(poly) - 1) for t in (poly[0], poly[k], poly[k + 1])]
            m = g.mesh(v['actor'], [{'attributes': {'POSITION': g.acc(np.array(tri, 'f4'), 'VEC3', True, 34962)}}])
            g.node({'name': v['actor'], 'mesh': m, 'extras': {'kind': v['class']}}); st['volumes'] += 1
        cache = {}
        for r in out['props']:
            how = r[rep_key]
            if how == 'none' or not r.get('mesh'): st['props_none'] += 1; continue
            key = (r['mesh'], how)
            if key not in cache:
                cache[key] = None
                m = out['meshes'][r['mesh']]
                if how == 'simple':
                    P, F = m['_simple_geom']
                    if P is not None:
                        Pg = ue_points_to_gltf(P).astype('f4')
                        cache[key] = (g.mesh(r['mesh'].rsplit('.', 1)[-1] + '_simple', [{'attributes': {'POSITION': g.acc(Pg, 'VEC3', True, 34962)},
                                       'indices': g.acc(F.astype('u4').ravel(), 'SCALAR', target=34963)}]), Pg.min(0), Pg.max(0), len(F))
                elif r.get('gltf') and os.path.exists(os.path.join(ROOT, r['gltf'])):
                    gg, bins = load_gltf(os.path.join(ROOT, r['gltf']))
                    en = {s['index']: s['enable_collision'] for s in m['sections']}
                    Ps, Is, base = [], [], 0
                    for pr in gg['meshes'][0]['primitives']:
                        if not en.get(pr.get('material', 0), True) or 'indices' not in pr: continue
                        P = accessor(gg, bins, pr['attributes']['POSITION']).astype('f4')
                        if not len(P): continue
                        Ps.append(P); Is.append(accessor(gg, bins, pr['indices']).astype('u4') + base); base += len(P)
                    if Ps:
                        P = np.concatenate(Ps); I = np.concatenate(Is)
                        cache[key] = (g.mesh(r['mesh'].rsplit('.', 1)[-1] + '_poly', [{'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)},
                                       'indices': g.acc(I, 'SCALAR', target=34963)}]), P.min(0), P.max(0), len(I) // 3)
            c = cache[key]
            if c is None: st['props_missing_geometry'] += 1; continue
            mi, lo, hi, nt = c
            M = np.array(r['gltf_matrix'], float).reshape(4, 4).T
            corners = np.array([[x, y, z, 1] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]) @ M.T
            if np.linalg.norm(corners[:, :3].max(0) - corners[:, :3].min(0)) > OVERSIZE_DIAG_M: st['props_oversize_skipped'] += 1; continue
            g.node({'name': r['actor'], 'mesh': mi, 'matrix': r['gltf_matrix'], 'extras': {'kind': 'prop_' + how, 'mesh': r['mesh']}})
            st['props_' + how] += 1; st['instanced_tris'] += nt
        path = os.path.join(OUT, 'collision_%s.glb' % kind); g.write(path)
        stats[kind] = dict(st, unique_meshes=sum(1 for x in cache.values() if x), size_mb=round(os.path.getsize(path) / 1e6, 2))
    # ------------------------------------------------------------------ summary
    for m in out['meshes'].values(): m.pop('_simple_geom', None)
    M = out['meshes'].values()
    out['stats'] = {'props': len(out['props']), 'unique_meshes': len(out['meshes']),
                    'meshes_with_simple_collision': sum(1 for m in M if m['simple']['has_geometry']),
                    'meshes_with_collision_disabled_sections': sum(1 for m in M if any(not s['enable_collision'] for s in m['sections'])),
                    'mesh_flags_authored': dict(Counter(f for m in M for f in m['flags_authored'])),
                    'props_pawn': dict(Counter(r['pawn'] for r in out['props'])), 'props_weapon': dict(Counter(r['weapon'] for r in out['props'])),
                    'props_rigid_body': dict(Counter(r['rigid_body'] for r in out['props'])),
                    'volumes': dict(Counter((v['class'], v['blocks_pawn'], v['blocks_weapon']) and '%s pawn=%s weapon=%s' % (v['class'], v['blocks_pawn'], v['blocks_weapon']) for v in out['volumes'])),
                    'physical_materials': len(out['physical_materials']), 'glb': stats}
    out['notes'] += [
        'Representation rule (UE3 UStaticMeshComponent::LineCheck/PointCheck): zero-extent -> simple iff UseSimpleLineCollision and '
        'BodySetup has geometry; non-zero-extent -> simple iff UseSimpleBoxCollision and geometry; else per-poly over sections with '
        'EnableCollision. HIGH CONFIDENCE (stock UE3; WFC native not decompiled). Flags/geometry CONFIRMED.',
        'Convex hull triangles are the authored FaceTriData indices into VertexData (UE mesh space; converted to glTF with the umodel '
        'convention and placed with the prop gltf_matrix).',
        'BlockingVolume BrushComponents that leave BlockZeroExtent unset (bool default false) block pawns but not hitscan.',
        'collision.glb (vs_collision.py) remains: it uses render geometry of every BLOCK prop for both trace types.']
    path = os.path.join(OUT, 'physics.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['stats'], indent=1, default=str)[:3000]); print('->', path)

if __name__ == '__main__':
    main()
