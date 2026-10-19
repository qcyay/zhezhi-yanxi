$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $PSScriptRoot
$candidates = @(
    (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'),
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
)
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) {
    foreach ($version in @('-3.12', '-3.11', '-3.10')) {
        try {
            $resolved = & $pyLauncher.Source $version -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) { $candidates += $resolved }
        } catch { continue }
    }
}
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand -and $pythonCommand.Source -notlike '*WindowsApps*') { $candidates += $pythonCommand.Source }
foreach ($version in @('312','311','310')) {
    $candidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python$version\python.exe"
    $candidates += Join-Path $env:ProgramFiles "Python$version\python.exe"
}
$runtime = $null
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if (!(Test-Path -LiteralPath $candidate)) { continue }
    try {
        & $candidate -c 'import sys,struct; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,12) and sys.maxsize > 2**32 else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $runtime = $candidate; break }
    } catch { continue }
}
if (!$runtime) {
    Write-Host '未找到兼容的 64 位 Python。请安装 Python 3.12（勾选 Add Python to PATH），然后再次双击 start.cmd。'
    Write-Host '下载地址：https://www.python.org/downloads/windows/'
    exit 1
}
Write-Host "使用 Python：$runtime"
& $runtime (Join-Path $PSScriptRoot 'bootstrap.py') @args
exit $LASTEXITCODE
