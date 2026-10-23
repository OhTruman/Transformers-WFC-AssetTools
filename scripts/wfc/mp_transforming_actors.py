"""TnTransformingWorldActor on the MP maps (Integration 2026-10-17 / package 7, 2026-10-18): skeletal world actors that block through
their PhysicsAsset, which collision_pawn.glb does not carry. Read only on ExtractedAssets; MP collision and every other MP output are NOT
changed here (only this file's JSON / doc and the GLBs below are written).

  python mp_transforming_actors.py -> docs/handoff/MP_TRANSFORMING_ACTORS.md + manifests/maps/mp_transforming_actors.json
                                      + manifests/maps/transforming_actors/<mesh>.glb (transforming_glb.py)

JSON (the 2026-10-17 keys are unchanged; everything below was added as sibling keys):
  meshes{<mesh>}: glb, clip, clip_length_s, clip_direction, source gltfs, bodies[{bone, boxes[{box_extent_ue, box_local_ue,
                  box_extent_gltf, box_local_gltf}]}], checks{clip_vs_umodel, skinned_vs_boxes}, body_bone_keyframes{bone: [{t, matrix}]}
  actors[*]: mesh, animset, anim_sequence, ue_matrix, drivers[{op, class, sequence, comment, target_link, values, inputs[{input,
             fired_by_direct, fired_by_events}]}], nav_nodes_in_volume[{node, class, location_gltf}]
Posing (glTF, column vectors): world_box = actor gltf_matrix x bone_global(t) x box_local_gltf, box half extents = box_extent_gltf / 2,
bone_global(t) from the GLB clip (or body_bone_keyframes). t = 0 is Untransformed, t = clip_length is Transformed (RE: the one
AnimNodeSequence sits at normalized position 0 = Untransformed / 1 = Transformed, rate +-1).
"""
import json, os, sys
from collections import deque
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import authored as A  # noqa: E402
import skel_collision as K  # noqa: E402
import transforming_glb as TG  # noqa: E402
from vs_common import VS_SHARED, ROOT, C4, C4i, ue_actor_matrix, ue_to_gltf_matrix  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
MAPS = ['MP_ESC_BrokenHope', 'MP_ESC_Remnant', 'MP_IAC_Berth', 'MP_IAC_Rust', 'MP_IAC_Seed', 'MP_IAC_Streets', 'MP_KON_Molten',
        'MP_ORB_Debris', 'MP_UND_Complex', 'MP_UND_Gorge']
SKIP = ('ObjPosX', 'ObjPosY', 'DrawWidth', 'DrawHeight', 'InputLinks', 'OutputLinks', 'VariableLinks', 'EventLinks', 'ParentSequence',
        'ObjName', 'bSuppressAutoComment', 'ObjClassVersion', 'ObjInstanceVersion', 'Targets')
KEY_HZ = 30.0
DIRECTION = ('t = 0 is Untransformed, t = clip_length is Transformed (RE MP_TRANSFORMING_ACTORS_RE.md: one AnimNodeSequence at normalized '
             'position 0 = Untransformed / 1 = Transformed, rate +-1)')

def kismet(M, subs=None):
    """ops of every exported level of the map + backward links dst -> [(src, output, input index)]"""
    subs = subs or json.load(open(os.path.join(VS_SHARED, 'Maps', M, 'map.json'), encoding='utf-8'))['sublevels']
    ops = {}
    for lv in subs:
        for o in A.find(lv + '.TheWorld.PersistentLevel.%'):
            p = o.get('props') or {}
            if 'OutputLinks' in p or 'InputLinks' in p or o['class'].startswith(('SeqEvent', 'TnSeqEvent', 'SeqAct', 'TnSeqAct', 'Sequence')):
                ops[o['opath']] = o
    back = {}
    for src, o in ops.items():
        for ol in (o['props'] or {}).get('OutputLinks') or []:
            for l in ol.get('Links') or []:
                if l.get('LinkedOp'): back.setdefault(l['LinkedOp'], []).append((src, ol.get('LinkDesc'), l.get('InputLinkIdx', 0)))
    return ops, back

