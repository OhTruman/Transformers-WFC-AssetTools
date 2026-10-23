"""TnTransformingWorldActors into the unit world.glb (Rendering / Integration 2026-10-23: A1's intro lift TnTransformingWorldActor_6275 is
in no world.glb, so it is not drawn). vs_map writes static-mesh actors only; a TnTransformingWorldActor (HmInterpolatedLightMapped-
SkeletalMeshActor) draws its SkeletalMeshComponent's mesh. Per unit: world.glb is rebuilt from its split input (work/campaign_pilot/
VerticalSlice/Maps/<CH>/sublevels/<level>/world.glb, byte-identical to the unit copy) + one node per TnTransformingWorldActor of that level:
  mesh: the skeletal mesh's content glTF at its BIND POSE (POSITION / NORMAL / TEXCOORD_0 / TEXCOORD_1; skin dropped; umodel mesh space,
        the same convention as the static mesh glTFs vs_map embeds); materials: component Materials overrides else the mesh's Materials
        slots, resolved / bound exactly as vs_map does (materials.resolve -> pbr_material -> bind_textures, URIs relative to the split dir)
  node: name = the actor, matrix = ue_to_gltf_matrix(component S*R*T x actor matrix(Location, Rotation, DrawScale, DrawScale3D, PrePivot)),
        extras {actor, class, component, mesh, skeletal_bind_pose: true, anim_sets, added_by}
The state the matinee / Kismet poses at runtime (AnimSets clips) is in matinee_skeletal.json; the bind pose is the authored rest shape
(PROVISIONAL as the 'current state' of a transforming actor that starts mid-animation). No lightmap extras (lit dynamically here).
    python add_transforming_actors.py <CH>   -> out/campaign_render/<CH>/<unit>/world.glb + <CH>/transforming_actors.json
"""
import hashlib, json, os, sqlite3, sys
from collections import Counter, OrderedDict as OD
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc')); sys.path.insert(0, HERE)
from vs_common import (GLB, read_glb, accessor, load_gltf, pbr_material, bind_textures, BLEND, ue_actor_matrix, ue_to_gltf_matrix,  # noqa: E402
                       ue_scale, ue_rot, ue_trans, ROOT)
import authored as A, materials, mp_roster as M  # noqa: E402
import campaign_render as CR  # noqa: E402
INV = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
CLASSES = ('TnTransformingWorldActor',)
TAG = 'AssetTools add_transforming_actors.py'

def xyz(d, ks, dflt):
    return [d.get(k, dflt) for k in ks] if isinstance(d, dict) else (d if d is not None else [dflt] * 3)

def open_glb(path):
    j, bins = read_glb(path); g = GLB(); g.j = j; g.bin = bytearray(bins[0])
    for k in ('nodes', 'meshes', 'materials', 'accessors', 'bufferViews', 'images', 'textures'): g.j.setdefault(k, [])
    g.j.setdefault('samplers', [{}]); g.j.setdefault('scenes', [{'nodes': []}])
    for ti, t in enumerate(g.j['textures']): g._img.setdefault(g.j['images'][t['source']]['uri'], ti)
    for mi, m in enumerate(g.j['materials']):
        w = (m.get('extras') or {}).get('wfc_material')
        if w: g._mat.setdefault(w, mi)
    return g

_MR = {}
def resolve_material(name, mesh_op):
    """umodel glTF material name -> full material object path: a Material* export of that name, the mesh's package first, else the one
    cooked in the most packages; umodel's placeholder 'dummy_material_N' (an empty slot) -> None"""
    if not name or name.startswith('dummy_material'): return None
    k = (name, mesh_op.split('.')[0])
    if k not in _MR:
        rows = INV.execute("select opath, count(distinct package) n from exports where (opath like ? or opath = ?) and class like 'Material%' "
                           "group by opath order by n desc", ('%.' + name, name)).fetchall()
        own = [o for o, _ in rows if o.split('.')[0] == k[1]]
        _MR[k] = own[0] if own else (rows[0][0] if rows else None)
    return _MR[k]

def material_index(g, opath, split_dir):
    key = opath or '<none>'
    if key in g._mat: return g._mat[key]
    r = materials.resolve(opath) if opath else {'roles': {}, 'blend_mode': 'BLEND_Opaque', 'two_sided': False}
    m = pbr_material((opath or 'WFC_Default').rsplit('.', 1)[-1], r.get('roles', {}), split_dir,
                     extras={'wfc_material': opath, 'blend_mode': r.get('blend_mode')},
                     double_sided=r.get('two_sided', False), blend=BLEND.get(r.get('blend_mode'), 'OPAQUE'))
    return g.material(key, bind_textures(g, m))

