from cx_Freeze import setup, Executable
import sys

# 依赖项
build_options = {
    'packages': [],
    'excludes': [
        'tkinter.test', 'unittest', 'pydoc', 'difflib', 'inspect',
        'email', 'urllib', 'http', 'xml', 'py_compile', 'doctest',
        'argparse', 'pickle', 'zipfile', 'sqlite3', 'ssl', 'html',
        'json', 'multiprocessing'
    ],
    'include_files': [],
    'optimize': 2
}

base = 'Win32GUI' if sys.platform=='win32' else None

executables = [
    Executable('main.py', base=base, target_name='微生物菌落计数器_cxFreeze版.exe')
]

setup(
    name='微生物菌落计数器',
    version='1.0',
    description='微生物菌落计数器 - 优化版',
    options={'build_exe': build_options},
    executables=executables
)