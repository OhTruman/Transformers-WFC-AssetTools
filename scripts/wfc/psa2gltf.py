"""ActorX .psa (from umodel) -> glTF 2.0 animation files (.anim.gltf + .bin)

umodel's command-line glTF export cannot write animations, so AnimSets are
exported as .psa and converted here using the SAME coordinate conventions as
umodel's glTF mesh exporter (UEViewer Exporters/ExportGLTF.cpp), so the output
retargets by bone name onto the extracted skeletal-mesh glTFs:
  psa key  : umodel writes MIRROR_MESH keys  q'=(x,-y,z,-w)  p'=(x,-y,z)
  glTF     : swap Y/Z, scale cm->m (0.01), root-bone rotation conjugated
Bones without a track come out of umodel as p=(0,0,0)/q=identity for every
frame; such constant channels are omitted so the mesh rest pose applies.
Rest pose for skeleton nodes is taken from the AnimSet's preview skeletal mesh
glTF when available (assets.json), otherwise identity.

Output: next to each .psa -> <name>.anim.gltf/.anim.bin; index in
AssetTools/manifests/extracted/animations_gltf.jsonl
"""
import json, os, struct, sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract  # noqa: E402

ROOT = os.path.dirname(extract.OUT)

def read_psa(path):
    d = open(path, 'rb').read(); o = 0; ch = {}
    while o + 32 <= len(d):
        cid = d[o:o + 20].split(b'\0')[0].decode('latin-1')
        sz, cnt = struct.unpack_from('<ii', d, o + 24)
        ch[cid] = (o + 32, sz, cnt); o += 32 + sz * cnt
    o, sz, n = ch['BONENAMES']
    bones = []
    for i in range(n):
        b = d[o + i * sz:o + (i + 1) * sz]
        name = b[:64].split(b'\0')[0].decode('latin-1')
        _, _, parent = struct.unpack_from('<3i', b, 64)
        bones.append({'name': name, 'parent': parent if i else -1})
    o, sz, n = ch['ANIMINFO']
    seqs = []
    for i in range(n):
        b = d[o + i * sz:o + (i + 1) * sz]
        name = b[:64].split(b'\0')[0].decode('latin-1')
        group = b[64:128].split(b'\0')[0].decode('latin-1')
        total_bones, root_inc, kcomp, kquot = struct.unpack_from('<4i', b, 128)
        kred, track_time, rate = struct.unpack_from('<3f', b, 144)
        start_bone, first_frame, nframes = struct.unpack_from('<3i', b, 156)
        seqs.append({'name': name, 'group': group, 'rate': rate, 'first': first_frame, 'frames': nframes})
    o, sz, n = ch['ANIMKEYS']
    keys = np.frombuffer(d, dtype='<f4', count=n * 8, offset=o).reshape(n, 8)
    return bones, seqs, keys

def to_gltf_space(keys, nb):
    p = keys[:, 0:3].copy(); q = keys[:, 3:7].copy()
    p[:, 1] *= -1; q[:, 1] *= -1; q[:, 3] *= -1           # undo MIRROR_MESH
    p = p[:, [0, 2, 1]] * 0.01                               # swap Y/Z, cm -> m
    q = q[:, [0, 2, 1, 3]]
    root = np.arange(len(q)) % nb == 0
    q[root, :3] *= -1                                        # conjugate root
    return p, q

def rest_pose(mesh_gltf):
    if not mesh_gltf or not os.path.exists(mesh_gltf): return {}
    g = json.load(open(mesh_gltf, encoding='utf-8'))
    return {n.get('name'): n for n in g.get('nodes', [])}

