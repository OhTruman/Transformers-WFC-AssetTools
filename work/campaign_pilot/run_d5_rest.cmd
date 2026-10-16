@echo off
setlocal enabledelayedexpansion
rem Campaign pilot, part 2: the stages after validate_smca_transforms (which stops the driver on 5 props without an extracted mesh).
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
set "WFC_VS_ROOT=F:\Transformers Rebuild\AssetTools\work\campaign_pilot\VerticalSlice"
set "L=logs\D5_OME_pipeline"
for %%S in (vs_validate m04_bsp m05_bsp_default_faces m04_kismet vs_pickups vs_destructibles vs_surface_audio map_structure_audit map_complete map_render_index) do (
  call scripts\wfc\hold_wait.cmd
  bin\py\python.exe scripts\wfc\run_bounded.py --cap-gb 6 --log %L%\rest_%%S.log -- scripts\wfc\%%S.py D5_OME >> work\campaign_pilot\pipeline_rest.log 2>&1
  echo %%S rc !errorlevel! >> work\campaign_pilot\pipeline_rest.log
)
echo done >> work\campaign_pilot\pipeline_rest.log
