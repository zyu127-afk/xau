param(
  [string]$PythonVersion = "3.12.10",
  [switch]$Force
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $root 'Runtime\python'
$python = Join-Path $runtime 'python.exe'

if((Test-Path $python) -and -not $Force){
  Write-Host "[Portable Python] already exists: $python"
  exit 0
}
if(Test-Path $runtime){ Remove-Item $runtime -Recurse -Force }
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

$zip = Join-Path $env:TEMP ("python-$PythonVersion-embed-amd64.zip")
$getPip = Join-Path $env:TEMP ("gts-get-pip-" + [guid]::NewGuid().ToString('N') + '.py')
$pythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$getPipUrl = "https://bootstrap.pypa.io/get-pip.py"

try {
  Write-Host "[Portable Python] downloading Python $PythonVersion embeddable runtime"
  Invoke-WebRequest -Uri $pythonUrl -OutFile $zip -UseBasicParsing
  Expand-Archive -Path $zip -DestinationPath $runtime -Force
  if(-not (Test-Path $python)){ throw "Portable Python extraction did not produce python.exe" }

  $pth = Get-ChildItem $runtime -Filter 'python*._pth' | Select-Object -First 1
  if(-not $pth){ throw 'Embeddable Python _pth file was not found.' }
  $lines = Get-Content $pth.FullName
  $new = @()
  $hasSitePackages = $false
  $hasImportSite = $false
  $hasProjectRoot = $false
  foreach($line in $lines){
    $trim = $line.Trim()
    if($trim -eq '#import site' -or $trim -eq 'import site'){
      if(-not $hasImportSite){ $new += 'import site'; $hasImportSite = $true }
      continue
    }
    if($trim -eq 'Lib\site-packages' -or $trim -eq 'Lib/site-packages'){
      if(-not $hasSitePackages){ $new += 'Lib\site-packages'; $hasSitePackages = $true }
      continue
    }
    if($trim -eq '..\..' -or $trim -eq '../..'){
      if(-not $hasProjectRoot){ $new += '..\..'; $hasProjectRoot = $true }
      continue
    }
    $new += $line
  }
  if(-not $hasProjectRoot){ $new += '..\..' }
  if(-not $hasSitePackages){ $new += 'Lib\site-packages' }
  if(-not $hasImportSite){ $new += 'import site' }
  Set-Content -Path $pth.FullName -Value $new -Encoding ASCII
  New-Item -ItemType Directory -Force -Path (Join-Path $runtime 'Lib\site-packages') | Out-Null

  Write-Host '[Portable Python] installing pip'
  Invoke-WebRequest -Uri $getPipUrl -OutFile $getPip -UseBasicParsing
  & $python $getPip --no-warn-script-location
  if($LASTEXITCODE -ne 0){ throw 'get-pip.py failed.' }

  Write-Host '[Portable Python] installing Engine/MT5/UI dependencies'
  & $python -m pip install --no-cache-dir --disable-pip-version-check -r (Join-Path $root 'Engine\requirements-windows.txt')
  if($LASTEXITCODE -ne 0){ throw 'Engine Windows dependency installation failed.' }
  & $python -m pip install --no-cache-dir --disable-pip-version-check -r (Join-Path $root 'UI\requirements.txt')
  if($LASTEXITCODE -ne 0){ throw 'UI dependency installation failed.' }

  & $python -c "import yaml,httpx,fastapi,uvicorn; import MetaTrader5; import Engine,UI; print('Portable Python dependency/project import check OK')"
  if($LASTEXITCODE -ne 0){ throw 'Portable Python dependency/project import validation failed.' }

  $manifest = @{
    python_version = $PythonVersion
    architecture = 'amd64'
    kind = 'python.org embeddable'
    project_root_relative = '..\..'
    built_at_utc = [DateTime]::UtcNow.ToString('o')
  } | ConvertTo-Json
  Set-Content -Path (Join-Path $runtime 'GTS_RUNTIME.json') -Value $manifest -Encoding UTF8
  Write-Host "[Portable Python] complete: $runtime"
}
finally {
  Remove-Item $zip -Force -ErrorAction SilentlyContinue
  Remove-Item $getPip -Force -ErrorAction SilentlyContinue
}
