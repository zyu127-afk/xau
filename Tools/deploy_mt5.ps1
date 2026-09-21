param(
  [string]$TerminalDataPath="",
  [string]$MetaEditorPath="",
  [switch]$SkipCompile
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if([string]::IsNullOrWhiteSpace($TerminalDataPath)){
  throw 'TerminalDataPath is required. Run Start/安装到新电脑.bat and choose the intended MT5 instance.'
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

if(-not $SkipCompile){
  if($MetaEditorPath -and (Test-Path $MetaEditorPath)){
    $source=Join-Path $experts 'GoldTradingGuardian.mq5'
    $log=Join-Path $root 'Logs\mt5_compile.log'
    New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
    & $MetaEditorPath "/compile:$source" "/log:$log"
    Start-Sleep -Milliseconds 500
    if(Test-Path (Join-Path $experts 'GoldTradingGuardian.ex5')){
      Write-Host '[MT5] GoldTradingGuardian.ex5 compiled successfully.'
    } else {
      Write-Warning "MetaEditor did not produce EX5. Inspect $log and compile manually in the selected MT5 MetaEditor."
    }
  } else {
    Write-Warning 'MetaEditor path was not resolved. Source is deployed; compile GoldTradingGuardian.mq5 manually in the selected MT5 MetaEditor.'
  }
}
