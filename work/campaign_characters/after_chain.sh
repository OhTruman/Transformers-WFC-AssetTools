#!/usr/bin/env bash
# queued behind run_chapters.sh (one interpreter at a time): actors A1 + D5 -> campaign characters -> blueprint dump -> actors of the rest
cd "/f/Transformers Rebuild/AssetTools" || exit 1
PY=bin/py/python.exe; RB=scripts/wfc/run_bounded.py; export PYTHONDONTWRITEBYTECODE=1
while ps -ef | grep -v grep | grep -q run_chapters.sh; do sleep 60; done
echo "chain done $(date '+%H:%M')"
hold() { ls "/f/Transformers Rebuild/"*/work/PERF_HOLD >/dev/null 2>&1 && { echo "PERF_HOLD: stopping"; exit 75; }; }
mkdir -p work/campaign_render/logs_actors
for CH in A1_IAC D5_OME; do hold; $PY $RB --cap-gb 6 --log work/campaign_render/logs_actors/$CH.log work/campaign_render/campaign_actors.py $CH >/dev/null 2>&1; echo "actors $CH $(grep -o 'rc=[0-9]*' work/campaign_render/logs_actors/$CH.log)"; done
hold; bash work/campaign_characters/run_characters.sh
hold; $PY $RB --cap-gb 6 --log work/campaign_characters/logs/blueprints.log work/campaign_characters/dump_blueprints.py >/dev/null 2>&1; echo "blueprints $(grep -o 'rc=[0-9]*' work/campaign_characters/logs/blueprints.log)"
for CH in A2_KON A3_COR A4_ORB A5_TRY D1_ORB D2_COR D3A_IAC D3B_IAC; do hold; $PY $RB --cap-gb 6 --log work/campaign_render/logs_actors/$CH.log work/campaign_render/campaign_actors.py $CH >/dev/null 2>&1; echo "actors $CH $(grep -o 'rc=[0-9]*' work/campaign_render/logs_actors/$CH.log)"; done
