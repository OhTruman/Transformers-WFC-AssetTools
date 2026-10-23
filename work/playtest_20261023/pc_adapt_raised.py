"""PC adaptation, Gameplay #18 (Integration 2026-10-23): where robots stand > 0.5 m above the visible floor on an authored SIMPLE HULL
(hull_float_audit.py: walkable_raised, kind prop_simple), that placement's pawn collision becomes per-poly render geometry (sections with
EnableCollision, vs_physics.py's per_poly rule), so the standing surface is the visible one. Read-only on ExtractedAssets.

    python pc_adapt_raised.py <MAP>

Base = the live ExtractedAssets/VerticalSlice/Maps/<MAP> files; for Seed its first adaptation (9745 dropped + 40 meshes per-poly) as
frozen in work/overlay_20261023. Every run starts from that base, so reruns never stack. Writes out/pc_adapt/<MAP>/{collision_pawn.glb, physics.json}
and adds / extends pc_adapt_manifest.json ('raised_hulls_per_poly'). Placements are matched by (actor, mesh, gltf matrix).
BlockingVolume / TnForcedDirVolume tops that stand raised are NOT changed here (list only: design call per volume).
"""
import hashlib, json, os, shutil, sys
from collections import Counter
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
from vs_common import ROOT, GLB, read_glb, accessor  # noqa: E402
sys.path.insert(0, HERE)
from seed_pc_adapt import per_poly  # noqa: E402  (same per-poly rule)

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]
def mkey(m): return tuple(np.round(np.array(m, float), 3)) if m else None

