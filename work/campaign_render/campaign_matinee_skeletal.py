"""Matinee skeletal bindings (Gameplay 2026-10-23, matinee AnimControl): every skeletal actor a matinee group with an AnimControl track
binds (SkeletalMeshActor / SkeletalMeshActorMAT / HmSkeletalMeshActor ...), with its mesh and the clips the tracks play; and the groups
bound to pawns / runtime actors (characters, spawned, player) with their GroupAnimSets' files and clips. Read only:
manifests/next_map/<CH>_matinee.json (vs_matinee: groups, bindings, AnimControl keys) + authored.db (InterpGroup GroupAnimSets, the
actor's SkeletalMeshComponent) + mp_roster.animset (content anim glTF + sequence names, as the character exports use).
  rows[]: actor, object, class, sublevel, location_gltf, rotation_deg, DrawScale3D (as actors.json); mesh, mesh_gltf (content skinned glTF);
          anim_sets (component AnimSets + the groups' GroupAnimSets) with anim_gltf + clip names; anim_files; clip_map {clip: anim glTF};
          clips_missing (a key's clip in none of those sets); uses [{interp_data, group, clips}]
  pawn_groups[]: interp_data, group, bound (as vs_matinee resolves it), clips, anim_sets / clip_map
    python campaign_matinee_skeletal.py <CH>  -> out/campaign_render/<CH>/matinee_skeletal.json
"""
import json, os, sys
from collections import Counter, OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc')); sys.path.insert(0, HERE)
import authored as A, mp_roster as M  # noqa: E402
import campaign_render as CR  # noqa: E402
DEG = 360.0 / 65536.0
RUNTIME = ('SPAWNED_BY:', 'WRITTEN_BY:', 'CHARACTER:', 'PLAYER')
_AS = {}

def animset(s):
    if s not in _AS:
        try:
            r = M.animset(s); _AS[s] = OD([('anim_set', s), ('anim_gltf', r.get('gltf_anim')), ('clips', [q['name'] for q in r.get('sequences') or []])])
        except Exception as x: _AS[s] = OD([('anim_set', s), ('anim_gltf', None), ('clips', []), ('error', repr(x)[:160])])
    return _AS[s]

def group_animsets(idata, name):
    for c in A.children(idata):
        if 'Group' in (c.get('class') or '') and A.values(c['opath']).get('GroupName') == name:
            return [s for s in A.values(c['opath']).get('GroupAnimSets') or [] if s]
    return []

def skel_component(actor):
    v = A.values(actor)
    for k in ('SkeletalMeshComponent', 'SkelMeshComp', 'Mesh'):
        c = v.get(k)
        if isinstance(c, str) and A.get(c) and (A.get(c)['class'] or '').endswith('SkeletalMeshComponent'): return c
    for c in A.children(actor):
        if (c.get('class') or '').endswith('SkeletalMeshComponent'): return c['opath']
    return None

def clip_map(sets, clips):
    cm, miss = OD(), []
    for c in clips:
        f = next((s['anim_gltf'] for s in sets if c in s['clips']), None)
        if f: cm[c] = f
        else: miss.append(c)
    return cm, miss

