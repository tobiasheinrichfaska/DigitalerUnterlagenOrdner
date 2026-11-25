"""Characterisation/parity tests for the NON-raster PDF operations (page count, page
size, split into chunks) — PyMuPDF replacement, step 1 (docs/pymupdf-extract-msg-ersatz.md).

Written against the fitz implementation first (green), kept green after the swap to
pikepdf. fitz is used in the TESTS as an independent oracle (text extraction, page
rect) — never in production code for these operations any more.

Known, deliberate deviation (documented below in ``test_split_*link*``): internal
(GoTo / /Dest) link annotations are dropped when a chunk is cut — their targets live
in other chunks and carrying them would drag the whole source page tree into every
part. URI links are kept. Same family as the 'text-PDF limitation' in CLAUDE.md.
"""

import io

import fitz
import pikepdf
import pytest
from pypdf import PdfReader

from core.engine import RealEngine
from formats.pdf_node import PDFNode
from services.render import page_count, page_dims
from pdf_synth import (broken_startxref, label, make_pdf, page_labels_fitz)

ENGINE = RealEngine()
TOL = 0.01


# ---------------------------------------------------------------- page geometry cases
# (id, pdf-bytes factory, expected [(w, h), ...]) — the expectations are hand-derived
# from the PDF spec (box / rotation / UserUnit semantics) and verified against fitz.
A4 = (595.0, 842.0)
CASES = [
    ("plain", lambda: make_pdf(pages=2), [A4, A4]),
    ("rot90", lambda: make_pdf([{"rotate": 90}]), [(842.0, 595.0)]),
    ("rot180", lambda: make_pdf([{"rotate": 180}]), [A4]),
    ("rot270", lambda: make_pdf([{"rotate": 270}]), [(842.0, 595.0)]),
    ("rot-90", lambda: make_pdf([{"rotate": -90}]), [(842.0, 595.0)]),
    ("rot450", lambda: make_pdf([{"rotate": 450}]), [(842.0, 595.0)]),
    ("mediabox-offset", lambda: make_pdf([{"mediabox": [100, 200, 695, 1042]}]), [A4]),
    ("mediabox-negative-origin", lambda: make_pdf([{"mediabox": [-300, -400, 295, 442]}]), [A4]),
    ("mediabox-inverted", lambda: make_pdf([{"mediabox": [595, 842, 0, 0]}]), [A4]),
    ("mediabox-float", lambda: make_pdf([{"mediabox": [0, 0, 612.5, 791.25]}]), [(612.5, 791.25)]),
    ("cropbox", lambda: make_pdf([{"mediabox": [0, 0, 612, 792], "cropbox": [50, 50, 350, 450]}]),
     [(300.0, 400.0)]),
    ("cropbox-partly-outside",
     lambda: make_pdf([{"mediabox": [0, 0, 612, 792], "cropbox": [-100, -100, 300, 300]}]),
     [(300.0, 300.0)]),
    ("cropbox-rotated",
     lambda: make_pdf([{"mediabox": [0, 0, 612, 792], "cropbox": [50, 50, 350, 450], "rotate": 90}]),
     [(400.0, 300.0)]),
    ("userunit", lambda: make_pdf([{"userunit": 2.0}]), None),  # expectation = fitz oracle
    ("userunit-half", lambda: make_pdf([{"userunit": 0.5}]), None),
    ("userunit-and-rotate", lambda: make_pdf([{"userunit": 2.0, "rotate": 90, "mediabox": [0, 0, 100, 200]}]),
     [(400.0, 200.0)]),
    ("userunit-zero", lambda: make_pdf([{"userunit": 0.0001}]), None),
    ("rot45-rounds", lambda: make_pdf([{"rotate": 45}]), None),
    ("mediabox-empty", lambda: make_pdf([{"mediabox": [0, 0, 0, 0]}]), [(612.0, 792.0)]),
    ("cropbox-fully-outside", lambda: make_pdf([{"cropbox": [1000, 1000, 2000, 2000]}]), None),
    ("mixed-sizes", lambda: make_pdf([{}, {"mediabox": [0, 0, 300, 400]}, {"rotate": 90}]),
     [A4, (300.0, 400.0), (842.0, 595.0)]),
    ("inherited-mediabox", lambda: make_pdf(pages=2, inherit={"MediaBox": [0, 0, 400, 500]}),
     [(400.0, 500.0), (400.0, 500.0)]),
    ("inherited-rotate", lambda: make_pdf(pages=2, inherit={"Rotate": 90}),
     [(842.0, 595.0), (842.0, 595.0)]),
    ("inherited-cropbox",
     lambda: make_pdf(pages=1, inherit={"CropBox": [0, 0, 200, 300]}), [(200.0, 300.0)]),
    ("no-mediabox-default", lambda: make_pdf([{"no_mediabox": True}]), None),  # fitz default
    ("encrypted-empty-pw", lambda: make_pdf(pages=3, encrypt=True), [A4] * 3),
    ("objstm-xrefstream", lambda: make_pdf(pages=3, objstm=True), [A4] * 3),
    ("broken-xref", lambda: broken_startxref(make_pdf(pages=3)), [A4] * 3),
    ("300-pages", lambda: make_pdf(pages=300), [A4] * 300),
]
IDS = [c[0] for c in CASES]


