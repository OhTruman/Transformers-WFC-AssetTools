"""Vertical slice: playable character (Optimus Prime) -> VerticalSlice/Characters/Optimus/

robot.glb / vehicle.glb : umodel skinned mesh + resolved materials (baked customization
                          colour textures) + curated, skeleton-verified animation clips
textures/               : baked base colour / emissive / specular per material (derived)
character.json          : manifest (meshes, skeletons, sockets, animation catalogue by
                          category with source sets, sounds via the game's own cue banks)
"""
import json, os, re, sys
from collections import defaultdict
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ue3pkg, props, extract, materials, animcompat  # noqa: E402
from vs_common import *  # noqa: E402,F401

NAME = 'Optimus'
OUT = os.path.join(VS, 'Characters', NAME)
ROBOT = 'TR_Optimus_ROBO_p.RB_Optimus_A_SKELMESH'
VEHICLE = 'TR_Optimus_VEH_p.VH_OptimusPrime_SKEL'
WEAPON_ARM = 'TR_Optimus_ROBO_p.RB_OptimusWeaponArm_SKEL'
CUE_BANKS = {'transformation': ['BL_TRANSFORM.OPTIMUS_BOT2VEH', 'BL_TRANSFORM.OPTIMUS_VEH2BOT'],
             'vehicle': 'BL_VEH_OPTIMUS_PRIME', 'footsteps_movement': 'BL_FS_LRG_BOT'}

CATEGORIES = [  # (category, regex on sequence name, form)
    ('idle', r'^(NAV_Idle|Nav_Idle_Base|Cust_Idle|Nav_Idle_Pose)$', 'robot'),
    ('walk', r'^Nav_StrafeWalk_[FBLR]$', 'robot'),
    ('run', r'^Nav_StrafeJog_[FBLR]$', 'robot'),
    ('turn', r'^(Nav_Pivot(90|180)_[LR]|Nav_IdlePivot90_[LR])$', 'robot'),
    ('jump', r'^(Nav_TakeOff_0[12]|Nav_TakeOff_01)$', 'robot'),
    ('fall', r'^(Nav_Jump_Descent(_0[23])?|Nav_Jump_Drift)$', 'robot'),
    ('land', r'^Nav_Land(_0[23])?$', 'robot'),
    ('boost_dodge', r'^(Nav_Boost_[FBLR]|Nav_Slide_[FB]|Nav_Hover)$', 'robot'),
    ('aim', r'^Shooting_Aim_[LFR]_[UCD]$', 'robot'),
    ('fire', r'^(ADD_Shooting_OverHeat_(Start|Loop|End)|Shooting_RocketBarrage_Stand_F)$', 'robot'),
    ('reload', r'^(Shooting_Reload_IonBlaster_ROBO|ADD_Shooting_Reload_(Fast|Med|Slow)_ROBO)$', 'robot'),
    ('equip', r'^(ADD_)?Shooting_(equip|UnEquip)_[Ww]eapon$', 'robot'),
    ('melee', r'^(Melee_GunButt_H2H|Melee_KnockBack_H2H|Melee_KnockForward_H2H|Melee_KnockLeft_H2H|Melee_KnockRight_H2H|'
              r'Melee_Block_H2H|MELEE_Stomp|Melee_EnergonSword_0[13]|Melee_2HitCombo_EnergonHammer)$', 'robot'),
    ('hit_reaction', r'^ADD_HitReaction_React_[FBLR]$', 'robot'),
    ('death', r'^(Death_FrontShot|Death_BackShot|Death_HeadShot)$', 'robot'),
    ('transform_to_vehicle', r'^Transform_ToVehicle_(ROBO|SuperBoost_Robo)$', 'robot'),
    ('transform_to_robot', r'^Transform_ToRobot_ROBO$', 'robot'),
    ('vehicle_idle', r'^(Nav_Idle_Wheels_VEH|Nav_Hover_Pose_VEH)$', 'vehicle'),
    ('vehicle_move', r'^(Nav_Hover_[FBLR]_VEH|ADD_Nav_Hover_VEH|Nav_HoverToBoost_VEH|Nav_BoostToHover_VEH)$', 'vehicle'),
    ('vehicle_transform_to_robot', r'^Transform_ToRobot_VEH$', 'vehicle'),
    ('vehicle_transform_to_vehicle', r'^Transform_ToVehicle_(VEH|SuperBoost_Veh)$', 'vehicle'),
    ('vehicle_death', r'^Death_Hover_VEH$', 'vehicle'),
]

