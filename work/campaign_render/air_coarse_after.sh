#!/usr/bin/env bash
# A4_ORB air nav at 8 m voxels (2 m and 4 m exceed the 6 GB cap): waits for the A2 / A3 air redo (air_after_lane.sh) to finish, so at most
# two heavy jobs run. One attempt; no air file if it fails too.
#   bash work/campaign_render/air_coarse_after.sh CH [CH ...]
cd "/f/Transformers Rebuild/AssetTools" || exit 1
PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; W=work/campaign_render; export PYTHONDONTWRITEBYTECODE=1
until { [ -f $W/lanes/lane_1.done ] || [ -f $W/lanes/lane_2.done ]; } && ! ps -ef | grep -v grep | grep -q air_after_lane.sh; do sleep 60; done
for CH in "$@"; do
  ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1 && { echo "PERF_HOLD: stopping before $CH"; exit 75; }
  R=out/campaign_render/$CH; L=$W/logs_$CH; I=$R/_air_input; mkdir -p $I
  cp $R/bot_nav.json $I/bot_nav.json; cp work/campaign_pilot/VerticalSlice/Maps/$CH/collision_pawn.glb $I/collision_pawn.glb
  WFC_AIR_VOX=8.0 $PY $RB --cap-gb 6 --log $L/air8.log scripts/wfc/bot_nav_air.py $CH --overlay $I --out $I </dev/null >/dev/null 2>&1 \
    && cp $I/bot_nav_air.json $R/bot_nav_air.json && echo "$CH air at 8 m $(date '+%H:%M')" || echo "$CH air at 8 m FAILED ($(grep -o 'peak_job_memory=[0-9.]* GB' $L/air8.log))"
done
