"""every actor-keyed world.glb node of a chapter carries extras.actor_path, and it names an actors.json object (or a counted exception)"""
import json, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..')); sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
from vs_common import read_glb  # noqa: E402
for ch in sys.argv[1:]:
    R = os.path.join(AT, 'out', 'campaign_render', ch)
    objs = {r['object'] for r in json.load(open(os.path.join(R, 'actors.json'), encoding='utf-8'))['actors']}
    c = Counter(); ex = []
    for u in sorted(os.listdir(R)):
        g = os.path.join(R, u, 'world.glb')
        if not os.path.exists(g): continue
        j, _ = read_glb(g)
        for n in j.get('nodes', []):
            e = n.get('extras') or {}
            if not e.get('actor'): continue
            if not e.get('actor_path'): c['missing'] += 1
            elif e['actor_path'] in objs: c['ok'] += 1
            else: c['not_in_actors_json'] += 1; ex.append((u, e['actor_path'].rsplit('.', 1)[-1], e.get('class'))) if len(ex) < 4 else None
    print(ch, dict(c), ex)
