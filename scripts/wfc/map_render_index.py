"""Renderer-facing render_index.json for any multiplayer map (generic counterpart of m04_complete's Streets index).

  python map_render_index.py <MAP>
    non-Streets -> ExtractedAssets/VerticalSlice/Maps/<MAP>/render_index.json  (the file the renderer's loadMapProps reads)
    MP_IAC_Streets -> manifests/maps/MP_IAC_Streets/render_index_crosscheck.json only (the validated Streets render_index is
                      m04_complete.py's and is never written here); the cross-check compares both section by section.

Sections (same keys / record shapes as the validated Streets index, same derivation rules):
  pickup_factory_visuals            ammo crate inventory pickup mesh at the factory, health / overshield mesh particles,
                                    flag / bomb resting meshes (m04_complete.objective_rest_visual)
  pickup_fx_components              every factory ParticleSystemComponent with its draw rule
  not_in_world_glb (authored renderables)
                                    domination totems, KOTH active-zone rings (class template), destructibles with every state
                                    static mesh (piece translation x actor; Streets CONFIRMED rule)
  authored_render_state / mode_visual_state / tdm_render_state
Inputs: per-map manifests from the generic pipeline (m03_common.map_out names) + the slice gameplay.json.
"""
import json, os, sys
from collections import Counter, OrderedDict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A  # noqa: E402
import smsections  # noqa: E402
from m03_common import MANI, CONF, PART, map_out, map_levels  # noqa: E402
from vs_common import VS, ROOT, ue_actor_matrix, ue_to_gltf_matrix, ue_scale, ue_trans  # noqa: E402
from m04_complete import objective_rest_visual  # noqa: E402

MODES = ['DM', 'TDM', 'CTF', 'EXT', 'DOM', 'KOTH']
GEN = 'AssetTools/scripts/wfc/map_render_index.py'

def J(p, d=None): return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else d
def mani(MAP, name): return J(os.path.join(MANI, map_out(MAP, name) if MAP != 'MP_IAC_Streets' else name), {})
def v3(d, keys, dflt): return [d.get(k, dflt) for k in keys] if isinstance(d, dict) else list(d or [dflt] * 3)
def actor_matrix(t, scale3=True):
    return ue_actor_matrix(v3(t.get('Location'), 'XYZ', 0.0), v3(t.get('Rotation'), ('Pitch', 'Yaw', 'Roll'), 0), t.get('DrawScale') or 1.0,
                           v3(t.get('DrawScale3D'), 'XYZ', 1.0) if scale3 else [1, 1, 1])
def val(f): return f.get('value') if isinstance(f, dict) and 'value' in f else f

