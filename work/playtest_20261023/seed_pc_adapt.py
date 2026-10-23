"""PC adaptation of MP_IAC_Seed pawn collision (Integration rebuild-84, 2026-10-23; playtest #10 / #13). Read-only on ExtractedAssets.

Reads the live VerticalSlice/Maps/MP_IAC_Seed/{collision_pawn.glb, physics.json, props.json} and writes ADAPTED COPIES to
AssetTools/out/pc_adapt/MP_IAC_Seed/ (the live files stay byte-identical; Gameplay adopts the copies):
  1. BlockingVolume_9745 (Seed_ART_m, y 16.5 -> 38.2 m) dropped: its collision_pawn node and its physics.json volumes[] record.
     BlockingVolume_7008 (Seed_BASE_m) kept.
  2. The meshes whose authored simple hull is smaller than the visual (seed_cylinders.json, max inset per side > 0.25 m) use per-poly
     pawn collision: render sections with EnableCollision, the same rule vs_physics.py applies to per_poly props. physics.json
     props[].pawn -> 'per_poly' for their placements; weapon / rigid-body representations unchanged.
Every changed record carries a sibling key 'pc_adaptation'. Manifest: pc_adapt_manifest.json (divergence note, lists, sizes).
"""
import hashlib, json, os, sys
from collections import Counter
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
from vs_common import ROOT, GLB, read_glb, load_gltf, accessor  # noqa: E402
SRC = os.path.join(ROOT, 'VerticalSlice', 'Maps', 'MP_IAC_Seed')
DST = os.path.join(AT, 'out', 'pc_adapt', 'MP_IAC_Seed')
DROP_VOLUMES = {'BlockingVolume_9745'}
INSET_M = 0.25
NOTE = ('PC adaptation (not original): BlockingVolume_9745 removed from pawn collision and per-poly pawn collision on %d meshes whose '
        'authored simple hulls are smaller than their visuals; original cooked data in ExtractedAssets/VerticalSlice/Maps/MP_IAC_Seed.')

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]

def per_poly(gltf_rel, sections):
    gg, bins = load_gltf(os.path.join(ROOT, gltf_rel))
    en = {s['index']: s['enable_collision'] for s in sections}
    Ps, Is, base = [], [], 0
    for pr in gg['meshes'][0]['primitives']:
        if not en.get(pr.get('material', 0), True) or 'indices' not in pr: continue
        P = accessor(gg, bins, pr['attributes']['POSITION']).astype('f4')
        if not len(P): continue
        Ps.append(P); Is.append(accessor(gg, bins, pr['indices']).astype('u4') + base); base += len(P)
    return (np.concatenate(Ps), np.concatenate(Is)) if Ps else None

