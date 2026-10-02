"""Rebuild MP_IAC_Streets collision with authored static-mesh collision.

The vertical-slice collision.glb previously held only BSP-solid surfaces + blocking-volume
convex hulls. The ~1952 placed static meshes carry authored collision flags (CollideActors /
BlockActors) in props.json: 1693 BLOCK the player, 259 do not. In UE3 the player cylinder
collides against each static mesh's collision representation; we reproduce that by including
the render geometry of every BLOCKING prop (per-poly path), excluding the non-colliders and
decorative/background geometry (and guarding against oversized meshes such as the skydome).

Meshes are INSTANCED (unique mesh once + a node per placement with its glTF matrix), so the
file stays small; the reconstruction bakes world-space collision at load time.

Output: ExtractedAssets/VerticalSlice/Maps/<MAP>/collision.glb  (collision_base.glb kept as
the pristine BSP+volume base so this step is idempotent).

    AssetTools\\bin\\py\\python.exe AssetTools\\scripts\\wfc\\vs_collision.py [MAP]
"""
import json, os, shutil, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import ROOT, VS, GLB, read_glb, load_gltf, accessor  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)
OVERSIZE_DIAG_M = 2000.0     # skip anything spanning more than this (skydome/background shells)


def mesh_world_aabb_diag(local_min, local_max, M):
    c = []
    for xb in (local_min[0], local_max[0]):
        for yb in (local_min[1], local_max[1]):
            for zb in (local_min[2], local_max[2]):
                v = M @ np.array([xb, yb, zb, 1.0])
                c.append(v[:3])
    c = np.array(c)
    return float(np.linalg.norm(c.max(0) - c.min(0)))


def main():
    base = os.path.join(OUT, 'collision_base.glb')
    cur = os.path.join(OUT, 'collision.glb')
    if not os.path.exists(base):
        if not os.path.exists(cur):
            print('ERROR: no collision.glb to seed base from', file=sys.stderr); sys.exit(1)
        shutil.copyfile(cur, base)
        print('seeded pristine base: collision_base.glb')

    col = GLB('AssetTools vs_collision (BSP + volumes + blocking static meshes)')

    # ---- base: BSP solid + blocking-volume hulls (already world-space, positions-only) ----
    bj, bbin = read_glb(base)
    base_tris = 0
    for node in bj.get('nodes', []):
        mi = node.get('mesh')
        if mi is None:
            continue
        for pr in bj['meshes'][mi]['primitives']:
            P = accessor(bj, bbin, pr['attributes']['POSITION']).astype('f4')
            if 'indices' in pr:
                idx = accessor(bj, bbin, pr['indices']).astype('u4')
            else:
                idx = np.arange(len(P), dtype='u4')
            m = col.mesh(bj['meshes'][mi].get('name', 'base'),
                         [{'attributes': {'POSITION': col.acc(P, 'VEC3', True, 34962)},
                           'indices': col.acc(idx, 'SCALAR', target=34963)}])
            col.node({'name': bj['meshes'][mi].get('name', 'base'), 'mesh': m,
                      'extras': {'kind': 'base'}})
            base_tris += len(idx) // 3

    # ---- blocking static-mesh props (instanced) ----
    props = json.load(open(os.path.join(OUT, 'props.json'), encoding='utf-8'))['props']
    mesh_cache = {}   # gltf path -> (col mesh index, local_min, local_max)
    inc = skipped_nonblock = skipped_err = skipped_big = 0
    prop_tris = 0

    def unique_mesh(gltf_rel):
        if gltf_rel in mesh_cache:
            return mesh_cache[gltf_rel]
        path = os.path.join(ROOT, gltf_rel)
        if not os.path.exists(path):
            mesh_cache[gltf_rel] = None
            return None
        g, bins = load_gltf(path)
        Ps, Is, base_v = [], [], 0
        lmin = np.array([1e30, 1e30, 1e30]); lmax = -lmin
        for pr in g['meshes'][0]['primitives']:
            at = pr['attributes']
            if 'POSITION' not in at or 'indices' not in pr:
                continue
            P = accessor(g, bins, at['POSITION']).astype('f4')
            if len(P) == 0:
                continue
            I = accessor(g, bins, pr['indices']).astype('u4') + base_v
            Ps.append(P); Is.append(I); base_v += len(P)
            lmin = np.minimum(lmin, P.min(0)); lmax = np.maximum(lmax, P.max(0))
        if not Ps:
            mesh_cache[gltf_rel] = None
            return None
        P = np.concatenate(Ps); I = np.concatenate(Is)
        mi = col.mesh(os.path.basename(gltf_rel),
                      [{'attributes': {'POSITION': col.acc(P, 'VEC3', True, 34962)},
                        'indices': col.acc(I, 'SCALAR', target=34963)}])
        mesh_cache[gltf_rel] = (mi, lmin, lmax, len(I) // 3)
        return mesh_cache[gltf_rel]

    for p in props:
        if not p.get('block'):
            skipped_nonblock += 1; continue
        if p.get('error') or not p.get('gltf'):
            skipped_err += 1; continue
        um = unique_mesh(p['gltf'])
        if um is None:
            skipped_err += 1; continue
        mi, lmin, lmax, tris = um
        M = np.array(p['gltf_matrix'], dtype='f8').reshape(4, 4).T   # column-major -> row for @
        if mesh_world_aabb_diag(lmin, lmax, M) > OVERSIZE_DIAG_M:
            skipped_big += 1; continue
        col.node({'name': p['actor'], 'mesh': mi, 'matrix': p['gltf_matrix'],
                  'extras': {'kind': 'prop_block', 'mesh': p.get('mesh')}})
        inc += 1; prop_tris += tris

    col.write(cur)
    sz = os.path.getsize(cur) / 1e6
    print(json.dumps({
        'map': MAP, 'out': cur, 'size_mb': round(sz, 2),
        'base_tris': base_tris, 'blocking_props_included': inc,
        'unique_prop_meshes': sum(1 for v in mesh_cache.values() if v),
        'prop_collision_tris_per_instance_sum': prop_tris,
        'skipped_nonblocking': skipped_nonblock, 'skipped_error_or_missing': skipped_err,
        'skipped_oversize(>%dm)' % int(OVERSIZE_DIAG_M): skipped_big,
    }, indent=1))


if __name__ == '__main__':
    main()
