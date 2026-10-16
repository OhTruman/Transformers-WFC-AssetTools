@echo off
rem Rerun named stages of a chapter: run_stages.cmd <MAP> <cap GB> <stage> [stage ...]   (log: work\campaign_pilot\<MAP>_stages.log)
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
call scripts\wfc\hold_wait.cmd
bin\py\python.exe scripts\wfc\run_bounded.py --cap-gb %CAP% --log logs\%M%_pipeline\stage_%1.log -- scripts\wfc\%1.py %M% >> %LOG% 2>&1
echo %1 rc !errorlevel! !time! >> %LOG%
shift
goto next
:end
echo done >> %LOG%
