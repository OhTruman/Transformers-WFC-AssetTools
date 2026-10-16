@echo off
rem WFC_PKG_CACHE proof (Integration 2026-10-16): MP_UND_Gorge full pipeline with cache 16 and 6 into work\pkgcache\c<N>;
rem canonical Gorge manifests saved and restored around it.
setlocal
cd /d "F:\Transformers Rebuild\AssetTools"
call scripts\wfc\f_env.cmd
set "LOG=work\pkgcache\run.log"
echo start %time% > %LOG%
bin\py\python.exe -c "import shutil,glob,os;d='work/pkgcache/mani_orig';[shutil.copytree(p,os.path.join(d,p),dirs_exist_ok=True) if os.path.isdir(p) else (os.makedirs(os.path.dirname(os.path.join(d,p)),exist_ok=True),shutil.copy2(p,os.path.join(d,p))) for p in glob.glob('manifests/maps/MP_UND_Gorge')+glob.glob('manifests/next_map/MP_UND_Gorge_*')]" >> %LOG% 2>&1
for %%N in (16 6) do call :run %%N
bin\py\python.exe -c "import shutil,os;d='work/pkgcache/mani_orig';[(os.makedirs(os.path.dirname(os.path.join(r[len(d)+1:],f)),exist_ok=True),shutil.copy2(os.path.join(r,f),os.path.join(r[len(d)+1:],f))) for r,_,fs in os.walk(d) for f in fs]" >> %LOG% 2>&1
echo done %time% >> %LOG%
exit /b
:run
call scripts\wfc\hold_wait.cmd
set "WFC_PKG_CACHE=%1"
set "WFC_VS_ROOT=F:\Transformers Rebuild\AssetTools\work\pkgcache\c%1\VerticalSlice"
bin\py\python.exe scripts\wfc\run_map_pipeline.py MP_UND_Gorge >> %LOG% 2>&1
echo cache %1 pipeline rc %errorlevel% %time% >> %LOG%
bin\py\python.exe -c "import shutil,glob,os;[shutil.copytree(p,'work/pkgcache/c%1/manifests/maps',dirs_exist_ok=True) if os.path.isdir(p) else (os.makedirs('work/pkgcache/c%1/manifests/next_map',exist_ok=True),shutil.copy2(p,'work/pkgcache/c%1/manifests/next_map/')) for p in glob.glob('manifests/maps/MP_UND_Gorge')+glob.glob('manifests/next_map/MP_UND_Gorge_*')]" >> %LOG% 2>&1
exit /b
