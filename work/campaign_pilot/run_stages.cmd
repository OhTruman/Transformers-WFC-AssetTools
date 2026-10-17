@echo off
rem Rerun named stages of a chapter: run_stages.cmd <MAP> <cap GB> <stage> [stage ...]   (log: work\campaign_pilot\<MAP>_stages.log)
rem Hold watchdog: run_bounded exits 76 when a PERF_HOLD appears mid-stage (stage killed); the stage is rerun from the start once no
rem hold has existed for 60 s (hold_clear60.cmd, pure cmd).
setlocal enabledelayedexpansion
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
set "WFC_VS_ROOT=F:\Transformers Rebuild\AssetTools\work\campaign_pilot\VerticalSlice"
set "M=%1"
set "CAP=%2"
set "LOG=work\campaign_pilot\%M%_stages.log"
echo start !time! > %LOG%
shift & shift
:next
if "%1"=="" goto end
:stage
call scripts\wfc\hold_wait.cmd
bin\py\python.exe scripts\wfc\run_bounded.py --cap-gb %CAP% --log logs\%M%_pipeline\stage_%1.log -- scripts\wfc\%1.py %M% >> %LOG% 2>&1
set "SRC=!errorlevel!"
if "!SRC!"=="76" (
  echo %1 interrupted by PERF_HOLD !time!, waiting for 60 s without a hold >> %LOG%
  call scripts\wfc\hold_clear60.cmd
  goto stage
)
echo %1 rc !SRC! !time! >> %LOG%
shift
goto next
:end
echo done >> %LOG%
