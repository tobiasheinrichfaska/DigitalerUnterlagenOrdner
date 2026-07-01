"""Unit tests for the pure DATEV write-back guard (no live DATEV)."""
from datev.writeback import (
    CONFLICT_CHANGED,
    CONFLICT_CONTENT,
    DECLINED,
    LOCKED,
    OK,
    decide_save_back,
    is_connected,
    valid_provenance,
)

GUID = "fa89ad42-8cd4-4828-8234-143161d41985"


def test_valid_provenance_requires_guid_int_file_id_and_int_or_numstr_sid():
    assert valid_provenance({"doc_guid": GUID, "file_id": 12, "structure_item_id": 9})
    assert valid_provenance({"doc_guid": GUID, "file_id": 12})  # sid may be absent/None


def test_valid_provenance_accepts_numeric_string_structure_item_id():
    # REGRESSION (2026-06-29): DATEVconnect returns the structure-item id as a numeric STRING
    # (structure_item_id_for_file → it["id"] = '1085416'), and the client coerces it via
    # int(structure_item_id) before the PUT. The old int-only guard rejected the string, so EVERY
    # live DokOrg-Pro write-back failed with "Dieses Dokument ist nicht (gültig) mit DATEV
    # verknüpft." This is the exact provenance captured from the failing checkout (see diag).
    assert valid_provenance({"doc_guid": GUID, "file_id": 1085420, "structure_item_id": "1085416",
                             "correspondence_partner_guid": GUID,
                             "source_name": "351932 - 351927 - datev-probe-test.pdf"})


def test_valid_provenance_rejects_crafted_belegtool_provenance():
    # an untrusted .belegtool could carry a hostile datev dict — reject before any server call.
    assert not valid_provenance({"doc_guid": "not-a-guid", "file_id": 12})
    # file_id is ALWAYS a real int (parse → int; upload_document_file coerces → int); a string
    # file_id means the value was never a real id → reject (even a numeric one).
    assert not valid_provenance({"doc_guid": GUID, "file_id": "12"})         # string file_id
    assert not valid_provenance({"doc_guid": GUID, "file_id": True})         # bool is not an int id
    # structure_item_id must be int OR a NUMERIC string (the client does int(sid)); a non-numeric
    # token would crash that coercion and cannot be a real id.
    assert not valid_provenance({"doc_guid": GUID, "file_id": 12, "structure_item_id": "x"})
    assert not valid_provenance({"doc_guid": GUID, "file_id": 12, "structure_item_id": "../etc"})
    assert not valid_provenance({"doc_guid": GUID, "file_id": 12, "structure_item_id": True})
    assert not valid_provenance(None) and not valid_provenance({})

# a baseline where everything agrees → write is allowed
BASE = dict(user_confirmed=True, checked_out_by_other_now=False,
            open_change_dt="2026-06-27T18:28:02.990", remote_change_dt="2026-06-27T18:28:02.990",
            opened_sha256="abc", remote_sha256="abc")


def test_ok_when_confirmed_not_foreign_checkout_unchanged_same_bytes():
    assert decide_save_back(**BASE) == OK


def test_declined_when_user_says_no():
    assert decide_save_back(**{**BASE, "user_confirmed": False}) == DECLINED


def test_foreign_checkout_blocks_but_my_own_does_not():
    # Checkout policy: a checkout by ANOTHER user/computer blocks (LOCKED); MY OWN checkout on
    # THIS computer is the normal DokOrg flow and does NOT block (the caller resolves ownership
    # and passes checked_out_by_other_now). With everything else agreeing, not-foreign → OK.
    assert decide_save_back(**{**BASE, "checked_out_by_other_now": True}) == LOCKED
    assert decide_save_back(**{**BASE, "checked_out_by_other_now": False}) == OK


def test_conflict_when_change_date_time_advanced():
    assert decide_save_back(**{**BASE, "remote_change_dt": "2026-06-27T19:00:00.000"}) \
        == CONFLICT_CHANGED


def test_conflict_when_server_bytes_differ_from_opened_original():
    assert decide_save_back(**{**BASE, "remote_sha256": "different"}) == CONFLICT_CONTENT


def test_decline_takes_precedence_over_everything():
    # if the user declines we never even look at lock/change state
    hostile = dict(user_confirmed=False, checked_out_by_other_now=True,
                   open_change_dt="a", remote_change_dt="b",
                   opened_sha256="x", remote_sha256="y")
    assert decide_save_back(**hostile) == DECLINED


def test_connection_state_and_save_as_breaks_it():
    prov = {"doc_guid": "fa89ad42-…", "file_id": 1085411, "structure_item_id": 1085409}
    assert is_connected(prov)
    # Save As clears the provenance → not connected → file-anew (UI gates on !connected)
    for broken in (None, {}, {"doc_guid": "x"}, {"file_id": 1}):
        assert not is_connected(broken)


def test_foreign_checkout_precedes_but_content_guards_still_apply():
    # a foreign checkout blocks FIRST (they may be editing), even if content also differs …
    assert decide_save_back(**{**BASE, "checked_out_by_other_now": True,
                               "remote_sha256": "other"}) == LOCKED
    # … and with NO foreign checkout the change/content guards still catch a real concurrent change
    assert decide_save_back(**{**BASE, "remote_change_dt": "later"}) == CONFLICT_CHANGED
    assert decide_save_back(**{**BASE, "remote_sha256": "other"}) == CONFLICT_CONTENT
