"""Provenance / reverse-match: given a file (size, title, name) decide which DATEV document it
came from, and measure how *uniquely* each component identifies a document over a real set.

The DATEVconnect document filter cannot query by description or size, so matching is done
client-side over an indexed set (list documents → read each structure for file size/name). These
pure helpers do the scoring/matching and are unit-tested without any live DATEV.

An ``entry`` is one document-file: ``{doc_id, desc, name, size, file_id, change_date_time}``.
"""
import os
import re
from collections import Counter

_GUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def parse_checkout_path(path):
    """EXACT provenance: DATEV materializes a checked-out document under
    ``…\\<document-guid>\\<document-file-id>``. Pull the source document GUID +
    ``document_file_id``. Two materialization shapes are seen in the wild:

    - **DMS:** ``…\\<guid>\\<file-id>`` — the file itself is named ``<file-id>`` (the optional
      ``.pdf`` is stripped to the numeric stem);
    - **DokOrg Pro:** ``…\\<guid>\\<file-id>\\<name.ext>`` — ``<file-id>`` is a FOLDER and the real
      file (any name/extension, often none) sits inside it, e.g.
      ``…\\DokorgPro\\739381c4-…\\1085416\\Rechnung``.

    Returns ``{"doc_guid", "file_id"}`` (or ``{}`` when no GUID→numeric pair is present at the
    tail). Anchored to the TAIL — the last ``<GUID>\\<numeric>`` pair — so a stray GUID earlier
    in the path (a temp dir) can't false-match, while both depths are recognized."""
    if not path:
        return {}
    parts = [p for p in re.split(r"[\\/]", str(path)) if p]
    # gi = index of the GUID; the segment right after it is the numeric document-file id.
    # Try the file's parent (DMS) first, then its grandparent (DokOrg Pro folder shape).
    for gi in (len(parts) - 2, len(parts) - 3):
        if gi < 0 or not _GUID_RE.fullmatch(parts[gi]):
            continue
        stem = os.path.splitext(parts[gi + 1])[0]
        if stem.isdigit():
            return {"doc_guid": parts[gi], "file_id": int(stem)}
    return {}


def provenance_stats(entries):
    """How reliably each component (or combination) pins down a single document over ``entries``.
    Returns counts of entries whose key is **unique** (appears once) — higher = more identifying —
    plus the worst collision size for each key."""
    n = len(entries)
    base = {"files": n, "unique_size": 0, "unique_title": 0, "unique_name": 0,
            "unique_size_title": 0, "worst_size_collision": 0, "worst_title_collision": 0}
    if not n:
        return base
    c_size = Counter(e.get("size") for e in entries)
    c_title = Counter(e.get("desc") for e in entries)
    c_name = Counter(e.get("name") for e in entries)
    c_combo = Counter((e.get("size"), e.get("desc")) for e in entries)
    base.update(
        unique_size=sum(1 for e in entries if c_size[e.get("size")] == 1),
        unique_title=sum(1 for e in entries if c_title[e.get("desc")] == 1),
        unique_name=sum(1 for e in entries if c_name[e.get("name")] == 1),
        unique_size_title=sum(1 for e in entries if c_combo[(e.get("size"), e.get("desc"))] == 1),
        worst_size_collision=max(c_size.values()),
        worst_title_collision=max(c_title.values()),
    )
    return base


def match_entries(entries, size=None, title=None, name=None):
    """The entries matching ALL provided components (ignored when None). Empty = no candidate;
    one = confident provenance; several = ambiguous (need another component)."""
    out = []
    for e in entries:
        if size is not None and e.get("size") != size:
            continue
        if title is not None and (e.get("desc") or "") != title:
            continue
        if name is not None and (e.get("name") or "") != name:
            continue
        out.append(e)
    return out
