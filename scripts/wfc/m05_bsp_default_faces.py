"""BSP faces that render with EngineMaterials.DefaultMaterial in MP_IAC_Streets: provenance + occlusion test (M05).

Provenance: the FBspSurf.Material and the cooked FModelElement.Material of these nodes both reference
EngineMaterials.DefaultMaterial; the source brushes' Models are cooked as 124-byte stubs without Polys, so no other
authored material assignment exists anywhere in the cook.
Occlusion: for each default-material polygon node, sample points (centroid + vertices pulled 15 % toward the centroid);
from each sample (started 1 cm behind the face) cast a ray along the face normal (front side) against the placed
static-mesh triangles of world.glb (corrected SMCA transforms, checkpoint 8d8195e+). A sample is COVERED when a mesh
triangle is hit within COVER_M metres. Node verdicts: hidden (all samples covered), partial, exposed.
Occluders exclude the sky dome and the 126 unlit components (light planes / beams; additive). Grid: triangles spanning
>64 cells are tested on every ray; in-script memory guard (8 GB).
Play visibility: viewpoints = every navigation node and every player start (deduplicated) at eye height (+EYE_UU); a face is VISIBLE IN PLAY
when some viewpoint on its front side within VIEW_M metres has an unobstructed line (placed static meshes + every other
rendered BSP polygon, uniform-grid ray caster) to one of its samples. This is a lower bound of the original visibility
set (players also jump / fly in vehicle form), so "never visible" is HIGH confidence, not CONFIRMED.
Output: AssetTools/manifests/streets_bsp_default_faces.json
"""
import json, os, sys
from collections import Counter, defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import objtree, bsp  # noqa: E402
from vs_common import VS, read_glb  # noqa: E402
from m03_common import write, CONF, HIGH, PART, map_arg, map_out, map_levels, bsp_level  # noqa: E402

MAP = map_arg()                      # positional map name (default MP_IAC_Streets)
LV_ = map_levels(MAP)
LV = bsp_level(MAP, LV_)
GLB = os.path.join(VS, 'Maps', MAP, 'world.glb')
COVER_M = 0.64          # 64 UU in front of the face
EYE_UU = 200.0
VIEW_M = 200.0
# WFC_M05_CELL: grid cell size (default 4 m, unchanged for MP). Accelerator only: ray hits are exact, so any cell size gives the
# same result; campaign chapters use a coarser cell for fewer grid entries (A1_IAC: 78 M entries at 4 m)
CELL = float(os.environ.get('WFC_M05_CELL') or 4.0)
# WFC_M05_TILE (m, campaign only): process default-material faces in tiles with tile-local obstacle grids; unset = original single grid
TILE = float(os.environ.get('WFC_M05_TILE') or 0)
ALL_LEVELS = bool(os.environ.get('WFC_M05_ALL_LEVELS'))
CT = {5126: 'f4', 5125: 'u4', 5123: 'u2', 5121: 'u1'}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

def acc(g, b, i):
    a = g['accessors'][i]; v = g['bufferViews'][a['bufferView']]
    n = NC[a['type']]; off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
    return np.frombuffer(b, '<' + CT[a['componentType']], a['count'] * n, off).reshape(a['count'], n) if n > 1 else \
        np.frombuffer(b, '<' + CT[a['componentType']], a['count'], off)

NONOCC = set()

def scene_triangles():
    pa = json.load(open(os.path.join(VS, 'Maps', MAP, 'props_authored.json'), encoding='utf-8'))['props']
    for x in pa:
        if x.get('lighting_channels_on') == [] or (x.get('render') or {}).get('bAcceptsLights') is False:
            NONOCC.add(x['component'] if x.get('container_class') == 'StaticMeshCollectionActor' else x['actor'])
    g, bins = read_glb(GLB); b = bins[0]
    cache = {}
    tris, owners, boxes = [], [], []
    for n in g['nodes']:
        if 'mesh' not in n or 'matrix' not in n: continue
        ex = n.get('extras') or {}
        if 'actor' not in ex: continue
        if (ex.get('component') or ex.get('actor')) in NONOCC or 'SpaceDome' in (ex.get('mesh') or ''): continue
        mi = n['mesh']
        if mi not in cache:
            T = []
            for p in g['meshes'][mi]['primitives']:
                P = acc(g, b, p['attributes']['POSITION']).astype('f8'); I = acc(g, b, p['indices']).astype('i8').reshape(-1, 3)
                T.append(P[I])
            cache[mi] = np.concatenate(T) if T else np.zeros((0, 3, 3))
        M = np.array(n['matrix'], 'f8').reshape(4, 4).T
        t = cache[mi] @ M[:3, :3].T + M[:3, 3]
        tris.append(t); owners.append((ex.get('actor'), ex.get('mesh'), len(t)))
        boxes.append((t.reshape(-1, 3).min(0), t.reshape(-1, 3).max(0)))
    return tris, owners, boxes

