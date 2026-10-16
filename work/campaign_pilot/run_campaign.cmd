@echo off
rem Campaign chapter through the generic map pipeline + vs_streaming (Integration GO 2026-10-16). CPU only; outputs under
rem work\campaign_pilot\VerticalSlice (WFC_VS_ROOT); per-stage wall time / peak memory in logs\<MAP>_pipeline and the probe json.
rem   run_campaign.cmd <MAP> [cap GB, default 6]     (log: work\campaign_pilot\<MAP>.log)
setlocal
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
set "WFC_VS_ROOT=F:\Transformers Rebuild\AssetTools\work\campaign_pilot\VerticalSlice"
set "CUDA_VISIBLE_DEVICES="
if "%WFC_PKG_CACHE%"=="" set "WFC_PKG_CACHE=6"
set "LOG=work\campaign_pilot\%1.log"
set "CAP=%~2"
if "%CAP%"=="" set "CAP=6"
echo start %date% %time% cap %CAP% pkgcache %WFC_PKG_CACHE% > %LOG%
call scripts\wfc\hold_wait.cmd
bin\py\python.exe scripts\wfc\run_map_pipeline.py %1 --cap-gb %CAP% >> %LOG% 2>&1
set "PRC=%errorlevel%"
echo pipeline rc %PRC% %time% >> %LOG%
rem m05 / structure audit pending for campaign chapters (Integration): when the driver stops, run the stages after m05
findstr /c:"FAILED at map_structure_audit" %LOG% >nul && call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" %1 %CAP% map_complete map_render_index
un_stages.cmd" %1 %CAP% map_complete map_render_index
findstr /c:"FAILED at m05_bsp_default_faces" %LOG% >nul && call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_campaign_rest.cmd" %1 %CAP%
un_campaign_rest.cmd" %1 %CAP%
call scripts\wfc\hold_wait.cmd
bin\py\python.exe scripts\wfc\run_bounded.py --cap-gb %CAP% --log logs\%1_pipeline\99_vs_streaming.log -- scripts\wfc\vs_streaming.py %1 >> %LOG% 2>&1
echo streaming rc %errorlevel% %time% >> %LOG%
echo done >> %LOG%