def srgb(lin): return np.clip(lin, 0, 1) ** (1 / 2.2)

def bake_customization(mat, tag):
    """Practical bake of the WFC character 'Cust' shader to base colour/emissive/specular.

    Lum_Map: R = specular power, G = diffuse luminance, B = energon glow
    CustClrAlphasMap: R = Cust_Color_A region, G = Cust_COLOR_B region, B = aux glow
    Grunge_Map: tint/dirt colour.  Colours are linear vector params (converted to sRGB).
    """
    t = mat['textures']
    def img(key):
        f = (t.get(key) or {}).get('file')
        return np.asarray(Image.open(os.path.join(ROOT, f)).convert('RGB'), 'f4') / 255 if f else None
    lum, cust, grunge = img('Lum_Map'), img('CustClrAlphasMap'), img('Grunge_Map')
    if lum is None: return None
    H, W = lum.shape[:2]
    def fit(a):
        if a is None: return None
        return np.asarray(Image.fromarray((a * 255).astype('u1')).resize((W, H)), 'f4') / 255
    cust, grunge = fit(cust), fit(grunge)
    v = mat.get('vectors', {}); s = mat.get('scalars', {})
    ca = np.array((v.get('Cust_Color_A') or [0.5, 0.5, 0.5])[:3]); cb = np.array((v.get('Cust_COLOR_B') or [0.5, 0.5, 0.5])[:3])
    neutral = np.array([0.32, 0.32, 0.33])
    base = np.broadcast_to(neutral, (H, W, 3)).copy()
    if cust is not None:
        a = cust[..., 0:1]; b = cust[..., 1:2]
        base = base * (1 - a) + ca * a
        base = base * (1 - b) + cb * b
    base = base * (lum[..., 1:2] ** 2.2) * s.get('ColorBrightness', 1.0) * 1.6
    if grunge is not None:
        g = grunge ** 2.2; base = base * (g / max(g.mean(), 1e-3))
    glow = lum[..., 2:3] + (cust[..., 2:3] if cust is not None else 0)
    emis = np.clip(glow, 0, 1) * np.array([0.25, 0.6, 1.0])
    spec = lum[..., 0]
    os.makedirs(os.path.join(OUT, 'textures'), exist_ok=True)
    files = {}
    for k, arr in (('basecolor', srgb(base)), ('emissive', srgb(emis))):
        p = os.path.join(OUT, 'textures', '%s_%s.png' % (tag, k)); Image.fromarray((arr * 255).astype('u1')).save(p); files[k] = p
    p = os.path.join(OUT, 'textures', '%s_specular.png' % tag); Image.fromarray((spec * 255).astype('u1')).save(p); files['specular'] = p
    return files

