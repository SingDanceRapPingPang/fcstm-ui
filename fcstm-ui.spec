# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs


block_cipher = None

datas = []
binaries = []
runtime_hooks = ['pyinstaller_rthook_z3.py']
plantuml_jar = Path('docs/plantuml.jar')
if plantuml_jar.exists():
    datas.append((str(plantuml_jar), 'docs'))
binaries += collect_dynamic_libs('z3', destdir='z3/lib')


a = Analysis(['main.py'],
             pathex=[],
             binaries=binaries,
             datas=datas,
             hiddenimports=['ipaddress'],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=runtime_hooks,
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          name='fcstm-ui',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )
