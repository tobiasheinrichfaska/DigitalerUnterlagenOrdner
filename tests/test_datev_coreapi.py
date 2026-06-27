"""CoreApi DATEV-mode wiring (the lazy gate + open-capture + save-back + file/export
dispatch) — exercised with a FAKE DatevService injected into CoreApi (no live DATEV,
no curl). The service's own logic is covered in test_datev_inapp.py."""

import fitz
import pytest

from core.api import CoreApi
from core.bridge import save_belegtool
from core.model import Document, Node

GUID = "fa89ad42-8cd4-4828-8234-143161d41985"


def _pdf(n=1):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=595, height=842).insert_text((50, 80), f"P{i}")
    b = d.tobytes()
    d.close()
    return b


def _belegtool(tmp_path, name="doc"):
    doc = Document(Node(name="root", is_folder=True,
                        children=(Node(name="leaf", original_data=_pdf(2), pdf_length=2),)))
    path = str(tmp_path / f"{name}.belegtool")
    save_belegtool(doc, path)
    return path


class FakeService:
    def __init__(self, *, prov=None, baseline=None, writeback_result=None,
                 file_result=None, client_guid="same-client", fail_file_calls=()):
        self.prov = prov
        self.baseline = baseline or {"open_change_dt": "t0", "was_checked_out_at_open": False,
                                     "opened_sha256": "h0"}
        self.writeback_result = writeback_result
        self.file_result = file_result
        self.client_guid = client_guid
        self.fail_file_calls = set(fail_file_calls)  # 0-based file_document call indices that fail
        self.filed = []

    def status(self):
        return {"ok": True, "connected": True, "feature": "DokAb", "keeps_revisions": False}

    def capture_provenance(self, path, opened):
        return (self.prov, self.baseline) if self.prov else (None, None)

    def writeback(self, prov, baseline, edited, *, user_confirmed=True, comment=None, backup_dir=None):
        return self.writeback_result

    def file_document(self, data, *, client_guid, description, domain_id=1, folder_id=None,
                      register_id=None, structure_name="beleg.pdf"):
        idx = len(self.filed)
        self.filed.append({"data": data, "client_guid": client_guid, "description": description})
        if idx in self.fail_file_calls:
            return {"ok": False, "error": "boom"}
        return self.file_result or {"ok": True,
                                    "provenance": {"doc_guid": "new-guid", "file_id": 1,
                                                   "structure_item_id": 2,
                                                   "correspondence_partner_guid": client_guid}}

    def resolve_client(self, number):
        return {"guid": self.client_guid, "name": "Muster", "number": number}


def _core_with_service(svc):
    core = CoreApi()
    core._datev_mode = True
    core._datev_service = svc
    return core


# --- mode gate -------------------------------------------------------------
def test_datev_mode_off_status_does_not_import_datev(monkeypatch):
    monkeypatch.setattr(CoreApi, "_datev_get_service",
                        lambda self: (_ for _ in ()).throw(AssertionError("should not connect")))
    core = CoreApi()
    core._datev_mode = False
    assert core.datev_status() == {"ok": True, "datev_mode": False, "connected": False}


