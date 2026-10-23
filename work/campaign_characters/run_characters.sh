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
$PY $RB --cap-gb 6 --log $W/logs/index.log work/escalation_characters/build.py index >/dev/null 2>&1
echo "no chassis: $($PY -c "import json;print([r['template'] for r in json.load(open(r'$W/roster.json',encoding='utf-8'))['templates'] if not r.get('chassis')])")"
