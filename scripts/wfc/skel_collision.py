"""PhysicsAsset collision of skeletal world actors (TnTransformingWorldActor) at the skeletal reference pose, as world triangles in
glTF space - for the campaign walk graph (map_structure_audit, campaign only; Integration 2026-10-17, decision A).

UE3: a SkeletalMeshComponent with a PhysicsAsset and BlockActors collides through the asset's RB_BodySetup bodies, one per bone,
each an aggregate of primitive elements whose TM is relative to the bone. Placed here at the reference pose (InitialState
'Untransformed'; matinee-driven poses are not evaluated):
  world (UE, row vectors) = p * Scale(X, Y, Z) / 2 box corner * ElemTM * BoneRefGlobal * ComponentToActor * ActorToWorld
BoneRefGlobal comes from the umodel skeletal glTF in ExtractedAssets/content (same axis convention as the maps: glTF = C * UE).
Element types: BoxElems are decoded (FKBoxElem X / Y / Z = full edge lengths). Any other type (Sphere / Sphyl / Convex) is
reported in 'undecoded', never guessed.
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import authored as A  # noqa: E402
from vs_common import ROOT, C4, C4i, ue_actor_matrix, ue_points_to_gltf  # noqa: E402

CONTENT = os.path.join(ROOT, 'content')
BOX = np.array([[x, y, z] for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)])
FACES = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
_bones = {}

def bone_ref_ue(skel):
    """skeletal mesh object path -> {bone name: 4x4 UE row-vector reference global matrix}, from the umodel glTF"""
    if skel in _bones: return _bones[skel]
    pk, nm = skel.split('.')[0], skel.split('.')[-1]
    f = os.path.join(CONTENT, pk, nm + '.gltf')
    out = {}
    if os.path.exists(f):
        g = json.load(open(f, encoding='utf-8')); nodes = g['nodes']
        par = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
        def local(n):
            if 'matrix' in n: return np.array(n['matrix'], 'f8').reshape(4, 4).T
            x, y, z, w = n.get('rotation', [0, 0, 0, 1])
            R = np.array([[1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)], [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
                          [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]])
            M = np.eye(4); M[:3, :3] = R * np.array(n.get('scale', [1, 1, 1]))[None, :]; M[:3, 3] = n.get('translation', [0, 0, 0]); return M
        glob = {}
        def G(i):
            if i not in glob: glob[i] = (G(par[i]) if i in par else np.eye(4)) @ local(nodes[i])
            return glob[i]
        for i, n in enumerate(nodes):
            if n.get('name'): out[n['name']] = (C4i @ G(i) @ C4).T      # glTF column-vector -> UE row-vector
    _bones[skel] = out
    return out

def actor_tris(opath):
    """-> (tris (n,3,3) glTF world, info dict) for one TnTransformingWorldActor"""
    v = A.values(opath) or {}; c = A.values(v.get('SkeletalMeshComponent') or '') or {}
    info = {'actor': opath.rsplit('.', 1)[-1], 'skeletal_mesh': c.get('SkeletalMesh'), 'physics_asset': c.get('PhysicsAsset'), 'boxes': 0, 'undecoded': {}}
    if not c.get('PhysicsAsset'): info['skipped'] = 'no PhysicsAsset'; return np.zeros((0, 3, 3)), info
    if not c.get('BlockActors', True) or not c.get('CollideActors', True): info['skipped'] = 'component BlockActors / CollideActors false'; return np.zeros((0, 3, 3)), info
    bones = bone_ref_ue(c.get('SkeletalMesh') or '')
    if not bones: info['skipped'] = 'no skeletal glTF / bones'; return np.zeros((0, 3, 3)), info
    L = v.get('Location') or {}; R = v.get('Rotation') or {}; S3 = v.get('DrawScale3D') or {}; P = v.get('PrePivot') or {}
    W = ue_actor_matrix((L.get('X', 0), L.get('Y', 0), L.get('Z', 0)), (R.get('Pitch', 0), R.get('Yaw', 0), R.get('Roll', 0)), v.get('DrawScale', 1.0),
                        (S3.get('X', 1), S3.get('Y', 1), S3.get('Z', 1)), (P.get('X', 0), P.get('Y', 0), P.get('Z', 0)))
    tris = []; missing = set()
    for b in (A.values(c['PhysicsAsset']) or {}).get('BodySetup') or []:
        bv = A.values(b) or {}; Bm = bones.get(bv.get('BoneName'))
        if Bm is None: missing.add(bv.get('BoneName')); continue
        for k, els in (bv.get('AggGeom') or {}).items():
            if k != 'BoxElems': info['undecoded'][k] = info['undecoded'].get(k, 0) + len(els or []); continue
            for e in els:
                if e.get('bNoRBCollision') and False: pass
                TM = np.array(e['TM'], 'f8').reshape(4, 4)
                pts = np.c_[BOX * [e['X'], e['Y'], e['Z']], np.ones(8)] @ TM @ Bm @ W
                g = ue_points_to_gltf(pts[:, :3]); tris.append(g[np.array(FACES)]); info['boxes'] += 1
    if missing: info['bones_missing'] = sorted(missing)
    return (np.concatenate(tris) if tris else np.zeros((0, 3, 3))), info

if __name__ == '__main__':
    T, info = actor_tris(sys.argv[1]); print(info, T.shape)
    if len(T): print('bounds', T.reshape(-1, 3).min(0).round(2), T.reshape(-1, 3).max(0).round(2))
