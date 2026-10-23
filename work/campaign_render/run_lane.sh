#!/usr/bin/env bash
# One lane of the campaign chain (Integration 2026-10-23: two lanes at once, each step under the 6 GB cap; chapters ship as they finish).
# Per chapter: the chain step (run_chapters.sh: render + inputs + nav + air nav + report), then its queue items right away (post-process,
# actors, destructibles, matinee_skeletal, transforming actors + materials rerun, chapter lightmaps + unit-copy removal, checkpoint spawns).
# The lane that finishes last rebuilds the outside-render asset list. Stops on a PERF_HOLD file.
#   bash work/campaign_render/run_lane.sh <lane name> CH [CH ...]
cd "/f/Transformers Rebuild/AssetTools" || exit 1
PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; W=work/campaign_render; export PYTHONDONTWRITEBYTECODE=1
LANE=$1; shift; mkdir -p $W/lanes
hold() { ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1 && { echo "PERF_HOLD: lane $LANE stopping"; exit 75; }; }
q() {   # q <log> <script> args...
  local log=$1; shift; hold
  $PY $RB --cap-gb 6 --log $log "$@" </dev/null >/dev/null 2>&1
  echo "  $(basename $log .log) $(grep -o 'rc=[0-9]*' $log)"
}
for CH in "$@"; do
  hold
  bash $W/run_chapters.sh $CH
  L=$W/logs_$CH; mkdir -p $L
  q $L/q_pp.log "F:/Transformers Rebuild/Rebuild/tools/render/build_campaign_pp.py" $CH "F:/Transformers Rebuild/AssetTools/out/campaign_render/$CH"
  q $L/q_actors.log $W/campaign_actors.py $CH
  q $L/q_destructibles.log $W/campaign_placed_destructibles.py $CH
  q $L/q_matinee_skeletal.log $W/campaign_matinee_skeletal.py $CH
  q $L/q_transforming.log $W/add_transforming_actors.py $CH --rerun-materials
  q $L/q_lightmaps.log $W/dedupe_lightmaps.py $CH --remove-unit-copies
  q $L/q_checkpoints.log $W/campaign_checkpoint_spawns.py $CH
  echo "$CH shipped $(date '+%H:%M')"; touch $W/lanes/done_$CH
done
touch $W/lanes/lane_$LANE.done
if [ -f $W/lanes/lane_1.done ] && [ -f $W/lanes/lane_2.done ]; then
  q $W/lanes/asset_list.log $W/campaign_asset_list.py; echo "asset list rebuilt $(date '+%H:%M')"
fi
