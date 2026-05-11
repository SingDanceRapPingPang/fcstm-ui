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
import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)


# Make sure the project root is on sys.path so collect_submodules('app')
# can actually import the package while the spec is evaluated.  Without
# this, PyInstaller silently returns just the top-level package and most
# of our laz-loaded submodules (export_to_excel, draggable_tree_widget,
# …) end up missing from the bundle.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(SPEC))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

BUILD_MODE = os.environ.get('FCSTM_UI_BUILD_MODE', 'onedir').lower()
APP_NAME = 'fcstm-ui'

datas = []
binaries = []
runtime_hooks = ['pyinstaller_rthook_z3.py']


def _collect_linux_system_libs():
    """Return a list of (src, '.') tuples for the Linux system libraries
    that PyInstaller does *not* bundle by default but that PyQt5 needs at
    runtime on a clean Ubuntu 22.04 box.

    PyInstaller already auto-collects the bulk of the Qt platform
    plugin's dependencies (libxcb-* sub-libs, libxkbcommon, libfontconfig,
    libfreetype, libstdc++, libdbus, libpng16, libz, …).  What it
    intentionally excludes are the OpenGL / GLX / X11 entry-point
    libraries — they sit on a system-driver excludelist because the
    matching mesa libGL on the build host may not match the GPU driver
    on the target box.

    For us the GUI never actually issues any GL draw calls (PyQt5 only
    needs the libGL.so.1 *symbols* to satisfy linker references), so
    bundling whatever libGL is on the build host is fine and gives us a
    self-contained artifact that runs on a fresh ubuntu:22.04 with zero
    apt installs (Java aside, which is policy-bundled separately).

    Returns an empty list on non-Linux hosts so the spec stays portable.
    """
    if sys.platform != 'linux':
        return []
    result = []
    seen = set()
    candidates = [
        'libGL.so.1',
        'libGLdispatch.so.0',
        'libGLX.so.0',
        'libX11.so.6',
        'libX11-xcb.so.1',
        'libXext.so.6',
        'libxcb.so.1',
        'libXau.so.6',
        'libXdmcp.so.6',
        'libbsd.so.0',
    ]
    search_dirs = [
        '/usr/lib/x86_64-linux-gnu',
        '/lib/x86_64-linux-gnu',
        '/usr/lib64',
    ]
    for name in candidates:
        for d in search_dirs:
            path = os.path.join(d, name)
            if os.path.exists(path) and path not in seen:
                # IMPORTANT: pass the SONAME path (e.g. /…/libGL.so.1),
                # NOT os.path.realpath which would resolve to the real
                # name (e.g. /…/libGL.so.1.7.0).  PyInstaller copies the
                # binary using the *source basename* as the destination
                # filename, and dlopen needs the SONAME to be present in
                # the runtime root.  When the source is a symlink chain
                # PyInstaller follows it and copies the real .so under
                # the SONAME basename, which is exactly what we want.
                result.append((path, '.'))
                seen.add(path)
                seen.add(os.path.realpath(path))
                break
    return result


binaries += _collect_linux_system_libs()

# z3-solver: bundle the native libz3 next to the python wrapper.  The
# runtime hook (pyinstaller_rthook_z3.py) sets Z3_LIBRARY_PATH so the
# python wrapper can find the right .so/.dll/.dylib at startup.
def _collect_z3_dynamic_libs():
    """Collect only the native z3 library for the current platform.

    Some z3-solver wheels carry native libraries for multiple platforms in
    the same package directory.  PyInstaller 5's macOS bindepend tries to
    parse every collected binary as Mach-O, so a stray Windows ``libz3.dll``
    aborts the build.  Keep the bundle platform-specific.
    """
    if sys.platform == 'win32':
        suffixes = ('.dll',)
    elif sys.platform == 'darwin':
        suffixes = ('.dylib',)
    else:
        suffixes = ('.so',)
    return [
        item
        for item in collect_dynamic_libs('z3', destdir='z3/lib')
        if item[0].lower().endswith(suffixes)
    ]


binaries += _collect_z3_dynamic_libs()


