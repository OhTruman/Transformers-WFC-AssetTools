#!/usr/bin/env bash
# Add render units for chapter levels the sublevel splitter skipped because the chapter world.glb holds no static geometry for them
# (Integration 2026-10-23): streamed levels whose only drawables are skeletal / transforming actors (D3A CourtTrans_VIG, A2 DRIVE3_Trans_Design)
# and the persistent BASE level (A4 / D3A / D3B / A5: logic only, but the persistent unit carries the whole-chapter gameplay.json and
# chapter.json's persistent_dir). Per level: split dir with an EMPTY world.glb -> prep (split JSONs) -> chapter (only the new units' render
# steps run; finished units skip) -> relpaths -> layout -> collision (collision glbs / physics / gameplay.json copy) -> transforming actors
# (nodes + materials rerun + gameplay json) -> lightmaps. All steps regenerate their outputs; light jobs.
#   bash work/campaign_render/add_units.sh CH LEVEL_m [LEVEL_m ...]
cd "/f/Transformers Rebuild/AssetTools" || exit 1
PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; W=work/campaign_render; export PYTHONDONTWRITEBYTECODE=1
CH=$1; shift; S=work/campaign_pilot/VerticalSlice/Maps/$CH/sublevels; L=$W/logs_$CH; mkdir -p $L
ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1 && { echo "PERF_HOLD: not adding units"; exit 75; }
for LV in "$@"; do
  mkdir -p $S/$LV
  # empty world.glb WITH nodes / scenes (Rendering's steps read j['nodes']); map_fx.json / render_index.json filtered for the level as the
  # splitter would (campaign_render.filt: records whose sublevel / actor / component prefix is the level; chapter-wide values kept)
  $PY $W/add_units_inputs.py $CH $LV
  echo "split dir $LV"
done
q() { local log=$1; shift; $PY $RB --cap-gb 6 --log $log "$@" </dev/null >/dev/null 2>&1; echo "  $(basename $log .log) $(grep -o 'rc=[0-9]*' $log)"; }
q $L/u_prep.log $W/campaign_render.py prep $CH
$PY $W/campaign_render.py chapter $CH > $L/u_chapter.log 2>&1; echo "  chapter: $(grep -c ' ok$' $L/u_chapter.log) steps run, fails $(grep -c FAIL $L/u_chapter.log)"
q $L/u_relpaths.log $W/relpaths.py $CH
q $L/u_layout.log $W/campaign_render.py layout $CH
q $L/u_collision.log $W/campaign_collision.py $CH
q $L/u_transforming.log $W/add_transforming_actors.py $CH --rerun-materials
q $L/u_lightmaps.log $W/dedupe_lightmaps.py $CH --remove-unit-copies
for LV in "$@"; do U=out/campaign_render/$CH/${LV%_m}; echo "$LV unit: $(ls $U 2>/dev/null | tr '\n' ' ' | cut -c1-300)"; done
grep -o '"persistent_dir": [^,]*' out/campaign_render/$CH/chapter.json
