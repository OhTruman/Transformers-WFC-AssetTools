@echo off
rem Wait until the system has at least WFC_COMMIT_RESUME_GB (default 18) of free commit (Integration 2026-10-12: jobs pause below
rem 14 GB, see hd_push.low_commit, and resume above 18; raised from 8 / 12 when C: ran tight). No python while waiting.
setlocal
if not defined WFC_COMMIT_RESUME_GB set WFC_COMMIT_RESUME_GB=18
set "SAID="
:check
for /f %%F in ('powershell -NoProfile -Command "[int]((Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory/1MB)"') do set FREE=%%F
if %FREE% GEQ %WFC_COMMIT_RESUME_GB% goto free
if not defined SAID echo commit_wait: free commit %FREE% GB below %WFC_COMMIT_RESUME_GB%, waiting (%date% %time%)
set "SAID=1"
ping -n 61 127.0.0.1 >nul
goto check
:free
if defined SAID echo commit_wait: free commit %FREE% GB, resuming (%date% %time%)
endlocal & exit /b 0
