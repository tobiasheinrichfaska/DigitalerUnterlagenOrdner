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
        self.filed.append({"data": data, "client_guid": client_guid, "description": description,
                           "structure_name": structure_name})
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


# --- PDF-Tool bridge save (a directly-opened .pdf, no node binding) ---------
def test_save_node_back_rejects_a_bridge_pdf_session(tmp_path):
    # a directly-opened .pdf has NO pdftool binding → save_node_back refuses it. This is exactly
    # the Critical bug the PDF-Tool tripped on; save_pdf_bytes is the bridge-session save.
    import base64
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(_pdf(1))
    core = CoreApi()
    sid = core.open(path=str(pdf))["session"]
    res = core.save_node_back(sid, base64.b64encode(_pdf(2)).decode())
    assert not res["ok"] and "gebundenes" in res["error"]


def test_save_pdf_bytes_updates_bridge_session_and_writes_pdf(tmp_path):
    # the plain 💾 Speichern: bakes the edit into the session AND writes the .pdf on disk.
    import base64
    pdf = tmp_path / "beleg.pdf"
    pdf.write_bytes(_pdf(1))
    core = CoreApi()
    sid = core.open(path=str(pdf))["session"]
    edited = _pdf(3)                                   # stand-in for the edited bytes
    res = core.save_pdf_bytes(sid, base64.b64encode(edited).decode())
    assert res["ok"] and res["local_kind"] == "pdf" and res["local_saved"] == str(pdf)
    # the session leaf now holds the edited bytes (what get_pdf_bytes serves / DATEV uploads)
    assert base64.b64decode(core.get_pdf_bytes(sid)["data_b64"]) == edited
    assert pdf.read_bytes() == edited                 # and the on-disk .pdf was overwritten


def test_update_pdf_bytes_bakes_session_only_no_disk_write(tmp_path):
    # the DATEV bake: updates the session leaf but does NOT touch the on-disk .pdf (the disk
    # write is deferred to the guarded DATEV op, so a refused write-back can't clobber the file).
    import base64
    pdf = tmp_path / "beleg.pdf"
    pdf.write_bytes(_pdf(1))
    original = pdf.read_bytes()
    core = CoreApi()
    sid = core.open(path=str(pdf))["session"]
    edited = _pdf(3)
    res = core.update_pdf_bytes(sid, base64.b64encode(edited).decode())
    assert res["ok"] and "local_saved" not in res     # session-only: no local persist
    assert base64.b64decode(core.get_pdf_bytes(sid)["data_b64"]) == edited  # session updated
    assert pdf.read_bytes() == original               # ON-DISK .pdf untouched


def test_update_pdf_bytes_guards(tmp_path):
    import base64
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(_pdf(1))
    core = CoreApi()
    sid = core.open(path=str(pdf))["session"]
    assert core.update_pdf_bytes(sid, "")["error"] == "keine Daten zum Speichern"
    assert core.update_pdf_bytes(sid, "@@not-base64@@")["error"] == "ungültige Daten"
    assert core.update_pdf_bytes("nope", base64.b64encode(_pdf(1)).decode())["error"] \
        == "unbekannte Sitzung"


def test_dispatch_pdf_bytes_rejects_a_folder_only_document():
    # a session whose document has no leaf (folders only) has no PDF to write into:
    # _dispatch_pdf_bytes must refuse rather than IndexError on leaves[0].
    import base64
    from core.session import DocumentSession
    core = CoreApi()
    doc = Document(Node(name="root", is_folder=True,
                        children=(Node(name="sub", is_folder=True, children=()),)))
    core._sessions["folderonly"] = DocumentSession(doc, engine=core._engine)
    res = core.update_pdf_bytes("folderonly", base64.b64encode(_pdf(1)).decode())
    assert res == {"ok": False, "error": "kein PDF im Dokument"}
    # save_pdf_bytes shares the guard → same refusal, and nothing is persisted
    assert core.save_pdf_bytes("folderonly", base64.b64encode(_pdf(1)).decode()) \
        == {"ok": False, "error": "kein PDF im Dokument"}


