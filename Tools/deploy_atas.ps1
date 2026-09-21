param(
  [string]$AtasInstallPath="",
  [string]$TargetPath="",
  [switch]$NoDeploy
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$project=Join-Path $root 'ATAS\GoldTradingDataBridge.ATAS\GoldTradingDataBridge.ATAS.csproj'
$logDir=Join-Path $root 'Logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if([string]::IsNullOrWhiteSpace($AtasInstallPath)){
  throw 'AtasInstallPath is required. Run the new-computer installer so the installed ATAS instance can be detected.'
}
if(-not (Test-Path $AtasInstallPath)){ throw "ATAS path not found: $AtasInstallPath" }
if(-not (Test-Path $project)){ throw "ATAS SDK binding project not found: $project" }

$sdkDll=Join-Path $AtasInstallPath 'ATAS.Indicators.dll'
if(-not (Test-Path $sdkDll)){
  $hit=Get-ChildItem -Path $AtasInstallPath -Filter 'ATAS.Indicators.dll' -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
  if($hit){ $sdkDll=$hit.FullName; $AtasInstallPath=$hit.Directory.FullName }
}
$dataFeeds=Join-Path $AtasInstallPath 'ATAS.DataFeedsCore.dll'
if(-not (Test-Path $sdkDll)){ throw 'ATAS.Indicators.dll was not found under the selected ATAS installation.' }
if(-not (Test-Path $dataFeeds)){ throw "ATAS.DataFeedsCore.dll was not found next to ATAS.Indicators.dll: $AtasInstallPath" }

$dotnet=Get-Command dotnet -ErrorAction SilentlyContinue
if(-not $dotnet){
  throw 'dotnet SDK was not found. Install the Microsoft .NET SDK matching the ATAS runtime (8 or 10), then rerun this script.'
}

$bytes=[IO.File]::ReadAllBytes($sdkDll)
$meta=[Text.Encoding]::UTF8.GetString($bytes)
$targets=@()
if($meta -match '\.NETCoreApp,Version=v10\.0'){ $targets += 'net10.0-windows' }
if($meta -match '\.NETCoreApp,Version=v8\.0'){ $targets += 'net8.0-windows' }
foreach($fallback in @('net10.0-windows','net8.0-windows')){ if($targets -notcontains $fallback){ $targets += $fallback } }

$built=$null
$selectedTfm=$null
foreach($tfm in $targets){
  $log=Join-Path $logDir ("atas_sdk_build_{0}.log" -f $tfm.Replace('.','_'))
  Write-Host "[ATAS] Trying SDK build target $tfm against $AtasInstallPath"
  $output=& dotnet build $project -c Release -f $tfm "/p:AtasInstallDir=$AtasInstallPath" 2>&1
  $output | Set-Content -Path $log -Encoding UTF8
  $candidate=Join-Path $root "ATAS\GoldTradingDataBridge.ATAS\bin\Release\$tfm\GoldTradingDataBridge.ATAS.dll"
  if($LASTEXITCODE -eq 0 -and (Test-Path $candidate)){
    $built=$candidate; $selectedTfm=$tfm; break
  }
}
if(-not $built){
  throw 'ATAS SDK bridge did not compile against the installed SDK. Inspect Logs/atas_sdk_build_*.log. No unverified DLL was deployed.'
}

$core=Join-Path $root "ATAS\GoldTradingDataBridge.ATAS\bin\Release\$selectedTfm\GoldTradingDataBridge.dll"
if(-not (Test-Path $core)){
  $core=Join-Path $root 'ATAS\GoldTradingDataBridge\bin\Release\net8.0\GoldTradingDataBridge.dll'
}
if(-not (Test-Path $core)){ throw 'GoldTradingDataBridge core DLL is missing after successful SDK build.' }

if([string]::IsNullOrWhiteSpace($TargetPath)){
  $TargetPath=Join-Path $env:APPDATA 'ATAS\Indicators'
}
if(-not $NoDeploy){
  New-Item -ItemType Directory -Force -Path $TargetPath | Out-Null
  Copy-Item $built (Join-Path $TargetPath 'GoldTradingDataBridge.ATAS.dll') -Force
  Copy-Item $core (Join-Path $TargetPath 'GoldTradingDataBridge.dll') -Force
  Write-Host "[ATAS] SDK bridge deployed to $TargetPath" -ForegroundColor Green
}

$runtime=Join-Path $root 'Runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
@{
  sdk_path=$AtasInstallPath
  target_path=$TargetPath
  target_framework=$selectedTfm
  built_dll=$built
  deployed=(-not $NoDeploy)
  built_at_utc=[DateTime]::UtcNow.ToString('o')
} | ConvertTo-Json | Set-Content -Path (Join-Path $runtime 'atas-binding.json') -Encoding UTF8

Write-Host "[ATAS] Verified local SDK build: $selectedTfm" -ForegroundColor Green
