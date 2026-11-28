# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Windows path/name semantics (audit z4 WP-1..WP-4), checked identically on Linux via ntpath."""
import base64
import ntpath
import os

import sys
import types

import pytest

for _m in ("pythoncom", "win32com", "win32com.client"):
    if _m not in sys.modules:
        try:
            __import__(_m)
        except ImportError:
            sys.modules[_m] = types.ModuleType(_m)
if not hasattr(sys.modules["win32com"], "client"):
    sys.modules["win32com"].client = sys.modules["win32com.client"]

from core.api import CoreApi, sweep_stale_view_dirs


def _record_import(monkeypatch):
    seen = []
    api = CoreApi()

    def fake_import_paths(session, paths, parent_id=None, index=None):
        seen.extend(paths)
        return {"ok": True}
    monkeypatch.setattr(api, "import_paths", fake_import_paths)
    return api, seen


@pytest.mark.parametrize("name", ["D:evil.pdf", "d:autorun.inf", "C:foo.pdf", "a:b:c.pdf",
                                  "..\\..\\x.pdf", "a\\b.pdf", ".hidden.pdf", "x.pdf:stream",
                                  "\\\\?\\C:\\x.pdf", "con.pdf"])
def test_import_bytes_stays_inside_tmpdir(monkeypatch, name):
    api, seen = _record_import(monkeypatch)
    captured = {}
    import tempfile
    real = tempfile.mkdtemp

    def mk(*a, **k):
        captured["d"] = real(*a, **k)
        return captured["d"]
    monkeypatch.setattr(tempfile, "mkdtemp", mk)
    api.import_bytes("s", name, base64.b64encode(b"%PDF").decode())
    (path,) = seen
    assert os.path.dirname(os.path.realpath(path)) == os.path.realpath(captured["d"])
    base = os.path.basename(path)
    # identical verdict under Windows semantics
    assert ntpath.splitdrive(base)[0] == ""
    assert not any(c in base for c in '<>:"|?*\\/')
    assert not base.startswith(".")


def test_sweep_ignores_glob_metacharacters(tmp_path):
    root = tmp_path / "Max[1]"
    root.mkdir()
    d = root / "beleg_view_ab12cd34"
    d.mkdir()
    os.utime(d, (1, 1))
    removed = sweep_stale_view_dirs(root=str(root))
    assert removed == [str(d)] and not d.exists()


@pytest.mark.parametrize("stem", ["²", "٣٤٥", "１２３", "①"])
def test_open_tolerates_non_ascii_digit_checkout_names(tmp_path, stem):
    guid = "0a0a0a02-1111-2222-3333-444444444444"
    d = tmp_path / guid
    d.mkdir()
    # any readable file will do; the name decides the checkout routing
    from tests.test_datev_coreapi import _pdf
    f = d / f"{stem}.pdf"
    f.write_bytes(_pdf(1))
    api = CoreApi()
    api._datev_mode = True
    r = api.open(path=str(f))
    assert r.get("ok") is not False


def test_safe_filename_windows_hardening():
    f = CoreApi._safe_filename
    for bad in ("NUL .pdf", "nul.tar.gz", "COM¹", "COM²", "com³.txt", "LPT¹", "LPT³ .x", "COM1 .txt",
                "CON  ", " NUL"):
        assert f(bad, "Export") == "Export", bad
    for ch in ("\t", "\n", "\x1f", "\x7f", "\x00", "\u202e", "\u200b", "\ufeff"):
        out = f(f"a{ch}b", "Export")
        assert out == "ab" or out == "a_b", (ch, out)
        assert ch not in out
    assert f("a. . b. ", "X") == "a. . b"  # R13-2: inner spaces kept
    assert f("Übergrößenträger ÄÖ", "X") == "Übergrößenträger ÄÖ"
    assert len(f("x" * 500, "X")) <= 120
    assert len(f("x" * 500, "X", dir_len=200, ext_len=10)) <= 240 - 200 - 10 - 1
    assert f("x" * 500, "X", dir_len=300, ext_len=10) == "X"
