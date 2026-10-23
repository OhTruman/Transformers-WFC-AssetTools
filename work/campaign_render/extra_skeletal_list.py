"""Undrawn skeletal world actors -> manifests/campaign/extra_skeletal_actors.json (Integration go 2026-10-23): per chapter, every placed
*SkeletalMeshActor* (SkeletalMeshActor, HmSkeletalMeshActor, HmLightMappedSkeletalMeshActor, SkeletalMeshActorMAT ...) that is NOT
  - in the chapter's matinee_skeletal.json (Gameplay poses those),
  (sentry spawn-point bodies ARE included: Gameplay only toggles their visibility; counted as of_which_sentry_body)
  - a TnTransformingWorldActor (its own class; already drawn by add_transforming_actors.py).
add_transforming_actors.py then draws them at bind pose. Each run rewrites the listed chapters (fresh, not merged).
    python extra_skeletal_list.py CH [CH ...]
"""
import json, os, sqlite3, sys
from collections import Counter, OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..')); sys.path.insert(0, HERE)
import campaign_render as CR  # noqa: E402
INV = sqlite3.connect(os.path.join(AT, 'manifests', 'inventory.db'))
EP = os.path.join(AT, 'manifests', 'campaign', 'extra_skeletal_actors.json')

def main(chs):
    cur = json.load(open(EP, encoding='utf-8')) if os.path.exists(EP) else {'chapters': {}}
    sp = json.load(open(os.path.join(AT, 'out', 'campaign_characters', 'spawnables.json'), encoding='utf-8'))
    sentry = {b['object'] for s in sp['sentries'] for f in s['factories'] for b in f['spawn_points']}
    for ch in chs:
        lv = CR.chapter_levels(ch); ph = ','.join('?' * len(lv))
        sk = [(o, c) for o, c in INV.execute("select distinct opath, class from exports where package in (%s) and class like '%%SkeletalMeshActor%%'" % ph, lv)
              if o.count('.') == 3 and '.TheWorld.PersistentLevel.' in o]
        mp = os.path.join(CR.OUTR, ch, 'matinee_skeletal.json')
        mat = {r['object'] for r in json.load(open(mp, encoding='utf-8'))['rows']} if os.path.exists(mp) else set()
        why = Counter(); keep = []
        for o, c in sorted(sk):
            # Integration correction 2026-10-23: sentry spawn-point bodies are drawn too (Gameplay only toggles them with setActorHidden)
            if o in mat: why['matinee_driven'] += 1
            else:
                keep.append(o); why['added'] += 1
                if o in sentry: why['of_which_sentry_body'] += 1
        cur['chapters'][ch] = sorted(set(keep))
        print(ch, dict(why), 'listed', len(cur['chapters'][ch]))
    cur['note'] = ('skeletal world actors that are neither TnTransformingWorldActor nor matinee-driven (sentry bodies included), drawn at bind '
                   'pose by add_transforming_actors.py (Integration go 2026-10-23; extra_skeletal_list.py)')
    json.dump(cur, open(EP, 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    main(sys.argv[1:])
