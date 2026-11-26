# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Licence texts of every dependency ship with the bundle (scripts/gen_third_party_notices.py).

* The generator is run against the venv the tests run in (offline, stdlib only).
* Per distribution of ``requirements.txt``: an entry in the generated table AND at least one licence file.
  A distribution that is not installed in THIS venv is SKIPPED with an explicit reason (visible with ``-rs``) -
  never silently green; the Windows build venv has all of them (``build.ps1`` runs the generator there).
* A distribution without a findable licence text is an ERROR (exit code 1) unless it is on the documented exception list.
* The bundle wiring (spec datas, MSIX layout, build.ps1 step, .gitignore) is pinned as text.
"""
import importlib.metadata as md
import re
from pathlib import Path

import pytest

from scripts import gen_third_party_notices as gen

ROOT = Path(__file__).resolve().parent.parent
REQ_NAMES = gen.parse_requirements(ROOT / "requirements.txt")


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out = tmp_path_factory.mktemp("gen")
    lic, notices = out / "licenses", out / "THIRD_PARTY_NOTICES.md"
    notices.write_text("# head\n\nhand written\n", encoding="utf-8")
    rc = gen.main(["--out-dir", str(lic), "--notices", str(notices), "--no-npm"])
    return rc, lic, notices.read_text(encoding="utf-8")


def _installed(name):
    try:
        md.distribution(name)
        return True
    except md.PackageNotFoundError:
        return False


def test_requirements_parse_includes_pins_and_local_packages():
    canon = {gen.canon(n) for n in REQ_NAMES}
    assert {"pypdfium2", "pillow", "pikepdf", "olefile", "datev-dokab", "belegtool-archives", "belegtool-compress"} <= canon
    assert "pyinstaller" in canon


@pytest.mark.parametrize("name", REQ_NAMES)
def test_every_requirement_has_a_table_entry_and_a_licence_file(generated, name):
    if not _installed(name):
        pytest.skip(f"{name} is not installed in this test venv - its licence text can only be verified in the build venv "
                    f"(NOT verified here)")
    rc, lic, text = generated
    key = gen.canon(name)
    assert re.search(rf"^\| {re.escape(md.distribution(name).metadata['Name'])} \|", text, re.M), f"no table row for {name}"
    d = lic / key
    files = [p for p in d.rglob("*") if p.is_file()] if d.is_dir() else []
    assert files or key in gen.NO_LICENSE_TEXT_EXCEPTIONS, f"no licence file collected for {name}"


def test_generator_succeeds_for_this_venv(generated):
    rc, lic, text = generated
    assert rc == 0
    assert gen.BEGIN in text and gen.END in text
    assert text.startswith("# head\n\nhand written\n"), "the hand-written part must never be touched"


def test_generator_is_reproducible(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        d.mkdir()
        (d / "N.md").write_text("# x\n", encoding="utf-8")
        gen.main(["--out-dir", str(d / "l"), "--notices", str(d / "N.md"), "--no-npm"])
    assert (a / "N.md").read_text(encoding="utf-8") == (b / "N.md").read_text(encoding="utf-8")
    assert sorted(p.relative_to(a / "l").as_posix() for p in (a / "l").rglob("*")) == \
        sorted(p.relative_to(b / "l").as_posix() for p in (b / "l").rglob("*"))


def test_pypdfium2_build_licenses_are_collected(generated):
    if not _installed("pypdfium2"):
        pytest.skip("pypdfium2 not installed in this venv - pdfium/Skia BUILD_LICENSES not verified here")
    _, lic, _ = generated
    assert (lic / "pypdfium2" / "BUILD_LICENSES" / "pdfium.txt").is_file()


def _fake_site(tmp_path, with_license: bool):
    root = tmp_path / "repo"
    site = tmp_path / "site"
    (root).mkdir()
    (site / "fakepkg_x-1.0.dist-info").mkdir(parents=True)
    (root / "requirements.txt").write_text("fakepkg-x==1.0\n", encoding="utf-8")
    (site / "fakepkg_x-1.0.dist-info" / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: fakepkg-x\nVersion: 1.0\nLicense-Expression: MIT\n", encoding="utf-8")
    if with_license:
        (site / "fakepkg_x-1.0.dist-info" / "licenses").mkdir()
        (site / "fakepkg_x-1.0.dist-info" / "licenses" / "LICENSE").write_text("MIT text", encoding="utf-8")
    return root, site


def test_distribution_without_licence_text_is_an_error(tmp_path, capsys):
    root, site = _fake_site(tmp_path, with_license=False)
    rc = gen.main(["--root", str(root), "--path", str(site), "--no-npm", "--out-dir", str(tmp_path / "l"),
                   "--notices", str(tmp_path / "N.md")])
    assert rc == 1
    assert "fakepkg-x" in capsys.readouterr().err
    assert "FEHLT" in (tmp_path / "N.md").read_text(encoding="utf-8")


def test_exception_list_with_reason_is_honoured(tmp_path, monkeypatch):
    root, site = _fake_site(tmp_path, with_license=False)
    monkeypatch.setitem(gen.NO_LICENSE_TEXT_EXCEPTIONS, "fakepkg-x", "test reason")
    rc = gen.main(["--root", str(root), "--path", str(site), "--no-npm", "--out-dir", str(tmp_path / "l"),
                   "--notices", str(tmp_path / "N.md")])
    assert rc == 0
    assert "test reason" in (tmp_path / "N.md").read_text(encoding="utf-8")


def test_licence_file_is_copied_when_present(tmp_path):
    root, site = _fake_site(tmp_path, with_license=True)
    rc = gen.main(["--root", str(root), "--path", str(site), "--no-npm", "--out-dir", str(tmp_path / "l"),
                   "--notices", str(tmp_path / "N.md")])
    assert rc == 0
    assert (tmp_path / "l" / "fakepkg-x" / "LICENSE").read_text(encoding="utf-8") == "MIT text"


def test_every_exception_has_a_reason():
    assert all(r.strip() for r in gen.NO_LICENSE_TEXT_EXCEPTIONS.values())


def test_npm_runtime_packages_are_listed_and_marked_when_not_captured(tmp_path):
    webui = tmp_path / "webui"
    webui.mkdir()
    (webui / "package-lock.json").write_text(
        '{"packages": {"": {}, "node_modules/foo": {"version": "1.0.0", "license": "MIT"},'
        ' "node_modules/devonly": {"version": "2.0.0", "dev": true},'
        ' "node_modules/opt": {"version": "3.0.0", "optional": true}}}', encoding="utf-8")
    entries, texts = gen.collect_npm(webui)
    assert [(e.name, e.version, e.license, e.captured) for e in entries] == [("foo", "1.0.0", "MIT", False)]
    assert "nicht erfasst" in gen.render_generated({}, entries)
    (webui / "node_modules" / "foo").mkdir(parents=True)
    (webui / "node_modules" / "foo" / "LICENSE").write_text("x", encoding="utf-8")
    entries, texts = gen.collect_npm(webui)
    assert entries[0].captured and entries[0].files == ["LICENSE"]


# ------------------------------------------------------------------------------------------------ bundle wiring

def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_spec_bundles_licenses_folder_and_notices():
    spec = _read("belegtool.spec")
    assert "THIRD_PARTY_NOTICES.md" in spec
    assert "(LICENSES_DIR, 'licenses')" in spec
    assert "gen_third_party_notices" in spec, "spec must fail loudly when licenses/ was not generated"


def test_msix_layout_copies_the_licenses_folder():
    ps = _read("packaging/build_msix.ps1")
    assert "licenses" in ps and "Copy-Item" in ps
    assert re.search(r"licenses", ps.split("# Licence texts", 1)[1])


def test_build_script_generates_licenses_before_pyinstaller():
    ps = _read("build.ps1")
    i, j = ps.find("gen_third_party_notices.py"), ps.find("pyinstaller.exe")
    assert 0 < i < j, "build.ps1 must run the generator before PyInstaller"


def test_generated_licenses_folder_is_not_committed():
    gi = _read(".gitignore").splitlines()
    assert "/licenses/" in gi


def test_spec_collects_pure_python_lgpl_libs_as_py_files_not_in_the_pyz():
    """LGPL exchangeability: svglib (LGPL-3.0-or-later, pure Python) must lie in _internal/ as .py, not as .pyc inside the
    PYZ. 'py' only - 'pyz+py' would keep the PYZ copy winning at import time. (Effect on Windows: unverified.)"""
    spec = _read("belegtool.spec")
    m = re.search(r"module_collection_mode\s*=\s*\{([^}]*)\}", spec)
    assert m, "module_collection_mode missing in belegtool.spec"
    modes = dict(re.findall(r"'([\w.]+)'\s*:\s*'([\w+]+)'", m.group(1)))
    assert modes.get("svglib") == "py"
    assert modes.get("bidi") == "py"
    assert "pyz" not in modes.values()


def test_windows_runbook_checks_licenses_and_svglib_py():
    ps = _read("scripts/windows_testlauf.ps1")
    assert "licenses" in ps and "svglib" in ps
    md_ = _read("docs/windows-pc-testlauf.md")
    assert "licenses" in md_ and "svglib" in md_
