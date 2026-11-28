# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""PDF-Tool audit x4: PT-2 (dirty close guard), PT-4 (unedited save is a no-op),
PT-5 (organizer close vs. its open tool windows)."""
import base64

import host
from core.api import CoreApi
from core.model import Document, Node
from core.session import DocumentSession
from helpers import create_valid_pdf


class _Closing:
    def __init__(self):
        self.fns = []

    def __iadd__(self, fn):
        self.fns.append(fn)
        return self


class _W:
    def __init__(self, uid, answer=True):
        self.uid = uid
        self.answer = answer
        self.asked = []
        self.destroyed = False
        self.events = type("E", (), {"closing": _Closing()})()

    def create_confirmation_dialog(self, title, msg):
        self.asked.append(msg)
        return self.answer

    def destroy(self):
        self.destroyed = True


def _api_with_node():
    api = CoreApi()
    sid = api.open()["session"]
    leaf = Node(name="scan", id="L", pdf_length=1, is_compressed=True,
                original_data=create_valid_pdf(pages=1))
    api._sessions[sid] = DocumentSession(
        Document(Node(name="root", id="r", is_folder=True, children=(leaf,))), engine=api._engine)
    return api, sid


def test_pt4_unedited_save_back_does_not_replace_the_source():
    api, sid = _api_with_node()
    pt = api.open_node_in_pdftool(sid, "L")["session"]
    data = api.get_pdf_bytes(pt)["data_b64"]
    res = api.save_node_back(pt, data)
    assert res["ok"]
    node = api._sessions[sid].document.find("L")
    assert node.is_compressed is True, "identical bytes must not issue SetNodeBytes"
    assert not api._sessions[sid].can_undo()


def _bind(core, win, api):
    host._bind_close(win, api)
    return win.events.closing.fns[0]


def test_pt2_dirty_tool_window_asks_before_close_and_clean_does_not():
    core = CoreApi()
    api = host.HostApi(core)
    w = _W("t1", answer=False)
    close = _bind(core, w, api)
    assert close() is True and not w.asked          # clean → no prompt
    api.set_dirty(True)
    assert close() is False and w.asked              # dirty + "Nein" → stays open
    w.answer = True
    assert close() is True


def _owner_and_tool(core):
    owner = host.HostApi(core)
    owner._session = owner.open()["session"]
    leaf = Node(name="scan", id="L", pdf_length=1, original_data=create_valid_pdf(pages=1))
    core._sessions[owner._session] = DocumentSession(
        Document(Node(name="root", id="r", is_folder=True, children=(leaf,))), engine=core._engine)
    pt = core.open_node_in_pdftool(owner._session, "L")["session"]
    tool = host.HostApi(core)
    tool._pdftool_session = pt
    return owner, tool, pt


def test_pt5_organizer_close_asks_when_a_tool_window_is_dirty(monkeypatch):
    core = CoreApi()
    owner, tool, pt = _owner_and_tool(core)
    ow, tw = _W("o"), _W("t")
    monkeypatch.setattr(host.webview, "windows", [ow, tw], raising=False)
    close_o = _bind(core, ow, owner)
    _bind(core, tw, tool)
    tool.set_dirty(True)
    ow.answer = False
    assert close_o() is False                        # user declines → everything stays
    assert pt in core._pdftool_bindings and not tw.destroyed
    ow.answer = True
    assert close_o() is True
    assert pt not in core._pdftool_bindings and tw.destroyed


def test_pt5_organizer_close_closes_clean_tool_windows_silently(monkeypatch):
    core = CoreApi()
    owner, tool, pt = _owner_and_tool(core)
    ow, tw = _W("o"), _W("t")
    monkeypatch.setattr(host.webview, "windows", [ow, tw], raising=False)
    close_o = _bind(core, ow, owner)
    _bind(core, tw, tool)
    assert close_o() is True and not ow.asked
    assert pt not in core._pdftool_bindings and tw.destroyed
