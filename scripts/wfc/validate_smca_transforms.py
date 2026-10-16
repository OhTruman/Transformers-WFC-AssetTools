"""Transform-level validation of every StaticMeshCollectionActor component (default MP_IAC_Streets; --map <MAP> for others,
written to manifests/next_map/<MAP>_transform_validation.json) (M04 geometry fix).

Independent expected transform per component (does not reuse vs_map code paths):
  P  = serialized CachedParentToWorld: the SMCA native tail, N x 16 big-endian floats in StaticMeshComponents order
       (re-read here from the cooked package)
  c  = component Scale, Scale3D, Rotation, Translation, effective through the archetype chain (manifests/authored.db)
  M  = S(Scale*Scale3D) * R(Rotation) * T(Translation) * P     (UE row vectors; RE: SetTransformedToWorld 0x82DC3508)
Cross-checks: the RE table RE-Workspace/notes/data/streets_smca_component_scale.json (scale/rotation/translation per
component), P is a pure rotation+translation.
Exported transform: props.json ue_matrix (+ gltf_matrix == UE->glTF conversion of ue_matrix), the world.glb node, and
the node in collision.glb / collision_pawn.glb / collision_weapon.glb.
Per component, independently: translation, rotation, scale X/Y/Z (signed), sign of each axis, determinant sign,
world AABB (mesh Bounds through the matrix). Also: lightmap bindings unchanged vs a before-snapshot and present on the
world.glb node; non-SMCA props.json records unchanged vs the snapshot.
Outputs: manifests/streets_transform_validation.json, manifests/streets_transform_fix_audit.json. Exit 1 on failure.
  python validate_smca_transforms.py [--before DIR]
"""
import argparse, json, math, os, struct, sys
from collections import Counter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from vs_common import VS, read_glb, ue_to_gltf_matrix, is_campaign  # noqa: E402

MAP = next((sys.argv[i + 1] for i, x in enumerate(sys.argv[:-1]) if x == '--map'), 'MP_IAC_Streets')
LV = MAP + '_ART_m'
SLICE = os.path.join(VS, 'Maps', MAP)
MANI = os.path.normpath(os.path.join(HERE, '..', '..', 'manifests'))
RE_TABLE = (r'F:/Transformers Rebuild/RE-Workspace/notes/data/streets_smca_component_scale.json' if MAP == 'MP_IAC_Streets' else '')
OUT_VALID = (os.path.join(MANI, 'streets_transform_validation.json') if MAP == 'MP_IAC_Streets' else
             os.path.join(MANI, 'next_map', MAP + '_transform_validation.json'))
OUT_AUDIT = (os.path.join(MANI, 'streets_transform_fix_audit.json') if MAP == 'MP_IAC_Streets' else
             os.path.join(MANI, 'next_map', MAP + '_transform_audit.json'))
TOL_T, TOL_S, TOL_R = 0.05, 1e-4, 1e-4          # UU, relative scale, rotation-matrix element

def rot(p, y, r):
    """UE3 FRotationMatrix (row vectors), angles in Unreal units."""
    k = math.pi / 32768.0
    SP, CP = math.sin(p * k), math.cos(p * k); SY, CY = math.sin(y * k), math.cos(y * k); SR, CR = math.sin(r * k), math.cos(r * k)
    return np.array([[CP * CY, CP * SY, SP, 0],
                     [SR * SP * CY - CR * SY, SR * SP * SY + CR * CY, -SR * CP, 0],
                     [-(CR * SP * CY + SR * SY), CY * SR - CR * SP * SY, CR * CP, 0],
                     [0, 0, 0, 1]], 'f8')

def v3(x, d):
    if x is None: return list(d)
    if isinstance(x, dict): return [x.get('X', 0.0), x.get('Y', 0.0), x.get('Z', 0.0)] if 'X' in x or 'Y' in x or 'Z' in x else [x.get('Pitch', 0), x.get('Yaw', 0), x.get('Roll', 0)]
    return list(x)

def native_parents():
    out = {}
    # every exported sublevel (map.json: name prefix + authored LevelStreaming, e.g. Seed streams MP_IAC_Global_Art_m)
    mj = os.path.join(SLICE, 'map.json')
    lvs = (json.load(open(mj, encoding='utf-8')).get('sublevels') if os.path.exists(mj) else None) or           [MAP + '_BASE_m', MAP + '_ART_m', MAP + '_AUDIO_m']
    for lv in lvs:
        try: out.update(_native_parents(lv))
        except Exception as e: print('native parents unavailable for', lv, e)
    return out