def main(mp):
    LIVE = os.path.join(ROOT, 'VerticalSlice', 'Maps', mp); DST = os.path.join(AT, 'out', 'pc_adapt', mp)
    # clean base every run (reruns never stack): Seed = its first adaptation as frozen in overlay_20261023, every other map = live
    SEED0 = os.path.join(AT, 'work', 'overlay_20261023', 'VerticalSlice', 'Maps', mp)
    base = SEED0 if mp == 'MP_IAC_Seed' else LIVE
    live_sha = {f: sha(os.path.join(LIVE, f)) for f in ('collision_pawn.glb', 'physics.json')}
    audit = json.load(open(os.path.join(HERE, 'hull_float', mp + '.json'), encoding='utf-8'))
    sel = {(r['actor'], r['mesh'], mkey(r['matrix'])): r for r in audit['rows'] if r['walkable_raised'] and r['kind'] == 'prop_simple'}
    # Gameplay-confirmed raised stands (probe_positions.py: the simple-hull placement under a reported robot's feet) join the selection
    gc = os.path.join(HERE, 'gameplay_confirmed.json')
    confirmed = [c for c in json.load(open(gc, encoding='utf-8'))['placements'] if c['map'] == mp] if os.path.exists(gc) else []
    for c in confirmed: sel.setdefault((c['actor'], c['mesh'], mkey(c['matrix'])), dict(c, source='gameplay_confirmed'))
    vols = [{k: r[k] for k in ('actor', 'kind', 'raised_m2', 'raised_gap_median_m', 'raised_gap_max_m')} for r in audit['rows']
            if r['walkable_raised'] and r['kind'] != 'prop_simple']
    ph = json.load(open(os.path.join(base, 'physics.json'), encoding='utf-8'))
    gltf_of = {p['mesh']: p.get('gltf') for p in json.load(open(os.path.join(LIVE, 'props.json'), encoding='utf-8'))['props'] if p.get('mesh')}
    poly = {}
    for (_, mesh, _) in sel:
        if mesh not in poly:
            g = gltf_of.get(mesh)
            poly[mesh] = per_poly(g, ph['meshes'][mesh]['sections']) if g and os.path.exists(os.path.join(ROOT, g)) else None
    bj, bbin = read_glb(os.path.join(base, 'collision_pawn.glb'))
    g = GLB('AssetTools pc_adapt_raised pawn collision (%s, PC adaptation)' % mp)
    copied, made, st, hit = {}, {}, Counter(), set()
    for node in bj.get('nodes', []):
        mi = node.get('mesh')
        if mi is None: continue
        ex = node.get('extras') or {}
        k = (node.get('name'), ex.get('mesh'), mkey(node.get('matrix')))
        if ex.get('kind') == 'prop_simple' and k in sel and poly.get(k[1]) is not None:
            mesh = k[1]
            if mesh not in made:
                P, I = poly[mesh]
                made[mesh] = g.mesh(mesh.rsplit('.', 1)[-1] + '_poly', [{'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)},
                                                                       'indices': g.acc(I, 'SCALAR', target=34963)}])
            g.node(dict(node, mesh=made[mesh], extras=dict(ex, kind='prop_per_poly', pc_adaptation='per-poly pawn collision (hull stands > 0.5 m above the visual)')))
            st['props_simple_to_per_poly'] += 1; hit.add(k); continue
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
    tmp = os.path.join(DST, 'collision_pawn.glb.tmp'); g.write(tmp)
    switched = 0
    for r in ph['props']:
        k = (r.get('actor'), r.get('mesh'), mkey(r.get('gltf_matrix')))
        if k in hit and r.get('pawn') == 'simple':
            r['pawn'] = 'per_poly'; r['pc_adaptation'] = {'pawn_original': 'simple', 'reason': 'hull stands > 0.5 m above the visual (Gameplay #18)'}
            switched += 1
    note = 'PC adaptation (not original): per-poly pawn collision on %d placements whose authored simple hulls stand > 0.5 m above the visual floor (Gameplay #18).' % len(hit)
    pa = ph.get('pc_adaptation') or {}
    pa['raised_hulls_per_poly'] = {'note': note, 'placements': len(hit), 'meshes': sorted({k[1] for k in hit})}
    ph['pc_adaptation'] = pa
    json.dump(ph, open(os.path.join(DST, 'physics.json.tmp'), 'w', encoding='utf-8'), indent=1, default=str)
    os.replace(tmp, os.path.join(DST, 'collision_pawn.glb')); os.replace(os.path.join(DST, 'physics.json.tmp'), os.path.join(DST, 'physics.json'))
    mf = os.path.join(DST, 'pc_adapt_manifest.json')
    man = json.load(open(mf, encoding='utf-8')) if os.path.exists(mf) else {'map': mp, 'source_dir': LIVE.replace('\\', '/')}
    man['raised_hulls_per_poly'] = {'generated_by': 'AssetTools/work/playtest_20261023/pc_adapt_raised.py', 'divergence': note,
                                    'base': 'overlay_20261023 (Seed first adaptation)' if base != LIVE else 'live ExtractedAssets',
                                    'audit': 'work/playtest_20261023/hull_float/%s.json' % mp, 'placements_selected': len(sel), 'gameplay_confirmed_selected': len(confirmed),
                                    'placements_switched_glb': len(hit), 'placements_switched_physics': switched,
                                    'meshes_without_render_geometry (left simple)': sorted(m for m, v in poly.items() if v is None),
                                    'raised_volumes (list only, unchanged)': vols, 'glb_stats': dict(st)}
    man['live_files_unchanged'] = live_sha == {f: sha(os.path.join(LIVE, f)) for f in live_sha}
    man['files'] = {f: {'bytes': os.path.getsize(os.path.join(DST, f)), 'sha256_12': sha(os.path.join(DST, f)),
                        'live_bytes': os.path.getsize(os.path.join(LIVE, f))} for f in ('collision_pawn.glb', 'physics.json')}
    man.setdefault('dev_pickup', {'env': 'WFC_OVERLAY_ROOT', 'rule': 'ExtractedAssets-relative files from the overlay when present, else ExtractedAssets'})
    json.dump(man, open(mf, 'w', encoding='utf-8'), indent=1)
    print(mp, 'base', 'seed0' if base != LIVE else 'live', 'selected', len(sel), 'switched', len(hit), switched, 'volumes list-only', len(vols),
          'glb', man['files']['collision_pawn.glb']['bytes'], 'live unchanged', man['live_files_unchanged'])

if __name__ == '__main__':
    main(sys.argv[1])