def test_set_datev_mode_persists_and_rebuilds(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from datev import inapp
    monkeypatch.setattr(inapp.DatevService, "connect",
                        classmethod(lambda cls, *a, **k: FakeService(prov=None)))
    core = CoreApi()
    st = core.set_datev_mode(True)
    assert st["datev_mode"] is True and st["connected"] is True
    from infra.settings import load_settings
    assert load_settings()["datev_mode"] is True
    off = core.set_datev_mode(False)
    assert off == {"ok": True, "datev_mode": False, "connected": False}


# --- open capture ----------------------------------------------------------
def test_open_in_datev_mode_captures_provenance(tmp_path):
    prov = {"doc_guid": GUID, "file_id": 1085411, "structure_item_id": 1085409,
            "correspondence_partner_guid": "client-x", "source_name": "Rechnung.pdf"}
    core = _core_with_service(FakeService(prov=prov))
    resp = core.open(path=_belegtool(tmp_path))
    assert resp["ok"]
    assert resp["datev"]["connected"] is True
    assert resp["datev"]["source_name"] == "Rechnung.pdf"
    assert resp["tree"]["datev"]["doc_guid"] == GUID         # tree carries provenance for the badge
    sid = resp["session"]
    assert core._datev_provenance(sid)["structure_item_id"] == 1085409
    assert sid in core._datev_baseline


def test_open_without_provenance_has_no_datev_block(tmp_path):
    core = _core_with_service(FakeService(prov=None))
    resp = core.open(path=_belegtool(tmp_path))
    assert "datev" not in resp
    assert resp["tree"]["datev"] is None


def test_open_normal_mode_off_never_touches_datev(tmp_path):
    core = CoreApi()  # datev_mode default False
    resp = core.open(path=_belegtool(tmp_path))
    assert "datev" not in resp and resp["tree"]["datev"] is None


# --- save-back -------------------------------------------------------------
def test_save_back_ok_updates_provenance_and_marks_saved(tmp_path):
    prov = {"doc_guid": GUID, "file_id": 1085411, "structure_item_id": 1085409}
    wb = {"ok": True, "verdict": "ok", "new_file_id": 9001, "new_change_dt": "t1",
          "provenance": {**prov, "file_id": 9001}}
    core = _core_with_service(FakeService(prov=prov, writeback_result=wb))
    resp = core.open(path=_belegtool(tmp_path))
    sid = resp["session"]
    path = core.document_path(sid)
    res = core.datev_save_back(sid, confirmed=True)
    assert res["ok"] and res["verdict"] == "ok"
    assert core._datev_provenance(sid)["file_id"] == 9001       # advanced; sid stable
    assert core._datev_baseline[sid]["open_change_dt"] == "t1"
    # parallel local save: the bound .belegtool is written in sync (no Save As prompt)
    assert res["local_saved"] == path
    import os
    assert os.path.exists(path)


def test_save_back_ok_but_local_save_fails_reports_local_error(tmp_path, monkeypatch):
    # DATEV write-back succeeds but the parallel local .belegtool save fails: ok stays True
    # (DATEV DID land), but local_error must surface so the divergence isn't silent, and the
    # baseline must adopt the SERVER-stored hash supplied by the service (new_sha256).
    prov = {"doc_guid": GUID, "file_id": 1085411, "structure_item_id": 1085409}
    wb = {"ok": True, "verdict": "ok", "new_file_id": 9001, "new_change_dt": "t1",
          "new_sha256": "server-hash", "provenance": {**prov, "file_id": 9001}}
    core = _core_with_service(FakeService(prov=prov, writeback_result=wb))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    monkeypatch.setattr(core, "save", lambda *a, **k: {"ok": False, "error": "Datenträger voll"})
    res = core.datev_save_back(sid, confirmed=True)
    assert res["ok"] and res["verdict"] == "ok"
    assert res["local_saved"] is None
    assert res["local_error"] == "Datenträger voll"
    assert core._datev_baseline[sid]["opened_sha256"] == "server-hash"   # server bytes, not uploaded


def test_save_back_ok_no_local_path_reports_unbound(tmp_path, monkeypatch):
    prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2}
    wb = {"ok": True, "verdict": "ok", "new_file_id": 9001, "new_change_dt": "t1",
          "provenance": {**prov, "file_id": 9001}}
    core = _core_with_service(FakeService(prov=prov, writeback_result=wb))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    monkeypatch.setattr(core, "document_path", lambda s: None)
    res = core.datev_save_back(sid, confirmed=True)
    assert res["ok"]
    assert res["local_error"] == "Kein lokaler Speicherort gebunden."


def test_save_back_reestablishes_baseline_for_reopened_file(tmp_path):
    # a reopened .belegtool has persisted provenance but NO live baseline → datev_save_back
    # must re-establish it from the server (and here safely report conflict_content), not crash.
    prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2}
    svc = FakeService(prov=prov, writeback_result={"ok": False, "verdict": "conflict_content"})
    core = _core_with_service(svc)
    sid = core.open(path=_belegtool(tmp_path))["session"]
    core._datev_baseline.pop(sid, None)        # simulate the reopened-file state
    res = core.datev_save_back(sid, confirmed=True)
    assert not res["ok"] and res["verdict"] == "conflict_content"


def test_set_datev_mode_off_clears_baselines(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2}
    core = _core_with_service(FakeService(prov=prov))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    assert sid in core._datev_baseline
    core.set_datev_mode(False)
    assert core._datev_baseline == {}          # mode-off frees stale per-session baselines


def test_datev_status_connect_failed_reports_error(monkeypatch):
    core = CoreApi()
    core._datev_mode = True
    monkeypatch.setattr(core, "_datev_get_service", lambda: None)
    st = core.datev_status()
    assert st["datev_mode"] is True and st["connected"] is False
    assert "Verbindung" in st["error"]


def test_open_mode_off_never_calls_datev_service(tmp_path, monkeypatch):
    # the lazy gate: with DATEV mode off, open() must NEVER reach the service (which would
    # import the datev package). Stub it to raise — a clean open proves the gate holds.
    core = CoreApi()  # datev_mode default False
    monkeypatch.setattr(core, "_datev_get_service",
                        lambda: (_ for _ in ()).throw(AssertionError("must not connect")))
    resp = core.open(path=_belegtool(tmp_path))
    assert resp["ok"] and "datev" not in resp


def test_save_back_conflict_returns_verdict_without_writing(tmp_path):
    prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2}
    core = _core_with_service(FakeService(
        prov=prov, writeback_result={"ok": False, "verdict": "conflict_changed"}))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    res = core.datev_save_back(sid, confirmed=True)
    assert not res["ok"] and res["verdict"] == "conflict_changed"


def test_save_back_not_connected_errors(tmp_path):
    core = _core_with_service(FakeService(prov=None))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    res = core.datev_save_back(sid)
    assert not res["ok"] and "DATEV" in res["error"]


