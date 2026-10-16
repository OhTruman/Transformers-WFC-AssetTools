@echo off
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
call scripts\wfc\hold_wait.cmd
bin\py\python.exe scripts\wfc\gridfix_proof.py > work\gridfix\proof.log 2>&1
echo done >> work\gridfix\proof.log
