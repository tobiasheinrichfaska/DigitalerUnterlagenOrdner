# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""CC-1/2/3 (t3 audit): per-session bookkeeping must not leak past the node/session lifetime."""
import os
import threading

import pytest

from pdf_synth import make_pdf
from core.api import CoreApi


@pytest.fixture
def pdf(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(make_pdf(pages=3, payload=30000))
    return str(p)


def test_cc1_removed_nodes_free_pcount_and_tokens_before_close(pdf):
    api = CoreApi()
    sid = api.open()["session"]
    r = api.import_paths(sid, [pdf])
    nid = r["tree"]["children"][0]["id"]
    api.render_window(sid, nid, 0, 1, 50)
    api._cancel_token(nid)
    assert any(k[0] == nid for k in api._pcount)
    assert api.dispatch(sid, {"type": "Delete", "node_id": nid})["ok"]
    assert not any(k[0] == nid for k in api._pcount)
    # undo brings the node back and it is compressible again (fresh token)
    assert api.undo(sid)["ok"]
    assert not api._cancel_token(nid).is_set()  # revived by _after_mutate
    api.close_session(sid)
    assert not api._pcount and not api._cancel_tokens


def test_cc1_close_frees_ids_removed_earlier(pdf):
    api = CoreApi()
    sid = api.open()["session"]
    nid = api.import_paths(sid, [pdf])["tree"]["children"][0]["id"]
    api.render_window(sid, nid, 0, 1, 50)
    api._cancel_token(nid)
    api.dispatch(sid, {"type": "Delete", "node_id": nid})
    api.close_session(sid)
    assert api._pcount == {} and api._cancel_tokens == {}


def test_cc2_save_racing_close_does_not_rebind_paths(pdf, tmp_path, monkeypatch):
    import core.bridge as br
    api = CoreApi()
    sid = api.open()["session"]
    api.import_paths(sid, [pdf])
    orig = br.save_belegtool
    started, go = threading.Event(), threading.Event()

    def slow(doc, path):
        started.set()
        go.wait()
        return orig(doc, path)
    monkeypatch.setattr(br, "save_belegtool", slow)
    t = threading.Thread(target=lambda: api.save(sid, str(tmp_path / "x.belegtool")))
    t.start()
    started.wait()
    api.close_session(sid)
    go.set()
    t.join()
    assert api._paths == {} and not api._sessions


def test_cc3_inplace_open_prunes_replaced_documents_variants(pdf, tmp_path):
    api = CoreApi()
    e = api._engine
    sid = api.open()["session"]
    nid = api.import_paths(sid, [pdf])["tree"]["children"][0]["id"]
    api.compress_options(sid, nid, 150)
    bp = str(tmp_path / "v.belegtool")
    assert api.save(sid, bp)["ok"]
    api.close_session(sid)
    before = len(e._persisted)
    sid = api.open(path=bp)["session"]
    assert len(e._persisted) > before
    api.open(session=sid)  # in-place: new empty document
    assert len(e._persisted) == before
    api.close_session(sid)
