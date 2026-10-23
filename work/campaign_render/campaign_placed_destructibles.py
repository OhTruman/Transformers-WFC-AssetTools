"""Placed campaign destructibles (Gameplay 2026-10-23: A1's 1,018 placed TnStaticDestructibleActor etc.; 138 SeqEvent_HmDestructibleState-
Notification events gate progression). One row per placed destructible of the chapter's levels, read only (authored.db / inventory.db):
  actor (short + full path), class, sublevel, location_ue / location_gltf (0.01 * (X, Z, Y)), rotation_deg (UE rotator * 360 / 65536, UE
  signs), DrawScale / DrawScale3D (effective);
  blueprint: the DestructibleComponent's Blueprint (prefab instances: from the archetype, as vs_destructibles); decoded ONCE per blueprint in
  `blueprints` (campaign_characters/campaign_destructibles.blueprint(): pieces -> states with InitialHealth / AutomaticTransitionTime /
  effects / links NextStateHandle + TransitionTrigger + Enabled; meshes with content glTF + cooked sections) plus, per state, the meshes it
  shows (glTF) and the collision flags its mesh effects carry (effective Collide* / Block* / Collision* values; none = UNKNOWN);
  damage: blueprint DamageAngle / AIDamageModifier / RadiusDamageModifier / MinRadiusDamageDistanceForModifier (+ any *Damage* blueprint
  value) and the actor's DestructibleDamageScale / bCanBeDamaged; instance: ReplicatedPieceStates, the component's Pieces;
  kismet: every Kismet object of the chapter whose Originator (or any object property) names the actor, with class (SeqEvent_Hm... /
  Destroyed / TakeDamage) and the property that names it.
    python campaign_placed_destructibles.py <CH>  -> out/campaign_render/<CH>/destructibles.json
"""
import json, os, re, sys
from collections import Counter, OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'work', 'campaign_characters')); sys.path.insert(0, HERE)
import campaign_destructibles as CD  # noqa: E402  (imports vs_destructibles with its default map; nothing is run)
import campaign_render as CR  # noqa: E402
A = CD.A; field = CD.field
DEG = 360.0 / 65536.0
DEST = ('TnStaticDestructibleActor', 'TnDestructibleActor', 'HmDestructibleActorBase', 'TnDynamicDestructibleActor')
COLL = re.compile(r'(Collide|Block|Collision)', re.I)

def eff(o, k):
    v = field(o, k); return v.get('value') if isinstance(v, dict) else v

_TPL = {}
def template_collision(cls):
    """collision flags of the effect factory class's default mesh-component template(s) (the component a state's mesh is spawned from;
    vs_destructibles uses the same source), e.g. HM_Engine.Default__HmStaticMeshDestructionEffectFactory.TextureLightmapMeshTemplate0"""
    if cls in _TPL: return _TPL[cls]
    out = OD()
    for pk in ('HM_Engine', 'TransGame', 'TransContent'):
        cdo = '%s.Default__%s' % (pk, cls)
        if not A.get(cdo): continue
        for c in A.children(cdo):
            if not (c.get('class') or '').endswith('Component'): continue
            v = {k: x for k, x in A.values(c['opath']).items() if COLL.search(k) and not isinstance(x, (dict, list))}
            if v: out[c['opath']] = v
        break
    _TPL[cls] = out
    return out

def state_view(bp_rec):
    """per piece / state: meshes shown (glTF) and the collision flags of its mesh effects"""
    out = []
    for pc in bp_rec['pieces']:
        for st in pc['states']:
            meshes, coll = [], []
            for e in st['effects']:
                ev = e.get('effective') or {}; au = e.get('authored') or {}
                m = au.get('Mesh') or au.get('MeshTemplate') or ev.get('Mesh') or ev.get('MeshTemplate')
                if m: meshes.append(OD([('mesh', m), ('effect_class', e['class']), ('gltf', (bp_rec['meshes'].get(m) or {}).get('gltf') or CD.VD.gltf(m))]))
                c = {k: v for k, v in ev.items() if COLL.search(k) and not isinstance(v, (dict, list))}
                if c: coll.append(OD([('effect_class', e['class']), ('source', 'effect factory (effective)'), ('flags', c)]))
                if m:
                    t = template_collision(e['class'])
                    if t: coll.append(OD([('effect_class', e['class']), ('source', 'factory class default mesh-component template (inherited)'),
                                          ('templates', t)]))
                    mv = A.values(m) if A.get(m) else {}
                    mc = {k: mv.get(k) for k in ('UseSimpleBoxCollision', 'UseSimpleLineCollision', 'UseSimpleRigidBodyCollision', 'BodySetup') if k in mv}
                    if mc: coll.append(OD([('mesh', m), ('source', 'mesh collision setup'), ('flags', mc)]))
            out.append(OD([('piece', pc['PieceName']), ('handle', st['handle']), ('StateName', (st['StateName'] or {}).get('value')),
                           ('InitialHealth', (st['InitialHealth'] or {}).get('value')),
                           ('AutomaticTransitionTime', (st['AutomaticTransitionTime'] or {}).get('value')),
                           ('meshes', meshes), ('collision', coll or ('none: this state shows no mesh' if not meshes
                                                                     else "UNKNOWN: no collision flag found for this state's meshes"))]))
    return out

