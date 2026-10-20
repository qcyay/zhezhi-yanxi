"""Exercise the launcher with Windows PowerShell 5.1, without network access."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "nt", "Windows launcher")
class RuntimeTests(unittest.TestCase):
    def run_script(self, script):
        library = str(Path(__file__).with_name("runtime.ps1")).replace("'", "''")
        # A parent PowerShell 7 session can export incompatible module directories.
        # Recreate the environment of a normal cmd.exe / double-click launch.
        environment = {k: v for k, v in os.environ.items() if k.lower() != "psmodulepath"}
        with tempfile.TemporaryDirectory(prefix="runtime test ") as root:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-Command", "$ErrorActionPreference='Stop'; . '" + library
                 + "'; $root='" + root.replace("'", "''") + "'; " + script],
                capture_output=True, text=True, errors="replace", env=environment,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_python_is_rejected(self):
        self.run_script("""
            if (Test-CompatiblePython (Join-Path $root 'missing.exe')) { exit 1 }
        """)

    def test_cached_runtime_never_downloads(self):
        self.run_script("""
            function Test-CompatiblePython { return $true }
            function Invoke-WebRequest { throw 'Unexpected network request' }
            $result = Install-ProjectPython $root
            if ($result -ne (Get-ProjectPython $root)) { exit 1 }
        """)

    def test_corrupt_download_is_rejected_and_lock_released(self):
        self.run_script("""
            function Test-CompatiblePython { return $false }
            function Invoke-WebRequest { param([switch]$UseBasicParsing,$TimeoutSec,$Uri,$OutFile)
                [IO.File]::WriteAllText($OutFile, 'corrupt')
            }
            function Expand-Archive { throw 'Must not extract unverified bytes' }
            for ($i=0; $i -lt 2; $i++) {
                try { Install-ProjectPython $root; exit 1 }
                catch { if ($_.Exception.Message -notlike '*checksum mismatch*') { throw } }
            }
            if (Get-ChildItem (Join-Path $root '.runtime') -Directory) { exit 1 }
        """)

    def test_network_failure_allows_retry(self):
        self.run_script("""
            function Test-CompatiblePython { return $false }
            function Invoke-WebRequest { throw 'Simulated network failure' }
            for ($i=0; $i -lt 2; $i++) {
                try { Install-ProjectPython $root; exit 1 }
                catch { if ($_.Exception.Message -ne 'Simulated network failure') { throw } }
            }
            if (Get-ChildItem (Join-Path $root '.runtime') -Directory) { exit 1 }
        """)

    def test_parallel_setup_is_rejected(self):
        self.run_script("""
            New-Item -ItemType Directory (Join-Path $root '.runtime') | Out-Null
            $held = [IO.File]::Open((Join-Path $root '.runtime\\setup.lock'),
                'OpenOrCreate', 'ReadWrite', 'None')
            try {
                try { Install-ProjectPython $root; exit 1 }
                catch { if ($_.Exception.Message -notlike '*Another launcher*') { throw } }
            } finally { $held.Dispose() }
        """)


if __name__ == "__main__":
    unittest.main()
