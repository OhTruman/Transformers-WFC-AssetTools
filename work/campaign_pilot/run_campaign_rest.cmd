@echo off
rem Stages after m05_bsp_default_faces (a Streets-era occlusion diagnostic) when it stops a chapter; same rules as run_campaign.cmd.
rem   run_campaign_rest.cmd <MAP> [cap GB]     (log: work\campaign_pilot\<MAP>_rest.log)
setlocal enabledelayedexpansion
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
set "WFC_VS_ROOT=F:\Transformers Rebuild\AssetTools\work\campaign_pilot\VerticalSlice"
set "CAP=%~2"
if "%CAP%"=="" set "CAP=6"
set "LOG=work\campaign_pilot\%1_rest.log"
echo start %time% > %LOG%
for %%S in (m04_kismet vs_pickups vs_destructibles vs_surface_audio map_structure_audit map_complete map_render_index) do (
  call scripts\wfc\hold_wait.cmd
  bin\py\python.exe scripts\wfc\run_bounded.py --cap-gb %CAP% --log logs\%1_pipeline\rest_%%S.log -- scripts\wfc\%%S.py %1 >> %LOG% 2>&1
  echo %%S rc !errorlevel! %time% >> %LOG%
)
echo done >> %LOG%
