@echo off
rem resume of run_skel.cmd after the 05:41 reboot: the three chapters it did not finish
cd /d "F:\Transformers Rebuild\AssetTools"
echo start > work\campaign_pilot\skel2.log
for %%M in (D3A_IAC D3B_IAC D5_OME) do (
  call work\campaign_pilot\run_stages.cmd %%M 10 map_structure_audit map_complete
  echo %%M done >> work\campaign_pilot\skel2.log
)
echo skel chain done >> work\campaign_pilot\skel2.log
