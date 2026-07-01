"""Pure decision logic for the DATEV write-back guard — DATEV mode only. UI-free, no live DATEV;
the caller gathers the open-time baseline + the save-time re-read and acts on the verdict. Any
non-OK verdict means: do NOT overwrite the DATEV document — offer a local filesystem save.

See docs/datev-integration-design.md. DokAb keeps no revision, so the overwrite is permanent;
this guard is what makes "update back to DATEV" safe on productive data.
"""

import re

_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

_NUM_ID_RE = re.compile(r"^[0-9]+$")  # an ASCII-numeric id string (int()-coercible by the client)


def _is_int_id(value):
    """A DATEV id in its canonical in-process form: a real, non-bool int. ``file_id`` is always
    this — ``parse_checkout_path`` yields an int and ``upload_document_file`` coerces the server's
    string id to int — so anything else means a crafted/garbled provenance."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_int_or_num_str_id(value):
    """A DATEV id as it may legitimately sit in provenance: a real int, OR the **numeric string**
    DATEVconnect returns for a structure-item id (e.g. '1085416'). The client does
    ``int(structure_item_id)`` before the PUT, so a non-numeric string (and bool) is rejected —
    it would crash that coercion and cannot be a real id."""
    return _is_int_id(value) or (isinstance(value, str) and bool(_NUM_ID_RE.match(value)))


def is_connected(provenance):
    """A working document is DATEV-connected iff it carries complete provenance
    (``doc_guid`` + ``file_id``). Established on open from a checkout path; **Save As clears the
    provenance** → not connected (and thus not write-back-able)."""
    return bool(provenance and provenance.get("doc_guid")
                and provenance.get("file_id") is not None)


def valid_provenance(provenance):
    """Stronger than ``is_connected``: the provenance is **structurally trustworthy** for a
    write-back. A ``.belegtool`` is untrusted input and can carry a crafted ``datev`` dict, so
    before any server call require a real GUID ``doc_guid``, an integer ``file_id``, and (if
    present) a ``structure_item_id`` that is an int OR the numeric string DATEVconnect returns
    for it. A bool is rejected (``bool`` is an ``int`` subclass)."""
    if not is_connected(provenance):
        return False
    if not _GUID_RE.match(str(provenance.get("doc_guid") or "")):
        return False
    if not _is_int_id(provenance.get("file_id")):   # always a real int (parse / upload coerce)
        return False
    sid = provenance.get("structure_item_id")
    if sid is not None and not _is_int_or_num_str_id(sid):   # server returns a numeric STRING
        return False
    return True


OK = "ok"
DECLINED = "declined"                    # user chose not to write back
LOCKED = "locked"                        # checked out by ANOTHER user → blocked
CHECKED_OUT_SELF = "checked_out_self"    # checked out by ME → DATEV refuses an API update on a
                                         # checked-out doc ("can't be changed because it is checked
                                         # out"); save the local working copy + check in via DATEV
CONFLICT_CHANGED = "conflict_changed"    # change_date_time advanced since open
CONFLICT_CONTENT = "conflict_content"    # server file bytes differ from the opened original


def decide_save_back(*, user_confirmed, checked_out_by_other_now,
                     open_change_dt, remote_change_dt, opened_sha256, remote_sha256):
    """Verdict for a DATEV write-back. Inputs: the open-time baseline
    (``open_change_dt``, ``opened_sha256`` of the file we opened) and the save-time re-read
    (``checked_out_by_other_now``, ``remote_change_dt``, ``remote_sha256`` fetched now). The byte
    compare is **server-now vs the opened original**, never a separate open-time fetch.

    ⚠️ Checkout policy: a checkout by **ME on THIS computer** is the normal DokOrg edit flow
    (*Auschecken → bearbeiten → Einchecken*) and does NOT block the write-back. A checkout by
    **another user OR on another computer** DOES block (``LOCKED``) — they may be editing it, and
    DokAb keeps no revision. The caller resolves ownership from ``checkout_user``/``checkout_computer``
    and passes the single ``checked_out_by_other_now`` bool (checked out AND not me-here)."""
    if not user_confirmed:
        return DECLINED
    if checked_out_by_other_now:
        return LOCKED
    if (open_change_dt or "") != (remote_change_dt or ""):
        return CONFLICT_CHANGED
    if opened_sha256 != remote_sha256:
        return CONFLICT_CONTENT
    return OK
