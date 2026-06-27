"""In-app DATEV orchestration (DATEV mode) — unit-tested with a FAKE client (no live
DATEVconnect). Covers provenance capture, the guarded write-back (every verdict), the
create/file flow, the SCIM user pick, and the pure payload/structure-item helpers."""

import hashlib

import pytest

from datev.inapp import (
    DatevService,
    build_create_payload,
    pick_connection_user,
    sha256,
    structure_item_id_for_file,
)

GUID = "fa89ad42-8cd4-4828-8234-143161d41985"


class FakeClient:
    """Records calls; serves canned reads; lets a test mutate server state between calls."""

    def __init__(self, *, document=None, file_bytes=b"%PDF server", structure_items=None,
                 users=None, new_file_id=9001, created_id="new-doc-guid"):
        self.document = document or {}
        self.file_bytes = file_bytes
        self.structure_items = structure_items if structure_items is not None else []
        self.users = users if users is not None else []
        self.new_file_id = new_file_id
        self.created_id = created_id
        self.uploaded = []
        self.puts = []
        self.creates = []

    def get_info(self):
        return {"feature": "DokAb"}

    def get_document(self, doc_id):
        return dict(self.document)

    def get_document_file(self, file_id):
        return self.file_bytes

    def list_structure_items(self, doc_id):
        return list(self.structure_items)

    def list_users(self):
        return self.users

    def upload_document_file(self, data):
        self.uploaded.append(data)
        return self.new_file_id

    def update_structure_item(self, doc_id, sid, file_id, revision_comment=None):
        self.puts.append((doc_id, sid, file_id, revision_comment))
        return {"http_status": 204, "raw_body": ""}

    def create_document(self, payload):
        self.creates.append(payload)
        return {"id": self.created_id, "http_status": 201}

    def resolve_client_guid(self, number):
        return {"guid": "client-guid", "name": "Muster", "number": number}


# --- pure helpers ----------------------------------------------------------
def test_pick_connection_user_prefers_sid_match():
    users = {"resources": [
        {"id": "u1", "display_name": "A", "active": True, "linked_windows_identity": {"value": "S-1-5-21-1"}},
        {"id": "u2", "display_name": "B", "active": True, "linked_windows_identity": {"value": "S-1-5-21-2"}},
    ]}
    assert pick_connection_user(users, my_sid="S-1-5-21-2")["id"] == "u2"


def test_pick_connection_user_falls_back_to_first_active():
    users = [{"id": "u1", "display_name": "A", "active": False},
             {"id": "u2", "display_name": "B", "active": True}]
    assert pick_connection_user(users, my_sid="S-1-5-21-9")["id"] == "u2"


def test_pick_connection_user_none_when_empty():
    assert pick_connection_user([], my_sid="x") is None


def test_build_create_payload_has_mandatory_set_and_no_state():
    p = build_create_payload(file_id="1085410", client_guid="c-guid",
                             description="Rechnung", user_guid="u-guid",
                             folder_id=177, register_id=461, created="2026-06-27T18:00:00")
    assert p["class"] == {"id": 1}
    assert p["correspondence_partner_guid"] == "c-guid"
    assert p["user"] == {"id": "u-guid"}
    assert "state" not in p                                  # class 1 → no state
    si = p["structure_items"][0]
    assert si["document_file_id"] == 1085410 and isinstance(si["document_file_id"], int)
    assert si["counter"] == 1 and si["parent_counter"] == 0
    assert si["creation_date"] == "2026-06-27T18:00:00"
    assert p["folder"] == {"id": 177} and p["register"] == {"id": 461}


def test_build_create_payload_omits_optional_placement():
    p = build_create_payload(file_id=1, client_guid="c", description="d", user_guid="u")
    assert "folder" not in p and "register" not in p


def test_structure_item_id_for_file_matches_document_file_id():
    items = [{"id": 1085409, "document_file_id": 1085411, "type": 1},
             {"id": 1085500, "document_file_id": 9999, "type": 1}]
    assert structure_item_id_for_file(items, 1085411) == 1085409
    assert structure_item_id_for_file(items, 12345) is None
    assert structure_item_id_for_file({"structure_items": items}, 1085411) == 1085409


# --- capture provenance ----------------------------------------------------
def test_capture_provenance_from_checkout_path():
    client = FakeClient(
        document={"change_date_time": "2026-06-27T10:00:00", "checked_out": False,
                  "correspondence_partner_guid": "client-guid"},
        structure_items=[{"id": 1085409, "document_file_id": 1085411}])
    svc = DatevService(client)
    path = rf"C:\Temp\DATEV\{GUID}\1085411.pdf"
    prov, baseline = svc.capture_provenance(path, b"%PDF opened")
    assert prov["doc_guid"] == GUID and prov["file_id"] == 1085411
    assert prov["structure_item_id"] == 1085409
    assert prov["correspondence_partner_guid"] == "client-guid"
    assert baseline["open_change_dt"] == "2026-06-27T10:00:00"
    assert baseline["was_checked_out_at_open"] is False
    assert baseline["opened_sha256"] == sha256(b"%PDF opened")


def test_capture_provenance_non_checkout_path_returns_none():
    svc = DatevService(FakeClient())
    prov, baseline = svc.capture_provenance(r"C:\Users\x\rechnung.pdf", b"x")
    assert prov is None and baseline is None


def test_capture_provenance_reports_checked_out_at_open():
    client = FakeClient(document={"change_date_time": "t", "checked_out": True},
                        structure_items=[{"id": 1, "document_file_id": 1085411}])
    prov, baseline = DatevService(client).capture_provenance(
        rf"\\srv\{GUID}\1085411", b"x")
    assert baseline["was_checked_out_at_open"] is True