def ray_hits(o, d, T, maxt):
    """Moller-Trumbore, many triangles one ray -> nearest t in (0, maxt] or None."""
    if not len(T): return None
    v0, v1, v2 = T[:, 0], T[:, 1], T[:, 2]
    e1, e2 = v1 - v0, v2 - v0
    h = np.cross(d, e2); a = (e1 * h).sum(1)
    ok = np.abs(a) > 1e-12
    f = np.where(ok, 1.0 / np.where(ok, a, 1), 0)
    s = o - v0; u = f * (s * h).sum(1)
    q = np.cross(s, e1); v = f * (q @ d); t = f * (e2 * q).sum(1)
    hit = ok & (u >= 0) & (u <= 1) & (v >= 0) & (u + v <= 1) & (t > 0) & (t <= maxt)
    return float(t[hit].min()) if hit.any() else None

MAX_CELLS_PER_TRI = 64          # larger triangles go to an always-tested list (memory bound)
MEM_LIMIT_GB = 8.0

def rss_gb():
    import ctypes, ctypes.wintypes as w
    class PMC(ctypes.Structure):
        _fields_ = [('cb', w.DWORD), ('PageFaultCount', w.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    k = ctypes.windll.kernel32; k.GetCurrentProcess.restype = ctypes.c_void_p
    ps = ctypes.windll.psapi; ps.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, w.DWORD]
    ps.GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 2 ** 30

def guard():
    if rss_gb() > MEM_LIMIT_GB:
        print('MEMORY GUARD: working set > %.1f GB, aborting' % MEM_LIMIT_GB); sys.exit(3)

class Grid:
    """uniform 3D grid over the obstacle triangles, stored compactly (2026-10-16): sorted int64 cell keys + per-cell ranges of int32
    triangle ids (CSR) instead of a dict of Python int lists (campaign chapters ran out of memory: A1 / A3 / D2 / D3B). Same cells, same
    candidate sets per ray, and ray_hits returns the nearest hit, so results are unchanged."""
    def __init__(self, T):
        self.T = T
        lo = T.min(1); hi = T.max(1)
        self.o = lo.min(0)
        a = np.floor((lo - self.o) / CELL).astype(np.int64); b = np.floor((hi - self.o) / CELL).astype(np.int64)
        dim = b - a + 1; span = np.prod(dim, axis=1)
        self.big = np.where(span > MAX_CELLS_PER_TRI)[0]
        self.n = (b.max(0) + 2) if len(b) else np.ones(3, np.int64)       # cells per axis (key = (x * ny + y) * nz + z)
        small = np.where(span <= MAX_CELLS_PER_TRI)[0]
        keys, ids = [], []
        shapes = dim[small]
        for shp in np.unique(shapes, axis=0):                              # one vectorised block per triangle footprint shape
            sel = small[np.all(shapes == shp, axis=1)]
            off = np.stack(np.meshgrid(*[np.arange(k) for k in shp], indexing='ij'), -1).reshape(-1, 3)
            c = a[sel][:, None, :] + off[None, :, :]
            keys.append(((c[..., 0] * self.n[1] + c[..., 1]) * self.n[2] + c[..., 2]).ravel())
            ids.append(np.repeat(sel.astype(np.int32), len(off)))
        keys = np.concatenate(keys) if keys else np.zeros(0, np.int64); ids = np.concatenate(ids) if ids else np.zeros(0, np.int32)
        order = np.argsort(keys, kind='stable'); self.ids = ids[order]; del ids
        keys = keys[order]; del order                                       # one sort; ranges by run boundaries (no second sort)
        b = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
        self.keys = keys[b]; self.start = b; self.end = np.r_[b[1:], len(keys)].astype(np.int64); del keys
        self.ncells = len(self.keys)
        self.bigset = set(int(i) for i in self.big)
        guard()
    def blocked(self, p0, p1, skip):
        d = p1 - p0; L = float(np.linalg.norm(d))
        if L < 1e-6: return False
        d = d / L
        n = int(L / (CELL * 0.5)) + 2
        c = np.floor((p0 + d[None, :] * (L * np.arange(n)[:, None] / (n - 1)) - self.o) / CELL).astype(np.int64)
        ok = np.all((c >= 0) & (c < self.n), axis=1)
        k = np.unique((c[ok, 0] * self.n[1] + c[ok, 1]) * self.n[2] + c[ok, 2])
        pos = np.searchsorted(self.keys, k); hit = pos < len(self.keys); hit[hit] = self.keys[pos[hit]] == k[hit]; pos = pos[hit]
        ids = set()
        for q in pos: ids.update(self.ids[self.start[q]:self.end[q]].tolist())
        ids |= self.bigset
        ids -= skip
        if not ids: return False
        t = ray_hits(p0, d, self.T[list(ids)], L - 0.02)
        return t is not None and t > 0.02

def level_model(lv):
    p = objtree.package(lv)
    level = next(i + 1 for i, e in enumerate(p.exports) if p.class_name(e) == 'Level')
    mi = max((i + 1 for i, e in enumerate(p.exports) if p.class_name(e) == 'Model' and e['outer'] == level),
             key=lambda i: p.exports[i - 1]['serial_size'])
    return p, bsp.read_model(p, mi)

def main():
    # WFC_M05_ALL_LEVELS (campaign): every level with exported BSP (map.json), not only bsp_level(); faces of all of them are analysed
    # and the BSP of all of them occludes. Unset = the single bsp_level() level, as before
    if ALL_LEVELS:
        mj = json.load(open(os.path.join(VS, 'Maps', MAP, 'map.json'), encoding='utf-8'))['bsp']
        LEVELS = [k for k, v in mj.items() if (v or {}).get('render_triangles')]
    else:
        LEVELS = [LV]
    LM = [(lv,) + level_model(lv) for lv in LEVELS]
    p, M = LM[0][1], LM[0][2]
    nkey = (lambda li, ni: (li, ni)) if ALL_LEVELS else (lambda li, ni: ni)
    tris, owners, boxes = scene_triangles()
    lo = np.array([b[0] for b in boxes]); hi = np.array([b[1] for b in boxes])
    # obstacle set: meshes + all rendered BSP polygons (fan triangles), remembering which BSP node owns which triangle
    bt, bown = [], []
    for li, (lv_, p_, M_) in enumerate(LM):
        for ni, (si, pts, node) in enumerate(bsp.polygons(M_)):
            if int(M_['surfs'][si]['PolyFlags']) & (bsp.PF_INVISIBLE | bsp.PF_PORTAL): continue
            G = np.stack([pts[:, 0], pts[:, 2], pts[:, 1]], 1) * 0.01
            for j in range(1, len(G) - 1):
                bt.append([G[0], G[j], G[j + 1]]); bown.append(nkey(li, ni))
    if not TILE:
        allT = np.concatenate([np.concatenate(tris), np.array(bt)])
        nmesh = sum(len(t) for t in tris)
        tri_of_node = defaultdict(set)
        for k, ni in enumerate(bown): tri_of_node[ni].add(nmesh + k)
        grid = Grid(allT); nobst = len(allT); nbig = len(grid.big); ncells = grid.ncells
    else:
        # WFC_M05_TILE (campaign): no global obstacle grid; per tile of default-material faces, a grid of the obstacles within the
        # tile's faces' bounds +- (VIEW_M + 1 m) - every visibility ray (<= VIEW_M) and cover ray lies inside that box
        btA = np.array(bt) if bt else np.zeros((0, 3, 3)); bt_lo = btA.min(1) if len(btA) else btA; bt_hi = btA.max(1) if len(btA) else btA
        bsp_of_node = defaultdict(list)
        for k, ni in enumerate(bown): bsp_of_node[ni].append(k)
        nobst = sum(len(t) for t in tris) + len(btA); nbig = ncells = 'per tile'
    nav = json.load(open(os.path.join(VS, 'Maps', MAP, 'navigation.json'), encoding='utf-8'))['nodes']
    pts = [n['location_ue'] for n in nav if n.get('location_ue')]
    sp = json.load(open(os.path.join(VS, 'Maps', MAP, 'gameplay.json'), encoding='utf-8'))['player_starts']
    for x in (sp if isinstance(sp, list) else [y for v in sp.values() for y in v]):
        if x.get('location_ue'): pts.append(x['location_ue'])
    V = np.unique(np.array([[q[0], q[2] + EYE_UU, q[1]] for q in pts]), axis=0) * 0.01
    print('obstacles', nobst, 'big', nbig, 'cells', ncells, 'viewpoints', len(V), 'tile', TILE, 'mem %.2f GB' % rss_gb(), flush=True)

    def default_nodes():
        for li, (lv_, p_, M_) in enumerate(LM):
            for ni, (si, pts, node) in enumerate(bsp.polygons(M_)):
                s = M_['surfs'][si]; mat = int(s['Material'])
                mp = p_.object_path(mat) if mat > 0 else (p_.full_path(mat) if mat < 0 else None)
                if mp and 'DefaultMaterial' in mp: yield (li, ni), si, pts, node

    def node_iter():
        if not TILE:
            for (li, ni), si, pts, node in default_nodes(): yield (li, ni), si, pts, node, grid, tri_of_node[nkey(li, ni)]
            return
        tiles = defaultdict(list)
        for ni, si, pts, node in default_nodes():
            G = np.stack([pts[:, 0], pts[:, 2], pts[:, 1]], 1) * 0.01; c = G.mean(0)
            tiles[(int(np.floor(c[0] / TILE)), int(np.floor(c[2] / TILE)))].append((ni, si, pts, node, G))
        for key in sorted(tiles):
            grp = tiles[key]
            bx0 = np.min([g[4].min(0) for g in grp], 0) - (VIEW_M + 1); bx1 = np.max([g[4].max(0) for g in grp], 0) + (VIEW_M + 1)
            mk = np.where(np.all(hi >= bx0, 1) & np.all(lo <= bx1, 1))[0]
            bk = np.where(np.all(bt_hi >= bx0, 1) & np.all(bt_lo <= bx1, 1))[0] if len(btA) else np.zeros(0, int)
            parts = [tris[k] for k in mk] + ([btA[bk]] if len(bk) else [])
            Tt = np.concatenate(parts) if parts else np.zeros((1, 3, 3)) + 1e9
            off = sum(len(tris[k]) for k in mk); g2l = {int(b): off + j for j, b in enumerate(bk)}
            gt = Grid(Tt)
            print('tile', key, 'faces', len(grp), 'obstacles', len(Tt), 'mem %.2f GB' % rss_gb(), flush=True)
            for ni, si, pts, node, G in grp:
                yield ni, si, pts, node, gt, {g2l[b] for b in bsp_of_node[nkey(*ni)] if b in g2l}
            del gt, Tt, parts

    nodes = []
    for (li, ni), si, pts, node, grid, skip in node_iter():
        lvname, p, M = LM[li]
        s = M['surfs'][si]
        G = np.stack([pts[:, 0], pts[:, 2], pts[:, 1]], 1) * 0.01
        nr = M['vectors'][int(s['vNormal'])]; n = np.array([nr[0], nr[2], nr[1]]); n /= np.linalg.norm(n)
        c = G.mean(0)
        samples = [c] + [v + 0.15 * (c - v) for v in G]
        blo, bhi = G.min(0) - COVER_M - 0.05, G.max(0) + COVER_M + 0.05
        cand = np.where(np.all(hi >= blo, 1) & np.all(lo <= bhi, 1))[0]
        T = np.concatenate([tris[k] for k in cand]) if len(cand) else np.zeros((0, 3, 3))
        cov = []
        for sp in samples:
            t = ray_hits(sp - 0.01 * n, n, T, COVER_M + 0.01)
            cov.append(t is not None)
        area = 0.5 * np.linalg.norm(sum(np.cross(G[i], G[(i + 1) % len(G)]) for i in range(len(G))))
        verdict = 'hidden' if all(cov) else ('partial' if any(cov) else 'exposed')
        front = V[((V - c) @ n > 0.05) & (np.linalg.norm(V - c, axis=1) < VIEW_M)]
        seen_by, first = 0, None
        for v in front[np.argsort(np.linalg.norm(front - c, axis=1))][:150]:
            for sp, cv_ in zip(samples, cov):
                if cv_: continue
                if not grid.blocked(v, sp + 0.02 * n, skip):
                    seen_by += 1; first = first or (v[[0, 2, 1]] * 100).round(0).tolist(); break
            if seen_by >= 3: break
        guard()
        nodes.append({**({'level': lvname} if ALL_LEVELS else {}), 'node_index': ni, 'surface': si, 'brush': p.object_path(int(s['Actor'])) if int(s['Actor']) > 0 else None,
                      'poly_flags_raw': '0x%08X' % int(s['PolyFlags']), 'centroid_ue': (c[[0, 2, 1]] * 100).round(1).tolist(),
                      'normal_ue': [round(float(x), 4) for x in n[[0, 2, 1]]], 'area_m2': round(float(area), 3),
                      'samples_covered': f'{sum(cov)}/{len(cov)}', 'verdict': verdict,
                      'front_side_viewpoints_within_%dm' % VIEW_M: int(len(front)),
                      'visible_in_play': seen_by > 0, 'example_viewpoint_ue': first,
                      'nearby_meshes': sorted({owners[k][1] for k in cand})[:6]})
    nodes.sort(key=lambda x: (LEVELS.index(x['level']) if ALL_LEVELS else 0, x['node_index']))   # tiles visit nodes out of order
    vc = Counter(x['verdict'] for x in nodes)
    vis = [x for x in nodes if x['visible_in_play']]
    area = defaultdict(float)
    for x in nodes: area[x['verdict']] += x['area_m2']
    out = {'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/m05_bsp_default_faces.py',
           'provenance': {'value': 'EngineMaterials.DefaultMaterial is the authored/cooked material of these BSP surfaces', 'confidence': CONF,
                          'evidence': ['FBspSurf.Material -> import EngineMaterials.DefaultMaterial',
                                       'cooked FModelElement.Material of the rendering ModelComponents -> EngineMaterials.DefaultMaterial',
                                       'source brush Models cooked as 124-byte stubs (no Polys): no alternative assignment survives',
                                       'UE3 renders a BSP surface with no material through GEngine->DefaultMaterial; the cooker resolved it the same way']},
           'occlusion_method': 'ray from 1 cm behind the face along its normal; covered if a placed static-mesh triangle is hit within %.2f m' % COVER_M,
           'counts': {'nodes': len(nodes), 'surfaces': len({x['surface'] for x in nodes}), 'brushes': len({x['brush'] for x in nodes}),
                      'by_verdict': dict(vc), 'area_m2_by_verdict': {k: round(v, 2) for k, v in area.items()},
                      'visible_in_play': len(vis), 'visible_in_play_area_m2': round(sum(x['area_m2'] for x in vis), 2)},
           'play_visibility_method': 'viewpoints: %d navigation nodes at +%d UU; front side; within %d m; occluders = meshes + BSP' % (len(V), EYE_UU, VIEW_M),
           'nodes': sorted(nodes, key=lambda x: (not x['visible_in_play'], -x['area_m2']))}
    write(map_out(MAP, 'streets_bsp_default_faces.json'), out)
    print(json.dumps(out['counts'], indent=1))
    for x in out['nodes'][:12]: print(x['visible_in_play'], x['verdict'], x['area_m2'], x['centroid_ue'], x['normal_ue'], x['samples_covered'], x['nearby_meshes'][:3])

if __name__ == '__main__':
    main()