def build_form(form, mesh_op, anim_sets, A):
    a = A[mesh_op.lower()]
    gl = next(o for o in a['extracted'] if o.endswith('.gltf'))
    g, bins = load_gltf(os.path.join(ROOT, gl))
    glb = GLB('AssetTools vs_character (%s %s)' % (NAME, form))
    glb.j = {k: v for k, v in g.items() if k != 'buffers'}
    for k in ('images', 'textures', 'samplers', 'animations'): glb.j.setdefault(k, [] if k != 'samplers' else [{}])
    glb.j['asset'] = {'version': '2.0', 'generator': 'AssetTools vs_character (from umodel %s)' % gl}
    glb.bin = bytearray(bins[0])
    # materials
    slots = a.get('materials') or []
    mat_records = []
    for k, m in enumerate(glb.j['materials']):
        op = slots[k]['ref'] if k < len(slots) and isinstance(slots[k], dict) and 'ref' in slots[k] else None
        if not op and k < len(slots) and slots[k].get('candidates'):
            op = next((c for c in slots[k]['candidates'] if c.split('.')[0] == a['original_package']), slots[k]['candidates'][0])
        r = materials.resolve(op) if op else {'roles': {}, 'textures': {}}
        tag = '%s_%d_%s' % (form, k, (op or 'none').rsplit('.', 1)[-1])
        baked = bake_customization(r, tag) if 'Lum_Map' in r.get('textures', {}) else None
        pm = pbr_material(m.get('name'), r.get('roles', {}), OUT, base_override=baked['basecolor'] if baked else None,
                          extras={'wfc_material': op, 'baked_from_customization_shader': bool(baked)})
        if baked:
            pm['emissiveTexture'] = {'index': None, '_uri': rel(baked['emissive'], OUT)}; pm['emissiveFactor'] = [1, 1, 1]
        glb.j['materials'][k] = bind_textures(glb, pm)
        mat_records.append({'slot': k, 'material': op, 'resolved': r,
                            'baked': {kk: rel(vv, ROOT) for kk, vv in (baked or {}).items()}})
    # animations: copy curated clips, retarget channels by bone name onto this mesh's nodes
    node_of = {n.get('name'): i for i, n in enumerate(glb.j['nodes'])}
    clips = []
    for set_op, set_gltf, wanted in anim_sets:
        ag, ab = load_gltf(os.path.join(ROOT, set_gltf))
        anode = [n['name'] for n in ag['nodes']]
        for an in ag.get('animations', []):
            cat = wanted.get(an['name'])
            if not cat: continue
            samplers, channels, missing = [], [], 0
            for ch in an['channels']:
                tgt = node_of.get(anode[ch['target']['node']])
                if tgt is None: missing += 1; continue
                s = an['samplers'][ch['sampler']]
                inp = accessor(ag, ab, s['input']).astype('f4')
                out = accessor(ag, ab, s['output']).astype('f4')
                samplers.append({'input': glb.acc(inp, 'SCALAR', True), 'output': glb.acc(out, 'VEC3' if out.shape[1] == 3 else 'VEC4'),
                                 'interpolation': 'LINEAR'})
                channels.append({'sampler': len(samplers) - 1, 'target': {'node': tgt, 'path': ch['target']['path']}})
            if not channels: continue
            dur = float(max(glb.j['accessors'][s['input']]['max'][0] for s in samplers))
            name = an['name'] if not any(c['name'] == an['name'] for c in clips) else '%s@%s' % (an['name'], set_op.split('.')[-1])
            glb.j['animations'].append({'name': name, 'samplers': samplers, 'channels': channels,
                                        'extras': {'category': cat, 'source_animset': set_op, 'additive': an['name'].upper().startswith('ADD'),
                                                   'unmapped_channels': missing}})
            clips.append({'name': name, 'sequence': an['name'], 'category': cat, 'source_animset': set_op,
                          'source_gltf': set_gltf, 'duration_s': round(dur, 4), 'channels': len(channels),
                          'unmapped_channels': missing, 'additive': an['name'].upper().startswith('ADD')})
    glb.j.pop('buffers', None)
    out = os.path.join(OUT, form + '.glb')
    glb.write(out)
    return out, mat_records, clips, gl

