@echo off
rem Wait while any lane's performance hold exists: F:\Transformers Rebuild\<lane>\work\PERF_HOLD (presence = hold; the content is
rem only a label). The convention comes from Experimental's tools/fidelity/lib/M07.ps1 Wait-WfcGpu. Pure cmd, so no python.exe exists
rem while the hold is on (lane watchdogs flag any foreign python.exe). WFC_GATE_IGNORE_HOLD=1 skips only this lane's own hold.
rem Use: call scripts\wfc\hold_wait.cmd && python run_bounded.py ...
setlocal
set "HELD="
:check
set "ON="
for /d %%L in ("%~dp0..\..\..\*") do (
  if exist "%%~fL\work\PERF_HOLD" (
    if /i "%%~nxL"=="AssetTools" (
      if not "%WFC_GATE_IGNORE_HOLD%"=="1" set "ON=%%~fL\work\PERF_HOLD"
    ) else set "ON=%%~fL\work\PERF_HOLD"
  )
)
if not defined ON goto free
if not defined HELD echo hold_wait: waiting, PERF_HOLD present: %ON% (%date% %time%)
set "HELD=1"
rem ping instead of timeout: timeout fails without a console (WMI-launched jobs)
ping -n 31 127.0.0.1 >nul
goto check
:free
if defined HELD echo hold_wait: hold released (%date% %time%)
endlocal & exit /b 0
