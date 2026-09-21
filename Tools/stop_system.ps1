param([int]$GraceSeconds=8)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime=Join-Path $root 'Runtime'
$pidFile=Join-Path $runtime 'processes.json'
$controlFile=Join-Path $runtime 'control.json'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

function Test-TrackedProcess($item){
  try {
    $p=Get-Process -Id ([int]$item.pid) -ErrorAction Stop
    $actualStart=$p.StartTime.ToUniversalTime()
    $expectedStart=[DateTime]::Parse([string]$item.started_at_utc).ToUniversalTime()
    if([Math]::Abs(($actualStart-$expectedStart).TotalSeconds) -gt 3){ return $false }
    try {
      if($item.executable -and $p.Path){
        if([IO.Path]::GetFullPath($p.Path) -ne [IO.Path]::GetFullPath([string]$item.executable)){ return $false }
      }
    } catch { }
    return $true
  } catch { return $false }
}

function Write-StopRequest {
  # A normal stop is deliberately incapable of inheriting a stale emergency close request.
  $state=@{ai_sleep=$false;pause_new_entries=$false;stop_system=$true;emergency_close_request=''}
  if(Test-Path $controlFile){
    try {
      $existing=Get-Content $controlFile -Raw | ConvertFrom-Json
      if($null -ne $existing.ai_sleep){ $state.ai_sleep=[bool]$existing.ai_sleep }
      if($null -ne $existing.pause_new_entries){ $state.pause_new_entries=[bool]$existing.pause_new_entries }
    } catch { }
  }
  $tmp=Join-Path $runtime ('control-'+[guid]::NewGuid().ToString('N')+'.json')
  $state | ConvertTo-Json | Set-Content -Path $tmp -Encoding UTF8
  Move-Item $tmp $controlFile -Force
}

Write-StopRequest
Write-Host '[INFO] Requested normal Engine stop. This does NOT request CLOSE_ALL and does not flatten MT5 positions.'

if(-not (Test-Path $pidFile)){
  Write-Warning 'Runtime/processes.json is missing. Stop request was written, but there are no tracked local UI/Engine PIDs to terminate.'
  exit 0
}

try { $record=Get-Content $pidFile -Raw | ConvertFrom-Json }
catch { throw 'Runtime/processes.json is invalid; refusing broad process termination.' }

$items=@($record.processes)
$engine=@($items | Where-Object {$_.role -eq 'engine'} | Select-Object -First 1)
if($engine.Count -gt 0 -and (Test-TrackedProcess $engine[0])){
  $deadline=[DateTime]::UtcNow.AddSeconds([Math]::Max(1,$GraceSeconds))
  while([DateTime]::UtcNow -lt $deadline){
    Start-Sleep -Milliseconds 250
    if(-not (Test-TrackedProcess $engine[0])){ break }
  }
}

foreach($item in $items){
  if(-not (Test-TrackedProcess $item)){
    Write-Host "[INFO] $($item.role) PID=$($item.pid) is already stopped or no longer matches the recorded process."
    continue
  }
  try {
    Stop-Process -Id ([int]$item.pid) -Force -ErrorAction Stop
    Write-Host "[OK] Stopped tracked $($item.role) PID=$($item.pid)" -ForegroundColor Green
  } catch {
    Write-Warning "Could not stop tracked $($item.role) PID=$($item.pid): $($_.Exception.Message)"
  }
}

Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
Write-Host '[OK] GoldTradingSystem local Engine/Dashboard shutdown complete.' -ForegroundColor Green
Write-Host '[INFO] MT5 Guardian remains attached in MT5; existing server SL and weekend protection are not removed.'
