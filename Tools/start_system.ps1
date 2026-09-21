param([switch]$NoBrowser)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime=Join-Path $root 'Runtime'
$pidFile=Join-Path $runtime 'processes.json'
$controlFile=Join-Path $runtime 'control.json'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

function Resolve-ProjectPython {
  foreach($candidate in @(
    (Join-Path $root 'Runtime\python\Scripts\python.exe'),
    (Join-Path $root 'Runtime\python\python.exe')
  )){
    if(Test-Path $candidate){ return (Resolve-Path $candidate).Path }
  }
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($cmd){ return $cmd.Source }
  throw 'Python runtime not found. Run the new-computer installer first.'
}

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

if(Test-Path $pidFile){
  try {
    $old=Get-Content $pidFile -Raw | ConvertFrom-Json
    $alive=@($old.processes | Where-Object { Test-TrackedProcess $_ })
    if($alive.Count -gt 0){
      throw 'GoldTradingSystem already has tracked local processes running. Run the system stop script first.'
    }
  } catch {
    if($_.Exception.Message -like 'GoldTradingSystem already*'){ throw }
  }
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$py=Resolve-ProjectPython
Push-Location $root
try {
  & $py -c "import yaml,httpx,fastapi,uvicorn" *> $null
  if($LASTEXITCODE -ne 0){ throw 'Python dependencies are incomplete. Run the new-computer installer first.' }

  $uiRaw=& $py -c "import json; from Engine.goldtrading.config import load_settings; s=load_settings(); print(json.dumps({'host':s.raw['ui']['host'],'port':int(s.raw['ui']['port'])}))"
  if($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($uiRaw)){ throw 'Unable to load UI configuration.' }
  $ui=$uiRaw | ConvertFrom-Json
  if([string]$ui.host -ne '127.0.0.1'){ throw 'V1 launcher requires ui.host=127.0.0.1 so Engine and Dashboard use one canonical loopback endpoint.' }
  $uiPort=[int]$ui.port
  $uiUrl="http://127.0.0.1:$uiPort"

  if(Test-Path $controlFile){ Remove-Item $controlFile -Force }

  $dashboard=Start-Process -FilePath $py -ArgumentList @('-m','uvicorn','UI.dashboard:app','--host','127.0.0.1','--port',[string]$uiPort) -WorkingDirectory $root -PassThru
  $ready=$false
  for($i=0;$i -lt 40;$i++){
    Start-Sleep -Milliseconds 250
    $dashboard.Refresh()
    if($dashboard.HasExited){ throw "Dashboard exited during startup with code $($dashboard.ExitCode)." }
    try {
      $r=Invoke-WebRequest -UseBasicParsing -Uri ($uiUrl+'/api/state') -TimeoutSec 1
      if($r.StatusCode -eq 200){ $ready=$true; break }
    } catch { }
  }
  if(-not $ready){
    try { Stop-Process -Id $dashboard.Id -Force -ErrorAction SilentlyContinue } catch { }
    throw "Dashboard did not become ready at $uiUrl."
  }

  $engine=Start-Process -FilePath $py -ArgumentList @('-m','Engine.goldtrading.main') -WorkingDirectory $root -PassThru
  Start-Sleep -Milliseconds 750
  $engine.Refresh()
  if($engine.HasExited){
    try { Stop-Process -Id $dashboard.Id -Force -ErrorAction SilentlyContinue } catch { }
    throw "Engine exited during startup with code $($engine.ExitCode). Inspect Logs/."
  }

  $record=@{
    schema=1
    root=$root
    started_at_utc=[DateTime]::UtcNow.ToString('o')
    ui_url=$uiUrl
    processes=@(
      @{role='dashboard';pid=$dashboard.Id;started_at_utc=$dashboard.StartTime.ToUniversalTime().ToString('o');executable=$py},
      @{role='engine';pid=$engine.Id;started_at_utc=$engine.StartTime.ToUniversalTime().ToString('o');executable=$py}
    )
  }
  $record | ConvertTo-Json -Depth 5 | Set-Content -Path $pidFile -Encoding UTF8

  Write-Host "[OK] Dashboard PID=$($dashboard.Id) $uiUrl" -ForegroundColor Green
  Write-Host "[OK] Engine PID=$($engine.Id)" -ForegroundColor Green
  Write-Host '[INFO] Normal stop does not flatten MT5 positions; Guardian remains inside MT5.'
  if(-not $NoBrowser){ Start-Process $uiUrl | Out-Null }
} finally {
  Pop-Location
}
