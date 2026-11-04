"""Load integrity of corrupt .belegtool files (QS-Gegenprüfung 2026-11-04: H-1, M-3, N-4).

A damaged file must open with VISIBLE warnings (``PDFStorage.load_warnings`` →
``CoreApi.open``'s ``warning`` field), never silently empty or flat, and a degraded
open must NOT bind the on-disk path — otherwise a plain Ctrl+S overwrites the
still-rescuable original with the degraded tree (the H-1 data-loss chain).
"""

import io
import json
from pathlib import Path

import fitz
import pytest
from pypdf import PdfReader, PdfWriter

import formats.pdf_storage as ps
from core.api import CoreApi
from core.bridge import save_belegtool
from core.model import Document, Node
from formats.pdf_storage import PDFStorage


def _pdf(n=1, tag="P"):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=200, height=200).insert_text((50, 80), f"{tag}{i}")
    b = d.tobytes()
    d.close()
    return b


def _page_texts(data: bytes):
    d = fitz.open(stream=data, filetype="pdf")
    try:
        return [p.get_text().strip() for p in d]
    finally:
        d.close()


def _save(tmp_path, children, name="doc"):
    doc = Document(Node(name="root", is_folder=True, children=tuple(children)))
    path = str(tmp_path / f"{name}.belegtool")
    save_belegtool(doc, path)
    return path


def _crafted(tmp_path, json_str, n_pages=2, name="crafted"):
    """A .belegtool whose /JSONStructure is exactly ``json_str`` (crafted corruption)."""
    writer = PdfWriter()
    reader = PdfReader(io.BytesIO(_pdf(n_pages)))
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({"/JSONStructure": json_str})
    path = str(tmp_path / f"{name}.belegtool")
    with open(path, "wb") as f:
        writer.write(f)
    return path


def _flaky_reader(monkeypatch, fail_calls):
    """Make the Nth..Mth PdfReader construction in pdf_storage raise (the page-tree
    parse is call 2; the sanitize-retry is call 3)."""
    real = ps.PdfReader
    calls = {"n": 0}

    def make(*a, **k):
        calls["n"] += 1
        if calls["n"] in fail_calls:
            raise Exception("synthetischer Seitenbaum-Defekt")
        return real(*a, **k)

    monkeypatch.setattr(ps, "PdfReader", make)
    return calls


# --- H-1: unreadable page tree ------------------------------------------------

def test_unreadable_page_tree_warns_instead_of_silent_empty(tmp_path, monkeypatch):
    path = _save(tmp_path, [Node(name="leaf", original_data=_pdf(2), pdf_length=2)])
    _flaky_reader(monkeypatch, fail_calls={2, 3})  # page tree broken, repair fails too
    storage = PDFStorage(path)
    warnings = list(getattr(storage, "load_warnings", []))
    assert any("Seitenbaum" in w for w in warnings), warnings
    assert storage.root.children == []  # nothing rescuable — but LOUDLY so


def test_unreadable_page_tree_rescued_by_repair(tmp_path, monkeypatch):
    """The repair retry (a full pikepdf rewrite) recovers the content, but the repaired
    bytes are NOT the on-disk file — the load must stay degraded (warning → Save-As)."""
    path = _save(tmp_path, [Node(name="leaf", original_data=_pdf(2), pdf_length=2)])
    _flaky_reader(monkeypatch, fail_calls={2})  # repair retry (call 3) succeeds
    storage = PDFStorage(path)
    assert [c.name for c in storage.root.children] == ["leaf"]
    warnings = list(getattr(storage, "load_warnings", []))
    assert any("repariert" in w for w in warnings), warnings


def test_real_broken_count_is_repaired_with_warning(tmp_path):
    """A REAL page-tree defect (non-numeric /Count): pikepdf regenerates the tree, the
    structure loads fully, and the load reports the repair (never silently empty)."""
    structure = {"children": [{"name": "A", "pdf_length": 2}]}
    path = _crafted(tmp_path, json.dumps(structure), n_pages=2, name="broken_count")
    raw = Path(path).read_bytes()
    assert raw.count(b"/Count 2") >= 1  # precondition: the raw tree is visible
    Path(path).write_bytes(raw.replace(b"/Count 2", b"/Count x", 1))
    storage = PDFStorage(path)
    warnings = list(getattr(storage, "load_warnings", []))
    assert [c.name for c in storage.root.children] == ["A"], warnings
    assert storage.root.children[0].pdf_length == 2
    assert any("repariert" in w or "Seitenbaum" in w for w in warnings), warnings


def test_open_degraded_does_not_bind_path(tmp_path, monkeypatch):
    """CoreApi.open on a degraded file: ok with warning, but Ctrl+S must become
    Save-As (document_path None) so the original is never overwritten."""
    path = _save(tmp_path, [Node(name="leaf", original_data=_pdf(2), pdf_length=2)])
    _flaky_reader(monkeypatch, fail_calls={2, 3})
    core = CoreApi()
    resp = core.open(None, path)
    assert resp["ok"] is True
    assert "Seitenbaum" in resp.get("warning", ""), resp
    assert core.document_path(resp["session"]) is None


