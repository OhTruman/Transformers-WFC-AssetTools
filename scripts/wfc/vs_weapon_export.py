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

def resolve_subobjects(x, owners, depth=0):
    """replace references to sub-objects of the given owner objects by {object, class, values} (one level)."""
    if isinstance(x, dict): return {k: resolve_subobjects(v, owners, depth) for k, v in x.items()}
    if isinstance(x, list): return [resolve_subobjects(v, owners, depth) for v in x]
    if isinstance(x, str) and depth < 2 and any(x.startswith(o + '.') for o in owners if o) and AU.get(x):
        return {'object': x, 'class': AU.get(x)['class'], 'values': resolve_subobjects(AU.values(x) or {}, owners, depth + 1)}
    return x

_fx = {}
def fx_status(t):
    """decode status of a particle template: emitters, TypeData class per emitter (Sprite / Mesh / Beam2 / Trail2 ...), undecoded modules."""
    if not t: return None
    if t in _fx: return _fx[t]
    import pstream
    if not AU.get(t): _fx[t] = {'template': t, 'in_dump': False}; return _fx[t]
    try:
        r = pstream.system(t); em = []
        for e in r.get('emitters') or []:
            L = (e.get('lods') or [{}])[0]
            td = (L.get('TypeDataModule') or {})
            em.append({'emitter': e.get('name'), 'type_data': td.get('class') or 'Sprite (no TypeData)',
                       'type_data_props': td.get('props'), 'material': ((L.get('RequiredModule') or {}).get('props') or {}).get('Material'),
                       'undecoded_modules (PMI_Unknown)': sum(1 for m in L.get('compiled_modules') or [] if m.get('module') == 'PMI_Unknown'),
                       'resolved_modules (PMI_Unknown slots named by object class)': [
                           {'slot': m['index'], 'module': m['module'], 'object': m.get('module_object'),
                            'properties': m.get('module_properties (authored, defaults filled)')}
                           for m in L.get('compiled_modules') or [] if m.get('module_enum')] or None,
                       'assignment_complete': L.get('assignment_complete')})
        bm = [{'object': o_, 'class': c_, 'values': AU.values(o_)} for (o_, c_) in AU.con().execute(
            "SELECT opath, class FROM objects WHERE opath LIKE ? AND class LIKE 'ParticleModuleBeam%'", (t + '.%',)).fetchall()]
        _fx[t] = {'template': t, 'in_dump': True, 'emitters': em,
                  'beam_modules (template sub-objects)': bm or None,
                  'beam_modules_note': ('PMI_Unknown / module_id 0 entries in beam LODs are these modules: ParticleModuleBeamSource, '
                                        'ParticleModuleBeamTarget (TargetMethod PEB2STM_UserSet, TargetName "TargetLocation"), and the WFC-specific '
                                        'ParticleModuleBeamSineWave. Emitter / LOD binding comes from the native LOD module list (RE '
                                        'TARGETED_PASS5 raw scan, HIGH)') if bm else None}
    except Exception as ex:
        _fx[t] = {'template': t, 'in_dump': True, 'decode_error': repr(ex)[:150]}
    return _fx[t]

_fov = None
def fine_aim_camera(weapon_pcs):
    """FOV for this weapon's camera state from CAM_Strategies_p.OverTheShoulder_STRATEGY TnFovCameraBehavior (robot form, every MP
    CAMSET; first FOVsByPCS entry whose PlayerCameraStates are all active wins - RE TARGETED_PASS5 section 3, CONFIRMED data)."""
    global _fov
    if _fov is None:
        r = AU.con().execute("SELECT opath FROM objects WHERE opath LIKE 'CAM_Strategies_p.OverTheShoulder_STRATEGY.%' "
                             "AND class='TnFovCameraBehavior'").fetchone()
        _fov = AU.values(r[0]) if r else {}
        _fov['_object'] = r[0] if r else None
    rows = _fov.get('FOVsByPCS') or []
    def pick(states):
        return next(((e.get('Settings') or {}) for e in rows if set(e.get('PlayerCameraStates') or []) <= set(states)), _fov.get('DefaultFOV'))
    return OrderedDict([('weapon_pcs', weapon_pcs), ('source', _fov.get('_object')),
                        ('fov_default', _fov.get('DefaultFOV')),
                        ('fov_fine_aim', pick([x for x in (weapon_pcs, 'TransGame.TnPCS_FineAim') if x])),
                        ('fov_fine_aim_hovering', pick([x for x in (weapon_pcs, 'TransGame.TnPCS_FineAim', 'TransGame.TnPCS_Hovering') if x])),
                        ('rule', 'first FOVsByPCS entry whose PlayerCameraStates are all active; weapon adds WeaponPCS, fine aim adds TnPCS_FineAim')])