def convert(args):
    psa, mesh_gltf = args[:2]
    out_base = args[2] if len(args) > 2 else None     # optional: write <out_base>.anim.gltf/.bin elsewhere (default: next to the .psa)
    bones, seqs, keys = read_psa(psa)
    nb = len(bones)
    P, Q = to_gltf_space(keys, nb)
    rest = rest_pose(mesh_gltf)
    blob = bytearray(); views = []; accs = []
    def add(arr, typ, minmax=False):
        arr = np.ascontiguousarray(arr, dtype='<f4')
        while len(blob) % 4: blob.append(0)
        views.append({'buffer': 0, 'byteOffset': len(blob), 'byteLength': arr.nbytes})
        blob.extend(arr.tobytes())
        a = {'bufferView': len(views) - 1, 'componentType': 5126, 'count': int(arr.shape[0]), 'type': typ}
        if minmax: a['min'] = [float(arr.min())]; a['max'] = [float(arr.max())]
        accs.append(a); return len(accs) - 1
    # umodel's PSA carries no hierarchy (all parents 0; UE3 AnimSets only store
    # TrackBoneNames). Take the hierarchy from the rest-pose mesh: parent = nearest
    # mesh ancestor that is also an animated track, else the track root.
    mesh_parent = {}
    if rest:
        g = json.load(open(mesh_gltf, encoding='utf-8'))
        for n in g['nodes']:
            for c in n.get('children', []):
                mesh_parent[g['nodes'][c].get('name')] = n.get('name')
    names = [b['name'] for b in bones]
    pos = {n: i for i, n in enumerate(names)}
    parent_of = []
    for i, b in enumerate(bones):
        p = -1
        if i and mesh_parent:
            a = mesh_parent.get(b['name'])
            while a is not None and a not in pos:
                a = mesh_parent.get(a)
            p = pos.get(a, 0) if a is not None else 0
        elif i:
            p = 0
        parent_of.append(p)
    nodes = []
    for i, b in enumerate(bones):
        n = {'name': b['name']}
        r = rest.get(b['name'])
        if r:
            for k in ('translation', 'rotation', 'scale'):
                if k in r: n[k] = r[k]
        kids = [j for j in range(nb) if parent_of[j] == i and j != i]
        if kids: n['children'] = kids
        nodes.append(n)
    anims = []
    for s in seqs:
        f0, nf = s['first'], s['frames']
        if nf <= 0: continue
        rate = s['rate'] if s['rate'] > 1e-3 else 30.0
        t = add(np.arange(nf, dtype='f4') / rate, 'SCALAR', True)
        samplers, channels = [], []
        for bi in range(nb):
            idx = (f0 + np.arange(nf)) * nb + bi
            pk, qk = P[idx], Q[idx]
            if np.any(pk != 0):
                samplers.append({'input': t, 'output': add(pk, 'VEC3'), 'interpolation': 'LINEAR'})
                channels.append({'sampler': len(samplers) - 1, 'target': {'node': bi, 'path': 'translation'}})
            ident = np.all(qk[:, :3] == 0) and np.all(np.abs(qk[:, 3]) == 1)
            if not ident:
                samplers.append({'input': t, 'output': add(qk, 'VEC4'), 'interpolation': 'LINEAR'})
                channels.append({'sampler': len(samplers) - 1, 'target': {'node': bi, 'path': 'rotation'}})
        if channels:
            anims.append({'name': s['name'], 'samplers': samplers, 'channels': channels})
    base = (out_base or psa[:-4]) + '.anim'
    g = {'asset': {'version': '2.0', 'generator': 'AssetTools psa2gltf (umodel glTF conventions)'},
         'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': nodes, 'animations': anims,
         'buffers': [{'uri': os.path.basename(base) + '.bin', 'byteLength': len(blob)}],
         'bufferViews': views, 'accessors': accs,
         'extras': {'source_psa': os.path.relpath(psa, ROOT).replace('\\', '/'),
                    'rest_pose_from': os.path.relpath(mesh_gltf, ROOT).replace('\\', '/') if rest else None,
                    'sequences': [{'name': s['name'], 'frames': s['frames'], 'rate': s['rate']} for s in seqs]}}
    open(base + '.bin', 'wb').write(blob)
    json.dump(g, open(base + '.gltf', 'w'), indent=0)
    return {'psa': g['extras']['source_psa'], 'output': os.path.relpath(base + '.gltf', ROOT).replace('\\', '/'),
            'bones': nb, 'sequences': len(anims), 'rest_pose_from': g['extras']['rest_pose_from']}

def main():
    assets = json.load(open(os.path.join(extract.MANI, 'assets.json'), encoding='utf-8'))['assets']
    mesh_gl = {a['object_path']: next((o for o in a['extracted'] if o.endswith('.gltf')), None)
               for a in assets if a['class'] == 'SkeletalMesh'}
    work = []
    for a in assets:
        if a['class'] != 'AnimSet': continue
        psa = next((o for o in a['extracted'] if o.endswith('.psa')), None)
        if not psa: continue
        mesh = a.get('preview_skeletal_mesh')
        if mesh not in mesh_gl or not mesh_gl.get(mesh):
            mesh = next((m for m in a.get('compatible_skeletal_meshes', []) if mesh_gl.get(m)), None)
        work.append((os.path.join(ROOT, psa), os.path.join(ROOT, mesh_gl[mesh]) if mesh and mesh_gl.get(mesh) else None))
    # several AnimSet records can map to one .psa file: convert each file once
    uniq = {}
    for w in work:
        uniq.setdefault(w[0], w)
    work = list(uniq.values())
    res = []
    with ProcessPoolExecutor() as ex:
        for r in ex.map(convert, work, chunksize=4): res.append(r)
    with open(os.path.join(extract.MANI, 'extracted', 'animations_gltf.jsonl'), 'w') as f:
        for r in res: f.write(json.dumps(r) + '\n')
    print('converted %d animsets, %d sequences, %d with rest pose' % (
        len(res), sum(r['sequences'] for r in res), sum(1 for r in res if r['rest_pose_from'])))

if __name__ == '__main__':
    main()
