# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""HA-1 (audit aa4): concurrent saves of the same document/path must serialise —
no shared temp name (spurious errno 2), no lost update, no leftovers."""
import os
import threading

from core.api import CoreApi
from core.bridge import load_belegtool, save_belegtool
from core.model import Document, Node
from helpers import create_valid_pdf


def _open_new(core, tmp_path, name):
    src = str(tmp_path / f"src_{name}.belegtool")
    save_belegtool(Document(Node(name="root", is_folder=True, children=(
        Node(name="a", pdf_length=2, original_data=create_valid_pdf(2)),))), src)
    return core.open(None, src)["session"]


def _leftovers(d):
    return [f for f in os.listdir(d) if ".tmp-" in f or f.endswith((".bak", ".wip", ".swapwip"))]


def test_eight_threads_saving_the_same_session_all_succeed(tmp_path):
    core = CoreApi()
    sid = _open_new(core, tmp_path, "one")
    path = str(tmp_path / "doc.belegtool")
    assert core.save(sid, path)["ok"]
    results = []
    for rnd in range(5):
        tree = core.get_state(sid)["tree"]
        core.dispatch(sid, {"type": "Rename", "node_id": tree["children"][0]["id"],
                            "name": f"round{rnd}"})
        out = [None] * 8

        def go(i):
            out[i] = core.save(sid, path)
        ts = [threading.Thread(target=go, args=(i,)) for i in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        results.extend(out)
        assert all(o and o["ok"] for o in out), out
    assert _leftovers(tmp_path) == []
    doc = load_belegtool(path)
    assert doc.root.children[0].name == "round4"


def test_concurrent_saves_of_two_sessions_to_one_path_do_not_error(tmp_path):
    core = CoreApi()
    sids = []
    for i in range(2):
        sids.append(_open_new(core, tmp_path, str(i)))
    path = str(tmp_path / "shared.belegtool")
    for _ in range(10):
        out = [None, None]

        def go(i):
            out[i] = core.save(sids[i], path)
        ts = [threading.Thread(target=go, args=(i,)) for i in (0, 1)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert all(o["ok"] for o in out), out
    assert _leftovers(tmp_path) == []
