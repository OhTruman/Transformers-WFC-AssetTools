"""Vertical slice: one weapon (Ion Blaster) -> VerticalSlice/Weapons/IonBlaster/

weapon.glb   : skinned weapon mesh + resolved material + its own animation clips
weapon.json  : authored definition (TnWeaponIonBlaster defaults -> WEPMESH + WEPDATA):
               event->sound cue->wav, event->anim, FX particle systems, tracer, decal,
               magazine mesh, HUD icons, gameplay numbers, owner (robot) animations
"""
import json, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, props, extract, materials, animcompat, vs_character  # noqa: E402
from vs_common import *  # noqa: E402,F401

OUT = os.path.join(VS, 'Weapons', 'IonBlaster')
MESH = 'WEP_IonBlaster_p.WEP_IonBlaster_SKEL'
ANIMSET = 'WEP_IonBlaster_p.WEP_IonBlaster_ANIM'
DEF = ('A1_IAC_Base_m', ['TransContent.Default__TnWeaponIonBlaster', 'WEP_IonBlaster_p.IonBlaster_WEPMESH',
                         'WEP_IonBlaster_p.IonBlaster_WEPDATA', 'WEP_IonBlaster_p.IonBlaster_SP_WEPDATA',
                         'WEP_IonBlaster_p.IonBlaster_SV_WEPDATA'])

def flat(v):
    if isinstance(v, dict) and 'ref' in v: return v['ref']
    if isinstance(v, list):
        if v and isinstance(v[0], dict) and 'name' in v[0] and 'type' in v[0]:
            return {x['name']: flat(x['value']) for x in v}
        return [flat(x) for x in v]
    return v

