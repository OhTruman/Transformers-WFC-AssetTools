"""Candidate refinement of the #18 adaptation for BROKEN / DEBRIS FLOORS (Experimental soak 2026-10-23: robots sink 1.1-1.3 m into the
cracks of per-poly CanyonFloor_B_Destroy / CanyonFloor_B; the nav loses those floors too). For the listed meshes, every placement that
the #18 pass switched to per-poly goes back to its AUTHORED simple hull, translated down by the placement's measured raised gap
(audit raised_gap_median_m, else the Gameplay-confirmed gap), so the crack-free hull top meets the visible floor. Read-only on
ExtractedAssets; base = overlay_20261023e. Writes out/pc_adapt/_candidates/lowered_hulls/VerticalSlice/Maps/<MAP>/{collision_pawn.glb,
physics.json} (overlay layout, not frozen) + lowered_hulls.json.

    python lowered_hulls.py <MAP>:<mesh substring>[,...] [...]   e.g. MP_ORB_Debris:CanyonFloor_B_Destroy,DebrisFloor_01 MP_UND_Gorge:CanyonFloor_B_STAT
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
from vs_common import ROOT, GLB, read_glb, accessor  # noqa: E402
OVE = os.path.join(AT, 'work', 'overlay_20261023e', 'VerticalSlice', 'Maps')
REVERT = '--revert' in sys.argv
# --revert: restore the authored hull unchanged (a uniform drop sinks hulls whose gap varies per spot: Debris (-134.9, 31.4) hull top
# = visual top there, so lowering by the placement median put it 0.76 m under the visible floor)
OUT = os.path.join(AT, 'out', 'pc_adapt', '_candidates', 'reverted_broken_floors' if REVERT else 'lowered_hulls', 'VerticalSlice', 'Maps')
def mkey(m): return tuple(np.round(np.array(m, float), 3)) if m else None

def one(mp, subs):
    B = os.path.join(OVE, mp); L = os.path.join(ROOT, 'VerticalSlice', 'Maps', mp)
    aud = json.load(open(os.path.join(HERE, 'hull_float', mp + '.json'), encoding='utf-8'))['rows']
    gap = {(r['actor'], r['mesh'], mkey(r['matrix'])): r['raised_gap_median_m'] for r in aud if r.get('raised_gap_median_m')}
    for c in json.load(open(os.path.join(HERE, 'gameplay_confirmed.json'), encoding='utf-8'))['placements']:
        if c['map'] == mp: gap.setdefault((c['actor'], c['mesh'], mkey(c['matrix'])), c['gap_m'])
    lj, lb = read_glb(os.path.join(L, 'collision_pawn.glb'))
    hull = {(n.get('name'), (n.get('extras') or {}).get('mesh'), mkey(n.get('matrix'))): n for n in lj['nodes']
            if (n.get('extras') or {}).get('kind') == 'prop_simple'}
    bj, bb = read_glb(os.path.join(B, 'collision_pawn.glb'))
    g = GLB('AssetTools lowered_hulls candidate (%s)' % mp); cache = {}; done = []
    def mesh_of(j, b, mi, tag):
        if (tag, mi) not in cache:
            prims = []
            for pr in j['meshes'][mi]['primitives']:
                P = accessor(j, b, pr['attributes']['POSITION']).astype('f4'); p2 = {'attributes': {'POSITION': g.acc(P, 'VEC3', True, 34962)}}
                if 'indices' in pr: p2['indices'] = g.acc(accessor(j, b, pr['indices']).astype('u4'), 'SCALAR', target=34963)
                prims.append(p2)
            cache[(tag, mi)] = g.mesh(j['meshes'][mi].get('name', ''), prims)
        return cache[(tag, mi)]
    for n in bj['nodes']:
        if n.get('mesh') is None: continue
        ex = n.get('extras') or {}; k = (n.get('name'), ex.get('mesh'), mkey(n.get('matrix')))
        if 'hull stands' in str(ex.get('pc_adaptation')) and any(s in str(ex.get('mesh')) for s in subs) and k in hull and gap.get(k):
            h = hull[k]; d = 0.0 if REVERT else float(gap[k]); M = list(h['matrix']); M[13] -= d          # glTF column-major: [13] = translation Y
            g.node(dict(h, mesh=mesh_of(lj, lb, h['mesh'], 'live'), matrix=M,
                        extras=dict(h.get('extras') or {}, kind='prop_simple', pc_adaptation=('authored hull restored (broken floor: per-poly cracks; #18 refinement)' if REVERT else 'authored hull lowered %.2f m to the visual top (broken floor; #18 refinement)' % d))))
            done.append({'actor': k[0], 'mesh': k[1], 'lowered_m': round(d, 2)}); continue
        g.node(dict(n, mesh=mesh_of(bj, bb, n['mesh'], 'base')))
    od = os.path.join(OUT, mp); os.makedirs(od, exist_ok=True); g.write(os.path.join(od, 'collision_pawn.glb'))
    ph = json.load(open(os.path.join(B, 'physics.json'), encoding='utf-8')); keys = {(x['actor'], x['mesh']) for x in done}
    for r in ph['props']:
        if (r.get('actor'), r.get('mesh')) in keys and r.get('pawn') == 'per_poly' and 'hull stands' in str((r.get('pc_adaptation') or {}).get('reason')):
            r['pawn'] = 'simple'; r['pc_adaptation'] = {'pawn_original': 'simple', 'reason': 'authored hull restored (broken floor; #18 refinement)' if REVERT else 'authored hull lowered to the visual top (broken floor; #18 refinement)'}
    json.dump(ph, open(os.path.join(od, 'physics.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(mp, 'lowered', len(done), done[:6])
    return done

if __name__ == '__main__':
    rep = {}
    for a in [x for x in sys.argv[1:] if not x.startswith('--')]:
        mp, s = a.split(':', 1); rep[mp] = one(mp, s.split(','))
    json.dump({'generated_by': 'AssetTools/work/playtest_20261023/lowered_hulls.py', 'base': 'overlay_20261023e', 'maps': rep},
              open(os.path.join(os.path.dirname(OUT), '..', 'reverted_broken_floors.json' if REVERT else 'lowered_hulls.json'), 'w', encoding='utf-8'), indent=1)
