"""Unit tests for the pywebview host glue (HostApi window resolution + guards)."""

import host
from core.api import CoreApi


class _FakeWin:
    def __init__(self, uid):
        self.uid = uid


def test_win_resolves_this_window_by_uid(monkeypatch):
    api = host.HostApi(CoreApi(), uid="w1")
    monkeypatch.setattr(host.webview, "windows", [_FakeWin("w0"), _FakeWin("w1")])
    assert api._win().uid == "w1"  # never windows[0]


def test_win_is_none_when_window_is_gone(monkeypatch):
    api = host.HostApi(CoreApi(), uid="gone")
    monkeypatch.setattr(host.webview, "windows", [_FakeWin("w0")])
    assert api._win() is None  # no fall back to a different window


def test_dialogs_error_when_window_gone(monkeypatch):
    api = host.HostApi(CoreApi(), uid="gone")
    monkeypatch.setattr(host.webview, "windows", [])
    sid = api.open()["session"]
    for resp in (api.save_file(sid), api.open_file(sid),
                 api.export_dialog(sid), api.import_dialog(sid)):
        assert resp["ok"] is False and "Fenster" in resp["error"]


def test_set_dirty_tracks_flag_for_close_guard():
    api = host.HostApi(CoreApi())
    assert api._dirty is False
    api.set_dirty(True)
    assert api._dirty is True
