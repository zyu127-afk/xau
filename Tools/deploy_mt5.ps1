param(
  [string]$TerminalDataPath="",
  [string]$MetaEditorPath="",
  [switch]$SkipCompile
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if([string]::IsNullOrWhiteSpace($TerminalDataPath)){
  throw 'TerminalDataPath is required. Run the new-computer installer and choose the intended MT5 instance.'
}
if(-not (Test-Path $TerminalDataPath)){ throw "MT5 data path not found: $TerminalDataPath" }
$experts=Join-Path $TerminalDataPath 'MQL5\Experts\GoldTradingSystem'
New-Item -ItemType Directory -Force -Path $experts | Out-Null
foreach($name in @('GoldTradingGuardian.mq5','GuardianIPC.mqh','GuardianState.mqh','GuardianHUD.mqh')){
  $src=Join-Path $root "MT5\$name"
  if(-not (Test-Path $src)){ throw "Missing MT5 master source: $src" }
  Copy-Item $src (Join-Path $experts $name) -Force
}
Write-Host "[MT5] Guardian source deployed to $experts"

function Show-CompileSummary([string]$LogPath){
  if(-not $LogPath -or -not (Test-Path $LogPath)){
    Write-Warning '[MT5] MetaEditor compile log was not created.'
    return
  }
  Write-Host '[MT5] MetaEditor compile summary:' -ForegroundColor Yellow
  $hits=Select-String -Path $LogPath -Pattern 'error|warning|result' -CaseSensitive:$false -ErrorAction SilentlyContinue
  if($hits){
    $hits | Select-Object -Last 20 | ForEach-Object { Write-Host ('  ' + $_.Line) }
  } else {
    Get-Content $LogPath -Tail 20 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host ('  ' + $_) }
  }
}

function Wait-ForCompileResult([string]$Ex5Path,[string]$LogPath,[int]$TimeoutSeconds=30){
  $deadline=[DateTime]::UtcNow.AddSeconds([Math]::Max(1,$TimeoutSeconds))
  while([DateTime]::UtcNow -lt $deadline){
    if(Test-Path $Ex5Path){ return $true }
    if(Test-Path $LogPath){
      $tail=(Get-Content $LogPath -Tail 8 -ErrorAction SilentlyContinue) -join "`n"
      if($tail -match '(?im)\b[1-9][0-9]*\s+errors?\b'){ return $false }
      if($tail -match '(?im)\b0\s+errors?\b' -and -not (Test-Path $Ex5Path)){
        Start-Sleep -Milliseconds 500
        if(Test-Path $Ex5Path){ return $true }
      }
    }
    Start-Sleep -Milliseconds 250
  }
  return (Test-Path $Ex5Path)
}

$compiled=$false
$compileAttempted=$false
$compileLog=''
if(-not $SkipCompile){
  if($MetaEditorPath -and (Test-Path $MetaEditorPath)){
    $compileAttempted=$true
    $source=Join-Path $experts 'GoldTradingGuardian.mq5'
    $ex5=Join-Path $experts 'GoldTradingGuardian.ex5'
    $compileLog=Join-Path $root 'Logs\mt5_compile.log'
    New-Item -ItemType Directory -Force -Path (Split-Path $compileLog) | Out-Null
    Remove-Item $compileLog -Force -ErrorAction SilentlyContinue
    Remove-Item $ex5 -Force -ErrorAction SilentlyContinue
    Write-Host '[MT5] Starting MetaEditor compile. Waiting up to 30 seconds for a fresh EX5...'
    & $MetaEditorPath "/compile:$source" "/log:$compileLog"
    $compiled=Wait-ForCompileResult $ex5 $compileLog 30
    if($compiled){
      Write-Host '[MT5] GoldTradingGuardian.ex5 compiled successfully.' -ForegroundColor Green
    } else {
      Write-Warning 'MetaEditor did not produce a fresh EX5 within the compile window.'
      Show-CompileSummary $compileLog
      Write-Warning "Full compile log: $compileLog"
    }
  } else {
    Write-Warning 'MetaEditor path was not resolved. Source is deployed; compile GoldTradingGuardian.mq5 manually in the selected MT5 MetaEditor.'
  }
} else {
  $compiled=Test-Path (Join-Path $experts 'GoldTradingGuardian.ex5')
}

$runtime=Join-Path $root 'Runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
@{
  source_deployed=$true
  compile_attempted=$compileAttempted
  ex5_compiled=$compiled
  data_path=$TerminalDataPath
  experts_path=$experts
  metaeditor_path=$MetaEditorPath
  compile_log=$compileLog
  checked_at_utc=[DateTime]::UtcNow.ToString('o')
} | ConvertTo-Json | Set-Content -Path (Join-Path $runtime 'mt5-binding.json') -Encoding UTF8

if(-not $compiled){
  Write-Warning '[MT5] Deployment status recorded, but EX5 compilation is not yet verified.'
}
