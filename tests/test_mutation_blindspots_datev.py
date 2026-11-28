# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Host-side guard for datev.writeback.valid_provenance (mutation blind spots MU-9).

The host suite only exercised decide_save_back; a crafted `datev` dict inside an untrusted
.belegtool must be rejected BEFORE any server call (structure_item_id check, strict False)."""

import pytest

from datev.writeback import valid_provenance

GUID = "12345678-1234-1234-1234-123456789abc"


def prov(**kw):
    base = {"doc_guid": GUID, "file_id": 7, "structure_item_id": 9085416}
    base.update(kw)
    return base


@pytest.mark.parametrize("sid", [9085416, "9085416", None])
def test_valid_structure_item_id_forms_are_accepted(sid):
    assert valid_provenance(prov(structure_item_id=sid)) is True


@pytest.mark.parametrize("sid", ["abc", "12a", "", "1.5", True, False, 1.5, [], {}, "-3"])
def test_crafted_structure_item_id_is_rejected(sid):
    assert valid_provenance(prov(structure_item_id=sid)) is False


@pytest.mark.parametrize("p", [
    prov(doc_guid="not-a-guid"),
    prov(doc_guid=""),
    prov(file_id=True),
    prov(file_id="7"),
    prov(file_id=None),
    {}, None,
])
def test_other_malformed_provenance_is_strictly_false(p):
    assert valid_provenance(p) is False
