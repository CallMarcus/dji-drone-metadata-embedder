# -*- mode: python ; coding: utf-8 -*-

__version__ = "v1.1.2"
a = Analysis(
    ['_pyinstaller_entry.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=['dji_metadata_embedder', 'dji_metadata_embedder.cli', 'dji_metadata_embedder.core', 'dji_metadata_embedder.telemetry_converter', 'dji_metadata_embedder.metadata_check', 'click', 'rich'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='dji-embed',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
