@echo off
rem Keep temp files and tool caches of AssetTools jobs on F: (C: is tight). Usage: call scripts\wfc\f_env.cmd ^&^& <command>
set "ATC=F:\Transformers Rebuild\AssetTools\cache"
set "TEMP=%ATC%\tmp"
set "TMP=%ATC%\tmp"
set "PIP_CACHE_DIR=%ATC%\pip"
set "TORCH_HOME=%ATC%\torch"
set "HF_HOME=%ATC%\hf"
set "XDG_CACHE_HOME=%ATC%"
