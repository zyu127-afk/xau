param(
  [string]$PythonExe = "",
  [switch]$Force
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime=Join-Path $root 'Runtime\python'

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
  throw '未找到 Python 3。请先安装 Python 3.11/3.12（64位），然后重新运行；Portable 包允许使用自动安装环境，而不是把系统 Python 路径写死。'
}

if((Test-Path $runtime) -and $Force){ Remove-Item $runtime -Recurse -Force }
if(-not (Test-Path (Join-Path $runtime 'Scripts\python.exe'))){
  Write-Host "[Runtime] 创建虚拟环境: $runtime"
  & $base -m venv $runtime
}
$py=Join-Path $runtime 'Scripts\python.exe'
if(-not (Test-Path $py)){ throw 'Python 虚拟环境创建失败。' }
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $root 'Engine\requirements-windows.txt')
& $py -m pip install -r (Join-Path $root 'UI\requirements.txt')
Write-Host '[Runtime] Python 环境准备完成。'
Write-Host $py
