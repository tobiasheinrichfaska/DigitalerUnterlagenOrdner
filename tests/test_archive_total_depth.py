"""M4 (audit 2026-11-03): since _ARCHIVE_MAX_DEPTH=10, a crafted archive (deep
member paths at every nesting level) could build an import tree deeper than the
.belegtool loader's _MAX_TREE_DEPTH=200 — the save succeeds, the reopen throws
StructureTooDeep and the WHOLE document (including unrelated work) is lost to
the user. The import must bound its TOTAL folder depth, not just per-member
path depth and container nesting separately.
"""
import io
import zipfile

from universal_importer import archives
from formats.pdf_storage import _MAX_TREE_DEPTH
from helpers import create_valid_pdf


def _deep_zip(levels: int, folders_per_level: int) -> bytes:
    path = "/".join(f"f{i:02d}" for i in range(folders_per_level))
    blob = _zip({f"{path}/doc.pdf": create_valid_pdf(pages=1)})
    for _ in range(levels - 1):
        blob = _zip({f"{path}/inner.zip": blob})
    return blob


def _zip(members: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


def _max_depth(nodes, at=1):
    best = at
    for n in nodes:
        kids = n.get("children")
        if kids:
            best = max(best, _max_depth(kids, at + 1))
    return best


def test_import_total_folder_depth_stays_under_the_loader_limit():
    # 9 container levels x 23-folder member paths: worst case within the nesting cap.
    structure = archives.extract_zip_to_structure(_deep_zip(9, 23))
    depth = _max_depth(structure)
    # +1 wrapper folder +1 root on filing; generous reserve for the user's own target folder.
    assert depth <= archives._MAX_TOTAL_FOLDER_DEPTH, f"Import erzeugt Tiefe {depth}"
    assert depth + 60 < _MAX_TREE_DEPTH, f"zu nah am Lade-Limit: {depth}"


def test_total_depth_invariant_against_the_loader_cap():
    # Static invariant: whatever the per-member and nesting caps are, one import
    # can never reach the loader's refusal depth (with reserve for the target folder).
    assert archives._MAX_TOTAL_FOLDER_DEPTH + 60 < _MAX_TREE_DEPTH


def test_normal_deep_nesting_keeps_its_folders():
    # A plain 10-level zip chain (flat names) must still build its full folder tree.
    blob = _zip({"doc.pdf": create_valid_pdf(pages=1)})
    for i in range(10, 0, -1):
        blob = _zip({f"lvl{i}.zip": blob})
    structure = archives.extract_zip_to_structure(blob)
    names = [n["name"] for n in _walk(structure)]
    assert "doc.pdf" in names and not any("zu tief" in n for n in names)
    assert _max_depth(structure) == 11


def _walk(nodes):
    for n in nodes:
        yield n
        yield from _walk(n.get("children") or [])
