"""Product-ready export of every multiplayer chassis -> ExtractedAssets/VerticalSlice/Characters/<ChassisId>/

  python vs_roster_export.py --all            (or one or more RE chassis ids: Car2 Truck4 ...)

Same contract as the Optimus slice character (vs_character.py): robot.glb / vehicle.glb (skinned authored MP meshes,
resolved materials with baked customization textures, curated skeleton-verified clips), textures/, character.json.
Folder name = RE chassis UniqueId (stable id, RE-Workspace/notes/data/mp_chassis_roster.json), e.g. Characters/Car2.

Inputs (no filename guessing): manifests/mp_content/roster_package.json (meshes = ROBODEF.SkelMesh / VEHDEF.SkeletalMesh,
material slots resolved within the mesh package family, bone-verified compatible AnimSets, transform clips, UI, weapons,
abilities, audio), mp_characters.json (iconic preset), authored.db (material parameters, team colour bindings).
Clip selection: every clip of the chassis-specific sets (name contains the iconic id) + the vs_character category set from
the shared compatible sets. Every glb / texture / clip path written is checked to exist (character.json validation).
Memory: one chassis at a time; run under run_bounded.py.
"""
import json, os, re, sys, time
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vs_character as VC  # noqa: E402
import materials  # noqa: E402
import authored as AU  # noqa: E402
from vs_common import VS, ROOT, load_gltf  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MANI = os.path.join(AT, 'manifests')
GEN = 'AssetTools/scripts/wfc/vs_roster_export.py'

def J(p): return json.load(open(os.path.join(MANI, p), encoding='utf-8'))
def rel(p): return os.path.relpath(p, ROOT).replace(os.sep, '/')

_anim_names = {}
def anim_names(gltf):
    if gltf not in _anim_names:
        j = json.load(open(os.path.join(ROOT, gltf), encoding='utf-8'))
        _anim_names[gltf] = [a['name'] for a in j.get('animations', [])]
    return _anim_names[gltf]

def set_gltf(set_op):
    pkg, name = set_op.split('.', 1)
    p = os.path.join('content', pkg, name.replace('.', '/') + '.anim.gltf').replace(os.sep, '/')
    return p if os.path.exists(os.path.join(ROOT, p)) else None

# MP-only clip categories (not in the Optimus slice list): objective-carrier melee (TnMeleeSet MWT_Flag / MWT_Bomb -> Melee_Mace),
# class abilities (Skill_*), grenade / detpack throws, the shared Whirlwind form clip (Gameplay request 2026-10-05)
EXTRA_CATEGORIES = [
    ('reload_per_weapon', r'^(ADD_)?Shooting_Reload_\w+_ROBO$', 'robot'),
    ('melee_objective_carrier', r'^Melee_Mace_0\d$', 'robot'),
    ('ability', r'^(ADD_)?Skill_\w+$', 'robot'),
    ('grenade_throw', r'^(ADD_)?Grenade_?Throw$|^ADD_Detpack_Release$', 'robot'),
    ('ability_form_robot', r'^Transform_(Whirlwind|Hover|ShieldPush)_ROBO$', 'robot'),
]

def select_clips(form, sets, specific_key):
    """[(set_op, set_gltf, {sequence: category})] - chassis-specific sets first (all clips), then shared (categorised only)."""
    spec = [s for s in sets if specific_key and specific_key.lower() in s.lower()]
    order = spec + [s for s in sets if s not in spec]
    seen, chosen = set(), []
    for s in order:
        g = set_gltf(s)
        if not g: continue
        wanted = {}
        for n in anim_names(g):
            if n in seen: continue
            cat = next((c for c, rx, f in VC.CATEGORIES + EXTRA_CATEGORIES if f == form and re.search(rx, n)), None)
            if cat is None and s in spec:
                cat = ('ability_form_' if n.startswith('Transform_') else 'chassis_specific_') + form
            if cat is None and form == 'vehicle':
                cat = 'vehicle_other'
            if cat is None:   # every clip of a bone-verified compatible set is exported (per-weapon reloads, melee variants, turret
                cat = 'ai_' + form if n.startswith('AI_') else 'other_' + form   # carry, reactions ...); uncategorised -> other_*
            if cat: wanted[n] = cat; seen.add(n)
        if wanted: chosen.append((s, g, wanted))
    return chosen


