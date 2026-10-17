@echo off
rem Wait until no lane's PERF_HOLD has existed for 60 s (Integration 2026-10-17: rerun an interrupted stage only after the hold has
rem been gone for 60 s). Pure cmd: no python runs while waiting. Use: call scripts\wfc\hold_clear60.cmd
setlocal
:again
call "%~dp0hold_wait.cmd"
timeout /t 60 /nobreak >nul
for /d %%L in ("%~dp0..\..\..\*") do if exist "%%~fL\work\PERF_HOLD" goto again
endlocal
