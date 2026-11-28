# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""SEC-4: untrusted numeric bridge inputs are clamped at the CoreApi boundary."""

from core.api import CoreApi
from core.commands import InsertNodes
from core.model import Node
from helpers import create_valid_pdf


def _api(pages=1):
    api = CoreApi()
    sid = api.hello()["session"]
    with api._lock:
        s = api._sessions[sid]
        leaf = Node(name="d", pdf_length=pages, original_data=create_valid_pdf(pages=pages))
        s.dispatch(InsertNodes(parent_id=s.document.root.id, nodes=(leaf,), index=None))
    return api, sid, leaf.id


def test_render_window_count_is_clamped():
    api, sid, nid = _api()
    r = api.render_window(sid, nid, 0, 10**6, 50)
    assert r["ok"] and len(r["pages"]) <= 64


def test_render_window_bad_values_do_not_explode():
    api, sid, nid = _api()
    assert len(api.render_window(sid, nid, 0, -5, 50)["pages"]) == 0
    assert api.render_window(sid, nid, "x", "y", "z")["ok"] in (True, False)
    r = api.render_window(sid, nid, -5, 3, 50)
    assert all(p is None for p in r["pages"][:5]) or r["first"] == 0


def test_dpi_is_clamped_in_render_and_options():
    api, sid, nid = _api()
    seen = []
    orig = api._renderer().render_window
    api._renderer().render_window = lambda *a: (seen.append(a[-1]), orig(*a))[1]
    api.render_window(sid, nid, 0, 1, 10**9)
    api.render_window(sid, nid, 0, 1, 0)
    assert seen == [600, 30]
    r = api.compress_options(sid, nid, 10**9)
    assert r["dpi"] == 600
    assert api.compress_options(sid, nid, "x")["dpi"] == 150


def test_compress_command_dpi_is_clamped():
    api, sid, nid = _api()
    got = []
    orig = api._engine.compress
    api._engine.compress = lambda d, dpi, *a, **k: (got.append(dpi), orig(d, dpi, *a, **k))[1]
    api.dispatch(sid, {"type": "Compress", "node_id": nid, "dpi": 10**9, "method": "jpg"})
    assert got and max(got) <= 600


def test_render_budget_is_clamped():
    api, sid, nid = _api()
    assert api.set_render_budget(10**9)["cache_budget"] <= 4096 * 1024 * 1024
    assert api.set_render_budget(-3)["cache_budget"] >= 16 * 1024 * 1024
    assert api.set_render_budget("x")["ok"] is False