# ------------------------------------------------------------------ clip notifies + vehicle FX / audio (playtest gap audit 2026-10-05)
_seq_cache = {}
VFA = {}
NOTIFY_SKIP = ('ObjectArchetype', 'NotifyInEditor')
def set_notifies(set_op):
    """{SequenceName: [notify records]} for an AnimSet: every AnimSequence's Notifies (time, class, effective authored params,
    sub-object parameter collections resolved one level)."""
    if set_op in _seq_cache: return _seq_cache[set_op]
    out = {}
    for r in AU.find(set_op + '.%', 'AnimSequence'):
        v = AU.values(r['opath']) or {}
        nm = v.get('SequenceName')
        if not nm: continue
        recs = []
        for x in v.get('Notifies') or []:
            no = (x or {}).get('Notify')
            g = AU.get(no) if no else None
            nv = {k: y for k, y in (AU.values(no) or {}).items() if k not in NOTIFY_SKIP} if no else {}
            for k, y in list(nv.items()):
                if isinstance(y, str) and no and y.startswith(no + '.') and AU.get(y):
                    nv[k] = {'object': y, 'class': AU.get(y)['class'], 'values': AU.values(y)}
            recs.append(OrderedDict([('time_s', x.get('Time')), ('duration_s', x.get('Duration')), ('class', g['class'] if g else None),
                                     ('comment', x.get('Comment')), ('params', nv)]))
        out[nm] = recs
    _seq_cache[set_op] = out
    return out

def vehicle_fx(vehdef):
    """authored vehicle-form particle structs on the VEHDEF (HoverFX / BoostFx / JumpFX / RamFX / ...): template, socket, params."""
    v = AU.values(vehdef) or {}
    fx = OrderedDict()
    for k, x in v.items():
        if isinstance(x, list) and x and isinstance(x[0], dict) and any(('Template' in kk) for kk in x[0]):
            rows = []
            for e in x:
                t = e.get('ParticleSystemTemplate') or e.get('Template')
                rows.append(OrderedDict([('template', t), ('socket', e.get('Socket') or e.get('SocketName')),
                                         ('other', {kk: yy for kk, yy in e.items() if kk not in ('ParticleSystemTemplate', 'Template', 'Socket', 'SocketName')}),
                                         ('template_in_dump', bool(AU.get(t)) if t else None)]))
            fx[k] = rows
    return fx

def runtime_colors_common():
    ap = AU.values('TransGame.Default__TnCharacterApplier')
    return {'applier_parameter_bindings (TransGame.Default__TnCharacterApplier, CONFIRMED)': {
                k: ap.get(k) for k in ('PrimaryColorMaterialParamName', 'SecondaryColorMaterialParamName', 'EnergonColorMaterialParamName')},
            'team_energon_colors (class defaults; used ONLY by kamikaze-mine fallbacks, never for bodies - RE b0d9b22)': {
                'neutral (TnTeamInfo)': AU.values('TransGame.Default__TnTeamInfo').get('EnergonColor'),
                'Autobots (TnFactionTeamAutobots)': AU.values('TransGame.Default__TnFactionTeamAutobots').get('EnergonColor'),
                'Decepticons (TnFactionTeamDecepticons)': AU.values('TransGame.Default__TnFactionTeamDecepticons').get('EnergonColor')},
            'behaviour': 'EnergonColor is NOT team-tinted (RE b0d9b22 TARGETED_PASS5_2026-10-06_energon, CONFIRMED script path): '
                         'TnCharacterApplier.ExtractColors uses CD.EnergonColor when set, else the robot mesh material default (first '
                         'slot / MIC chain defining EnergonColor) -> manifests/mp_content/energon_defaults.json; ApplyColorsToMesh writes '
                         'it to robot + vehicle meshes. Cust_Color_A / Cust_COLOR_B: CD colours when not (0,0,0,255), else the mesh '
                         'material values (RE (a)).',
            'energon_defaults': 'manifests/mp_content/energon_defaults.json (energon_defaults.py)'}

