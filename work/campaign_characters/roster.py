"""Campaign AI character roster (Gameplay / Integration 2026-10-23): every AiCharacterDefinitionTemplate a campaign TnActorFactoryAI names
(manifests/next_map/<CH>_pawn_factories.json), D5 first (OmegaSupreme / Soldier_Jet_Autobot), then play order. Same per-template record as
the Escalation roster (work/escalation_roster/roster.py template(): chassis ROBODEF -> meshes, anim sets, vehicle form, weapons, FX, cues).
Campaign templates are distinct objects from the Escalation ones even where the names match (TR_AiCharacterDefinition_p vs
TR_AiEscalation_p), so each gets its own id: the template name without _AICD, plus the package when two packages share a name.
Writes work/campaign_characters/roster.json (+ ids, first chapter, factory count). Read only.
"""
import json, os, sys
from collections import OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'work', 'escalation_roster'))
import roster as ER  # noqa: E402  (module import only: its main() is not run)
ORDER = ['D5_OME', 'A1_IAC', 'A2_KON', 'A3_COR', 'A4_ORB', 'A5_TRY', 'D1_ORB', 'D2_COR', 'D3A_IAC', 'D3B_IAC']

def main():
    seen, blueprints = OD(), OD()
    for ch in ORDER:
        p = os.path.join(ROOT, 'manifests', 'next_map', ch + '_pawn_factories.json')
        if not os.path.exists(p): continue
        for f in json.load(open(p, encoding='utf-8'))['pawn_factories']:
            fac = f.get('factory') or {}
            t = fac.get('AiCharacterDefinitionTemplate') or (fac.get('archetype') if fac.get('class') == 'TnActorFactoryAI' else None)
            if fac.get('Blueprint'):
                b = blueprints.setdefault(fac['Blueprint'], OD([('blueprint', fac['Blueprint']), ('factory_class', fac.get('class')),
                                                                 ('actor_class', fac.get('NewActorClass')), ('chapters', []), ('factories', 0)]))
                b['factories'] += 1
                if ch not in b['chapters']: b['chapters'].append(ch)
            elif t:
                r = seen.setdefault(t, OD([('template', t), ('first_chapter', ch), ('chapters', []), ('factories', 0)]))
                r['factories'] += 1
                if ch not in r['chapters']: r['chapters'].append(ch)
    names = {}
    for t in seen: names.setdefault(t.split('.')[-1], []).append(t)
    rows = []
    for t, info in seen.items():
        n = t.split('.')[-1].replace('_AICD', '')
        cid = n if len(names[t.split('.')[-1]]) == 1 else '%s__%s' % (n, t.split('.')[0])
        rec = ER.template(t); rec.update(OD([('id', cid)] + list(info.items())[1:]))
        rows.append(rec)
    json.dump(OD([('generated_by', 'AssetTools/work/campaign_characters/roster.py'), ('order', ORDER), ('templates', rows),
                  ('destructible_blueprints', list(blueprints.values()))]),
              open(os.path.join(HERE, 'roster.json'), 'w', encoding='utf-8'), indent=1)
    for r in rows:
        print('%-40s %-14s %3d fac  chassis=%s veh=%s mesh_ext=%s' % (r['id'], r['first_chapter'], r['factories'], (r.get('chassis') or '-').split('.')[-1],
              (r.get('vehicle_form') or '-').split('.')[-1], bool((r.get('robot_mesh') or {}).get('extracted'))))
    print('blueprints', [(b['blueprint'], b['factories']) for b in blueprints.values()])

if __name__ == '__main__':
    main()
