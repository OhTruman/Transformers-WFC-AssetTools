"""Broad-coverage index of high-value assets for the reconstruction.

Heuristic, name/structure based (not identity-proven).  Output:
  AssetTools/manifests/high_value.json
  AssetTools/docs/HIGH_VALUE_ASSETS.md
"""
import json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract  # noqa: E402

MANI = extract.MANI
DOCS = os.path.join(os.path.dirname(MANI), 'docs')

MOVE = re.compile(r'(^|_)(nav|run|walk|jog|sprint|jump|land|fall|idle|strafe|dodge|hover|boost|turn|crouch|evade|drive|fly)', re.I)
FIRE = re.compile(r'(fire|shot|shoot|blast|burst|charge|reload|overheat)', re.I)

def main():
    A = json.load(open(os.path.join(MANI, 'assets.json'), encoding='utf-8'))['assets']
    maps = json.load(open(os.path.join(MANI, 'maps.json'), encoding='utf-8'))
    by = defaultdict(list)
    for a in A: by[a['class']].append(a)
    first = lambda a, ext: next((o for o in a['extracted'] if o.endswith(ext)), None)

    # --- playable / named transformers: TR_<Name>_ROBO_p + TR_<Name>_VEH_p
    chars = defaultdict(lambda: {'robot_meshes': [], 'vehicle_meshes': [], 'weapon_arm_meshes': [],
                                 'animsets': [], 'transform_sequences': [], 'textures': 0, 'sound_packages': []})
    for a in by['SkeletalMesh']:
        m = re.match(r'TR_([A-Za-z]+)_(ROBO|VEH)_p$', a['original_package'])
        if not m: continue
        c = chars[m.group(1)]
        entry = {'object': a['object_path'], 'gltf': first(a, '.gltf'),
                 'bones': a.get('skeleton', {}).get('bone_count'), 'map_usage': len(a['map_usage'])}
        if 'WeaponArm' in a['object_name'] or 'Arm_' in a['object_name']: c['weapon_arm_meshes'].append(entry)
        elif m.group(2) == 'ROBO': c['robot_meshes'].append(entry)
        else: c['vehicle_meshes'].append(entry)
    for a in by['Texture2D']:
        m = re.match(r'TR_([A-Za-z]+)_(ROBO|VEH)_p$', a['original_package'])
        if m and m.group(1) in chars: chars[m.group(1)]['textures'] += 1
    mesh_owner = {}
    for n, c in chars.items():
        for e in c['robot_meshes'] + c['vehicle_meshes']: mesh_owner[e['object']] = n
    for a in by['AnimSet']:
        pv = a.get('preview_skeletal_mesh')
        n = mesh_owner.get(pv)
        if not n: continue
        seqs = a.get('sequences', [])
        chars[n]['animsets'].append({'object': a['object_path'], 'anim_gltf': (first(a, '.psa') or '')[:-4] + '.anim.gltf' if first(a, '.psa') else None,
                                     'sequences': len(seqs)})
        chars[n]['transform_sequences'] += [s['name'] for s in seqs if s.get('name') and 'transform' in s['name'].lower()]
    pkgs = {a['original_package'] for a in A}
    for n, c in chars.items():
        c['sound_packages'] = sorted(p for p in pkgs if re.search(r'(^|_)%s($|_)' % re.escape(n.upper()), p.upper())
                                     and p.startswith(('WL_', 'BL_')))
        c['transform_sequences'] = sorted(set(c['transform_sequences']))
    def rank(e):   # visual meshes first; collision hulls, cine and part (CP_) meshes last
        o = e['object'].split('.')[-1].upper()
        return (('HULL' in o) + ('CINE' in o) + o.startswith('CP_') + ('_STAT' in o), -(e['bones'] or 0))
    for c in chars.values():
        c['robot_meshes'].sort(key=rank); c['vehicle_meshes'].sort(key=rank)
    playable = {n: c for n, c in chars.items() if c['robot_meshes'] and c['vehicle_meshes']}

    # --- transformation & movement animations (all sets)
    transform, movement = [], []
    for a in by['AnimSet']:
        for s in a.get('sequences', []):
            nm = s.get('name') or ''
            rec = {'sequence': nm, 'animset': a['object_path'], 'frames': s.get('frames'), 'length_s': s.get('length'),
                   'preview_mesh': a.get('preview_skeletal_mesh')}
            if 'transform' in nm.lower(): transform.append(rec)
            elif MOVE.search(nm) and not nm.upper().startswith(('CINE', 'VIG')): movement.append(rec)

    # --- weapons
    weapons = defaultdict(lambda: {'meshes': [], 'textures': 0, 'materials': 0})
    for a in A:
        m = re.match(r'WEP_([A-Za-z0-9]+?)(_AI)?_p$', a['original_package'])
        if not m: continue
        w = weapons[m.group(1)]
        if a['class'] in ('SkeletalMesh', 'StaticMesh'):
            w['meshes'].append({'object': a['object_path'], 'class': a['class'], 'gltf': first(a, '.gltf')})
        elif a['class'] == 'Texture2D': w['textures'] += 1
        elif a['asset_type'] in ('material', 'material_instance'): w['materials'] += 1
    weapons = {k: v for k, v in weapons.items() if v['meshes']}

    # --- sounds
    waves = by['SoundNodeWaveEx'] + by['SoundNodeWave']
    def snd(a): return {'object': a['object_path'], 'wav': first(a, '.wav')}
    weapon_fire = [snd(a) for a in waves if a['original_package'].startswith(('WL_GUN', 'WL_WPN')) and FIRE.search(a['object_name'])]
    weapon_all = [a for a in waves if a['original_package'].startswith(('WL_GUN', 'WL_WPN'))]
    footsteps = [snd(a) for a in waves if a['original_package'].startswith('WL_FS') or re.search(r'(^|_)(FS|FOOTSTEP)', a['object_name'], re.I)]
    transform_snd = [snd(a) for a in waves if a['original_package'].startswith('WL_TRANS')]
    music = [snd(a) for a in waves if a['original_package'].startswith('WL_MX')]
    dialog = [a for a in waves if a['original_package'].startswith('WL_DX')]

    # --- multiplayer maps
    mp = defaultdict(list)
    for m in maps:
        if m['map'].startswith('MP_'):
            key = '_'.join(m['map'].split('_')[:3])
            mp[key].append({'package': m['map'], 'actors': m['actors'], 'asset_refs': m['asset_refs'],
                            'json': 'maps/%s.json' % m['map']})

    # --- environment materials/textures and UI
    env_tex = defaultdict(int)
    for a in by['Texture2D']:
        if a['original_package'].startswith(('ENV_', 'TPRO_', 'PROP_')): env_tex[a['original_package']] += 1
    ui = [{'object': a['object_path'], 'class': a['class'], 'file': (a['extracted'] or [None])[0]}
          for a in by['GFxMovieInfo'] + by['SwfMovie']]
    hud_tex = [a['object_path'] for a in by['Texture2D'] if a['original_package'].startswith('UI_')]

    hv = {
        'note': 'Heuristic name/structure-based selection; identities not individually verified.',
        'playable_transformers': dict(sorted(playable.items())),
        'other_characters': sorted(n for n in chars if n not in playable),
        'transformation_animations': transform, 'player_movement_animations': movement,
        'player_weapons': dict(sorted(weapons.items())),
        'weapon_fire_sounds': weapon_fire, 'weapon_sound_total': len(weapon_all),
        'footstep_sounds': footsteps, 'transformation_sounds': transform_snd,
        'music': music, 'dialog_wave_count': len(dialog),
        'multiplayer_maps': dict(sorted(mp.items())),
        'environment_texture_packages': dict(sorted(env_tex.items(), key=lambda kv: -kv[1])),
        'ui_movies': ui, 'ui_texture_count': len(hud_tex),
    }
    json.dump(hv, open(os.path.join(MANI, 'high_value.json'), 'w'), indent=1)

    L = ['# High-value assets (first pass)', '',
         '_Generated by `scripts/wfc/high_value.py` from `manifests/assets.json`. Heuristic, name-based; identities are not individually verified._', '',
         '## Playable/named Transformers with robot + vehicle meshes (%d)' % len(playable), '',
         '| Character | Robot mesh | Vehicle mesh | Bones | AnimSets | Transform seqs | Textures |', '|---|---|---|---|---|---|---|']
    for n, c in sorted(playable.items()):
        L.append('| %s | `%s` | `%s` | %s | %d | %d | %d |' % (
            n, c['robot_meshes'][0]['object'].split('.')[-1], c['vehicle_meshes'][0]['object'].split('.')[-1],
            c['robot_meshes'][0]['bones'], len(c['animsets']), len(c['transform_sequences']), c['textures']))
    L += ['', 'Other character packages (robot or vehicle only / NPC variants): ' + ', '.join(hv['other_characters']), '',
          '## Animations', '', '- Transformation sequences: **%d**' % len(transform),
          '- Player movement sequences (nav/run/jump/hover/boost/...): **%d**' % len(movement), '',
          'Examples: ' + ', '.join(sorted({t['sequence'] for t in transform})[:25]), '',
          '## Player weapons with meshes (%d)' % len(weapons), '', ', '.join(sorted(weapons)), '',
          '## Sounds', '', '- Weapon sounds (WL_GUN*/WL_WPN*): **%d** (fire/shot/reload-named: %d)' % (len(weapon_all), len(weapon_fire)),
          '- Footsteps: **%d**' % len(footsteps), '- Transformation sounds (WL_TRANS*): **%d**' % len(transform_snd),
          '- Music (WL_MX*): **%d**' % len(music), '- Dialog waves (WL_DX*): **%d**' % len(dialog), '',
          '## Multiplayer maps (%d)' % len(mp), '', '| Map | Sub-level packages | Placed actors |', '|---|---|---|']
    for k, v in sorted(mp.items()):
        L.append('| %s | %s | %d |' % (k, ', '.join(x['package'] for x in v), sum(x['actors'] for x in v)))
    L += ['', '## Environment texture packages (top 15)', '']
    for k, v in list(hv['environment_texture_packages'].items())[:15]: L.append('- %s: %d textures' % (k, v))
    L += ['', '## UI', '', '- Scaleform movies: %d (exported as .gfx)' % len(ui), '- UI textures: %d' % len(hud_tex), '']
    os.makedirs(DOCS, exist_ok=True)
    open(os.path.join(DOCS, 'HIGH_VALUE_ASSETS.md'), 'w', encoding='utf-8').write('\n'.join(L))
    print('playable', len(playable), 'transform seqs', len(transform), 'movement', len(movement), 'weapons', len(weapons),
          'fire sounds', len(weapon_fire), 'footsteps', len(footsteps), 'mp maps', len(mp), 'ui', len(ui))

if __name__ == '__main__':
    main()
