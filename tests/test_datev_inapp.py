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

    def list_clients(self):
        return [{"id": "g-2", "number": "10002", "name": "Beta GmbH"},
                {"id": "g-1", "number": "10001", "name": "Alpha AG"},
                {"number": "10003", "name": "no-guid → dropped"}]

    def list_domains(self):
        return [{"id": 1, "name": "Mandanten", "folders": [
            {"id": 177, "name": "Stammakte", "registers": [{"id": 461, "name": "Korrespondenz"}]},
            {"id": 178, "name": "Jahresakte", "registers": []}]}]


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
    assert "year" not in p and "month" not in p and "receipt_date" not in p


def test_build_create_payload_sets_veranlagung_year_and_month_and_receipt_date():
    # the DATEV DMS Document properties: year (int32) + month (int16) = Veranlagungszeitraum/-monat;
    # receipt_date = the document's own date (Belegdatum). All optional, ints for the period.
    p = build_create_payload(file_id=1, client_guid="c", description="d", user_guid="u",
                             receipt_date="2025-03-14T00:00:00", fiscal_year="2025", fiscal_month="3")
    assert p["year"] == 2025 and isinstance(p["year"], int)
    assert p["month"] == 3 and isinstance(p["month"], int)
    assert p["receipt_date"] == "2025-03-14T00:00:00"
    # the structure-item technical dates are NOT the document date (default = now)
    assert p["structure_items"][0]["creation_date"] != "2025-03-14T00:00:00"


def test_build_create_payload_year_without_month_is_valid_month_alone_dropped():
    p1 = build_create_payload(file_id=1, client_guid="c", description="d", user_guid="u", fiscal_year=2024)
    assert p1["year"] == 2024 and "month" not in p1
    p2 = build_create_payload(file_id=1, client_guid="c", description="d", user_guid="u", fiscal_month=6)
    assert "month" not in p2 and "year" not in p2          # a month with no year is meaningless


def test_service_list_clients_normalizes_and_sorts_and_drops_guidless():
    svc = DatevService(FakeClient())
    rows = svc.list_clients()
    assert [r["number"] for r in rows] == ["10001", "10002"]   # sorted, the guid-less row dropped
    assert rows[0] == {"guid": "g-1", "number": "10001", "name": "Alpha AG"}


def test_service_list_placements_parses_folders_and_registers():
    svc = DatevService(FakeClient())
    folders = svc.list_placements(domain_id=1)
    assert [f["id"] for f in folders] == [177, 178]
    assert folders[0]["name"] == "Stammakte"
    assert folders[0]["registers"] == [{"id": 461, "name": "Korrespondenz"}]
    assert folders[1]["registers"] == []


def test_service_list_placements_empty_on_shape_surprise():
    class Bad(FakeClient):
        def list_domains(self):
            raise RuntimeError("master-data off")
    assert DatevService(Bad()).list_placements() == []


def test_file_document_passes_veranlagung_and_receipt_date_to_create(monkeypatch):
    fc = FakeClient()
    svc = DatevService(fc, my_sid="s")
    monkeypatch.setattr("datev.inapp.pick_connection_user", lambda users, sid: {"id": "u-guid"})
    svc.file_document(b"%PDF", client_guid="c", description="Rechnung",
                      document_date="2025-03-14T00:00:00", fiscal_year=2025, fiscal_month=3)
    payload = fc.creates[0]
    assert payload["year"] == 2025 and payload["month"] == 3
    assert payload["receipt_date"] == "2025-03-14T00:00:00"


def test_connect_honours_datev_config_json_base_url(tmp_path, monkeypatch):
    # REGRESSION (v3.10.0): connect() ignored datev.config.json — it only read a settings
    # override, so a shipped config never changed the host (always localhost:58452). It must
    # now resolve the DMS host:port from the file's base_url and pin the DMS path.
    from datev import inapp, config
    (tmp_path / "datev.config.json").write_text(
        '{"base_url": "https://DatevServer:58452", "verify_tls": false}', encoding="utf-8")
    monkeypatch.setattr(config, "basis_dir", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)

    captured = {}

    class _Probe:
        def __init__(self, cfg, transport, master_data_base=None):
            captured["base_url"] = cfg.base_url

        def get_info(self):
            return {"feature": "DokAb"}
    monkeypatch.setattr(inapp, "DatevConnectClient", _Probe, raising=False)
    # connect() imports DatevConnectClient lazily inside the function, so patch the source module
    monkeypatch.setattr("datev.client.DatevConnectClient", _Probe)

    svc = inapp.DatevService.connect(settings={})
    assert captured["base_url"] == "https://DatevServer:58452/datev/api/dms/v2"
    st = svc.status()
    assert st["base_url"] == "https://DatevServer:58452/datev/api/dms/v2"
    assert st["config_present"] is True and st["config_path"].endswith("datev.config.json")


