# Render every episode to out/epNN.mp4 at 1920x1080, then join them into out/full_film.mp4.
# Video is copied as-is; the audio gets one linear gain toward -16 LUFS (capped so true peak stays
# under -1.5 dBTP). A linear gain keeps the room tone exactly as far under the voices as it was mixed;
# single-pass loudnorm would act like an AGC and swell the ambience in the long narrator-free stretches.
# Usage: .\tools\render_all.ps1            (all episodes)
#        .\tools\render_all.ps1 ep03 ep04  (just these; full film is rebuilt from whatever exists)
#        .\tools\render_all.ps1 -JoinOnly  (no rendering; rejoin and remix out/ep*.mp4)
param([switch]$JoinOnly, [Parameter(ValueFromRemainingArguments = $true)][string[]]$Episodes)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$portable = Join-Path $env:USERPROFILE 'tools\node-v24.22.1-win-x64'
if (-not (Get-Command npx -ErrorAction SilentlyContinue) -and (Test-Path $portable)) { $env:Path = "$portable;$env:Path" }

if ($JoinOnly) { $Episodes = @() }
elseif (-not $Episodes) { $Episodes = Get-ChildItem episodes\ep*.json | ForEach-Object { $_.BaseName } | Sort-Object }
New-Item -ItemType Directory -Force out | Out-Null

foreach ($ep in $Episodes) {
    Write-Host "=== rendering $ep"
    # Compositions are 1280x720; scale 1.5 renders 1080p from the 2048 px source images.
    npx remotion render $ep "out/$ep.mp4" --scale=1.5 --crf=18 --audio-bitrate=192k --log=error
    if ($LASTEXITCODE -ne 0) { throw "render failed for $ep" }
}

$list = Get-ChildItem out\ep*.mp4 | Sort-Object Name | ForEach-Object { "file '$($_.FullName -replace '\\','/')'" }
$list | Set-Content -Encoding ascii out\concat.txt
npx remotion ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i out/concat.txt -c copy out/joined.mp4
if ($LASTEXITCODE -ne 0) { throw "concat failed" }
$report = (npx remotion ffmpeg -hide_banner -nostats -i out/joined.mp4 -vn -af "loudnorm=I=-16:TP=-1.5:print_format=json" -f null - 2>&1) | Out-String
$m = [regex]::Match($report, '\{[^{}]*"input_i"[^{}]*\}').Value | ConvertFrom-Json
$gain = [math]::Round([math]::Min(-16 - [double]$m.input_i, -1.5 - [double]$m.input_tp), 2)
Write-Host "=== film measured $($m.input_i) LUFS, true peak $($m.input_tp) dBTP -> gain $gain dB"
npx remotion ffmpeg -y -hide_banner -loglevel error -i out/joined.mp4 -c:v copy -af "volume=$($gain)dB" `
    -ar 48000 -c:a aac -b:a 192k -movflags +faststart out/full_film.mp4
if ($LASTEXITCODE -ne 0) { throw "final mix failed" }
Remove-Item out/joined.mp4
Write-Host "=== done: out/full_film.mp4"
