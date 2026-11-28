# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Regression tests for the y2 acceptance findings AC-1/2/4/5 and y4 IO-6 (set_datev_mode)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from core.api import CoreApi  # noqa: E402
from core.commands import AddFolder, CommandError, apply  # noqa: E402
from core.model import Document, Node  # noqa: E402


# --- AC-1 -------------------------------------------------------------------
@pytest.mark.parametrize("name", ["", "   "])
def test_add_folder_rejects_empty_name(name):
    doc = Document(Node(name="root", is_folder=True))
    with pytest.raises(CommandError, match="Der Name darf nicht leer sein"):
        apply(doc, AddFolder(parent_id=doc.root.id, name=name))


def test_add_folder_default_name_still_works():
    doc = Document(Node(name="root", is_folder=True))
    out = apply(doc, AddFolder(parent_id=doc.root.id))
    assert out.root.children[0].name == "Neuer Ordner"


# --- AC-2 -------------------------------------------------------------------
def test_export_of_only_empty_folders_is_nothing_to_export(tmp_path):
    api = CoreApi()
    sid = api.open()["session"]
    root = api.get_state(sid)["tree"]["id"]
    r = api.dispatch(sid, {"type": "AddFolder", "parent_id": root, "name": "F"})
    fid = r["tree"]["children"][0]["id"]
    out = api.export(sid, str(tmp_path / "e.pdf"), node_ids=[fid])
    assert out == {"ok": False, "error": "nichts zu exportieren"}
    assert not (tmp_path / "e.pdf").exists()


# --- AC-5 (refuted on re-check: pin the existing behaviour) ------------------
def test_noop_commands_do_not_dirty_or_add_undo(tmp_path):
    from reportlab.pdfgen import canvas
    p = tmp_path / "a.pdf"
    c = canvas.Canvas(str(p)); c.drawString(50, 700, "x"); c.save()
    api = CoreApi()
    sid = api.open()["session"]
    api.import_paths(sid, [str(p)], None, None)
    st = api.get_state(sid)
    a = st["tree"]["children"][0]["id"]
    root = st["tree"]["id"]
    api.dispatch(sid, {"type": "SetTags", "node_id": a, "tags": ["x"]})
    api.dispatch(sid, {"type": "SetStatus", "node_id": a, "status": "erfasst"})
    api.save(sid, str(tmp_path / "s.belegtool"))
    name = api.get_state(sid)["tree"]["children"][0]["name"]
    undo_len = len(api._sessions[sid]._undo)
    for cmd in [
        {"type": "TagMany", "node_ids": [a], "tag": "", "add": True},
        {"type": "TagMany", "node_ids": [a], "tag": "zz", "add": False},
        {"type": "SetStatus", "node_id": a, "status": "erfasst"},
        {"type": "SetTags", "node_id": a, "tags": ["x"]},
        {"type": "Rename", "node_id": a, "name": name},
        {"type": "Move", "node_id": a, "new_parent_id": root, "index": 0},
    ]:
        r = api.dispatch(sid, cmd)
        assert r["ok"], (cmd, r)
        assert r["dirty"] is False, cmd
        assert len(api._sessions[sid]._undo) == undo_len, cmd


# --- AC-4 -------------------------------------------------------------------
class _Svc:
    def __init__(self, clients=None, fail=False):
        self.clients, self.fail, self.filed = clients, fail, []

    def list_clients(self):
        if self.fail:
            raise RuntimeError("down")
        return self.clients

    def file_document(self, *a, **k):
        self.filed.append(k)
        return {"ok": True, "provenance": {"doc_guid": "g", "file_id": 1, "structure_item_id": 2,
                                           "correspondence_partner_guid": k.get("client_guid")}}


def _core(svc):
    core = CoreApi()
    core._datev_mode = True
    core._datev_service = svc
    return core


@pytest.mark.parametrize("svc", [_Svc(clients=[]), _Svc(fail=True)])
def test_no_client_list_means_no_datev_filing(svc, tmp_path):
    import fitz
    d = fitz.open(); d.new_page(); d.save(str(tmp_path / "a.pdf"))
    core = _core(svc)
    sid = core.open()["session"]
    core.import_paths(sid, [str(tmp_path / "a.pdf")], None, None)
    r1 = core.datev_file(sid, client_guid="c1", description="d")
    r2 = core.datev_export(sid, client_guid="c1", description="d")
    for r in (r1, r2):
        assert r["ok"] is False and r["error"]
    assert svc.filed == []


# --- IO-6 -------------------------------------------------------------------
def test_set_datev_mode_reports_settings_write_failure(monkeypatch):
    import infra.settings as st

    def boom(**kw):
        raise OSError("disk full")
    monkeypatch.setattr(st, "update_settings", boom)
    core = CoreApi()
    core._datev_mode = False
    r = core.set_datev_mode(True)
    assert r["ok"] is False and r["error"]
    assert core._datev_mode is False
