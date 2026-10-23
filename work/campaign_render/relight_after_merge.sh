#!/usr/bin/env bash
# Rerun one unit's lighting step once Rendering's decal-tail guard (RENDERING_DECAL_TAIL.patch) is on the integration head
# (D1_ORB_Crash2_ART crashed in build_lighting decals(), 2026-10-23). Light job; logs the PARTIAL count Rendering asked for.
#   bash work/campaign_render/relight_after_merge.sh CH SUBLEVEL_m
cd "/f/Transformers Rebuild/AssetTools" || exit 1
CH=$1; SUB=$2; U=${SUB%_m}
until grep -q "unreadable receiver tail" "/f/Transformers Rebuild/Rebuild/tools/render/build_lighting.py"; do sleep 120; done
ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1 && { echo "PERF_HOLD: not rerunning"; exit 75; }
L=out/campaign_render/$CH/$U/_status/lighting_rerun.log
PYTHONDONTWRITEBYTECODE=1 bin/py/python.exe scripts/wfc/run_bounded.py --cap-gb 6 --log $L work/campaign_render/campaign_render.py step $CH $SUB lighting </dev/null >/dev/null 2>&1
echo "$CH $U lighting rerun $(date '+%H:%M'): ok=$(bin/py/python.exe -c "import json;print(json.load(open('out/campaign_render/$CH/$U/_status/lighting.json',encoding='utf-8')).get('ok'))") | $(grep -o 'decals: [0-9]* components with an unreadable receiver tail skipped[^"]*' $L out/campaign_render/$CH/$U/_status/*.log 2>/dev/null | head -1)"
# the unit's lightmaps go through the chapter dedupe again (package-correct, copies removed)
PYTHONDONTWRITEBYTECODE=1 bin/py/python.exe scripts/wfc/run_bounded.py --cap-gb 3 --log work/campaign_render/logs_$CH/q_lightmaps_relight.log work/campaign_render/dedupe_lightmaps.py $CH --remove-unit-copies </dev/null >/dev/null 2>&1
echo "lightmaps $(grep -o 'rc=[0-9]*' work/campaign_render/logs_$CH/q_lightmaps_relight.log)"
