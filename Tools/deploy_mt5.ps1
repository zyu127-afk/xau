param([string]$TerminalDataPath="")
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if([string]::IsNullOrWhiteSpace($TerminalDataPath)){
  throw 'TerminalDataPath is required. Run Tools/detect_platforms.ps1 and choose the intended MT5 instance.'
}
$experts=Join-Path $TerminalDataPath 'MQL5\Experts\GoldTradingSystem'
New-Item -ItemType Directory -Force -Path $experts | Out-Null
Copy-Item (Join-Path $root 'MT5\GoldTradingGuardian.mq5') $experts -Force
Copy-Item (Join-Path $root 'MT5\GuardianIPC.mqh') $experts -Force
Write-Host "MT5 source deployed to $experts"
Write-Host 'Compile GoldTradingGuardian.mq5 with the MetaEditor belonging to this MT5 instance before use.'
