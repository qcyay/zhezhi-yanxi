"""Build a self-contained Windows x64 portable ZIP using the current interpreter."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    os.chdir(ROOT)
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(str(ROOT / p) for p in ('.deps', '.builddeps'))
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm',
                    str(ROOT / 'desktop.spec')], env=env, check=True)
    folder = ROOT / 'dist' / 'ZheZhiYanXi'
    shutil.copy2(ROOT / 'PORTABLE_README.txt', folder / '使用说明.txt')
    # Retain distribution license notices alongside frozen third-party libraries.
    licenses = folder / 'THIRD_PARTY_LICENSES'
    licenses.mkdir(exist_ok=True)
    python_license = Path(sys.executable).parent / 'LICENSE.txt'
    if python_license.exists():
        shutil.copy2(python_license, licenses / 'Python-LICENSE.txt')
    for metadata in (ROOT / '.deps').glob('*.dist-info'):
        for source in metadata.rglob('*'):
            if source.is_file() and any(word in source.name.lower() for word in ('license', 'copying', 'notice')):
                destination = licenses / metadata.name / source.relative_to(metadata)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    version = (ROOT / 'VERSION').read_text('utf-8').strip()
    archive = Path(shutil.make_archive(str(ROOT / 'dist' / f'ZheZhiYanXi-{version}-Windows-x64'),
                                     'zip', folder.parent, folder.name))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{checksum}  {archive.name}\n', encoding='utf-8')
    print(archive)
    print(f'SHA256: {checksum}')


if __name__ == '__main__':
    main()
