"""Check project dependencies and start the local application without global installs."""
import importlib
import os
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DEPENDENCIES = ('pypdf', 'openpyxl', 'xlrd', 'rapidocr_onnxruntime', 'onnxruntime', 'numpy', 'cv2', 'PIL')

def missing_dependencies():
    missing = []
    for name in DEPENDENCIES:
        try:
            importlib.import_module(name)
        except Exception:
            missing.append(name)
    return missing

def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / '.deps'))
    missing = missing_dependencies()
    if missing:
        if '--dependencies-ready' in sys.argv:
            print('依赖安装后仍无法加载：' + ', '.join(missing), flush=True)
            return 1
        print('首次运行需要准备文档解析和图片识别组件，可能需要几分钟。', flush=True)
        print('依赖仅安装到本项目 .deps 文件夹，不修改其他 Python 环境。', flush=True)
        command = [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                   '--upgrade', '--target', str(ROOT / '.deps'), '-r', str(ROOT / 'requirements.txt')]
        result = subprocess.run(command)
        if result.returncode:
            print('组件安装未完成。请检查网络和上方错误，再次双击 start.cmd 重试。', flush=True)
            return result.returncode
        # Fresh interpreter avoids loading mixed old/new versions after installation.
        return subprocess.call([sys.executable, str(ROOT / 'bootstrap.py'), '--dependencies-ready', *sys.argv[1:]])
    if '--check' in sys.argv:
        print('运行环境和依赖检查通过。', flush=True)
        return 0
    sys.argv = [str(ROOT / 'app.py'), *[a for a in sys.argv[1:] if a != '--dependencies-ready']]
    runpy.run_path(str(ROOT / 'app.py'), run_name='__main__')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