def build(MAP):
    inv = J(os.path.join(MANI, 'streets_actor_inventory.json' if MAP == 'MP_IAC_Streets' else 'next_map/%s_actor_inventory.json' % MAP), {})
    actors = inv.get('actors') or []
    gp = J(os.path.join(VS, 'Maps', MAP, 'gameplay.json'), {})
    pf = mani(MAP, 'streets_pickup_factories.json'); pfx = (mani(MAP, 'streets_pickup_fx.json') or {}).get('systems') or {}
    dd = mani(MAP, 'streets_destructibles.json')
    base_lv = map_levels(MAP)['base']
    ri = OrderedDict([('map', MAP), ('generated_by', GEN), ('coordinate_system', 'see map.json (glTF Y-up metres)'),
                      ('note', 'generic render index (same keys and rules as the validated Streets index from m04_complete.py)'),
                      ('not_in_world_glb (authored renderables)', []), ('authored_render_state', [])])
    R = ri['not_in_world_glb (authored renderables)']
    bases = []
    for a in actors:
        if a['class'] == 'TnDominationPoint':
            sk = next((c for c in a['components'] if c['class'] == 'SkeletalMeshComponent'), {})
            t = a['transform']; M = actor_matrix(t)
            R.append({'actor': a['actor'], 'kind': 'domination energon totem (SkeletalMesh)', 'mesh': sk.get('SkeletalMesh'),
                      'gltf': 'content/PROP_NEU_Pickups_p/EnergonTotem/NEU_EnergonTotem_SKEL.gltf',
                      'anim': 'content/PROP_NEU_Pickups_p/EnergonTotem/NEU_EnergonTotem_ANM.anim.gltf',
                      'idle_anim (DeactivatedLoopAnim)': A.values(a['actor']).get('DeactivatedLoopAnim'),
                      'transform': t, 'CastShadow': sk.get('CastShadow'), 'visible_in_modes': ['DOM'],
                      'ue_matrix': M.tolist(), 'gltf_matrix': ue_to_gltf_matrix(M),
                      'section_materials': 'skeletal mesh slots (see glTF materials)',
                      'component_template': 'TransContent.Default__TnDominationPoint.PointMesh0', 'confidence': CONF})
        if a['class'] == 'InterpActor' and a.get('bHidden'):
            bases.append(a['actor'])
            ri['authored_render_state'].append({'actor': a['actor'], 'state': 'bHidden=true at load; Kismet UnHide per gameplay.json mode rules',
                                                'in_world_glb': True, 'confidence': CONF})
        if a.get('Physics') == 'PHYS_Rotating':
            ri['authored_render_state'].append({'actor': a['actor'], 'state': 'PHYS_Rotating %s' % A.values(a['actor']).get('RotationRate'),
                                                'in_world_glb': True, 'confidence': CONF})
    # KOTH rings (class template component placed with the zone transform)
    tmpl = 'TransContent.Default__TnKingOfTheHillZone.ActiveMeshComponent0'
    tv = A.values(tmpl); kz = A.values('TransContent.Default__TnKingOfTheHillZone'); tmesh = tv.get('StaticMesh')
    secs = (smsections.sections(base_lv, tmesh) or []) if tmesh and base_lv else []
    for a in actors:
        if a['class'] != 'TnKingOfTheHillZone': continue
        t = a['transform']; M = actor_matrix(t)
        R.append({'actor': a['actor'], 'kind': 'KOTH active-zone ring (class template StaticMeshComponent)', 'mesh': tmesh,
                  'gltf': 'content/' + tmesh.split('.')[0] + '/Mesh/' + tmesh.rsplit('.', 1)[-1] + '.gltf',
                  'component_template': tmpl, 'component_transform': 'identity (template has no Translation/Rotation; Scale 1)',
                  'section_materials': [s['material'] for s in secs], 'material_overrides': tv.get('Materials'),
                  'transform': t, 'ue_matrix': M.tolist(), 'gltf_matrix': ue_to_gltf_matrix(M),
                  'CastShadow': tv.get('CastShadow'), 'CollideActors': tv.get('CollideActors'),
                  'runtime_colors (zone class defaults)': {'NeutralColor': kz.get('NeutralColor'), 'CaptureColor': kz.get('CaptureColor')},
                  'visible_in_modes': ['KOTH'], 'visibility_rule': 'only the currently active zone (random at MatchStarting, rotates via ActivateNewZone)',
                  'confidence': CONF})
    # destructibles: every state static mesh at piece translation x actor (no DrawScale on the actor term; Streets CONFIRMED)
    gl_of = lambda m: ('content/' + '/'.join(m.split('.')) + '.gltf') if m else None
    inv_by = {a['actor']: a for a in actors}
    for d in dd.get('actors') or []:
        a = inv_by.get(d['actor'])
        t = (a or {}).get('transform') or {k: val(v) for k, v in (d.get('transform') or {}).items() if k in ('Location', 'Rotation', 'DrawScale', 'DrawScale3D')}
        A_ = ue_actor_matrix(v3(t.get('Location'), 'XYZ', 0.0), v3(t.get('Rotation'), ('Pitch', 'Yaw', 'Roll'), 0), t.get('DrawScale') or 1.0,
                             v3(t.get('DrawScale3D'), 'XYZ', 1.0))
        states, first_t = [], None
        for pc in d.get('pieces') or []:
            pp = (val(pc.get('Transform')) or {}).get('Position') or {}
            ptv = [pp.get('X', 0), pp.get('Y', 0), pp.get('Z', 0)]
            if first_t is None: first_t = ptv
            PT = ue_trans(ptv)
            for st in pc.get('states') or []:
                sm = []
                for e in st.get('effects') or []:
                    if e['class'] != 'HmStaticMeshDestructionEffectFactory' or not e['authored'].get('Mesh'): continue
                    m_ = e['authored']['Mesh']; Ms = PT @ A_
                    sm.append({'mesh': m_, 'gltf': gl_of(m_), 'gltf_exists': os.path.exists(os.path.join(ROOT, gl_of(m_))),
                               'ue_matrix': Ms.tolist(), 'gltf_matrix': ue_to_gltf_matrix(Ms),
                               'lighting': e['authored'].get('LightingOption'), 'confidence': CONF})
                states.append({'piece': pc.get('PieceName'), 'handle': st.get('handle'),
                               'InitialHealth': val(st.get('InitialHealth')), 'AutomaticTransitionTime': val(st.get('AutomaticTransitionTime')),
                               'links': [{'to': l.get('NextStateHandle'), 'trigger': l.get('TransitionTrigger')} for l in st.get('links') or []],
                               'static_meshes': sm,
                               'animated_mesh_templates': [e['authored'].get('ComponentTemplate') for e in st.get('effects') or []
                                                           if e['class'] == 'HmAnimatedMeshDestructionEffectFactory'] or None,
                               'effects': dict(Counter(e['class'] for e in st.get('effects') or []))})
        first = next((s['static_meshes'][0] for s in states if s['static_meshes']), None)
        R.append({'actor': d['actor'], 'kind': 'destructible (intact state mesh)', 'class': d.get('class'),
                  'mesh': (first or {}).get('mesh'), 'gltf': (first or {}).get('gltf'), 'transform': t,
                  'component_translation_ue': first_t or [0, 0, 0], 'blueprint': (d.get('blueprint') or {}).get('object'),
                  'details': 'manifests/%s' % map_out(MAP, 'streets_destructibles.json'), 'states': states,
                  'state_note': 'handle 0 intact (drawn at load); draw only the current state static meshes; animated-mesh states '
                                '(HmAnimatedMeshDestructionEffect) carry a SkeletalMeshComponent template instead',
                  'visible_in_modes': MODES, 'confidence': CONF})
    # pickup factory visuals
    def fx_mesh(ps):
        for e in (pfx.get(ps) or {}).get('emitters') or []:
            L = e['lods'][0]
            if not L.get('mesh_record'): continue
            dd_ = {m['module']: {x['property']: x['values'] for x in m['distributions']} for m in L['compiled_modules']}
            return {'mesh': L['mesh'], 'gltf': L['mesh_record']['gltf'], 'section_materials': L['mesh_record']['section_materials'],
                    'StartLocation': (dd_.get('PMI_Location') or {}).get('StartLocation'), 'StartSize': (dd_.get('PMI_Size') or {}).get('StartSize'),
                    'MeshStartRotation': (dd_.get('PMI_MeshRotation') or {}).get('StartRotation'),
                    'MeshRotationRate': (dd_.get('PMI_MeshRotationRate') or {}).get('StartRotationRate'), 'emitter': e['name']}
        return None
    ammo = (((pf.get('factory_classes') or {}).get('TnAmmoCratePickupFactory') or {}).get('inventory') or {}).get('pickup_mesh')
    picks = []
    for i in pf.get('instances') or []:
        t = i['transform']; Af = actor_matrix(t, scale3=False)
        b = {'actor': i['actor'], 'class': i['class'], 'factory_gltf_matrix': ue_to_gltf_matrix(Af)}
        if i['class'] == 'TnAmmoCratePickupFactory' and ammo:
            picks.append(dict(b, kind='ammo crate pickup mesh (inventory PickupFactoryMesh)', mesh=ammo['StaticMesh'], gltf=ammo['gltf'],
                              component_template=ammo['component'], ue_matrix=Af.tolist(), gltf_matrix=ue_to_gltf_matrix(Af),
                              rotation_rate=ammo['PickupRotationRate'], rotation_deg_per_s=round(ammo['PickupRotationRate']['Yaw'] * 360 / 65536, 3),
                              CastShadow=ammo['CastShadow'], CollideActors=ammo['CollideActors'], CullDistance=ammo['CullDistance'],
                              visible_in_modes=MODES, visible_when='pickup available (hidden after pickup until RespawnTime %s s)' % val(i['RespawnTime']),
                              placement_confidence=CONF, placement_note='mesh = factory origin (same rule as Streets, m04_complete)'))
        elif i['class'] in ('TnHealthPickupFactory', 'TnOverShieldPickupFactory'):
            ps = ((i.get('effects') or {}).get('CustomPickupEffect') or {}).get('Template')
            m = fx_mesh(ps) if ps else None
            if not m: continue
            sl = m['StartLocation'] or [0, 0, 0]; ss = m['StartSize'] or [1, 1, 1]
            Mp = ue_scale(ss[:3]) @ ue_trans(sl[:3]) @ Af
            picks.append(dict(b, kind='%s mesh particle (%s emitter %s)' % (i['class'], ps, m['emitter']), mesh=m['mesh'], gltf=m['gltf'],
                              section_materials=m['section_materials'], authored_particle=m,
                              approx_ue_matrix=Mp.tolist(), approx_gltf_matrix=ue_to_gltf_matrix(Mp),
                              visible_in_modes=MODES, visible_when='CustomPickupEffect active while available', placement_confidence=PART))
        elif i['class'] in ('TnGameObjectivePickupFactoryFlag', 'TnGameObjectivePickupFactoryBomb'):
            try: picks.append(objective_rest_visual(i, b, Af))
            except Exception as e: picks.append(dict(b, kind='objective factory resting mesh (%s)' % i['class'], error=repr(e)[:200]))
    ri['pickup_factory_visuals'] = picks
    attached = {c: {k: v['in_Components_array']['value'] for k, v in r.get('effect_components', {}).items()}
                for c, r in (pf.get('factory_classes') or {}).items() if isinstance(r, dict)}
    mode_of = {'TnGameObjectivePickupFactoryFlag': ['CTF'], 'TnGameObjectivePickupFactoryBomb': ['EXT']}
    fxc = []
    for i in pf.get('instances') or []:
        Af = actor_matrix(i['transform'], scale3=False)
        for slot, e in (i.get('effects') or {}).items():
            att = attached.get(i['class'], {}).get(slot)
            auto = e['bAutoActivate'] if e.get('bAutoActivate') is not None else True
            fxc.append({'component': e.get('component'), 'factory': i['actor'], 'factory_class': i['class'], 'slot': slot,
                        'template': e.get('Template'), 'attached_at_spawn (in Components array)': att, 'bAutoActivate': auto,
                        'ue_matrix': Af.tolist(), 'gltf_matrix': ue_to_gltf_matrix(Af),
                        'visible_in_modes': mode_of.get(i['class'], MODES),
                        'draw_rule': ('do not draw: not attached at spawn' if not att else
                                      'draw while the pickup / factory is available (SetPickupVisible / SetPickupHidden)'),
                        'confidence': CONF})
    ri['pickup_fx_components'] = {'count': len(fxc), 'by_template': dict(Counter(x['template'] for x in fxc)), 'components': fxc}
    # mode state (map_complete's class rules + Kismet bases)
    import map_complete as MC
    by_cls = lambda c: [a for a in actors if a['class'] == c]
    ms = OrderedDict()
    for cls, rule in MC.CLASS_RULES.items():
        acts = by_cls(cls)
        if acts: ms[cls] = dict(rule, actors=[a['actor'].rsplit('.', 1)[-1] for a in acts])
    kis = [t['actor'] for r in gp.get('mode_dependent_visibility') or [] if r.get('action') == 'UnHide' for t in r.get('targets', []) if t.get('initially_hidden')]
    if kis: ms['Kismet-hidden objective props'] = {'visible_in': sorted({MC.RULE_MODE.get((r.get('rule') or '').split('.')[-1], r.get('mode_comment'))
                                                                         for r in gp.get('mode_dependent_visibility') or []}), 'actors': sorted(kis)}
    ri['mode_visual_state'] = ms
    hid = sorted({x for v in ms.values() if 'TDM' not in v['visible_in'] for x in v['actors']})
    ri['tdm_render_state'] = {'hide': hid, 'count': len(hid)}
    # path validation
    paths = [x.get('gltf') for x in R + picks if isinstance(x.get('gltf'), str)]
    paths += [m['gltf'] for x in R for s in x.get('states') or [] for m in s['static_meshes']]
    ri['validation'] = {'gltf_paths': len(set(paths)), 'missing': sorted({p for p in paths if not os.path.exists(os.path.join(ROOT, p))}),
                        'counts': dict(Counter(x['kind'].split(' (')[0] for x in R)), 'pickup_visuals': len(picks), 'pickup_fx': len(fxc)}
    return ri