def test_open_intact_file_binds_path_and_has_no_warning(tmp_path):
    path = _save(tmp_path, [Node(name="leaf", original_data=_pdf(2), pdf_length=2)])
    core = CoreApi()
    resp = core.open(None, path)
    assert resp["ok"] is True and "warning" not in resp
    assert core.document_path(resp["session"]) == path


# --- M-3b: structure JSON unparseable → one-node fallback must warn -------------

def test_invalid_structure_json_falls_back_with_warning(tmp_path):
    path = _crafted(tmp_path, "{dies ist kein json", n_pages=2)
    storage = PDFStorage(path)
    warnings = list(getattr(storage, "load_warnings", []))
    assert any("Dokumentstruktur" in w for w in warnings), warnings
    assert len(storage.root.children) == 1  # fallback single-node import still works
    assert not storage.root.children[0].is_folder


# --- M-3a: nodes past the page end --------------------------------------------

def test_truncated_and_skipped_nodes_warn(tmp_path):
    structure = {"children": [
        {"name": "A", "pdf_length": 5},
        {"name": "B", "pdf_length": 1},
    ]}
    path = _crafted(tmp_path, json.dumps(structure), n_pages=3)
    storage = PDFStorage(path)
    warnings = list(getattr(storage, "load_warnings", []))
    assert any("A" in w and "gekürzt" in w for w in warnings), warnings
    assert any("B" in w and "übersprungen" in w for w in warnings), warnings
    kids = storage.root.children
    assert [c.name for c in kids] == ["A"] and kids[0].pdf_length == 3


# --- N-4: hostile pdf_length values --------------------------------------------

def test_negative_pdf_length_does_not_rewind_page_counter(tmp_path):
    structure = {"children": [
        {"name": "A", "pdf_length": 2},
        {"name": "NEG", "pdf_length": -1},
        {"name": "B", "pdf_length": 1},
    ]}
    path = _crafted(tmp_path, json.dumps(structure), n_pages=4)
    storage = PDFStorage(path)
    by_name = {c.name: c for c in storage.root.children}
    assert by_name["NEG"].pdf_length == 0
    # B must get page P2 — NOT a duplicate of A's P1 (the rewind bug)
    assert _page_texts(by_name["B"].original_pdf_data) == ["P2"]
    warnings = list(getattr(storage, "load_warnings", []))
    assert any("NEG" in w and "Seitenanzahl" in w for w in warnings), warnings


def test_non_int_pdf_length_degrades_that_node_only(tmp_path):
    structure = {"children": [
        {"name": "A", "pdf_length": "2"},
        {"name": "B", "pdf_length": 2},
    ]}
    path = _crafted(tmp_path, json.dumps(structure), n_pages=2)
    storage = PDFStorage(path)
    by_name = {c.name: c for c in storage.root.children}
    assert by_name["A"].pdf_length == 0  # corrupt value → empty leaf, not a crash
    assert by_name["B"].pdf_length == 2  # the honest sibling keeps its pages
    warnings = list(getattr(storage, "load_warnings", []))
    assert any("A" in w and "Seitenanzahl" in w for w in warnings), warnings


def test_zero_pdf_length_stays_legitimate(tmp_path):
    """0-page leaves exist legitimately (Known Limitations) — no warning for them."""
    structure = {"children": [
        {"name": "EMPTY", "pdf_length": 0},
        {"name": "B", "pdf_length": 2},
    ]}
    path = _crafted(tmp_path, json.dumps(structure), n_pages=2)
    storage = PDFStorage(path)
    assert not getattr(storage, "load_warnings", [])
    by_name = {c.name: c for c in storage.root.children}
    assert by_name["EMPTY"].pdf_length == 0 and by_name["B"].pdf_length == 2


# --- H-1b/H-1c (QS-Bewertung 2026-11-04): rewritten/externally edited files ------

def test_structure_in_object_stream_still_loads(tmp_path):
    """A .belegtool rewritten by another tool (qpdf/Acrobat 'optimize') can move the
    Info dict into a compressed object stream — the raw-bytes marker check misses it,
    and the file used to load silently FLAT (Ctrl+S then destroyed the structure)."""
    import pikepdf
    path = _save(tmp_path, [
        Node(name="F", is_folder=True,
             children=(Node(name="leaf", original_data=_pdf(2), pdf_length=2),)),
    ], name="objstm")
    rewritten = str(tmp_path / "rewritten.belegtool")
    with pikepdf.open(path) as pdf:
        pdf.save(rewritten, object_stream_mode=pikepdf.ObjectStreamMode.generate,
                 compress_streams=True)
    raw = Path(rewritten).read_bytes()
    if b"/JSONStructure" in raw:
        pytest.skip("pikepdf kept the marker raw — vector not reproducible here")
    storage = PDFStorage(rewritten)
    names = [c.name for c in storage.root.children]
    assert names == ["F"], (names, storage.load_warnings)  # structure survived
    assert storage.root.children[0].is_folder


