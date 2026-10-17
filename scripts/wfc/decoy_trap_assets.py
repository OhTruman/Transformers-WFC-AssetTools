"""Decoy Trap (Scout MP ability) asset manifest for Gameplay / Systems (Integration 2026-10-18; RE MP_DECOY_TRAP_RE.md 3f0271f).

Read-only over authored.db / inventory.db / ExtractedAssets. Writes
  manifests/abilities/decoy_trap_assets.json
  out/abilities/decoy_trap/  (icon PNG copies, DecoyTrap_FX + the inherited pickup / anim-notify FX as pstream system JSON)
Every value is cooked / authored data (CONFIRMED) unless a 'confidence' field says otherwise.
"""
import json, os, shutil, sqlite3, sys
from collections import OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import authored as A  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EA = os.path.abspath(os.path.join(ROOT, '..', 'ExtractedAssets'))
OUT_JSON = os.path.join(ROOT, 'manifests', 'abilities', 'decoy_trap_assets.json')
OUT_DIR = os.path.join(ROOT, 'out', 'abilities', 'decoy_trap')
CHARS = os.path.join(EA, 'VerticalSlice', 'Characters')
WEAPONS = os.path.join(EA, 'VerticalSlice', 'Weapons')
DB = sqlite3.connect(os.path.join(ROOT, 'manifests', 'authored.db'))
INV = sqlite3.connect(os.path.join(ROOT, 'manifests', 'inventory.db'))

def props(o):
    r = DB.execute('select props from objects where opath=?', (o,)).fetchone()
    return json.loads(r[0]) if r and r[0] else ({} if r else None)

def resolved(o):
    """component / CDO props with the archetype chain filled in (nearest wins), plus where each value came from"""
    out, src = {}, {}
    while o:
        r = DB.execute('select archetype, props from objects where opath=?', (o,)).fetchone()
        if not r: break
        for k, v in (json.loads(r[1]) if r[1] else {}).items():
            if k not in out: out[k] = v; src[k] = o
        o = r[0]
    return {'values': out, 'value_source': src}

def rel(p): return os.path.relpath(p, os.path.join(EA, '..')).replace(os.sep, '/')

def texture(opath, png):
    f = os.path.join(EA, 'content', *png.split('/'))
    ok = os.path.exists(f)
    d = {'texture': opath, 'png': 'ExtractedAssets/content/' + png, 'exists': ok}
    if ok:
        from PIL import Image
        im = Image.open(f); d.update({'size': list(im.size), 'mode': im.mode, 'bytes': os.path.getsize(f)})
        os.makedirs(os.path.join(OUT_DIR, 'icons'), exist_ok=True)
        shutil.copy2(f, os.path.join(OUT_DIR, 'icons', os.path.basename(f)))
        d['copy'] = 'AssetTools/out/abilities/decoy_trap/icons/' + os.path.basename(f)
    return d

def fx(ps):
    import pstream
    s = pstream.system(ps)
    os.makedirs(os.path.join(OUT_DIR, 'fx'), exist_ok=True)
    fn = ps.split('.')[-1] + '.pstream.json'
    json.dump(s, open(os.path.join(OUT_DIR, 'fx', fn), 'w', encoding='utf-8'), indent=1)
    em = s.get('emitters') or []
    return OD([('template', ps), ('file', 'AssetTools/out/abilities/decoy_trap/fx/' + fn), ('missing', bool(s.get('missing_in'))),
               ('emitters', len(em)), ('lods_per_emitter', sorted({len(e.get('lods') or []) for e in em})),
               ('assignment_complete_all_lods', all(L.get('assignment_complete') for e in em for L in e.get('lods') or [])),
               ('provisional_distributions', sum(1 for e in em for L in e.get('lods') or [] for m in L.get('compiled_modules') or []
                                                 for d in m.get('distributions') or [] if d.get('confidence') != 'CONFIRMED'))])

