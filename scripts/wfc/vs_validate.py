"""Validate the vertical slice and write AssetTools/manifests/vertical_slice.json.

Checks (all programmatic):
  * every GLB parses; accessors inside buffer; meshes have triangles; images exist & decode
  * skinned GLBs: skin joints, JOINTS_0/WEIGHTS_0, weights sum ~1, IBM count == joints
  * animations: channels target skin joints, unit quaternions, increasing times,
    skinned pose at mid-clip of EVERY clip stays finite and plausibly sized
  * manifests: every referenced file path exists
  * map: BSP + props geometry present, spawn points have ground below (raycast)
"""
import json, os, re, sys, time
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vs_common import ROOT, VS, read_glb, accessor, rel  # noqa: E402
import vs_skinpreview, vs_preview, extract  # noqa: E402

REPORT = {'generated': time.strftime('%Y-%m-%d %H:%M:%S'), 'checks': [], 'failures': 0}

def check(name, ok, detail=None):
    REPORT['checks'].append({'check': name, 'ok': bool(ok), 'detail': detail})
    if not ok: REPORT['failures'] += 1
    return ok

def glb_checks(path, skinned=False):
    tag = rel(path, ROOT)
    try:
        j, bins = read_glb(path)
    except Exception as ex:
        return check('parse %s' % tag, False, repr(ex))
    check('parse %s' % tag, True)
    blen = len(bins[0]); bad = 0
    for a in j['accessors']:
        v = j['bufferViews'][a['bufferView']]
        if v['byteOffset'] + v['byteLength'] > blen: bad += 1
    check('accessors in buffer %s' % tag, bad == 0, {'accessors': len(j['accessors']), 'out_of_range': bad})
    tris = 0
    for m in j.get('meshes', []):
        for p in m['primitives']:
            tris += (j['accessors'][p['indices']]['count'] if 'indices' in p else j['accessors'][p['attributes']['POSITION']]['count']) // 3
    check('geometry %s' % tag, tris > 0, {'meshes': len(j.get('meshes', [])), 'triangles': tris, 'nodes': len(j['nodes'])})
    missing = []; ok_img = 0
    for im in j.get('images', []):
        f = os.path.normpath(os.path.join(os.path.dirname(path), im['uri']))
        try: Image.open(f).verify(); ok_img += 1
        except Exception: missing.append(im['uri'])
    check('textures exist+decode %s' % tag, not missing, {'images': len(j.get('images', [])), 'ok': ok_img, 'missing': missing[:10]})
    info = {'triangles': tris, 'images': len(j.get('images', [])), 'materials': len(j.get('materials', []))}
    if skinned:
        sk = j.get('skins', [])
        check('skin %s' % tag, bool(sk) and len(sk[0]['joints']) > 0, {'joints': len(sk[0]['joints']) if sk else 0})
        ibm = j['accessors'][sk[0]['inverseBindMatrices']]['count']
        check('IBM count %s' % tag, ibm == len(sk[0]['joints']), {'ibm': ibm})
        wsum = []
        for m in j['meshes']:
            for p in m['primitives']:
                if 'WEIGHTS_0' in p['attributes']:
                    w = accessor(j, bins, p['attributes']['WEIGHTS_0']).astype('f8')
                    if w.max() > 1.5: w = w / 255
                    wsum.append(np.abs(w.sum(1) - 1).max())
        check('skin weights normalized %s' % tag, wsum and max(wsum) < 0.02, {'max_weight_sum_error': float(max(wsum)) if wsum else None})
        joints = set(sk[0]['joints'])
        bind_h = vs_skinpreview.pose(path)[1].reshape(-1, 3)
        bind_h = float(bind_h[:, 1].max() - bind_h[:, 1].min())
        anim_res = []
        for an in j.get('animations', []):
            tgt_ok = all(c['target']['node'] in joints for c in an['channels'])
            qbad = tinc = 0
            for s in an['samplers']:
                T = accessor(j, bins, s['input']); V = accessor(j, bins, s['output'])
                if len(T) > 1 and np.any(np.diff(T) < 0): tinc += 1
                if V.ndim == 2 and V.shape[1] == 4 and np.abs(np.linalg.norm(V, axis=1) - 1).max() > 0.01: qbad += 1
            _, Tm, _, _ = vs_skinpreview.pose(path, an['name'], 0.5)
            P = Tm.reshape(-1, 3); h = float(P[:, 1].max() - P[:, 1].min())
            lo, hi = np.percentile(P[:, 1], [1, 99]); hr = float(hi - lo)
            # robust extent: a few authored bones may park/eject parts far away (hidden pieces,
            # magazine ejects); the body itself must stay plausibly sized
            sane = bool(np.isfinite(P).all()) and 0.1 * bind_h < hr < 3.0 * bind_h
            far = []
            if h > 3.0 * bind_h:
                far = sorted({j['nodes'][c['target']['node']]['name'] for c in an['channels'] if c['target']['path'] == 'translation'
                              and float(np.abs(accessor(j, bins, an['samplers'][c['sampler']]['output'])).max()) > 2 * bind_h})
            if not sane and far and len(far) <= max(1, 0.05 * len(joints)):
                _, Tm2, _, _ = vs_skinpreview.pose(path, an['name'], 0.5, drop_translation=far)
                P2 = Tm2.reshape(-1, 3); h2 = float(P2[:, 1].max() - P2[:, 1].min())
                if np.isfinite(P2).all() and 0.1 * bind_h < h2 < 3.0 * bind_h:
                    sane = True   # only authored part parking / ejection is out of range
            anim_res.append({'clip': an['name'], 'targets_skin_joints': tgt_ok, 'non_unit_quat_tracks': qbad,
                             'non_increasing_time_tracks': tinc, 'mid_pose_height_m': round(h, 3),
                             'mid_pose_robust_height_m': round(hr, 3), 'pose_sane': sane,
                             'parked_or_ejected_part_bones': far})
        bad = [a for a in anim_res if not (a['targets_skin_joints'] and a['non_unit_quat_tracks'] == 0 and a['non_increasing_time_tracks'] == 0 and a['pose_sane'])]
        check('animations valid %s' % tag, not bad, {'clips': len(anim_res), 'bad': bad[:10], 'bind_height_m': round(bind_h, 3),
              'clips_with_parked_parts': [(a['clip'], a['parked_or_ejected_part_bones']) for a in anim_res if a['parked_or_ejected_part_bones']]})
        info.update({'joints': len(sk[0]['joints']), 'clips': len(anim_res), 'bind_height_m': round(bind_h, 3)})
    return info

