"""Fire data for the campaign AI weapons (Gameplay 2026-10-23, sentries): weapon.json keeps only the data-object references, so this adds a
sibling `fire` block to out/campaign_characters/weapons/<pid>/weapon.json (campaign outputs only; MP / Escalation weapon files untouched):
  data: the AiData object's effective values for firing (FireInterval, FireIntervalModifier, InstantHitDamage(+Types), WeaponFireTypes,
        WeaponProjectiles, WeaponRange, clip / ammo / reload / burst / spread keys), and PlayerData's when it is another object
  class_defaults: the weapon CDO's firing / beam keys (Beam*, DamagePerSecond, ...: the beam weapons keep them on the class)
  projectiles[]: per WeaponProjectiles class, its CDO effective values (Speed, MaxSpeed, AccelRate, Damage, DamageRadius, MomentumTransfer,
        homing / seek / lock, LifeSpan, gravity / physics, explosion templates)
Values are authored (effective = authored + parents, UE units: cm, s); how native code combines them (e.g. homing) is PROVISIONAL.
    python weapon_fire.py [<pid> ...]   (default: the 8 sentry weapons)
"""
import json, os, re, sys
from collections import OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
import authored as A  # noqa: E402
W = os.path.join(AT, 'out', 'campaign_characters', 'weapons')
SENTRY = ['SentryLight', 'SentryRocket', 'SentryHomingRocket', 'SentryRepair', 'SentryDeathBeam', 'WarshipHomingRocketSentry', 'OmegaShipMG', 'OmegaShipRocket']
FIRE = re.compile(r'(Fire|Interval|Damage|Projectile|Range|Ammo|Clip|Reload|Burst|Shot|Spread|Beam|Charge|Heat|Lock|Homing|Seek|Target|Cone|Accuracy|Refire|Repair|Heal)', re.I)
PROJ = re.compile(r'(Speed|Accel|Damage|Radius|Momentum|Homing|Seek|Lock|Track|Life|Gravity|Physics|Explosion|Turn|Rotation|Velocity|Bounce|Fuse|Target|Curve|Arm)', re.I)

def pick(v, rx):
    return OD((k, x) for k, x in sorted(v.items()) if rx.search(k) and not (isinstance(x, str) and '.Default__' in x and 'Component' in x))

def fire(pid):
    cls = 'TransContent.TnWeapon' + pid; cdo = 'TransContent.Default__TnWeapon' + pid
    cv = A.values(cdo) if A.get(cdo) else {}
    ad, pd = cv.get('AiData'), cv.get('PlayerData')
    av = A.values(ad) if ad and A.get(ad) else {}; pv = A.values(pd) if pd and A.get(pd) and pd != ad else {}
    projs = []
    for pc in list(OD.fromkeys([p for p in (av.get('WeaponProjectiles') or pv.get('WeaponProjectiles') or cv.get('WeaponProjectiles') or []) if p])):
        pk, c = pc.split('.', 1); pcdo = '%s.Default__%s' % (pk, c)
        v = A.values(pcdo) if A.get(pcdo) else {}
        # damage / speed live in the projectile's data object (*_PROJDATA behind Data / AiData), not on the class
        dobj = OD((k, v.get(k)) for k in ('AiData', 'Data') if v.get(k) and A.get(v.get(k)))
        projs.append(OD([('class', pc), ('found', bool(v)), ('class_chain', [x['opath'] for x in A.chain(pcdo)][:4] if v else []), ('values', pick(v, PROJ)),
                         ('data_objects', dobj), ('data', OD(sorted((A.values(dobj.get('AiData') or dobj.get('Data')) or {}).items())) if dobj else None),
                         ('data_other', OD(sorted((A.values(dobj['Data']) or {}).items())) if dobj.get('Data') and dobj.get('Data') != dobj.get('AiData') else None)]))
    hitscan = bool(av.get('InstantHitDamage') or pv.get('InstantHitDamage')) and not projs
    return OD([('class', cls), ('ai_data', ad), ('player_data', pd),
               ('kind', 'projectile' if projs else ('beam' if av.get('DamagePerSecond') or any('Beam' in k for k in cv) else ('instant_hit' if hitscan else 'UNKNOWN'))),
               ('interval_note', 'FireInterval per fire mode; FireIntervalModifier.IntervalRange (Min / Max, RampTime) is the authored AI cadence (how native '
                                 'combines the two: PROVISIONAL)'),
               ('data', pick(av, FIRE)), ('player_data_values', pick(pv, FIRE) if pv else 'same object as AiData'),
               ('class_defaults', pick(cv, FIRE)), ('projectiles', projs),
               ('note', 'authored effective values (UE units: cm, s); native combination (homing, beam tick, repair) PROVISIONAL')])

def main(pids):
    for pid in pids:
        p = os.path.join(W, pid, 'weapon.json')
        if not os.path.exists(p): print(pid, 'no weapon.json'); continue
        j = json.load(open(p, encoding='utf-8'), object_pairs_hook=OD); j['fire'] = fire(pid)
        json.dump(j, open(p, 'w', encoding='utf-8'), indent=1, default=str)
        f = j['fire']; d = f['data']
        print(pid, f['kind'], {k: d.get(k) for k in ('FireInterval', 'InstantHitDamage', 'WeaponRange', 'MaxAmmoClipCount')},
              'modifier', d.get('FireIntervalModifier'), 'dps', d.get('DamagePerSecond'),
              [(x['class'].split('.')[-1], {k: (x['data'] or {}).get(k) for k in ('InitialSpeed', 'MaxSpeed', 'Damage', 'DamageRadius')}, 'life', x['values'].get('LifeSpan'))
               for x in f['projectiles']])

if __name__ == '__main__':
    main(sys.argv[1:] or SENTRY)