def main(ch):
    mt = json.load(open(os.path.join(AT, 'manifests', 'next_map', ch + '_matinee.json'), encoding='utf-8'))
    rows, pawn_groups, why = OD(), [], Counter()
    for m in mt['matinees']:
        idata = m['interp_data']
        for g in m['groups']:
            clips = [k['anim'] for t in g['tracks'] if t.get('class') == 'InterpTrackAnimControl' for k in t.get('keys') or [] if k.get('anim')]
            if not clips: continue
            gsets = group_animsets(idata, g['name']); clips = list(OD.fromkeys(clips))
            acts = [a for b in (g.get('bound') or {}).values() for a in (b or {}).get('actors', [])]
            static = [a for a in acts if not a.startswith(RUNTIME) and A.get(a)]
            skel = [a for a in static if 'SkeletalMesh' in (A.get(a)['class'] or '')]
            others = [a for a in acts if a not in skel]
            if others or not acts:
                sets = [animset(s) for s in gsets]; cm, miss = clip_map(sets, clips)
                pawn_groups.append(OD([('interp_data', idata), ('sublevel', m.get('sublevel')), ('group', g['name']), ('binding', g.get('binding')),
                                       ('bound', others), ('bound_classes', {a: (A.get(a) or {}).get('class') for a in others if A.get(a)}),
                                       ('clips', clips), ('anim_sets', sets), ('clip_map', cm), ('clips_missing', miss)]))
                why['pawn_or_runtime_groups'] += 1
            for a in skel:
                if a not in rows:
                    r = A.get(a); own = r.get('props') or {}; comp = skel_component(a); cv = A.values(comp) if comp else {}
                    skm = cv.get('SkeletalMesh'); L = own.get('Location'); R = own.get('Rotation') or {}
                    rows[a] = OD([('actor', a.rsplit('.', 1)[-1]), ('object', a), ('class', r['class']), ('sublevel', a.split('.')[0]),
                                  ('location_ue', L), ('location_gltf', [round(0.01 * L['X'], 4), round(0.01 * L['Z'], 4), round(0.01 * L['Y'], 4)] if L else None),
                                  ('rotation_deg', OD((k.lower(), round(R.get(k, 0) * DEG, 3)) for k in ('Yaw', 'Pitch', 'Roll'))),
                                  ('DrawScale', A.values(a).get('DrawScale')), ('DrawScale3D', A.values(a).get('DrawScale3D')),
                                  ('component', comp), ('mesh', skm), ('mesh_gltf', M.gltf(skm) if skm else None),
                                  ('component_anim_sets', [s for s in cv.get('AnimSets') or [] if s]), ('group_anim_sets', []), ('uses', [])])
                rw = rows[a]
                for s in gsets:
                    if s not in rw['group_anim_sets']: rw['group_anim_sets'].append(s)
                rw['uses'].append(OD([('interp_data', idata), ('group', g['name']), ('clips', clips)]))
                why['skeletal_bindings'] += 1
    for rw in rows.values():
        sets = [animset(s) for s in rw['component_anim_sets'] + rw['group_anim_sets']]
        clips = list(OD.fromkeys(c for u in rw['uses'] for c in u['clips']))
        cm, miss = clip_map(sets, clips)
        rw['anim_sets'] = sets; rw['anim_files'] = sorted({s['anim_gltf'] for s in sets if s['anim_gltf']}); rw['clip_map'] = cm; rw['clips_missing'] = miss
    out = OD([('chapter', ch), ('generated_by', 'AssetTools/work/campaign_render/campaign_matinee_skeletal.py'),
              ('source', 'manifests/next_map/%s_matinee.json + authored.db + content anim glTF (mp_roster.animset)' % ch),
              ('units', 'location_gltf metres Y-up = 0.01 * (X, Z, Y)_UE; rotation_deg = UE rotator * 360 / 65536 (UE signs)'),
              ('counts', OD([('skeletal_actors', len(rows)), ('pawn_or_runtime_groups', len(pawn_groups)),
                             ('actors_without_mesh_gltf', sum(1 for r in rows.values() if not r['mesh_gltf'])),
                             ('clips_missing', sum(len(r['clips_missing']) for r in rows.values()) + sum(len(p['clips_missing']) for p in pawn_groups)),
                             ('by_class', OD(Counter(r['class'] for r in rows.values()).most_common()))] + list(why.items()))),
              ('rows', list(rows.values())), ('pawn_groups', pawn_groups)])
    json.dump(out, open(os.path.join(CR.OUTR, ch, 'matinee_skeletal.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['counts']))

if __name__ == '__main__':
    main(sys.argv[1])