def test_save_back_rejects_crafted_provenance_before_any_server_call(tmp_path):
    # an untrusted .belegtool with a hostile datev dict (non-GUID / non-int) is refused
    # up front — the fake service's writeback is never reached.
    svc = FakeService(prov=None, writeback_result={"ok": True, "verdict": "ok"})
    core = _core_with_service(svc)
    sid = core.open(path=_belegtool(tmp_path))["session"]
    core._datev_set_provenance(sid, {"doc_guid": "not-a-guid", "file_id": "x"})
    res = core.datev_save_back(sid, confirmed=True)
    assert not res["ok"] and "gültig" in res["error"]


def test_close_session_frees_datev_baseline(tmp_path):
    prov = {"doc_guid": GUID, "file_id": 1085411, "structure_item_id": 1085409}
    core = _core_with_service(FakeService(prov=prov))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    assert sid in core._datev_baseline           # captured on open
    core.close_session(sid)
    assert sid not in core._datev_baseline        # freed on close (no leak)


# --- file + export ---------------------------------------------------------
def test_datev_file_creates_and_adopts_provenance(tmp_path):
    svc = FakeService(prov=None)
    core = _core_with_service(svc)
    sid = core.open(path=_belegtool(tmp_path))["session"]
    res = core.datev_file(sid, mandant_number=10001, description="Beleg")
    assert res["ok"]
    assert svc.filed[0]["client_guid"] == "same-client"        # resolved from the Mandant number
    assert core._datev_provenance(sid)["doc_guid"] == "new-guid"  # now connected


def test_datev_export_files_each_split_part(tmp_path):
    # a document with two top folders + a low split threshold → two part PDFs, each filed.
    big = Document(Node(name="root", is_folder=True, children=(
        Node(name="A", is_folder=True, children=(Node(name="a", original_data=_pdf(60), pdf_length=60),)),
        Node(name="B", is_folder=True, children=(Node(name="b", original_data=_pdf(60), pdf_length=60),)),
    )))
    path = str(tmp_path / "big.belegtool")
    save_belegtool(big, path)
    svc = FakeService(prov={"doc_guid": GUID, "file_id": 1, "structure_item_id": 2,
                            "correspondence_partner_guid": "client-x"})
    core = _core_with_service(svc)
    sid = core.open(path=path)["session"]
    res = core.datev_export(sid, options={"split_pages": 100, "split_level": "top"})
    assert res["ok"] and res["parts"] >= 2                     # split into >=2 parts
    assert len(svc.filed) == res["parts"]
    assert all(f["client_guid"] == "client-x" for f in svc.filed)  # same client, no Mandant given


def test_datev_export_short_circuits_when_pdf_export_fails(tmp_path, monkeypatch):
    # if the underlying PDF export fails, datev_export returns that error and files NOTHING.
    prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2,
            "correspondence_partner_guid": "client-x"}
    svc = FakeService(prov=prov)
    core = _core_with_service(svc)
    sid = core.open(path=_belegtool(tmp_path))["session"]
    monkeypatch.setattr(core, "export",
                        lambda *a, **k: {"ok": False, "error": "nichts zu exportieren"})
    res = core.datev_export(sid)
    assert not res["ok"] and res["error"] == "nichts zu exportieren"
    assert svc.filed == []


def test_datev_export_sanitizes_hostile_document_name(tmp_path):
    # a document name with path separators / traversal must not write outside the temp dir
    # (datev_export builds a real temp path from the name — no native dialog to vet it).
    prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2,
            "correspondence_partner_guid": "client-x"}
    svc = FakeService(prov=prov)
    core = _core_with_service(svc)
    resp = core.open(path=_belegtool(tmp_path))
    sid = resp["session"]
    root_id = resp["tree"]["id"]
    core.dispatch(sid, {"type": "Rename", "node_id": root_id, "name": "../../evil/name"})
    res = core.datev_export(sid)  # single PDF (no split) — must not raise or escape
    assert res["ok"] and len(svc.filed) == 1


def test_datev_export_partial_failure_reports_how_many_landed(tmp_path):
    # one split part fails to file → ok:false WITH detail (the OK parts already landed in
    # DokAb, no rollback), not a silent generic failure.
    big = Document(Node(name="root", is_folder=True, children=(
        Node(name="A", is_folder=True, children=(Node(name="a", original_data=_pdf(60), pdf_length=60),)),
        Node(name="B", is_folder=True, children=(Node(name="b", original_data=_pdf(60), pdf_length=60),)),
    )))
    path = str(tmp_path / "big.belegtool")
    save_belegtool(big, path)
    svc = FakeService(prov={"doc_guid": GUID, "file_id": 1, "structure_item_id": 2,
                            "correspondence_partner_guid": "client-x"},
                      fail_file_calls={1})  # second part fails
    core = _core_with_service(svc)
    sid = core.open(path=path)["session"]
    res = core.datev_export(sid, options={"split_pages": 100, "split_level": "top"})
    assert not res["ok"]
    assert res["filed_ok"] == res["parts"] - 1                 # all but one landed
    assert "von" in res["error"]                               # "Nur X von Y …"
    assert any(f["ok"] for f in res["filed"]) and any(not f["ok"] for f in res["filed"])
