# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Audit aa4 HostApi regressions (HA-2..HA-7), with a fake pywebview window."""
import os

import pytest

import host
from core.api import CoreApi
from core.bridge import save_belegtool
from core.model import Document, Node
from helpers import create_valid_pdf


class _Ev:
    def __iadd__(self, f):
        return self


class _Win:
    def __init__(self, uid="w1"):
        self.uid = uid
        self.events = type("E", (), {"closing": _Ev(), "loaded": _Ev()})()
        self.file_dialog = lambda *a, **k: None
        self.confirm = lambda *a, **k: True

    def expose(self, *fns):
        pass

    def create_file_dialog(self, *a, **k):
        return self.file_dialog(*a, **k)

    def create_confirmation_dialog(self, *a, **k):
        return self.confirm(*a, **k)


def _belegtool(tmp_path, name="d.belegtool"):
    p = str(tmp_path / name)
    save_belegtool(Document(Node(name="root", is_folder=True, children=(
        Node(name="a", pdf_length=1, original_data=create_valid_pdf(1)),))), p)
    return p


def _api(monkeypatch, win=None):
    win = win or _Win()
    monkeypatch.setattr(host.webview, "windows", [win])
    return host.HostApi(CoreApi(), uid=win.uid), win


def test_second_open_none_replaces_the_session_instead_of_leaking(monkeypatch):  # HA-2
    api, _ = _api(monkeypatch)
    s1 = api.open()["session"]
    s2 = api.open()["session"]
    assert s1 == s2
    assert len(api._core._sessions) == 1


def test_failed_window_creation_releases_the_pdftool_binding(monkeypatch, tmp_path):  # HA-3
    api, _ = _api(monkeypatch)
    core = api._core
    sid = core.open(None, _belegtool(tmp_path))["session"]
    leaf = core.get_state(sid)["tree"]["children"][0]["id"]
    monkeypatch.setattr(host, "_open_window", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = api.open_node_in_pdftool(sid, leaf)
    assert r["ok"] is False
    assert not core._node_locks and not core._pdftool_bindings
    monkeypatch.setattr(host, "_open_window", lambda *a, **k: {"ok": True})
    assert api.open_node_in_pdftool(sid, leaf)["ok"] is True  # retry is not node_locked


def test_failed_view_window_removes_the_temp_view_dir(monkeypatch, tmp_path):  # HA-3
    api, _ = _api(monkeypatch)
    core = api._core
    sid = core.open(None, _belegtool(tmp_path))["session"]
    leaf = core.get_state(sid)["tree"]["children"][0]["id"]
    monkeypatch.setattr(host, "_open_window", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = api.open_view_in_new_window(sid, [leaf], "v")
    assert r["ok"] is False
    assert not core._pending_view_dirs


def test_open_view_in_new_window_returns_the_node_count(monkeypatch, tmp_path):  # HA-4
    api, _ = _api(monkeypatch)
    core = api._core
    sid = core.open(None, _belegtool(tmp_path))["session"]
    leaf = core.get_state(sid)["tree"]["children"][0]["id"]
    monkeypatch.setattr(host, "_open_window", lambda *a, **k: {"ok": True})
    r = api.open_view_in_new_window(sid, [leaf], "v")
    assert r["ok"] is True and r["count"] == 1


def test_open_file_does_not_create_a_session_when_the_window_vanished(monkeypatch, tmp_path):  # HA-6
    api, win = _api(monkeypatch)
    p = _belegtool(tmp_path)

    def dlg(*a, **k):
        host.webview.windows.clear()  # window closed while the dialog was up
        return (p,)
    win.file_dialog = dlg
    r = api.open_file(None)
    assert r["ok"] is False
    assert not api._core._sessions


@pytest.mark.parametrize("meth", ["open_file", "save_file_as", "export_dialog", "import_dialog"])
def test_file_dialog_exceptions_become_error_dicts(monkeypatch, meth):  # HA-7
    api, win = _api(monkeypatch)
    sid = api._core.open()["session"]

    def boom(*a, **k):
        raise OSError("secret C:\\internal path")
    win.file_dialog = boom
    r = getattr(api, meth)(sid)
    assert r["ok"] is False
    assert "secret" not in r["error"] and "internal" not in r["error"]


def test_confirmation_dialog_exception_becomes_error_dict(monkeypatch):  # HA-7
    api, win = _api(monkeypatch)
    sid = api._core.open()["session"]

    def boom(*a, **k):
        raise OSError("secret")
    win.confirm = boom
    r = api.save_to_datev(sid)
    assert r["ok"] is False and "secret" not in r["error"]
