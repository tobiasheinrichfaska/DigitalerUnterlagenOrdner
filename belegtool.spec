# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules, collect_all, collect_dynamic_libs, collect_data_files

PROJECT_DIR = SPECPATH  # injected by PyInstaller: the spec's directory

# Licence texts of every bundled dependency (licenses/<dist>/..., generated; NOT checked in, see .gitignore).
# build.ps1 runs the generator BEFORE PyInstaller; this fallback covers a direct `pyinstaller belegtool.spec`.
# A distribution without a findable licence text makes the generator (and so this build) fail on purpose.
LICENSES_DIR = os.path.join(PROJECT_DIR, 'licenses')
if not os.path.isdir(LICENSES_DIR):
    import subprocess
    import sys
    subprocess.check_call([sys.executable, os.path.join(PROJECT_DIR, 'scripts', 'gen_third_party_notices.py')])

reportlab_imports = collect_submodules('reportlab')
xhtml2pdf_imports = collect_submodules('xhtml2pdf')
core_imports = collect_submodules('core')
# datev-dokab: installed package, imported lazily in DATEV mode only (invisible to static analysis)
datev_imports = collect_submodules('datev')
# belegtool-archives: installed package, reached via the lazily imported universal_importer / formats.pdf_storage
archives_imports = collect_submodules('belegtool_archives')
# belegtool-compress: installed package, lazily imported by core.engine / host._prewarm via formats.compress_pdf_bytes
compress_imports = collect_submodules('belegtool_compress')

# PDF rasterizer: pypdfium2 + its native pdfium DLL (pypdfium2_raw/pdfium.dll) and the version.json files it reads at
# import. PyMuPDF (fitz) is NOT bundled any more (AGPL; guarded by tests/test_no_agpl_pdf_deps.py).
pdfium_binaries = collect_dynamic_libs('pypdfium2_raw') + collect_dynamic_libs('pypdfium2')
pdfium_datas = collect_data_files('pypdfium2') + collect_data_files('pypdfium2_raw')
pdfium_imports = collect_submodules('pypdfium2') + collect_submodules('pypdfium2_raw')

# New GUI stack: pywebview + its Windows EdgeChromium backend (pythonnet/clr).
# collect_all grabs the package submodules, data files and the native DLLs
# (WebView2Loader, Python.Runtime, …) that the backend loads at runtime.
webview_datas, webview_bins, webview_hidden = collect_all('webview')
pynet_datas, pynet_bins, pynet_hidden = collect_all('pythonnet')
clrloader_datas, clrloader_bins, clrloader_hidden = collect_all('clr_loader')

a = Analysis(
    ['host.py'],
    pathex=[PROJECT_DIR],
    binaries=webview_bins + pynet_bins + clrloader_bins + pdfium_binaries,
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
        (LICENSES_DIR, 'licenses'),
    ] + webview_datas + pynet_datas + clrloader_datas + pdfium_datas,
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'pi_heif',
        '_pi_heif',
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
    ] + reportlab_imports + xhtml2pdf_imports + core_imports + datev_imports + archives_imports + compress_imports + pdfium_imports
      + webview_hidden + pynet_hidden + clrloader_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # extract_msg (GPLv3) / RTFDE (LGPL) were replaced by the own olefile reader -- never bundle them again
    # (guarded by tests/test_no_gpl_msg_deps.py). PyMuPDF (AGPL/Artifex) is a dev-only test oracle: never bundle it
    # (guarded by tests/test_no_agpl_pdf_deps.py).
    excludes=['pytest', 'unittest', 'extract_msg', 'RTFDE', 'fitz', 'pymupdf'],
    noarchive=False,
    # LGPL relinking/exchangeability (docs/licence-audit.md, "LGPL: Austausch/Relinking"): the pure-Python LGPL libraries
    # are collected as plain .py files in _internal/ instead of .pyc inside the PYZ archive, so a user can replace them.
    # 'py' (NOT 'pyz+py': the PYZ copy would win at import). Verified on Linux with PyInstaller 6.20.0; Windows: unverified.
    module_collection_mode={'svglib': 'py', 'bidi': 'py'},
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
