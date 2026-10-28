# Render every episode to out/epNN.mp4 at 1920x1080, then join them into out/full_film.mp4
# (video copied as-is, audio loudness-normalised to -16 LUFS for presentation playback).
# Usage: .\tools\render_all.ps1            (all episodes)
#        .\tools\render_all.ps1 ep03 ep04  (just these; full film is rebuilt from whatever exists)
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Episodes)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$portable = Join-Path $env:USERPROFILE 'tools\node-v24.22.1-win-x64'
if (-not (Get-Command npx -ErrorAction SilentlyContinue) -and (Test-Path $portable)) { $env:Path = "$portable;$env:Path" }

if (-not $Episodes) { $Episodes = Get-ChildItem episodes\ep*.json | ForEach-Object { $_.BaseName } | Sort-Object }
New-Item -ItemType Directory -Force out | Out-Null

foreach ($ep in $Episodes) {
    Write-Host "=== rendering $ep"
    # Compositions are 1280x720; scale 1.5 renders 1080p from the 2048 px source images.
    npx remotion render $ep "out/$ep.mp4" --scale=1.5 --crf=18 --audio-bitrate=192k --log=error
    if ($LASTEXITCODE -ne 0) { throw "render failed for $ep" }
}

$list = Get-ChildItem out\ep*.mp4 | Sort-Object Name | ForEach-Object { "file '$($_.FullName -replace '\\','/')'" }
$list | Set-Content -Encoding ascii out\concat.txt
npx remotion ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i out/concat.txt -c:v copy `
    -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 -c:a aac -b:a 192k -movflags +faststart out/full_film.mp4
if ($LASTEXITCODE -ne 0) { throw "concat failed" }
Write-Host "=== done: out/full_film.mp4"
