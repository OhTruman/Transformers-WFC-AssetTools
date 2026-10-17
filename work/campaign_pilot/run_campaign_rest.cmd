@echo off
rem Stages after m05_bsp_default_faces when the driver stops there; same rules as run_campaign.cmd (hold watchdog: rc 76 -> wait
rem 60 s without a hold, rerun the stage).   run_campaign_rest.cmd <MAP> [cap GB]     (log: work\campaign_pilot\<MAP>_rest.log)
setlocal enabledelayedexpansion
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
set "WFC_VS_ROOT=F:\Transformers Rebuild\AssetTools\work\campaign_pilot\VerticalSlice"
set "CAP=%~2"
if "%CAP%"=="" set "CAP=6"
set "M=%1"
set "LOG=work\campaign_pilot\%1_rest.log"
echo start !time! > %LOG%
for %%S in (m04_kismet vs_pickups vs_destructibles vs_surface_audio map_structure_audit map_complete map_render_index) do call :run %%S
echo done >> %LOG%
exit /b
:run
call scripts\wfc\hold_wait.cmd
bin\py\python.exe scripts\wfc\run_bounded.py --cap-gb %CAP% --log logs\%M%_pipeline\rest_%1.log -- scripts\wfc\%1.py %M% >> %LOG% 2>&1
set "SRC=!errorlevel!"
if "!SRC!"=="76" (
  echo %1 interrupted by PERF_HOLD !time!, waiting for 60 s without a hold >> %LOG%
  call scripts\wfc\hold_clear60.cmd
  goto run
)
echo %1 rc !SRC! !time! >> %LOG%
exit /b
