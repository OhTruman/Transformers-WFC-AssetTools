"""Campaign render gap #5 (CAMPAIGN_RENDER_DRYRUN.md finding 5; Integration 2026-10-23: per-sublevel inputs, the original's streaming
model, RAM bounded): split a chapter's world.glb / map_fx.json / render_index.json by streaming sublevel.

    python split_sublevels.py <CHAPTER>     (one chapter per bounded run)

Input  work/campaign_pilot/VerticalSlice/Maps/<CH>/{world.glb, map_fx.json, render_index.json, props.json, map.json} (read-only).
Output work/campaign_pilot/VerticalSlice/Maps/<CH>/sublevels/<level>/{world.glb, map_fx.json, render_index.json} + sublevels/index.json.

Sublevel of a record = the package prefix of its full object path:
  world.glb node: extras.component, else extras.source (BSP), else props.json (actor, mesh, matrix) -> sublevel;
  map_fx: particle_components[].sublevel / component prefix; decals[] the same; particle_systems / decal_materials keep the entries
          the sublevel's components / decals reference; counts recomputed;
  render_index: every list of records is filtered by the prefix of its 'actor' / 'component' / 'factory' path (recursively in dicts);
          short-name actor lists (mode_visual_state / tdm_render_state 'actors') keep the names placed in that sublevel.
Nothing is dropped: records with no resolvable sublevel go to sublevels/_unassigned/. Every split file keeps the chapter file's keys and
adds sibling keys 'sublevel' / 'split_from'. world.glb subsets keep node order, matrices and extras; meshes / accessors / materials /
textures / images are re-indexed and the binary repacked; image URIs are rebased two folders down.
"""
import json, os, struct, sys
from collections import Counter, defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
CVS = os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice', 'Maps')
UNASSIGNED = '_unassigned'

def read_glb(p):
    with open(p, 'rb') as f: data = f.read()
    n = struct.unpack_from('<I', data, 12)[0]; j = json.loads(data[20:20 + n])
    o = 20 + n; bl = struct.unpack_from('<I', data, o)[0]
    return j, memoryview(data)[o + 8:o + 8 + bl]

def write_glb(p, j, bin_):
    js = json.dumps(j, separators=(',', ':')).encode('utf-8'); js += b' ' * (-len(js) % 4); bin_ += b'\0' * (-len(bin_) % 4)
    with open(p, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(bin_)))
        f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js); f.write(struct.pack('<II', len(bin_), 0x004E4942)); f.write(bin_)

def subset_glb(j, bin_, node_ids, level):
    nodes = [dict(j['nodes'][i]) for i in node_ids]
    mesh_map, acc_map, bv_map, mat_map, tex_map, img_map, smp_map = {}, {}, {}, {}, {}, {}, {}
    out = {'asset': dict(j['asset'], extras={'sublevel': level, 'split_from': 'world.glb'}), 'scene': 0,
           'scenes': [{'nodes': list(range(len(nodes)))}], 'nodes': nodes, 'meshes': [], 'accessors': [], 'bufferViews': [],
           'materials': [], 'textures': [], 'images': [], 'samplers': [], 'buffers': []}
    chunks, off = [], 0
    def m(map_, i, src, dst, fn=None):
        if i not in map_:
            map_[i] = len(out[dst]); out[dst].append(None); out[dst][map_[i]] = fn(src[i]) if fn else dict(src[i])
        return map_[i]
    def bv(i):
        nonlocal off
        if i not in bv_map:
            v = dict(j['bufferViews'][i]); s = v.get('byteOffset', 0); b = bytes(bin_[s:s + v['byteLength']])
            pad = -off % 4; chunks.append(b'\0' * pad); off += pad
            v['byteOffset'] = off; v['buffer'] = 0; chunks.append(b); off += len(b)
            bv_map[i] = len(out['bufferViews']); out['bufferViews'].append(v)
        return bv_map[i]
    def acc(i):
        if i not in acc_map:
            a = dict(j['accessors'][i])
            if 'bufferView' in a: a['bufferView'] = bv(a['bufferView'])
            acc_map[i] = len(out['accessors']); out['accessors'].append(a)
        return acc_map[i]
    def texinfo(t):
        t = dict(t); t['index'] = tex(t['index']); return t
    def tex(i):
        if i not in tex_map:
            t = dict(j['textures'][i])
            if 'source' in t: t['source'] = img(t['source'])
            if 'sampler' in t: t['sampler'] = m(smp_map, t['sampler'], j['samplers'], 'samplers')
            tex_map[i] = len(out['textures']); out['textures'].append(t)
        return tex_map[i]
    def img(i):
        if i not in img_map:
            im = dict(j['images'][i])
            if 'uri' in im and not im['uri'].startswith('data:'): im['uri'] = '../../' + im['uri']
            if 'bufferView' in im: im['bufferView'] = bv(im['bufferView'])
            img_map[i] = len(out['images']); out['images'].append(im)
        return img_map[i]
    def mat(i):
        if i not in mat_map:
            mt = json.loads(json.dumps(j['materials'][i]))
            pb = mt.get('pbrMetallicRoughness') or {}
            for k in ('baseColorTexture', 'metallicRoughnessTexture'):
                if k in pb: pb[k] = texinfo(pb[k])
            for k in ('normalTexture', 'occlusionTexture', 'emissiveTexture'):
                if k in mt: mt[k] = texinfo(mt[k])
            mat_map[i] = len(out['materials']); out['materials'].append(mt)
        return mat_map[i]
    def mesh(i):
        if i not in mesh_map:
            me = json.loads(json.dumps(j['meshes'][i]))
            for pr in me['primitives']:
                pr['attributes'] = {k: acc(v) for k, v in pr['attributes'].items()}
                if 'indices' in pr: pr['indices'] = acc(pr['indices'])
                if 'material' in pr: pr['material'] = mat(pr['material'])
                for t in pr.get('targets') or []:
                    for k in list(t): t[k] = acc(t[k])
            mesh_map[i] = len(out['meshes']); out['meshes'].append(me)
        return mesh_map[i]
    for nd in nodes:
        assert 'children' not in nd and 'skin' not in nd, 'flat static node list expected'
        if 'mesh' in nd: nd['mesh'] = mesh(nd['mesh'])
    out['buffers'] = [{'byteLength': off}]
    for k in ('textures', 'images', 'samplers', 'materials', 'meshes'):
        if not out[k]: out.pop(k)
    for k in ('extensionsUsed', 'extensionsRequired'):
        if k in j: out[k] = j[k]
    return out, b''.join(chunks)

