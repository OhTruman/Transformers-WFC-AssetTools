@echo off
rem Re-run the chapters after the authored.db re-parse (recovered meshes / lights): D5, A5, A1
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_campaign.cmd" D5_OME 10
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_campaign.cmd" A5_TRY 10
call "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\run_campaign.cmd" A1_IAC 10
echo all done > "F:\Transformers Rebuild\AssetTools\work\campaign_pilot\rerun3.done"