def chapter(ch):
    R = os.path.join(CR.OUTR, ch); S = os.path.join(AT, 'work', 'campaign_pilot', 'VerticalSlice', 'Maps', ch, 'sublevels')
    levels = CR.chapter_levels(ch); ph = ','.join('?' * len(levels))
    acts = sorted((o, c) for o, c in INV.execute('select distinct opath, class from exports where package in (%s)' % ph, levels)
                  if c in CLASSES and o.count('.') == 3 and '.TheWorld.PersistentLevel.' in o)
    by_lv = {}
    for o, c in acts: by_lv.setdefault(o.split('.')[0], []).append((o, c))
    rep, why = OD(), Counter()
    for lv, items in sorted(by_lv.items()):
        ud = os.path.join(R, CR.outname(lv)); src = os.path.join(S, lv, 'world.glb'); dst = os.path.join(ud, 'world.glb')
        if not (os.path.isdir(ud) and os.path.exists(src)): why['level_without_unit_or_split'] += len(items); rep[lv] = 'no unit dir / split world.glb'; continue
        g = open_glb(src); split_dir = os.path.join(S, lv); rows = []
        for o, c in items:
            v = A.values(o); comp = v.get('SkeletalMeshComponent'); cv = A.values(comp) if comp else {}
            skm = cv.get('SkeletalMesh'); gl = M.gltf(skm) if skm else None
            row = OD([('actor', o.rsplit('.', 1)[-1]), ('class', c), ('component', comp), ('mesh', skm), ('gltf', gl)])
            if not gl: row['skipped'] = 'no SkeletalMesh / no content glTF'; rows.append(row); why['no_mesh'] += 1; continue
            gj, gb = load_gltf(os.path.join(ROOT, gl))
            slots = [x for x in (A.values(skm).get('Materials') or [])] if A.get(skm) else []
            if not any(slots):   # SkeletalMesh slots are native-serialized: resolve the glTF's slot names (umodel) by object name
                slots = [resolve_material(m.get('name'), skm) for m in gj.get('materials') or []]
                row['material_source'] = 'glTF slot names resolved by name (inventory.db; mesh package first)'
            row['materials'] = slots
            over = cv.get('Materials') or []
            prims = []
            for pr in gj['meshes'][0]['primitives']:
                at = pr['attributes']
                if gj['accessors'][at['POSITION']]['count'] == 0 or 'indices' not in pr or gj['accessors'][pr['indices']]['count'] == 0: continue
                attrs = {'POSITION': g.acc(accessor(gj, gb, at['POSITION']).astype('f4'), 'VEC3', True, 34962)}
                for k, t in (('NORMAL', 'VEC3'), ('TEXCOORD_0', 'VEC2'), ('TEXCOORD_1', 'VEC2')):
                    if k in at: attrs[k] = g.acc(accessor(gj, gb, at[k]).astype('f4'), t, target=34962)
                slot = pr.get('material', 0)
                mop = over[slot] if slot < len(over) and over[slot] else (slots[slot] if slot < len(slots) else None)
                prims.append({'attributes': attrs, 'indices': g.acc(accessor(gj, gb, pr['indices']).astype('u4'), 'SCALAR', target=34963),
                              'material': material_index(g, mop, split_dir)})
            if not prims: row['skipped'] = 'mesh has no geometry'; rows.append(row); why['no_geometry'] += 1; continue
            mi = g.mesh(skm.rsplit('.', 1)[-1], prims)
            cm = ue_scale([cv.get('Scale', 1.0) * x for x in xyz(cv.get('Scale3D'), 'XYZ', 1.0)]) @ \
                 ue_rot(*xyz(cv.get('Rotation'), ('Pitch', 'Yaw', 'Roll'), 0)) @ ue_trans(xyz(cv.get('Translation'), 'XYZ', 0.0))
            am = ue_actor_matrix(xyz(v.get('Location'), 'XYZ', 0.0), xyz(v.get('Rotation'), ('Pitch', 'Yaw', 'Roll'), 0), v.get('DrawScale', 1.0),
                                 xyz(v.get('DrawScale3D'), 'XYZ', 1.0), xyz(v.get('PrePivot'), 'XYZ', 0.0))
            mat = ue_to_gltf_matrix(cm @ am)
            g.node({'name': row['actor'], 'mesh': mi, 'matrix': mat,
                    'extras': {'actor': row['actor'], 'class': c, 'component': comp, 'mesh': skm, 'skeletal_bind_pose': True,
                               'anim_sets': [x for x in cv.get('AnimSets') or [] if x], 'added_by': TAG}})
            row.update(primitives=len(prims), material_slots=[p['material'] for p in prims], gltf_matrix=mat); rows.append(row); why['added'] += 1
        g.write(dst)
        rep[lv] = OD([('unit', CR.outname(lv)), ('source_sha256', hashlib.sha256(open(src, 'rb').read()).hexdigest()),
                      ('world_glb_sha256', hashlib.sha256(open(dst, 'rb').read()).hexdigest()), ('actors', rows)])
    # the materials the new nodes use go into the chapter's render-material list, which the materials step builds into each unit's
    # materials_glsl.json (Rendering's loader resolves a sub's material only from that file); rerun that step for these units after
    used = sorted({m for l in rep.values() if isinstance(l, dict) for a in l['actors'] for m in a.get('materials') or [] if m})
    lst = os.path.join(AT, 'manifests', 'campaign', 'render_materials', ch + '.txt')
    have = [x.strip() for x in open(lst, encoding='utf-8')] if os.path.exists(lst) else []
    new = [m for m in used if m not in have]
    if new:
        raw = open(lst, 'rb').read() if os.path.exists(lst) else b''
        with open(lst, 'ab') as f:
            if raw and not raw.endswith(b'\n'): f.write(b'\n')
            f.write(''.join(m + '\n' for m in new).encode('utf-8'))
    units = sorted({l['unit'] for l in rep.values() if isinstance(l, dict) and any('primitives' in a for a in l['actors'])})
    out = OD([('chapter', ch), ('generated_by', 'AssetTools/work/campaign_render/add_transforming_actors.py'), ('counts', dict(why)),
              ('materials_used', used), ('materials_added_to_render_list', new),
              ('units_to_rerun_materials', [lv for lv, l in rep.items() if isinstance(l, dict) and l['unit'] in units]), ('levels', rep)])
    json.dump(out, open(os.path.join(R, 'transforming_actors.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(ch, json.dumps(out['counts']))

if __name__ == '__main__':
    for ch in sys.argv[1:]: chapter(ch)
