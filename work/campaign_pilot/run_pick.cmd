@echo off
rem campaign pickup discovery: vs_gameplay + vs_pickups + map_complete + render_index on every chapter (Integration 2026-10-17)
set "WFC_PKG_CACHE=10"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D5_OME 10 vs_gameplay vs_pickups map_complete map_render_index
echo pick D5_OME done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A5_TRY 10 vs_gameplay vs_pickups map_complete map_render_index
echo pick A5_TRY done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D3B_IAC 10 vs_gameplay vs_pickups map_complete map_render_index
echo pick D3B_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A1_IAC 10 vs_gameplay vs_pickups map_complete map_render_index
echo pick A1_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D3A_IAC 10 vs_gameplay vs_pickups map_complete map_render_index
echo pick D3A_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A4_ORB 10 vs_gameplay vs_pickups map_complete map_render_index
echo pick A4_ORB done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D2_COR 10 vs_gameplay vs_pickups map_complete map_render_index
echo pick D2_COR done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A3_COR 10 vs_gameplay vs_pickups map_complete map_render_index
echo pick A3_COR done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A2_KON 10 vs_gameplay vs_pickups map_complete map_render_index
echo pick A2_KON done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D1_ORB 10 vs_gameplay vs_pickups map_complete map_render_index
echo pick D1_ORB done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
echo pick chain done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\pick.log"
