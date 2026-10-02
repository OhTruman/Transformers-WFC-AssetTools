"""Recover WFC baked-lightmap bindings for MP_IAC_Streets static meshes.

Decodes the licensee-144 FStaticMeshComponentLODInfo / FLightMap2D native serialization in
MP_IAC_Streets_ART_m.xxx and joins each placed prop (props.json) to its lightmap:
  - directional coefficient-0 atlas (LightMapTexture2D in the _LM package, exported to PNG)
  - CoordinateScale / CoordinateBias (maps the mesh TEXCOORD_1 into the atlas)
  - coefficient-0 ScaleVector (HDR scale of the stored lightmap)

Serialization (verified): after the component's tagged props, big-endian native block:
  ... [LightMapType=2] [LightGuids.Num:byte] [LightGuids: Num x FGuid(16)]
      [lead int32 = 0] 3 x ([tex: BE int32 export index][ScaleVector: 3 BE floats][1.0])
      [CoordinateScale: 2 BE floats] [CoordinateBias: 2 BE floats]
The texture is a positive export index into THIS package's export table (seekfree forward
export whose name matches the _LM atlas).

Output: ExtractedAssets/VerticalSlice/Maps/<MAP>/lightmaps.json
    AssetTools\\bin\\py\\python.exe AssetTools\\scripts\\wfc\\vs_lightmap.py [MAP]
"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ue3pkg, props as propsmod
from vs_common import VS

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
CK = r'F:/Transformers Rebuild/Game Dump/TransGame/CookedXenon'
OUT = os.path.join(VS, 'Maps', MAP)
SHARED = None  # discovered: the shared dominant-light GUID


def lm_name(p, idx):
    if idx > 0 and idx - 1 < len(p.exports) and p.class_name(p.exports[idx - 1]) == 'LightMapTexture2D':
        return p.obj_name(idx)
    return None


def parse_component(p, nat):
    global SHARED
    # anchor on the shared dominant-light GUID; it precedes with a 1-byte LightGuids.Num
    if SHARED is None:
        # locate by scanning for a 16-byte value that recurs; here we take the first component's
        return None
    g = nat.find(SHARED)
    if g < 1:
        return None
    num = nat[g - 1]
    o = g + num * 16
    if o + 4 > len(nat):
        return None
    o += 4  # lead int32 (0)
    coeffs = []
    while o + 20 <= len(nat):
        ref = struct.unpack_from('>i', nat, o)[0]
        nm = lm_name(p, ref)
        if not nm:
            break
        sv = struct.unpack_from('>3f', nat, o + 4)
        coeffs.append((nm, sv))
        o += 20
    if not coeffs or o + 16 > len(nat):
        return None
    cs = struct.unpack_from('>2f', nat, o)
    cb = struct.unpack_from('>2f', nat, o + 8)
    return {'atlas': coeffs[0][0], 'coeffs': [c[0] for c in coeffs],
            'scaleVec': list(coeffs[0][1]), 'coordScale': list(cs), 'coordBias': list(cb)}


def main():
    global SHARED
    p = ue3pkg.Package(os.path.join(CK, MAP + '_ART_m.xxx'))
    pr = propsmod.PropReader(p)

    # Pass 1: discover the shared dominant-light GUID = the 16 bytes right after LightMapType=2
    # in the first lightmapped component (it recurs in every lightmapped component).
    for i, e in enumerate(p.exports):
        if p.class_name(e) != 'StaticMeshComponent':
            continue
        try:
            used = pr.read_object(i + 1)[1]
        except Exception:
            continue
        nat = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
        if len(nat) > 40 and struct.unpack_from('<i', nat, 16)[0] == 2:
            SHARED = nat[21:37]
            break
    if SHARED is None:
        print('ERROR: no lightmapped component found', file=sys.stderr); sys.exit(1)
    print('shared dominant-light GUID:', SHARED.hex())

    # Pass 2: parse every lightmapped component, keyed by object path.
    by_path = {}
    for i, e in enumerate(p.exports):
        if p.class_name(e) != 'StaticMeshComponent':
            continue
        try:
            used = pr.read_object(i + 1)[1]
        except Exception:
            continue
        nat = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
        rec = parse_component(p, nat)
        if rec:
            by_path[p.object_path(i + 1).lower()] = rec
    print('parsed lightmapped components:', len(by_path))

    # Join to placed props.
    pj = json.load(open(os.path.join(OUT, 'props.json'), encoding='utf-8'))
    out = []
    hit = miss = 0
    atlases = set()
    for pr_ in pj['props']:
        comp = (pr_.get('component') or '').lower()
        rec = by_path.get(comp)
        if rec:
            atlases.add(rec['atlas'])
            out.append({'actor': pr_.get('actor'), 'component': pr_.get('component'),
                        'atlas': rec['atlas'], 'coordScale': rec['coordScale'],
                        'coordBias': rec['coordBias'], 'scaleVec': rec['scaleVec']})
            hit += 1
        else:
            miss += 1
    json.dump({'map': MAP, 'count': hit, 'atlases_used': sorted(atlases),
               'note': 'atlas = _LM LightMapTexture2D (coeff0). lightmap UV = TEXCOORD_1*coordScale+coordBias.',
               'props': out}, open(os.path.join(OUT, 'lightmaps.json'), 'w'), indent=0)
    print('props with lightmap: %d   without: %d   unique atlases used: %d'
          % (hit, miss, len(atlases)))
    print('wrote', os.path.join(OUT, 'lightmaps.json'))


if __name__ == '__main__':
    main()
