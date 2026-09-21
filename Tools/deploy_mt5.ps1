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

$compiled=$false
$compileAttempted=$false
$compileLog=''
if(-not $SkipCompile){
  if($MetaEditorPath -and (Test-Path $MetaEditorPath)){
    $compileAttempted=$true
    $source=Join-Path $experts 'GoldTradingGuardian.mq5'
    $compileLog=Join-Path $root 'Logs\mt5_compile.log'
    New-Item -ItemType Directory -Force -Path (Split-Path $compileLog) | Out-Null
    & $MetaEditorPath "/compile:$source" "/log:$compileLog"
    Start-Sleep -Milliseconds 750
    $compiled=Test-Path (Join-Path $experts 'GoldTradingGuardian.ex5')
    if($compiled){
      Write-Host '[MT5] GoldTradingGuardian.ex5 compiled successfully.' -ForegroundColor Green
    } else {
      Write-Warning "MetaEditor did not produce EX5. Inspect $compileLog and compile manually in the selected MT5 MetaEditor."
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
