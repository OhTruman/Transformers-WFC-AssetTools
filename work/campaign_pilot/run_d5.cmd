@echo off
rem Campaign pilot (Integration GO 2026-10-16): D5_OME through the generic map pipeline, CPU only, outputs under work\campaign_pilot.
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
set "WFC_VS_ROOT=F:\Transformers Rebuild\AssetTools\work\campaign_pilot\VerticalSlice"
set "CUDA_VISIBLE_DEVICES="
call scripts\wfc\hold_wait.cmd
bin\py\python.exe scripts\wfc\run_map_pipeline.py D5_OME > work\campaign_pilot\pipeline.log 2>&1
echo rc %errorlevel% >> work\campaign_pilot\pipeline.log