def test_safe_filename_neutralizes_reserved_and_separators():
    f = CoreApi._safe_filename
    assert f("Rechnung 2024", "Export") == "Rechnung 2024"
    for reserved in ("NUL", "nul", "CON", "PRN", "COM1", "LPT9", "NUL.pdf", "COM1.foo"):
        assert f(reserved, "Export") == "Export"             # reserved (even with an extension)
    for hostile in ("../../evil", "a/b\\c", 'x:y*z?"<>'):
        assert not any(ch in f(hostile, "Export") for ch in '<>:"/\\|?*')  # no illegal char survives
    assert f("", "X") == "X" and f(None, "X") == "X"


def test_datev_local_persist_dispatches_on_extension(tmp_path):
    core = CoreApi()
    bt = core.open(path=_belegtool(tmp_path))["session"]     # .belegtool path → save() format
    r1 = core._datev_local_persist(bt, b"%PDF ignored on the belegtool branch")
    assert r1["local_kind"] == "belegtool" and r1["local_saved"].endswith(".belegtool")
    pdf = tmp_path / "x.pdf"                                  # .pdf path → raw bytes written
    pdf.write_bytes(_pdf(1))
    pd = core.open(path=str(pdf))["session"]
    r2 = core._datev_local_persist(pd, b"%PDF-1.4 edited")
    assert r2["local_kind"] == "pdf" and pdf.read_bytes() == b"%PDF-1.4 edited"
    new = core.open()["session"]                             # untitled, no bound path
    r3 = core._datev_local_persist(new, b"x")
    assert r3["local_saved"] is None and "Speicherort" in r3["local_error"]


def test_pdf_tool_edit_reaches_datev_writeback(tmp_path):
    # the full PDF-Tool DATEV path: open a checkout .pdf (bridge), bake an edit via the
    # session-only update_pdf_bytes, then write back — the UPLOADED bytes must reflect the edit.
    from datev.inapp import DatevService
    import base64
    import fitz
    raw = _pdf(1)
    fid = 1085411
    checkout = tmp_path / GUID / f"{fid}.pdf"
    checkout.parent.mkdir(parents=True)
    checkout.write_bytes(raw)

    class _Client:
        def __init__(self):
            self.uploaded = []

        def get_document(self, g):
            return {"change_date_time": "t0", "checked_out": False,
                    "correspondence_partner_guid": "c"}

        def get_document_file(self, f):
            return raw

        def list_structure_items(self, g):
            return [{"id": 1085409, "document_file_id": fid}]

        def upload_document_file(self, data):
            self.uploaded.append(data)
            return 9001

        def update_structure_item(self, g, sid, f, revision_comment=None):
            return {"http_status": 204}

    core = CoreApi()
    core._datev_mode = True
    svc = DatevService(_Client())
    core._datev_service = svc
    sid = core.open(path=str(checkout))["session"]
    core.update_pdf_bytes(sid, base64.b64encode(_pdf(4)).decode())   # edit: now 4 pages (session)
    res = core.datev_save_back(sid, confirmed=True)
    assert res["ok"] and res["verdict"] == "ok", res
    uploaded = svc._client.uploaded[0]
    assert uploaded != raw                                          # the edit reached DATEV
    assert fitz.open(stream=uploaded, filetype="pdf").page_count == 4


def test_datev_writeback_refused_does_not_clobber_local_checkout(tmp_path):
    # REGRESSION (round-7 audit, Medium): the PDF-Tool DATEV bake is SESSION-ONLY, so a refused
    # write-back (here conflict_content: the server changed since open) must leave the on-disk
    # checkout .pdf UNTOUCHED — never silently overwrite it while telling the user "save locally".
    from datev.inapp import DatevService
    import base64
    raw = _pdf(1)
    fid = 1085411
    checkout = tmp_path / GUID / f"{fid}.pdf"
    checkout.parent.mkdir(parents=True)
    checkout.write_bytes(raw)

    class _Client:
        def get_document(self, g):
            return {"change_date_time": "t0", "checked_out": False,
                    "correspondence_partner_guid": "c"}

        def get_document_file(self, f):
            return b"%PDF-1.4 DIFFERENT server bytes"     # server changed → conflict_content

        def list_structure_items(self, g):
            return [{"id": 1085409, "document_file_id": fid}]

        def upload_document_file(self, data):
            raise AssertionError("must not upload on a refused write-back")

        def update_structure_item(self, *a, **k):
            raise AssertionError("must not PUT on a refused write-back")

    core = CoreApi()
    core._datev_mode = True
    core._datev_service = DatevService(_Client())
    sid = core.open(path=str(checkout))["session"]
    core.update_pdf_bytes(sid, base64.b64encode(_pdf(4)).decode())   # bake edit (session only)
    assert checkout.read_bytes() == raw                             # bake did NOT touch disk
    res = core.datev_save_back(sid, confirmed=True)
    assert not res["ok"] and res["verdict"] == "conflict_content"
    assert checkout.read_bytes() == raw                             # refused → file left untouched


