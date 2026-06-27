"""Unit tests for the pure DATEV write-back guard (no live DATEV)."""
from datev.writeback import (
    CONFLICT_CHANGED,
    CONFLICT_CONTENT,
    DECLINED,
    LOCKED,
    OK,
    decide_save_back,
)

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


def test_lock_takes_precedence_over_change_and_content():
    locked = {**BASE, "was_checked_out_at_open": True,
              "remote_change_dt": "later", "remote_sha256": "other"}
    assert decide_save_back(**locked) == LOCKED
