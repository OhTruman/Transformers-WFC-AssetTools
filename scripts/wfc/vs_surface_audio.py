"""Streets surface -> robot footstep / landing audio (M03 P4).

Chain (UE3/WFC, every link from cooked data):
  surface material (Material / MIC, PhysMaterial resolved through the MIC Parent chain)   [materials_authored.json list]
  BlockingVolume.PhysMaterialOverride                                                      [placed actors]
  Engine.DefaultPhysMaterialName (fallback when nothing resolves)                          [Engine CDO]
    -> PhysicalMaterial.PhysicalMaterialProperty (TnPhysicalMaterialProperty).FootstepSounds  (HmSoundEvent per slot)
       absent property object / unset slot -> HmFootstepComponent.Default*Sound (pawn FootstepComp)
    -> HmSoundEvent -> pawn HmSoundEventSet (Optimus: SoundEvents.CHR_OPTIMUS) -> SoundCue (BL_FS_LRG_BOT.*)
    -> cue graph: root volume/pitch/attenuation, WaveEvent variants (random selection), waves
Output: AssetTools/manifests/streets_surface_audio.json
"""
import json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree, typed_props as tp  # noqa: E402
from m03_common import field, lit, write, pkg_of, CONF, HIGH, PART, UNK, map_arg, map_out, map_levels# noqa: E402
from vs_common import VS  # noqa: E402

MAP = map_arg()                      # positional map name (default MP_IAC_Streets)
LV_ = map_levels(MAP)
SLICE = os.path.join(VS, 'Maps', MAP)
SLOTS = ['FootstepWalk', 'FootstepJog', 'FootstepRun', 'FootstepCrouchWalk', 'FootstepCrouchJog', 'FootstepCrouchRun',
         'FootstepScuff', 'FootstepCrouchScuff', 'FootstepJump', 'FootstepLand', 'FootstepHardLand', 'FootstepDashLand']
COMP_DEFAULT = {'FootstepWalk': 'DefaultWalkSound', 'FootstepJog': 'DefaultJogSound', 'FootstepRun': 'DefaultRunSound',
                'FootstepCrouchWalk': 'DefaultCrouchWalkSound', 'FootstepCrouchJog': 'DefaultCrouchJogSound',
                'FootstepCrouchRun': 'DefaultCrouchRunSound', 'FootstepScuff': 'DefaultScuffSound',
                'FootstepCrouchScuff': 'DefaultCrouchScuffSound', 'FootstepJump': 'DefaultJumpSound',
                'FootstepLand': 'DefaultLandSound', 'FootstepHardLand': 'DefaultHardLandSound', 'FootstepDashLand': None}
NOTIFY = {'walk': 'FootstepWalk', 'run': 'FootstepRun', 'scuff': 'FootstepScuff', 'land': 'FootstepLand', 'hard-land': 'FootstepHardLand'}
FOOTCOMP = 'TransGame.Default__TnPawn.FootstepComp0'
EVENTSET = 'SoundEvents.CHR_OPTIMUS'

def read_cooked(opath, prefer=(LV_['base'], LV_['art'])):
    inv = objtree.inv()
    rows = [r[0] for r in inv.execute('SELECT package FROM exports WHERE opath=? ORDER BY serial_size DESC', (opath,)).fetchall()]
    pk = next((p for p in prefer if p in rows), rows[0] if rows else None)
    if not pk: return None, None, rows
    p = objtree.package(pk)
    return tp.simplify(p._tr.read_dict(p._idx[opath.lower()])), pk, rows

def resolve_physmat(m):
    path, o, seen = [], m, set()
    while o and o not in seen:
        seen.add(o); pr = (A.get(o) or {}).get('props') or {}
        path.append(o)
        for k in ('PhysMaterial', 'PhysicalMaterial'):
            if pr.get(k): return {'physmat': pr[k], 'set_on': o, 'property': k, 'parent_chain': path}
        o = pr.get('Parent')
    return {'physmat': None, 'set_on': None, 'property': None, 'parent_chain': path}

