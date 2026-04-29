# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for fcstm-ui.

Toggle between onefile / onedir by setting the FCSTM_UI_BUILD_MODE env var
when invoking pyinstaller, e.g.:

    FCSTM_UI_BUILD_MODE=onefile pyinstaller --noconfirm main.spec
    FCSTM_UI_BUILD_MODE=onedir  pyinstaller --noconfirm main.spec

Defaults to onedir.
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)


BUILD_MODE = os.environ.get('FCSTM_UI_BUILD_MODE', 'onedir').lower()
APP_NAME = 'fcstm-ui'

datas = []
binaries = []
runtime_hooks = ['pyinstaller_rthook_z3.py']

# z3-solver: bundle the native libz3 next to the python wrapper.  The
# runtime hook (pyinstaller_rthook_z3.py) sets Z3_LIBRARY_PATH so the
# python wrapper can find the right .so/.dll/.dylib at startup.
binaries += collect_dynamic_libs('z3', destdir='z3/lib')

# pyfcstm ships data files (DSL grammar tokens, packaged template zips,
# verify design notes, etc.) inside its package; PyInstaller does not pick
# those up automatically because they are referenced through importlib
# resources / pkg_resources at runtime.
datas += collect_data_files('pyfcstm', includes=[
    '**/*.g4', '**/*.tokens', '**/*.interp',
    '**/*.json', '**/*.yaml', '**/*.yml',
    '**/*.zip', '**/*.png', '**/*.md',
])

# qtawesome ships the FontAwesome / Material font files as package data.
datas += collect_data_files('qtawesome')

# Bundled PlantUML jar (Java *bytecode* — Java runtime is NOT bundled,
# the target machine must have `java` on PATH).
plantuml_jar = Path('docs/plantuml.jar')
if plantuml_jar.exists():
    datas.append((str(plantuml_jar), 'docs'))

# Help PyInstaller discover modules that get imported via string lookups
# inside pyfcstm / hbutils, plus a handful of stdlib modules that PyQt5
# imports lazily.
hiddenimports = []
hiddenimports += collect_submodules('pyfcstm')
hiddenimports += collect_submodules('plantumlcli')
hiddenimports += collect_submodules('hbutils')
hiddenimports += [
    'ipaddress',
    'pkg_resources.py2_warn',
    'pkg_resources.markers',
]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        '_pytest',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if BUILD_MODE == 'onefile':
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )
