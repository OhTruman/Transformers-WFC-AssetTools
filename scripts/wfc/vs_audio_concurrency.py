"""Cue-level concurrency / priority / retrigger data for the vertical-slice cues (M03 P5).

Every concurrency-relevant field that EXISTS in the cooked schema is reported per cue with its origin:
  authored (on the cue / node), inherited default (class CDO), or unset-in-schema-default.
Fields that do NOT exist anywhere in the WFC audio schema (per-owner limit, virtualization, voice-steal fade ...)
are listed once under schema_absent_fields with UNKNOWN runtime semantics.

Schema (cooked script classes):
  Engine.SoundCue          MaxConcurrentPlayCount (CDO 5), InstanceLimiting (enum InstanceLimitType, CDO kKillFarthest),
                           bLooping, Is3D, IsDialog
  HM_Engine.SoundNodeRoot  Priority, ChanceToPlayNone, DelayMin/Max, Category/SecondaryCategory(+Distance), PlayMixerPreset,
                           PlayMixerPresetOnlyIfLocalPlayerSound, IsPlayerPOV, IsUnpausable, bLooping, NonLocalPlayer*
  HM_Engine.SoundNodeWaveEvent  Priority + OverridePriority, ChanceToPlayNone, DelayMin/Max, Time, bLooping, PlayWhenSilent
  HM_Engine.SoundMixerProperties.SoundCategoryProperties  ChannelCountMixerPresetName/Threshold/Time (voice-count driven mixer)
  Engine.HmSoundEventDialogGroup  InstanceLimit, ReTriggerDelayMin/Max (dialog events only)
Output: AssetTools/manifests/vertical_slice_audio_concurrency.json
"""
import json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored as A, objtree  # noqa: E402
from m03_common import write, pkg_of, CONF, HIGH, PART, UNK  # noqa: E402
from vs_common import VS  # noqa: E402

SLICE = os.path.join(VS, 'Maps', 'MP_IAC_Streets')
CUE_CDO = 'Engine.Default__SoundCue'
ROOT_CDO = 'HM_Engine.Default__SoundNodeRoot'
WE_CDO = 'HM_Engine.Default__SoundNodeWaveEvent'
CUE_FIELDS = ['MaxConcurrentPlayCount', 'InstanceLimiting', 'bLooping', 'Is3D', 'IsDialog']
ROOT_FIELDS = ['Priority', 'ChanceToPlayNone', 'DelayMin', 'DelayMax', 'Category', 'SecondaryCategory', 'SecondaryCategoryDistance',
               'EnableSecondaryCategory', 'PlayMixerPreset', 'PlayMixerPresetOnlyIfLocalPlayerSound', 'IsPlayerPOV', 'IsUnpausable',
               'bLooping', 'NonLocalPlayerPitching', 'NonLocalPlayerPitch', 'Volume', 'SpatializationType']
WE_FIELDS = ['Priority', 'OverridePriority', 'ChanceToPlayNone', 'DelayMin', 'DelayMax', 'Time', 'bLooping', 'PlayWhenSilent']
TYPE_DEFAULT = {'IntProperty': 0, 'FloatProperty': 0.0, 'BoolProperty': False, 'ByteProperty': '(enum value 0)',
                'ObjectProperty': None, 'NameProperty': 'None', 'StrProperty': ''}
SCHEMA_ABSENT = {
    'per_owner_vs_global_limit': 'no field: MaxConcurrentPlayCount is a SoundCue property (count over PlayingAudioComponents of '
                                 'that cue); whether WFC counts per owner or globally is native',
    'voice_virtualization': 'no field in SoundCue / SoundNodeRoot / SoundNodeWaveEvent / categories',
    'fade_on_concurrency_steal': 'no field; AudioComponent FadeIn/FadeOut are runtime members, not authored per cue',
    'retrigger_delay (non-dialog)': 'no field for SFX cues; only HmSoundEventDialogGroup.ReTriggerDelayMin/Max (dialog)',
    'priority_based_replacement': 'Priority exists (root / wave event) but no field states how priority is used for voice '
                                  'stealing; InstanceLimiting only names kKillOldest / kKillNewest / kKillFarthest',
    'quietest_voice_replacement': 'not an option of InstanceLimitType'}