def prefix(s, levels):
    p = (s or '').split('.')[0]
    return p if p in levels else None

def node_level(nd, levels, props_idx):
    e = nd.get('extras') or {}
    lv = prefix(e.get('component'), levels) or prefix(e.get('source'), levels)
    if lv: return lv
    cands = props_idx.get((e.get('actor'), e.get('mesh'))) or []
    if len({c[0] for c in cands}) == 1: return cands[0][0]
    if cands and nd.get('matrix'):
        M = np.array(nd['matrix'], float)
        best = min(cands, key=lambda c: float(np.abs(np.array(c[1], float) - M).sum()) if c[1] else 1e18)
        if best[1] and float(np.abs(np.array(best[1], float) - M).sum()) < 1e-3: return best[0]
    return None

def rec_level(r, levels):
    if not isinstance(r, dict): return None
    if r.get('sublevel') in levels: return r['sublevel']
    for k in ('actor', 'component', 'owner', 'factory'):
        lv = prefix(r.get(k), levels) if isinstance(r.get(k), str) else None
        if lv: return lv
    return None

def split_value(v, levels, short_names, depth=0):
    """-> {level: filtered value} for lists of records / dicts holding them; None if the value is chapter-wide (copied as is)."""
    if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
        lv = [rec_level(x, levels) for x in v]
        if any(lv):
            out = defaultdict(list)
            for x, l in zip(v, lv): out[l or UNASSIGNED].append(x)
            return out
        return None
    if isinstance(v, dict) and depth < 4:
        parts, any_split = {}, False
        for k, x in v.items():
            s = split_value(x, levels, short_names, depth + 1)
            if s is None and k == 'actors' and isinstance(x, list) and all(isinstance(a, str) for a in x):
                s = defaultdict(list)
                for a in x: s[short_names.get(a, UNASSIGNED)].append(a)
            if s is not None: any_split = True
            parts[k] = s
        if not any_split: return None
        out = {}
        for l in set().union(*[set(s) for s in parts.values() if s is not None]):
            d = {}
            for k, x in v.items():
                s = parts[k]
                if s is None: d[k] = x
                elif l in s: d[k] = s[l]
                else: d[k] = [] if isinstance(x, list) else {}
            if 'count' in d and isinstance(d.get('components'), list): d['count'] = len(d['components'])
            out[l] = d
        return out
    return None

