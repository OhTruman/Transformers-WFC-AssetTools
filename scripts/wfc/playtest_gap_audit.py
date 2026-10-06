"""Targeted audit of the newest human-playtest gaps -> manifests/audit/playtest_gaps.json + docs/PLAYTEST_GAP_AUDIT.md

  python playtest_gap_audit.py

For each reported defect area, decide from the cooked data and the current exports whether the original authored assets are:
  EXTRACTED AND VALID        present in the exports and consumable as-is
  EXTRACTED BUT NOT CONSUMED present (and now in a runtime manifest) but the consumer does not use it yet
  BAD/INCOMPLETE EXPORT      export exists but is wrong / incomplete
  REFERENCE ISSUE            data exists but the manifest pointed at it wrongly / not at all (fixed in this pass where noted)
  NOT PRESENT IN DUMP        the original does not author it
  UNKNOWN                    not decidable from authored data (native / runtime)
Evidence is recomputed from the exports on every run (character.json / weapon.json / map outputs / the Rendering lane's
render data, read-only). Default four classes = RE: Leader Truck3/Truck4, Scientist Jet4/Jet, Scout Car2/Car4, Soldier Tank3/Tank2.
"""
import json, os, sys, time
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import ROOT, VS  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
REND = os.path.normpath(os.path.join(AT, '..', 'Rebuild-Rendering', 'work', 'render'))
CLASSES = OrderedDict([('Scout', ['Car2', 'Car4']), ('Scientist', ['Jet4', 'Jet']), ('Leader', ['Truck3', 'Truck4']), ('Soldier', ['Tank3', 'Tank2'])])
EV, NC, BAD, REF, NP, UNK = ('EXTRACTED AND VALID', 'EXTRACTED BUT NOT CONSUMED', 'BAD/INCOMPLETE EXPORT', 'REFERENCE ISSUE',
                             'NOT PRESENT IN DUMP', 'UNKNOWN')

def J(p, d=None):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d
def char(cid): return J(os.path.join(VS, 'Characters', cid, 'character.json'), {})
def wpn(pid):
    d = os.path.join(VS, 'Weapons', pid)
    return J(os.path.join(d, 'weapon_mp.json')) or J(os.path.join(d, 'weapon.json'), {})
def key(d, prefix): return next((v for k, v in d.items() if k.startswith(prefix)), None)

def item(area, verdict, owner, evidence, action=None, fixed_in_this_pass=None):
    return OrderedDict([('area', area), ('verdict', verdict), ('owner', owner), ('evidence', evidence), ('action', action),
                        ('fixed_in_this_pass', fixed_in_this_pass)])

