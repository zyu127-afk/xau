$ErrorActionPreference='SilentlyContinue'
Write-Host '=== MT5 candidates ==='
Get-ChildItem "$env:APPDATA\MetaQuotes\Terminal" -Directory | ForEach-Object {
  $origin=Join-Path $_.FullName 'origin.txt'
  if(Test-Path $origin){ [PSCustomObject]@{DataPath=$_.FullName; Origin=(Get-Content $origin -Raw).Trim()} }
} | Format-Table -AutoSize
Write-Host '=== ATAS candidates ==='
@("$env:LOCALAPPDATA\ATAS Platform","$env:APPDATA\ATAS Platform","$env:ProgramFiles\ATAS Platform") | Where-Object {Test-Path $_} | ForEach-Object {Write-Host $_}
Write-Host '把选定路径写入 Config\paths.yaml；源码中不要写死用户目录。'