def _native_parents(LV):
    p = objtree.package(LV)
    out = {}
    for i, e in enumerate(p.exports):
        if p.class_name(e) != 'StaticMeshCollectionActor': continue
        a = p.object_path(i + 1)
        if not a.startswith(LV + '.TheWorld.PersistentLevel.'): continue
        comps = (A.get(a)['props'] or {}).get('StaticMeshComponents') or []
        _, used = p._tr.read_object(i + 1)
        raw = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
        for k, c in enumerate(comps):
            if c and len(raw) >= 64 * (k + 1):
                out[c] = np.array(struct.unpack_from('>16f', raw, 64 * k), 'f8').reshape(4, 4)
    return out

def decompose(M, Q):
    """signed per-axis scale and off-diagonal residual of M3 against the pure rotation Q3 (M3 = diag(s) Q3)."""
    D = M[:3, :3] @ np.linalg.inv(Q[:3, :3])
    s = np.diag(D).copy()
    off = float(np.abs(D - np.diag(s)).max())
    return s, off

def aabb(M, b):
    if not b: return None
    o = np.array(b['origin']); e = np.array(b['box_extent'])
    cs = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]) * e + o
    w = np.c_[cs, np.ones(8)] @ M
    return [w[:, :3].min(0).round(2).tolist(), w[:, :3].max(0).round(2).tolist()]

