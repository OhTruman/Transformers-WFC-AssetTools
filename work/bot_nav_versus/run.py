"""BrokenHope versus bot nav (Integration 2026-10-18): bot_nav.py unchanged, run with its own --out, with the pawn collision augmented by
the 5 transforming bridges' 3 deck boxes each, posed in the Transformed state (the versus layout: every transforming actor transformed).

Posing (manifests/maps/mp_transforming_actors.json 'posing'): world_box = actor.gltf_matrix x bone_global(t_end) x box_local_gltf, half
extents = box_extent_gltf / 2; bone_global(t_end) = the last body_bone_keyframes entry (t = clip_length = Transformed). Matrices are glTF
column-major. Each box -> 12 outward-wound triangles, yielded as one extra node by a wrapper around map_structure_audit.node_tris, which
both bot_nav passes (walkable layers, obstruction samples) read. Nothing else changes, so other maps are untouched by construction.
  python run.py base     -> work/bot_nav_versus/base/   (today's generator, no boxes: drift check against the live file)
  python run.py versus   -> work/bot_nav_versus/versus/ (+ deck boxes); also writes deck_boxes.json
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'wfc'))
MAP = 'MP_ESC_BrokenHope'

def deck_boxes():
    d = json.load(open(os.path.join(ROOT, 'manifests', 'maps', 'mp_transforming_actors.json'), encoding='utf-8'))
    out = []
    for a in d['actors']:
        if a['map'] != MAP: continue
        m = d['meshes'][a['mesh']]
        if 'Bridge' not in a['mesh']: continue
        A = np.array(a['gltf_matrix']).reshape(4, 4).T
        for body in m['bodies']:
            kf = m['body_bone_keyframes'][body['bone']][-1]
            B = np.array(kf['matrix']).reshape(4, 4).T
            for bi, bx in enumerate(body['boxes']):
                L = np.array(bx['box_local_gltf']).reshape(4, 4).T
                W = A @ B @ L; h = np.array(bx['box_extent_gltf']) / 2
                C = np.array([[sx * h[0], sy * h[1], sz * h[2], 1.0] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) @ W.T
                out.append({'actor': a['actor'], 'bone': body['bone'], 'box': bi, 't_s': kf['t'], 'corners_gltf': C[:, :3].tolist(),
                            'aabb_gltf': [C[:, :3].min(0).round(3).tolist(), C[:, :3].max(0).round(3).tolist()]})
    return out

# corner index = sx*4 + sy*2 + sz (0 = -, 1 = +); faces as outward quads
FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]

def tris(C):
    C = np.array(C); ctr = C.mean(0); T = []
    for f in FACES:
        q = C[list(f)]
        for t in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
            t = np.array(t); n = np.cross(t[1] - t[0], t[2] - t[0])
            if np.dot(n, t.mean(0) - ctr) < 0: t = t[[0, 2, 1]]       # wind outward
            T.append(t)
    return np.array(T)

if __name__ == '__main__':
    mode = sys.argv[1]
    dst = os.path.join(HERE, mode); os.makedirs(dst, exist_ok=True)
    sys.argv = ['bot_nav.py', MAP, '--out', dst]
    import map_structure_audit as MSA
    if mode == 'versus':
        boxes = deck_boxes()
        json.dump({'map': MAP, 'state': 'Transformed (t = clip end)', 'boxes': boxes}, open(os.path.join(HERE, 'deck_boxes.json'), 'w'), indent=1)
        extra = np.concatenate([tris(b['corners_gltf']) for b in boxes])
        orig = MSA.node_tris
        def node_tris(path, want_normals=False):
            yield from orig(path, want_normals)
            if os.path.basename(path) == 'collision_pawn.glb':
                yield None, {'name': 'versus_bridge_decks'}, None, extra, None, 1.0
        MSA.node_tris = node_tris
    import bot_nav
    bot_nav.main()