def events_into(op, idx, ops, back, depth=12):
    direct = [{'op': s, 'class': (ops.get(s) or {}).get('class'), 'output': d} for s, d, i in back.get(op, []) if i == idx]
    seen = {op}; q = deque((s, 1) for s, d, i in back.get(op, []) if i == idx); ev = []
    while q:
        cur, dp = q.popleft()
        if cur in seen: continue
        seen.add(cur); o = ops.get(cur)
        if not o: continue
        if o['class'].startswith(('SeqEvent', 'TnSeqEvent')):
            v = A.values(cur) or {}
            ev.append({'event': cur, 'class': o['class'], 'EventName': v.get('EventName'), 'ObjComment': v.get('ObjComment'), 'depth': dp}); continue
        if dp < depth:
            for s, d, i in back.get(cur, []): q.append((s, dp + 1))
    return direct, ev

def drivers(actor, ops, back):
    out = []
    for var, prop in A.refs_to(actor):
        if prop != 'ObjValue' or not ((A.get(var) or {}).get('class') or '').startswith('SeqVar'): continue
        for op, p2 in A.refs_to(var):
            g = A.get(op) or {}; c = g.get('class') or ''
            if p2 != 'VariableLinks' or c == 'Sequence': continue
            gp = g.get('props') or {}; v = A.values(op) or {}
            links = [vl.get('LinkDesc') for vl in gp.get('VariableLinks') or [] if var in (vl.get('LinkedVariables') or [])]
            ins = []
            for idx, il in enumerate(gp.get('InputLinks') or []):
                d, e = events_into(op, idx, ops, back)
                if d: ins.append({'input': il.get('LinkDesc'), 'fired_by_direct': d, 'fired_by_events': e})
            out.append({'op': op, 'class': c, 'sequence': v.get('ParentSequence'), 'comment': v.get('ObjComment'), 'target_link': links,
                        'values': {k: x for k, x in v.items() if k not in SKIP}, 'inputs': ins})
    return sorted(out, key=lambda x: x['op'])

def mesh_record(mesh_op, animset, seq, pa):
    b = TG.build(mesh_op, animset, seq)
    clip = b['clips'][0] if b['clips'] else {}
    L = clip.get('duration_s') or 0.0
    glb = b['glb']; src = os.path.join(ROOT, b['source_anim_gltf'])
    # checks: GLB clip vs the umodel anim glTF (bone globals at both ends); skinned mesh AABB vs body boxes at both ends
    ga = TG.bone_globals(glb, seq, [0.0, L]); gb = TG.bone_globals(src, seq, [0.0, L])
    common = [n for n in ga if n in gb]
    clip_dev = max((float(np.abs(ga[n][k] - gb[n][k]).max()) for n in common for k in (0, 1)), default=None)
    bodies = []
    for bs in (A.values(pa) or {}).get('BodySetup') or []:
        bv = A.values(bs) or {}; boxes = []
        for e in (bv.get('AggGeom') or {}).get('BoxElems') or []:
            TM = np.array(e['TM'], 'f8').reshape(4, 4)
            boxes.append({'box_extent_ue': [e['X'], e['Y'], e['Z']], 'box_local_ue': [float(x) for x in TM.reshape(-1)],
                          'box_extent_gltf': [e['X'] * 0.01, e['Z'] * 0.01, e['Y'] * 0.01], 'box_local_gltf': ue_to_gltf_matrix(TM)})
        und = {k: len(x or []) for k, x in (bv.get('AggGeom') or {}).items() if k != 'BoxElems' and x}
        bodies.append({'bone': bv.get('BoneName'), 'boxes': boxes, 'undecoded': und})
    sk = {}
    for tag, t in (('t0', 0.0), ('end', L)):
        G = TG.bone_globals(glb, seq, [t], {x['bone'] for x in bodies}); pts = []
        for bd in bodies:
            Bg = (G.get(bd['bone']) or [None])[0]
            if Bg is None: continue
            for bx in bd['boxes']:
                Lg = np.array(bx['box_local_gltf']).reshape(4, 4).T; h = np.array(bx['box_extent_gltf']) / 2
                for cx in (-1, 1):
                    for cy in (-1, 1):
                        for cz in (-1, 1): pts.append((Bg @ Lg @ np.array([cx * h[0], cy * h[1], cz * h[2], 1.0]))[:3])
        lo, hi = TG.skinned_bounds(glb, seq, t)
        P = np.array(pts) if pts else np.zeros((1, 3))
        sk[tag] = {'skinned_mesh_aabb': [lo.round(3).tolist(), hi.round(3).tolist()], 'boxes_aabb': [P.min(0).round(3).tolist(), P.max(0).round(3).tolist()]}
    times = [round(k / KEY_HZ, 4) for k in range(int(L * KEY_HZ) + 1)]
    if not times or times[-1] < L: times.append(round(L, 4))
    Gk = TG.bone_globals(glb, seq, times, {x['bone'] for x in bodies})
    kf = {bn: [{'t': t, 'matrix': [round(float(x), 6) for x in m.T.reshape(-1)]} for t, m in zip(times, ms)] for bn, ms in Gk.items()}
    return {'glb': os.path.relpath(glb, AT).replace('\\', '/'), 'clip': seq, 'clip_length_s': L, 'clip_direction': DIRECTION,
            'source_mesh_gltf': b['source_mesh_gltf'], 'source_anim_gltf': b['source_anim_gltf'], 'materials': b['materials'],
            'clip_channels': clip.get('channels'), 'clip_unmapped_channels': clip.get('unmapped_channels'),
            'bodies': bodies, 'checks': {'clip_vs_umodel_max_abs_global': clip_dev, 'bones_compared': len(common), 'skinned_vs_boxes': sk},
            'body_bone_keyframes_hz': KEY_HZ, 'body_bone_keyframes': kf}, Gk

