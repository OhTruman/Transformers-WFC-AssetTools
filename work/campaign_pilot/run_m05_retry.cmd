@echo off
rem tiled m05 retry for A1_IAC / A3_COR (the 14:59 loop in run_diag.cmd did not run), then map_complete / render_index
set "WFC_PKG_CACHE=10"
set "WFC_M05_TILE=256"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A1_IAC 10 m05_bsp_default_faces map_complete map_render_index
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A3_COR 10 m05_bsp_default_faces map_complete map_render_index
echo retry done > "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05_retry.done"