def main():
    before = {f: sha(os.path.join(SRC, f)) for f in ('collision_pawn.glb', 'physics.json', 'props.json')}
    cyl = json.load(open(os.path.join(HERE, 'seed_cylinders.json'), encoding='utf-8'))['rows']
    target = {r['mesh']: r for r in cyl if r['max_inset_per_side_m'] > INSET_M}
    ph = json.load(open(os.path.join(SRC, 'physics.json'), encoding='utf-8'))
    gltf_of = {p['mesh']: p.get('gltf') for p in json.load(open(os.path.join(SRC, 'props.json'), encoding='utf-8'))['props'] if p.get('mesh')}
    poly = {}
    for mesh in sorted(target):
        g = gltf_of.get(mesh)
        poly[mesh] = per_poly(g, ph['meshes'][mesh]['sections']) if g and os.path.exists(os.path.join(ROOT, g)) else None
    missing = sorted(m for m, v in poly.items() if v is None)
    # ---- collision_pawn.glb: copy every node, drop the volume, swap the simple-hull mesh of the targeted props
    bj, bbin = read_glb(os.path.join(SRC, 'collision_pawn.glb'))
    g = GLB('AssetTools seed_pc_adapt pawn collision (MP_IAC_Seed, PC adaptation)')
    copied, made, st = {}, {}, Counter()
    for node in bj.get('nodes', []):
        mi = node.get('mesh')
        if mi is None: continue
        ex = node.get('extras') or {}
        if node.get('name') in DROP_VOLUMES: st['volume_nodes_dropped'] += 1; continue
        mesh = ex.get('mesh')
        if ex.get('kind') == 'prop_simple' and mesh in target and poly.get(mesh) is not None:
            if mesh not in made:
                P, I = poly[mesh]
                made[mesh] = g.mesh(mesh.rsplit('.', 1)[-1] + '_poly', [{'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)},
                                                                       'indices': g.acc(I, 'SCALAR', target=34963)}])
            n = dict(node, mesh=made[mesh], extras=dict(ex, kind='prop_per_poly', pc_adaptation='per-poly pawn collision (hull smaller than visual)'))
            g.node(n); st['props_simple_to_per_poly'] += 1; continue
        if mi not in copied:
            src = bj['meshes'][mi]; prims = []
            for pr in src['primitives']:
                P = accessor(bj, bbin, pr['attributes']['POSITION']).astype('f4')
                p2 = {'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)}}
                if 'indices' in pr: p2['indices'] = g.acc(accessor(bj, bbin, pr['indices']).astype('u4'), 'SCALAR', target=34963)
                prims.append(p2)
            copied[mi] = g.mesh(src.get('name', ''), prims)
        g.node(dict(node, mesh=copied[mi])); st['nodes_copied'] += 1
    os.makedirs(DST, exist_ok=True)
    gp = os.path.join(DST, 'collision_pawn.glb'); g.write(gp)
    # ---- physics.json copy
    vols = [v for v in ph['volumes'] if v['actor'] in DROP_VOLUMES]
    ph['volumes'] = [v for v in ph['volumes'] if v['actor'] not in DROP_VOLUMES]
    for r in ph['props']:
        if r.get('mesh') in target and r.get('pawn') == 'simple' and poly.get(r['mesh']) is not None:
            r['pawn'] = 'per_poly'; r['pc_adaptation'] = {'pawn_original': 'simple', 'reason': 'authored hull smaller than visual'}
    ph['pc_adaptation'] = {'note': NOTE % len(made), 'dropped_volumes': [v['actor'] for v in vols], 'per_poly_pawn_meshes': sorted(made)}
    pp = os.path.join(DST, 'physics.json'); json.dump(ph, open(pp, 'w', encoding='utf-8'), indent=1, default=str)
    after = {f: sha(os.path.join(SRC, f)) for f in before}
    man = {'map': 'MP_IAC_Seed', 'generated_by': 'AssetTools/work/playtest_20261023/seed_pc_adapt.py', 'divergence': NOTE % len(made),
           'decided_by': 'Integration rebuild-84, 2026-10-23 (playtest #10 / #13)', 'source_dir': SRC.replace('\\', '/'),
           'live_files_unchanged': before == after, 'live_sha256_12': before,
           'files': {os.path.basename(p): {'bytes': os.path.getsize(p), 'sha256_12': sha(p),
                                           'live_bytes': os.path.getsize(os.path.join(SRC, os.path.basename(p)))} for p in (gp, pp)},
           'dropped_volumes': [{'actor': v['actor'], 'sublevel': v.get('sublevel'), 'class': v['class']} for v in vols],
           'kept_volumes_note': 'BlockingVolume_7008 (Seed_BASE_m, y -8.9 -> 18.6 m) kept as cooked',
           'per_poly_pawn_meshes': [{'mesh': m, 'placements_switched': sum(1 for r in ph['props'] if r.get('mesh') == m and r.get('pc_adaptation')),
                                     'triangles': int(len(poly[m][1]) // 3), 'hull_inset_per_axis_m': target[m]['inset_per_axis_m']} for m in sorted(made)],
           'meshes_without_render_geometry (left simple)': missing, 'glb_stats': dict(st)}
    json.dump(man, open(os.path.join(DST, 'pc_adapt_manifest.json'), 'w', encoding='utf-8'), indent=1)
    print(json.dumps({k: man[k] for k in ('live_files_unchanged', 'files', 'dropped_volumes', 'glb_stats', 'meshes_without_render_geometry (left simple)')}, indent=1))
    print('per-poly meshes', len(made), 'triangles', sum(r['triangles'] for r in man['per_poly_pawn_meshes']))

if __name__ == '__main__':
    main()
