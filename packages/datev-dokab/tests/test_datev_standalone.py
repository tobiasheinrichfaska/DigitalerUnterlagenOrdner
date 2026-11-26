# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""The `datev` package (packages/datev-dokab) must stay extractable into its own repo: it may not import the
host application (`infra`, `core`, `version_info`, `formats`, `services`, `host`...).
Static (AST) check + an isolated-interpreter import without the app on sys.path."""

import ast
import shutil
import subprocess
import sys
from pathlib import Path

DATEV = Path(__file__).resolve().parent.parent / "datev"
HOST_PACKAGES = {"infra", "core", "version_info", "formats", "services", "host",
                 "universal_importer", "webui"}
LIBRARY_FILES = sorted(DATEV.glob("*.py"))


def _imported_roots(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):  # also lazy imports inside functions
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def test_library_has_no_host_imports():
    offenders = {p.name: sorted(set(_imported_roots(p)) & HOST_PACKAGES) for p in LIBRARY_FILES}
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, offenders


def test_import_without_host_packages(tmp_path):
    shutil.copytree(DATEV, tmp_path / "datev",
                    ignore=shutil.ignore_patterns("__pycache__"))
    code = (
        f"import sys; sys.path.insert(0, {str(tmp_path)!r})\n"
        "import datev, datev.inapp, datev.writeback, datev.provenance, datev.client\n"
        "bad = [m for m in ('infra', 'core', 'version_info') if m in sys.modules]\n"
        "assert not bad, bad\n"
        "from datev import _log\n"
        "got = []\n"
        "_log.set_diag(got.append)\n"
        "_log.diag('x')\n"
        "assert got == ['x']\n"
        "_log.set_diag(None)\n"
        "_log.diag('ignored')  # default is a no-op\n"
        "assert _log.logger.name == 'datev'\n"
    )
    # -I: isolated mode (ignores PYTHONPATH/cwd/user site) -> the app's `infra` cannot leak in
    r = subprocess.run([sys.executable, "-I", "-c", code], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
