param(
  [string]$Version = "0.21.0-dev",
  [string]$Output = "Backup",
  [switch]$RequirePortablePython
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outDir=Join-Path $root $Output
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function New-Staging([string]$Name){
  $p=Join-Path $env:TEMP ($Name+'_'+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force -Path $p | Out-Null
  return $p
}
function Copy-Project([string]$Dest,[string[]]$SkipTop,[bool]$IncludeRuntimePython){
  Get-ChildItem $root -Force | Where-Object {$_.Name -notin (@('.git','Backup','Data','Logs')+$SkipTop)} | ForEach-Object {
    Copy-Item $_.FullName -Destination $Dest -Recurse -Force
  }
  foreach($secret in @('Config\secrets.local','Config\config.yaml','Config\paths.yaml','Runtime\dashboard.token','Runtime\control.json')){
    $p=Join-Path $Dest $secret
    if(Test-Path $p){Remove-Item $p -Force}
  }
  if(-not $IncludeRuntimePython){
    $runtimePython=Join-Path $Dest 'Runtime\python'
    if(Test-Path $runtimePython){Remove-Item $runtimePython -Recurse -Force}
  }
  Get-ChildItem $Dest -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
  Get-ChildItem $Dest -Recurse -File -Include '*.pyc','*.pyo' -ErrorAction SilentlyContinue | Remove-Item -Force
}
function Zip-Staging([string]$Staging,[string]$Target){
  if(Test-Path $Target){Remove-Item $Target -Force}
  Compress-Archive -Path (Join-Path $Staging '*') -DestinationPath $Target -CompressionLevel Optimal
  Remove-Item $Staging -Recurse -Force
  Write-Host "Created $Target"
}

$portablePython=Join-Path $root 'Runtime\python\python.exe'
$hasPortablePython=Test-Path $portablePython
if($RequirePortablePython -and -not $hasPortablePython){
  throw 'Portable Python runtime is required but Runtime\python\python.exe is missing. Run Tools\build_portable_python.ps1 first.'
}

$devStage=New-Staging 'GTS_DEV'
Copy-Project $devStage @() $false
$dev=Join-Path $outDir ("GoldTradingSystem_Dev_"+$Version+".zip")
Zip-Staging $devStage $dev

$portableStage=New-Staging 'GTS_PORTABLE'
Copy-Project $portableStage @('.github','Tests') $hasPortablePython
$runtimeLine = if($hasPortablePython){
  '已内置 Runtime\python\python.exe；目标电脑无需预装 Python。'
} else {
  '当前构建未内置 Python；Start\安装到新电脑.bat 会使用已安装 Python 建立项目环境。正式交付工作流会要求内置 runtime。'
}
$note=@"
GoldTradingSystem Portable $Version

1. 解压整个文件夹到任意本地磁盘。
2. 双击 Start\安装到新电脑.bat：检测/选择 MT5、准备配置、部署 Guardian，并检查项目 Python 运行环境。
3. 按 Docs\MANUAL_SETUP.md 完成 ATAS SDK / Rithmic Paper / MT5 Socket 实机步骤。
4. 双击 Start\启动系统.bat。

$runtimeLine
Portable 包不包含真实 API Key、个人路径、数据库、日志或账户数据。
"@
Set-Content -Path (Join-Path $portableStage 'PORTABLE_README.txt') -Value $note -Encoding UTF8
$portable=Join-Path $outDir ("GoldTradingSystem_Portable_"+$Version+".zip")
Zip-Staging $portableStage $portable
