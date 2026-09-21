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

function Remove-MachineState([string]$Dest){
  $sensitive=@(
    '.env',
    'Config\secrets.local',
    'Config\config.yaml',
    'Config\paths.yaml',
    'Runtime\dashboard.token',
    'Runtime\control.json',
    'Runtime\acceptance-report.json',
    'Runtime\atas-binding.json',
    'Runtime\mt5-binding.json',
    'Runtime\processes.json',
    'Runtime\diagnostics'
  )
  foreach($rel in $sensitive){
    $p=Join-Path $Dest $rel
    if(Test-Path $p){ Remove-Item $p -Recurse -Force }
  }
  # Defense in depth for hidden/untracked environment files created on a developer PC.
  Get-ChildItem $Dest -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq '.env' -or $_.Name -eq 'secrets.local' } |
    Remove-Item -Force
}

function Ensure-PortableSkeleton([string]$Dest){
  foreach($name in @('Data','Logs','Backup')){
    $dir=Join-Path $Dest $name
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $readme=Join-Path $root ($name+'\README.md')
    if(Test-Path $readme){ Copy-Item $readme (Join-Path $dir 'README.md') -Force }
  }
  New-Item -ItemType Directory -Force -Path (Join-Path $Dest 'Runtime') | Out-Null
}

function Copy-Project([string]$Dest,[string[]]$SkipTop,[bool]$IncludeRuntimePython){
  Get-ChildItem $root -Force | Where-Object {$_.Name -notin (@('.git','Backup','Data','Logs')+$SkipTop)} | ForEach-Object {
    Copy-Item $_.FullName -Destination $Dest -Recurse -Force
  }
  Remove-MachineState $Dest
  if(-not $IncludeRuntimePython){
    $runtimePython=Join-Path $Dest 'Runtime\python'
    if(Test-Path $runtimePython){Remove-Item $runtimePython -Recurse -Force}
  }
  Get-ChildItem $Dest -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
  Get-ChildItem $Dest -Recurse -File -Include '*.pyc','*.pyo' -ErrorAction SilentlyContinue | Remove-Item -Force
  Ensure-PortableSkeleton $Dest
}

function Resolve-CommitSha {
  $sha=[string]$env:GITHUB_SHA
  if([string]::IsNullOrWhiteSpace($sha)){
    try { $sha=(& git -C $root rev-parse HEAD 2>$null).Trim() } catch { $sha='' }
  }
  if([string]::IsNullOrWhiteSpace($sha)){ return 'unknown' }
  return $sha
}

function Write-BuildInfo([string]$Dest,[string]$PackageType,[bool]$EmbeddedPython){
  @{
    schema=1
    version=$Version
    package_type=$PackageType
    commit=(Resolve-CommitSha)
    built_at_utc=[DateTime]::UtcNow.ToString('o')
    embedded_python=$EmbeddedPython
  } | ConvertTo-Json | Set-Content -Path (Join-Path $Dest 'BUILD_INFO.json') -Encoding UTF8
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
Write-BuildInfo $devStage 'Dev' $false
$dev=Join-Path $outDir ("GoldTradingSystem_Dev_"+$Version+".zip")
Zip-Staging $devStage $dev

$portableStage=New-Staging 'GTS_PORTABLE'
Copy-Project $portableStage @('.github','Tests') $hasPortablePython
Write-BuildInfo $portableStage 'Portable' $hasPortablePython
$runtimeLine = if($hasPortablePython){
  '已内置 Runtime\python\python.exe；目标电脑无需预装 Python。'
} else {
  '当前构建未内置 Python；Start\安装到新电脑.bat 会使用已安装 Python 建立项目环境。正式交付工作流会要求内置 runtime。'
}
$note=@"
GoldTradingSystem Portable $Version

1. 解压整个文件夹到任意本地磁盘。
2. 双击 Start\安装到新电脑.bat：检测/选择 MT5、准备配置、部署/编译 Guardian，并在检测到 ATAS 时尝试针对本机 SDK 编译/部署 Bridge。
3. 按 Docs\MANUAL_SETUP.md 完成 MT5 Socket、ATAS 图表加载、Rithmic Paper、DeepSeek 与模拟盘实机步骤。
4. 先运行 Start\本机验收.bat，再运行 Start\启动系统.bat。
5. 正常结束时双击 Start\停止系统.bat；它只停止本系统记录的 Engine/Dashboard，不自动平掉 MT5 仓位。

$runtimeLine
Portable 包不包含真实 API Key、个人路径、数据库、日志、绑定状态、进程状态或验收/诊断数据。
BUILD_INFO.json 记录版本、构建提交与是否内嵌 Python，便于追溯交付物。
"@
Set-Content -Path (Join-Path $portableStage 'PORTABLE_README.txt') -Value $note -Encoding UTF8
$portable=Join-Path $outDir ("GoldTradingSystem_Portable_"+$Version+".zip")
Zip-Staging $portableStage $portable