def _fitz_dims(data):
    with fitz.open(stream=data, filetype="pdf") as d:
        return [(p.rect.width, p.rect.height) for p in d]


def _close(a, b):
    return len(a) == len(b) and all(
        abs(x[0] - y[0]) <= TOL and abs(x[1] - y[1]) <= TOL for x, y in zip(a, b))


@pytest.mark.parametrize("cid,factory,expected", CASES, ids=IDS)
def test_page_dims_matches_expected_and_fitz(cid, factory, expected):
    data = factory()
    oracle = _fitz_dims(data)
    if expected is not None:
        assert _close(oracle, expected), "test expectation wrong for fitz: %r" % (oracle,)
    got = page_dims(data)
    assert _close(got, oracle), "%s: %r != fitz %r" % (cid, got[:3], oracle[:3])


@pytest.mark.parametrize("cid,factory,expected", CASES, ids=IDS)
def test_page_count_matches_fitz(cid, factory, expected):
    data = factory()
    with fitz.open(stream=data, filetype="pdf") as d:
        n = d.page_count
    assert page_count(data) == n
    assert PDFNode("x", pdf_data=data).pdf_length == n
    assert ENGINE.page_count(data) == n


def test_page_count_accepts_bytesio_and_garbage():
    data = make_pdf(pages=4)
    assert page_count(io.BytesIO(data)) == 4
    assert page_dims(io.BytesIO(data)) == [A4] * 4 or _close(page_dims(io.BytesIO(data)), [A4] * 4)
    for junk in (b"", b"not a pdf at all", b"%PDF-1.4\ngarbage"):
        assert page_count(junk) == 0
        assert page_dims(junk) == []
        assert PDFNode("x", pdf_data=junk or None).pdf_length == 0
    assert page_count(None) == 0 and page_dims(None) == []


def test_zero_page_pdf():
    pdf = pikepdf.Pdf.new()
    buf = io.BytesIO()
    pdf.save(buf)
    data = buf.getvalue()
    assert page_count(data) == 0
    assert page_dims(data) == []
    assert PDFNode("x", pdf_data=data).pdf_length == 0
    assert ENGINE.split_chunks(data, 3) == [] if _fitz_can_open(data) else True


def _fitz_can_open(data):
    try:
        with fitz.open(stream=data, filetype="pdf"):
            return True
    except Exception:
        return False


def test_sanitized_broken_xref_counts_agree():
    """Beschädigte xref → sanitize → Zählung: alle Wege liefern dieselbe Seitenzahl."""
    from infra.tools import sanitize_pdf
    broken = broken_startxref(make_pdf(pages=5))
    fixed = sanitize_pdf(broken)
    assert page_count(fixed) == 5
    assert page_count(broken) == 5
    assert len(page_dims(fixed)) == 5


