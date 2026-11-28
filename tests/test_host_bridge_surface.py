# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""SEC-1/SEC-2: nothing reachable from the pywebview bridge may expose CoreApi or
dunder/private attributes; only the public HostApi methods resolve."""
import inspect
import re
import threading

import pytest

import host
from core.api import CoreApi
from webview.util import js_bridge_call


class _Win:
    """Minimal stand-in for webview.Window as used by js_bridge_call / expose."""
    uid = "w1"

    def __init__(self, js_api=None):
        self._js_api = js_api
        self._functions = {}
        self.out = []
        self.ev = threading.Event()

    def expose(self, *fns):
        for f in fns:
            self._functions[f.__name__] = f

    def evaluate_js(self, code):
        self.out.append(code)
        self.ev.set()


def _exposed(core=None):
    api = host.HostApi(core or CoreApi(), uid="w1")
    win = _Win(host._NO_JS_API)
    host._expose_api(win, api)
    return win, api


def _call(win, name, params=()):
    win.out.clear()
    win.ev.clear()
    js_bridge_call(win, name, list(params), "7")
    win.ev.wait(1.5)
    return win.out[-1] if win.out else None


def test_open_window_passes_no_js_api(monkeypatch):
    seen = {}

    class W:
        uid = "u"
        events = type("E", (), {"closing": type("C", (), {"__iadd__": lambda s, f: s})(),
                                "loaded": type("C", (), {"__iadd__": lambda s, f: s})()})()

        def expose(self, *f):
            seen["exposed"] = [x.__name__ for x in f]

    def fake_create(title, url, **kw):
        seen["js_api"] = kw.get("js_api", "MISSING")
        return W()

    monkeypatch.setattr(host.webview, "create_window", fake_create)
    host._open_window(CoreApi())
    assert seen["js_api"] is host._NO_JS_API
    assert "open" in seen["exposed"] and "export_dialog" in seen["exposed"]


@pytest.mark.parametrize("name", [
    "_core.open", "_core.export", "_core.save", "_core.import_paths",
    "__class__", "__init__.__globals__", "_dirty", "_win", "_core",
    "open.__globals__", "open.__self__", "open.__closure__",
])
def test_private_and_core_names_do_not_resolve(name):
    win, _ = _exposed()
    out = _call(win, name, ["s", "x"])
    assert out is None  # dispatcher logged "does not exist" and never evaluated JS


def test_public_names_still_resolve():
    win, _ = _exposed()
    out = _call(win, "set_dirty", [True])
    assert out is not None and '"ok": true' in out


def test_every_core_js_method_resolves():
    src = open("webui/src/lib/core.js", encoding="utf-8").read()
    names = set(re.findall(r"call\('([a-z_]+)'", src))
    assert len(names) > 20
    win, _ = _exposed()
    missing = sorted(n for n in names if n not in win._functions)
    assert not missing, missing


def test_exposed_signatures_match_hostapi():
    win, _ = _exposed()
    for name, fn in win._functions.items():
        want = list(inspect.getfullargspec(getattr(host.HostApi, name)).args)[1:]
        assert list(inspect.getfullargspec(fn).args) == want, name


def test_export_dialog_strips_page_supplied_overwrite(monkeypatch):
    calls = []

    class Core:
        def document_name(self, s):
            return "doc"

        def export(self, session, path, node_ids, options):
            calls.append(dict(options or {}))
            if not (options or {}).get("overwrite"):
                return {"ok": False, "code": "exists", "existing": [path]}
            return {"ok": True}

    class W:
        uid = "w1"
        asked = 0

        def create_file_dialog(self, *a, **k):
            return "/tmp/Report.pdf"

        def create_confirmation_dialog(self, *a):
            W.asked += 1
            return True

    monkeypatch.setattr(host.webview, "windows", [W()])
    api = host.HostApi(Core(), uid="w1")
    api.export_dialog("s", None, {"overwrite": True, "split_pages": 1})
    assert calls[0].get("overwrite") is not True
    assert W.asked == 1  # the native confirm is now unavoidable
    assert calls[1]["overwrite"] is True