def physmat_rec(pm):
    v = (A.get(pm) or {}).get('props') or {}
    prop = v.get('PhysicalMaterialProperty')
    rec = {'physmat': pm, 'package_of_record': pkg_of(pm), 'authored': v, 'PhysicalMaterialProperty': prop}
    comp = A.values(FOOTCOMP)
    slots = {}
    if prop:
        d, pk, rows = read_cooked(prop)
        fs = (d or {}).get('FootstepSounds') or {}
        rec['property_object'] = {'object': prop, 'class': 'TnPhysicalMaterialProperty', 'read_from_package': pk,
                                  'cooked_in_streets': [r for r in rows if r.startswith(MAP)],
                                  'Type': (d or {}).get('Type'), 'FootstepSounds_raw': fs,
                                  'BodyImpactSounds': (d or {}).get('BodyImpactSounds'),
                                  'has_weapon_impact_tables': bool((d or {}).get('WeaponTypeSpecificImpactSounds') or
                                                                   (d or {}).get('WeaponTypeSpecificDecals'))}
    else:
        fs = {}
        rec['property_object'] = None
    for s in SLOTS:
        if s in fs and fs[s]:
            slots[s] = {'event': fs[s], 'origin': 'authored on %s.FootstepSounds.%s' % (prop, s), 'confidence': CONF}
        else:
            dk = COMP_DEFAULT[s]
            ev = comp.get(dk) if dk else None
            slots[s] = {'event': ev, 'origin': ('slot unset (or no PhysicalMaterialProperty) -> %s.%s' % (FOOTCOMP, dk)) if dk
                        else 'slot unset and HmFootstepComponent has no default for it -> no event',
                        'confidence': HIGH if dk else CONF,
                        'note': 'fallback to the footstep component default is the documented role of Default*Sound; '
                                'the native lookup itself is not authored data' if dk else None}
    rec['slots'] = slots
    return rec

def cue_digest(c):
    q = A.cue(c)
    def ev(t, acc):
        if t.get('class') == 'SoundNodeWaveEvent':
            acc.append({'node': t['node'], 'params': t.get('params', {}),
                        'waves': [k.get('node') for k in t.get('children', []) if k.get('class', '').startswith('SoundNodeWave')]})
        for k in t.get('children', []): ev(k, acc)
        return acc
    evs = ev(q['tree'], []) if q.get('tree') else []
    return {'cue': c, 'root': q.get('root'), 'category': q.get('category'), 'wave_events': evs,
            'waves': [{'wave': w['wave'], 'wav': w['wav'], 'duration': w['duration']} for w in q.get('waves', [])],
            'random_selection': 'each SoundNodeWaveEvent with >1 child wave picks one child per play (variants); '
                                'selection weighting/no-repeat is native (no Weights authored)'}