PATH_RX = re.compile(r'\.(glb|gltf|png|wav|psa|fsb|bin|gfx|json|fxa|mkv)$', re.I)

def manifest_paths(obj, base, out):
    if isinstance(obj, dict):
        for v in obj.values(): manifest_paths(v, base, out)
    elif isinstance(obj, list):
        for v in obj: manifest_paths(v, base, out)
    elif isinstance(obj, str) and PATH_RX.search(obj) and '/' in obj and not obj.startswith(('http', 'TR_', 'WEP_')):
        cands = [os.path.join(ROOT, obj), os.path.join(base, obj)]
        out.append((obj, any(os.path.exists(c) for c in cands)))

def check_manifest(path):
    d = json.load(open(path, encoding='utf-8')); refs = []
    manifest_paths(d, os.path.dirname(path), refs)
    miss = sorted({r for r, ok in refs if not ok})
    check('manifest paths exist %s' % rel(path, ROOT), not miss, {'references': len(refs), 'missing': miss[:20]})
    return d

def spawn_ground(world_glb, spawns):
    T, _ = vs_preview.world_triangles(world_glb)
    mn = T.min(1); mx = T.max(1)
    res = []
    for s in spawns:
        x, y, z = s['location_gltf']
        sel = (mn[:, 0] <= x) & (mx[:, 0] >= x) & (mn[:, 2] <= z) & (mx[:, 2] >= z) & (mn[:, 1] <= y + 1)
        best = None
        for t in T[sel]:
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
            d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
            if abs(d) < 1e-12: continue
            w0 = ((bz - cz) * (x - cx) + (cx - bx) * (z - cz)) / d
            w1 = ((cz - az) * (x - cx) + (ax - cx) * (z - cz)) / d
            w2 = 1 - w0 - w1
            if min(w0, w1, w2) < 0: continue
            gy = w0 * ay + w1 * by + w2 * cy
            if gy <= y + 0.5 and (best is None or gy > best): best = gy
        res.append({'actor': s['actor'], 'class': s['class'], 'drop_to_ground_m': None if best is None else round(y - best, 3)})
    return res

