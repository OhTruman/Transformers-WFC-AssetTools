"""Campaign pawn factories that spawn something other than an AI character (Gameplay 2026-10-23: A2's sentry factories held):
  TnActorFactorySentryAI (138, 11 TURRETDEFs): a TnSentry archetype (MaxAttackRange, WeaponClass, TurretPieceName, WeaponSocketName ...)
     spawned ON its spawn point, a placed SkeletalMeshActor (the turret body: mesh glTF, transform; whether its glTF has the turret piece /
     weapon socket bones); the weapon: class CDO data objects + effective AiData / PlayerData values (and weapon.json where exported)
  TnActorFactoryRollerMine (46): TransGame.TnRollerMine class default (components: meshes as content glTF) + the factory's authored values
  (TnActorFactorySpawnableDestructible: the battery blueprints -> destructibles/, already exported)
Read only -> out/campaign_characters/spawnables.json (+ the sentry weapons to export, printed).
"""
import glob, json, os, re, sys
from collections import Counter, OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(AT)
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
import authored as A, mp_roster as M  # noqa: E402
DEG = 360.0 / 65536.0

def eff(o): return OD(sorted(A.values(o).items())) if o and A.get(o) else None

def weapon(cls):
    pk, c = cls.split('.', 1); cdo = '%s.Default__%s' % (pk, c); v = A.values(cdo) if A.get(cdo) else {}
    pid = c.replace('TnWeapon', '')
    wj = next((p for p in (os.path.join(TR, 'ExtractedAssets', 'VerticalSlice', 'Weapons', pid, 'weapon.json'),
                           os.path.join(AT, 'out', 'escalation_characters', 'weapons', pid, 'weapon.json'),
                           os.path.join(AT, 'out', 'campaign_characters', 'weapons', pid, 'weapon.json')) if os.path.exists(p)), None)
    return OD([('class', cls), ('weapon_json', os.path.relpath(wj, TR).replace(os.sep, '/') if wj else None),
               ('WeaponMeshTemplate', v.get('WeaponMeshTemplate')), ('PlayerData', v.get('PlayerData')), ('AiData', v.get('AiData')),
               ('ai_data_values', eff(v.get('AiData'))), ('player_data_values', eff(v.get('PlayerData')) if v.get('PlayerData') != v.get('AiData') else 'same as AiData')])

def body(o):
    v = A.values(o) if A.get(o) else {}
    comp = v.get('SkeletalMeshComponent'); cv = A.values(comp) if comp and A.get(comp) else {}
    skm = cv.get('SkeletalMesh'); gl = M.gltf(skm) if skm else None
    bones = []
    if gl and os.path.exists(os.path.join(TR, 'ExtractedAssets', gl)):
        g = json.load(open(os.path.join(TR, 'ExtractedAssets', gl), encoding='utf-8')); bones = [n.get('name') for n in g.get('nodes') or []]
    L = v.get('Location'); R = v.get('Rotation') or {}
    return OD([('object', o), ('class', (A.get(o) or {}).get('class')), ('location_gltf', [round(0.01 * L['X'], 4), round(0.01 * L['Z'], 4), round(0.01 * L['Y'], 4)] if L else None),
               ('rotation_deg', OD((k.lower(), round(R.get(k, 0) * DEG, 3)) for k in ('Yaw', 'Pitch', 'Roll'))), ('DrawScale', v.get('DrawScale')),
               ('DrawScale3D', v.get('DrawScale3D')), ('mesh', skm), ('mesh_gltf', gl), ('bones', bones)])

def main():
    sentries, mines, weapons = OD(), [], OD()
    for f in sorted(glob.glob(os.path.join(AT, 'manifests', 'next_map', '*_pawn_factories.json'))):
        ch = os.path.basename(f).replace('_pawn_factories.json', '')
        for p in json.load(open(f, encoding='utf-8'))['pawn_factories']:
            fc = (p.get('factory') or {}).get('class')
            if fc == 'TnActorFactorySentryAI':
                t = p['factory'].get('archetype')
                if t not in sentries:
                    v = eff(t) or {}
                    sentries[t] = OD([('turretdef', t), ('class', (A.get(t) or {}).get('class')), ('values', v), ('weapon', None), ('factories', [])])
                    if v.get('WeaponClass'): weapons.setdefault(v['WeaponClass'], None)
                sp = [body(s['object']) for s in p.get('spawn_points') or [] if s.get('object')]
                tp = (sentries[t]['values'] or {}).get('TurretPieceName'); ws = (sentries[t]['values'] or {}).get('WeaponSocketName')
                for b in sp: b['has_turret_piece'] = any(tp and tp.lower() in (x or '').lower() for x in b['bones']); b.pop('bones')
                sentries[t]['factories'].append(OD([('chapter', ch), ('action', p['action']), ('sublevel', p.get('sublevel')), ('sequence', p.get('sequence')),
                                                    ('spawn_points', sp), ('spawn_count', p.get('spawn_count')), ('fired_by_events', p.get('fired_by_events')),
                                                    ('outputs', p.get('outputs'))]))
            elif fc == 'TnActorFactoryRollerMine':
                mines.append(OD([('chapter', ch), ('action', p['action']), ('sublevel', p.get('sublevel')),
                                 ('factory_values', {k: v for k, v in p['factory'].items() if k not in ('object', 'class', 'archetype')}),
                                 ('spawn_points', p.get('spawn_points')), ('fired_by_events', p.get('fired_by_events'))]))
    for w in weapons: weapons[w] = weapon(w)
    for s in sentries.values(): s['weapon'] = weapons.get((s['values'] or {}).get('WeaponClass'))
    rm = 'TransGame.Default__TnRollerMine'; comps = []
    for c in A.children(rm) if A.get(rm) else []:
        cv = A.values(c['opath']); m = cv.get('StaticMesh') or cv.get('SkeletalMesh')
        if m: comps.append(OD([('component', c['opath']), ('class', c['class']), ('mesh', m), ('mesh_gltf', M.gltf(m)), ('Scale', cv.get('Scale')),
                                ('Scale3D', cv.get('Scale3D')), ('Translation', cv.get('Translation'))]))
    out = OD([('generated_by', 'AssetTools/work/campaign_characters/campaign_spawnables.py'),
              ('source', 'manifests/next_map/<CH>_pawn_factories.json + authored.db effective values + content glTF'),
              ('units', 'UE (cm, s) for values; location_gltf metres'),
              ('sentries', list(sentries.values())),
              ('roller_mine', OD([('class', 'TransGame.TnRollerMine'), ('class_defaults', eff(rm)), ('mesh_components', comps), ('factories', mines)])),
              ('weapons', weapons),
              ('spawnable_destructibles', 'the battery blueprints: out/campaign_characters/destructibles/ (campaign_destructibles.py)')])
    json.dump(out, open(os.path.join(AT, 'out', 'campaign_characters', 'spawnables.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print('sentries', [(s['turretdef'].split('.')[-1], len(s['factories'])) for s in sentries.values()])
    print('roller mines', len(mines), 'mesh comps', [(c['mesh'], c['mesh_gltf']) for c in comps])
    print('weapons', [(w.split('.')[-1], bool(r['weapon_json']), bool(r['ai_data_values'])) for w, r in weapons.items()])
    nob = Counter(b['mesh_gltf'] is None for s in sentries.values() for f in s['factories'] for b in f['spawn_points']); print('spawn bodies without glTF', nob[True], 'with', nob[False])

if __name__ == '__main__':
    main()
