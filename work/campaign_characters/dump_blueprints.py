"""Raw dump of the campaign destructible blueprints (roster.json destructible_blueprints) and every object under them / they reference
(2 hops), from authored.db, so the spawnable-destructible export can be written against the real structure. Read only ->
work/campaign_characters/blueprints_raw.json."""
import json, os, re, sqlite3
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
DB = sqlite3.connect(os.path.join(AT, 'manifests', 'authored.db'))
bps = [b['blueprint'] for b in json.load(open(os.path.join(HERE, 'roster.json'), encoding='utf-8'))['destructible_blueprints']]
out = {}
for bp in bps:
    objs, front = {}, [bp]
    for o, c, p in DB.execute('select opath, class, props from objects where opath like ?', (bp + '.%',)): objs[o] = {'class': c, 'props': json.loads(p or '{}')}
    for hop in range(2):
        nxt = []
        for o in front:
            r = DB.execute('select class, props from objects where opath=?', (o,)).fetchone()
            if not r: continue
            objs.setdefault(o, {'class': r[0], 'props': json.loads(r[1] or '{}')})
            for m in set(re.findall(r'"([A-Za-z0-9_]+\.[A-Za-z0-9_.]+)"', r[1] or '')):
                if m not in objs: nxt.append(m)
        front = nxt
    out[bp] = objs
json.dump(out, open(os.path.join(HERE, 'blueprints_raw.json'), 'w', encoding='utf-8'), indent=1)
print({k: len(v) for k, v in out.items()})
