@echo off
rem m04_bsp key-search fix: bsp audit + map_complete on every chapter
set "WFC_PKG_CACHE=10"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D5_OME 10 m04_bsp map_complete
echo bsp D5_OME done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A5_TRY 10 m04_bsp map_complete
echo bsp A5_TRY done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D3B_IAC 10 m04_bsp map_complete
echo bsp D3B_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A1_IAC 10 m04_bsp map_complete
echo bsp A1_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D3A_IAC 10 m04_bsp map_complete
echo bsp D3A_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A4_ORB 10 m04_bsp map_complete
echo bsp A4_ORB done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D2_COR 10 m04_bsp map_complete
echo bsp D2_COR done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A3_COR 10 m04_bsp map_complete
echo bsp A3_COR done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A2_KON 10 m04_bsp map_complete
echo bsp A2_KON done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D1_ORB 10 m04_bsp map_complete
echo bsp D1_ORB done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
echo bsp chain done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\bsp.log"