# --- guarded write-back ----------------------------------------------------
def _connected():
    opened = b"%PDF original opened bytes"
    client = FakeClient(
        document={"change_date_time": "2026-06-27T10:00:00", "checked_out": False},
        file_bytes=opened,
        structure_items=[{"id": 1085409, "document_file_id": 1085411}])
    prov = {"doc_guid": GUID, "file_id": 1085411, "structure_item_id": 1085409}
    baseline = {"open_change_dt": "2026-06-27T10:00:00",
                "was_checked_out_at_open": False, "opened_sha256": sha256(opened)}
    return client, prov, baseline


def test_writeback_ok_uploads_and_puts(tmp_path):
    client, prov, baseline = _connected()
    res = DatevService(client).writeback(prov, baseline, b"%PDF edited",
                                         comment="BelegTool", backup_dir=str(tmp_path))
    assert res["ok"] and res["verdict"] == "ok"
    assert client.uploaded == [b"%PDF edited"]
    assert client.puts == [(GUID, 1085409, 9001, "BelegTool")]
    assert res["provenance"]["file_id"] == 9001            # advances; sid stays stable
    assert res["provenance"]["structure_item_id"] == 1085409
    # the fetched server bytes were backed up locally before the overwrite
    assert res["backup_path"] and open(res["backup_path"], "rb").read() == b"%PDF original opened bytes"


def test_writeback_declined_does_not_write():
    client, prov, baseline = _connected()
    res = DatevService(client).writeback(prov, baseline, b"x", user_confirmed=False)
    assert not res["ok"] and res["verdict"] == "declined"
    assert client.uploaded == [] and client.puts == []


def test_writeback_change_dt_advanced_is_conflict():
    client, prov, baseline = _connected()
    client.document["change_date_time"] = "2026-06-27T11:00:00"  # someone wrote since open
    res = DatevService(client).writeback(prov, baseline, b"x")
    assert not res["ok"] and res["verdict"] == "conflict_changed"
    assert client.puts == []


def test_writeback_checked_out_now_is_locked():
    client, prov, baseline = _connected()
    client.document["checked_out"] = True
    res = DatevService(client).writeback(prov, baseline, b"x")
    assert res["verdict"] == "locked" and client.puts == []


def test_writeback_server_bytes_changed_is_conflict_content():
    client, prov, baseline = _connected()
    client.file_bytes = b"%PDF DIFFERENT server bytes"   # same change_dt, different content
    res = DatevService(client).writeback(prov, baseline, b"x")
    assert res["verdict"] == "conflict_content" and client.puts == []


def test_writeback_without_structure_item_refuses():
    client, prov, baseline = _connected()
    prov = dict(prov, structure_item_id=None)
    res = DatevService(client).writeback(prov, baseline, b"x")
    assert not res["ok"] and res["verdict"] == "no_structure_item"
    assert client.puts == []


# --- file a NEW document (single + per split-part) -------------------------
def test_file_document_uploads_then_creates_and_returns_provenance():
    client = FakeClient(new_file_id=5555, created_id="created-guid",
                        structure_items=[{"id": 777, "document_file_id": 5555}])
    svc = DatevService(client, my_sid="S-1-5-21-2")
    svc._client.users = [{"id": "u2", "active": True,
                          "linked_windows_identity": {"value": "S-1-5-21-2"}}]
    res = svc.file_document(b"%PDF export", client_guid="client-guid",
                            description="Gesamtexport", folder_id=177)
    assert res["ok"]
    assert client.uploaded == [b"%PDF export"]
    payload = client.creates[0]
    assert payload["correspondence_partner_guid"] == "client-guid"
    assert payload["user"] == {"id": "u2"}
    assert res["provenance"]["doc_guid"] == "created-guid"
    assert res["provenance"]["file_id"] == 5555
    assert res["provenance"]["structure_item_id"] == 777


def test_file_document_each_split_part_is_its_own_document():
    # "pdf split export also": filing N part PDFs files N documents under the same client.
    client = FakeClient()
    client.users = [{"id": "u1", "active": True}]
    svc = DatevService(client)
    parts = [b"%PDF part1", b"%PDF part2", b"%PDF part3"]
    for i, p in enumerate(parts, 1):
        svc.file_document(p, client_guid="c", description=f"Teil {i}")
    assert client.uploaded == parts            # every part uploaded
    assert len(client.creates) == 3            # one create per part
    assert all(c["correspondence_partner_guid"] == "c" for c in client.creates)


def test_file_document_no_user_errors():
    svc = DatevService(FakeClient(users=[]))
    res = svc.file_document(b"x", client_guid="c", description="d")
    assert not res["ok"] and "Benutzer" in res["error"]


def test_client_guid_for_document_reads_correspondence_partner():
    client = FakeClient(document={"correspondence_partner_guid": "same-client"})
    assert DatevService(client).client_guid_for_document(GUID) == "same-client"


def test_status_reports_feature_and_revision_policy():
    assert DatevService(FakeClient(), feature="DokAb").status() == {
        "ok": True, "connected": True, "feature": "DokAb", "keeps_revisions": False}
    assert DatevService(FakeClient(), feature="DMS").status()["keeps_revisions"] is True
    assert DatevService(FakeClient(), feature=None).status()["connected"] is False


def test_sha256_matches_hashlib():
    assert sha256(b"abc") == hashlib.sha256(b"abc").hexdigest()
