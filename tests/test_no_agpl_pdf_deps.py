"""Licence guard: the shipped product must not contain PyMuPDF/MuPDF (AGPL-3.0 / Artifex commercial).

PyMuPDF was the last "red" dependency of docs/licence-audit.md. It was replaced on 2026-11-26 by pypdfium2
(BSD-3-Clause / Apache-2.0, bundled pdfium) behind the rasterizer port ``belegtool_compress.raster``
(measurements: docs/pdfium-spike.md). PyMuPDF survives ONLY as a development/test oracle (requirements-dev.txt,
the ``oracle`` extra of belegtool-compress, tests/ and scripts/ fixture generators) - none of which is shipped.

This test fails when it comes back into the product: requirements.txt, the package metadata, an import in
production code, or a PyInstaller spec that bundles it / forgets pdfium's DLL.
"""
import ast
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("fitz", "pymupdf")                                  # compared after lower() and "-" / "." -> "_"
# Production code = everything except dev-only places: tests, build/fixture scripts, the web UI and tooling dirs.
_SKIP_DIRS = {".git", ".claude", "node_modules", "dist", "build", ".build_venv", ".venv", "venv", "__pycache__",
              ".pytest_cache", "vendor", "import-archiv", "tests", "scripts", "webui", "manual_tests"}


def _norm(name: str) -> str:
    return name.lower().replace("-", "_").replace(".", "_")


def _is_forbidden(name: str) -> bool:
    return _norm(name) in FORBIDDEN


def _production_python_files():
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


def test_requirements_do_not_list_pymupdf():
    bad = [n for n in _requirement_names(ROOT / "requirements.txt") if _is_forbidden(n)]
    assert not bad, f"AGPL PDF engine in requirements.txt (docs/licence-audit.md): {bad}"


def test_requirements_pin_pypdfium2():
    names = {_norm(n) for n in _requirement_names(ROOT / "requirements.txt")}
    assert "pypdfium2" in names
    line = next(l for l in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
                if _norm(l).startswith("pypdfium2"))
    assert "==" in line, "pypdfium2 must be pinned (the bundled pdfium binary is part of the product)"


def test_pymupdf_is_dev_only_oracle():
    dev = {_norm(n) for n in _requirement_names(ROOT / "requirements-dev.txt")}
    assert "pymupdf" in dev, "tests/fixture generators and the parity oracle need PyMuPDF in requirements-dev.txt"


def test_compress_package_depends_on_pdfium_not_pymupdf():
    meta = tomllib.loads((ROOT / "packages" / "belegtool-compress" / "pyproject.toml").read_text(encoding="utf-8"))
    deps = {_norm(re.match(r"[A-Za-z0-9_.\-]+", d).group(0)) for d in meta["project"]["dependencies"]}
    assert "pypdfium2" in deps and not (deps & set(FORBIDDEN)), deps
    oracle = {_norm(re.match(r"[A-Za-z0-9_.\-]+", d).group(0))
              for d in meta["project"]["optional-dependencies"]["oracle"]}
    assert oracle == {"pymupdf"}


def test_no_other_package_metadata_depends_on_it():
    for pyproject in (ROOT / "packages").glob("*/pyproject.toml"):
        if pyproject.parent.name == "belegtool-compress":
            continue
        text = _norm(pyproject.read_text(encoding="utf-8"))
        for f in FORBIDDEN:
            assert f not in text, f"{pyproject} mentions {f}"


def test_no_production_source_imports_pymupdf():
    offenders = []
    for path in _production_python_files():
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
    assert not offenders, f"fitz/pymupdf imported by production code (AGPL, docs/licence-audit.md): {offenders}"


def _spec():
    return (ROOT / "belegtool.spec").read_text(encoding="utf-8")


def test_pyinstaller_spec_excludes_pymupdf_and_does_not_bundle_it():
    spec = _spec()
    excludes = re.search(r"excludes\s*=\s*\[(.*?)\]", spec, re.S)
    assert excludes, "belegtool.spec has no excludes list"
    for mod in ("fitz", "pymupdf"):
        assert f"'{mod}'" in excludes.group(1), f"{mod} must be in the spec excludes"
    hidden = re.search(r"hiddenimports\s*=\s*\[(.*?)\]\s*\+", spec, re.S)
    assert hidden and "'fitz'" not in hidden.group(1) and "'pymupdf'" not in hidden.group(1)


def test_pyinstaller_spec_collects_pdfium_and_its_dll():
    spec = _spec()
    assert "pypdfium2" in spec and "pypdfium2_raw" in spec
    assert "collect_dynamic_libs" in spec and "collect_data_files" in spec   # pdfium.dll lives in pypdfium2_raw/
