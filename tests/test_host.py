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
    # The session is bound to the opened file → Save writes in place (no Save-As).
    assert api._core.document_path(opened["session"]) == str(path)


def test_argv_belegtool_becomes_startup_path(tmp_path):
    # BelegTool.exe <file.belegtool> / file association: an existing .belegtool on
    # the command line is opened on startup (was silently dropped before).
    path = tmp_path / "doc.belegtool"
    path.write_bytes(b"x")
    assert host._startup_path_from_argv(["host.py", str(path)]) == str(path)


def test_argv_no_file_is_no_startup_path():
    assert host._startup_path_from_argv(["host.py"]) is None  # bare launch
    assert host._startup_path_from_argv(["host.py", "C:\\nope.belegtool"]) is None  # missing file


def test_argv_non_belegtool_is_ignored(tmp_path):
    # A PDF (or anything else) belongs on the import path, not startup-open.
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert host._startup_path_from_argv(["host.py", str(pdf)]) is None


def test_export_dialog_default_filename_is_document_name(monkeypatch):
    core = CoreApi()
    api = host.HostApi(core, uid="w")
    sid = api.open()["session"]
    name = core.document_name(sid)
    captured = {}

    class _Win:
        uid = "w"

        def create_file_dialog(self, *a, **k):
            captured.update(k)
            return None  # cancel — we only care about the proposed filename

    monkeypatch.setattr(host.webview, "windows", [_Win()])
    api.export_dialog(sid)
    assert captured.get("save_filename") == f"{name}.pdf"  # doc name, not "Export.pdf"


def test_webview2_installed_returns_bool():
    assert isinstance(host._webview2_installed(), bool)


def test_main_aborts_with_warning_when_webview2_missing(monkeypatch):
    flags = {"warned": False, "started": False}
    monkeypatch.setattr(host, "_webview2_installed", lambda: False)
    monkeypatch.setattr(host, "_warn_missing_webview2", lambda: flags.__setitem__("warned", True))
    monkeypatch.setattr(host.webview, "start", lambda *a, **k: flags.__setitem__("started", True))
    monkeypatch.delenv("BELEG_SKIP_WEBVIEW2_CHECK", raising=False)
    host.main()
    assert flags["warned"] and not flags["started"]  # warned the user, never opened a blank window


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


def test_close_guard_frees_the_windows_session():
    # Closing a window must free its session in the shared CoreApi (lock + document
    # bytes + caches) — not only the file lock.
    captured = []

    class _Closing:
        def __iadd__(self, fn):
            captured.append(fn)
            return self

    class _W:
        uid = "w"

        def __init__(self):
            self.events = type("E", (), {"closing": _Closing()})()

    core = CoreApi()
    api = host.HostApi(core)
    api._session = api.open()["session"]
    host._bind_close(_W(), api)
    assert captured, "closing handler was not registered"
    assert captured[0]() is True              # not dirty → close proceeds
    assert api._session not in core._sessions  # the session died with the window


def test_close_guard_logs_release_failure_but_still_closes(monkeypatch):
    # A failing release/close_session must not block the window close, but it must
    # be TRACED (logger.exception) — a bare pass silently leaked the whole session.
    captured = []

    class _Closing:
        def __iadd__(self, fn):
            captured.append(fn)
            return self

    class _W:
        uid = "w"

        def __init__(self):
            self.events = type("E", (), {"closing": _Closing()})()

    core = CoreApi()
    api = host.HostApi(core)
    api._session = api.open()["session"]
    monkeypatch.setattr(core, "release",
                        lambda sid: (_ for _ in ()).throw(RuntimeError("boom")))
    logged = []
    monkeypatch.setattr(host.logger, "exception", lambda *a, **k: logged.append(a))
    host._bind_close(_W(), api)
    assert captured[0]() is True  # close still proceeds (swallowed)
    assert logged, "close failure was not logged"


def test_is_clr_load_error_matches_pythonnet_failures():
    for msg in ("Failed to initialize pythonnet",
                "Could not load file or assembly Python.Runtime",
                "loader.initialize returned -1",
                "clr_loader could not resolve the runtime"):
        assert host._is_clr_load_error(Exception(msg)) is True, msg


def test_is_clr_load_error_ignores_other_failures():
    for msg in ("ERR_UNSAFE_PORT", "[WinError 10048] address already in use",
                "KeyError: 'session'", ""):
        assert host._is_clr_load_error(Exception(msg)) is False, msg


def test_main_logs_and_explains_clr_load_failure(monkeypatch):
    # A pythonnet load failure must be LOGGED (not only shown in the dialog) and
    # routed to the MotW explanation instead of a raw traceback.
    calls = {"warned": None, "logged": False}

    class _Log:
        def exception(self, *a, **k):
            calls["logged"] = True

    monkeypatch.setattr(host, "_webview2_installed", lambda: True)
    monkeypatch.setattr(host, "_open_window", lambda core, startup_path=None, restore=False: {"ok": True})
    monkeypatch.setattr(host.webview, "start",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Failed to initialize Python.Runtime")))
    monkeypatch.setattr(host, "_warn_clr_load_failed", lambda e: calls.__setitem__("warned", e))
    monkeypatch.setattr(host, "logger", _Log())
    host.main()  # must return (no raise): the failure is explained, not crashed on
    assert calls["logged"] is True
    assert isinstance(calls["warned"], RuntimeError)


def test_new_window_creates_a_window(monkeypatch):
    created = []
    monkeypatch.setattr(host.webview, "create_window",
                        lambda *a, **k: created.append(_Win(f"w{len(created)}")) or created[-1])
    monkeypatch.setattr(host.webview, "windows", created)
    api = host.HostApi(CoreApi())
    assert api.new_window()["ok"] is True
    assert len(created) == 1