def _collect_mini_racer_runtime():
    """Collect MiniRacer's V8 shared library and sidecar data files.

    pyfcstm's SysDeSim SVG/PNG renderer runs inside MiniRacer.  Both the
    Python 3.7 ``py-mini-racer`` wheel and the newer ``mini-racer`` wheel
    expose the ``py_mini_racer`` package, but they resolve native files
    differently under PyInstaller:

    * py-mini-racer 0.6 looks for ``<_MEIPASS>/libmini_racer.<libc>.so``
      (or the platform equivalent).
    * mini-racer 0.14 looks under ``<_MEIPASS>/py_mini_racer`` and also
      needs ``icudtl.dat`` next to the shared library.

    Stage native libraries in both places and sidecar data files under the
    package directory so either wheel works in frozen builds.
    """
    import importlib

    runtime_binaries = []
    runtime_datas = []
    seen = set()
    try:
        mod = importlib.import_module('py_mini_racer')
    except ImportError:
        return runtime_binaries, runtime_datas

    package_dir = Path(getattr(mod, '__file__', '')).resolve().parent
    if not package_dir.is_dir():
        return runtime_binaries, runtime_datas

    for item in package_dir.rglob('*'):
        if not item.is_file() or '__pycache__' in item.parts:
            continue
        suffix = item.suffix.lower()
        if suffix in {'.py', '.pyc', '.pyo', '.pyi'}:
            continue
        src = str(item)
        rel_dir = item.parent.relative_to(package_dir.parent)
        for dest in ('.', str(rel_dir)):
            key = (src, dest)
            if key in seen:
                continue
            seen.add(key)
            entry = (src, dest)
            if suffix in {'.so', '.dylib', '.dll', '.pyd'}:
                runtime_binaries.append(entry)
            else:
                runtime_datas.append(entry)
    return runtime_binaries, runtime_datas


mini_racer_binaries, mini_racer_datas = _collect_mini_racer_runtime()
binaries += mini_racer_binaries
datas += mini_racer_datas

# pyfcstm ships data files (DSL grammar tokens, packaged template zips,
# verify design notes, etc.) inside its package; PyInstaller does not pick
# those up automatically because they are referenced through importlib
# resources / pkg_resources at runtime.
datas += collect_data_files('pyfcstm', includes=[
    '**/*.g4', '**/*.tokens', '**/*.interp',
    '**/*.json', '**/*.yaml', '**/*.yml',
    '**/*.zip', '**/*.png', '**/*.md',
    '**/*.js', '**/*.dat',
])

# qtawesome ships the FontAwesome / Material font files as package data.
datas += collect_data_files('qtawesome')

# Bundled PlantUML jar (Java *bytecode* — Java runtime is NOT bundled,
# the target machine must have `java` on PATH).
plantuml_jar = Path('docs/plantuml.jar')
if plantuml_jar.exists():
    datas.append((str(plantuml_jar), 'docs'))

# Sample DSL file used by the smoke-test routine to do an end-to-end
# parse + plantuml render check inside the frozen build.
for sample_dsl in [
    Path('docs/StateMachine.fcstm'),
    Path('docs/topology_controller_all_in_one.fcstm'),
]:
    if sample_dsl.exists():
        datas.append((str(sample_dsl), 'docs'))

# Help PyInstaller discover modules that get imported via string lookups
# inside pyfcstm / hbutils, plus a handful of stdlib modules that PyQt5
# imports lazily.
hiddenimports = []
hiddenimports += collect_submodules('pyfcstm')
hiddenimports += collect_submodules('plantumlcli')
hiddenimports += collect_submodules('hbutils')
hiddenimports += collect_submodules('py_mini_racer')
# App-level submodules — several are loaded by name (importlib/subprocess
# strings inside dialog handlers) so PyInstaller can't see them via static
# analysis.
hiddenimports += collect_submodules('app')
# Document export deps — only referenced from inside lazily-loaded utility
# modules, so PyInstaller misses them too.
hiddenimports += collect_submodules('openpyxl')
hiddenimports += collect_submodules('docx')
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
