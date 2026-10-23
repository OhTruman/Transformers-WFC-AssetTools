"""Checkpoint spawn spots (Gameplay M1, 2026-10-23): per chapter, every Checkpoint / TnCampaignPlayerStart (any *PlayerStart / *Checkpoint
class) with its authored AuxilliarySpawnPoints resolved to actors (class, location_gltf, rotation_deg, Base when attached), plus Tag,
StreamingState, DisplayOrder, Group. Read only (inventory.db / authored.db, effective values). Writes
manifests/next_map/<CH>_checkpoint_spawns.json, and out/campaign_render/<CH>/checkpoint_spawns.json where that chapter dir exists.
    python campaign_checkpoint_spawns.py [<CH> ...]   (default: all 10 chapters)
"""
import json, os, sqlite3, sys
from collections import OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc')); sys.path.insert(0, HERE)
import authored as A  # noqa: E402
import campaign_render as CR  # noqa: E402
INV = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
DEG = 360.0 / 65536.0
CHS = ['D5_OME', 'A1_IAC', 'A2_KON', 'A3_COR', 'A4_ORB', 'A5_TRY', 'D1_ORB', 'D2_COR', 'D3A_IAC', 'D3B_IAC']

def place(o):
    r = A.get(o)
    if not r: return OD([('object', o), ('found', False)])
    v = A.values(o); L = v.get('Location'); R = v.get('Rotation') or {}
    return OD([('object', o), ('actor', o.rsplit('.', 1)[-1]), ('class', r['class']), ('sublevel', o.split('.')[0]), ('location_ue', L),
               ('location_gltf', [round(0.01 * L['X'], 4), round(0.01 * L['Z'], 4), round(0.01 * L['Y'], 4)] if L else None),
               ('rotation_deg', OD((k.lower(), round(R.get(k, 0) * DEG, 3)) for k in ('Yaw', 'Pitch', 'Roll'))),
               ('base', v.get('Base')), ('base_bone', v.get('BaseBoneName'))])

def chapter(ch):
    levels = CR.chapter_levels(ch); ph = ','.join('?' * len(levels))
    objs = sorted({(o, c) for o, c in INV.execute('select distinct opath, class from exports where package in (%s)' % ph, levels)
                   if o.count('.') == 3 and '.TheWorld.PersistentLevel.' in o and ('Checkpoint' in c or 'PlayerStart' in c)})
    rows = []
    for o, c in objs:
        v = A.values(o); row = place(o)
        row.update(OD([('Tag', v.get('Tag')), ('StreamingState', v.get('StreamingState')), ('DisplayOrder', v.get('DisplayOrder')),
                       ('Group', v.get('Group')), ('auxilliary_spawn_points', [place(x) for x in v.get('AuxilliarySpawnPoints') or [] if x])]))
        rows.append(row)
    out = OD([('chapter', ch), ('generated_by', 'AssetTools/work/campaign_render/campaign_checkpoint_spawns.py'),
              ('source', 'manifests/authored.db (effective values; cooked levels)'),
              ('units', 'location_gltf metres Y-up = 0.01 * (X, Z, Y)_UE; rotation_deg = UE rotator * 360 / 65536 (UE signs)'),
              ('counts', OD([('checkpoints_and_starts', len(rows)), ('with_aux_spawn_points', sum(1 for r in rows if r['auxilliary_spawn_points'])),
                             ('aux_spawn_points', sum(len(r['auxilliary_spawn_points']) for r in rows))])),
              ('rows', rows)])
    s = json.dumps(out, indent=1, default=str)
    open(os.path.join(AT, 'manifests', 'next_map', ch + '_checkpoint_spawns.json'), 'w', encoding='utf-8').write(s)
    if os.path.isdir(os.path.join(CR.OUTR, ch)): open(os.path.join(CR.OUTR, ch, 'checkpoint_spawns.json'), 'w', encoding='utf-8').write(s)
    print(ch, json.dumps(out['counts']))

if __name__ == '__main__':
    for ch in sys.argv[1:] or CHS: chapter(ch)
