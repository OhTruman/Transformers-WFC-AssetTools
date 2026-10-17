@echo off
rem m05 over ALL BSP levels per chapter (tiled), then map_complete / render_index; Integration 2026-10-16
set "WFC_PKG_CACHE=10"
set "WFC_M05_TILE=256"
set "WFC_M05_ALL_LEVELS=1"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D5_OME 10 m05_bsp_default_faces map_complete map_render_index
echo m05all D5_OME done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A5_TRY 10 m05_bsp_default_faces map_complete map_render_index
echo m05all A5_TRY done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D3B_IAC 10 m05_bsp_default_faces map_complete map_render_index
echo m05all D3B_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A1_IAC 10 m05_bsp_default_faces map_complete map_render_index
echo m05all A1_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D3A_IAC 10 m05_bsp_default_faces map_complete map_render_index
echo m05all D3A_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A4_ORB 10 m05_bsp_default_faces map_complete map_render_index
echo m05all A4_ORB done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D2_COR 10 m05_bsp_default_faces map_complete map_render_index
echo m05all D2_COR done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A3_COR 10 m05_bsp_default_faces map_complete map_render_index
echo m05all A3_COR done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A2_KON 10 m05_bsp_default_faces map_complete map_render_index
echo m05all A2_KON done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D1_ORB 10 m05_bsp_default_faces map_complete map_render_index
echo m05all D1_ORB done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
echo m05all chain done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\m05all.log"