def test_datev_file_to_pdf_path_overwrites_with_filed_bytes(tmp_path):
    # filing a not-connected .pdf (PDF-Tool file-anew) writes the filed effective bytes back to
    # the .pdf on disk (local_kind 'pdf'), keeping the file consistent.
    pdf = tmp_path / "beleg.pdf"
    pdf.write_bytes(_pdf(1))
    svc = FakeService(prov=None)
    core = _core_with_service(svc)
    sid = core.open(path=str(pdf))["session"]
    res = core.datev_file(sid, mandant_number=10001)
    assert res["ok"] and res["local_kind"] == "pdf" and res["local_saved"] == str(pdf)
    assert pdf.read_bytes().startswith(b"%PDF") and pdf.read_bytes() == svc.filed[0]["data"]


def test_save_back_checkout_pdf_local_write_failure_reports_error(tmp_path, monkeypatch):
    # DATEV ok but the on-disk checkout .pdf can't be written (read-only / removed) → ok stays,
    # local_error names it, local_kind 'pdf'.
    prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2}
    wb = {"ok": True, "verdict": "ok", "new_file_id": 9001, "new_change_dt": "t1",
          "new_sha256": "h", "provenance": {**prov, "file_id": 9001}}
    core = _core_with_service(FakeService(prov=prov, writeback_result=wb))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    monkeypatch.setattr(core, "document_path", lambda s: str(tmp_path / "gone" / "x.pdf"))
    res = core.datev_save_back(sid, confirmed=True)
    assert res["ok"] and res["verdict"] == "ok"
    assert res["local_kind"] == "pdf" and res["local_saved"] is None and res["local_error"]


# --- save-back -------------------------------------------------------------
def test_open_unedited_checkout_writeback_is_ok_not_false_conflict(tmp_path):
    # REGRESSION (round-4 audit, HIGH): the open-time content baseline must hash the RAW
    # checkout file (== the server file), NOT the re-serialised effective bytes. With the real
    # DatevService over a fake client, opening an UNEDITED checkout .pdf and writing it straight
    # back must return OK — never a false conflict_content (server bytes == the raw checkout).
    from datev.inapp import DatevService
    raw = _pdf(2)
    fid = 1085411
    checkout_dir = tmp_path / GUID
    checkout_dir.mkdir(parents=True)
    checkout = checkout_dir / f"{fid}.pdf"
    checkout.write_bytes(raw)

    class _Client:
        def __init__(self):
            self.uploaded, self.puts = [], []

        def get_document(self, g):
            return {"change_date_time": "t0", "checked_out": False,
                    "correspondence_partner_guid": "client-x"}

        def get_document_file(self, f):
            return raw                              # the server still holds the raw checkout

        def list_structure_items(self, g):
            return [{"id": 1085409, "document_file_id": fid}]

        def upload_document_file(self, data):
            self.uploaded.append(data)
            return 9001

        def update_structure_item(self, g, sid, f, revision_comment=None):
            self.puts.append((g, sid, f))
            return {"http_status": 204}

    core = CoreApi()
    core._datev_mode = True
    svc = DatevService(_Client())
    core._datev_service = svc
    resp = core.open(path=str(checkout))
    assert resp.get("datev", {}).get("connected") is True       # captured as a checkout
    res = core.datev_save_back(resp["session"], confirmed=True)
    assert res["ok"] and res["verdict"] == "ok", res            # NOT conflict_content
    # PDF-Tool path: the on-disk checkout .pdf is overwritten with the SAME clean effective
    # bytes that went to DATEV (a plain PDF, not .belegtool format) so the file stays consistent.
    assert res["local_kind"] == "pdf" and res["local_saved"] == str(checkout)
    uploaded = svc._client.uploaded[0]
    assert checkout.read_bytes() == uploaded and checkout.read_bytes().startswith(b"%PDF")


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
    assert res["local_saved"] == path and res["local_kind"] == "belegtool"
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