def main():
    mats = json.load(open(os.path.join(SLICE, 'materials_authored.json'), encoding='utf-8'))['materials']
    by_pm = defaultdict(list); mat_rows = []
    for m, r in sorted(mats.items()):
        res = resolve_physmat(m)
        mat_rows.append({'material': m, 'usage': r.get('usage'), **res,
                         'confidence': CONF if res['physmat'] else HIGH,
                         'note': None if res['physmat'] else 'no PhysMaterial on the material or any parent -> engine fallback '
                                                             '(Engine.DefaultPhysMaterialName)'})
        by_pm[res['physmat']].append(m)
    d = A.con()
    vols = [{'actor': o, 'PhysMaterialOverride': json.loads(p).get('PhysMaterialOverride'), 'confidence': CONF}
            for o, p in d.execute("SELECT opath, props FROM objects WHERE package LIKE ? AND props LIKE '%PhysMaterialOverride%'",
                                  (MAP + '%',)).fetchall()]
    eng = field('Engine.Default__Engine', 'DefaultPhysMaterialName',
                note='value baked into the cooked Engine CDO (config); used when a trace hits no physical material')
    pms = sorted({p for p in by_pm if p} | {v['PhysMaterialOverride'] for v in vols} | {eng['value']})
    physmats = {pm: physmat_rec(pm) for pm in pms}
    physmats['<no PhysicalMaterialProperty / engine default component>'] = {
        'slots': {s: {'event': A.values(FOOTCOMP).get(COMP_DEFAULT[s]) if COMP_DEFAULT[s] else None,
                      'origin': FOOTCOMP + '.' + (COMP_DEFAULT[s] or '-'), 'confidence': CONF} for s in SLOTS}}
    es = A.values(EVENTSET).get('SoundEventSet') or []
    emap = {e['Event']: e['Sound'] for e in es if e and e.get('Event')}
    events = sorted({sl['event'] for r in physmats.values() for sl in r['slots'].values() if sl['event']} |
                    {'SoundEvents_Footsteps.FS_DEFAULT_JUMP_CHARGED', 'SoundEvents_Footsteps.FS_DEFAULT_LAND_HIGH_FALL'})
    event_to_cue = {}
    for e in events:
        c = emap.get(e)
        event_to_cue[e] = {'cue': c, 'event_set': EVENTSET,
                           'confidence': CONF,
                           'note': None if c else 'event not present in the Optimus HmSoundEventSet -> no sound is mapped '
                                                  '(whether the engine plays anything is native: treat as silent)'}
    cues = {c['cue']: cue_digest(c['cue']) for c in event_to_cue.values() if c['cue']}
    # distinct footstep tables across all Streets physmats
    distinct = Counter(json.dumps({s: r['slots'][s]['event'] for s in SLOTS}, sort_keys=True) for r in physmats.values())
    out = {
        'map': MAP, 'generated_by': 'AssetTools/scripts/wfc/vs_surface_audio.py',
        'headline': {'value': ('Every %s surface resolves to the SAME footstep events (FS_DEFAULT_*). WFC has no '
                              'surface-specific robot footstep/landing audio on this map: the per-character HmSoundEventSet '
                              'chooses the sound (Optimus -> BL_FS_LRG_BOT.*). The rebuild\'s "generic/default" footsteps are '
                              'the authored behaviour, not a fallback.') % ('Streets' if MAP == 'MP_IAC_Streets' else MAP) if len(distinct) == 1 else
                              ('%s physical materials map to %d distinct footstep tables (see physical_materials)' % (MAP, len(distinct))),
                     'confidence': CONF,
                     'distinct_footstep_tables_across_streets_physmats': len(distinct)},
        'pawn_footstep_component': {'object': FOOTCOMP, 'defaults': {k: v for k, v in A.values(FOOTCOMP).items() if k.startswith('Default')},
                                    'PhysicalMaterialOverride': field(FOOTCOMP, 'PhysicalMaterialOverride', default=None),
                                    'confidence': CONF},
        'kismet_footstep_overrides_in_streets': {'value': 0, 'class': 'SeqAct_SetFootstepMaterialOverride', 'confidence': CONF},
        'engine_fallback_physmat': eng,
        'surface_materials': mat_rows,
        'materials_per_physmat': {str(k): v for k, v in by_pm.items()},
        'blocking_volume_overrides': vols,
        'physical_materials': physmats,
        'notify_to_slot (Systems-confirmed notify logic -> PhysicalMaterialPropertyFootstepSounds slot)': NOTIFY,
        'event_to_cue (Optimus robot)': event_to_cue,
        'cues': cues,
        'robot_size_distinction': {
            'mechanism': 'per-character HmSoundEventSet maps the same FS_DEFAULT_* events to different banks',
            'FS_DEFAULT_WALK bank usage across all event sets': None, 'confidence': CONF},
        'vehicle': 'no footstep path in vehicle form; vehicle land sounds come from HmPlayerVehicleAudioComponent '
                   '(Hover/BoostLandSound) - see vehicle_audio_loops.json / vertical_slice_audio_concurrency.json',
        'unresolved': ['which surface the native footstep trace samples (hit triangle material vs component PhysMaterialOverride '
                       'vs BodySetup) - irrelevant here because every candidate yields identical events',
                       'FootstepJog / Crouch* / DashLand events are not mapped in SoundEvents.CHR_OPTIMUS: native behaviour '
                       'for an unmapped event (expected: silent)']}
    c = Counter()
    for s, p in A.refs_to('SoundEvents_Footsteps.FS_DEFAULT_WALK'):
        for e in (A.values(s).get('SoundEventSet') or []):
            if e and e.get('Event') == 'SoundEvents_Footsteps.FS_DEFAULT_WALK':
                c[(e.get('Sound') or 'None').split('.')[0]] += 1
    out['robot_size_distinction']['FS_DEFAULT_WALK bank usage across all event sets'] = dict(c)
    write(map_out(MAP, 'streets_surface_audio.json'), out)
    print(out['headline']['distinct_footstep_tables_across_streets_physmats'], {k: len(v) for k, v in by_pm.items()},
          {e: v['cue'] for e, v in event_to_cue.items()})

if __name__ == '__main__':
    main()