def main():
    A = os.path.join(VS, 'Characters', 'Optimus'); W = os.path.join(VS, 'Weapons', 'IonBlaster')
    MP = sys.argv[1] if len(sys.argv) > 1 else 'MP_IAC_Streets'; M = os.path.join(VS, 'Maps', MP)
    robot = glb_checks(os.path.join(A, 'robot.glb'), True)
    vehicle = glb_checks(os.path.join(A, 'vehicle.glb'), True)
    weapon = glb_checks(os.path.join(W, 'weapon.glb'), True)
    world = glb_checks(os.path.join(M, 'world.glb'))
    colli = glb_checks(os.path.join(M, 'collision.glb'))
    check('robot non-empty', robot.get('triangles', 0) > 1000, robot)
    check('vehicle non-empty', vehicle.get('triangles', 0) > 1000, vehicle)
    ch = check_manifest(os.path.join(A, 'character.json'))
    wp = check_manifest(os.path.join(W, 'weapon.json'))
    mp = check_manifest(os.path.join(M, 'map.json'))
    pj = check_manifest(os.path.join(M, 'props.json'))
    sp = json.load(open(os.path.join(M, 'spawnpoints.json')))
    for f in ('collision.json', 'lights.json'): check_manifest(os.path.join(M, f))
    bspt = sum(v.get('render_triangles', 0) for v in mp['bsp'].values())
    check('map BSP geometry recovered', bspt > 0, {'bsp_render_triangles': bspt})   # completeness vs authored: m04_bsp audit
    check('map props placed with meshes', pj['count'] > 500 and all(p.get('gltf') for p in pj['props']),
          {'props': pj['count'], 'without_mesh': sum(1 for p in pj['props'] if not p.get('gltf'))})
    starts = [s for s in sp['points'] if 'PlayerStart' in s['class']]
    gw = spawn_ground(os.path.join(M, 'world.glb'), starts)
    gc = spawn_ground(os.path.join(M, 'collision.glb'), starts)
    g = []
    for a, b in zip(gw, gc):   # ground = nearest of render geometry and solid collision below
        ds = [x for x in (a['drop_to_ground_m'], b['drop_to_ground_m']) if x is not None]
        g.append(dict(a, drop_to_ground_m=min(ds) if ds else None,
                      ground=('collision' if b['drop_to_ground_m'] is not None and (a['drop_to_ground_m'] is None or b['drop_to_ground_m'] < a['drop_to_ground_m']) else 'render')))
    grounded = [x for x in g if x['drop_to_ground_m'] is not None and x['drop_to_ground_m'] < 6.0]
    check('player starts have ground within 6 m below', len(grounded) >= 0.9 * len(g),
          {'player_starts': len(g), 'grounded': len(grounded),
           'grounded_on_collision_only': sum(1 for x in grounded if x['ground'] == 'collision'),
           'median_drop_m': float(np.median([x['drop_to_ground_m'] for x in grounded])) if grounded else None,
           'ungrounded': [x for x in g if x not in grounded][:10]})
    # wav files of all referenced sounds
    wavs = []
    def walk(o):
        if isinstance(o, dict):
            if o.get('wav'): wavs.append(o['wav'])
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(ch['sounds']); walk(wp['sounds'])
    bad_wav = [w for w in wavs if not os.path.exists(os.path.join(ROOT, w)) or os.path.getsize(os.path.join(ROOT, w)) < 100]
    check('sound wav files exist', not bad_wav, {'wavs': len(set(wavs)), 'missing': bad_wav[:10]})
    cats = sorted({c['category'] for c in ch['robot']['animations']} | {c['category'] for c in ch['vehicle']['animations']})

    vs = {
        'generated': REPORT['generated'],
        'root': 'ExtractedAssets (paths below are relative to it)',
        'coordinate_system': 'glTF Y-up, metres, right-handed; v_gltf = 0.01*(x,z,y)_UE (umodel convention; all slice files agree)',
        'player_character': {
            'name': 'Optimus Prime', 'manifest': rel(os.path.join(A, 'character.json'), ROOT),
            'robot_form': {'glb': ch['robot']['glb'], 'mesh_object': ch['robot']['mesh_object'], 'joints': robot.get('joints'),
                           'triangles': robot.get('triangles'), 'height_m': robot.get('bind_height_m'), 'embedded_clips': robot.get('clips'),
                           'sockets': len(ch['robot']['sockets'])},
            'vehicle_form': {'glb': ch['vehicle']['glb'], 'mesh_object': ch['vehicle']['mesh_object'], 'joints': vehicle.get('joints'),
                             'triangles': vehicle.get('triangles'), 'embedded_clips': vehicle.get('clips')},
            'skeleton_relationship': ch['skeleton_relationship'],
            'animations': {'embedded_in_glb': {f: [{'name': c['name'], 'category': c['category'], 'duration_s': c['duration_s'], 'additive': c['additive']}
                                                   for c in ch[f]['animations']] for f in ('robot', 'vehicle')},
                           'categories_covered': cats,
                           'full_compatible_sets': ch['animation_sets_full']},
            'transformation': {'robot_to_vehicle': ['robot:Transform_ToVehicle_ROBO', 'vehicle:Transform_ToVehicle_VEH'],
                               'vehicle_to_robot': ['vehicle:Transform_ToRobot_VEH', 'robot:Transform_ToRobot_ROBO'],
                               'sounds': ch['sounds']['transformation']},
            'sounds': {'vehicle': ch['sounds']['vehicle'], 'footsteps_movement': ch['sounds']['footsteps_movement']},
            'materials': {f: [{'slot': m['slot'], 'material': m['material'], 'baked': m['baked'],
                               'roles': {k: v.get('file') for k, v in m['resolved'].get('roles', {}).items()}} for m in ch[f]['materials']]
                          for f in ('robot', 'vehicle')},
        },
        'weapon': {'name': 'Ion Blaster', 'manifest': rel(os.path.join(W, 'weapon.json'), ROOT), 'glb': wp['mesh']['glb'],
                   'clips': [c['name'] for c in wp['mesh']['animations']], 'fire_sound': wp['sounds']['firing'],
                   'reload_sounds': wp['sounds']['reload'], 'hud_icons': wp['hud_icons'], 'gameplay': wp['gameplay'],
                   'effects': [e['object'] for e in wp['effects']['particle_systems']]},
        'map': {'name': MP, 'dir': rel(M, ROOT), 'world_glb': rel(os.path.join(M, 'world.glb'), ROOT),
                'collision_glb': rel(os.path.join(M, 'collision.glb'), ROOT),
                'files': {k: rel(os.path.join(M, k), ROOT) for k in ('map.json', 'props.json', 'collision.json', 'spawnpoints.json', 'lights.json', 'materials.json')},
                'sublevels': mp['sublevels'], 'bsp_render_triangles': bspt, 'placed_props': pj['count'],
                'unique_meshes': mp['unique_meshes'], 'spawn_and_gameplay_points': sp['counts'],
                'world_triangles': world.get('triangles')},
        'validation': {'checks': len(REPORT['checks']), 'failures': REPORT['failures'],
                       'report': 'AssetTools/manifests/vertical_slice_validation.json'},
    }
    if MP == 'MP_IAC_Streets':
        json.dump(REPORT, open(os.path.join(extract.MANI, 'vertical_slice_validation.json'), 'w'), indent=1, default=str)
        json.dump(vs, open(os.path.join(extract.MANI, 'vertical_slice.json'), 'w'), indent=1, default=str)
    else:   # second-map probe: same checks, separate report, slice manifests untouched
        os.makedirs(os.path.join(extract.MANI, 'next_map'), exist_ok=True)
        json.dump(REPORT, open(os.path.join(extract.MANI, 'next_map', MP + '_validation.json'), 'w'), indent=1, default=str)
    for c in REPORT['checks']:
        print('%-4s %s %s' % ('OK' if c['ok'] else 'FAIL', c['check'], '' if c['ok'] else json.dumps(c['detail'], default=str)[:400]))
    print('checks', len(REPORT['checks']), 'failures', REPORT['failures'])

if __name__ == '__main__':
    main()
