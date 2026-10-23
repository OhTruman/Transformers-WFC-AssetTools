"""Campaign AI weapon values (Gameplay 2026-10-23), the campaign counterpart of manifests/escalation/escalation_weapons.json: per weapon class
any campaign AI template uses (roster.json weapon_classes + action_weapon_classes), the weapon CDO's data objects and the effective
authored values of PlayerData (campaign / SP) and AiData, plus where its weapon.json lives (an MP export in VerticalSlice/Weapons, an
Escalation one, or out/campaign_characters/weapons). vs_weapon_export keeps only the PlayerData reference, hence this table. Read only
(authored.db) -> out/campaign_characters/campaign_weapons.json.
"""
import json, os, sys
from collections import OrderedDict as OD
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..')); TR = os.path.dirname(AT)
sys.path.insert(0, os.path.join(AT, 'scripts', 'wfc'))
import authored as A  # noqa: E402
OUT = os.path.join(AT, 'out', 'campaign_characters')

def values(o):
    if not o or not A.get(o): return None
    return OD((k, v.get('value')) for k, v in sorted(A.effective(o).items()))

def where(pid):
    for p in (os.path.join(TR, 'ExtractedAssets', 'VerticalSlice', 'Weapons', pid), os.path.join(AT, 'out', 'escalation_characters', 'weapons', pid),
              os.path.join(OUT, 'weapons', pid)):
        if os.path.exists(os.path.join(p, 'weapon.json')): return os.path.relpath(os.path.join(p, 'weapon.json'), TR).replace(os.sep, '/')
    return None

def main():
    R = json.load(open(os.path.join(HERE, 'roster.json'), encoding='utf-8'))['templates']
    users = OD()
    for r in R:
        for w in r.get('weapon_classes') or []: users.setdefault(w['class'], OD()).setdefault(r['id'], ['override'])
        for w in r.get('action_weapon_classes') or []: users.setdefault(w['class'], OD()).setdefault(r['id'], []).extend(w['actions'])
    rows = OD()
    for cls, u in users.items():
        pk, c = cls.split('.', 1); cdo = '%s.Default__%s' % (pk, c)
        e = A.effective(cdo) if A.get(cdo) else {}
        g = lambda k: (e.get(k) or {}).get('value')
        pid = c.replace('TnWeapon', '')
        rows[pid] = OD([('class', cls), ('weapon_json', where(pid)), ('cdo_found', bool(e)),
                        ('data_objects', OD([('PlayerData', g('PlayerData')), ('AiData', g('AiData')), ('MultiplayerData', g('MultiplayerData')),
                                             ('SurvivalData', g('SurvivalData'))])),
                        ('player_data_values', values(g('PlayerData'))),
                        ('ai_data_values', values(g('AiData')) if g('AiData') != g('PlayerData') else 'same object as PlayerData'),
                        ('used_by', OD((k, sorted(set(v))) for k, v in u.items()))])
    out = OD([('generated_by', 'AssetTools/work/campaign_characters/campaign_weapons.py'),
              ('source', 'manifests/authored.db: weapon CDO -> PlayerData / AiData effective authored values (UE units: cm, s)'),
              ('counts', OD([('weapon_classes', len(rows)), ('with_weapon_json', sum(1 for r in rows.values() if r['weapon_json'])),
                             ('without_player_data', sorted(k for k, r in rows.items() if not r['player_data_values']))])),
              ('weapons', rows)])
    json.dump(out, open(os.path.join(OUT, 'campaign_weapons.json'), 'w', encoding='utf-8'), indent=1, default=str)
    print(json.dumps(out['counts']))

if __name__ == '__main__':
    main()
