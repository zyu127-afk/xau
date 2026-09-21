param(
  [string]$PythonExe = "",
  [switch]$Force
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime=Join-Path $root 'Runtime\python'
$embedded=Join-Path $runtime 'python.exe'
$venv=Join-Path $runtime 'Scripts\python.exe'

function Test-GtsPython([string]$Exe){
  if(-not (Test-Path $Exe)){ return $false }
  & $Exe -c "import yaml,httpx,fastapi,uvicorn; import MetaTrader5" 2>$null
  return $LASTEXITCODE -eq 0
}

if((Test-Path $embedded) -and -not $Force){
  if(Test-GtsPython $embedded){
    Write-Host "[Runtime] 使用已内置 Portable Python: $embedded"
    Write-Host $embedded
    exit 0
  }
  throw '检测到 Runtime\python\python.exe，但依赖自检失败。请重新构建 Portable runtime 或使用 -Force。'
}

function Find-Python {
  param([string]$Explicit)
  if($Explicit -and (Test-Path $Explicit)){ return (Resolve-Path $Explicit).Path }
  foreach($cmd in @('py','python')){
    try{
      if($cmd -eq 'py'){
        $p=& py -3.12 -c "import sys;print(sys.executable)" 2>$null
      } else {
        $p=& python -c "import sys;print(sys.executable)" 2>$null
      }
      if($LASTEXITCODE -eq 0 -and $p -and (Test-Path $p.Trim())){ return $p.Trim() }
    } catch {}
  }
  return $null
}

$base=Find-Python $PythonExe
if(-not $base){
  throw '未找到可用 Python 3，也没有内置 Portable Python。请使用正式 Portable ZIP，或安装 Python 3.11/3.12（64位）后重试。'
}

if((Test-Path $runtime) -and $Force){ Remove-Item $runtime -Recurse -Force }
if(-not (Test-Path $venv)){
  if(Test-Path $runtime){ Remove-Item $runtime -Recurse -Force }
  Write-Host "[Runtime] 创建虚拟环境: $runtime"
  & $base -m venv $runtime
  if($LASTEXITCODE -ne 0){ throw 'Python 虚拟环境创建失败。' }
}
if(-not (Test-Path $venv)){ throw 'Python 虚拟环境缺少 Scripts\python.exe。' }
& $venv -m pip install --upgrade pip
if($LASTEXITCODE -ne 0){ throw 'pip 更新失败。' }
& $venv -m pip install --no-cache-dir -r (Join-Path $root 'Engine\requirements-windows.txt')
if($LASTEXITCODE -ne 0){ throw 'Engine Windows 依赖安装失败。' }
& $venv -m pip install --no-cache-dir -r (Join-Path $root 'UI\requirements.txt')
if($LASTEXITCODE -ne 0){ throw 'UI 依赖安装失败。' }
if(-not (Test-GtsPython $venv)){ throw 'Python 环境依赖自检失败。' }
Write-Host '[Runtime] Python venv 环境准备完成。'
Write-Host $venv
