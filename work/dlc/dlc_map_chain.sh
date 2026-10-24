#!/usr/bin/env bash
# One DLC map, all AssetTools steps (Integration 2026-10-23; one heavy lane): MP pipeline -> render data -> bot_nav -> bot_nav_air (2 m, else
# 4 m, else 8 m) -> packaging lists. Stops on PERF_HOLD. Per-map log: work/dlc/chain_<MAP>.log
#   bash work/dlc/dlc_map_chain.sh <MAP>      (FROM_STAGE=N resumes the MP pipeline at stage N; WFC_AUDIT_CELL passes through to the audit)
cd "/f/Transformers Rebuild/AssetTools" || exit 1
. work/dlc/dlc_env.sh
M=$1; PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; L=work/dlc/chain_$M; mkdir -p $L
hold() { ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1 && { echo "PERF_HOLD: stopping $M"; exit 75; }; }
hold; rm -f logs/map_pipeline.lock
$PY scripts/wfc/run_map_pipeline.py $M --from-stage ${FROM_STAGE:-1} > $L/pipeline.log 2>&1; echo "pipeline: $(tail -1 $L/pipeline.log)"
grep -q "pipeline $M OK" $L/pipeline.log || { echo "$M stopped after the pipeline"; exit 1; }
hold; $PY work/dlc/dlc_render.py $M > $L/render.log 2>&1; echo "render: $(grep 'render data' $L/render.log)"
hold; $PY $RB --cap-gb 6 --log $L/bot_nav.log scripts/wfc/bot_nav.py $M </dev/null >/dev/null 2>&1; echo "bot_nav: $(grep -o 'rc=[0-9]*' $L/bot_nav.log)"
for V in 2 4 8; do
  hold; WFC_AIR_VOX=$V $PY $RB --cap-gb 6 --log $L/air_${V}m.log scripts/wfc/bot_nav_air.py $M </dev/null >/dev/null 2>&1
  if grep -q "rc=0" $L/air_${V}m.log; then echo "air: ${V} m"; break; else echo "air ${V} m failed ($(grep -o 'peak_job_memory=[0-9.]* GB' $L/air_${V}m.log))"; fi
done
hold; $PY $RB --cap-gb 3 --log $L/lists.log work/dlc/dlc_map_lists.py $M </dev/null >/dev/null 2>&1; echo "lists: $(grep -v 'run_bounded\|^$' $L/lists.log | tail -1)"
echo "$M chain done $(date '+%H:%M')"
