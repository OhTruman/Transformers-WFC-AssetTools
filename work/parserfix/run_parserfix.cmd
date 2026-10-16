@echo off
rem Parser-fix gate (Integration 2026-10-16): Berth + Gorge through the generic pipeline with the OLD authored rows (undo) and then
rem the re-parsed rows, both into work\parserfix\<before|after>\VerticalSlice. Canonical MP manifests saved and restored around it.
setlocal
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
set "LOG=work\parserfix\run.log"
set "BAK=F:\Transformers Rebuild\AssetTools\backups\authored_reparse_20261016_072202.json"
echo start %time% > %LOG%
bin\py\python.exe -c "import shutil,glob,os;d='work/parserfix/mani_orig';[shutil.copytree(p,os.path.join(d,p.replace(os.sep,'/')),dirs_exist_ok=True) if os.path.isdir(p) else (os.makedirs(os.path.dirname(os.path.join(d,p)),exist_ok=True),shutil.copy2(p,os.path.join(d,p))) for m in ('MP_IAC_Berth','MP_UND_Gorge') for p in glob.glob('manifests/maps/'+m)+glob.glob('manifests/next_map/'+m+'_*')]" >> %LOG% 2>&1
bin\py\python.exe scripts\wfc\authored_reparse.py undo "%BAK%" >> %LOG% 2>&1
for %%T in (before after) do (
  if "%%T"=="after" bin\py\python.exe scripts\wfc\authored_reparse.py apply MP_IAC_Berth MP_UND_Gorge >> %LOG% 2>&1
  for %%M in (MP_IAC_Berth MP_UND_Gorge) do (
    call scripts\wfc\hold_wait.cmd
    set "WFC_VS_ROOT=F:\Transformers Rebuild\AssetTools\work\parserfix\%%T\VerticalSlice"
    call :run %%M %%T
  )
)
bin\py\python.exe -c "import shutil,os;d='work/parserfix/mani_orig';[ (os.makedirs(os.path.dirname(os.path.join(r[len(d)+1:],f)),exist_ok=True),shutil.copy2(os.path.join(r,f),os.path.join(r[len(d)+1:],f))) for r,_,fs in os.walk(d) for f in fs]" >> %LOG% 2>&1
echo done %time% >> %LOG%
exit /b
:run
set "WFC_VS_ROOT=F:\Transformers Rebuild\AssetTools\work\parserfix\%2\VerticalSlice"
bin\py\python.exe scripts\wfc\run_map_pipeline.py %1 >> %LOG% 2>&1
echo %1 %2 pipeline rc %errorlevel% %time% >> %LOG%
bin\py\python.exe -c "import shutil,glob,os;[shutil.copytree(p,os.path.join('work/parserfix/%2/manifests',os.path.basename(p)),dirs_exist_ok=True) if os.path.isdir(p) else (os.makedirs('work/parserfix/%2/manifests/next_map',exist_ok=True),shutil.copy2(p,'work/parserfix/%2/manifests/next_map/')) for p in glob.glob('manifests/maps/%1')+glob.glob('manifests/next_map/%1_*')]" >> %LOG% 2>&1
exit /b