def glb_nodes(path):
    g, _ = read_glb(path)
    out = {}
    for n in g.get('nodes', []):
        if 'matrix' in n: out.setdefault(n.get('name'), []).append(n)
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--before'); ap.add_argument('--map'); a = ap.parse_args()
    props = json.load(open(os.path.join(SLICE, 'props.json'), encoding='utf-8'))['props']
    meshes = json.load(open(os.path.join(SLICE, 'props_authored.json'), encoding='utf-8')).get('meshes') or {}
    re_t = json.load(open(RE_TABLE, encoding='utf-8')) if os.path.exists(RE_TABLE) else {}
    P = native_parents()
    world = glb_nodes(os.path.join(SLICE, 'world.glb'))
    cols = {f: glb_nodes(os.path.join(SLICE, f)) for f in ('collision.glb', 'collision_pawn.glb', 'collision_weapon.glb')}
    lm = {x['component']: x for x in json.load(open(os.path.join(SLICE, 'lightmaps.json'), encoding='utf-8'))['props']}
    before = {}
    if a.before:
        before = {(x['sublevel'], x.get('component') or x['actor']): x for x in json.load(open(os.path.join(a.before, 'props.json'), encoding='utf-8'))['props']}
        lm_before = {x['component']: x for x in json.load(open(os.path.join(a.before, 'lightmaps.json'), encoding='utf-8'))['props']}
    st = Counter(); fails = []; recs = []
    smca = [x for x in props if x['class'] == 'StaticMeshCollectionActor']
    idx = {}
    for x in smca:
        k = int(x['actor'].split('.')[-1]) if False else None
    # node name in world.glb is '<SMCA name>.<k>'
    for x in smca:
        comp = x['component']
        st['components_checked'] += 1
        if comp not in P: fails.append('no native parent: ' + comp); st['missing_native'] += 1; continue
        Pm = P[comp]
        pr = np.linalg.norm(Pm[:3, :3], axis=1)
        st['native_parent_pure_rotation'] += int(np.allclose(pr, 1, atol=1e-4) and abs(np.linalg.det(Pm[:3, :3]) - 1) < 1e-3)
        cv = A.values(comp)
        s = cv.get('Scale', 1.0) if cv.get('Scale') is not None else 1.0
        s3 = v3(cv.get('Scale3D'), (1, 1, 1))
        rt = v3(cv.get('Rotation'), (0, 0, 0)); tr = v3(cv.get('Translation'), (0, 0, 0))
        S = np.diag([s * s3[0], s * s3[1], s * s3[2], 1.0])
        R = rot(*rt); T = np.eye(4); T[3, :3] = tr
        Mexp = S @ R @ T @ Pm
        Q = R @ Pm                                   # pure rotation part (translation ignored in 3x3)
        # RE cross-check
        r = re_t.get(comp)
        if r is not None:
            st['re_table_entries'] += 1
            ok_re = np.allclose(r['scale'], [s * v for v in s3], rtol=1e-4, atol=1e-5) and list(r['rotation']) == [int(v) for v in rt] \
                and np.allclose(r['translation'], tr, atol=1e-3)
            st['re_table_agree'] += int(ok_re)
            if not ok_re: fails.append('RE table disagrees: ' + comp)
        elif RE_TABLE:
            st['re_table_missing'] += 1; fails.append('not in RE table: ' + comp)
        else:
            st['re_table_not_applicable (no RE table for this map)'] += 1
        Mx = np.array(x['ue_matrix'], 'f8')
        sx, off = decompose(Mx, Q); se = np.array([s * v for v in s3])
        t_ok = np.allclose(Mx[3, :3], Mexp[3, :3], atol=TOL_T)
        r_ok = off < TOL_R * max(1.0, float(np.abs(se).max()))
        s_ok = np.allclose(sx, se, rtol=TOL_S, atol=1e-6)
        sign_ok = bool(np.all(np.sign(sx) == np.sign(se)))
        det_ok = np.sign(np.linalg.det(Mx[:3, :3])) == np.sign(np.linalg.det(Mexp[:3, :3]))
        g_ok = np.allclose(np.array(x['gltf_matrix']), np.array(ue_to_gltf_matrix(Mx)), atol=1e-6)
        b = (meshes.get(x['mesh']) or {}).get('bounds_ue')
        bx, be = aabb(Mx, b), aabb(Mexp, b)
        b_ok = bx is None or np.allclose(np.array(bx), np.array(be), atol=0.5)
        # glb nodes: find node with this matrix among nodes named actor.k (component order)
        nm_nodes = world.get(None, [])
        for f, k in (('t', t_ok), ('r', r_ok), ('s', s_ok), ('sign', sign_ok), ('det', det_ok), ('gltf', g_ok), ('bounds', b_ok)):
            st[f + '_match'] += int(bool(k))
            if not k: st[f + '_mismatch'] += 1
        allok = t_ok and r_ok and s_ok and sign_ok and det_ok and g_ok and b_ok
        st['exact_matches'] += int(allok)
        if not allok: fails.append('transform mismatch: %s t=%s r=%s s=%s sign=%s det=%s gltf=%s bounds=%s' % (comp, t_ok, r_ok, s_ok, sign_ok, det_ok, g_ok, b_ok))
        mirrored = np.linalg.det(Mexp[:3, :3]) < 0
        st['mirrored_det_negative'] += int(mirrored); st['any_negative_axis'] += int(bool((se < 0).any()))
        st['two_negative_axes_not_mirrored'] += int(int((se < 0).sum()) == 2); st['non_uniform'] += int(not np.allclose(se, se[0])); st['scale_not_one'] += int(not np.allclose(se, 1))
        # lightmap binding
        if comp in lm:
            st['lightmap_bound'] += 1
            if a.before:
                lb = lm_before.get(comp)
                same = lb is not None and all(lb[f] == lm[comp][f] for f in ('atlas', 'coeffs', 'coordScale', 'coordBias', 'scaleVec'))
                st['lightmap_unchanged'] += int(same)
                if not same: fails.append('lightmap binding changed: ' + comp)
        rec = {'component': comp, 'actor': x['actor'], 'mesh': x['mesh'], 'expected_scale': se.round(6).tolist(), 'exported_scale': sx.round(6).tolist(),
               'mirrored': bool(mirrored), 'translation': Mexp[3, :3].round(3).tolist(), 'aabb_ue': bx, 'ok': bool(allok)}
        if a.before:
            ob = before.get((x['sublevel'], comp))
            if ob:
                Mo = np.array(ob['ue_matrix'], 'f8'); so, _ = decompose(Mo, Q)
                rec['before'] = {'scale': so.round(6).tolist(), 'mirrored': bool(np.linalg.det(Mo[:3, :3]) < 0), 'aabb_ue': aabb(Mo, b),
                                 'ue_matrix': ob['ue_matrix']}
                rec['after_ue_matrix'] = x['ue_matrix']
        recs.append(rec)
    # glb node agreement: every prop gltf_matrix appears as a node matrix in world.glb and each collision glb
    def matset(nodes):
        return {tuple(np.round(np.array(n['matrix'], 'f8'), 4).tolist()) for v in nodes.values() for n in v}
    wm = matset(world)
    for x in smca:
        # campaign: components whose StaticMesh does not resolve (D5 GLB_ART sky / light-ray cards) have no world.glb node
        if is_campaign(MAP) and not x.get('gltf'): st['campaign_meshless_components_skipped'] += 1; continue
        key = tuple(np.round(np.array(x['gltf_matrix'], 'f8'), 4).tolist())
        st['world_glb_node_match'] += int(key in wm)
        if key not in wm: fails.append('world.glb node missing for ' + x['component'])
    cur = {tuple(np.round(np.array(x['gltf_matrix'], 'f8'), 4).tolist()) for x in props}
    stale = set()
    if a.before:
        stale = {tuple(np.round(np.array(r['before']['ue_matrix'] and ue_to_gltf_matrix(np.array(r['before']['ue_matrix'])), 'f8'), 4).tolist())
                 for r in recs if r.get('before') and r['before']['ue_matrix'] != r['after_ue_matrix']}
    for f, nodes in cols.items():
        cm = matset(nodes); n_in = sum(1 for x in smca if tuple(np.round(np.array(x['gltf_matrix'], 'f8'), 4).tolist()) in cm)
        st[f + '_smca_nodes_with_corrected_matrix'] = n_in
        bad = [m for m in cm if m in stale and m not in cur]
        st[f + '_stale_pre_fix_matrices'] = len(bad)
        if bad: fails.append('%s still contains %d pre-fix matrices' % (f, len(bad)))
    # world.glb lightmap extras on lightmapped nodes
    lmn = sum(1 for v in world.values() for n in v if (n.get('extras') or {}).get('lm_atlas'))
    st['world_glb_lightmapped_nodes'] = lmn
    # non-SMCA records unchanged
    if a.before:
        for x in props:
            if x['class'] == 'StaticMeshCollectionActor': continue
            ob = before.get((x['sublevel'], x.get('component') or x['actor']))
            same = ob is not None and ob['ue_matrix'] == x['ue_matrix']
            st['non_smca_unchanged'] += int(same)
            if not same: fails.append('non-SMCA record changed: ' + (x.get('component') or x['actor']))
        st['non_smca_total'] = sum(1 for x in props if x['class'] != 'StaticMeshCollectionActor')
        st['smca_records_changed_vs_before'] = sum(1 for r in recs if r.get('before') and r['before']['ue_matrix'] != r['after_ue_matrix'])
    out = {'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/validate_smca_transforms.py',
           'rule': 'M = S(Scale*Scale3D) * R(Rotation) * T(Translation) * CachedParentToWorld (UE row vectors)',
           'tolerances': {'translation_uu': TOL_T, 'scale_rel': TOL_S, 'rotation_offdiag': TOL_R, 'bounds_uu': 0.5},
           'stats': dict(st), 'failures': fails}
    json.dump(out, open(OUT_VALID, 'w'), indent=1)
    if a.before:
        big = sorted((r for r in recs if r.get('before')), key=lambda r: -abs(math.log(max(1e-6, abs(np.prod(r['expected_scale']))) /
                                                                                  max(1e-6, abs(np.prod(r['before']['scale']))))))
        mir = [r for r in recs if r['mirrored']]
        fam = Counter(r['mesh'].rsplit('.', 1)[-1] for r in recs if r.get('before') and r['before']['ue_matrix'] != r['after_ue_matrix'])
        json.dump({'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/validate_smca_transforms.py',
                   'changed_components': st.get('smca_records_changed_vs_before'), 'changed_by_mesh': dict(fam.most_common()),
                   'largest_volume_corrections': big[:25], 'mirrored_examples': mir[:15],
                   'backdrop': [r for r in recs if 'CityBackdrop' in r['mesh'] or 'SpaceDome' in r['mesh']],
                   'all_components': recs}, open(OUT_AUDIT, 'w'), indent=1)
    print(json.dumps(dict(st), indent=1)); print('failures', len(fails)); [print('  FAIL', f) for f in fails[:20]]
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
