#!/usr/bin/env bash
# Campaign air-nav queue (Integration 2026-10-23), replacing the chained air waiters. One heavy job at a time, after a lane has finished
# (so with the other lane at most two). PERF_HOLD: waits before each attempt while the file exists; during an attempt it checks every 30 s
# and, if a hold appears, kills that attempt's process tree, waits for the hold to clear, and retries the same item. Each finished item
# (air file written, or every voxel size tried) leaves lanes/air_done_<CH>, so a relaunch after a reboot resumes where it stopped
# (resume_lanes.ps1 relaunches this). After the lanes finish, any chapter without bot_nav_air.json and without a marker is appended at 8 m.
#   bash work/campaign_render/air_queue.sh
cd "/f/Transformers Rebuild/AssetTools" || exit 1
PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; W=work/campaign_render; LN=$W/lanes; export PYTHONDONTWRITEBYTECODE=1
hold() { ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1; }
# item = CH:voxel sizes to try in order (A2 / A3: redo from the lowered floor nav; the rest exceeded the cap at 2 and 4 m)
ITEMS="A2_KON:2,4 A3_COR:2,4 A4_ORB:8 D1_ORB:8 D3A_IAC:8 D2_COR:8"
until [ -f $LN/lane_1.done ] || [ -f $LN/lane_2.done ]; do sleep 60; done
run_one() {   # run_one CH VOX -> 0 when bot_nav_air.json was written; 2 when interrupted by a hold
  local CH=$1 VOX=$2 R=out/campaign_render/$1 L=$W/logs_$1 I=out/campaign_render/$1/_air_input
  mkdir -p $I $L; cp $R/bot_nav.json $I/bot_nav.json; cp work/campaign_pilot/VerticalSlice/Maps/$CH/collision_pawn.glb $I/collision_pawn.glb
  rm -f $I/bot_nav_air.json
  WFC_AIR_VOX=$VOX $PY $RB --cap-gb 6 --log $L/airq_${VOX}m.log scripts/wfc/bot_nav_air.py $CH --overlay $I --out $I </dev/null >/dev/null 2>&1 &
  local pid=$!
  while kill -0 $pid 2>/dev/null; do
    if hold; then
      local wp=$(cat /proc/$pid/winpid 2>/dev/null)
      [ -n "$wp" ] && taskkill //PID $wp //T //F >/dev/null 2>&1; kill $pid 2>/dev/null; wait $pid 2>/dev/null
      echo "$CH ${VOX}m interrupted by PERF_HOLD $(date '+%H:%M')"; return 2
    fi
    sleep 30
  done
  wait $pid
  [ -f $I/bot_nav_air.json ] && cp $I/bot_nav_air.json $R/bot_nav_air.json && return 0
  return 1
}
process() {   # process CH VOXLIST
  local CH=$1 V
  [ -f $LN/air_done_$CH ] && return 0
  for V in ${2//,/ }; do
    while true; do
      while hold; do sleep 60; done
      run_one $CH $V; rc=$?
      [ $rc -eq 2 ] && { while hold; do sleep 60; done; continue; }   # hold: wait, then retry the same size
      break
    done
    if [ $rc -eq 0 ]; then echo "$CH air at ${V}m $(date '+%H:%M') ($(grep -o 'peak_job_memory=[0-9.]* GB' $W/logs_$CH/airq_${V}m.log))"; echo "ok ${V}m" > $LN/air_done_$CH; return 0; fi
    echo "$CH air at ${V}m FAILED ($(grep -o 'peak_job_memory=[0-9.]* GB' $W/logs_$CH/airq_${V}m.log))"
  done
  echo "none (tried ${2})" > $LN/air_done_$CH
}
for it in $ITEMS; do process ${it%%:*} ${it#*:}; done
# chapters still to ship get their air attempt from the lane; after both lanes, any chapter left without an air file: one 8 m try
until [ -f $LN/lane_1.done ] && [ -f $LN/lane_2.done ]; do sleep 60; done
for CH in A5_TRY D3B_IAC; do
  [ -f out/campaign_render/$CH/bot_nav_air.json ] && { [ -f $LN/air_done_$CH ] || echo "ok (lane)" > $LN/air_done_$CH; continue; }
  process $CH 8
done
echo "air queue done $(date '+%H:%M')"; touch $LN/air_queue.done
