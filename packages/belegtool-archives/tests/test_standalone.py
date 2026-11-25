"""The `belegtool_archives` package (packages/belegtool-archives) must stay extractable into its own repo:
it may not import the host application (`infra`, `core`, `formats`, `services`, `universal_importer`...).
Static (AST) check + an isolated-interpreter import without the app on sys.path."""

import ast
import shutil
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "belegtool_archives"
HOST_PACKAGES = {"infra", "core", "version_info", "formats", "services", "host",
                 "universal_importer", "webui", "datev"}
LIBRARY_FILES = sorted(PKG.glob("*.py"))


def _imported_roots(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):  # also lazy imports inside functions
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def test_library_files_exist():
    assert {p.name for p in LIBRARY_FILES} >= {"__init__.py", "archives.py", "limits.py"}


def test_library_has_no_host_imports():
    offenders = {p.name: sorted(set(_imported_roots(p)) & HOST_PACKAGES) for p in LIBRARY_FILES}
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, offenders


def test_logger_name():
    src = (PKG / "archives.py").read_text(encoding="utf-8")
    assert 'logging.getLogger("belegtool_archives")' in src


def test_import_without_host_packages(tmp_path):
    shutil.copytree(PKG, tmp_path / "belegtool_archives",
                    ignore=shutil.ignore_patterns("__pycache__"))
    code = (
        f"import sys; sys.path.insert(0, {str(tmp_path)!r})\n"
        "import belegtool_archives, belegtool_archives.archives, belegtool_archives.limits\n"
        "bad = [m for m in ('infra', 'core', 'version_info', 'universal_importer') if m in sys.modules]\n"
        "assert not bad, bad\n"
    )
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
