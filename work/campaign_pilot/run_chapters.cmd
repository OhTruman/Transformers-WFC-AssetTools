@echo off
rem Remaining campaign chapters in size order, one at a time (Integration 2026-10-16). After each: the generated doc. The chain stops
rem when a chapter's driver fails anywhere other than m05 (pending) - a cap hit or a new blocker class is for Integration to decide.
setlocal
cd /d "F:\Transformers Rebuild\AssetTools"
set "WFC_PKG_CACHE=10"
for %%M in (D2_COR A3_COR A4_ORB D3A_IAC A2_KON D1_ORB) do (
  call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_campaign.cmd" %%M 10
  bin\py\python.exe scripts\wfc\campaign_chapter_doc.py %%M >> work\campaign_pilot\chapters.log 2>&1
  findstr /c:"FAILED at" work\campaign_pilot\%%M.log | findstr /v /c:"FAILED at m05_bsp_default_faces" | findstr /v /c:"FAILED at map_structure_audit" >nul && (echo STOP after %%M >> work\campaign_pilot\chapters.log & goto end)
  echo chapter %%M done %time% >> work\campaign_pilot\chapters.log
)
:end
echo chain done %time% >> work\campaign_pilot\chapters.log
