# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules, collect_all

PROJECT_DIR = SPECPATH  # injected by PyInstaller: the spec's directory

reportlab_imports = collect_submodules('reportlab')
xhtml2pdf_imports = collect_submodules('xhtml2pdf')
core_imports = collect_submodules('core')

# New GUI stack: pywebview + its Windows EdgeChromium backend (pythonnet/clr).
# collect_all grabs the package submodules, data files and the native DLLs
# (WebView2Loader, Python.Runtime, …) that the backend loads at runtime.
webview_datas, webview_bins, webview_hidden = collect_all('webview')
pynet_datas, pynet_bins, pynet_hidden = collect_all('pythonnet')
clrloader_datas, clrloader_bins, clrloader_hidden = collect_all('clr_loader')

a = Analysis(
    ['host.py'],
    pathex=[PROJECT_DIR],
    binaries=webview_bins + pynet_bins + clrloader_bins,
    datas=[
        # React production assets the pywebview host loads (PROD_INDEX).
        (os.path.join(PROJECT_DIR, 'webui', 'dist'), os.path.join('webui', 'dist')),
    ] + webview_datas + pynet_datas + clrloader_datas,
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'fitz',
        'pikepdf',
        'pypdf',
        'pypdf.errors',
        'pypdf.filters',
        'pypdf.generic',
        'pypdf.xmp',
        'formats.pdf_node',
        'formats.pdf_storage',
        'formats.compress_pdf_bytes',
        'formats.toc_export',
        'universal_importer',
        'universal_importer.converters',
        'universal_importer.importer',
        'universal_importer.archives',
        'version_info',
        'log_config',
        'tools',
        # React/pywebview GUI
        'host',
        'clr',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
    ] + reportlab_imports + xhtml2pdf_imports + core_imports
      + webview_hidden + pynet_hidden + clrloader_hidden,
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
    name='BelegTool',
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
    icon=os.path.join(PROJECT_DIR, 'assets', 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BelegTool',
)
