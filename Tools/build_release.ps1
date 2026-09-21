param(
  [string]$Version = "0.1.0-dev",
  [string]$Output = "Backup"
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outDir=Join-Path $root $Output
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$staging=Join-Path $env:TEMP ("GoldTradingSystem_"+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $staging | Out-Null
$exclude=@('.git','Backup','Data','Logs','Runtime\python','Config\secrets.local','__pycache__')
Get-ChildItem $root -Force | Where-Object {$_.Name -notin @('.git','Backup','Data','Logs')} | ForEach-Object {
  Copy-Item $_.FullName -Destination $staging -Recurse -Force
}
$secret=Join-Path $staging 'Config\secrets.local'
if(Test-Path $secret){Remove-Item $secret -Force}
Get-ChildItem $staging -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
$dev=Join-Path $outDir ("GoldTradingSystem_Dev_"+$Version+".zip")
if(Test-Path $dev){Remove-Item $dev -Force}
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $dev -CompressionLevel Optimal
Write-Host "Created $dev"
Remove-Item $staging -Recurse -Force