def test_open_mode_off_does_not_import_datev_package(tmp_path):
    # STRUCTURAL lazy-gate proof: a mode-off launch must not leave the datev package in
    # sys.modules — a regressed top-level `import datev` would fail THIS even if behaviour looks
    # fine. Drop any datev.* imported by sibling test modules first so we measure the gate, then
    # RESTORE them in finally so this test can't pollute the (randomly-ordered) suite.
    import sys
    saved = {k: v for k, v in sys.modules.items() if k == "datev" or k.startswith("datev.")}
    for m in saved:
        del sys.modules[m]
    try:
        core = CoreApi()  # mode off
        core.open(path=_belegtool(tmp_path))
        assert "datev" not in sys.modules and "datev.inapp" not in sys.modules
    finally:
        sys.modules.update(saved)


def test_save_back_reestablished_baseline_ok_path_caches_baseline(tmp_path):
    # the OK-after-reopen branch: a reopened .belegtool (no live baseline) whose re-established
    # baseline matches → write-back succeeds and a baseline is cached for the session.
    prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2}
    wb = {"ok": True, "verdict": "ok", "new_file_id": 9001, "new_change_dt": "t1",
          "new_sha256": "h", "provenance": {**prov, "file_id": 9001}}
    core = _core_with_service(FakeService(prov=prov, writeback_result=wb))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    core._datev_baseline.pop(sid, None)        # reopened-file state (no live baseline)
    res = core.datev_save_back(sid, confirmed=True)
    assert res["ok"] and res["verdict"] == "ok"
    assert sid in core._datev_baseline         # re-established + cached


def test_set_datev_mode_true_drops_old_service_and_rebuilds(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from datev import inapp
    fresh = FakeService(prov=None)
    monkeypatch.setattr(inapp.DatevService, "connect", classmethod(lambda cls, *a, **k: fresh))
    core = CoreApi()
    core._datev_service = object()             # a stale "already built" instance
    core.set_datev_mode(True)
    assert core._datev_service is fresh         # old dropped, rebuilt on next use


def test_datev_export_errors_when_export_yields_no_path(tmp_path, monkeypatch):
    prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2,
            "correspondence_partner_guid": "client-x"}
    svc = FakeService(prov=prov)
    core = _core_with_service(svc)
    sid = core.open(path=_belegtool(tmp_path))["session"]
    monkeypatch.setattr(core, "export", lambda *a, **k: {"ok": True})  # ok but no paths/path
    res = core.datev_export(sid)
    assert not res["ok"] and "Datei" in res["error"]
    assert svc.filed == []                     # nothing opened/filed (no open(None))


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
def test_datev_status_connected_merges_mode(tmp_path):
    core = _core_with_service(FakeService(prov=None))
    st = core.datev_status()
    assert st["datev_mode"] is True and st["connected"] is True
    assert st["feature"] == "DokAb" and st["keeps_revisions"] is False   # from svc.status()


def test_datev_file_persists_link_locally(tmp_path):
    # filing a not-connected doc must save the new DATEV link into the bound .belegtool, so
    # closing the window can't lose it (the doc is no longer at a re-derivable checkout path).
    svc = FakeService(prov=None)
    core = _core_with_service(svc)
    sid = core.open(path=_belegtool(tmp_path))["session"]
    path = core.document_path(sid)
    res = core.datev_file(sid, mandant_number=10001, description="Beleg")
    assert res["ok"] and res["local_saved"] == path
    reopened = CoreApi().open(path=path)            # the adopted link survived to disk
    assert reopened["tree"]["datev"]["doc_guid"] == "new-guid"


def test_datev_file_resolve_failure_returns_error(tmp_path):
    class Boom(FakeService):
        def resolve_client(self, number):
            raise RuntimeError("Mandant 999 unbekannt")
    core = _core_with_service(Boom(prov=None))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    res = core.datev_file(sid, mandant_number=999)
    assert not res["ok"] and "unbekannt" in res["error"]


def test_datev_file_service_raise_returns_error_not_propagated(tmp_path):
    # Regression (round 9): svc.file_document() raising (DatevAuthError / network down / license)
    # must be caught and returned as {ok: False, verdict: 'error', ...} — NOT propagate uncaught
    # across the pywebview bridge as a raw rejection. Mirrors datev_save_back / datev_export guards.
    class Boom(FakeService):
        def file_document(self, *a, **k):
            raise RuntimeError("network down")
    core = _core_with_service(Boom(prov=None))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    res = core.datev_file(sid, mandant_number=10001)
    assert not res["ok"] and res["verdict"] == "error" and "network down" in res["error"]


