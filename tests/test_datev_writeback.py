"""Unit tests for the pure DATEV write-back guard (no live DATEV)."""
from datev.writeback import (
    CONFLICT_CHANGED,
    CONFLICT_CONTENT,
    DECLINED,
    LOCKED,
    OK,
    can_file_to_datev,
    can_write_back,
    decide_save_back,
    is_connected,
    valid_provenance,
)

GUID = "fa89ad42-8cd4-4828-8234-143161d41985"


def test_valid_provenance_requires_guid_and_int_ids():
    assert valid_provenance({"doc_guid": GUID, "file_id": 12, "structure_item_id": 9})
    assert valid_provenance({"doc_guid": GUID, "file_id": 12})  # sid may be absent/None


def test_valid_provenance_rejects_crafted_belegtool_provenance():
    # an untrusted .belegtool could carry a hostile datev dict — reject before any server call
    assert not valid_provenance({"doc_guid": "not-a-guid", "file_id": 12})
    assert not valid_provenance({"doc_guid": GUID, "file_id": "12"})        # string id
    assert not valid_provenance({"doc_guid": GUID, "file_id": True})        # bool is not an int id
    assert not valid_provenance({"doc_guid": GUID, "file_id": 12, "structure_item_id": "x"})
    assert not valid_provenance(None) and not valid_provenance({})

# a baseline where everything agrees → write is allowed
BASE = dict(user_confirmed=True, was_checked_out_at_open=False, checked_out_by_other_now=False,
            open_change_dt="2026-06-27T18:28:02.990", remote_change_dt="2026-06-27T18:28:02.990",
            opened_sha256="abc", remote_sha256="abc")


def test_ok_when_confirmed_unlocked_unchanged_same_bytes():
    assert decide_save_back(**BASE) == OK


def test_declined_when_user_says_no():
    assert decide_save_back(**{**BASE, "user_confirmed": False}) == DECLINED


def test_locked_if_checked_out_at_open_or_now():
    assert decide_save_back(**{**BASE, "was_checked_out_at_open": True}) == LOCKED
    assert decide_save_back(**{**BASE, "checked_out_by_other_now": True}) == LOCKED


def test_conflict_when_change_date_time_advanced():
    assert decide_save_back(**{**BASE, "remote_change_dt": "2026-06-27T19:00:00.000"}) \
        == CONFLICT_CHANGED


def test_conflict_when_server_bytes_differ_from_opened_original():
    assert decide_save_back(**{**BASE, "remote_sha256": "different"}) == CONFLICT_CONTENT


def test_decline_takes_precedence_over_everything():
    # if the user declines we never even look at lock/change state
    hostile = dict(user_confirmed=False, was_checked_out_at_open=True,
                   checked_out_by_other_now=True, open_change_dt="a", remote_change_dt="b",
                   opened_sha256="x", remote_sha256="y")
    assert decide_save_back(**hostile) == DECLINED


def test_connection_state_and_save_as_breaks_it():
    prov = {"doc_guid": "fa89ad42-…", "file_id": 1085411, "structure_item_id": 1085409}
    assert is_connected(prov) and can_write_back(prov) and not can_file_to_datev(prov)
    # Save As clears the provenance → not connected → file-anew, no write-back
    for broken in (None, {}, {"doc_guid": "x"}, {"file_id": 1}):
        assert not is_connected(broken)
        assert not can_write_back(broken) and can_file_to_datev(broken)


def test_lock_takes_precedence_over_change_and_content():
    locked = {**BASE, "was_checked_out_at_open": True,
              "remote_change_dt": "later", "remote_sha256": "other"}
    assert decide_save_back(**locked) == LOCKED
