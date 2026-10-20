@echo off
rem campaign starts: vs_gameplay + vs_validate + structure audit (2 m) + map_complete on every chapter
set "WFC_PKG_CACHE=10"
set "WFC_AUDIT_CELL=2"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D5_OME 10 vs_gameplay vs_validate map_structure_audit map_complete
echo st D5_OME done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A5_TRY 10 vs_gameplay vs_validate map_structure_audit map_complete
echo st A5_TRY done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D3B_IAC 10 vs_gameplay vs_validate map_structure_audit map_complete
echo st D3B_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A1_IAC 10 vs_gameplay vs_validate map_structure_audit map_complete
echo st A1_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D3A_IAC 10 vs_gameplay vs_validate map_structure_audit map_complete
echo st D3A_IAC done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A4_ORB 10 vs_gameplay vs_validate map_structure_audit map_complete
echo st A4_ORB done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D2_COR 10 vs_gameplay vs_validate map_structure_audit map_complete
echo st D2_COR done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A3_COR 10 vs_gameplay vs_validate map_structure_audit map_complete
echo st A3_COR done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" A2_KON 10 vs_gameplay vs_validate map_structure_audit map_complete
echo st A2_KON done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_stages.cmd" D1_ORB 10 vs_gameplay vs_validate map_structure_audit map_complete
echo st D1_ORB done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
echo st chain done >> "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\st.log"
