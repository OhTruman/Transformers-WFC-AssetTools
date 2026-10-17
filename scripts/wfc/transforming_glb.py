"""Package-7 support (Integration 2026-10-18): skinned GLBs + body-bone keyframes for the MP TnTransformingWorldActor meshes.

  build(mesh_op, animset_op, sequence) -> GLB at manifests/maps/transforming_actors/<mesh>.glb
      the slice character's form (vs_character.build_form: umodel skinned mesh, resolved materials, the one clip retargeted by
      bone name); texture URIs stay relative to ExtractedAssets (no copies)
  bone_globals(gltf_path, clip, times) -> {bone: [4x4 glTF mesh-space global per time]} evaluated from the glTF clip
      (LINEAR translation / scale, slerp rotation; non-animated bones keep their local)
  skinned_bounds(glb, clip, t) -> mesh-space AABB of the linear-blend-skinned vertices at time t (box check)
Read only on ExtractedAssets.
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from vs_common import load_gltf, read_glb, accessor, ROOT  # noqa: E402

AT = os.path.dirname(os.path.dirname(HERE))
OUTDIR = os.path.join(AT, 'manifests', 'maps', 'transforming_actors')

def build(mesh_op, animset_op, sequence):
    import vs_character as VC, materials
    A = materials.assets()
    a = A[animset_op.lower()]
    psa = next(o for o in a['extracted'] if o.endswith('.psa'))
    set_gltf = psa[:-4] + '.anim.gltf'
    os.makedirs(OUTDIR, exist_ok=True)
    VC.OUT = OUTDIR; VC.NAME = 'TransformingActors'
    form = mesh_op.rsplit('.', 1)[-1]
    out, mats, clips, gl = VC.build_form(form, mesh_op, [(animset_op, set_gltf, {sequence: 'transform'})], A)
    return {'glb': out, 'source_mesh_gltf': gl, 'source_anim_gltf': set_gltf, 'clips': clips,
            'materials': [{'slot': m['slot'], 'material': m['material']} for m in mats]}

def _quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)], [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
                     [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]])

def _slerp(a, b, u):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b); d = float(np.dot(a, b))
    if d < 0: b = -b; d = -d
    if d > 0.9995: r = a + u * (b - a); return r / np.linalg.norm(r)
    th = np.arccos(d); return (np.sin((1 - u) * th) * a + np.sin(u * th) * b) / np.sin(th)

def _sample(inp, out, t, path):
    if t <= inp[0]: return out[0]
    if t >= inp[-1]: return out[-1]
    k = int(np.searchsorted(inp, t)) - 1; u = (t - inp[k]) / max(inp[k + 1] - inp[k], 1e-9)
    return _slerp(out[k], out[k + 1], u) if path == 'rotation' else out[k] + u * (out[k + 1] - out[k])

def _load(path):
    if path.lower().endswith('.glb'): return read_glb(path)
    g, bins = load_gltf(path); return g, bins

def clip_of(g, name):
    return next((a for a in g.get('animations', []) if a.get('name') == name), None)

def bone_globals(path, clip, times, bones=None):
    """glTF mesh-space global matrix per node name and time (column-vector 4x4), from the file's node rest + the clip"""
    g, bins = _load(path); nodes = g['nodes']
    par = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    an = clip_of(g, clip) if isinstance(clip, str) else clip
    ch = {}
    if an:
        for c in an['channels']:
            s = an['samplers'][c['sampler']]
            ch[(c['target']['node'], c['target']['path'])] = (accessor(g, bins, s['input']).astype('f8').ravel(), accessor(g, bins, s['output']).astype('f8'))
    out = {}
    for t in times:
        loc = {}
        for i, n in enumerate(nodes):
            T = np.array(n.get('translation', [0, 0, 0]), 'f8'); R = np.array(n.get('rotation', [0, 0, 0, 1]), 'f8'); S = np.array(n.get('scale', [1, 1, 1]), 'f8')
            if (i, 'translation') in ch: T = _sample(*ch[(i, 'translation')], t, 'translation')
            if (i, 'rotation') in ch: R = _sample(*ch[(i, 'rotation')], t, 'rotation')
            if (i, 'scale') in ch: S = _sample(*ch[(i, 'scale')], t, 'scale')
            M = np.eye(4)
            if 'matrix' in n and (i, 'translation') not in ch and (i, 'rotation') not in ch: M = np.array(n['matrix'], 'f8').reshape(4, 4).T
            else: M[:3, :3] = _quat_mat(R) * S[None, :]; M[:3, 3] = T
            loc[i] = M
        glob = {}
        def G(i):
            if i not in glob: glob[i] = (G(par[i]) if i in par else np.eye(4)) @ loc[i]
            return glob[i]
        for i, n in enumerate(nodes):
            nm = n.get('name')
            if nm and (bones is None or nm in bones): out.setdefault(nm, []).append(G(i))
    return out

def skinned_bounds(glb_path, clip, t):
    """AABB (mesh space, glTF metres) of the skinned vertices at clip time t (linear blend skinning with the skin's IBMs)"""
    g, bins = read_glb(glb_path); skin = g['skins'][0]
    joints = skin['joints']; ibm = accessor(g, bins, skin['inverseBindMatrices']).astype('f8').reshape(-1, 4, 4).transpose(0, 2, 1)
    names = [g['nodes'][j]['name'] for j in joints]
    G = bone_globals(glb_path, clip, [t], set(names))
    J = np.stack([G[n][0] @ ibm[k] for k, n in enumerate(names)])
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for m in g['meshes']:
        for p in m['primitives']:
            P = accessor(g, bins, p['attributes']['POSITION']).astype('f8')
            Jn = accessor(g, bins, p['attributes']['JOINTS_0']).astype('i8'); W = accessor(g, bins, p['attributes']['WEIGHTS_0']).astype('f8')
            wa = g['accessors'][p['attributes']['WEIGHTS_0']]
            if wa.get('normalized'): W /= {5121: 255.0, 5123: 65535.0}.get(wa.get('componentType'), 1.0)   # umodel: normalized ubyte
            Ph = np.c_[P, np.ones(len(P))]
            V = np.zeros((len(P), 3))
            for k in range(4):
                V += W[:, k:k + 1] * np.einsum('nij,nj->ni', J[Jn[:, k]], Ph)[:, :3]
            lo = np.minimum(lo, V.min(0)); hi = np.maximum(hi, V.max(0))
    return lo, hi
