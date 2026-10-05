"""Per-vertex (LMT_1D) baked lightmaps for any map -> ExtractedAssets/VerticalSlice/Maps/<MAP>/vertex_lightmaps.json

  python vs_vertex_lightmaps.py <MAP>

StaticMeshComponent LODData[0].LightMap with LightMapType 1 (FLightMap1D), big-endian after the tagged properties:
  [13] type = 1, [17] LightGuids.Num, GUIDs (16 each), Owner (4), DirectionalSamples bulk data
  (5 ints: Flags, ElementCount, SizeOnDisk, OffsetInFile, <checksum>), ElementCount x FQuantizedDirectionalLightSample
  (3 x FColor, 4 bytes each), then ScaleVectors[3] (FVector). Vertex order = the mesh's LOD0 vertex buffer.
Records use the renderer's existing schema (Rendering build_lighting.py `vertex_lightmaps`: count, samples_hex, scales).

Why this exists: the 4th byte of every sample colour is 254/255 on Streets / Debris but 0 on Gorge, Rust, Seed, Berth,
Complex, Molten and the Escalation maps. A decoder that requires that byte >= 250 drops every vertex lightmap on those maps
(50-635 components each render without baked light). The RGB layout and scale vectors are identical; the 4th byte is not
part of the colour (HIGH: same bulk size count*12, monotone RGB, scales in the Streets range).
Validation: sample count == the component mesh's LOD0 vertex count (umodel glTF POSITION count) where the mesh is exported.
"""
import json, os, struct, sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, props as propsmod, extract  # noqa: E402
import authored as A  # noqa: E402
from vs_common import VS, ROOT, map_sublevels  # noqa: E402

GEN = 'AssetTools/scripts/wfc/vs_vertex_lightmaps.py'

def decode(nat):
    if len(nat) < 40 or struct.unpack_from('<i', nat, 16)[0] != 1 or struct.unpack_from('>i', nat, 13)[0] != 1:
        return None, 'not LMT_1D'
    ng = struct.unpack_from('>i', nat, 17)[0]
    if ng < 0 or ng > 4096: return None, 'bad guid count'
    o = 21 + 16 * ng + 4
    if o + 20 > len(nat): return None, 'short header'
    _flags, count, size = struct.unpack_from('>iii', nat, o); o += 20
    if count <= 0 or size != count * 12 or o + size + 36 > len(nat): return None, 'bulk size mismatch'
    data = nat[o:o + size]
    scales = [list(struct.unpack_from('>3f', nat, o + size + 12 * k)) for k in range(3)]
    fourth = Counter(data[k * 4] for k in range(0, min(count * 3, 300)))
    return {'count': count, 'samples_hex': data.hex(), 'scales': scales, 'light_guids': ng,
            'fourth_byte': 'ff/fe' if all(b >= 250 for b in fourth) else ('00' if set(fourth) == {0} else 'mixed')}, None

def main():
    MAP = sys.argv[1]
    out_dir = os.path.join(VS, 'Maps', MAP)
    props = json.load(open(os.path.join(out_dir, 'props.json'), encoding='utf-8'))['props']
    by_comp = {(p.get('component') or '').lower(): p for p in props if p.get('component')}
    by_actor = {(p['sublevel'], p['actor']): p for p in props if not p.get('component')}
    vcount = {}
    def mesh_vertices(gltf):
        if gltf not in vcount:
            try:
                j = json.load(open(os.path.join(ROOT, gltf), encoding='utf-8'))
                vcount[gltf] = sum(j['accessors'][pr['attributes']['POSITION']]['count'] for pr in j['meshes'][0]['primitives'])
            except Exception:
                vcount[gltf] = None
        return vcount[gltf]
    cooked = {n[:-4].lower(): n[:-4] for n in os.listdir(extract.COOKED) if n.endswith('.xxx')}
    recs, fails, fourth, levels = OrderedDict(), Counter(), Counter(), {}
    match = Counter()
    for lv in map_sublevels(MAP, A):
        if lv.lower() not in cooked: continue
        p = ue3pkg.Package(os.path.join(extract.COOKED, cooked[lv.lower()] + '.xxx')); pr = propsmod.PropReader(p)
        n = 0
        for i, e in enumerate(p.exports):
            if p.class_name(e) != 'StaticMeshComponent': continue
            op = p.object_path(i + 1)
            if not op.startswith(lv + '.TheWorld.PersistentLevel.'): continue
            try: used = pr.read_object(i + 1)[1]
            except Exception: continue
            nat = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
            if len(nat) <= 40 or struct.unpack_from('<i', nat, 16)[0] != 1: continue
            r, err = decode(nat)
            if not r: fails[err] += 1; continue
            prop = by_comp.get(op.lower()) or (by_actor.get((lv, op.split('.')[3])) if op.count('.') == 4 else None)
            mv = mesh_vertices(prop['gltf']) if prop and prop.get('gltf') else None
            r['actor'] = op.split('.')[3]; r['mesh'] = (prop or {}).get('mesh'); r['mesh_lod0_vertices'] = mv
            r['vertex_count_match'] = (mv == r['count']) if mv is not None else None
            match['match' if r['vertex_count_match'] else 'mismatch' if r['vertex_count_match'] is False else 'mesh not in props']  += 1
            fourth[r['fourth_byte']] += 1
            recs[op] = r; n += 1
        levels[lv] = n
    out = OrderedDict([('map', MAP), ('generated_by', GEN),
                       ('schema', 'component path -> {count, samples_hex (count x 3 FColor, 4 bytes each, RGB in bytes 1-3), scales '
                                  '[3 x FVector], ...}; same as the renderer lighting.json vertex_lightmaps'),
                       ('stats', {'components': len(recs), 'by_level': levels, 'decode_failures': dict(fails), 'fourth_byte': dict(fourth),
                                  'vertex_count_check': dict(match)}),
                       ('vertex_lightmaps', recs)])
    json.dump(out, open(os.path.join(out_dir, 'vertex_lightmaps.json'), 'w', encoding='utf-8'))
    print(MAP, json.dumps(out['stats']))

if __name__ == '__main__':
    main()