def test_structure_item_id_for_file_matches_document_file_id():
    items = [{"id": 1085409, "document_file_id": 1085411, "type": 1},
             {"id": 1085500, "document_file_id": 9999, "type": 1}]
    assert structure_item_id_for_file(items, 1085411) == 1085409
    assert structure_item_id_for_file(items, 12345) is None
    assert structure_item_id_for_file({"structure_items": items}, 1085411) == 1085409


def test_resolve_structure_item():
    from datev.inapp import resolve_structure_item
    items = [{"id": "s1", "document_file_id": 111}, {"id": "s2", "document_file_id": 222}]
    # path number matches a document_file_id → that item (DMS / DokorgPro path, number IS the id)
    assert resolve_structure_item(items, 222) == {"id": "s2", "document_file_id": 222}
    # no match + several items → None (ambiguous; caller refuses rather than guess)
    assert resolve_structure_item(items, 999) is None
    # no match + SOLE item → that item (DokOrg CheckOut working-copy id case)
    one = [{"id": "only", "document_file_id": 555}]
    assert resolve_structure_item(one, 999) == {"id": "only", "document_file_id": 555}
    assert resolve_structure_item({"structure_items": one}, None) == {"id": "only", "document_file_id": 555}
    assert resolve_structure_item([], 1) is None


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


def test_capture_provenance_dokorg_checkout_resolves_real_file_id():
    # REGRESSION (2026-06-30, REAL data): the DokOrg "CheckOut" path embeds a WORKING-COPY number
    # (1085522) that is NOT a server document_file_id → get_document_file 404s ("document_file with
    # id 1085522 not found") and the structure-item lookup fails (prov_sid=None). Resolve the REAL
    # document_file_id + structure_item_id from the server (the sole structure item) via doc_guid.
    client = FakeClient(
        document={"change_date_time": "t0", "checked_out": True,
                  "correspondence_partner_guid": "client-guid"},
        structure_items=[{"id": "1085416", "document_file_id": 1085600}])
    path = rf"C:\Users\Tobias\AppData\Roaming\DokOrg\CheckOut\{GUID}\1085522\datev-probe-test.pdf"
    prov, baseline = DatevService(client).capture_provenance(path, b"%PDF opened")
    assert prov["doc_guid"] == GUID
    assert prov["file_id"] == 1085600          # OVERRIDDEN to the server file id (not the path 1085522)
    assert prov["structure_item_id"] == "1085416"


def test_capture_provenance_non_checkout_path_returns_none():
    svc = DatevService(FakeClient())
    prov, baseline = svc.capture_provenance(r"C:\Users\x\rechnung.pdf", b"x")
    assert prov is None and baseline is None


def test_capture_provenance_survives_server_read_failure():
    # the checkout path gives doc_guid/file_id even if the server reads fail — provenance is
    # still returned (degraded), never an exception.
    class Boom(FakeClient):
        def get_document(self, doc_id):
            raise RuntimeError("server down")

    prov, baseline = DatevService(Boom()).capture_provenance(
        rf"C:\Temp\{GUID}\1085411.pdf", b"x")
    assert prov["doc_guid"] == GUID and prov["file_id"] == 1085411
    assert baseline["open_change_dt"] is None       # read failed → stays None, no crash


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


def test_writeback_my_own_checkout_returns_checked_out_self(monkeypatch):
    # Confirmed live 2026-06-30: DATEV refuses an API update on a checked-out doc ("can't be changed
    # because it is checked out"). So MY OWN checkout → verdict CHECKED_OUT_SELF and NOTHING is
    # pushed to the server (the caller saves the local working copy; the user checks in via DATEV).
    # Uses a TS label "WTS (user1)" — machine "WTS" ≠ COMPUTERNAME, recognised by session user.
    monkeypatch.setenv("COMPUTERNAME", "TSHOST")
    monkeypatch.setenv("USERNAME", "user1")
    client, prov, baseline = _connected()
    client.document["checked_out"] = True
    client.document["checkout_computer"] = "WTS (USER1)"
    client.document["checkout_user"] = {"id": "11111111", "is_deleted": True, "name": "User One"}
    res = DatevService(client).writeback(prov, baseline, b"%PDF edited", comment="BelegTool")
    assert not res["ok"] and res["verdict"] == "checked_out_self"
    assert client.puts == [] and client.uploaded == []   # nothing written to the server