def sockets(mesh_op, A):
    a = A[mesh_op.lower()]
    p = ue3pkg.Package(os.path.join(extract.COOKED, a['owner_package'] + '.xxx')); pr = props.PropReader(p)
    mi = next(i + 1 for i in range(len(p.exports)) if p.object_path(i + 1).lower() == mesh_op.lower())
    out = []
    for i, e in enumerate(p.exports):
        if p.class_name(e) == 'SkeletalMeshSocket' and e['outer'] == mi:
            d = props.props_dict(pr.read_object(i + 1)[0])
            loc = d.get('RelativeLocation', [0, 0, 0]); rot = d.get('RelativeRotation', [0, 0, 0])
            out.append({'socket': d.get('SocketName'), 'bone': d.get('BoneName'), 'relative_location_ue': loc,
                        'relative_rotation_ue': rot, 'relative_location_gltf': ue_points_to_gltf([loc])[0].round(5).tolist(),
                        'relative_scale': d.get('RelativeScale', 1.0)})
    return out

def cue(op, A):
    c = A.get(op.lower())
    if not c: return {'cue': op, 'error': 'not found'}
    waves = []
    for w in c.get('references', {}).get('sounds', []):
        wa = A.get(w.lower())
        waves.append({'wave': w, 'wav': next((o for o in (wa or {}).get('extracted', []) if o.endswith('.wav')), None)})
    return {'cue': op, 'class': c['class'], 'waves': waves}

