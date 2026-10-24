#!/usr/bin/env bash
# Per DLC map, after dlc_map_chain.sh (2026-10-23): transforming actors in the MP schema (maps with TnTransformingWorldActors) and, for the
# Escalation maps, escalation_geometry.json + escalation_navmesh.json (RE's exports in RE-Workspace/notes/data/escalation/) - then the
# packaging lists again (they pick up the transforming GLBs). Stops on PERF_HOLD.
#   bash work/dlc/dlc_map_extras.sh <MAP>
cd "/f/Transformers Rebuild/AssetTools" || exit 1
. work/dlc/dlc_env.sh
M=$1; PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; L=work/dlc/chain_$M; mkdir -p $L
hold() { ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1 && { echo "PERF_HOLD: stopping $M"; exit 75; }; }
hold; $PY $RB --cap-gb 4 --log $L/transforming.log scripts/wfc/mp_transforming_actors.py --dlc-map $M </dev/null >/dev/null 2>&1
echo "transforming: $(grep -v 'run_bounded\|^$' $L/transforming.log | tail -1 | cut -c1-200)"
case "$M" in
  MP_ESC_*) hold; $PY $RB --cap-gb 4 --log $L/escalation.log scripts/wfc/escalation_data.py --maps $M </dev/null >/dev/null 2>&1
            echo "escalation: $(grep -v 'run_bounded\|^$' $L/escalation.log | tail -1 | cut -c1-250)";;
esac
hold; $PY $RB --cap-gb 3 --log $L/lists.log work/dlc/dlc_map_lists.py $M </dev/null >/dev/null 2>&1; echo "lists: $(grep -v 'run_bounded\|^$' $L/lists.log | tail -1 | cut -c1-200)"
echo "$M extras done $(date '+%H:%M')"
