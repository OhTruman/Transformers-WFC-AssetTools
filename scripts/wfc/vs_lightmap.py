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


def parse_generic(p, nat):
    """Same record without the shared-GUID anchor: [13] BE i32 LightMapType, [17] BE i32 LightGuids.Num,
    GUIDs, lead int32, 3 x (tex, ScaleVector), CoordinateScale, CoordinateBias. Works for every level package."""
    if len(nat) < 41 or struct.unpack_from('>i', nat, 13)[0] != 2:
        return None
    n = struct.unpack_from('>i', nat, 17)[0]
    if not 0 <= n < 64:
        return None
    o = 21 + 16 * n + 4
    coeffs = []
    while o + 20 <= len(nat) and len(coeffs) < 3:
        nm = lm_name(p, struct.unpack_from('>i', nat, o)[0])
        if not nm:
            break
        coeffs.append((nm, struct.unpack_from('>3f', nat, o + 4))); o += 20
    if not coeffs or o + 16 > len(nat):
        return None
    return {'atlas': coeffs[0][0], 'coeffs': [c[0] for c in coeffs], 'scaleVec': list(coeffs[0][1]),
            'coordScale': list(struct.unpack_from('>2f', nat, o)), 'coordBias': list(struct.unpack_from('>2f', nat, o + 8))}


def main():
    """All lightmapped level packages of the map (ART + BASE); props joined by component path, actor-placed props
    (StaticMeshActor / StaticInterpActor / InterpActor rows without a component key) through their cooked
    StaticMeshComponent (the only one under the actor)."""
    cooked = {n[:-4].lower(): n[:-4] for n in os.listdir(CK) if n.endswith('.xxx')}
    levels = [n[:-4] for n in os.listdir(CK) if n.lower().startswith(MAP.lower() + '_') and n.lower().endswith('_m.xxx')]
    # + streamed sublevels exported by vs_map (authored LevelStreaming: Debris art lives in MP_ORB_Art_m, Seed in MP_IAC_Global_Art_m)
    mj = os.path.join(OUT, 'map.json')
    if os.path.exists(mj):
        levels += [l for l in json.load(open(mj, encoding='utf-8')).get('sublevels') or [] if l.lower() in cooked and l not in levels]
    def lm_package(lv):
        # ART-level atlases live in <ART>_LM (matched case-insensitively: Rust / ORB cook _Art_m); other levels keep the original
        # rule (atlas cooked inline in the level package - Streets BASE validated)
        if lv.lower().endswith('_art_m') and (lv + '_LM').lower() in cooked: return cooked[(lv + '_LM').lower()]
        return lv + ('_LM' if lv.endswith('_ART_m') else '').replace('_BASE_m', '_Base_m_LM')
    by_path, comp_of_actor = {}, {}
    for lv in sorted(levels):
        p = ue3pkg.Package(os.path.join(CK, lv + '.xxx'))
        pr = propsmod.PropReader(p)
        n = 0
        for i, e in enumerate(p.exports):
            if p.class_name(e) != 'StaticMeshComponent':
                continue
            op = p.object_path(i + 1)
            if not op.startswith(lv + '.TheWorld.PersistentLevel.'):
                continue
            if op.count('.') == 4:
                comp_of_actor.setdefault((lv, op.split('.')[3]), []).append(op)
            try:
                used = pr.read_object(i + 1)[1]
            except Exception:
                continue
            nat = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
            rec = parse_generic(p, nat)
            if rec:
                rec['atlas_package'] = lm_package(lv)
                by_path[op.lower()] = rec; n += 1
        print('%s: lightmapped components %d' % (lv, n))
    pj = json.load(open(os.path.join(OUT, 'props.json'), encoding='utf-8'))
    pngdir = os.path.join(OUT, 'lightmaps')
    out = []
    hit = miss = 0
    atlases = set()
    for pr_ in pj['props']:
        comp = pr_.get('component')
        if not comp:
            cands = comp_of_actor.get((pr_['sublevel'], pr_['actor']), [])
            comp = cands[0] if len(cands) == 1 else None
        rec = by_path.get((comp or '').lower())
        if rec:
            atlases.add(rec['atlas'])
            png = os.path.join(pngdir, rec['atlas'] + '.png')
            out.append({'actor': pr_.get('actor'), 'component': comp, 'sublevel': pr_['sublevel'],
                        'atlas': rec['atlas'], 'coeffs': rec['coeffs'], 'atlas_package': rec['atlas_package'],
                        'atlas_png': ('lightmaps/' + rec['atlas'] + '.png') if os.path.exists(png) else None,
                        'coordScale': rec['coordScale'], 'coordBias': rec['coordBias'], 'scaleVec': rec['scaleVec']})
            hit += 1
        else:
            miss += 1
    json.dump({'map': MAP, 'count': hit, 'atlases_used': sorted(atlases),
               'atlases_without_png': sorted(a for a in atlases if not os.path.exists(os.path.join(pngdir, a + '.png'))),
               'note': 'atlas = _LM LightMapTexture2D (coeff0). lightmap UV = TEXCOORD_1*coordScale+coordBias. '
                       'Covers every level package; actor-placed props joined through their StaticMeshComponent.',
               'props': out}, open(os.path.join(OUT, 'lightmaps.json'), 'w'), indent=0)
    print('props with lightmap: %d   without: %d   unique atlases used: %d'
          % (hit, miss, len(atlases)))
    print('wrote', os.path.join(OUT, 'lightmaps.json'))


if __name__ == '__main__':
    main()
