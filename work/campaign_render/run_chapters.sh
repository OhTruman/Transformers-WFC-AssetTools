#!/usr/bin/env bash
# Campaign chapters, broad stroke (Integration / user 2026-10-23: produce the data once, play order, one report per chapter).
# Per chapter, sequential, every step a bounded process (run_bounded 6 GB), stops on a PERF_HOLD file:
#   render prep + chapter (all steps on the integration tools/render head) -> relpaths -> layout -> collision / nav inputs ->
#   bot_nav -> floor lowering -> fill (off-nav checkpoints) + mover-attached cells -> air nav (2 m voxels, 4 m if the cap is hit) -> report
#   bash work/campaign_render/run_chapters.sh A2_KON A3_COR ...
cd "/f/Transformers Rebuild/AssetTools" || exit 1
PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; W=work/campaign_render
export PYTHONDONTWRITEBYTECODE=1
for CH in "$@"; do
  if ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1; then echo "PERF_HOLD: stopping before $CH"; exit 75; fi
  L=$W/logs_$CH; mkdir -p $L; R=out/campaign_render/$CH
  echo "== $CH $(date '+%H:%M')"
  $PY $RB --cap-gb 6 --log $L/prep.log $W/campaign_render.py prep $CH >/dev/null 2>&1
  $PY $W/campaign_render.py chapter $CH > $L/chapter.log 2>&1
  $PY $RB --cap-gb 6 --log $L/relpaths.log $W/relpaths.py $CH >/dev/null 2>&1
  $PY $RB --cap-gb 6 --log $L/layout.log $W/campaign_render.py layout $CH >/dev/null 2>&1
  $PY $RB --cap-gb 6 --log $L/gaps.log $W/gaps.py $CH >/dev/null 2>&1
  $PY $RB --cap-gb 6 --log $L/collision.log $W/campaign_collision.py $CH >/dev/null 2>&1
  $PY $RB --cap-gb 6 --log $L/bot_nav.log $W/campaign_bot_nav.py $CH >/dev/null 2>&1
  G=$(ls $R/*/collision_pawn.glb 2>/dev/null | tr '\n' ' ')
  $PY $RB --cap-gb 6 --log $L/lower.log work/playtest_20261023/lower_nav_cells.py $R/bot_nav.json $G >/dev/null 2>&1
  $PY $RB --cap-gb 6 --log $L/fill_prepare.log $W/campaign_nav_fill.py $CH prepare >/dev/null 2>&1
  if grep -q '"location_gltf": \[' $R/_fill_input/gameplay.json 2>/dev/null; then
    mkdir -p $R/_fill_out
    WFC_VS_ROOT='F:\Transformers Rebuild\AssetTools\work\campaign_pilot\VerticalSlice' $PY $RB --cap-gb 6 --log $L/fill_nav.log scripts/wfc/bot_nav.py $CH --overlay $R/_fill_input --out $R/_fill_out >/dev/null 2>&1
  fi
  $PY $RB --cap-gb 6 --log $L/fill_merge.log $W/campaign_nav_fill.py $CH merge >/dev/null 2>&1
  I=$R/_air_input; mkdir -p $I; cp $R/bot_nav.json $I/bot_nav.json; cp work/campaign_pilot/VerticalSlice/Maps/$CH/collision_pawn.glb $I/collision_pawn.glb
  $PY $RB --cap-gb 6 --log $L/air.log scripts/wfc/bot_nav_air.py $CH --overlay $I --out $I >/dev/null 2>&1 || \
    WFC_AIR_VOX=4.0 $PY $RB --cap-gb 6 --log $L/air4.log scripts/wfc/bot_nav_air.py $CH --overlay $I --out $I >/dev/null 2>&1
  cp $I/bot_nav_air.json $R/bot_nav_air.json 2>/dev/null
  $PY $RB --cap-gb 6 --log $L/report.log $W/campaign_render.py report $CH >/dev/null 2>&1
  echo "$CH done $(date '+%H:%M'): $(grep -h 'sublevels\|MB' $L/report.log | head -1) | fails: $(grep -c FAIL $L/chapter.log)"
done
