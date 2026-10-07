"""Authored MP progression tables (unlocks, challenges, XP, killstreaks, skills) -> manifests/mp_content/progression.json

  python progression.py

Source (CONFIRMED, cooked Xbox 360 config decoded by coalesced.py; values verbatim, multi-valued keys kept as lists):
  TransCustomization.ini  [<Id> TnDataProvider_{Ability,Chassis,Killstreak,Skill,Specialty}]  (unlock level / specialty restrictions)
  TransChallenges.ini     [<Id> TnDataProvider_Challenge]  (ChallengeId, StatPropertyId, GoalValues[], XpRewardValues[])
  Xe-TransGame.ini        [TransGame.TnXpManager] (LevelTable[]), [TransGame.TnXpEventType*] (XpAmount ...),
                          [TransGame.TnCharacterCustomizationData], kill-award / multikill settings
  TransGame.int / .FRA    localized FriendlyName / ChallengeName / Description per provider section
Runtime semantics (level = thresholds passed, per-specialty XP, award rules) are RE's: notes/MP_PROGRESSION_SCORING_AI_2026-10-06.md.
"""
import json, os, re, sys, time
from collections import OrderedDict as OD

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coalesced as C  # noqa: E402

AT = os.path.normpath(os.path.join(HERE, '..', '..'))
CFG = os.path.join(C.OUT, 'Coalesced_ini', 'TransGame', 'Config', 'Xenon', 'Cooked')
LOC = {'INT': os.path.join(C.OUT, 'Coalesced_int', 'TransGame', 'Localization', 'INT', 'TransGame.int'),
       'FRA': os.path.join(C.OUT, 'Coalesced_FRA', 'TransGame', 'Localization', 'FRA', 'TransGame.fra')}
XP_SECTIONS = re.compile(r'^TransGame\.(TnXp\w*|TnCharacterCustomizationData|TnKillAward\w*|TnGameRules_TrackKillsMP|TnStatistics\w*Xp\w*)$')

def ini(path):
    if not os.path.exists(path): return {}
    raw = open(path, 'rb').read()
    try: txt = raw.decode('utf-8')
    except UnicodeDecodeError: txt = raw.decode('cp1252')   # localized .FRA text is Windows-1252
    return C.parse_ini(txt)

def flat(kv):
    return OD((k, v[0] if len(v) == 1 else v) for k, v in kv.items())

def num(v):
    if isinstance(v, list): return [num(x) for x in v]
    if isinstance(v, str):
        try: return int(v, 0) if re.match(r'^-?(0x[0-9a-fA-F]+|\d+)$', v) else float(v) if re.match(r'^-?\d+\.\d*$', v) else v
        except ValueError: return v
    return v

def main():
    loc = {lang: ini(p) for lang, p in LOC.items()}
    providers = OD()
    for fn in ('TransCustomization.ini', 'TransChallenges.ini'):
        for sec, kv in ini(os.path.join(CFG, fn)).items():
            m = re.match(r'^(\S+) (TnDataProvider_\w+)$', sec)
            if not m: continue
            pid, kind = m.group(1), m.group(2).replace('TnDataProvider_', '')
            rec = OD((k, num(v)) for k, v in flat(kv).items())
            for lang, L in loc.items():
                t = L.get(sec)
                if t: rec['loc_' + lang] = flat(t)
            providers.setdefault(kind, OD())[pid] = rec
    game = ini(os.path.join(CFG, 'Xe-TransGame.ini'))
    xp = OD((sec, OD((k, num(v)) for k, v in flat(kv).items())) for sec, kv in game.items() if XP_SECTIONS.match(sec))
    lt = (xp.get('TransGame.TnXpManager') or {}).get('LevelTable') or []
    out = OD([('generated_by', 'AssetTools/scripts/wfc/progression.py'), ('generated', time.strftime('%Y-%m-%d %H:%M')),
              ('source', 'cooked Coalesced.ini / Coalesced.int (Xbox 360), decoded; values verbatim (CONFIRMED authored data)'),
              ('semantics', 'RE notes/MP_PROGRESSION_SCORING_AI_2026-10-06.md (+ notes/data/mp_*.json): per-specialty XP and level '
                            '0..25 = number of LevelTable thresholds <= XP; challenge tiers = GoalValues[i] -> XpRewardValues[i]'),
              ('providers', providers), ('xp_config', xp),
              ('summary', OD([('providers', {k: len(v) for k, v in providers.items()}), ('level_table_thresholds', len(lt) if isinstance(lt, list) else 1),
                              ('max_level_xp', lt[-1] if isinstance(lt, list) and lt else lt), ('xp_sections', len(xp))]))])
    json.dump(out, open(os.path.join(AT, 'manifests', 'mp_content', 'progression.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(json.dumps(out['summary']))

if __name__ == '__main__':
    main()