def main():
    MAP = sys.argv[1]
    ri = build(MAP)
    if MAP == 'MP_IAC_Streets':
        out = os.path.join(MANI, 'maps', MAP, 'render_index_crosscheck.json')
        canon = J(os.path.join(VS, 'Maps', MAP, 'render_index.json'), {})
        cx = {}
        for sec in ('pickup_factory_visuals', 'not_in_world_glb (authored renderables)'):
            a = {x['actor'] + '|' + x['kind']: x for x in canon.get(sec) or []}
            b = {x['actor'] + '|' + x['kind']: x for x in ri.get(sec) or []}
            mm = []
            for k in set(a) & set(b):
                for f in ('ue_matrix', 'approx_ue_matrix', 'gltf', 'mesh', 'component_translation_ue'):
                    if f in a[k] and f in b[k]:
                        x, y = a[k][f], b[k][f]
                        same = np.allclose(np.array(x, float), np.array(y, float), atol=1e-4) if f.endswith('matrix') or f.endswith('_ue') else x == y
                        if not same: mm.append('%s %s' % (k, f))
            sa = {x['actor'] + '|' + x['kind']: x for x in canon.get(sec) or []}
            cx[sec] = {'validated': len(a), 'generic': len(b), 'same_keys': set(a) == set(b), 'only_validated': sorted(set(a) - set(b)),
                       'only_generic': sorted(set(b) - set(a)), 'field_mismatches': mm}
        cx['tdm_hidden_identical'] = set(x.rsplit('.', 1)[-1] for x in ri['tdm_render_state']['hide']) == \
            set((x if isinstance(x, str) else x.get('actor', '')).rsplit('.', 1)[-1] for x in (canon.get('tdm_render_state') or {}).get('hide') or [])
        ri['crosscheck_vs_validated_streets'] = cx
        print(json.dumps(cx, indent=1, default=str)[:3000])
    else:
        out = os.path.join(VS, 'Maps', MAP, 'render_index.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(ri, open(out, 'w', encoding='utf-8'), indent=1, default=str)
    print(MAP, ri['validation'], '->', out)

if __name__ == '__main__':
    main()
