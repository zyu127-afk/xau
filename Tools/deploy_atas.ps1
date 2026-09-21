param([string]$AtasTargetPath="")
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if([string]::IsNullOrWhiteSpace($AtasTargetPath)){throw 'AtasTargetPath is required after detecting the installed ATAS instance.'}
$source=Join-Path $root 'ATAS\GoldTradingDataBridge'
Write-Host "ATAS bridge source: $source"
Write-Host "Requested target: $AtasTargetPath"
Write-Host 'The SDK-bound assembly must be compiled against the installed ATAS SDK before deployment. This script deliberately does not copy an unverified binary.'
