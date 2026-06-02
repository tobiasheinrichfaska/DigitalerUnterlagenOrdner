"""Unit tests for the pywebview host glue (HostApi window resolution + guards)."""

import host
from core.api import CoreApi
from core.bridge import save_belegtool
from core.model import Document, Node
from helpers import create_valid_pdf


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


def test_config_omits_startup_path_by_default():
    api = host.HostApi(CoreApi())
    assert "startup_path" not in api.config()


def test_config_exposes_startup_path_when_set():
    # The first window carries the .belegtool handed over by the legacy GUI;
    # the React app reads it from config() and opens it on load.
    api = host.HostApi(CoreApi())
    api._startup_path = r"C:\tmp\handover.belegtool"
    cfg = api.config()
    assert cfg["startup_path"] == r"C:\tmp\handover.belegtool"
    assert cfg["ok"] and "app_name" in cfg  # still carries the core config


def test_startup_path_file_opens_via_host(tmp_path):
    # The hand-over round-trip: a .belegtool snapshot opens in the new GUI exactly
    # as App.jsx does it — core.open(null, startup_path).
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="Übergabe", pdf_length=1, original_data=create_valid_pdf(1)),
    )))
    path = tmp_path / "handover.belegtool"
    save_belegtool(src, path)
    api = host.HostApi(CoreApi())
    api._startup_path = str(path)
    opened = api.open(None, api.config()["startup_path"])
    assert opened["ok"]
    assert [c["name"] for c in opened["tree"]["children"]] == ["Übergabe"]


def test_hostapi_delegates_core_ops():
    api = host.HostApi(CoreApi())
    assert api.config()["ok"] and "default_dpi" in api.config()
    opened = api.open()
    assert opened["ok"] and opened["tree"]["name"].startswith("Dokument")
    r = api.dispatch(opened["session"], {"type": "AddFolder", "parent_id": opened["tree"]["id"],
                                         "name": "X", "index": None, "new_id": "x"})
    assert [c["name"] for c in r["tree"]["children"]] == ["X"]
    assert api.undo(opened["session"])["tree"]["children"] == []


class _Hook:
    def __iadd__(self, fn):
        return self


class _Win:
    def __init__(self, uid):
        self.uid = uid
        self.events = type("E", (), {"closing": _Hook()})()


def test_new_window_creates_a_window(monkeypatch):
    created = []
    monkeypatch.setattr(host.webview, "create_window",
                        lambda *a, **k: created.append(_Win(f"w{len(created)}")) or created[-1])
    monkeypatch.setattr(host.webview, "windows", created)
    api = host.HostApi(CoreApi())
    assert api.new_window()["ok"] is True
    assert len(created) == 1
