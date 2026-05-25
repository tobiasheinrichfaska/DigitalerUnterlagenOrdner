# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

tkdnd_src = 'AppData/Local/Programs/Python/Python312/Lib/site-packages/tkinterdnd2/tkdnd'
PROJECT_DIR = os.path.abspath('c:/skripte/private/DigitalerUnterlagenOrdner')

reportlab_imports = collect_submodules('reportlab')
xhtml2pdf_imports = collect_submodules('xhtml2pdf')

a = Analysis(
    ['belegtool_main.py'],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=[
        (tkdnd_src, 'tkinterdnd2/tkdnd'),
    ],
    hiddenimports=[
        'tkinterdnd2',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'fitz',
        'pikepdf',
        'pypdf',
        'pypdf.errors',
        'pypdf.filters',
        'pypdf.generic',
        'pypdf.xmp',
        'pdf_node',
        'pdf_storage',
        'compress_pdf_bytes',
        'view_preview',
        'view_tree',
        'panel_controls',
        'universal_importer',
        'status_display',
        'version_info',
        'log_config',
        'tools',
        'preview_page',
        'toc_export',
    ] + reportlab_imports + xhtml2pdf_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'unittest'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PDF-Storage',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
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
    upx=True,
    upx_exclude=[],
    name='PDF-Storage',
)