def main():
    rows = []; meshes = {}; posed = {}; navs = {}; kis = {}
    for M in MAPS:
        subs = json.load(open(os.path.join(VS_SHARED, 'Maps', M, 'map.json'), encoding='utf-8'))['sublevels']
        for lv in subs:
            for r in A.find(lv + '.TheWorld.PersistentLevel.%', 'TnTransformingWorldActor'):
                if r['opath'].count('.') != 3: continue
                v = A.values(r['opath']) or {}; c = A.values(v.get('SkeletalMeshComponent') or '') or {}
                T, info = K.actor_tris(r['opath'])
                L = v.get('Location') or {}; R = v.get('Rotation') or {}
                W = ue_actor_matrix((L.get('X', 0), L.get('Y', 0), L.get('Z', 0)), (R.get('Pitch', 0), R.get('Yaw', 0), R.get('Roll', 0)), v.get('DrawScale', 1.0))
                row = {'map': M, 'sublevel': lv, 'actor': r['opath'].rsplit('.', 1)[-1], 'object': r['opath'],
                       'skeletal_mesh': c.get('SkeletalMesh'), 'physics_asset': c.get('PhysicsAsset'),
                       'location_ue': [L.get('X'), L.get('Y'), L.get('Z')], 'rotation_ue': [R.get('Pitch', 0), R.get('Yaw', 0), R.get('Roll', 0)],
                       'draw_scale': v.get('DrawScale', 1.0), 'gltf_matrix': ue_to_gltf_matrix(W),
                       'initial_state': v.get('InitialState'), 'hidden': bool(v.get('bHidden')), 'physics': v.get('Physics'),
                       'block': {'actor_bBlockActors': v.get('bBlockActors'), 'component_BlockActors': c.get('BlockActors'),
                                 'component_CollideActors': c.get('CollideActors'), 'CollisionPreset': v.get('CollisionPreset')},
                       'boxes': info['boxes'], 'skipped': info.get('skipped'), 'undecoded': info['undecoded'],
                       'collision_bounds_gltf_m': [T.reshape(-1, 3).min(0).round(2).tolist(), T.reshape(-1, 3).max(0).round(2).tolist()] if len(T) else None}
                # ---- package 7 sibling keys
                seq = (A.values(c.get('Animations')) or {}).get('AnimSeqName') if c.get('Animations') else None
                animset = (c.get('AnimSets') or [None])[0]; mk = (c.get('SkeletalMesh') or '').rsplit('.', 1)[-1]
                if mk and mk not in meshes and seq and animset:
                    meshes[mk], posed[mk] = mesh_record(c['SkeletalMesh'], animset, seq, c.get('PhysicsAsset'))
                if M not in kis: kis[M] = kismet(M)
                row.update({'mesh': mk, 'animset': animset, 'anim_sequence': seq, 'ue_matrix': [float(x) for x in W.reshape(-1)],
                            'drivers': drivers(r['opath'], *kis[M])})
                # nav nodes inside the actor's box volume (either end pose), +1 m: the nodes its state gates (no nav point references it)
                if M not in navs:
                    nf = os.path.join(VS_SHARED, 'Maps', M, 'navigation.json')
                    navs[M] = json.load(open(nf, encoding='utf-8')).get('nodes', []) if os.path.exists(nf) else []
                pts = []
                Wg = np.array(row['gltf_matrix']).reshape(4, 4).T
                for bd in (meshes.get(mk) or {}).get('bodies', []):
                    for ms in (posed.get(mk) or {}).get(bd['bone'], [])[:1] + (posed.get(mk) or {}).get(bd['bone'], [])[-1:]:
                        for bx in bd['boxes']:
                            Lg = np.array(bx['box_local_gltf']).reshape(4, 4).T; h = np.array(bx['box_extent_gltf']) / 2
                            for s in ((-1, -1, -1), (1, 1, 1), (-1, 1, -1), (1, -1, 1), (-1, -1, 1), (1, 1, -1), (-1, 1, 1), (1, -1, -1)):
                                pts.append((Wg @ ms @ Lg @ np.array([s[0] * h[0], s[1] * h[1], s[2] * h[2], 1.0]))[:3])
                if pts:
                    P = np.array(pts); lo, hi = P.min(0) - 1.0, P.max(0) + 1.0
                    row['nav_nodes_in_volume'] = [{'node': n['node'], 'class': n['class'], 'location_gltf': n['location_gltf']} for n in navs[M]
                                                  if n.get('location_gltf') and all(lo[k] <= n['location_gltf'][k] <= hi[k] for k in range(3))]
                    row['volume_aabb_gltf_m'] = [lo.round(2).tolist(), hi.round(2).tolist()]
                rows.append(row)
    out = os.path.join(AT, 'manifests', 'maps', 'mp_transforming_actors.json')
    json.dump({'generated_by': 'AssetTools/scripts/wfc/mp_transforming_actors.py', 'actors': rows, 'meshes': meshes,
               'posing': 'world_box = actor gltf_matrix x bone_global(t) x box_local_gltf; half extents = box_extent_gltf / 2; ' + DIRECTION},
              open(out, 'w', encoding='utf-8'), indent=1)
    L = ['# TnTransformingWorldActor on the MP maps (AssetTools, generated)', '',
         'Generated by `scripts/wfc/mp_transforming_actors.py`; data in `manifests/maps/mp_transforming_actors.json` (pose as UE values and '
         'glTF matrix, collision bounds in glTF metres).', '',
         '**What these are:** skeletal world actors (High Moon "transforming" props) that block through their PhysicsAsset bodies. '
         'Every body element is a box (decoded by `skel_collision.py`).',
         '`collision_pawn.glb` does not carry them, so the MP runtime may let pawns pass through.',
         '',
         '**Status:** the campaign walk graph includes them from 2026-10-17 (campaign only). MP collision is unchanged.',
         '',
         '**Fidelity check for Gameplay:** does the runtime block on these? If not, add a gated fix in package 7.', '',
         '| map | sublevel | actor | physics asset | boxes | blocks (comp) | hidden | collision bounds glTF m (min / max) |', '|---|---|---|---|---|---|---|---|']
    for r in rows:
        b = r['collision_bounds_gltf_m']
        L.append('| %s | %s | %s | `%s` | %d | %s | %s | %s |' % (r['map'], r['sublevel'].replace(r['map'] + '_', ''), r['actor'], r['physics_asset'],
                 r['boxes'], r['block']['component_BlockActors'], r['hidden'], ('%s / %s' % (b[0], b[1])) if b else (r['skipped'] or '-')))
    L += ['', 'Totals: %d actors, %d with box collision, %d boxes.' % (len(rows), sum(1 for r in rows if r['boxes']), sum(r['boxes'] for r in rows))]
    L += ['', '## Package 7: meshes, clips, bodies (2026-10-18)', '',
          '**Posing** (glTF, column vectors): `world_box = actor.gltf_matrix x bone_global(t) x box_local_gltf`, with half extents '
          '`box_extent_gltf / 2`. `bone_global(t)` comes from the GLB clip, or from `meshes[*].body_bone_keyframes` (30 Hz, column-major 4x4).',
          '', '**Clip direction:** ' + DIRECTION + '.', '',
          '| mesh | GLB (for the package overlay) | clip | length s | bodies (bone: boxes) | clip vs umodel max abs | boxes AABB t0 / end vs skinned mesh AABB t0 / end |',
          '|---|---|---|---|---|---|---|']
    for mk, m in meshes.items():
        s = m['checks']['skinned_vs_boxes']
        L.append('| %s | `%s` | %s | %.4f | %s | %s | %s / %s vs %s / %s |' % (mk, m['glb'], m['clip'], m['clip_length_s'],
                 ', '.join('%s: %d' % (b['bone'], len(b['boxes'])) for b in m['bodies']), m['checks']['clip_vs_umodel_max_abs_global'],
                 s['t0']['boxes_aabb'], s['end']['boxes_aabb'], s['t0']['skinned_mesh_aabb'], s['end']['skinned_mesh_aabb']))
    L += ['', '**For Systems (package overlay):** the GLBs above are new files under `AssetTools/manifests/maps/transforming_actors/`. Their texture '
          'URIs are relative paths into `ExtractedAssets/content/` (no texture copies).', '',
          '## Drivers (Kismet that sets state, collision and visibility)', '',
          'Every Kismet op whose target variable holds the actor, with the inputs that are fired and the events behind them. A transform '
          'can be paired with SeqAct_ChangeCollision / SeqAct_ToggleHidden (the BrokenHope bridges), so collision follows those as well as the pose.', '',
          '| map | actor | initial state | ops (class: inputs fired <- events) | nav nodes in volume |', '|---|---|---|---|---|']
    for r in rows:
        ops = '; '.join('%s: %s' % (d['class'], ', '.join('%s <- %s' % (i['input'], '/'.join(sorted({e.get('EventName') or e['class'] for e in i['fired_by_events']})) or '-')
                                                       for i in d['inputs']) or 'no input fired') for d in r.get('drivers', []))
        L.append('| %s | %s | %s | %s | %d |' % (r['map'], r['actor'], r['initial_state'], ops or '-', len(r.get('nav_nodes_in_volume') or [])))
    doc = os.path.join(AT, 'docs', 'handoff', 'MP_TRANSFORMING_ACTORS.md')
    open(doc, 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print(doc, len(rows), 'actors', len(meshes), 'meshes')

def campaign(ch):
    """--campaign <CH> (Integration / Gameplay 2026-10-23: nobody implemented TnSeqAct_TransformWorldProp, campaign doors / pods never open):
    the same records for a campaign chapter's TnTransformingWorldActors -> out/campaign_render/<CH>/transforming_actors_gameplay.json
    (the MP schema: actors[] + meshes{} + posing); mesh GLBs -> out/campaign_render/_transforming_actors/ (shared by the chapters).
    Levels = the chapter's levels; navigation.json = out/campaign_render/<CH>/navigation.json. main() / the MP outputs are untouched."""
    sys.path.insert(0, os.path.join(AT, 'work', 'campaign_render')); import campaign_render as CR
    TG.OUTDIR = os.path.join(AT, 'out', 'campaign_render', '_transforming_actors'); os.makedirs(TG.OUTDIR, exist_ok=True)
    levels = CR.chapter_levels(ch); R = os.path.join(AT, 'out', 'campaign_render', ch)
    nf = os.path.join(R, 'navigation.json'); nav = json.load(open(nf, encoding='utf-8')).get('nodes', []) if os.path.exists(nf) else []
    ops, back = kismet(ch, levels)
    rows = []; meshes = {}; posed = {}; errors = {}
    for lv in levels:
        for r in A.find(lv + '.TheWorld.PersistentLevel.%', 'TnTransformingWorldActor'):
            if r['opath'].count('.') != 3: continue
            v = A.values(r['opath']) or {}; c = A.values(v.get('SkeletalMeshComponent') or '') or {}
            try: T, info = K.actor_tris(r['opath'])
            except Exception as x: T, info = np.zeros((0, 3, 3)), {'boxes': 0, 'undecoded': {}, 'skipped': 'actor_tris: %r' % (x,)}
            L = v.get('Location') or {}; Rr = v.get('Rotation') or {}
            W = ue_actor_matrix((L.get('X', 0), L.get('Y', 0), L.get('Z', 0)), (Rr.get('Pitch', 0), Rr.get('Yaw', 0), Rr.get('Roll', 0)), v.get('DrawScale', 1.0))
            row = {'map': ch, 'sublevel': lv, 'actor': r['opath'].rsplit('.', 1)[-1], 'object': r['opath'],
                   'skeletal_mesh': c.get('SkeletalMesh'), 'physics_asset': c.get('PhysicsAsset'),
                   'location_ue': [L.get('X'), L.get('Y'), L.get('Z')], 'rotation_ue': [Rr.get('Pitch', 0), Rr.get('Yaw', 0), Rr.get('Roll', 0)],
                   'draw_scale': v.get('DrawScale', 1.0), 'gltf_matrix': ue_to_gltf_matrix(W),
                   'initial_state': v.get('InitialState'), 'hidden': bool(v.get('bHidden')), 'physics': v.get('Physics'),
                   'block': {'actor_bBlockActors': v.get('bBlockActors'), 'component_BlockActors': c.get('BlockActors'),
                             'component_CollideActors': c.get('CollideActors'), 'CollisionPreset': v.get('CollisionPreset')},
                   'boxes': info['boxes'], 'skipped': info.get('skipped'), 'undecoded': info['undecoded'],
                   'collision_bounds_gltf_m': [T.reshape(-1, 3).min(0).round(2).tolist(), T.reshape(-1, 3).max(0).round(2).tolist()] if len(T) else None}
            seq = (A.values(c.get('Animations')) or {}).get('AnimSeqName') if c.get('Animations') else None
            animset = (c.get('AnimSets') or [None])[0]; mk = (c.get('SkeletalMesh') or '').rsplit('.', 1)[-1]
            if mk and mk not in meshes and mk not in errors and seq and animset:
                try: meshes[mk], posed[mk] = mesh_record(c['SkeletalMesh'], animset, seq, c.get('PhysicsAsset'))
                except Exception as x: errors[mk] = repr(x)[:300]
            row.update({'mesh': mk, 'animset': animset, 'anim_sequence': seq, 'ue_matrix': [float(x) for x in W.reshape(-1)],
                        'drivers': drivers(r['opath'], ops, back)})
            if mk in errors: row['mesh_error'] = errors[mk]
            pts = []; Wg = np.array(row['gltf_matrix']).reshape(4, 4).T
            for bd in (meshes.get(mk) or {}).get('bodies', []):
                for ms in (posed.get(mk) or {}).get(bd['bone'], [])[:1] + (posed.get(mk) or {}).get(bd['bone'], [])[-1:]:
                    for bx in bd['boxes']:
                        Lg = np.array(bx['box_local_gltf']).reshape(4, 4).T; h = np.array(bx['box_extent_gltf']) / 2
                        for sg in ((-1, -1, -1), (1, 1, 1), (-1, 1, -1), (1, -1, 1), (-1, -1, 1), (1, 1, -1), (-1, 1, 1), (1, -1, -1)):
                            pts.append((Wg @ ms @ Lg @ np.array([sg[0] * h[0], sg[1] * h[1], sg[2] * h[2], 1.0]))[:3])
            if pts:
                P = np.array(pts); lo, hi = P.min(0) - 1.0, P.max(0) + 1.0
                row['nav_nodes_in_volume'] = [{'node': n['node'], 'class': n['class'], 'location_gltf': n['location_gltf']} for n in nav
                                              if n.get('location_gltf') and all(lo[k] <= n['location_gltf'][k] <= hi[k] for k in range(3))]
                row['volume_aabb_gltf_m'] = [lo.round(2).tolist(), hi.round(2).tolist()]
            rows.append(row)
    out = os.path.join(R, 'transforming_actors_gameplay.json')
    json.dump({'generated_by': 'AssetTools/scripts/wfc/mp_transforming_actors.py --campaign ' + ch, 'chapter': ch, 'actors': rows, 'meshes': meshes,
               'mesh_errors': errors, 'posing': 'world_box = actor gltf_matrix x bone_global(t) x box_local_gltf; half extents = box_extent_gltf / 2; ' + DIRECTION},
              open(out, 'w', encoding='utf-8'), indent=1)
    print(out, len(rows), 'actors', len(meshes), 'meshes', 'errors', errors, '| with drivers', sum(1 for r in rows if r['drivers']),
          '| with boxes', sum(1 for r in rows if r['boxes']))

if __name__ == '__main__':
    if '--campaign' in sys.argv: campaign(sys.argv[sys.argv.index('--campaign') + 1])
    else: main()
