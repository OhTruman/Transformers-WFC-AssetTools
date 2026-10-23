#!/usr/bin/env bash
# Campaign AI bodies (Gameplay / Integration 2026-10-23): roster -> one bounded build.py character process per template in roster order
# (D5 first, then play order) -> index. Output: AssetTools/out/campaign_characters/<id>/ (the escalation_characters layout).
cd "/f/Transformers Rebuild/AssetTools" || exit 1
PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; W=work/campaign_characters; mkdir -p $W/logs
export PYTHONDONTWRITEBYTECODE=1 WFC_CHAR_OUT="F:\\Transformers Rebuild\\AssetTools\\out\\campaign_characters"
export WFC_ROSTER_JSON="F:\\Transformers Rebuild\\AssetTools\\work\\campaign_characters\\roster.json"
$PY $RB --cap-gb 6 --log $W/logs/roster.log $W/roster.py >/dev/null 2>&1
grep -o '"template": "[^"]*_AICD", *$\|"id": "[^"]*"' $W/roster.json > /dev/null
$PY -c "import json;[print(r['template'],r['id']) for r in json.load(open(r'$W/roster.json',encoding='utf-8'))['templates'] if r.get('chassis')]" > $W/logs/todo.txt
while read -r T ID; do
  if ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1; then echo "PERF_HOLD: stopping before $ID"; exit 75; fi
  WFC_CHAR_ID=$ID $PY $RB --cap-gb 6 --log $W/logs/c_$ID.log work/escalation_characters/build.py character "$T" >/dev/null 2>&1
  echo "$ID $(grep -o 'rc=[0-9]*' $W/logs/c_$ID.log)"
done < $W/logs/todo.txt
# the AI weapons (action set + overrides) not already exported as an MP weapon (ExtractedAssets/VerticalSlice/Weapons) or an Escalation one
$PY -c "
import json, os
R = json.load(open(r'$W/roster.json', encoding='utf-8'))['templates']; ws = []
for r in R:
    for w in [x['class'] for x in r.get('weapon_classes') or []] + [x['class'] for x in r.get('action_weapon_classes') or []]:
        if w not in ws: ws.append(w)
have = set(os.listdir(r'F:/Transformers Rebuild/ExtractedAssets/VerticalSlice/Weapons')) | set(os.listdir('out/escalation_characters/weapons'))
for w in ws:
    pid = w.split('.')[-1].replace('TnWeapon', '')
    if pid not in have: print(w, pid)" > $W/logs/weapons_todo.txt
while read -r WC PID; do
  if ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1; then echo "PERF_HOLD: stopping before $PID"; exit 75; fi
  [ -f "out/campaign_characters/weapons/$PID/weapon.json" ] && { echo "w $PID exists"; continue; }
  $PY $RB --cap-gb 6 --log $W/logs/w_$PID.log work/escalation_characters/build.py weapon "$WC" >/dev/null 2>&1
  echo "w $PID $(grep -o 'rc=[0-9]*' $W/logs/w_$PID.log)"
done < $W/logs/weapons_todo.txt
$PY $RB --cap-gb 6 --log $W/logs/campaign_weapons.log $W/campaign_weapons.py >/dev/null 2>&1
$PY $RB --cap-gb 6 --log $W/logs/index.log work/escalation_characters/build.py index >/dev/null 2>&1
echo "no chassis: $($PY -c "import json;print([r['template'] for r in json.load(open(r'$W/roster.json',encoding='utf-8'))['templates'] if not r.get('chassis')])")"
