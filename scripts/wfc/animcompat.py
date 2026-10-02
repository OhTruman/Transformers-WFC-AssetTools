"""Skeleton compatibility of AnimSets vs a skeletal mesh, beyond name matching.

UE3 AnimSets store only TrackBoneNames, so the hierarchy is the mesh's. Two tests:
  coverage   : fraction of the AnimSet's track bones present in the mesh skeleton
  proportion : for bones whose translation is keyed, |t_anim(frame0)| vs |t_rest|
               (bone lengths) over the full-body (non-additive) sequences; a set
               authored for a different skeleton class (e.g. LightMedium vs
               HeavyMedium) shows large relative errors even with identical names.
Verdict: compatible if coverage == 1 and median length error <= 5%.
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import psa2gltf, extract  # noqa: E402

ROOT = os.path.dirname(extract.OUT)

def mesh_skeleton(gltf_rel):
    g = json.load(open(os.path.join(ROOT, gltf_rel), encoding='utf-8'))
    nodes = g['nodes']; joints = g['skins'][0]['joints']
    rest = {nodes[j]['name']: np.array(nodes[j].get('translation', [0, 0, 0])) for j in joints}
    return rest

def evaluate(psa_rel, rest):
    bones, seqs, keys = psa2gltf.read_psa(os.path.join(ROOT, psa_rel))
    names = [b['name'] for b in bones]; nb = len(names)
    P, _ = psa2gltf.to_gltf_space(keys, nb)
    coverage = sum(1 for n in names if n in rest) / nb
    errs = []
    for s in seqs:
        if s['frames'] <= 0 or s['name'].upper().startswith('ADD'): continue
        f0 = s['first'] * nb
        for bi, n in enumerate(names):
            if n not in rest or bi == 0: continue
            t = P[f0 + bi]; r = np.linalg.norm(rest[n])
            if np.any(t != 0) and r > 1e-4:
                errs.append(abs(np.linalg.norm(t) - r) / r)
    med = float(np.median(errs)) if errs else None
    within = float(np.mean(np.array(errs) <= 0.05)) if errs else None
    ok = coverage == 1.0 and (med is not None and med <= 0.05)
    return {'track_bones': nb, 'coverage': round(coverage, 4), 'length_samples': len(errs),
            'median_length_error': None if med is None else round(med, 4),
            'within_5pct': None if within is None else round(within, 4),
            'compatible': ok, 'sequences': [s['name'] for s in seqs]}

if __name__ == '__main__':
    rest = mesh_skeleton(sys.argv[1])
    for p in sys.argv[2:]:
        print(p, json.dumps({k: v for k, v in evaluate(p, rest).items() if k != 'sequences'}))