def main():
    A = materials.assets()
    os.makedirs(OUT, exist_ok=True)
    # --- skeleton compatibility over every AnimSet (coverage + bone-length proportion test)
    forms = {'robot': ROBOT, 'vehicle': VEHICLE}
    compat = {}
    for form, mop in forms.items():
        gl = next(o for o in A[mop.lower()]['extracted'] if o.endswith('.gltf'))
        rest = animcompat.mesh_skeleton(gl)
        res = []
        for a in A.values():
            if a['class'] != 'AnimSet': continue
            psa = next((o for o in a['extracted'] if o.endswith('.psa')), None)
            if not psa: continue
            r = animcompat.evaluate(psa, rest)
            if r['coverage'] < 0.9: continue
            full = r['track_bones'] >= 0.8 * max(1, max(len(rest) - 14, 1)) if form == 'robot' else r['track_bones'] >= 0.8 * len(rest)
            res.append(dict(r, animset=a['object_path'], anim_gltf=psa[:-4] + '.anim.gltf', psa=psa,
                            full_body=bool(full), preview_mesh=a.get('preview_skeletal_mesh')))
        compat[form] = {'mesh_joints': len(rest), 'evaluated': res}
    # --- curated clip selection from compatible, full-body sets (prefer Optimus-specific, then shared)
    sel = {}
    for form in forms:
        ok = [r for r in compat[form]['evaluated'] if r['compatible'] and r['full_body']]
        pref = sorted(ok, key=lambda r: (0 if 'Optimus' in r['animset'] else 1 if 'HeavyMedium_ANM_p.Shared' in r['animset']
                                         else 2 if 'Melee_TwoHanded' in r['animset'] else 3, r['animset']))
        chosen, seen = [], set()
        for r in pref:
            wanted = {}
            for s in r['sequences']:
                if s in seen: continue
                for cat, rx, f in CATEGORIES:
                    if f == form and re.search(rx, s):
                        wanted[s] = cat; seen.add(s); break
            if wanted: chosen.append((r['animset'], r['anim_gltf'], wanted))
        sel[form] = chosen
    built = {}
    for form, mop in forms.items():
        built[form] = build_form(form, mop, sel[form], A)
    # weapon arm (robot's built-in arm cannon mesh)
    wa = A[WEAPON_ARM.lower()]
    manifest = {
        'character': NAME, 'faction': 'Autobot', 'skeleton_class': 'HeavyMedium (92 animated tracks; mesh has 106 joints)',
        'coordinate_system': 'glTF Y-up metres (umodel convention: v = 0.01*(x,z,y)_UE)',
        'robot': {'mesh_object': ROBOT, 'glb': rel(built['robot'][0], ROOT), 'source_gltf': built['robot'][3],
                  'joints': compat['robot']['mesh_joints'], 'materials': built['robot'][1],
                  'sockets': sockets(ROBOT, A), 'animations': built['robot'][2],
                  'physics_asset': 'TR_Optimus_ROBODEF_p.RB_Optimus_A_PHYSSYS (not converted)',
                  'facefx': next((o for o in A.get('tr_optimus_robo_p.rb_optimus_facefx', {}).get('extracted', [])), None)},
        'vehicle': {'mesh_object': VEHICLE, 'glb': rel(built['vehicle'][0], ROOT), 'source_gltf': built['vehicle'][3],
                    'joints': compat['vehicle']['mesh_joints'], 'materials': built['vehicle'][1],
                    'sockets': sockets(VEHICLE, A), 'animations': built['vehicle'][2],
                    'collision_hull_mesh': next((o for o in A.get('tr_optimus_veh_p.vh_optimusprime_hull', {}).get('extracted', []) if o.endswith('.gltf')), None)},
        'weapon_arm': {'mesh_object': WEAPON_ARM, 'gltf': next(o for o in wa['extracted'] if o.endswith('.gltf'))},
        'skeleton_relationship': ('Robot and vehicle are separate skeletons with no shared bone names (106 vs %d joints). '
                                  'Transformation = robot clip Transform_ToVehicle_ROBO / vehicle clip Transform_ToVehicle_VEH '
                                  '(and the reverse Transform_ToRobot_*), each on its own skeleton; the game swaps meshes '
                                  'during the transition.' % compat['vehicle']['mesh_joints']),
        'animation_compatibility': {f: {'compatible_full_body_sets': [r['animset'] for r in compat[f]['evaluated'] if r['compatible'] and r['full_body']],
                                        'compatible_partial_sets': [r['animset'] for r in compat[f]['evaluated'] if r['compatible'] and not r['full_body']],
                                        'rejected_name_similar_sets': [{'animset': r['animset'], 'coverage': r['coverage'],
                                                                        'median_length_error': r['median_length_error']}
                                                                       for r in compat[f]['evaluated'] if not r['compatible']],
                                        'method': 'track-bone coverage == 1 and median bone-length error <= 5% (animcompat.py)'}
                                    for f in forms},
        'animation_sets_full': {f: [{'animset': r['animset'], 'anim_gltf': r['anim_gltf'], 'sequences': len(r['sequences'])}
                                    for r in compat[f]['evaluated'] if r['compatible'] and r['full_body']] for f in forms},
        'sounds': {'transformation': [cue(c, A) for c in CUE_BANKS['transformation']],
                   'vehicle': [cue(a['object_path'], A) for a in A.values() if a['original_package'] == CUE_BANKS['vehicle'] and a['class'] == 'SoundCue'],
                   'footsteps_movement': [cue(a['object_path'], A) for a in A.values() if a['original_package'] == CUE_BANKS['footsteps_movement'] and a['class'] == 'SoundCue'],
                   'dialog_package': 'WL_DX_OPRIME (+_INT/_FRA), %d waves' % sum(1 for a in A.values() if a['original_package'].startswith('WL_DX_OPRIME') and a['extracted'])},
        'notes': ['Robot firing has no dedicated body clip: weapon fire is the weapon-mesh clip IonBlaster_Fire plus procedural '
                  'SpineRecoil/RightHandRecoil (see weapon manifest); aim uses the 9-way Shooting_Aim_* grid as an aim offset.',
                  'ADD_* clips are additive deltas (extras.additive) and must be applied on top of a base pose.',
                  'Base colour/emissive/specular textures are bakes of the customization shader (Cust_Color_A/B, Lum, Grunge) - an approximation.'],
    }
    json.dump(manifest, open(os.path.join(OUT, 'character.json'), 'w'), indent=1, default=list)
    for f in forms:
        cats = defaultdict(int)
        for c in built[f][2]: cats[c['category']] += 1
        print(f, built[f][0], 'clips', len(built[f][2]), dict(cats))
    print('compatible full-body sets', {f: len(manifest['animation_sets_full'][f]) for f in forms})

if __name__ == '__main__':
    main()