def main():
    A = materials.assets()
    os.makedirs(OUT, exist_ok=True)
    p = ue3pkg.Package(os.path.join(extract.COOKED, DEF[0] + '.xxx')); pr = props.PropReader(p)
    idx = {p.object_path(i + 1): i + 1 for i in range(len(p.exports))}
    defs = {op: {k: flat(v) for k, v in props.props_dict(pr.read_object(idx[op])[0]).items()} for op in DEF[1]}
    wm = defs['WEP_IonBlaster_p.IonBlaster_WEPMESH']; wd = defs['WEP_IonBlaster_p.IonBlaster_WEPDATA']
    # int-typed arrays of floats (array element type unknown to the tag reader) -> reinterpret
    for d in defs.values():
        if isinstance(d.get('InstantHitDamage'), list):
            d['InstantHitDamage'] = [struct.unpack('>f', struct.pack('>i', x))[0] if isinstance(x, int) else x for x in d['InstantHitDamage']]
    # sub-objects of the weapon mesh template (components, FX parameter collection)
    wm_i = idx['WEP_IonBlaster_p.IonBlaster_WEPMESH']
    subs = {}
    for i, e in enumerate(p.exports):
        if e['outer'] == wm_i:
            try: subs[p.object_path(i + 1)] = {'class': p.class_name(e), **{k: flat(v) for k, v in props.props_dict(pr.read_object(i + 1)[0]).items()}}
            except Exception: pass
    # mesh + animations
    gl = next(o for o in A[MESH.lower()]['extracted'] if o.endswith('.gltf'))
    rest = animcompat.mesh_skeleton(gl)
    aset = A[ANIMSET.lower()]
    psa = next(o for o in aset['extracted'] if o.endswith('.psa'))
    comp = animcompat.evaluate(psa, rest)
    wanted = {s: ('fire' if 'Fire' in s else 'equip' if 'Equip' in s else 'putdown' if 'Drop' in s
                  else 'reload' if 'Reload' in s else 'idle' if 'Idle' in s else 'other') for s in comp['sequences']}
    vs_character.OUT = OUT
    glb_path, mats, clips, _ = vs_character.build_form('weapon', MESH, [(ANIMSET, psa[:-4] + '.anim.gltf', wanted)], A)
    cue = lambda op: vs_character.cue(op, A)
    events = []
    for ev in wm.get('WeaponEventSounds', []) or []:
        events.append({'event': ev.get('WeaponEventType'), 'cue': ev.get('WeaponSound'),
                       'resolved': cue(ev['WeaponSound']) if ev.get('WeaponSound') else None})
    ui = [a for a in A.values() if a['class'] == 'Texture2D' and re.search(r'IonBlaster', a['object_name'], re.I)
          and a['original_package'].startswith('UI_')]
    fx = [a for a in A.values() if a['original_package'] == 'FX_IonBlaster_p']
    def first(a, ext): return next((o for o in a['extracted'] if o.endswith(ext)), None)
    man = {
        'weapon': 'Ion Blaster', 'item_name': defs['TransContent.Default__TnWeaponIonBlaster'].get('ItemName'),
        'class': 'TransContent.TnWeaponIonBlaster',
        'mesh': {'object': MESH, 'glb': rel(glb_path, ROOT), 'source_gltf': gl, 'joints': len(rest),
                 'materials': mats, 'animations': clips,
                 'animset_compatibility': {k: v for k, v in comp.items() if k != 'sequences'}},
        'magazine_mesh': {'object': 'FX_IonBlaster_p.IonBlaster_Mag_STAT',
                          'gltf': first(A['fx_ionblaster_p.ionblaster_mag_stat'], '.gltf'),
                          'material': 'FX_IonBlaster_p.IonBlaster_Mag_MATINST'},
        'sounds': {'events': events,
                   'all_cues_in_bank': [cue(a['object_path']) for a in A.values()
                                        if a['original_package'] == 'BL_WPN_GUN_ION_BLASTER' and a['class'] == 'SoundCue'],
                   'firing': cue('BL_WPN_GUN_ION_BLASTER.SHOOT'), 'firing_tail': cue('BL_WPN_GUN_ION_BLASTER.SHOOT_TAIL'),
                   'reload': [cue('BL_WPN_GUN_ION_BLASTER.ANIM_RELOAD_01'), cue('BL_WPN_GUN_ION_BLASTER.ANIM_RELOAD_02')]},
        'event_animations': wm.get('WeaponEventAnims'),
        'effects': {'particle_systems': [{'object': a['object_path'], 'references': a.get('references', {}),
                                          'note': 'ParticleSystem not converted; use as effect reference'}
                                         for a in fx if a['class'] == 'ParticleSystem'],
                    'tracer_material': 'FX_Materials_p.Materials.IonBlasterTrail_MAT',
                    'tracer_templates': wm.get('TracerTemplates'), 'muzzle_flash_templates': wm.get('MuzzleFlashTemplate') or wm.get('MuzzleFlashTemplates'),
                    'impact_decal': wm.get('DefaultDecal'),
                    'projectile': 'none - instant hit (bInstantHit=true); damage type TransGame.TnDamageTypeIonBlaster'},
        'hud_icons': [{'object': a['object_path'], 'png': first(a, '.png')} for a in ui],
        'owner_animations': {'reload_robot': 'Shooting_Reload_IonBlaster_ROBO (TR_HeavyMedium_ANM_p.Shared_ROBO_ANIM; embedded in Optimus robot.glb)',
                             'aim': 'Shooting_Aim_* 9-way grid', 'recoil': {'spine': wm.get('SpineRecoil'), 'right_hand': wm.get('RightHandRecoil')}},
        'gameplay': {k: wd.get(k) for k in ('MaxAmmoCount', 'MaxAmmoClipCount', 'InitialReserveAmmoCount', 'DefaultPickupAmount',
                                            'FireIntervalModifier', 'PerShotSpreadModifier', 'FineAimSpreadModifier',
                                            'InstantHitDamage', 'InstantHitDamageTypes', 'WeaponRange', 'RangeDamageModifiers',
                                            'EquipTime', 'PutDownTime', 'WeaponReloadAnimTime', 'HeatProperties')},
        'heat': {'HeatPerShot': wm.get('HeatPerShot'), 'HeatCooldownTime': wm.get('HeatCooldownTime')},
        'authored_definitions': defs, 'weapon_mesh_subobjects': subs,
    }
    json.dump(man, open(os.path.join(OUT, 'weapon.json'), 'w'), indent=1, default=list)
    print('weapon.glb', glb_path, 'clips', [(c['name'], c['category']) for c in clips], 'compat', {k: v for k, v in comp.items() if k != 'sequences'})
    print('events', [(e['event'], len((e['resolved'] or {}).get('waves', []))) for e in events], 'icons', len(ui), 'fx', len(man['effects']['particle_systems']))
    print('damage', wd.get('InstantHitDamage'), 'interval', wd.get('FireIntervalModifier'))

if __name__ == '__main__':
    main()