def main(ch):
    levels = CR.chapter_levels(ch); ph = ','.join('?' * len(levels))
    exports = CD.INV.execute('select distinct opath, class from exports where package in (%s)' % ph, levels).fetchall()
    actors = sorted(o for o, c in exports if c in DEST and o.count('.') == 3 and '.TheWorld.PersistentLevel.' in o)
    aset = set(actors); short = {a.rsplit('.', 1)[-1]: a for a in actors}
    # Kismet references (one scan): objects under a Main_Sequence naming an actor, by property
    kis = {}
    for o, c in exports:
        if '.PersistentLevel.Main_Sequence' not in o: continue
        r = (A.get(o) or {}).get('props') or {}
        for k, v in r.items():
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, str) and (x in aset or (x.rsplit('.', 1)[-1] in short and '.PersistentLevel.' in x)):
                    tgt = x if x in aset else short[x.rsplit('.', 1)[-1]]
                    kis.setdefault(tgt, []).append(OD([('object', o), ('class', c), ('property', k)]))
    bps, rows, why = OD(), [], Counter()
    for a in actors:
        r = A.get(a) or {}; own = r.get('props') or {}
        comp = own.get('DestructibleComponent') or eff(a, 'DestructibleComponent')
        cv = ((A.get(comp) or {}).get('props') or {}) if comp else {}
        if comp and not cv.get('Blueprint'):
            cv = {**{k: v for k, v in A.values(comp).items() if k in ('Blueprint', 'Pieces', 'BlueprintVersion', 'CodeVersion')}, **cv}
        bp = cv.get('Blueprint')
        if bp and bp not in bps:
            try:
                rec = CD.blueprint(bp, levels); rec['states_view'] = state_view(rec); bps[bp] = rec
            except Exception as x: bps[bp] = {'blueprint': bp, 'error': repr(x)[:300]}
        why['with_blueprint' if bp else 'no_blueprint'] += 1
        L = own.get('Location'); R = own.get('Rotation') or {}
        rows.append(OD([('actor', a.rsplit('.', 1)[-1]), ('object', a), ('class', r.get('class')), ('sublevel', a.split('.')[0]),
                        ('location_ue', L), ('location_gltf', [round(0.01 * L['X'], 4), round(0.01 * L['Z'], 4), round(0.01 * L['Y'], 4)] if L else None),
                        ('rotation_deg', OD((k.lower(), round(R.get(k, 0) * DEG, 3)) for k in ('Yaw', 'Pitch', 'Roll'))),
                        ('DrawScale', eff(a, 'DrawScale')), ('DrawScale3D', eff(a, 'DrawScale3D')),
                        ('blueprint', bp), ('component', comp),
                        ('damage', OD([('DestructibleDamageScale', eff(a, 'DestructibleDamageScale')), ('bCanBeDamaged', eff(a, 'bCanBeDamaged'))])),
                        ('instance', OD([('ReplicatedPieceStates', eff(a, 'ReplicatedPieceStates')), ('Pieces', cv.get('Pieces'))])),
                        ('collision_flags', {k: eff(a, k) for k in ('bCollideActors', 'bBlockActors', 'bProjTarget', 'CollisionType')}),
                        ('kismet', kis.get(a, []))]))
    for bp, rec in bps.items():
        if 'error' in rec: continue
        d = rec.get('blueprint_defaults (inherited)') or {}
        rec['damage_modifiers'] = {k: (v.get('value') if isinstance(v, dict) else v) for k, v in d.items()}
    out = OD([('chapter', ch), ('generated_by', 'AssetTools/work/campaign_render/campaign_placed_destructibles.py'),
              ('source', 'manifests/authored.db + inventory.db (authored / effective values; cooked levels)'),
              ('units', 'location_gltf metres Y-up = 0.01 * (X, Z, Y)_UE; rotation_deg = UE rotator * 360 / 65536 (UE signs); health in UE units'),
              ('counts', OD([('destructibles', len(rows)), ('blueprints', len(bps)), ('with_kismet', sum(1 for x in rows if x['kismet'])),
                             ('kismet_refs_by_class', OD(Counter(k['class'] for x in rows for k in x['kismet']).most_common()))]
                            + list(why.items()) + [('blueprint_errors', [b for b, r in bps.items() if 'error' in r])])),
              ('destructibles', rows), ('blueprints', bps)])
    json.dump(out, open(os.path.join(CR.OUTR, ch, 'destructibles.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['counts'])[:900])

if __name__ == '__main__':
    main(sys.argv[1])
