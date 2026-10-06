"""Beast light-probe grids (BeastLightEnvironmentVolume.RenderSource -> BeastLightEnvironmentBox) -> Maps/<MAP>/light_probes.json

  python vs_light_probes.py <MAP>

Format (RE commit 13fd546, notes/MILESTONE03_RENDERING_LIGHTVIS_SHADOW.md addendum 2; RE-Workspace/tools/beast_probes.py;
CONFIRMED from default.xex lookup 0x82FC6DB8 / volume pick 0x82CCB228 / SH->ambient cube 0x82CBE520):
  BeastLightEnvironmentBox native tail after the tagged props: int32 BE count, then count x FSHVectorRGB (27 BE float32:
  R[9], G[9], B[9] planar, stock UE3 L2 SH order index = L*(L+1)+M). count = PointsX*PointsY*PointsZ; asserted
  len(tail) = 4 + 108*count. Point index = (z*PointsY + y)*PointsX + x.
Lookup (Rendering): local = worldToLocal * P_ue (row-vector UE matrix), grid coord g = (N-1)*(local+1)/2, trilinear.
Volumes without RenderSource (Berth / Gorge / Complex) carry no baked probes: listed with render_source null.
"""
import json, os, struct, sys, time
from collections import OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from vs_common import VS, map_sublevels, ue_actor_matrix, ue_to_gltf_matrix  # noqa: E402

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'
OUT = os.path.join(VS, 'Maps', MAP)

def box_sh(box):
    """decode the native SH tail of a BeastLightEnvironmentBox from the cooked package that holds its data"""
    inv = objtree.inv()
    rows = inv.execute("SELECT package FROM exports WHERE opath = ? AND class = 'BeastLightEnvironmentBox' ORDER BY serial_size DESC",
                       (box,)).fetchall()
    for (pkg,) in rows:
        p = objtree.package(pkg)
        for i, e in enumerate(p.exports, 1):
            if p.class_name(e) != 'BeastLightEnvironmentBox' or p.object_path(i) != box: continue
            props, used = p._tr.read_object(i)
            pr = {x['name']: x.get('value') for x in props}
            nat = p.data[e['serial_offset'] + used:e['serial_offset'] + e['serial_size']]
            if len(nat) < 4: continue
            n = struct.unpack_from('>i', nat, 0)[0]
            if n != pr['PointsX'] * pr['PointsY'] * pr['PointsZ'] or len(nat) != 4 + 108 * n: continue
            return pkg, n, [list(struct.unpack_from('>27f', nat, 4 + k * 108)) for k in range(n)]
    return None, 0, None

def main():
    subs = map_sublevels(MAP, A)
    vols = []
    for sub in subs:
        for (o,) in A.con().execute("SELECT opath FROM objects WHERE class = 'BeastLightEnvironmentVolume' AND opath LIKE ?",
                                    (sub + '.TheWorld.PersistentLevel.%',)).fetchall():
            v = A.values(o)
            loc = v.get('Location') or {}; rot = v.get('Rotation') or {}; s3 = v.get('DrawScale3D') or {}; pp = v.get('PrePivot') or {}
            M = ue_actor_matrix((loc.get('X', 0), loc.get('Y', 0), loc.get('Z', 0)),
                                (rot.get('Pitch', 0), rot.get('Yaw', 0), rot.get('Roll', 0)), v.get('DrawScale', 1.0),
                                (s3.get('X', 1), s3.get('Y', 1), s3.get('Z', 1)), (pp.get('X', 0), pp.get('Y', 0), pp.get('Z', 0)))
            rec = OD([('volume', o), ('sublevel', sub), ('bEnabled', v.get('bEnabled', False)), ('Priority', v.get('Priority', 0)),
                      ('Location', loc), ('Rotation', rot), ('DrawScale', v.get('DrawScale', 1.0)), ('DrawScale3D', s3),
                      ('ue_matrix', M.tolist()), ('gltf_matrix', ue_to_gltf_matrix(M)), ('PointDistance', v.get('PointDistance')),
                      ('render_source', v.get('RenderSource'))])
            box = v.get('RenderSource')
            if box:
                bv = A.values(box) or {}
                gen = A.values(bv.get('BoxSampleGenerator')) if bv.get('BoxSampleGenerator') else {}
                pkg, n, sh = box_sh(box)
                rec['box'] = OD([('object', box), ('data_package', pkg), ('PointsX', bv.get('PointsX')), ('PointsY', bv.get('PointsY')),
                                 ('PointsZ', bv.get('PointsZ')), ('Distance', bv.get('Distance')), ('m_worldToLocal', bv.get('m_worldToLocal')),
                                 ('BoxSampleGenerator', OD([('object', bv.get('BoxSampleGenerator')),
                                                            ('m_worldToLocal', gen.get('m_worldToLocal')), ('m_localToWorld', gen.get('m_localToWorld')),
                                                            ('m_ep', gen.get('m_ep', 0)), ('m_ep_note', 'not serialized = default 0 (EdgePolicy 0; RE: all MP generators)' if 'm_ep' not in gen else 'authored'),
                                                            ('mp', gen.get('mp', 0))])),
                                 ('count', n), ('sh_rgb_planar_L2', sh)])
                if sh is None: rec['box']['error'] = 'native SH tail not found / size assertion failed'
            vols.append(rec)
    out = OD([('map', MAP), ('generated_by', 'AssetTools/scripts/wfc/vs_light_probes.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('source', 'BeastLightEnvironmentVolume.RenderSource -> BeastLightEnvironmentBox native SH (RE 13fd546; CONFIRMED)'),
              ('format', {'sh': 'per point 27 float: R[9], G[9], B[9]; stock UE3 L2 real SH basis (index = L*(L+1)+M)',
                          'point_index': '(z*PointsY + y)*PointsX + x',
                          'lookup': 'local = P_ue (row vector) * m_worldToLocal (4x4 row-major as authored); g = (N-1)*(local+1)/2; trilinear',
                          'units': 'UE cm, Z-up (ue_matrix); gltf_matrix = same volume in glTF metres Y-up'}),
              ('volumes', vols),
              ('summary', {'volumes': len(vols), 'with_probes': sum(1 for x in vols if x.get('box') and x['box'].get('sh_rgb_planar_L2')),
                           'points': sum(x['box']['count'] for x in vols if x.get('box'))})])
    json.dump(out, open(os.path.join(OUT, 'light_probes.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    print(MAP, json.dumps(out['summary']))

if __name__ == '__main__':
    main()
