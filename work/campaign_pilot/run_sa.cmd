@echo off
rem structure audit (2 m) + map_complete on every chapter after the mesh-less explanation
set "WFC_PKG_CACHE=10"
set "WFC_AUDIT_CELL=2"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D5_OME 10 map_structure_audit map_complete
echo sa D5_OME done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A5_TRY 10 map_structure_audit map_complete
echo sa A5_TRY done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D3B_IAC 10 map_structure_audit map_complete
echo sa D3B_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A1_IAC 10 map_structure_audit map_complete
echo sa A1_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D3A_IAC 10 map_structure_audit map_complete
echo sa D3A_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A4_ORB 10 map_structure_audit map_complete
echo sa A4_ORB done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D2_COR 10 map_structure_audit map_complete
echo sa D2_COR done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A3_COR 10 map_structure_audit map_complete
echo sa A3_COR done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A2_KON 10 map_structure_audit map_complete
echo sa A2_KON done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D1_ORB 10 map_structure_audit map_complete
echo sa D1_ORB done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
echo sa chain done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\sa.log"
