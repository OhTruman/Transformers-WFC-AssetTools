#!/usr/bin/env bash
# Air nav for chapters whose floor nav was redone after their lane step (A2 / A3, 2026-10-23: lowering had failed on empty collision glbs,
# A3's collision on an unsuffixed NavigationCell). Heavy (~6 GB at 4 m), so it waits until a lane finishes: two heavy jobs at most.
#   bash work/campaign_render/air_after_lane.sh CH [CH ...]
cd "/f/Transformers Rebuild/AssetTools" || exit 1
PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; W=work/campaign_render; export PYTHONDONTWRITEBYTECODE=1
until [ -f $W/lanes/lane_1.done ] || [ -f $W/lanes/lane_2.done ]; do sleep 60; done
for CH in "$@"; do
  ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1 && { echo "PERF_HOLD: stopping before $CH"; exit 75; }
  R=out/campaign_render/$CH; L=$W/logs_$CH; I=$R/_air_input; mkdir -p $I
  cp $R/bot_nav.json $I/bot_nav.json; cp work/campaign_pilot/VerticalSlice/Maps/$CH/collision_pawn.glb $I/collision_pawn.glb
  $PY $RB --cap-gb 6 --log $L/air_redo.log scripts/wfc/bot_nav_air.py $CH --overlay $I --out $I </dev/null >/dev/null 2>&1 || \
    WFC_AIR_VOX=4.0 $PY $RB --cap-gb 6 --log $L/air4_redo.log scripts/wfc/bot_nav_air.py $CH --overlay $I --out $I </dev/null >/dev/null 2>&1
  cp $I/bot_nav_air.json $R/bot_nav_air.json && echo "$CH air redone $(date '+%H:%M')" || echo "$CH air FAILED"
done
