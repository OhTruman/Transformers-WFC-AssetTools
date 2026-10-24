"""District's new Escalation enemy (RE / Gameplay / Integration 2026-10-23): TR_District_p.AiEscalation_Soldier_Jet_Autobot_AICD, an Autobot
copy of Soldier_Jet_Decepticon on the base chassis TR_SoldierJetAut_ROBODEF_p. Builds its roster record with the Escalation roster's
template() (the DLC authored.db attached behind the base one on the roster's own connection) -> work/dlc/esc_roster_dlc.json; then
    WFC_ROSTER_JSON=<that> python work/escalation_characters/build.py character AiEscalation_Soldier_Jet_Autobot_AICD
writes out/escalation_characters/AiEscalation_Soldier_Jet_Autobot (the escalation_characters layout), and build.py index adds its row.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); AT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(AT, 'work', 'escalation_roster'))
import roster as ER  # noqa: E402
DLC = os.path.join(AT, 'manifests', 'dlc', 'authored.db')
ER.DB.execute("ATTACH DATABASE ? AS xdb", (DLC,))   # the roster's connection is not URI-mode: plain path (read only by use)
for t in ('objects', 'refs'):
    ER.DB.execute('CREATE TEMP VIEW %s AS SELECT * FROM main.%s UNION ALL SELECT * FROM xdb.%s' % (t, t, t))
T = 'TR_District_p.AiEscalation_Soldier_Jet_Autobot_AICD'
rec = ER.template(T)
# its weapons come from the AI action set (as the campaign templates; the roster's override rule finds none): the campaign roster's
# action_weapons() on this same (DLC-attached) connection
sys.path.insert(0, os.path.join(AT, 'work', 'campaign_characters'))
import importlib.util as _u
_s = _u.spec_from_file_location('campaign_roster', os.path.join(AT, 'work', 'campaign_characters', 'roster.py')); CRO = _u.module_from_spec(_s); _s.loader.exec_module(CRO)
rec['action_weapon_classes'] = CRO.action_weapons(T)
print('action weapons', [(w['class'].split('.')[-1], len(w['actions'])) for w in rec['action_weapon_classes']])
print({k: rec.get(k) for k in ('template', 'class', 'chassis', 'vehicle_form')}, 'weapons', [w['class'] for w in rec.get('weapon_classes') or []])
json.dump({'generated_by': 'AssetTools/work/dlc/esc_jet_autobot.py', 'templates': [rec]}, open(os.path.join(HERE, 'esc_roster_dlc.json'), 'w', encoding='utf-8'), indent=1)
