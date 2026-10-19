"""Check project dependencies and start the local application without global installs."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DEPENDENCIES = ('pypdf', 'openpyxl', 'xlrd', 'rapidocr_onnxruntime', 'onnxruntime', 'numpy', 'cv2', 'PIL')

def missing_dependencies():
    # Probe in a separate process: importing DLLs here would lock them while pip repairs .deps.
    probe = """import importlib,json,sys
sys.path.insert(0,sys.argv[1])
missing=[]
for name in json.loads(sys.argv[2]):
    try: importlib.import_module(name)
    except Exception: missing.append(name)
print(json.dumps(missing))
"""
    result = subprocess.run([sys.executable, '-c', probe, str(ROOT / '.deps'), json.dumps(DEPENDENCIES)],
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    try:
        return json.loads(result.stdout.strip().splitlines()[-1]) if result.returncode == 0 else list(DEPENDENCIES)
    except (ValueError, IndexError):
        return list(DEPENDENCIES)


def install_dependencies(command):
    import msvcrt
    with (ROOT / '.setup.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            print('另一个启动窗口正在安装组件，请等待它完成，不要重复启动。', flush=True)
            return 1
        try:
            return subprocess.run(command).returncode
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

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
        result = install_dependencies(command)
        if result:
            print('组件安装未完成。请检查网络和上方错误，再次双击 start.cmd 重试。', flush=True)
            return result
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
