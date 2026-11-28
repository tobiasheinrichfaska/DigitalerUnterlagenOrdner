# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Audit v3 S-2..S-7 regressions (formats/infra/services/host)."""
import importlib
import io
import json
import subprocess
import sys
import zipfile

import pikepdf

import host
from infra.settings import DEFAULTS, load_settings
from services import variant_blobs, variant_store


def test_s2_failed_embed_leaves_saved_file_intact(tmp_path, monkeypatch):
    p = tmp_path / "a.belegtool"
    pdf = pikepdf.new()
    pdf.add_blank_page()
    pdf.save(p)
    orig = p.read_bytes()
    monkeypatch.setattr(variant_store, "_collect_variant_blobs", lambda *a, **k: {"x": b"y"})

    real_save = pikepdf.Pdf.save

    def boom(self, target, *a, **k):
        with open(target, "wb") as f:
            f.write(b"%PDF-partial")
        raise OSError("disk full")

    monkeypatch.setattr(pikepdf.Pdf, "save", boom)
    assert variant_store.embed_variants(str(p), None, None) == 0
    monkeypatch.setattr(pikepdf.Pdf, "save", real_save)
    assert p.read_bytes() == orig
    assert [x.name for x in tmp_path.iterdir()] == ["a.belegtool"]


def test_s3_invalid_utf8_settings_load_defaults(tmp_path):
    p = tmp_path / "s.json"
    p.write_bytes(b"\xff\xfe\x00b")
    assert load_settings(str(p)) == DEFAULTS


def test_s4_settings_types_validated(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"datev_mode": "false", "dms_base_url": 5}))
    got = load_settings(str(p))
    assert got["datev_mode"] is False and got["dms_base_url"] is None


def test_s5_corrupt_blob_unpack_returns_empty():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("150/jpg", b"hello world " * 100)
    raw = bytearray(buf.getvalue())
    i = raw.index(b"150/jpg") + len(b"150/jpg")
    for k in range(i + 4, i + 20):
        raw[k] ^= 0xFF
    assert variant_blobs.unpack(bytes(raw)) == {}


def _import_log_config(env):
    code = "import infra.log_config as m; print(m.LOGLEVEL)"
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                          cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]))


def test_s6_log_config_import_robust(tmp_path):
    import os
    env = dict(os.environ, LOCALAPPDATA="/proc/nope/x", PDF_TOOL_LOG_LEVEL="BASIC_FORMAT")
    r = _import_log_config(env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "99"


def test_s7_open_file_remembers_session_for_close(monkeypatch):
    class Core:
        def __init__(self):
            self.calls = []

        def open(self, session, path):
            return {"ok": True, "session": "S1"}

        def release(self, s):
            self.calls.append(("release", s))
            raise RuntimeError("boom")

        def close_session(self, s):
            self.calls.append(("close", s))

    class Win:
        uid = "w"

        def create_file_dialog(self, *a, **k):
            return ["x.belegtool"]

    core = Core()
    api = host.HostApi(core, uid="w")
    monkeypatch.setattr(host.webview, "windows", [Win()])
    assert api.open_file(None)["ok"]
    assert api._session == "S1"
    captured = []

    class _C:
        def __iadd__(self, fn):
            captured.append(fn)
            return self

    class _W:
        uid = "w"
        events = type("E", (), {"closing": _C()})()

    host._bind_close(_W(), api)
    assert captured[0]() is True
    assert ("close", "S1") in core.calls  # close_session runs even though release raised