def main():
    ability = props('TransGame.Default__TnAbilityDecoyTrap')
    trap = props('TransGame.Default__TnDecoyTrap')
    drop = resolved('TransGame.Default__TnDroppedPickupDecoyTrap')
    buff = props('TransGame.Default__TnBuffDecoyTrap')
    m = OD()
    m['generated_by'] = 'AssetTools/scripts/wfc/decoy_trap_assets.py'
    m['mechanics_source'] = 'RE-Workspace/work/handoff/MP_DECOY_TRAP_RE.md (3f0271f)'
    m['data_sources'] = ['manifests/authored.db (CDOs)', 'manifests/inventory.db', 'ExtractedAssets/VerticalSlice/{Characters,Weapons}',
                         'scripts/wfc/pstream.py (compiled particle modules)']
    m['classes'] = {c: props('TransGame.Default__' + c) for c in
                    ('TnAbilityDecoyTrap', 'TnDecoyTrap', 'TnBuffDecoyTrap', 'TnBuffDotFromDecoy', 'TnBuffIncreaseDecoyTrapTime',
                     'TnSkillDecoyDot', 'TnSkillIncreaseDecoyTrapTime', 'TnDamageTypeDecoyDot', 'TnObjectiveMarkerTypeDecoyTrap',
                     'TnXpEventTypeKillDecoyTrap')}
    m['classes']['TnDroppedPickupDecoyTrap (archetype chain resolved)'] = drop

    # ---- the trap's visual: no mesh of its own ----
    weapons = []
    for w in sorted(os.listdir(WEAPONS)):
        f = os.path.join(WEAPONS, w, 'weapon.json')
        if not os.path.exists(f): continue
        d = json.load(open(f, encoding='utf-8'))
        cd = d.get('class_defaults (weapon CDO, sub-objects resolved)') or {}
        weapons.append(OD([('weapon', w), ('class', d.get('class')), ('glb', (d.get('mesh') or {}).get('glb')),
                           ('mesh_object', (d.get('mesh') or {}).get('object')),
                           ('materials', [x.get('material') for x in (d.get('mesh') or {}).get('materials') or []]),
                           ('PickupScale', cd.get('PickupScale')), ('PickupRotationRate', cd.get('PickupRotationRate')),
                           ('DroppedPickupClass', cd.get('DroppedPickupClass')),
                           ('usable_by_chassis', d.get('usable_by_chassis'))]))
    m['trap_visual'] = OD([
        ('own_mesh', None),
        ('rule', 'TnDecoyTrap has no mesh: DroppedPickupMesh None, PickupFactoryMesh = MeshComponentA whose StaticMesh is unset through '
                 'the chain (TnBuffPickup.MeshComponentA sets only render flags). TnAbilityDecoyTrap.OnDropInventory -> SetDecoyWeapon(owner '
                 'current weapon class): the dropped trap shows THAT WEAPON\'s pickup mesh (RE §2, CONFIRMED). So the trap mesh, materials '
                 'and defrag material are the per-weapon ones already exported in VerticalSlice/Weapons/<W>/weapon.{glb,json}.'),
        ('spin', 'weapon PickupRotationRate with Yaw negated (RE §2)'),
        ('scale', 'weapon PickupScale (HIGH: the dropped-weapon path applies it as for a real drop)'),
        ('highlight_fx', OD([('component', 'HighlightFx0 (StaticMeshComponent, inherited TnDroppedPickupDefrag)'),
                             ('static_mesh', resolved('TransGame.Default__TnDroppedPickupDecoyTrap.HighlightFx0')['values'].get('StaticMesh')),
                             ('material', drop['values'].get('HighlightFxMat')),
                             ('values', resolved('TransGame.Default__TnDroppedPickupDecoyTrap.HighlightFx0'))])),
        ('pickup_effect', OD([('component', 'PickupEffect0 (ParticleSystemComponent, inherited TnDroppedPickupDefrag)'),
                              ('values', resolved('TransGame.Default__TnDroppedPickupDecoyTrap.PickupEffect0'))])),
        ('defragger', 'Defragger0: TnDefragger with no authored values through the chain (the fade-in / glitch drives the weapon '
                      'material\'s defrag parameter; the WEP materials sample WEP_Shared_p WEP_Defrag_Alphas)'),
        ('candidate_weapons (all exported weapons; the trap copies whatever the thrower holds)', weapons)])

    # ---- collision ----
    m['collision'] = OD([
        ('CollisionCylinder (world collision of the dropped trap)', resolved('TransGame.Default__TnDroppedPickupDecoyTrap.CollisionCylinder')),
        ('TouchCylinder (pickup volume; RE §3)', resolved('TransGame.Default__TnDroppedPickupDecoyTrap.TouchCylinder')),
        ('note', 'Cylinders only; no mesh collision (the weapon mesh is not a collider: TnBuffPickup.MeshComponentA CollideActors false). '
                 'InstantKillDamageTypes and CanBeDestroyed are in the resolved TnDroppedPickupDecoyTrap values.')])

    # ---- animations per chassis ----
    want = {'Skill_Barrier': 'deploy (ability OnTriggerAnimParams; thrower)',
            'HitReactions_React_DecoyTrap_In': 'stun loop (TnBuffDecoyTrap.IntroLoopAnimation; victim, robot form)',
            'HitReactions_React_DecoyTrap_Out': 'stun end (TnBuffDecoyTrap.OutroAnimation; victim, robot form)',
            'HitReactions_React_DecoyTrap': 'present in the AnimSets; no class references it (UNKNOWN use)'}
    chassis = []
    for c in sorted(os.listdir(CHARS)):
        f = os.path.join(CHARS, c, 'character.json')
        if not os.path.exists(f): continue
        d = json.load(open(f, encoding='utf-8'))
        rob = (d.get('robot') or {}).get('animations') or []
        notify_only = (d.get('notify_only_clips (ability clips without glb track)') or {}).get('clips') or []
        anims = OD()
        for n in want:
            e = next((x for x in rob if x.get('sequence') == n), None)
            src = 'robot.glb track'
            if e is None:
                e = next((x for x in notify_only if x.get('sequence') == n), None); src = 'notify-only (no glb track)'
            anims[n] = None if e is None else OD([('animset', e.get('source_animset')), ('in', src), ('duration_s', e.get('duration_s')),
                                                  ('notifies', e.get('notifies') or [])])
        ab = d.get('abilities') or {}
        chassis.append(OD([('chassis', c), ('display', d.get('display')), ('class', d.get('class (chassis DefaultSpecialty)')),
                           ('mp_status', d.get('mp_status')),
                           ('decoy_in_class_pool', 'DecoyTrap' in (ab.get('class_pool') or [])),
                           ('glb', 'ExtractedAssets/VerticalSlice/Characters/%s/robot.glb' % c), ('animations', anims)]))
    m['animations'] = OD([('roles', want),
                          ('note', 'No dedicated deploy or hold anim exists: the ability plays Skill_Barrier (the Barrier ability\'s clip) '
                                   'once at trigger; there is no hold state. The stun clips play in robot form only (RE §4); a vehicle-form '
                                   'victim gets no anim. AnimSet = AnimName lookup on the pawn\'s own sets (AnimSet None in the CDO).'),
                          ('per_chassis', chassis),
                          ('missing', [OD([('chassis', x['chassis']), ('anim', n)]) for x in chassis for n, v in x['animations'].items()
                                       if v is None and n != 'HitReactions_React_DecoyTrap'])])

    # ---- UI ----
    m['ui'] = OD([('hud_ability_icon', texture('UI_GFxHud_p.TnAbilityDecoyTrap', 'UI_GFxHud_p/TnAbilityDecoyTrap.png')),
                  ('kill_feed_icon (death_Decoy is a HUD texture, not a death anim)', texture('UI_GFxHud_p.death_Decoy', 'UI_GFxHud_p/death_Decoy.png')),
                  ('character_select_icon', texture('UI_GFxCharacterSelect_p.DecoyTrap', 'UI_GFxCharacterSelect_p/DecoyTrap.png')),
                  ('victim_marker (TnObjectiveMarkerTypeDecoyTrap, creator client only)',
                   OD([('material', 'UI_HudMarkers_p.MarkerDeceptDestructible_MAT'),
                       ('material_refs', [OD([('prop', p), ('dst', d), ('class', k)]) for p, d, k in DB.execute(
                           'select prop, dst, dst_class from refs where src=?', ('UI_HudMarkers_p.MarkerDeceptDestructible_MAT',))]),
                       ('MarkerDescription', buff.get('MarkerDescription'))]))])

    # ---- audio ----
    m['audio'] = OD([('DECOY_TRAP_DEPLOY (ability OnTriggerSound)', A.cue(ability['OnTriggerSound'])),
                     ('DECOY_TRAP_EXPLODE (TnDecoyTrap PickupSound)', A.cue(trap['PickupSound'])),
                     ('loop', OD([('separate_loop_cue', None),
                                  ('in_explode_cue', 'WL_TRANS_POWER.TRANS_POWER_TRAP_ELEC_LP (4.59 s) is a LAYER of DECOY_TRAP_EXPLODE: one '
                                                     'wave event with a volume envelope 0 -> 1 by 0.15 s, held to 4.10 s, 0 at 4.57 s, pitch '
                                                     '-36 -> 0 over 0.28 s. With the _EXPLO hit, a random KAMIKAZE_EXPL_0x (pitch var 2) '
                                                     'and a random DEATH_LIGHT_0x at 3.50 s (-3 dB), the cue is a ~5 s one-shot spanning '
                                                     'the stun.'),
                                  ('root_LoopStart_LoopEnd', 'the cue root carries LoopStart 0.320 / LoopEnd 1.052; what the HM root does '
                                                             'with them is UNKNOWN (no RE note).')])),
                     ('note', 'BL_TRANS_POWER has only DECOY_TRAP_DEPLOY / DECOY_TRAP_EXPLODE for the decoy, and no decoy class carries an '
                              'ambient / loop sound property; the trap is silent while it lies on the ground. Each wave has its .wav '
                              'and .fsb in ExtractedAssets/content.')])

    # ---- FX ----
    pe = resolved('TransGame.Default__TnDroppedPickupDecoyTrap.PickupEffect0')['values'].get('Template')
    notify_fx = sorted({n['params'].get('ParticleSystemTemplate') for x in chassis for k, v in x['animations'].items() if v
                        for n in v['notifies'] if (n.get('params') or {}).get('ParticleSystemTemplate')})
    m['fx'] = OD([('DecoyTrap_FX (TnBuffDecoyTrap.ApplyFx; loops at the victim TargetingSocket)', fx(buff['ApplyFx'])),
                  ('pickup_effect (inherited PickupEffect0, bAutoActivate false)', fx(pe) if pe else None),
                  ('anim_notify_fx (on the stun clip)', [fx(t) for t in notify_fx]),
                  ('trap_own_idle_or_explode', None),
                  ('note', 'There is no trap-specific idle or explode particle system in the cook: the trap shows the weapon mesh + the '
                           'inherited dropped-pickup PickupEffect / HighlightFx, and the "explode" is only the pickup sound (RE §4).')])
    m['not_in_dump'] = [
        'a trap mesh of its own (by design: the thrower\'s weapon mesh)',
        'a dedicated deploy / hold anim (Skill_Barrier is reused; no hold)',
        'death_Decoy as an animation (it is the kill-feed icon texture)',
        'a trap loop sound', 'a trap idle / explode FX']
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(m, open(OUT_JSON, 'w', encoding='utf-8'), indent=1)
    print('wrote', OUT_JSON)
    print('chassis', len(chassis), 'decoy pool', sum(x['decoy_in_class_pool'] for x in chassis), 'missing anims', len(m['animations']['missing']))
    print('fx', json.dumps({k: v for k, v in m['fx'].items() if k != 'note'}, default=str)[:900])

if __name__ == '__main__':
    main()
