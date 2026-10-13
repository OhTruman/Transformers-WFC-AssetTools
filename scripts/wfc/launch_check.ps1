# Launch an AssetTools runner detached (WMI Win32_Process Create, survives the session) and confirm it is alive 60 s later
# (Integration 2026-10-13: a silent relaunch failure went unnoticed for 13 min). Writes a start-up line to the runner's log first.
#   powershell -NoProfile -File scripts\wfc\launch_check.ps1 out\hd\run_e_gen.cmd logs\hd_e_gen.log
param([Parameter(Mandatory)][string]$Runner, [Parameter(Mandatory)][string]$Log, [int]$WaitSeconds = 60)
$root = 'F:\Transformers Rebuild\AssetTools'
$runnerPath = Join-Path $root $Runner; $logPath = Join-Path $root $Log
if (-not (Test-Path $runnerPath)) { Write-Output "launch_check: runner not found: $runnerPath"; exit 2 }
Add-Content -Path $logPath -Value ("=== launch {0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Runner) -Encoding ascii
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = "cmd.exe /c `"$runnerPath`""; CurrentDirectory = $root }
if ($r.ReturnValue -ne 0) { Write-Output "launch_check: create failed rv $($r.ReturnValue)"; exit 1 }
Start-Sleep -Seconds $WaitSeconds
$alive = Get-CimInstance Win32_Process -Filter "ProcessId=$($r.ProcessId)" -ErrorAction SilentlyContinue
$kids = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($r.ProcessId)" -ErrorAction SilentlyContinue)
if (-not $alive) {
    Add-Content -Path $logPath -Value ("=== launch_check: DEAD after {0}s ({1})" -f $WaitSeconds, (Get-Date -Format 'HH:mm:ss')) -Encoding ascii
    Write-Output "launch_check: $Runner DEAD after $WaitSeconds s (pid $($r.ProcessId)); see $Log"; exit 1
}
Write-Output ("launch_check: {0} alive after {1}s, pid {2}, {3} child process(es)" -f $Runner, $WaitSeconds, $r.ProcessId, $kids.Count)
