@echo off
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
call scripts\wfc\hold_wait.cmd
bin\py\python.exe scripts\wfc\pickupfix_proof.py > work\pickupfix\proof.log 2>&1
echo done >> work\pickupfix\proof.log
