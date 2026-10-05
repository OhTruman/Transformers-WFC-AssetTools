"""Rigid-body data of ability-spawned physics actors -> manifests/mp_content/ability_physics.json  (Gameplay request 2026-10-05)

RollerSphere: TnAbilityRollerSphere spawns TnRollerMineAbility (PHYS_RigidBody) with SetLocalLinearVelocity(InitialVelocity)
(RE decomp TransGame.TnAbilityRollerSphere.SpawnMine). Values = effective authored data (authored.effective: authored over the
class chain, with the defining object). Properties absent from every cooked object are reported UNKNOWN, never guessed.
"""
import json, os, sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))

def eff(o, keys):
    e = A.effective(o) or {}
    return OrderedDict((k, {'value': e[k]['value'], 'from': e[k].get('from')} if k in e else
                        {'value': None, 'status': 'UNKNOWN: not present on the object or its cooked class chain'}) for k in keys)

def main():
    ab = 'TransGame.Default__TnAbilityRollerSphere'; act = 'TransGame.Default__TnRollerMineAbility'
    comp = act + '.StaticMeshComponent0'
    mesh = A.values(comp).get('StaticMesh'); bs = A.values(mesh).get('BodySetup')
    agg = (A.values(bs) or {}).get('AggGeom') or {}
    sph = [s.get('Radius') for s in agg.get('SphereElems') or []]
    scale = A.values(comp).get('Scale') or 1.0
    pm = A.values(bs).get('PhysMaterial')
    out = OrderedDict([
        ('generated_by', 'AssetTools/scripts/wfc/mp_ability_physics.py'),
        ('RollerSphere', OrderedDict([
            ('ability', eff(ab, ['SpawnDelay', 'SpawnOffset', 'InitialVelocity', 'ResourceRequired', 'CooldownReductionModifier'])),
            ('spawn_rule', 'SpawnLoc = Owner.Location + SpawnOffset rotated by Owner.Rotation; safe-location test radius = mesh '
                           'Bounds.SphereRadius * Scale * 1.1; Spawn(TnRollerMineAbility, SpawnLoc, Owner.Rotation); '
                           'SetLocalLinearVelocity(InitialVelocity) (local space: 2750 UU/s forward). Retry after 1 s if unsafe. '
                           'RE decomp TransGame.TnAbilityRollerSphere.SpawnMine (CONFIRMED)'),
            ('actor', eff(act, ['Physics', 'BuffRadius', 'ArmTime', 'MeleeImpulse', '_Fuse', '_DamageRadius', '_DamageAmount', '_DamageMomentum',
                                '_Health', 'MaxProjectileSpeed', 'bDamageAppliesImpulse', 'BlockRigidBody', 'CollisionPreset'])),
            ('melee_push', 'TakeDamage from a friendly melee hit: CollisionComponent.AddLinearVelocity(Normal(XY dir from attacker) * '
                           'MeleeImpulse) (RE decomp TransGame.TnRollerMineAbility.TakeDamage, CONFIRMED)'),
            ('component', eff(comp, ['StaticMesh', 'Scale', 'Scale3D', 'RBChannel', 'RBCollideWithChannels', 'RBDominanceGroup',
                                     'BlockRigidBody', 'bNotifyRigidBodyCollision', 'ScriptRigidBodyCollisionThreshold',
                                     'RBPositionCorrectionAmount', 'RBLinearVelocityCorrectionAmount', 'RBRotationCorrectionAmount',
                                     'RBAngularVelocityCorrectionAmount'])),
            ('collision_shape', {'mesh': mesh, 'body_setup': bs, 'sphere_radius_ue (mesh space)': sph,
                                 'effective_radius_ue (x component Scale %s)' % scale: [r * scale for r in sph],
                                 'effective_radius_m': [round(r * scale * 0.01, 4) for r in sph], 'other_elements': {k: len(v or []) for k, v in agg.items() if k != 'SphereElems'}}),
            ('body_setup', eff(bs, ['PhysMaterial', 'Mass', 'bEnableSleeping', 'bBlockZeroExtent', 'bBlockNonZeroExtent'])),
            ('body_setup_mass_note', 'RB_BodySetup.Mass = 1.0 is the engine class default (not authored on this body). Whether the WFC engine '
                                     'treats it as absolute mass or a scale on density x volume is native: UNKNOWN'),
            ('physical_material', eff(pm, ['Friction', 'Restitution', 'LinearDamping', 'AngularDamping', 'Density', 'SleepEnergyThreshold'])),
            ('physical_material_note', 'LinearDamping 0.6 is authored on the material; Friction 0.7 / Restitution 0.3 come from '
                                       'Engine.Default__PhysicalMaterial. AngularDamping and Density are not in any cooked object '
                                       '(stock UE3 source defaults are 0.0 and 1.0 - not evidence for this build: UNKNOWN)')]))])
    json.dump(out, open(os.path.join(AT, 'manifests', 'mp_content', 'ability_physics.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['RollerSphere']['collision_shape']), {k: v['value'] for k, v in out['RollerSphere']['physical_material'].items()})

if __name__ == '__main__':
    main()