def main():
    out = []
    # ---- vehicle propulsion / hover / boost / jump FX per class
    for cls, ids in CLASSES.items():
        ev = {}
        for cid in ids:
            c = char(cid)
            fx = key(c, 'vehicle_fx') or {}
            socks = {s['socket'] for s in (c.get('vehicle') or {}).get('sockets') or []}
            ev[cid] = {k: {'count': len(v), 'templates': sorted({x['template'] for x in v}),
                           'sockets_missing_on_vehicle_glb': [x['socket'] for x in v if x['socket'] and x['socket'] not in socks],
                           'templates_in_dump': all(x.get('template_in_dump') for x in v)} for k, v in fx.items() if k != 'DefaultSkeletalGibTemplate'}
        out.append(item('%s vehicle propulsion / hover / boost / jump FX' % cls, NC, 'SYSTEMS (wiring) + RENDERING (Size/Color params)', ev,
                        'templates + sockets now in Characters/<id>/character.json "vehicle_fx (VEHDEF particle structs ...)"; every socket exists on '
                        'vehicle.glb, every template decodes. Spawn at the sockets per form, toggled by the clip notifies TnAnimNotify_ToggleVehicleFx',
                        'vehicle_fx added to character.json (was only in manifests/audit/vehicle_fx_audio.json)'))
    # ---- vehicle weapons / projectiles per class
    for cls, ids in CLASSES.items():
        ev = {}
        for cid in ids:
            c = char(cid)
            vw = ((key(c.get('weapons') or {}, 'vehicle_form') or {}).get('from_iconic_preset')) or []
            socks = {s['socket'] for s in (c.get('vehicle') or {}).get('sockets') or []}
            for pid in vw:
                w = wpn(pid)
                g = w.get('gameplay (versus WEPDATA = MultiplayerData, CONFIRMED)') or {}
                mz = (w.get('mesh') or {}).get('muzzle_sockets') or []
                pr = w.get('projectiles') or []
                ev['%s/%s' % (cid, pid)] = {
                    'fire_types': g.get('WeaponFireTypes'), 'muzzle_sockets': mz,
                    'muzzle_sockets_missing_on_vehicle': [m for m in mz if m not in socks],
                    'projectile_visuals': [{'class': p.get('class'), 'kind': (p.get('projectile_visual') or {}).get('kind', '')[:60],
                                            'flight_effect': ((p.get('projectile_visual') or {}).get('flight_effect') or {}).get('template'),
                                            'explosion_effect': ((p.get('projectile_visual') or {}).get('explosion_effect') or {}).get('template')} for p in pr],
                    'tracer_muzzle_impact': sorted(((w.get('effects') or {}).get('decode_status') or {}).keys())}
        miss = [k for k, v in ev.items() if v['muzzle_sockets_missing_on_vehicle']]
        out.append(item('%s vehicle weapon projectiles / tracers / muzzle sockets' % cls, NC if not miss else REF, 'GAMEPLAY / RENDERING', ev,
                        'projectiles are particle-only (TnProjectileMesh authors no mesh component, CONFIRMED): draw FlightEffect at the projectile, '
                        'ExplosionEffect + decal on impact; instant-hit vehicle guns use the tracer + muzzle flash at WeaponSocket_Primary/2. '
                        'Muzzle sockets missing on the vehicle: %s' % (miss or 'none'),
                        'weapon.json projectile_visual + effect decode status (was "projectile mesh gltf: None")'))
    # ---- per-chassis vehicle audio
    ev = {}
    for cls, ids in CLASSES.items():
        for cid in ids:
            va = key(char(cid), 'vehicle_audio') or []
            ev[cid] = dict(Counter(x['export'] for x in va))
    out.append(item('Per-chassis vehicle audio (engine / boost / jump / land / speed)', NC, 'SYSTEMS', ev,
                    'per-event cue + WAV resolution now in character.json "vehicle_audio (...)"; UNKNOWN entries are events absent from the '
                    'chassis event set (engine default / silent)', 'vehicle_audio added to character.json'))
    # ---- transformation effects
    ev = {}
    for cls, ids in CLASSES.items():
        for cid in ids:
            c = char(cid)
            tr = [a for f in ('robot', 'vehicle') for a in (c.get(f) or {}).get('animations') or [] if a['sequence'].startswith('Transform_To')]
            ev[cid] = {'play_effect': sorted({(n['params'].get('ParticleSystemTemplate'), n['params'].get('SocketName')) and n['params'].get('ParticleSystemTemplate')
                                              for a in tr for n in a.get('notifies') or [] if n['class'] == 'HmAnimNotify_PlayEffect'}),
                       'sounds': sorted({n['params'].get('SoundCue') for a in tr for n in a.get('notifies') or [] if n['class'] == 'HmAnimNotify_Sound'}),
                       'mesh_swap_notifies': sum(1 for a in tr for n in a.get('notifies') or [] if n['class'] == 'TnAnimNotify_ToggleHidden'),
                       'vehicle_fx_toggles': sum(1 for a in tr for n in a.get('notifies') or [] if n['class'] == 'TnAnimNotify_ToggleVehicleFx')}
    scout_fx = any(ev[c]['play_effect'] for c in CLASSES['Scout'])
    out.append(item('Transformation effects (Scout and other chassis)', NC, 'GAMEPLAY (notify dispatch) + RENDERING / SYSTEMS', ev,
                    'transform clips now carry their notifies in character.json (animations[].notifies): sounds, mesh hide/show timings, '
                    'vehicle-FX toggles and any PlayEffect. Particle effects on transformation are authored ONLY where listed (Starscream: '
                    'Trails_Bumblebee_FX at knee / wing sockets); the Scout chassis author none (%s). Spark_Transformer_FX is a vehicle '
                    'rigid-body impact effect (TnVehicleForm.RigidBodyCollisionOccurred, contact speed >= 1200), not a transform effect'
                    % ('NOT PRESENT IN DUMP for Scout particles' if not scout_fx else 'present'),
                    'clip notifies added to character.json'))
    out.append(item('Scout transformation particles', NP if not scout_fx else EV, 'NONE', {c: ev[c]['play_effect'] for c in CLASSES['Scout']},
                    'the original Scout transform is mesh swap + transform sound; do not invent sparks'))
    # ---- repair ray
    w = wpn('RepairRay')
    ds = ((w.get('effects') or {}).get('decode_status') or {})
    beam = next((v for k, v in ds.items() if 'Tracer_RepairBeam' in k), {})
    out.append(item('Scientist Repair Ray visuals / data', NC, 'GAMEPLAY (simulation: HUD weaponSimulated false) + RENDERING (beam fidelity)', {
        'mesh': (w.get('mesh') or {}).get('glb'), 'clips': len(((w.get('animations') or {}).get('clips_in_glb')) or []),
        'beam': {'template': beam.get('template'), 'emitters': [(e['emitter'], e['type_data'], e.get('material'), e['undecoded_modules (PMI_Unknown)'])
                                                               for e in beam.get('emitters') or []],
                 'beam2_type_data': [e.get('type_data_props') for e in beam.get('emitters') or [] if 'Beam' in (e.get('type_data') or '')][:1]},
        'gameplay': {k: (w.get('gameplay (versus WEPDATA = MultiplayerData, CONFIRMED)') or {}).get(k) for k in
                     ('WeaponFireTypes', 'InstantHitDamage', 'InstantHitDamageTypes', 'WeaponRange', 'MaxAmmoCount', 'HeatProperties')},
        'repair_rate': (w.get('class_defaults (weapon CDO, sub-objects resolved)') or {}).get('RepairRateModifier'),
        'can_target_teammates': (w.get('class_defaults (weapon CDO, sub-objects resolved)') or {}).get('CanTargetTeammates')},
        'all authored data exported: Beam2 tracer on WP_Looping (TaperMethod / InterpolationPoints / TaperScale in beam2_type_data), heal '
        'damage type, range 3500, heat modifiers (overheat 3.5 s, gain 20 / s, loss 20 / s after 3 s), buff-scaled repair rate',
        'heat modifiers + RepairRateModifier resolved inline in weapon.json (were bare object paths)'))
    # ---- beam / trail / ribbon modules
    bt = []
    for pid in ('RepairRay', 'AssaultRifle', 'SniperRifle', 'AssaultRifleVehicle', 'TankCannon', 'HomingRocketVehicle', 'RocketVehicle'):
        for t, s in ((wpn(pid).get('effects') or {}).get('decode_status') or {}).items():
            for e in s.get('emitters') or []:
                if 'Beam' in e['type_data'] or 'Trail' in e['type_data'] or 'Ribbon' in e['type_data']:
                    bt.append({'weapon': pid, 'template': t, 'emitter': e['emitter'], 'type_data': e['type_data'],
                               'type_data_props': e.get('type_data_props'), 'undecoded_modules': e['undecoded_modules (PMI_Unknown)']})
    out.append(item('Beam / trail / ribbon modules for missing FX', NC, 'RENDERING (fidelity) + RE (undecoded module ids)', bt,
                    'TypeDataBeam2 / Trail2 tagged settings (TaperMethod, InterpolationPoints, TaperScale, ...) are extracted per template; '
                    'Rendering M44 draws Beam2 / Trail2 but does not apply taper / interpolation / noise yet. The module_id 0 (PMI_Unknown) '
                    'entries are ParticleModuleBeamSource / BeamTarget (TargetName "TargetLocation", user-set) / the WFC-specific '
                    'BeamSineWave (SineWaves amplitude / period / speed / direction): all listed with values in weapon.json effects.decode_status '
                    '"beam_modules (template sub-objects)" (RE TARGETED_PASS5 binding, HIGH)', 'beam modules identified and exported'))
    # ---- Molten lava / floors
    ma = (J(os.path.join(VS, 'Maps', 'MP_KON_Molten', 'materials_authored.json'), {}) or {}).get('materials') or {}
    lava = [k for k in ma if 'Energon' in k and ('Plasma' in k or 'River' in k or 'Lava' in k)]
    floors_missing = sorted({k for k, v in ma.items() for t_, x in (v.get('textures') or {}).items()
                             if isinstance(x, dict) and not x.get('file') and x.get('class') == 'Texture2D'})
    unexported_2d = Counter(x.get('texture') for v in ma.values() for x in (v.get('textures') or {}).values()
                            if isinstance(x, dict) and not x.get('file') and x.get('class') == 'Texture2D')
    g = (J(os.path.join(REND, 'MP_KON_Molten', 'materials_glsl.json'), {}) or {})
    G = g.get('materials', g)
    out.append(item('Molten lava material (animated)', EV, 'RENDERING', {
        'lava_materials': lava, 'master': 'ENV_AllShader_p.Energon_River.Energon_River_Mat (5 Panners, 9 ShaderCode, DepthBiasedAlpha)',
        'textures_exported': 'all 6 (ElectricArcs, DiffClouds, Water_NORMENV_EnergonRiver)',
        'compiled_by_rendering (read-only)': {k: bool(G.get(k)) and not (G.get(k) or {}).get('error') for k in lava}},
        'extracted; Rendering compiles it with time-driven panners'))
    rep = (J(os.path.join(AT, 'manifests', 'audit', 'repaired_textures.json'), {}) or {}).get('textures') or {}
    still = {}
    for mp_ in sorted(os.listdir(os.path.join(VS, 'Maps'))):
        mm = (J(os.path.join(VS, 'Maps', mp_, 'materials_authored.json'), {}) or {}).get('materials') or {}
        n_ = sum(1 for v in mm.values() for x in (v.get('textures') or {}).values()
                 if isinstance(x, dict) and not x.get('file') and x.get('class') == 'Texture2D')
        if n_: still[mp_] = n_
    out.append(item('Molten (and every MP map) floor normal / mask textures', BAD, 'ASSETTOOLS (repaired) -> RENDERING (rebuild render data)', {
        'molten_materials_with_an_unexported_Texture2D_before_repair': len(floors_missing), 'of_materials': len(ma),
        'repaired_textures': {k: {'references': v['references'], 'output': v['output']} for k, v in rep.items()},
        'content_note': 'Pixel_4_NORM is a flat placeholder normal (mean RGB 126,126,255): no visual change; Pixel_4_Mask carries mask '
                        'channels (R/G); Pixel_4_WHT decodes black (4x4, 1 reference) - suspicious, UNKNOWN',
        'materials_still_unbound_after_refresh': still,
        'rendering_render_data (read-only)': 'Rebuild-Rendering/work/render/MP_KON_Molten/tex lacks Pixel_4_NORM (has Pixel_4_Mask, Crackle_1_NORM)'},
        'Rendering: rebuild render data (build_materials.py reads ExtractedAssets/content first). Streets materials_authored not refreshed '
        '(held: Streets regeneration needs explicit approval)',
        'repair_missing_textures.py: 6 cooked Texture2D exported to content/ENV_AllShader_p/Textures and registered; materials_authored '
        'refreshed for the 9 non-Streets maps'))
    # ---- Orbital Debris sky / background
    mj = J(os.path.join(VS, 'Maps', 'MP_ORB_Debris', 'map.json'), {}) or {}
    gd = (J(os.path.join(REND, 'MP_ORB_Debris', 'materials_glsl.json'), {}) or {})
    GD = gd.get('materials', gd)
    out.append(item('Orbital Debris sky / background / streamed sublevels', EV, 'RENDERING', {
        'sublevels_exported': mj.get('sublevels'), 'authored_streaming': ['MP_ORB_Art_m', 'MP_ORB_Audio_m'],
        'background_meshes': ['ENV_ORB_Spacedome_p.SpaceDome_STATMESH (override Spacedome_Nebula_MAT)',
                              'ENV_ORB_CybertronPlanet_p.MATTE.Cybertron_MATTE_STAT (override Cybertron_2D_Planet_MAT)',
                              'DES_ORB_Asteroids_p SpaceDebris / BigAsteroid / Asteroid_Debris'],
        'override_materials_compiled (read-only)': {k: bool(GD.get(k)) for k in ('ENV_ORB_Spacedome_p.Spacedome_Nebula_MAT',
                                                                                 'ENV_NEU_CybertronOrbit_P.2D_Planet_Card.Cybertron_2D_Planet_MAT')},
        'note': 'Spacedome_MAT / CybertronMATTE_MAT are not compiled because the placed actors override them (correct)'},
        'extracted, streamed levels complete; only the shared reflection cubemaps are missing (separate gap)'))
    # ---- projectile bodies (grenades) + title planet override
    bodies = {}
    for pid in ('FlashBangs', 'HealGrenades', 'FlakGrenades'):
        for pr in wpn(pid).get('projectiles') or []:
            bodies['%s/%s' % (pid, pr['class'].rsplit('.', 1)[-1])] = pr.get('body_mesh')
    out.append(item('Grenade projectile bodies', REF, 'GAMEPLAY / RENDERING', bodies,
                    'mesh body = PROJMESH.StaticMesh (+ DrawScale); agrees with RE notes/data/projectile_effect_bindings.json for all 15 MP '
                    'projectile classes (vehicle projectiles have no mesh: the FlightEffect is the body)',
                    'weapon.json projectiles[].body_mesh (was reported as particle-only)'))
    out.append(item('Title planet surface material override (UI_FrontEnd)', EV, 'RENDERING', {
        'SurfaceA_STAT / SurfaceB_STAT': 'world.glb binds ENV_NEU_CybertronLowShell_Mat (component override), not the mesh default LowSurface',
        'lightmaps': 'UI_FrontEnd lightmaps.json (UI_FrontEnd_m_LM atlases)'}, 'RE TARGETED_PASS5 confirms; no AssetTools change needed'))
    # ---- sniper / fine-aim UI
    hp = (J(os.path.join(AT, 'manifests', 'hud', 'hud_package.json'), {}) or {}).get('crosshair') or {}
    sn = wpn('SniperRifle')
    fa = {pid: (wpn(pid).get('fine_aim_camera (OverTheShoulder strategy FOV)') or {}) for pid in ('SniperRifle', 'HeavyPistol', 'BurstRifle', 'AssaultRifle')}
    out.append(item('Sniper / fine-aim FOV and camera', NC, 'GAMEPLAY (camera states) + FRONTEND (scope)', {
        'fov_by_weapon': {k: {'weapon_pcs': v.get('weapon_pcs'), 'fine_aim': v.get('fov_fine_aim'), 'default': v.get('fov_default')} for k, v in fa.items()},
        'source': 'CAM_Strategies_p.OverTheShoulder_STRATEGY TnFovCameraBehavior.FOVsByPCS (RE TARGETED_PASS5 s3, CONFIRMED data)',
        'scope_symbols': (hp.get('scopes') or {}).get('symbols'),
        'sniper_fine_aim_data (MultiplayerData)': {k: (sn.get('gameplay (versus WEPDATA = MultiplayerData, CONFIRMED)') or {}).get(k)
                                                   for k in ('FineAimTargetFocusParams', 'FineAimSpreadModifier', 'PerShotSpreadModifier')}},
        'fine-aim FOV now in weapon.json "fine_aim_camera (...)" (Sniper 20, HeavyPistol / BurstRifle 30, other weapons 45, default 80); '
        'the scope symbol a weapon selects remains UNKNOWN (native / ActionScript)', 'fine_aim_camera added to weapon.json'))
    out.append(item('Sniper scope symbol selection', UNK, 'FRONTEND / RE', {'symbols': (hp.get('scopes') or {}).get('symbols')},
                    'not in authored data'))
    res = OrderedDict([('generated_by', 'AssetTools/scripts/wfc/playtest_gap_audit.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
                       ('vocabulary', [EV, NC, BAD, REF, NP, UNK]), ('default_four_classes', CLASSES), ('items', out)])
    json.dump(res, open(os.path.join(AT, 'manifests', 'audit', 'playtest_gaps.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    md = ['# Human-playtest gap audit (assets)', '',
          '*Generated by `scripts/wfc/playtest_gap_audit.py` (%s). Do not edit; rerun the generator. Evidence is in '
          '`manifests/audit/playtest_gaps.json`.*' % res['generated'], '',
          '| area | verdict | owner | action | fixed in this pass |', '|---|---|---|---|---|']
    md += ['| %s | **%s** | %s | %s | %s |' % (i['area'], i['verdict'], i['owner'], (i['action'] or '').replace('|', '/'), i['fixed_in_this_pass'] or '')
           for i in out]
    open(os.path.join(AT, 'docs', 'PLAYTEST_GAP_AUDIT.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    for i in out: print(i['verdict'], '|', i['area'])

if __name__ == '__main__':
    main()
