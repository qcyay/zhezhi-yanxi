# Kept ASCII-only so Windows PowerShell 5.1 can read this without a BOM.
function Test-CompatiblePython([string]$Path) {
    if (!$Path -or !(Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    try {
        & $Path -I -c 'import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,12) and sys.maxsize > 2**32 else 1)' 2>$null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

function Get-ProjectPython([string]$Root) {
    return Join-Path $Root '.runtime\python-3.12.10\tools\python.exe'
}

function Install-ProjectPython([string]$Root) {
    $runtime = Get-ProjectPython $Root
    $directory = Join-Path $Root '.runtime'
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    # File sharing lock is released even on an exception or process termination.
    try {
        $lock = [IO.File]::Open((Join-Path $directory 'setup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    } catch { throw 'Another launcher is preparing Python. Wait for it to finish, then retry.' }
    $stage = $null
    try {
        if (Test-CompatiblePython $runtime) { return $runtime }
        $stage = Join-Path $directory ('download-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $stage | Out-Null
        $archive = Join-Path $stage 'python.zip'
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $previousProgress = $ProgressPreference
        try {
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 180 -Uri 'https://api.nuget.org/v3-flatcontainer/python/3.12.10/python.3.12.10.nupkg' -OutFile $archive
        } finally { $ProgressPreference = $previousProgress }
        $expected = '0EB85C2DFCCCCF1B17352DE4C397F69194035B7D37149EACC16F1147D93DE3B8'
        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) {
            throw 'Python download checksum mismatch. Retry on a trusted network.'
        }
        $extracted = Join-Path $stage 'package'
        Expand-Archive -LiteralPath $archive -DestinationPath $extracted
        if (!(Test-CompatiblePython (Join-Path $extracted 'tools\python.exe'))) {
            throw 'Downloaded Python cannot run on this Windows installation.'
        }
        $destination = Join-Path $directory 'python-3.12.10'
        $backup = Join-Path $directory ('broken-' + [Guid]::NewGuid().ToString('N'))
        $allowed = [IO.Path]::GetFullPath($directory) + [IO.Path]::DirectorySeparatorChar
        foreach ($target in @($extracted, $destination, $backup)) {
            if (![IO.Path]::GetFullPath($target).StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Runtime path escaped the project runtime directory.'
            }
        }
        # Keep any broken prior runtime for diagnosis; never delete arbitrary paths.
        if (Test-Path -LiteralPath $destination) {
            Move-Item -LiteralPath $destination -Destination $backup
        }
        Move-Item -LiteralPath $extracted -Destination $destination
        return $runtime
    } finally {
        if ($stage) {
            $resolvedStage = [IO.Path]::GetFullPath($stage)
            $allowed = [IO.Path]::GetFullPath($directory) + [IO.Path]::DirectorySeparatorChar
            if ($resolvedStage.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $resolvedStage -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
        $lock.Dispose()
    }
}
