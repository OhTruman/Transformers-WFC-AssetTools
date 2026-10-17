@echo off
rem skeletal world-actor collision rerun (Integration 2026-10-17 decision A): structure audit + map_complete on every chapter
cd /d "F:\Transformers Rebuild\AssetTools"
echo start %time% > work\campaign_pilot\skel.log
for %%M in (A1_IAC A2_KON A3_COR A4_ORB A5_TRY D1_ORB D2_COR D3A_IAC D3B_IAC D5_OME) do (
  call work\campaign_pilot\run_stages.cmd %%M 10 map_structure_audit map_complete
  echo %%M done %time% >> work\campaign_pilot\skel.log
)
echo skel chain done >> work\campaign_pilot\skel.log
