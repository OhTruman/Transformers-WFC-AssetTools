"""Product-ready export of every multiplayer weapon -> ExtractedAssets/VerticalSlice/Weapons/<ProviderId>/

  python vs_weapon_export.py --all            (or provider ids: IonBlaster Bazooka ...)

Contract (same as the Ion Blaster slice weapon): weapon.glb (umodel weapon mesh + resolved materials + the weapon's own
AnimSet clips) and weapon.json. Folder = TnDataProvider_Weapon provider id (stable weapon id shared by Gameplay / Frontend,
TransWeapons.ini); one record per weapon class in manifests/mp_content/mp_weapons.json.
weapon.json joins: mp_weapons.json (definition, ammo, damage, restrictions, effects, sounds, kill-feed icon, UI ratings),
the WEPMESH (AnimatedMesh AnimSets, sockets, recoil, heat, decals, impact / bullet-by sounds, muzzle light), sound cues ->
extracted WAVs, projectile class defaults -> projectile mesh / templates, HUD weapon icon (hud_package icon_sets),
chassis that may use it (roster_package), owner (robot) socket. Every path is checked.
"""
import json, os, re, sys, time
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vs_character as VC  # noqa: E402
import materials  # noqa: E402
import authored as AU  # noqa: E402
from vs_common import VS, ROOT  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MANI = os.path.join(AT, 'manifests')
GEN = 'AssetTools/scripts/wfc/vs_weapon_export.py'

def J(p): return json.load(open(os.path.join(MANI, p), encoding='utf-8'))
def rel(p): return os.path.relpath(p, ROOT).replace(os.sep, '/')

def anim_gltf(set_op):
    pkg, name = set_op.split('.', 1)
    p = os.path.join('content', pkg, name.replace('.', '/') + '.anim.gltf').replace(os.sep, '/')
    return p if os.path.exists(os.path.join(ROOT, p)) else None

def projectile(cls, A):
    if not cls: return None
    pkg, name = cls.split('.', 1)
    d = AU.values('%s.Default__%s' % (pkg, name)) or {}
    rec = OrderedDict([('class', cls), ('LifeSpan', d.get('LifeSpan')), ('Speed', d.get('Speed')), ('MaxSpeed', d.get('MaxSpeed')),
                       ('Damage', d.get('Damage')), ('DamageRadius', d.get('DamageRadius')), ('MomentumTransfer', d.get('MomentumTransfer'))])
    pm = d.get('Mesh')
    if pm:
        v = AU.values(pm) or {}
        keep = {k: x for k, x in v.items() if isinstance(x, (str, int, float, bool)) and
                re.search(r'Mesh|Template|Sound|Light|Explosion|Flight|Trail|Decal|Speed|Damage|Radius|Accel|Homing|Gravity', k)}
        rec['projectile_mesh'] = {'object': pm, 'properties': keep}
        for k, x in keep.items():
            if isinstance(x, str) and x.count('.') >= 1 and 'StaticMesh' in k or k in ('Mesh', 'StaticMesh'):
                a = A.get(str(x).lower()) or {}
                gl = next((o for o in a.get('extracted') or [] if o.endswith('.gltf')), None)
                if gl: rec['projectile_mesh']['gltf'] = gl
    rec['other_defaults'] = {k: x for k, x in d.items() if isinstance(x, (int, float)) and k not in rec}
    return rec

