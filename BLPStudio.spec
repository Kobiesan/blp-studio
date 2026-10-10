# Portable build recipe. No machine-specific paths.
a = Analysis(['blp_studio.py'], pathex=[], binaries=[], datas=[('Application.png','.'),('VERSION','.'),('LICENSE','.'),('ASSETS.md','.'),('THIRD_PARTY_NOTICES.md','.'),('licenses','licenses')],
             hiddenimports=['viewer'], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['numpy'], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='BLPStudio',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
          upx_exclude=[], runtime_tmpdir=None, console=False,
          disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None,icon='Application.ico')