def enum(pkg, path):
    p = objtree.package(pkg); x = p.exports[p._idx[path.lower()] - 1]
    raw = p.data[x['serial_offset']:x['serial_offset'] + x['serial_size']]
    n = struct.unpack_from('>i', raw, 20)[0]
    return [p.names[struct.unpack_from('>i', raw, 24 + 8 * j)[0]] for j in range(n)]

def schema(cls):
    r = A.con().execute('SELECT props FROM types WHERE path=?', (cls,)).fetchone()
    return json.loads(r[0]) if r and r[0] else {}

S_CUE, S_ROOT, S_WE = schema('Engine.SoundCue'), schema('HM_Engine.SoundNodeRoot'), schema('HM_Engine.SoundNodeWaveEvent')

def fval(obj, f, cdo, sch):
    own = (A.get(obj) or {}).get('props') or {}
    if f in own: v, origin = own[f], 'authored'
    else:
        cv = A.values(cdo)
        if f in cv: v, origin = cv[f], 'inherited default (%s)' % cdo
        else:
            t = (sch.get(f) or {}).get('type')
            v, origin = TYPE_DEFAULT.get(t), 'unset in object and class default -> %s zero value' % t
    if f in ('Category', 'SecondaryCategory') and isinstance(v, str) and '.' in v:
        v = ((A.get(v) or {}).get('props') or {}).get('CategoryName') or (A.values(v).get('CategoryName')) or v
    if f == 'PlayMixerPreset' and isinstance(v, str) and '.' in v:
        v = ((A.get(v) or {}).get('props') or {}).get('PresetName') or A.values(v).get('PresetName') or v
    return {'value': v, 'origin': origin}

def cue_rec(c, users):
    r = A.get(c)
    if not r: return {'cue': c, 'missing': True, 'used_by': users}
    rec = {'cue': c, 'package': r['package'], 'used_by': sorted(users),
           'cue_fields': {f: fval(c, f, CUE_CDO, S_CUE) for f in CUE_FIELDS}}
    fn = (r['props'] or {}).get('FirstNode')
    if fn and (A.get(fn) or {}).get('class') == 'SoundNodeRoot':
        rec['root'] = {'node': fn, **{f: fval(fn, f, ROOT_CDO, S_ROOT) for f in ROOT_FIELDS}}
        wes = []
        def walk(n, depth=0):
            o = A.get(n)
            if not o or depth > 24: return
            if o['class'] == 'SoundNodeWaveEvent':
                wes.append({'node': n.rsplit('.', 1)[-1], 'variants': len([k for k in (o['props'] or {}).get('ChildNodes') or [] if k]),
                            **{f: fval(n, f, WE_CDO, S_WE) for f in WE_FIELDS}})
            for k in (o['props'] or {}).get('ChildNodes') or []:
                if k: walk(k, depth + 1)
        walk(fn)
        rec['wave_events'] = wes
    elif fn:
        rec['first_node_class'] = (A.get(fn) or {}).get('class')
    return rec

def categories():
    mx = (A.get('SoundConfig.SoundMixerProperties') or {}).get('props') or {}
    out = {}
    def walk(lst):
        for c in lst or []:
            if not isinstance(c, dict): continue
            out[c.get('Name')] = {k: c.get(k) for k in ('Volume', 'IsMusic', 'ChannelCountMixerPresetName',
                                                        'ChannelCountMixerPresetThreshold', 'ChannelCountMixerPresetTime')}
            walk(c.get('ChildCategories'))
    walk(mx.get('SoundCategories'))
    return out

def slice_cues():
    users = {}
    def add(c, who):
        if c: users.setdefault(c, set()).add(who)
    for e in A.values('SoundEvents.CHR_OPTIMUS').get('SoundEventSet') or []:
        if e and e.get('Sound'):
            ev = e.get('Event') or ''
            add(e['Sound'], 'footsteps/jump/landing' if 'Footsteps' in ev else 'optimus robot')
    vd = A.values('TR_Optimus_ROBODEF_p.Optimus_ROBODEF')['TransformerVehicle']
    for e in A.values(A.values(vd)['SoundEventSet']).get('SoundEventSet') or []:
        if e and e.get('Sound'): add(e['Sound'], 'optimus vehicle')
    add(A.values(vd).get('DeathSound'), 'optimus vehicle')
    wm = A.values('WEP_IonBlaster_p.IonBlaster_WEPMESH')
    for e in wm.get('WeaponEventSounds') or []:
        add(e.get('WeaponSound'), 'fine aim' if 'FineAim' in (e.get('WeaponEventType') or '') else 'ion blaster')
    for k in ('PickupSound', 'DefaultImpactSound', 'BulletBySound'): add(wm.get(k), 'ion blaster')
    w = json.load(open(os.path.join(VS, 'Weapons', 'IonBlaster', 'weapon.json'), encoding='utf-8'))
    import re
    for c in set(re.findall(r'BL_WPN_GUN_ION_BLASTER\.[A-Z0-9_]+', json.dumps(w))): add(c, 'ion blaster')
    for c in ('BL_TRANSFORM.OPTIMUS_BOT2VEH', 'BL_TRANSFORM.OPTIMUS_VEH2BOT', 'BL_TRANS_POWER.TRANSFORM_DISABLED'):
        add(c, 'transformation')
    a = json.load(open(os.path.join(SLICE, 'audio.json'), encoding='utf-8'))
    for c in a['cues']: add(c, 'MP_IAC_Streets ambience')
    return users

def main():
    users = slice_cues()
    recs = [cue_rec(c, u) for c, u in sorted(users.items())]
    cats = categories()
    used_cats = {r['root']['Category']['value'] for r in recs if r.get('root')} | \
                {r['root']['SecondaryCategory']['value'] for r in recs if r.get('root')}
    from collections import Counter
    summ = Counter()
    for r in recs:
        if r.get('missing'): continue
        cf = r['cue_fields']
        summ['MaxConcurrentPlayCount authored'] += cf['MaxConcurrentPlayCount']['origin'] == 'authored'
        summ['InstanceLimiting authored'] += cf['InstanceLimiting']['origin'] == 'authored'
        summ['root Priority authored'] += bool(r.get('root')) and r['root']['Priority']['origin'] == 'authored'
        summ['cues'] += 1
    out = {'generated_by': 'AssetTools/scripts/wfc/vs_audio_concurrency.py',
           'scope': 'cues used by Optimus robot/vehicle, Ion Blaster, transformation, Streets ambience, fine aim, jump, landing, footsteps',
           'class_defaults (CONFIRMED)': {'Engine.Default__SoundCue': {k: A.values(CUE_CDO).get(k) for k in CUE_FIELDS},
                                          'InstanceLimitType enum': enum('Engine', 'Engine.SoundCue.InstanceLimitType'),
                                          'HM_Engine.Default__SoundNodeRoot': {k: A.values(ROOT_CDO).get(k) for k in ROOT_FIELDS
                                                                               if k in A.values(ROOT_CDO)},
                                          'HM_Engine.Default__SoundNodeWaveEvent': {k: A.values(WE_CDO).get(k) for k in WE_FIELDS
                                                                                    if k in A.values(WE_CDO)}},
           'semantics': {'MaxConcurrentPlayCount + InstanceLimiting': 'CONFIRMED fields; UE3 meaning: when the cue already has '
                                                                       'MaxConcurrentPlayCount playing components, kill the oldest / '
                                                                       'newest / farthest instance. WFC runtime enforcement: native',
                         'Priority': 'authored float; runtime use (voice stealing order) UNKNOWN - native',
                         'ChannelCountMixerPreset*': 'category-level: when the category voice count passes Threshold, '
                                                     'the named mixer preset applies (Time = hold/fade); runtime semantics native'},
           'schema_absent_fields (UNKNOWN runtime semantics -> Native RE)': SCHEMA_ABSENT,
           'summary': dict(summ),
           'categories_used': {c: cats.get(c) for c in sorted(x for x in used_cats if x)},
           'cues': recs}
    write('vertical_slice_audio_concurrency.json', out)
    print(json.dumps(out['summary']), len(recs))

if __name__ == '__main__':
    main()
