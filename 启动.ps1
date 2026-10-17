$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')) { $runtime = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
elseif (Test-Path -LiteralPath $bundled) { $runtime = $bundled }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $runtime = 'py' }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $runtime = 'python' }
else { Write-Host '请先安装 Python 3.12 或更高版本。'; Read-Host '按回车退出'; exit 1 }
& $runtime app.py
if ($LASTEXITCODE -ne 0) { Read-Host '启动失败，按回车退出' }
