"""Pure decision logic for the DATEV write-back guard — DATEV mode only. UI-free, no live DATEV;
the caller gathers the open-time baseline + the save-time re-read and acts on the verdict. Any
non-OK verdict means: do NOT overwrite the DATEV document — offer a local filesystem save.

See docs/datev-integration-design.md. DokAb keeps no revision, so the overwrite is permanent;
this guard is what makes "update back to DATEV" safe on productive data.
"""

import re

_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


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
    present) an integer ``structure_item_id``. A bool is rejected (``bool`` is an ``int``
    subclass)."""
    if not is_connected(provenance):
        return False
    if not _GUID_RE.match(str(provenance.get("doc_guid") or "")):
        return False
    fid = provenance.get("file_id")
    if isinstance(fid, bool) or not isinstance(fid, int):
        return False
    sid = provenance.get("structure_item_id")
    if sid is not None and (isinstance(sid, bool) or not isinstance(sid, int)):
        return False
    return True


OK = "ok"
DECLINED = "declined"                    # user chose not to write back
LOCKED = "locked"                        # checked out at open or now → cannot write
CONFLICT_CHANGED = "conflict_changed"    # change_date_time advanced since open
CONFLICT_CONTENT = "conflict_content"    # server file bytes differ from the opened original


def decide_save_back(*, user_confirmed, was_checked_out_at_open, checked_out_by_other_now,
                     open_change_dt, remote_change_dt, opened_sha256, remote_sha256):
    """Verdict for a DATEV write-back. Inputs: the open-time baseline
    (``was_checked_out_at_open``, ``open_change_dt``, ``opened_sha256`` of the file we opened)
    and the save-time re-read (``checked_out_by_other_now``, ``remote_change_dt``,
    ``remote_sha256`` of the server file fetched now). The byte compare is **server-now vs the
    opened original**, never a separate open-time fetch."""
    if not user_confirmed:
        return DECLINED
    if was_checked_out_at_open or checked_out_by_other_now:
        return LOCKED
    if (open_change_dt or "") != (remote_change_dt or ""):
        return CONFLICT_CHANGED
    if opened_sha256 != remote_sha256:
        return CONFLICT_CONTENT
    return OK
