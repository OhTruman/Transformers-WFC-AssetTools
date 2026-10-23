#!/usr/bin/env bash
# queued behind run_chapters.sh (one heavy job at a time): per chain chapter, Rendering's post-process export + the actor table.
# D5 / A1 pp + actors, the campaign characters and the destructibles already ran beside the chain (light jobs; Integration 2026-10-23).
cd "/f/Transformers Rebuild/AssetTools" || exit 1
PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; export PYTHONDONTWRITEBYTECODE=1
while ps -ef | grep -v grep | grep -q run_chapters.sh; do sleep 60; done
echo "chain done $(date '+%H:%M')"
hold() { ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1 && { echo "PERF_HOLD: stopping"; exit 75; }; }
mkdir -p work/campaign_render/logs_actors work/campaign_render/logs_pp
PP="F:/Transformers Rebuild/Rebuild/tools/render/build_campaign_pp.py"
for CH in A2_KON A3_COR A4_ORB A5_TRY D1_ORB D2_COR D3A_IAC D3B_IAC; do
  hold
  if [ -f out/campaign_render/$CH/chapter.json ]; then
    $PY $RB --cap-gb 6 --log work/campaign_render/logs_pp/$CH.log "$PP" $CH "F:/Transformers Rebuild/AssetTools/out/campaign_render/$CH" >/dev/null 2>&1
    echo "pp $CH $(grep -o 'rc=[0-9]*' work/campaign_render/logs_pp/$CH.log)"
  else echo "pp $CH: no chapter.json, skipped"; fi
  $PY $RB --cap-gb 6 --log work/campaign_render/logs_actors/$CH.log work/campaign_render/campaign_actors.py $CH >/dev/null 2>&1
  echo "actors $CH $(grep -o 'rc=[0-9]*' work/campaign_render/logs_actors/$CH.log)"
  $PY $RB --cap-gb 6 --log work/campaign_render/logs_actors/dest_$CH.log work/campaign_render/campaign_placed_destructibles.py $CH >/dev/null 2>&1
  echo "destructibles $CH $(grep -o 'rc=[0-9]*' work/campaign_render/logs_actors/dest_$CH.log)"
  $PY $RB --cap-gb 6 --log work/campaign_render/logs_actors/matskel_$CH.log work/campaign_render/campaign_matinee_skeletal.py $CH >/dev/null 2>&1
  echo "matinee_skeletal $CH $(grep -o 'rc=[0-9]*' work/campaign_render/logs_actors/matskel_$CH.log)"
done
# one lightmap set per chapter, byte-identical unit copies removed (Integration go 2026-10-23; loader reads <chapter>/lightmaps/ first), then the asset list
for CH in A2_KON A3_COR A4_ORB A5_TRY D1_ORB D2_COR D3A_IAC D3B_IAC; do
  hold; $PY $RB --cap-gb 6 --log work/campaign_render/logs_actors/dedupe_$CH.log work/campaign_render/dedupe_lightmaps.py $CH --remove-unit-copies >/dev/null 2>&1
  echo "lightmaps $CH $(grep -o 'rc=[0-9]*' work/campaign_render/logs_actors/dedupe_$CH.log)"
done
hold; $PY $RB --cap-gb 6 --log work/campaign_render/logs_actors/asset_list.log work/campaign_render/campaign_asset_list.py >/dev/null 2>&1; echo "asset list $(grep -o 'rc=[0-9]*' work/campaign_render/logs_actors/asset_list.log)"