def projectile(cls, A):
    if not cls: return None
    pkg, name = cls.split('.', 1)
    d = AU.values('%s.Default__%s' % (pkg, name)) or {}
    rec = OrderedDict([('class', cls), ('LifeSpan', d.get('LifeSpan')), ('Speed', d.get('Speed')), ('MaxSpeed', d.get('MaxSpeed')),
                       ('Damage', d.get('Damage')), ('DamageRadius', d.get('DamageRadius')), ('MomentumTransfer', d.get('MomentumTransfer'))])
    pm = d.get('Mesh')
    # the visible body: the projectile class default's mesh component (MeshComp -> StaticMesh), if any (RE projectile_effect_bindings)
    mc = d.get('MeshComp'); mcv = AU.values(mc) if mc and AU.get(mc) else {}
    body = mcv.get('StaticMesh') or mcv.get('SkeletalMesh')
    if body:
        a_ = A.get(body.lower()) or {}
        rec['body_mesh'] = {'component': mc, 'mesh': body, 'gltf': next((o for o in a_.get('extracted') or [] if o.endswith('.gltf')), None),
                            'scale': mcv.get('Scale'), 'scale3d': mcv.get('Scale3D'), 'translation': mcv.get('Translation'),
                            'rotation': mcv.get('Rotation'), 'materials': mcv.get('Materials')}
    if pm and not body and (AU.values(pm) or {}).get('StaticMesh'):   # grenades: StaticMesh + DrawScale authored on the PROJMESH itself
        pv_ = AU.values(pm); body = pv_['StaticMesh']; a_ = A.get(body.lower()) or {}
        rec['body_mesh'] = {'source': pm + '.StaticMesh', 'mesh': body, 'draw_scale': pv_.get('DrawScale'),
                            'gltf': next((o for o in a_.get('extracted') or [] if o.endswith('.gltf')), None)}
    if pm:
        v = AU.values(pm) or {}
        rec['projectile_visual'] = OrderedDict([
            ('kind', ('mesh body %s (class-default mesh component) + flight particle' % body) if body else
                     'particle-only: no mesh on the projectile class default mesh component; the FlightEffect is the visible body (CONFIRMED)'),
            ('flight_effect', fx_status(v.get('FlightEffect'))), ('explosion_effect', fx_status(v.get('ExplosionEffect'))),
            ('flight_sound', v.get('FlightSound')), ('explosion_sound', v.get('ExplosionSound')), ('bounce_sound', v.get('BounceSound')),
            ('decal_applicator', resolve_subobjects(v.get('DecalApplicator'), [pm])),
            ('particle_parameters (team colour / index)', resolve_subobjects(v.get('Parameters'), [pm]))])
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
    wd = w.get('gameplay (versus WEPDATA = MultiplayerData, CONFIRMED)') or {}   # versus data (RE 2026-10-05)
    wdo = (w.get('wepdata_objects') or {}).get('MultiplayerData (versus)')
    wd = resolve_subobjects(wd, [wdo])
    pk_, cn_ = w['class'].split('.', 1)
    cdo = '%s.Default__%s' % (pk_, cn_)
    class_defaults = resolve_subobjects({k: v for k, v in (AU.values(cdo) or {}).items()
                                         if not k.startswith(('b', 'Net', 'Role', 'Remote', 'Tick')) and k not in ('Components', 'SupportedEvents')}, [cdo])
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
        ('effects', OrderedDict([('authored', w.get('effects')),
                                 ('decode_status', {t: fx_status(t) for t in sorted({x for x in
                                     [m.get('PSTemplate') for m in (w.get('effects') or {}).get('muzzle_flashes') or []] +
                                     [m.get('TracerTemplate') for m in (w.get('effects') or {}).get('tracers') or []] +
                                     [(w.get('effects') or {}).get('default_squib')] if x})}),
                                 ('default_decal', wmv.get('DefaultDecal')),
                                 ('muzzle_light', wmv.get('MuzzleFlashLight')), ('muzzle_flash_duration', wmv.get('MuzzleFlashDuration')),
                                 ('impact_squib', {k: wmv.get(k) for k in ('ImpactSquibPercentage', 'ImpactSquibMaxCount', 'MaxImpactEffectDistance')})])),
        ('projectiles', projs or None),
        ('sounds', sounds),
        ('gameplay (versus WEPDATA = MultiplayerData, CONFIRMED)', wd),
        ('versus_data_source', OrderedDict([
            ('object', wdo),
            ('selected_by', 'MultiplayerData' if (AU.values(cdo) or {}).get('MultiplayerData') else
                            'PlayerData (fallback: MultiplayerData unset on the class chain)'),
            ('rule', 'TnWeapon.GivenTo: TnMultiplayerGame.DesiredWeaponDataType = 3 (Multiplayer); GetWeaponDataByType(3) == none -> '
                     'WDT 1 PlayerData; no fallback to DefaultTnWeaponData; AI holders use AiData (RE 2026-10-07, CONFIRMED from script)')])),
        ('wepdata_objects', w.get('wepdata_objects')),
        ('class_defaults (weapon CDO, sub-objects resolved)', class_defaults),
        ('fine_aim_camera (OverTheShoulder strategy FOV)', fine_aim_camera((AU.values(cdo) or {}).get('WeaponPCS'))),
        ('hud_scope (Hud_GFX ActionScript on NotifyFineAimChanged(1), by weapon class; RE TARGETED_PASS5 CONFIRMED)',
         {'TnWeaponSniperRifle': 'mc_longScope', 'TnWeaponBurstRifle': 'mc_mediumScope', 'TnWeaponHeavyPistol': 'mc_shortScope'}.get(cn_)),
        ('gameplay (campaign / SP PlayerData)', w.get('gameplay (player WEPDATA)')), ('ai_data', w.get('ai_data')), ('damage_types', w.get('damage_types')),
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