def test_belegtool_without_structure_warns_and_unbinds(tmp_path):
    """A .belegtool whose structure is gone entirely (stripped metadata) must degrade
    LOUDLY — it always carries one when our writer produced it."""
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(_pdf(2))).pages:
        writer.add_page(page)
    path = str(tmp_path / "stripped.belegtool")
    with open(path, "wb") as f:
        writer.write(f)
    storage = PDFStorage(path)
    warnings = list(getattr(storage, "load_warnings", []))
    assert any("Dokumentstruktur fehlt" in w for w in warnings), warnings
    core = CoreApi()
    resp = core.open(None, path)
    assert resp["ok"] and "Dokumentstruktur fehlt" in resp.get("warning", "")
    assert core.document_path(resp["session"]) is None


def test_plain_pdf_without_marker_keeps_the_fast_path(tmp_path):
    """A plain .pdf import has no structure by nature — no warning, no full-parse
    requirement, same behaviour as before."""
    p = tmp_path / "plain.pdf"
    p.write_bytes(_pdf(2))
    storage = PDFStorage(str(p))
    assert not getattr(storage, "load_warnings", [])
    assert len(storage.root.children) == 1


def test_extra_pages_beyond_structure_warn(tmp_path):
    """Pages appended by an external editor used to be dropped SILENTLY on the next
    save — the structure consumes fewer pages than the file holds."""
    structure = {"children": [{"name": "A", "pdf_length": 2}]}
    path = _crafted(tmp_path, json.dumps(structure), n_pages=5)
    storage = PDFStorage(path)
    warnings = list(getattr(storage, "load_warnings", []))
    assert any("mehr als die Struktur beschreibt" in w for w in warnings), warnings
    core = CoreApi()
    resp = core.open(None, path)
    assert "mehr als die Struktur beschreibt" in resp.get("warning", "")
    assert core.document_path(resp["session"]) is None


def test_exact_page_consumption_stays_warning_free(tmp_path):
    structure = {"children": [{"name": "A", "pdf_length": 2}, {"name": "B", "pdf_length": 1}]}
    path = _crafted(tmp_path, json.dumps(structure), n_pages=3)
    storage = PDFStorage(path)
    assert not getattr(storage, "load_warnings", [])


def test_vz_values_are_coerced_to_int_or_none(tmp_path):
    """Hand-edited/foreign vz values must never crash a later Merge (min/max over
    mixed types): non-int coerces or drops on load."""
    structure = {"children": [
        {"name": "A", "pdf_length": 1, "vz_start": "2024", "vz_end": 2024},
        {"name": "B", "pdf_length": 1, "vz_start": {"bogus": 1}, "vz_end": None},
    ]}
    path = _crafted(tmp_path, json.dumps(structure), n_pages=2)
    by_name = {c.name: c for c in PDFStorage(path).root.children}
    assert by_name["A"].vz_start == 2024 and by_name["A"].vz_end == 2024
    assert by_name["B"].vz_start is None and by_name["B"].vz_end is None


# --- degraded sessions suggest a rescue name for Save-As -------------------------

def test_session_degraded_flag_set_and_cleared_by_save(tmp_path, monkeypatch):
    path = _save(tmp_path, [Node(name="leaf", original_data=_pdf(2), pdf_length=2)])
    _flaky_reader(monkeypatch, fail_calls={2, 3, 4})
    core = CoreApi()
    sid = core.open(None, path)["session"]
    assert core.session_degraded(sid) is True
    monkeypatch.undo()
    out = str(tmp_path / "rescued.belegtool")
    assert core.save(sid, out)["ok"] is True
    assert core.session_degraded(sid) is False  # the rescue is saved → normal session


def test_session_degraded_false_for_healthy_open(tmp_path):
    path = _save(tmp_path, [Node(name="leaf", original_data=_pdf(2), pdf_length=2)])
    core = CoreApi()
    sid = core.open(None, path)["session"]
    assert core.session_degraded(sid) is False


# --- import of a corrupt .belegtool must be refused with a visible reason -------

def test_import_corrupt_belegtool_is_refused_with_reason(tmp_path, monkeypatch):
    good = _save(tmp_path, [Node(name="ok", original_data=_pdf(1), pdf_length=1)], name="good")
    bad = _save(tmp_path, [Node(name="leaf", original_data=_pdf(2), pdf_length=2)], name="bad")
    core = CoreApi()
    sid = core.open(None, good)["session"]
    _flaky_reader(monkeypatch, fail_calls={2, 3})
    resp = core.import_paths(sid, [bad])
    assert resp["ok"] is False
    assert "beschädigt" in resp.get("error", ""), resp
