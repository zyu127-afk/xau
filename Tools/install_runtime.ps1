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
    Write-Host "[Runtime] Using bundled Portable Python: $embedded"
    Write-Host $embedded
    return
  }
  throw 'Runtime\python\python.exe exists, but dependency self-test failed. Rebuild the Portable runtime or use -Force.'
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
  throw 'No usable Python 3 was found and no bundled Portable Python exists. Use the official Portable ZIP or install 64-bit Python 3.11/3.12.'
}

if((Test-Path $runtime) -and $Force){ Remove-Item $runtime -Recurse -Force }
if(-not (Test-Path $venv)){
  if(Test-Path $runtime){ Remove-Item $runtime -Recurse -Force }
  Write-Host "[Runtime] Creating virtual environment: $runtime"
  & $base -m venv $runtime
  if($LASTEXITCODE -ne 0){ throw 'Failed to create Python virtual environment.' }
}
if(-not (Test-Path $venv)){ throw 'Python virtual environment is missing Scripts\python.exe.' }
& $venv -m pip install --upgrade pip
if($LASTEXITCODE -ne 0){ throw 'pip upgrade failed.' }
& $venv -m pip install --no-cache-dir -r (Join-Path $root 'Engine\requirements-windows.txt')
if($LASTEXITCODE -ne 0){ throw 'Engine Windows dependency installation failed.' }
& $venv -m pip install --no-cache-dir -r (Join-Path $root 'UI\requirements.txt')
if($LASTEXITCODE -ne 0){ throw 'UI dependency installation failed.' }
if(-not (Test-GtsPython $venv)){ throw 'Python dependency self-test failed.' }
Write-Host '[Runtime] Python environment is ready.'
Write-Host $venv