# ---------------------------------------------------------------- split_chunks
SPLIT_SOURCES = [
    ("plain7", lambda: make_pdf(pages=7)),
    ("geometry", lambda: make_pdf([{"rotate": 90}, {"mediabox": [100, 100, 400, 600]},
                                   {"mediabox": [0, 0, 612, 792], "cropbox": [10, 10, 300, 400]},
                                   {"rotate": 270}, {}, {"mediabox": [0, 0, 300, 300]},
                                   {"rotate": 180}])),
    ("inherited-box-rot", lambda: make_pdf(pages=7, inherit={"MediaBox": [0, 0, 400, 500],
                                                              "Rotate": 90})),
    ("inherited-resources", lambda: make_pdf(pages=7, inherit={"Resources": True})),
    ("encrypted", lambda: make_pdf(pages=7, encrypt=True)),
    ("objstm", lambda: make_pdf(pages=7, objstm=True)),
    ("broken-xref", lambda: broken_startxref(make_pdf(pages=7))),
]


@pytest.mark.parametrize("sid,factory", SPLIT_SOURCES, ids=[s[0] for s in SPLIT_SOURCES])
@pytest.mark.parametrize("size", [1, 3, 7, 50])
def test_split_chunks_order_content_geometry(sid, factory, size):
    data = factory()
    src_dims = _fitz_dims(data)
    chunks = ENGINE.split_chunks(data, size)
    n = len(src_dims)
    assert [c[1] for c in chunks] == [min(size, n - i) for i in range(0, n, size)]
    cursor = 0
    for blob, cnt in chunks:
        assert isinstance(blob, bytes) and blob.startswith(b"%PDF")
        # valid PDF: structurally checkable, right page count
        with pikepdf.open(io.BytesIO(blob)) as p:
            assert len(p.pages) == cnt
            p.save(io.BytesIO())  # qpdf walks every reachable object
        PdfReader(io.BytesIO(blob), strict=True)
        assert page_count(blob) == cnt
        # geometry (size incl. rotation/crop/inheritance) survives
        assert _close(_fitz_dims(blob), src_dims[cursor:cursor + cnt]), (sid, cursor)
        # order + content
        assert page_labels_fitz(blob) == [label(cursor + k) for k in range(cnt)]
        cursor += cnt
    assert cursor == n


def test_split_chunks_size_below_one_is_clamped():
    data = make_pdf(pages=3)
    assert [c[1] for c in ENGINE.split_chunks(data, 0)] == [1, 1, 1]
    assert [c[1] for c in ENGINE.split_chunks(data, -5)] == [1, 1, 1]


def test_split_chunks_large_document():
    data = make_pdf(pages=300)
    chunks = ENGINE.split_chunks(data, 100)
    assert [c[1] for c in chunks] == [100, 100, 100]
    assert page_labels_fitz(chunks[1][0])[0] == label(100)
    assert page_labels_fitz(chunks[2][0])[-1] == label(299)


def test_split_chunks_garbage_raises():
    with pytest.raises(Exception):
        ENGINE.split_chunks(b"definitely not a pdf", 3)


def test_split_keeps_uri_links():
    data = make_pdf(pages=4, link_uri=True)
    for blob, cnt in ENGINE.split_chunks(data, 2):
        with fitz.open(stream=blob, filetype="pdf") as d:
            for p in d:
                uris = [lk.get("uri") for lk in p.get_links()]
                # exact list-element match (not a substring test of a sanitised URL)
                assert uris.count("https://example.com/") >= 1


def test_split_internal_links_do_not_drag_in_other_pages():
    """DELIBERATE DEVIATION: internal GoTo links are dropped on split (their target pages are
    not in the chunk; kept they would be dead links). What must hold with ANY engine: a
    1-page chunk of a doc with internal links has exactly 1 page, stays small (no linked
    page dragged along) and carries no dead /Dest."""
    n = 40
    data = make_pdf(pages=n, link_uri=True, link_goto=True, payload=20000)
    chunks = ENGINE.split_chunks(data, 1)
    assert len(chunks) == n
    biggest = max(len(b) for b, _ in chunks)
    # one page = ~20 KB of image; a part that dragged a link target along would be >= 40 KB
    assert biggest < 30000, (biggest, len(data))
    for blob, cnt in chunks[:5]:
        assert page_count(blob) == 1
        with pikepdf.open(io.BytesIO(blob)) as p:
            assert len(p.pages) == 1
    for blob, cnt in chunks[:5]:
        with pikepdf.open(io.BytesIO(blob)) as p:
            for a in p.pages[0].obj.get("/Annots", []):
                assert "/Dest" not in a
