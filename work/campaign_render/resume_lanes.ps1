# Resume the two-lane campaign chain after a reboot (Integration 2026-10-23). Durable state:
#   - render steps: out/campaign_render/<CH>/<unit>/_status/<step>.json (campaign_render.py chapter skips ok steps)
#   - shipped chapters: work/campaign_render/lanes/done_<CH> (skipped here)
#   - everything else in a chapter's chain / queue regenerates its outputs, so a half-done chapter is simply rerun from its first step
# Run from PowerShell:  powershell -File "F:\Transformers Rebuild\AssetTools\work\campaign_render\resume_lanes.ps1"
$AT = 'F:\Transformers Rebuild\AssetTools'; $L = Join-Path $AT 'work\campaign_render\lanes'
$bash = 'C:\Program Files\Git\usr\bin\bash.exe'
New-Item -ItemType Directory -Force $L | Out-Null
if (Test-Path 'F:\Transformers Rebuild\*\work\PERF_HOLD') { 'PERF_HOLD present: not resuming'; exit 75 }
# the air-nav queue (air_queue.sh): relaunched on its own when unfinished and not running; it resumes from lanes/air_done_<CH> markers
# and waits by itself for a lane to finish and for any PERF_HOLD to clear
$airRunning = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'air_queue\.sh' })
if (-not (Test-Path (Join-Path $L 'air_queue.done')) -and $airRunning.Count -eq 0) {
    $cl = 'cmd.exe /c ""' + $bash + '" -lc "cd ''/f/Transformers Rebuild/AssetTools'' && bash work/campaign_render/air_queue.sh >> work/campaign_render/lanes/air_queue.log 2>&1""'
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cl; CurrentDirectory = $AT }
    "air queue resumed (rc $($r.ReturnValue), pid $($r.ProcessId))"
} elseif ($airRunning.Count -gt 0) { 'air queue already running' } else { 'air queue: done' }
$running = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'run_lane\.sh|run_chapters\.sh|campaign_render\.py' })
if ($running.Count -gt 0) { "lanes still running ($($running.Count) processes): not resuming lanes"; exit 1 }
$lanes = @{ '1' = @('A3_COR', 'A4_ORB', 'D3A_IAC', 'A5_TRY'); '2' = @('D1_ORB', 'D2_COR', 'D3B_IAC') }
foreach ($k in '1', '2') {
    $todo = @($lanes[$k] | Where-Object { -not (Test-Path (Join-Path $L "done_$_")) })
    if ($todo.Count -eq 0) { "lane $k`: all shipped"; New-Item -ItemType File -Force (Join-Path $L "lane_$k.done") | Out-Null; continue }
    Remove-Item -ErrorAction SilentlyContinue (Join-Path $L "lane_$k.done")
    $cl = 'cmd.exe /c ""' + $bash + '" -lc "cd ''/f/Transformers Rebuild/AssetTools'' && bash work/campaign_render/run_lane.sh ' + $k + ' ' + ($todo -join ' ') +
          ' >> work/campaign_render/lanes/lane_' + $k + '.log 2>&1""'
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cl; CurrentDirectory = $AT }
    "lane $k resumed: $($todo -join ' ') (rc $($r.ReturnValue), pid $($r.ProcessId))"
}
