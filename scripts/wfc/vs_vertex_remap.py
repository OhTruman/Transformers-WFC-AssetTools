"""Cooked LOD0 vertex index per glTF vertex, for meshes whose glTF vertex count differs from the cooked count
-> ExtractedAssets/VerticalSlice/Maps/<MAP>/vertex_remap.json   (vs_map then writes it into world.glb as _WFC_SRCVERT)

  python vs_vertex_remap.py MAP

Why: umodel's glTF export writes each section as its own primitive holding only the vertices that section references,
re-indexed. When sections share cooked vertices (TunnelPipeA_Debri_B_EdgeGlow_STAT: section 1 spans cooked 18..1575 and
shares 40 vertices with section 0), the glTF has more vertices than the cooked LOD (1616 vs 1576) and the per-vertex
FLightMap1D samples (cooked order, vertex_lightmaps.json) can no longer be bound by position in the vertex array.

How (exact, no float matching): umodel's ActorX export of the same mesh (.pskx) keeps the cooked vertex order (one wedge per
cooked vertex; VTXW count == cooked LOD0 vertex count) and writes the faces of each section in index-buffer order, as the glTF
does. Pairing glTF triangle k of primitive p with pskx face k of material p gives glTF vertex -> wedge (= cooked vertex). The
corner permutation is solved per primitive (umodel's pskx swaps corners; (1,0,2) on WFC) and must be conflict-free; UVs are
checked to be identical. Meshes failing a check are reported, never guessed.

Targets: vertex_lightmaps.json records with vertex_count_match == false (sample count != glTF vertex count).
"""
import glob, itertools, json, os, shutil, struct, subprocess, sys, tempfile
from collections import OrderedDict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract, objtree  # noqa: E402
from vs_common import ROOT, VS, accessor, load_gltf  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)

def read_pskx(path):
    d = open(path, 'rb').read(); o = 0; ch = {}
    while o + 32 <= len(d):
        n = d[o:o + 20].split(b'\0')[0].decode('ascii', 'replace'); _, sz, cnt = struct.unpack_from('<3i', d, o + 20)
        ch[n] = (o + 32, sz, cnt); o += 32 + sz * cnt
    o, sz, c = ch['VTXW0000']
    W = [struct.unpack_from('<IffB', d, o + i * sz) for i in range(c)]
    key = 'FACE3200' if 'FACE3200' in ch else 'FACE0000'
    o, sz, c = ch[key]
    F = [struct.unpack_from('<3IBB' if key == 'FACE3200' else '<3HBB', d, o + i * sz) for i in range(c)]
    return W, F

def remap(mesh, gltf_rel, pkg):
    tmp = tempfile.mkdtemp(prefix='vremap_')
    try:
        subprocess.run([extract.UMODEL, '-export', '-path=%s' % extract.COOKED, '-game=trans', '-out=%s' % tmp, '-notex', pkg + '.xxx', '-obj=%s' % mesh.rsplit('.', 1)[-1]], capture_output=True, timeout=300)
        ps = [p for p in glob.glob(os.path.join(tmp, '**', mesh.rsplit('.', 1)[-1] + '.pskx'), recursive=True)]
        if not ps: return None, 'pskx export failed'
        W, F = read_pskx(ps[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    g, bins = load_gltf(os.path.join(ROOT, gltf_rel))
    prims = []
    for pi, pr in enumerate(g['meshes'][0]['primitives']):
        n = g['accessors'][pr['attributes']['POSITION']]['count']
        if n == 0: prims.append([]); continue
        idx = accessor(g, bins, pr['indices']).reshape(-1, 3)
        fs = [f for f in F if f[3] == pi]
        if len(fs) != len(idx): return None, 'primitive %d: %d glTF triangles vs %d pskx faces' % (pi, len(idx), len(fs))
        for perm in itertools.permutations(range(3)):
            m = -np.ones(n, int); bad = 0
            for t, fc in zip(idx, fs):
                for j in range(3):
                    w = fc[perm[j]]; v = t[j]
                    if m[v] < 0: m[v] = w
                    elif m[v] != w: bad += 1
            if bad == 0: break
        if bad or (m < 0).any(): return None, 'primitive %d: no conflict-free corner permutation' % pi
        if 'TEXCOORD_0' in pr['attributes']:
            uv = accessor(g, bins, pr['attributes']['TEXCOORD_0'])
            if np.abs(np.array([[W[k][1], W[k][2]] for k in m]) - uv).max() > 1e-5:
                return None, 'primitive %d: UV check failed' % pi
        prims.append([int(k) for k in m])
    return {'gltf': gltf_rel, 'cooked_vertices': len(W), 'corner_permutation': list(perm), 'primitives': prims}, None

def main():
    vl = json.load(open(os.path.join(OUT, 'vertex_lightmaps.json'), encoding='utf-8'))
    recs = vl['vertex_lightmaps']; recs = recs.values() if isinstance(recs, dict) else recs
    props = {p['mesh']: p.get('gltf') for p in json.load(open(os.path.join(OUT, 'props.json'), encoding='utf-8'))['props'] if p.get('mesh')}
    targets = sorted({r['mesh'] for r in recs if r.get('vertex_count_match') is False and r.get('mesh')})
    inv = objtree.inv()
    meshes, failures = OrderedDict(), OrderedDict()
    for mesh in targets:
        row = inv.execute("SELECT package FROM exports WHERE opath = ? AND class = 'StaticMesh' ORDER BY serial_size DESC, package",
                          (mesh,)).fetchone()
        if not row or not props.get(mesh): failures[mesh] = 'no cooked package / glTF'; continue
        r, err = remap(mesh, props[mesh], row[0])
        if r: r['package'] = row[0]; meshes[mesh] = r
        else: failures[mesh] = err
        print(mesh, 'OK' if r else err)
    json.dump(OrderedDict([
        ('map', MAP), ('generated_by', 'AssetTools/scripts/wfc/vs_vertex_remap.py'),
        ('attribute', '_WFC_SRCVERT (UNSIGNED_INT SCALAR) on these meshes\' world.glb primitives = cooked LOD0 vertex index; index '
                      'vertex_lightmaps samples through it'),
        ('primitive_order', 'glTF primitive order of the mesh (world.glb keeps it; empty primitives are [])'),
        ('meshes', meshes), ('failures', failures)]), open(os.path.join(OUT, 'vertex_remap.json'), 'w', encoding='utf-8'), indent=0)
    print('%s: %d remapped, %d failed' % (MAP, len(meshes), len(failures)))

if __name__ == '__main__':
    main()
