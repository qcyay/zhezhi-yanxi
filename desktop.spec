# Build with the project's dependencies on PYTHONPATH.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
datas = [(str(root / 'static'), 'static')]
datas += [(str(root / name), '.') for name in
          ('reference_sources.json', 'starter_recommendations.json', 'VERSION')]
binaries = []
hiddenimports = ['xlrd', 'openpyxl', 'pypdf', 'PIL', 'package_check']
for package in ('rapidocr_onnxruntime', 'onnxruntime', 'pyclipper', 'shapely'):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis([str(root / 'desktop_entry.py')], pathex=[str(root), str(root / '.deps')],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             hookspath=[], runtime_hooks=[], excludes=['pytest', 'IPython', 'tkinter'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ZheZhiYanXi',
          console=True, icon=str(root / 'static' / 'app.ico'), upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='ZheZhiYanXi', upx=False)
