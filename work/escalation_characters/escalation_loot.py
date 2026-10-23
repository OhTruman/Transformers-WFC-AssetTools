"""Escalation loot pickup (Gameplay M11, 2026-10-23): TransContent.TnAbilityResourcePickup (the Inventory a kill drops) and its
DroppedPickupClass TnAbilityResourceDroppedPickup (the world actor): authored / effective CDO values (AddedResource, LifeSpan, Lifetime,
SeekRadius / SeekSpeed, the CollisionCylinder radius / height / offset, PickupSound, messages), the effect it shows
(DroppedPickupParticles PSC: template + translation) decoded (vs_destructibles.particle_rec: emitters, materials, mesh emitters), and the
mesh emitters' meshes as content glTF. Read only -> manifests/escalation/escalation_loot_pickup.json. Units: UE (cm, s).
"""
import json, os, re, sys
from collections import OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.argv = sys.argv[:1]; sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
import authored as A, vs_destructibles as VD  # noqa: E402
PK, DR = 'TransContent.Default__TnAbilityResourcePickup', 'TransContent.Default__TnAbilityResourceDroppedPickup'
KEEP = re.compile(r'(Resource|Life|Seek|Radius|Height|Pickup|Sound|Message|Particle|Hidden|Touch|Collision|Desire|Class)', re.I)

def vals(o): return OD((k, v) for k, v in sorted(A.values(o).items()) if KEEP.search(k))

def main():
    pv, dv = A.values(PK), A.values(DR)
    psc = pv.get('DroppedPickupParticles'); pscv = A.values(psc) if psc else {}
    ps = pscv.get('Template'); rec = VD.particle_rec(ps, []) if ps else None
    t = json.dumps(rec, default=str) if rec else ''
    meshes = sorted(set(re.findall(r'"([A-Za-z0-9_]+\.[A-Za-z0-9_.]*_STAT)"', t)))
    cyl = pv and dv.get('CollisionComponent'); cv = A.values(cyl) if cyl else {}
    out = OD([('generated_by', 'AssetTools/work/escalation_characters/escalation_loot.py'),
              ('source', 'manifests/authored.db: class defaults (effective = authored + parents) + compiled particle stream'),
              ('units', 'UE: cm, seconds (gltf metres = 0.01 x)'),
              ('pickup', OD([('class', 'TransContent.TnAbilityResourcePickup'), ('class_chain', [c['opath'] for c in A.chain(PK)]), ('values', vals(PK))])),
              ('dropped_pickup', OD([('class', pv.get('DroppedPickupClass')), ('class_chain', [c['opath'] for c in A.chain(DR)]), ('values', vals(DR)),
                                     ('collision_cylinder', OD([('object', cyl), ('CollisionRadius', cv.get('CollisionRadius')),
                                                                ('CollisionHeight', cv.get('CollisionHeight')), ('Translation', cv.get('Translation')),
                                                                ('CollideActors', cv.get('CollideActors'))]))])),
              ('summary', OD([('AddedResource', pv.get('AddedResource')), ('LifeSpan_s (actor auto-destroy)', dv.get('LifeSpan')),
                              ('Lifetime_s', dv.get('Lifetime')), ('SeekRadius_uu', dv.get('SeekRadius')), ('SeekSpeed_uu_s', dv.get('SeekSpeed')),
                              ('pickup_radius_uu (CollisionCylinder)', cv.get('CollisionRadius')), ('pickup_height_uu', cv.get('CollisionHeight')),
                              ('PickupSound', pv.get('PickupSound')),
                              ('note', 'LifeSpan (10 s) and Lifetime (60 s) are both authored on the dropped pickup; which one ends the drop '
                                       '(HmDroppedPickup / TnDroppedPickup native or script) is RE\'s to confirm - PROVISIONAL')])),
              ('effect', OD([('component', psc), ('template', ps), ('translation', pscv.get('Translation')), ('scale3d', pscv.get('Scale3D')),
                             ('mesh_emitter_meshes', [OD([('mesh', m), ('gltf', VD.gltf(m))]) for m in meshes]),
                             ('particle_system', rec)])),
              ('mesh', 'none: neither class authors a StaticMesh / SkeletalMesh component; the drop is drawn by its particle system')])
    os.makedirs(os.path.join(AT, 'manifests', 'escalation'), exist_ok=True)
    json.dump(out, open(os.path.join(AT, 'manifests', 'escalation', 'escalation_loot_pickup.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['summary'], default=str)); print([(m['mesh'], m['gltf']) for m in out['effect']['mesh_emitter_meshes']])

if __name__ == '__main__':
    main()