def test_writeback_foreign_checkout_is_locked_and_names_who(monkeypatch):
    # A checkout by ANOTHER user / on ANOTHER computer BLOCKS (LOCKED) and surfaces WHO has it.
    monkeypatch.setenv("COMPUTERNAME", "MYBOX")
    monkeypatch.setenv("USERNAME", "tobias")
    client, prov, baseline = _connected()
    client.document["checked_out"] = True
    client.document["checkout_computer"] = "OTHERBOX (andrea)"
    client.document["checkout_user"] = {"id": "u2", "name": "Andrea Müller"}
    res = DatevService(client).writeback(prov, baseline, b"x")
    assert not res["ok"] and res["verdict"] == "locked" and client.puts == []
    assert "Andrea Müller" in res["checkout_by"] and "OTHERBOX" in res["checkout_by"]


def test_writeback_server_bytes_changed_is_conflict_content():
    client, prov, baseline = _connected()
    client.file_bytes = b"%PDF DIFFERENT server bytes"   # same change_dt, different content
    res = DatevService(client).writeback(prov, baseline, b"x")
    assert res["verdict"] == "conflict_content" and client.puts == []


def test_is_my_checkout_and_label_pure():
    from datev.inapp import checkout_label, is_my_checkout
    me = dict(my_machine="MYBOX", my_user="tobias", my_dms_id="u1")
    # the session user (the "(user)" in checkout_computer) matches my Windows USERNAME → mine
    assert is_my_checkout({"checked_out": True, "checkout_computer": "MYBOX (tobias)"}, **me)
    # DMS user id match is an ADDITIONAL accept signal (session label differs) → mine
    assert is_my_checkout({"checked_out": True, "checkout_computer": "SOMEHOST (svc)",
                           "checkout_user": {"id": "u1"}}, **me)
    # REGRESSION (2026-06-29, terminal-server data pattern): the checkout label is "WTS (USER1)"
    # — "WTS" is a DATEV/TS session label, NOT the Windows COMPUTERNAME (TSHOST); AND the
    # checkout was stamped by a now-DELETED Nutzer whose GUID differs from the live connection's.
    # So neither the machine string nor the DMS id matches — ONLY the Windows session user does
    # (USER1 == user1), and that must identify ME. Earlier this blocked every TS write-back as
    # "locked". (The deleted/duplicate Nutzer is a DATEV-side data problem.)
    me_ts = dict(my_machine="TSHOST", my_user="user1",
                 my_dms_id="22222222-2222-2222-2222-222222222222")
    assert is_my_checkout({"checked_out": True, "checkout_computer": "WTS (USER1)",
                           "checkout_user": {"id": "11111111-1111-1111-1111-111111111111",
                                             "is_deleted": True}}, **me_ts)
    # session-user match is case-insensitive
    assert is_my_checkout({"checked_out": True, "checkout_computer": "WTS (User1)"},
                          my_machine="TSHOST", my_user="USER1")
    # another USER (a different "(windows-user)") → NOT mine, even on the same box / foreign DMS id
    assert not is_my_checkout({"checked_out": True, "checkout_computer": "WTS (ANDREA)",
                               "checkout_user": {"id": "u2"}}, **me)
    assert not is_my_checkout({"checked_out": True, "checkout_computer": "MYBOX (andrea)",
                               "checkout_user": {"id": "u2"}}, **me)
    # not checked out / no checkout info → NOT mine (conservative → blocks)
    assert not is_my_checkout({"checked_out": False, "checkout_computer": "MYBOX (tobias)"}, **me)
    assert not is_my_checkout({"checked_out": True}, **me)
    assert checkout_label({"checked_out": True, "checkout_user": {"name": "Andrea"},
                           "checkout_computer": "WTS"}) == "Andrea (WTS)"
    assert checkout_label({"checked_out": False}) is None


def test_writeback_without_structure_item_refuses():
    client, prov, baseline = _connected()
    prov = dict(prov, structure_item_id=None)
    res = DatevService(client).writeback(prov, baseline, b"x")
    assert not res["ok"] and res["verdict"] == "no_structure_item"
    assert client.puts == []


def test_writeback_backup_filename_is_path_safe(tmp_path):
    # defense-in-depth: a crafted provenance must never let the backup escape backup_dir
    # via path separators in doc_guid (CoreApi also gates with valid_provenance upstream).
    import os
    client, prov, baseline = _connected()
    prov = dict(prov, doc_guid="../../../etc/evil")
    res = DatevService(client).writeback(prov, baseline, b"%PDF edited", backup_dir=str(tmp_path))
    assert res["ok"] and res["backup_path"]
    # the backup landed INSIDE backup_dir — no traversal
    assert os.path.dirname(os.path.abspath(res["backup_path"])) == os.path.abspath(str(tmp_path))
    assert ".." not in os.path.basename(res["backup_path"])


