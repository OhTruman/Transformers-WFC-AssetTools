"""Gameplay #18 reconciliation: at given robot feet positions (glTF m), the supporting pawn-collision surface (highest collision_pawn.glb
triangle at or below feet + 0.3 m, the node that supplies it) and the visible floor (highest world.glb triangle at or below feet + 0.05 m;
any visible surface within (feet + 0.05, feet + 0.6] reported as cover). Read-only. Prints one line per position.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc')); sys.path.insert(0, HERE)
import map_structure_audit as MSA  # noqa: E402
from hull_float_audit import bary_y  # noqa: E402
VSM = r'F:\Transformers Rebuild\ExtractedAssets\VerticalSlice\Maps'
POS = {'MP_UND_Gorge': [(-68.11, -4.05, -55.05), (-57.27, 12.20, -123.69), (-57.48, 12.20, -123.70), (-57.13, 12.94, -120.64)],
       'MP_ORB_Debris': [(-223.16, 132.99, 55.79), (-221.33, 132.99, 54.79), (72.79, 124.67, -80.01),
                         (-164.79, 133.37, -155.0), (-169.07, 133.37, -160.0), (-165.93, 133.37, -165.0), (-163.13, 133.37, -158.0), (-162.54, 133.37, -162.0)],
       'MP_IAC_Rust': [(-87.56, 19.63, -145.54)]}

def surfaces(path, P, R=0.0):
    out = []
    for j, n, mat, T, agree, det in MSA.node_tris(path):
        if not len(T): continue
        if (n.get('extras') or {}).get('hidden_game'): continue
        for p in P:
            k = (T[:, :, 0].min(1) <= p[0]) & (T[:, :, 0].max(1) >= p[0]) & (T[:, :, 2].min(1) <= p[2]) & (T[:, :, 2].max(1) >= p[2])
            for t in T[k]:
                y = bary_y(t, np.array([p[0]]), np.array([p[2]]))[0]
                if not np.isnan(y): out.append((p, float(y), n.get('name'), (n.get('extras') or {}).get('kind'), ((n.get('extras') or {}).get('mesh') or '').split('.')[-1],
                                                (j['materials'][mat].get('name') if mat is not None and 'materials' in j else None),
                                                (n.get('extras') or {}).get('mesh'), n.get('matrix')))
    return out

def main():
    confirmed = []
    for mp, P in POS.items():
        D = os.path.join(VSM, mp)
        col = surfaces(os.path.join(D, 'collision_pawn.glb'), P); vis = surfaces(os.path.join(D, 'world.glb'), P)
        for p in P:
            c = [s for s in col if s[0] == p and s[1] <= p[1] + 0.3]; v = [s for s in vis if s[0] == p and s[1] <= p[1] + 0.05]
            cov = [s for s in vis if s[0] == p and p[1] + 0.05 < s[1] <= p[1] + 0.6]
            sc = max(c, key=lambda s: s[1]) if c else None; sv = max(v, key=lambda s: s[1]) if v else None
            print(mp, p, '| support', (round(sc[1], 2), sc[2], sc[3], sc[4]) if sc else None,
                  '| visual', (round(sv[1], 2), sv[2], sv[4], sv[5]) if sv else None,
                  '| support-visual', round(sc[1] - sv[1], 2) if sc and sv else None, '| cover', [(round(s[1], 2), s[4]) for s in cov][:2])
            if sc and sv and sc[3] == 'prop_simple' and sc[1] - sv[1] > 0.5 and not cov:
                confirmed.append({'map': mp, 'position_gltf': list(p), 'actor': sc[2], 'mesh': sc[6], 'matrix': sc[7],
                                  'support_y_m': round(sc[1], 2), 'visual_y_m': round(sv[1], 2), 'gap_m': round(sc[1] - sv[1], 2)})
    import json
    json.dump({'generated_by': 'AssetTools/work/playtest_20261023/probe_positions.py',
               'source': 'Gameplay #18 robot feet positions (rebuild-gameplay-b9, 2026-10-23)', 'placements': confirmed},
              open(os.path.join(HERE, 'gameplay_confirmed.json'), 'w', encoding='utf-8'), indent=1)
    print('gameplay-confirmed simple-hull placements:', len(confirmed))

if __name__ == '__main__':
    main()
