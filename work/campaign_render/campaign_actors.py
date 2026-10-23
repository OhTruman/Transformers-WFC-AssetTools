"""Chapter actor table (Gameplay 2026-10-23: the campaign AI ops - MoveToActor, SetMoveToObjective, UseInteract, ShootAtActor, UseTurret -
name actors by object path; navigation.json only covers NavigationPoints). One row per actor of the chapter's levels (every
<level>.TheWorld.PersistentLevel.<actor> export, not the level's components / Model / Polys), read only from manifests/inventory.db + authored.db:
  object (path), class, sublevel, location_ue / location_gltf (0.01 * (X, Z, Y)), rotation_ue (UE rotator units) + rotation_deg
  (yaw / pitch / roll = units * 360 / 65536, UE sign conventions, not converted), DrawScale / DrawScale3D when authored,
  base (Base actor) + base_bone (BaseBoneName) when attached, referenced_by_kismet (a Kismet object under Main_Sequence names it),
  props: for TnInteract* / turrets / pickups / factories, the authored properties (radius, duration, weapon ... as authored);
  hidden: the authored effective bHidden of every actor (hidden ones also as props.bHidden).
Authored values only: an actor with no authored Location has location null (class default = origin; flagged location_default).
    python campaign_actors.py <CH>   -> out/campaign_render/<CH>/actors.json
"""
import json, os, re, sqlite3, sys
from collections import Counter, OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import campaign_render as CR  # noqa: E402
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
import authored as A  # noqa: E402
DB = sqlite3.connect(os.path.join(AT, 'manifests', 'authored.db')); INV = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
KEEP_PROPS = re.compile(r'(Interact|Turret|Pickup|Factory|Weapon|Emote)', re.I)
DEG = 360.0 / 65536.0

def main(ch):
    levels = CR.chapter_levels(ch); ph = ','.join('?' * len(levels))
    exports = INV.execute("select distinct opath, class from exports where package in (%s)" % ph, levels).fetchall()
    actors = [(o, c) for o, c in exports if o.count('.') == 3 and '.TheWorld.PersistentLevel.' in o
              and not (c.endswith('Component') or c in ('Model', 'Polys', 'Sequence', 'Level', 'World'))]   # level-owned objects, not actors
    names = {o.rsplit('.', 1)[-1]: o for o, _ in actors}
    # Kismet references: an authored property of a Kismet object (under a level's Main_Sequence) naming an actor
    refd = set()
    for o, _ in exports:
        if '.PersistentLevel.Main_Sequence' not in o: continue
        r = DB.execute('select props from objects where opath=?', (o,)).fetchone()
        if not r or not r[0]: continue
        for m in re.findall(r'PersistentLevel\.([A-Za-z0-9_]+)', r[0]):
            if m in names: refd.add(names[m])
    rows, by_cls = [], Counter()
    for o, c in sorted(actors):
        r = DB.execute('select props from objects where opath=?', (o,)).fetchone(); p = json.loads((r[0] if r else None) or '{}')
        L = p.get('Location'); R = p.get('Rotation') or {}
        row = OD([('object', o), ('actor', o.rsplit('.', 1)[-1]), ('class', c), ('sublevel', o.split('.')[0]),
                  ('location_ue', L), ('location_gltf', [round(0.01 * L['X'], 4), round(0.01 * L['Z'], 4), round(0.01 * L['Y'], 4)] if L else None)])
        if not L: row['location_default'] = True
        if R: row['rotation_ue'] = R; row['rotation_deg'] = OD((k.lower(), round(R.get(k, 0) * DEG, 3)) for k in ('Yaw', 'Pitch', 'Roll'))
        for k in ('DrawScale', 'DrawScale3D'):
            if k in p: row[k] = p[k]
        if p.get('Base'): row['base'] = p['Base']; row['base_bone'] = p.get('BaseBoneName')
        if o in refd: row['referenced_by_kismet'] = True
        if KEEP_PROPS.search(c):
            row['props'] = {k: v for k, v in p.items() if k not in ('Location', 'Rotation', 'DrawScale', 'DrawScale3D', 'Base', 'BaseBoneName',
                                                                   'Components', 'CollisionComponent', 'Tag', 'Name')}
        # authored EFFECTIVE bHidden (instance, else archetype / class default) on every row; hidden ones also as props.bHidden, the key
        # Gameplay's loader reads (Integration 2026-10-23: A2 set dressing started visible)
        hid = bool(A.values(o).get('bHidden'))
        row['hidden'] = hid
        if hid: row.setdefault('props', {})['bHidden'] = True
        rows.append(row); by_cls[c] += 1
    out = OD([('chapter', ch), ('generated_by', 'AssetTools/work/campaign_render/campaign_actors.py'),
              ('source', 'manifests/inventory.db + authored.db (authored values; cooked levels)'),
              ('units', 'location_gltf metres Y-up = 0.01 * (X, Z, Y)_UE; rotation_deg = UE rotator * 360 / 65536 (UE signs)'),
              ('counts', OD([('actors', len(rows)), ('referenced_by_kismet', len(refd)), ('attached', sum(1 for r in rows if r.get('base'))),
                             ('hidden', sum(1 for r in rows if r.get('hidden'))),
                             ('location_default', sum(1 for r in rows if r.get('location_default')))])),
              ('by_class', OD(by_cls.most_common())), ('actors', rows)])
    json.dump(out, open(os.path.join(CR.OUTR, ch, 'actors.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['counts']), list(out['by_class'].items())[:12])

if __name__ == '__main__':
    main(sys.argv[1])
