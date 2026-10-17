"""Escalation closed-doors bot nav (cross-check for the original escalation_navmesh.json; Integration 2026-10-18, plan C).

Escalation start state (Gameplay spec section 2 / 5; TransformingActors keeps the authored closed start): every transforming door
CLOSED = the Untransformed pose (t = 0 of its TransOut clip, the first body_bone_keyframes entry); bridges hidden until bought, so no
deck (the MP pawn collision has no transforming-actor geometry at all, so leaving bridges out IS the hidden state); the 7 BrokenHope
DynamicBlockingVolumes are already in collision_pawn.glb. bot_nav.py is unchanged: its triangle reader (map_structure_audit.node_tris)
is wrapped to append the posed door boxes, as for the versus nav (work/bot_nav_versus/run.py).
  python run.py <MAP> base | closed      -> work/bot_nav_escalation/<MAP>/<mode>/bot_nav.json (+ door_boxes.json)
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'wfc')); sys.path.insert(0, os.path.join(ROOT, 'work', 'bot_nav_versus'))
from run import tris  # noqa: E402  (same outward-wound box triangulation as the versus nav)

def door_boxes(MAP):
    d = json.load(open(os.path.join(ROOT, 'manifests', 'maps', 'mp_transforming_actors.json'), encoding='utf-8'))
    out = []
    for a in d['actors']:
        if a['map'] != MAP or 'Door' not in a['mesh']: continue
        m = d['meshes'][a['mesh']]; A = np.array(a['gltf_matrix']).reshape(4, 4).T
        for body in m['bodies']:
            kf = m['body_bone_keyframes'][body['bone']][0]                       # t = 0: Untransformed = closed
            B = np.array(kf['matrix']).reshape(4, 4).T
            for bi, bx in enumerate(body['boxes']):
                L = np.array(bx['box_local_gltf']).reshape(4, 4).T; h = np.array(bx['box_extent_gltf']) / 2
                C = np.array([[sx * h[0], sy * h[1], sz * h[2], 1.0] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) @ (A @ B @ L).T
                out.append({'actor': a['actor'], 'mesh': a['mesh'], 'bone': body['bone'], 'box': bi, 't_s': kf['t'],
                            'corners_gltf': C[:, :3].tolist(), 'aabb_gltf': [C[:, :3].min(0).round(3).tolist(), C[:, :3].max(0).round(3).tolist()]})
    return out

if __name__ == '__main__':
    MAP, mode = sys.argv[1], sys.argv[2]
    dst = os.path.join(HERE, MAP, mode); os.makedirs(dst, exist_ok=True)
    sys.argv = ['bot_nav.py', MAP, '--out', dst]
    import map_structure_audit as MSA
    if mode == 'closed':
        boxes = door_boxes(MAP)
        json.dump({'map': MAP, 'state': 'Escalation start: doors closed (Untransformed, t = 0), bridges hidden', 'boxes': boxes},
                  open(os.path.join(dst, 'door_boxes.json'), 'w'), indent=1)
        extra = np.concatenate([tris(b['corners_gltf']) for b in boxes])
        orig = MSA.node_tris
        def node_tris(path, want_normals=False):
            yield from orig(path, want_normals)
            if os.path.basename(path) == 'collision_pawn.glb':
                yield None, {'name': 'escalation_closed_doors'}, None, extra, None, 1.0
        MSA.node_tris = node_tris
    import bot_nav
    bot_nav.main()
