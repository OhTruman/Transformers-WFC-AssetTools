@echo off
rem Campaign movies -> out\movies (movies_webm.py; ffmpeg 4 threads below-normal). rc 76 = PERF_HOLD (encode killed): wait 60 s hold-free, resume.
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
echo start %date% %time% > work\campaign_pilot\movies.log
:again
call scripts\wfc\hold_wait.cmd
bin\py\python.exe scripts\wfc\movies_webm.py >> work\campaign_pilot\movies.log 2>&1
if errorlevel 76 if not errorlevel 77 (
  echo held %time%, waiting 60 s hold-free >> work\campaign_pilot\movies.log
  call scripts\wfc\hold_clear60.cmd
  goto again
)
echo movies chain done %time% >> work\campaign_pilot\movies.log
