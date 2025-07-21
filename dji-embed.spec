# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/dji_metadata_embedder/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/dji_metadata_embedder/templates', 'templates'),
    ],
    hiddenimports=[
        'dji_metadata_embedder',
        'dji_metadata_embedder.cli',
        'dji_metadata_embedder.core',
        'dji_metadata_embedder.parsers',
        'dji_metadata_embedder.telemetry_converter',
        'dji_metadata_embedder.metadata_check',
        'dji_metadata_embedder.wizard',
        'rich',
        'click',
        'tqdm',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
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