def export(cid, ch, preset, A, common):
    t0 = time.time()
    out_dir = os.path.join(VS, 'Characters', cid)
    os.makedirs(out_dir, exist_ok=True)
    VC.NAME, VC.OUT = cid, out_dir
    iconic = (ch.get('re_identity') or {}).get('UniqueIconicId') or ''
    key = re.sub(r'[^A-Za-z]', '', iconic)
    res = OrderedDict()
    for form in ('robot', 'vehicle'):
        f = ch[form]; mop = f['skeletal_mesh']
        a = A.get(mop.lower())
        if not a or not any(o.endswith('.gltf') for o in a.get('extracted') or []):
            res[form] = {'error': 'mesh not extracted', 'mesh_object': mop}; continue
        compat = ((ch.get('animation_compat') or {}).get(form) or {}).get('anim_sets') or {}
        # compatible, plus near-complete partial sets (<= 2 missing bones and <= 5% of tracks): UE3 skips tracks whose bone the
        # mesh lacks (AnimSet track -> mesh bone mapping), so the rest of the clip plays unchanged (HIGH; Soundwave misses 1 of 84)
        def usable(st):
            if st.get('status') == 'compatible': return True
            return st.get('status') == 'partial' and (st.get('missing_count') or 99) <= 2 and                 (st.get('missing_count') or 99) <= 0.05 * max(1, st.get('track_bones') or 0)
        sets = [s for s in f.get('anim_sets') or [] if usable(compat.get(s) or {})]
        partial = {s: (compat.get(s) or {}).get('missing_on_mesh') for s in sets if (compat.get(s) or {}).get('status') == 'partial'}
        sel = select_clips(form, sets, key)
        slots = f.get('material_slots (umodel short names resolved within the mesh package family - HIGH)') or []
        saved = a.get('materials')
        if slots: a['materials'] = [{'ref': s['material']} if s.get('material') else {} for s in slots]
        try:
            glb, mats, clips, src = VC.build_form(form, mop, sel, A)
        finally:
            a['materials'] = saved
        for c_ in clips:
            c_['notifies'] = set_notifies(c_['source_animset']).get(c_['sequence'], [])
        cats = Counter(c['category'] for c in clips)
        res[form] = OrderedDict([
            ('mesh_object', mop), ('definition', f.get('definition')), ('glb', rel(glb)), ('source_gltf', src),
            ('joints', f.get('joint_count')), ('skeleton_signature', f.get('skeleton_signature')),
            ('physics_asset', f.get('physics_asset')), ('anim_tree', f.get('anim_tree')),
            ('anim_sets_compatible', sets), ('anim_sets_partial_used (missing bones; tracks skipped as in UE3, HIGH)', partial or None),
            ('anim_sets_rejected', [s for s in f.get('anim_sets') or [] if s not in sets]),
            ('sockets', VC.sockets(mop, A)),
            ('materials', [{'slot': m['slot'], 'material': m['material'],
                            'textures': {k: (v or {}).get('file') for k, v in ((m['resolved'] or {}).get('textures') or {}).items()},
                            'roles': (m['resolved'] or {}).get('roles'),
                            'customization_parameters': {'vectors': (m['resolved'] or {}).get('vectors'), 'scalars': (m['resolved'] or {}).get('scalars')},
                            'baked': m['baked']} for m in mats]),
            ('animations', clips), ('clip_counts_by_category', dict(cats))])
        if form == 'robot':
            res[form]['overshield_material'] = f.get('overshield_material'); res[form]['energy_death_material'] = f.get('energy_death_material')
            res[form]['buff_materials'] = f.get('buff_materials'); res[form]['arm_blueprint'] = f.get('arm_blueprint')
            res[form]['face_fx'] = f.get('face_fx')
        else:
            res[form]['vehicle_form'] = f.get('vehicle_form'); res[form]['definition_class'] = f.get('definition_class')
    # transform clips actually present in the glbs
    have = {form: {c['sequence'] for c in (res[form].get('animations') or [])} for form in res}
    tc = ch.get('transform_clips') or {}
    trans = {'robot': [x['clip'] for x in tc.get('robot (to vehicle / to robot)') or []],
             'vehicle': [x['clip'] for x in tc.get('vehicle (to vehicle / to robot)') or []]}
    man = OrderedDict([
        ('generated_by', GEN), ('chassis_id', cid), ('stable_id_source', 'RE mp_chassis_roster.json UniqueId'),
        ('iconic_id', iconic), ('display', ch.get('display')), ('faction', ch.get('faction')),
        ('class (chassis DefaultSpecialty)', ch.get('class')), ('iconic_preset', preset),
        ('availability', ch.get('availability')), ('mp_status', ch.get('mp_status')), ('locks', ch.get('locks')),
        ('coordinate_system', 'glTF Y-up metres (umodel convention: v = 0.01*(x,z,y)_UE)'),
        ('robot', res.get('robot')), ('vehicle', res.get('vehicle')),
        ('transformation', {'clips_in_glb': {f: [c for c in trans[f] if c in have.get(f, set())] for f in trans},
                            'clips_authored': trans,
                            'rule': 'robot clip Transform_To*_ROBO on robot.glb, vehicle clip Transform_To*_VEH on vehicle.glb; separate '
                                    'skeletons, the game swaps meshes during the overlap (EVIDENCE_PASS2 section 3)'}),
        ('stats', ch.get('stats')), ('weapons', ch.get('weapons')), ('abilities', ch.get('abilities')),
        ('ui', ch.get('ui')), ('audio', ch.get('audio')),
        ('team_colour', common),
        ('vehicle_fx (VEHDEF particle structs; sockets on vehicle.glb)', vehicle_fx((ch.get('vehicle') or {}).get('definition'))
                                                                          if (ch.get('vehicle') or {}).get('definition') else None),
        ('vehicle_audio (VEHDEF AudioComp events -> chassis event set -> cue -> WAV)', VFA.get(cid)),
        ('notify_semantics', {'TnAnimNotify_ToggleHidden': 'robot / vehicle mesh swap points: params.Option when authored (e.g. Toggle_Hide), '
                                                            'otherwise the class default; which mesh it targets is script / native (UNKNOWN)',
                              'TnAnimNotify_ToggleVehicleFx': 'params.Option (Toggle_EnableFx / Toggle_DisableFx): vehicle_fx on / off',
                              'HmAnimNotify_PlayEffect': 'params.ParticleSystemTemplate at params.SocketName (Parameters = colour / size params)',
                              'HmAnimNotify_Sound': 'params.SoundCue (FireWhenForwards / FireWhenBackwards)'}),
        ('menu', {'customization_camera_id': (ch.get('ui') or {}).get('customization_camera_id') or (ch.get('re_identity') or {}).get('CustomizationCameraId'),
                  'portraits': ((ch.get('ui') or {}).get('portraits')), 'class_icon': (ch.get('ui') or {}).get('class_icon')}),
        ('roster_package_entry', 'manifests/mp_content/roster_package.json chassis["%s"]' % cid)])
    # path validation
    paths = []
    def collect(x):
        if isinstance(x, dict): [collect(v) for v in x.values()]
        elif isinstance(x, list): [collect(v) for v in x]
        elif isinstance(x, str) and re.match(r'^(content|VerticalSlice)/.*\.(glb|gltf|png|tga|wav|psa)$', x): paths.append(x)
    collect(man)
    missing = sorted({p for p in paths if not os.path.exists(os.path.join(ROOT, p))})
    man['validation'] = {'paths_checked': len(set(paths)), 'missing': missing,
                         'robot_ok': 'glb' in (res.get('robot') or {}), 'vehicle_ok': 'glb' in (res.get('vehicle') or {}),
                         'transform_clips_present': all(c in have.get(f, set()) for f in trans for c in trans[f]),
                         'seconds': round(time.time() - t0, 1)}
    json.dump(man, open(os.path.join(out_dir, 'character.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    return man

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    roster = J('mp_content/roster_package.json')['chassis']
    presets = {c['chassis_id']: c.get('iconic_preset') for c in J('mp_content/mp_characters.json')['characters']}
    ids = list(roster) if '--all' in sys.argv else args
    A = materials.assets()
    common = runtime_colors_common()
    va = json.load(open(os.path.join(MANI, 'audit', 'vehicle_fx_audio.json'), encoding='utf-8')).get('rows') or {} \
        if os.path.exists(os.path.join(MANI, 'audit', 'vehicle_fx_audio.json')) else {}
    VFA.update({cid: [{k: r.get(k) for k in ('form', 'property', 'category', 'object', 'cue', 'waves', 'wavs_exported', 'export', 'why')}
                      for r in v.get('records') or [] if r.get('kind') == 'sound'] for cid, v in va.items()})
    index = OrderedDict()
    for cid in ids:
        try:
            m = export(cid, roster[cid], presets.get(cid), A, common)
            v = m['validation']
            index[cid] = {'dir': 'VerticalSlice/Characters/%s' % cid, 'iconic_id': m['iconic_id'], 'faction': m['faction'],
                          'class': m['class (chassis DefaultSpecialty)'], 'robot_glb': (m['robot'] or {}).get('glb'),
                          'vehicle_glb': (m['vehicle'] or {}).get('glb'),
                          'robot_clips': len((m['robot'] or {}).get('animations') or []), 'vehicle_clips': len((m['vehicle'] or {}).get('animations') or []),
                          'validation': v}
            print(cid, m['iconic_id'], 'robot clips', index[cid]['robot_clips'], 'vehicle clips', index[cid]['vehicle_clips'],
                  'missing', len(v['missing']), 'transform ok', v['transform_clips_present'], '%.0fs' % v['seconds'], flush=True)
        except Exception as e:
            import traceback; traceback.print_exc()
            index[cid] = {'error': repr(e)[:300]}
            print(cid, 'ERROR', repr(e)[:200], flush=True)
    if '--all' in sys.argv:
        out = OrderedDict([('generated_by', GEN), ('root', 'ExtractedAssets (local, not pushed); paths relative to it'),
                           ('contract', 'Characters/<ChassisId>/{robot.glb, vehicle.glb, character.json, textures/} - same as Optimus'),
                           ('chassis', index)])
        json.dump(out, open(os.path.join(MANI, 'mp_content', 'character_export_index.json'), 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    main()