def main(ch):
    D = os.path.join(CVS, ch); OUT = os.path.join(D, 'sublevels')
    levels = list(json.load(open(os.path.join(D, 'map.json'), encoding='utf-8'))['sublevels']); lvset = set(levels) | {UNASSIGNED}
    pj = json.load(open(os.path.join(D, 'props.json'), encoding='utf-8')); props = pj['props'] if isinstance(pj, dict) else pj
    props_idx = defaultdict(list)
    for p in props:
        if p.get('sublevel') in lvset: props_idx[(p.get('actor'), p.get('mesh'))].append((p['sublevel'], p.get('gltf_matrix')))
    short = {}
    for p in props:
        if p.get('sublevel') in lvset: short.setdefault(p.get('actor'), p['sublevel'])
    # world.glb
    j, bin_ = read_glb(os.path.join(D, 'world.glb'))
    by_lv = defaultdict(list)
    for i, nd in enumerate(j['nodes']): by_lv[node_level(nd, lvset, props_idx) or UNASSIGNED].append(i)
    # map_fx
    fx = json.load(open(os.path.join(D, 'map_fx.json'), encoding='utf-8'))
    fx_by = defaultdict(lambda: defaultdict(list))
    for k in ('particle_components', 'decals'):
        for r in fx.get(k) or []: fx_by[rec_level(r, lvset) or UNASSIGNED][k].append(r)
    # render_index
    ri = json.load(open(os.path.join(D, 'render_index.json'), encoding='utf-8'))
    for k, v in ri.items():
        if isinstance(v, list):
            for r in v:
                if isinstance(r, dict) and isinstance(r.get('actor'), str):
                    lv = prefix(r['actor'], lvset)
                    if lv: short.setdefault(r['actor'].split('.')[-1], lv)
    ri_parts = {k: split_value(v, lvset, short) for k, v in ri.items()}
    all_lv = [l for l in levels + [UNASSIGNED] if l in by_lv or l in fx_by or any(s and l in s for s in ri_parts.values())]
    index = {'chapter': ch, 'generated_by': 'AssetTools/work/campaign_render_dryrun/split_sublevels.py', 'levels': {}}
    tot = Counter()
    for l in all_lv:
        od = os.path.join(OUT, l); os.makedirs(od, exist_ok=True)
        sj, sb = subset_glb(j, bin_, by_lv.get(l, []), l); write_glb(os.path.join(od, 'world.glb'), sj, sb)
        pcs, dcs = fx_by[l]['particle_components'], fx_by[l]['decals']
        used_ps = {r.get('template') or r.get('particle_system') for r in pcs}
        used_dm = {r.get('material') or r.get('decal_material') for r in dcs}
        ps = fx.get('particle_systems'); dm = fx.get('decal_materials')
        sfx = dict(fx, sublevel=l, split_from='map_fx.json', particle_components=pcs, decals=dcs,
                   particle_systems={k: v for k, v in ps.items() if k in used_ps} if isinstance(ps, dict) else ps,
                   decal_materials={k: v for k, v in dm.items() if k in used_dm} if isinstance(dm, dict) else dm)
        sfx['counts'] = dict(fx.get('counts') or {}, decals=len(dcs), particle_components=len(pcs),
                             particle_systems=len(sfx['particle_systems']) if isinstance(sfx['particle_systems'], dict) else None,
                             decal_materials=len(sfx['decal_materials']) if isinstance(sfx['decal_materials'], dict) else None)
        json.dump(sfx, open(os.path.join(od, 'map_fx.json'), 'w', encoding='utf-8'), indent=1)
        sri = {}
        for k, v in ri.items():
            s = ri_parts[k]
            sri[k] = v if s is None else (s.get(l) if l in s else ([] if isinstance(v, list) else {}))
        sri['sublevel'] = l; sri['split_from'] = 'render_index.json'
        json.dump(sri, open(os.path.join(od, 'render_index.json'), 'w', encoding='utf-8'), indent=1)
        sz = {f: os.path.getsize(os.path.join(od, f)) for f in ('world.glb', 'map_fx.json', 'render_index.json')}
        index['levels'][l] = {'nodes': len(by_lv.get(l, [])), 'meshes': len(sj.get('meshes') or []), 'materials': len(sj.get('materials') or []),
                              'particle_components': len(pcs), 'decals': len(dcs), 'bytes': sz}
        tot['nodes'] += len(by_lv.get(l, [])); tot['pc'] += len(pcs); tot['decals'] += len(dcs); tot['bytes'] += sum(sz.values())
    # no-loss check
    ri_src = sum(len(v) for k, v in ri.items() if isinstance(v, list) and ri_parts[k] is not None)
    ri_dst = sum(len(index_ri) for k in ri if isinstance(ri[k], list) and ri_parts[k] is not None for index_ri in ri_parts[k].values())
    index['check'] = {'nodes': [len(j['nodes']), tot['nodes']], 'particle_components': [len(fx.get('particle_components') or []), tot['pc']],
                      'decals': [len(fx.get('decals') or []), tot['decals']], 'render_index_split_list_records': [ri_src, ri_dst],
                      'unassigned_nodes': len(by_lv.get(UNASSIGNED, [])), 'unassigned_particle_components': len(fx_by[UNASSIGNED]['particle_components']),
                      'chapter_bytes': sum(os.path.getsize(os.path.join(D, f)) for f in ('world.glb', 'map_fx.json', 'render_index.json')),
                      'split_bytes': tot['bytes']}
    index['check']['pass'] = all(a == b for a, b in (index['check'][k] for k in ('nodes', 'particle_components', 'decals', 'render_index_split_list_records')))
    json.dump(index, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), indent=1)
    print(ch, 'levels', len(all_lv), json.dumps(index['check']))

if __name__ == '__main__':
    main(sys.argv[1])
