$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $PSScriptRoot
. (Join-Path $PSScriptRoot 'runtime.ps1')
$candidates = @(
    (Get-ProjectPython $PSScriptRoot),
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
foreach ($name in @('python.exe', 'python3.exe', 'python3.12.exe', 'python3.11.exe', 'python3.10.exe')) {
    foreach ($command in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
        if ($command.Source -and $command.Source -notlike '*WindowsApps*') { $candidates += $command.Source }
    }
}
# PEP 514 registrations also cover custom installation directories without PATH.
foreach ($registryRoot in @('HKCU:\Software\Python', 'HKLM:\Software\Python')) {
    foreach ($company in @(Get-ChildItem $registryRoot -ErrorAction SilentlyContinue)) {
        foreach ($tag in @(Get-ChildItem $company.PSPath -ErrorAction SilentlyContinue)) {
            $install = Get-Item (Join-Path $tag.PSPath 'InstallPath') -ErrorAction SilentlyContinue
            if ($install) {
                $registered = $install.GetValue('ExecutablePath')
                if ($registered) { $candidates += $registered }
                elseif ($install.GetValue('')) { $candidates += Join-Path $install.GetValue('') 'python.exe' }
            }
        }
    }
}
foreach ($version in @('312','311','310')) {
    $candidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python$version\python.exe"
    $candidates += Join-Path $env:ProgramFiles "Python$version\python.exe"
}
$runtime = $null
if ($args -contains '--local-python') {
    $candidates = @((Get-ProjectPython $PSScriptRoot))
    $args = @($args | Where-Object { $_ -ne '--local-python' })
}
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if (Test-CompatiblePython $candidate) { $runtime = $candidate; break }
}
if (!$runtime) {
    Write-Host '未找到可用的 64 位 Python 3.10–3.12，正在下载项目专用 Python 3.12。'
    Write-Host '仅保存到项目 .runtime 目录，无需管理员权限，不修改系统 PATH。首次启动请保持联网。'
    try {
        if (![Environment]::Is64BitOperatingSystem) { throw '64-bit Windows is required.' }
        $runtime = Install-ProjectPython $PSScriptRoot
    } catch {
        Write-Host "自动准备 Python 失败：$($_.Exception.Message)"
        Write-Host '请检查网络、磁盘空间和文件夹写入权限后重试。也可手动安装 64 位 Python 3.12（含 pip）。'
        Write-Host '下载地址：https://www.python.org/downloads/release/python-31210/'
        exit 1
    }
}
Write-Host "使用 Python：$runtime"
& $runtime (Join-Path $PSScriptRoot 'bootstrap.py') @args
exit $LASTEXITCODE
