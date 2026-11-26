# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules, collect_all

PROJECT_DIR = SPECPATH  # injected by PyInstaller: the spec's directory

reportlab_imports = collect_submodules('reportlab')
xhtml2pdf_imports = collect_submodules('xhtml2pdf')
core_imports = collect_submodules('core')
# datev-dokab: installed package, imported lazily in DATEV mode only (invisible to static analysis)
datev_imports = collect_submodules('datev')
# belegtool-archives: installed package, reached via the lazily imported universal_importer / formats.pdf_storage
archives_imports = collect_submodules('belegtool_archives')
# belegtool-compress: installed package, lazily imported by core.engine / host._prewarm via formats.compress_pdf_bytes
compress_imports = collect_submodules('belegtool_compress')

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
        # Licence / notice texts (AGPL full text, owner notice, third-party notices).
        # NOT LICENSE_COMMERCIAL.md: commercial terms are not part of the AGPL distribution.
        # Note: with PyInstaller >= 6 onedir, dest '.' lands in _internal/; build_msix.ps1
        # additionally copies them next to BelegTool.exe.
        (os.path.join(PROJECT_DIR, 'COPYING'), '.'),
        (os.path.join(PROJECT_DIR, 'LICENSE'), '.'),
        (os.path.join(PROJECT_DIR, 'THIRD_PARTY_NOTICES.md'), '.'),
    ] + webview_datas + pynet_datas + clrloader_datas,
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'pi_heif',
        '_pi_heif',
        'fitz',
        'pikepdf',
        'pypdf',
        'pypdf.errors',
        'pypdf.filters',
        'pypdf.generic',
        'pypdf.xmp',
        # .msg reader of belegtool_archives (olefile BSD-2, compressed-rtf MIT; imported in a try/except)
        'olefile',
        'compressed_rtf',
        'formats.pdf_node',
        'formats.pdf_storage',
        'formats.compress_pdf_bytes',
        'formats.toc_export',
        'universal_importer',
        'universal_importer.converters',
        'universal_importer.importer',
        'universal_importer.archives',
        'version_info',
        'infra.log_config',
        'infra.tools',
        # React/pywebview GUI
        'host',
        'clr',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
    ] + reportlab_imports + xhtml2pdf_imports + core_imports + datev_imports + archives_imports + compress_imports
      + webview_hidden + pynet_hidden + clrloader_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # extract_msg (GPLv3) / RTFDE (LGPL) were replaced by the own olefile reader -- never bundle them again
    # (guarded by tests/test_no_gpl_msg_deps.py).
    excludes=['pytest', 'unittest', 'extract_msg', 'RTFDE'],
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
    # UPX OFF: packing the managed .NET assembly (pythonnet's Python.Runtime.dll) and
    # native DLLs (WebView2Loader) can make them unloadable and trips AV heuristics.
    # The size win isn't worth the corruption/false-positive risk.
    upx=False,
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
    upx=False,  # see EXE() above — UPX can corrupt the .NET/native DLLs + trips AV
    upx_exclude=[],
    name='BelegTool',
)