def test_writeback_new_sha256_is_server_stored_bytes_not_uploaded(tmp_path):
    # the post-write baseline hash must come from the bytes DokAb STORED (read back),
    # not the bytes we uploaded — else a server-side re-process would spuriously trip
    # conflict_content on the next write-back.
    client, prov, baseline = _connected()
    res = DatevService(client).writeback(prov, baseline, b"%PDF edited", backup_dir=str(tmp_path))
    assert res["ok"]
    assert res["new_sha256"] == sha256(client.file_bytes)        # server read-back
    assert res["new_sha256"] != sha256(b"%PDF edited")           # NOT the uploaded bytes


def test_writeback_new_sha256_falls_back_when_server_readback_fails(tmp_path):
    # if reading the stored bytes back fails after a successful write, the baseline hash
    # falls back to the uploaded bytes (better a baseline than none) — write still ok.
    client, prov, baseline = _connected()
    orig = client.get_document_file

    def gdf(file_id):
        if file_id == client.new_file_id:   # the POST-write read-back (not the guard read)
            raise RuntimeError("read-back failed")
        return orig(file_id)

    client.get_document_file = gdf
    res = DatevService(client).writeback(prov, baseline, b"%PDF edited", backup_dir=str(tmp_path))
    assert res["ok"]
    assert res["new_sha256"] == sha256(b"%PDF edited")     # fell back to the uploaded bytes


def test_pick_connection_user_skips_deleted():
    users = [{"id": "u1", "display_name": "A", "active": True, "is_deleted": True},
             {"id": "u2", "display_name": "B", "active": True}]
    assert pick_connection_user(users, my_sid="no-match")["id"] == "u2"


def test_writeback_put_error_after_upload_returns_error_verdict(tmp_path):
    # the PUT (update_structure_item) failing AFTER a successful upload must also come back
    # as a clean error verdict (not an exception), with the upload recorded + a backup written.
    client, prov, baseline = _connected()

    def boom(*a, **k):
        raise RuntimeError("PUT 409")

    client.update_structure_item = boom
    res = DatevService(client).writeback(prov, baseline, b"%PDF edited", backup_dir=str(tmp_path))
    assert not res["ok"] and res["verdict"] == "error"
    assert "PUT 409" in res["error"]
    assert client.uploaded == [b"%PDF edited"]      # upload happened before the PUT failed
    assert res["backup_path"] and open(res["backup_path"], "rb").read()


def test_writeback_upload_error_returns_error_verdict_not_exception(tmp_path):
    # a mid-write network/HTTP error (after the guard passed) must come back as a clean
    # {ok:false, verdict:"error"}, NOT propagate as an unhandled exception across the bridge.
    client, prov, baseline = _connected()

    def boom(_data):
        raise RuntimeError("network down")

    client.upload_document_file = boom
    res = DatevService(client).writeback(prov, baseline, b"%PDF edited", backup_dir=str(tmp_path))
    assert not res["ok"] and res["verdict"] == "error"
    assert "network down" in res["error"]
    assert client.puts == []                       # nothing was PUT
    # the server bytes were still backed up locally before the failed upload
    assert res["backup_path"] and open(res["backup_path"], "rb").read()


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


def test_file_document_explicit_user_guid_skips_scim_lookup():
    client = FakeClient(new_file_id=5555, created_id="cg",
                        structure_items=[{"id": 7, "document_file_id": 5555}])
    seen = {"users": 0}
    orig = client.list_users

    def lu():
        seen["users"] += 1
        return orig()

    client.list_users = lu
    res = DatevService(client).file_document(b"x", client_guid="c", description="d",
                                             user_guid="u-explicit")
    assert res["ok"] and client.creates[0]["user"] == {"id": "u-explicit"}
    assert seen["users"] == 0                        # explicit user → no SCIM list query


def test_connect_with_injected_client_get_info_failure_sets_feature_none():
    class Boom(FakeClient):
        def get_info(self):
            raise RuntimeError("no /info")

    svc = DatevService.connect(client=Boom(), my_sid="x")
    assert svc.feature is None and svc.status()["connected"] is False


def test_file_document_no_user_errors():
    svc = DatevService(FakeClient(users=[]))
    res = svc.file_document(b"x", client_guid="c", description="d")
    assert not res["ok"] and "Benutzer" in res["error"]


def test_status_reports_feature_and_revision_policy():
    st = DatevService(FakeClient(), feature="DokAb", base_url="https://h:58452/x").status()
    assert st["ok"] and st["connected"] is True and st["feature"] == "DokAb"
    assert st["keeps_revisions"] is False
    assert st["base_url"] == "https://h:58452/x"           # surfaced for the user (diagnose host)
    assert "config_path" in st and "config_present" in st
    assert DatevService(FakeClient(), feature="DMS").status()["keeps_revisions"] is True
    assert DatevService(FakeClient(), feature=None).status()["connected"] is False


def test_sha256_matches_hashlib():
    assert sha256(b"abc") == hashlib.sha256(b"abc").hexdigest()