def export(pid, w, A, hud_icons, chassis_by_weapon, owner_socket):
    t0 = time.time()
    out_dir = os.path.join(VS, 'Weapons', pid)
    os.makedirs(out_dir, exist_ok=True)
    VC.NAME, VC.OUT = pid, out_dir
    # never overwrite the hand-built slice weapon (vs_weapon.py, loaded by Gameplay): write *_mp files next to it
    prev = os.path.join(out_dir, 'weapon.json')
    slice_owned = os.path.exists(prev) and json.load(open(prev, encoding='utf-8')).get('generated_by') != GEN
    stem = 'weapon_mp' if slice_owned else 'weapon'
    m = w.get('mesh') or {}
    wm = m.get('weapon_mesh_template')
    wmv = AU.values(wm) if wm else {}
    am = AU.values(wmv['AnimatedMesh']) if wmv.get('AnimatedMesh') else {}
    smc = AU.values(am['Mesh']) if am.get('Mesh') else {}           # AnimatedMesh.Mesh = the weapon SkeletalMeshComponent
    sets = [s for s in (am.get('AnimSets') or smc.get('AnimSets') or []) if isinstance(s, str)]
    glb = None; mats = []; clips = []; src = None
    if m.get('skeletal_mesh') and A.get(m['skeletal_mesh'].lower()):
        sel = []
        for s in sets:
            g = anim_gltf(s)
            if not g: continue
            names = [a['name'] for a in json.load(open(os.path.join(ROOT, g), encoding='utf-8')).get('animations', [])]
            sel.append((s, g, {n: 'weapon' for n in names}))
        glb, mats, clips, src = VC.build_form(stem, m['skeletal_mesh'], sel, A)
    sounds = []
    for e in (w.get('sounds') or {}).get('events') or []:
        if e.get('WeaponSound'): sounds.append(dict(event=e.get('WeaponEventType'), **VC.cue(e['WeaponSound'], A)))
    for k in ('PickupSound', 'DefaultImpactSound', 'BulletBySound'):
        if wmv.get(k): sounds.append(dict(event=k, **VC.cue(wmv[k], A)))
    wd = w.get('gameplay (player WEPDATA)') or {}
    projs = [projectile(c, A) for c in dict.fromkeys(x for x in (wd.get('WeaponProjectiles') or []) if x)]
    cls_short = w['class'].rsplit('.', 1)[-1]
    man = OrderedDict([
        ('generated_by', GEN), ('weapon_id', pid), ('stable_id_source', 'TnDataProvider_Weapon UniqueId (TransWeapons.ini)'),
        ('class', w['class']), ('provider_ids', w.get('provider_ids')), ('display_name', w.get('display_name')),
        ('description', w.get('description')), ('weapon_type_code', w.get('weapon_type_code')),
        ('mesh', OrderedDict([('object', m.get('skeletal_mesh')), ('weapon_mesh_template', wm), ('glb', rel(glb) if glb else None),
                              ('source_gltf', src), ('mesh_note', m.get('mesh_note')),
                              ('materials', [{'slot': x['slot'], 'material': x['material'],
                                              'textures': {k: (v or {}).get('file') for k, v in ((x['resolved'] or {}).get('textures') or {}).items()},
                                              'roles': (x['resolved'] or {}).get('roles'), 'blend_mode': (x['resolved'] or {}).get('blend_mode')} for x in mats]),
                              ('buff_materials', m.get('buff_materials')),
                              ('sockets', VC.sockets(m['skeletal_mesh'], A) if glb else []),
                              ('muzzle_sockets', m.get('muzzle_sockets')), ('reference_bone', wmv.get('_ReferenceBoneName')),
                              ('pickup_mesh', m.get('pickup_mesh')), ('pickup_mesh_translation_ue', m.get('pickup_mesh_translation'))])),
        ('animations', OrderedDict([('anim_sets', sets), ('clips_in_glb', clips), ('idle', m.get('idle_animation')),
                                    ('event_anims (weapon mesh)', m.get('event_anims')),
                                    ('owner_animations (robot body)', w.get('owner_animations') or (wd.get('OwnerAnimations') if isinstance(wd.get('OwnerAnimations'), (list, dict)) else None))])),
        ('attachment', {'owner_socket (robot)': owner_socket, 'reference_bone': wmv.get('_ReferenceBoneName'),
                        'rule': 'weapon reference bone placed at the robot WeaponSocket_Primary (per-chassis socket in '
                                'Characters/<ChassisId>/character.json robot.sockets); vehicle-form weapons fire from the vehicle sockets'}),
        ('recoil (procedural, WEPMESH)', {k: wmv.get(k) for k in ('SpineRecoil', 'RightHandRecoil') if wmv.get(k)}),
        ('heat', {k: wmv.get(k) for k in ('HeatPerShot', 'HeatCooldownTime', 'LowAmmoThreshold') if wmv.get(k) is not None}),
        ('effects', OrderedDict([('authored', w.get('effects')), ('default_decal', wmv.get('DefaultDecal')),
                                 ('muzzle_light', wmv.get('MuzzleFlashLight')), ('muzzle_flash_duration', wmv.get('MuzzleFlashDuration')),
                                 ('impact_squib', {k: wmv.get(k) for k in ('ImpactSquibPercentage', 'ImpactSquibMaxCount', 'MaxImpactEffectDistance')})])),
        ('projectiles', projs or None),
        ('sounds', sounds),
        ('gameplay (player WEPDATA)', wd), ('ai_data', w.get('ai_data')), ('damage_types', w.get('damage_types')),
        ('restrictions', w.get('restrictions')), ('usable_by_chassis', chassis_by_weapon.get(pid)),
        ('ui', OrderedDict([('ratings', w.get('ui_ratings')), ('kill_feed_icon', w.get('kill_feed_icon')),
                            ('hud_weapon_icon', hud_icons.get(cls_short)),
                            ('loadout_icons (GFx export name == provider id, HIGH)',
                             {mv: 'content/%s/%s.png' % (mv, pid) for mv in ('UI_GFxCharacterSelect_p', 'UI_GFxCustomize_p')
                              if os.path.exists(os.path.join(ROOT, 'content', mv, pid + '.png'))} or None),
                            ('menu_preview', 'weapon glTF (no dedicated preview mesh authored for MP loadouts: INFERRED from absence)')])),
        ('mp', w.get('mp')), ('mp_weapons_entry', 'manifests/mp_content/mp_weapons.json weapons["%s"]' % w['class'])])
    paths = []
    def collect(x):
        if isinstance(x, dict): [collect(v) for v in x.values()]
        elif isinstance(x, list): [collect(v) for v in x]
        elif isinstance(x, str) and re.match(r'^(content|VerticalSlice)/.*\.(glb|gltf|png|tga|wav)$', x): paths.append(x)
    collect(man)
    missing = sorted({p for p in paths if not os.path.exists(os.path.join(ROOT, p))})
    man['validation'] = {'paths_checked': len(set(paths)), 'missing': missing, 'glb': bool(glb), 'clips': len(clips),
                         'sounds_with_wav': sum(1 for s in sounds if any(x.get('wav') for x in s.get('waves') or [])),
                         'sounds': len(sounds), 'seconds': round(time.time() - t0, 1)}
    man['files'] = {'json': 'VerticalSlice/Weapons/%s/%s.json' % (pid, stem), 'slice_weapon_kept': slice_owned}
    json.dump(man, open(os.path.join(out_dir, stem + '.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    return man

def main():
    weapons = J('mp_content/mp_weapons.json')['weapons']
    by_pid = OrderedDict()
    for cls, w in weapons.items():
        for pid in (w.get('provider_ids') or [cls.rsplit('.', 1)[-1].replace('TnWeapon', '')])[:1]:
            by_pid[pid] = w
    ids = list(by_pid) if '--all' in sys.argv else [a for a in sys.argv[1:] if not a.startswith('--')]
    roster = J('mp_content/roster_package.json')['chassis']
    chassis_by_weapon = {}
    for cid, ch in roster.items():
        wpn = ch.get('weapons') or {}
        on = next((v for k, v in wpn.items() if k.startswith('allowed_on_foot')), []) or []
        veh = (next((v for k, v in wpn.items() if k.startswith('vehicle_form')), {}) or {}).get('from_iconic_preset') or []
        for p in on: chassis_by_weapon.setdefault(p, {'on_foot': [], 'vehicle_preset': []})['on_foot'].append(cid)
        for p in veh: chassis_by_weapon.setdefault(p, {'on_foot': [], 'vehicle_preset': []})['vehicle_preset'].append(cid)
    hud = json.load(open(os.path.join(MANI, 'hud', 'hud_package.json'), encoding='utf-8'))
    hud_icons = {}
    for setname, s in (hud.get('icon_sets') or {}).items():
        if 'weapon' not in setname.lower(): continue
        for k, v in (s.items() if isinstance(s, dict) else []):
            hud_icons[k] = v
    owner_socket = 'WeaponSocket_Primary'
    A = materials.assets()
    index = OrderedDict()
    for pid in ids:
        try:
            m = export(pid, by_pid[pid], A, hud_icons, chassis_by_weapon, owner_socket)
            index[pid] = {'dir': 'VerticalSlice/Weapons/%s' % pid, 'json': m['files']['json'], 'class': m['class'], 'glb': m['mesh']['glb'],
                          'mesh_note': m['mesh']['mesh_note'], 'validation': m['validation']}
            v = m['validation']
            print(pid, 'glb', v['glb'], 'clips', v['clips'], 'sounds %d/%d' % (v['sounds_with_wav'], v['sounds']), 'missing', len(v['missing']),
                  'icon', bool(m['ui']['hud_weapon_icon']), flush=True)
        except Exception as e:
            import traceback; traceback.print_exc()
            index[pid] = {'error': repr(e)[:300]}; print(pid, 'ERROR', repr(e)[:200], flush=True)
    if '--all' in sys.argv:
        json.dump(OrderedDict([('generated_by', GEN), ('root', 'ExtractedAssets (local, not pushed); paths relative to it'),
                               ('contract', 'Weapons/<ProviderId>/{weapon.glb, weapon.json}'), ('weapons', index)]),
                  open(os.path.join(MANI, 'mp_content', 'weapon_export_index.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    main()