def test_datev_file_no_mandant_errors(tmp_path):
    core = _core_with_service(FakeService(prov=None))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    res = core.datev_file(sid)                       # neither client_guid nor mandant_number
    assert not res["ok"] and "Mandant" in res["error"]


def test_datev_file_explicit_client_guid_skips_resolve(tmp_path):
    class NoResolve(FakeService):
        def resolve_client(self, number):
            raise AssertionError("resolve_client must not be called for an explicit guid")
    core = _core_with_service(NoResolve(prov=None))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    res = core.datev_file(sid, client_guid="explicit-guid")
    assert res["ok"]
    assert core._datev_service.filed[0]["client_guid"] == "explicit-guid"


def test_datev_file_ok_but_local_save_fails_reports_local_error(tmp_path, monkeypatch):
    core = _core_with_service(FakeService(prov=None))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    monkeypatch.setattr(core, "save", lambda *a, **k: {"ok": False, "error": "Datenträger voll"})
    res = core.datev_file(sid, mandant_number=10001)
    assert res["ok"]                                  # DATEV filing succeeded
    assert res.get("local_saved") is None and res["local_error"] == "Datenträger voll"


def test_datev_export_no_mandant_no_provenance_errors(tmp_path):
    core = _core_with_service(FakeService(prov=None))   # not connected → no same-client guid
    sid = core.open(path=_belegtool(tmp_path))["session"]
    res = core.datev_export(sid)                     # no mandant, nothing connected
    assert not res["ok"] and "Mandant" in res["error"]


def test_datev_export_resolve_failure_returns_error(tmp_path):
    class Boom(FakeService):
        def resolve_client(self, number):
            raise RuntimeError("resolve down")
    core = _core_with_service(Boom(prov=None))
    sid = core.open(path=_belegtool(tmp_path))["session"]
    res = core.datev_export(sid, mandant_number=999)
    assert not res["ok"] and "resolve down" in res["error"]


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
    # each split part is its own document with a DISTINCT structure name + description
    assert len({f["structure_name"] for f in svc.filed}) == res["parts"]
    assert len({f["description"] for f in svc.filed}) == res["parts"]


def test_datev_export_split_descriptions_suffix_the_given_one(tmp_path):
    # with an explicit description each split part gets "<desc> — <label>" (distinct + traceable).
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
    res = core.datev_export(sid, options={"split_pages": 100, "split_level": "top"},
                            description="Gesamt")
    assert res["ok"] and res["parts"] >= 2
    descs = [f["description"] for f in svc.filed]
    assert all(d.startswith("Gesamt — ") for d in descs)       # suffixed with the part label
    assert len(set(descs)) == len(descs)                       # distinct


def test_datev_export_single_keeps_plain_description(tmp_path):
    # a single (non-split) export keeps the given description verbatim — no part suffix.
    svc = FakeService(prov={"doc_guid": GUID, "file_id": 1, "structure_item_id": 2,
                            "correspondence_partner_guid": "client-x"})
    core = _core_with_service(svc)
    sid = core.open(path=_belegtool(tmp_path))["session"]
    res = core.datev_export(sid, description="Rechnung 2024")
    assert res["ok"] and res["parts"] == 1
    assert svc.filed[0]["description"] == "Rechnung 2024"


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


def test_datev_export_sanitizes_reserved_device_name(tmp_path):
    # a Windows reserved device name ("NUL") as the document name must not become the temp file
    # base — _safe_filename falls back to the default (datev_export is a distinct caller of it).
    prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2,
            "correspondence_partner_guid": "client-x"}
    svc = FakeService(prov=prov)
    core = _core_with_service(svc)
    resp = core.open(path=_belegtool(tmp_path))
    sid = resp["session"]
    core.dispatch(sid, {"type": "Rename", "node_id": resp["tree"]["id"], "name": "NUL"})
    res = core.datev_export(sid)
    assert res["ok"] and len(svc.filed) == 1
    assert svc.filed[0]["structure_name"].split(".")[0].upper() != "NUL"   # not a device name


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
