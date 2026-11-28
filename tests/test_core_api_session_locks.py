# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""R-1/R-2 regressions: silent/pdf-bytes writers must serialise with the slow per-session
_mutate; reopening a session must drop its stale PDF-Tool node locks."""
import threading
import time

from core.api import CoreApi
from core.model import Document, Node
from core.session import DocumentSession
from helpers import create_valid_pdf


def _api():
    leaf = Node(name="scan", id="L", pdf_length=1, original_data=create_valid_pdf(pages=1))
    doc = Document(Node(name="root", id="r", is_folder=True, children=(leaf,)))
    api = CoreApi()
    sid = api.open()["session"]
    api._sessions[sid] = DocumentSession(doc, engine=api._engine)
    return api, sid


def test_provenance_write_not_lost_during_slow_mutation():
    api, sid = _api()

    class Slow:
        def rotate(self, b, a):
            time.sleep(0.8)
            return b

        def page_count(self, b):
            return 1

    api._engine = Slow()
    api._sessions[sid]._engine = api._engine
    t = threading.Thread(target=lambda: api.dispatch(
        sid, {"type": "Rotate", "node_id": "L", "direction": "right"}))
    t.start()
    time.sleep(0.3)
    api._datev_set_provenance(sid, {"doc_guid": "x"})
    t.join()
    prov = api._sessions[sid].document.root.datev
    assert prov and prov.get("doc_guid") == "x"


def test_reopen_same_session_drops_stale_pdftool_locks():
    api, sid = _api()
    api.open_node_in_pdftool(sid, "L")
    assert api.open(session=sid)["ok"]
    assert not any(own == sid for (own, _n) in api._node_locks)
    assert not any(own == sid for (own, _n) in api._pdftool_bindings.values())
    assert api.undo(sid).get("code") != "node_locked"
