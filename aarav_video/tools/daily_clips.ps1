# Daily job: generate today's free-quota clips for the key shots, then rebuild and re-render the film.
# Run by the "AaravKeyShots" scheduled task; removes that task once every key shot has a clip.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$log = Join-Path $root 'clips\daily_log.txt'
$portable = Join-Path $env:USERPROFILE 'tools\node-v24.22.1-win-x64'
if (Test-Path $portable) { $env:Path = "$portable;$env:Path" }
$py = Join-Path $root '.venv\Scripts\python.exe'

function Log($msg) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm') $msg" | Add-Content -Encoding utf8 $log }

$keys = Get-Content clips\key_shots.json -Raw | ConvertFrom-Json
$missing = @($keys | Where-Object { -not (Test-Path "clips\in\$_.mp4") })
Log "start: $($missing.Count) key shots missing"

if ($missing.Count -gt 0) {
    # --max-hours 1: take what today's quota allows, then stop instead of waiting a day.
    & $py -I -u tools\hf_video.py --only @missing --seconds 4 --max-hours 1 *>&1 | Add-Content -Encoding utf8 $log
}

$made = @($keys | Where-Object { Test-Path "clips\in\$_.mp4" }).Count
$new = $missing.Count - @($keys | Where-Object { -not (Test-Path "clips\in\$_.mp4") }).Count
Log "clips now: $made of $($keys.Count) key shots ($new new today)"

if ($new -gt 0) {
    & $py -I tools\freeze_masks.py *>&1 | Out-Null
    & $py -I tools\voice.py all *>&1 | Out-Null
    & (Join-Path $root 'tools\render_all.ps1') *>&1 | Add-Content -Encoding utf8 $log
    Log "re-rendered episodes and full film"
}

if ($made -ge $keys.Count) {
    Unregister-ScheduledTask -TaskName 'AaravKeyShots' -Confirm:$false -ErrorAction SilentlyContinue
    Log "all key shots done; scheduled task removed"
}
