# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Licence guard: the Outlook .msg import must stay free of GPL/LGPL code (docs/licence-audit.md).

extract-msg (GPLv3) and its dependency RTFDE (LGPLv3) were replaced on 2026-11-26 by the own reader in
packages/belegtool-archives/belegtool_archives/msg_reader.py (olefile BSD-2 + compressed-rtf MIT). This test
fails when one of them comes back: in requirements.txt, in any package metadata of the repo, as an import
anywhere in the Python sources, or when the PyInstaller spec stops excluding them from the bundle.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("extract_msg", "rtfde")                     # compared after lower() and "-" / "." -> "_"
_SKIP_DIRS = {".git", ".claude", "node_modules", "dist", "build", ".build_venv", ".venv", "venv", "__pycache__",
              ".pytest_cache", "vendor", "import-archiv"}


def _norm(name: str) -> str:
    return name.lower().replace("-", "_").replace(".", "_")


def _is_forbidden(name: str) -> bool:
    n = _norm(name)
    return any(n == f or n.startswith(f + "_") for f in FORBIDDEN)


def _python_files():
    for p in ROOT.rglob("*.py"):
        parts = p.relative_to(ROOT).parts
        if not (set(parts) & _SKIP_DIRS) and not any(part.endswith(".egg-info") for part in parts):
            yield p


def _requirement_names(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", ".", "/")):
            continue
        m = re.match(r"[A-Za-z0-9_.\-]+", line)
        if m:
            yield m.group(0)


def test_requirements_do_not_list_extract_msg_or_rtfde():
    bad = [n for n in _requirement_names(ROOT / "requirements.txt") if _is_forbidden(n)]
    assert not bad, f"GPL/LGPL .msg dependency in requirements.txt (docs/licence-audit.md): {bad}"


def test_requirements_pin_the_permissive_msg_readers():
    names = {_norm(n) for n in _requirement_names(ROOT / "requirements.txt")}
    assert {"olefile", "compressed_rtf"} <= names


def test_package_metadata_does_not_depend_on_them():
    for pyproject in (ROOT / "packages").glob("*/pyproject.toml"):
        text = _norm(pyproject.read_text(encoding="utf-8"))
        for f in FORBIDDEN:
            assert f not in text, f"{pyproject} mentions {f}"


def test_no_python_source_imports_them():
    offenders = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                mods = [node.module]
            elif (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
                  and isinstance(node.args[0].value, str)
                  and getattr(node.func, "attr", getattr(node.func, "id", "")) in ("import_module", "__import__")):
                mods = [node.args[0].value]
            if any(_is_forbidden(m.split(".")[0]) for m in mods):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, f"extract_msg/RTFDE imported (GPLv3/LGPL, docs/licence-audit.md): {offenders}"


def test_pyinstaller_spec_excludes_them():
    spec = (ROOT / "belegtool.spec").read_text(encoding="utf-8")
    excludes = re.search(r"excludes\s*=\s*\[(.*?)\]", spec, re.S)
    assert excludes, "belegtool.spec has no excludes list"
    for mod in ("extract_msg", "RTFDE"):
        assert f"'{mod}'" in excludes.group(1), f"{mod} must stay in the spec excludes"
