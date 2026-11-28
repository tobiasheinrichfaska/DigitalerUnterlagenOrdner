# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Regression tests for corpus findings CP-1 (rotate on repaired PDF), CP-2 (junk before %PDF-),
CP-3 (dead link annotations in page-level split export)."""
import io

import pikepdf
import pypdfium2 as pdfium
from reportlab.pdfgen import canvas

from core.engine import RealEngine
from formats.pdf_node import PDFNode
from formats.toc_export import _slice_leaf
from infra.tools import sanitize_pdf


def _pdf(pages=5):
    b = io.BytesIO()
    c = canvas.Canvas(b)
    for i in range(pages):
        c.drawString(100, 700, f"Seite {i}")
        c.showPage()
    c.save()
    return b.getvalue()


def test_cp1_rotate_on_repaired_truncated_pdf():
    repaired = sanitize_pdf(_pdf()[:-600])
    out = RealEngine().rotate(repaired, 90)
    with pikepdf.open(io.BytesIO(out)) as p:
        assert len(p.pages) == 5
        assert all(int(pg.obj.get("/Rotate", 0)) % 360 == 90 for pg in p.pages)


def test_cp2_junk_before_header_is_normalised():
    data = b"JUNK" * 375 + _pdf(3)
    out = sanitize_pdf(data)
    doc = pdfium.PdfDocument(out)
    assert len(doc) == 3


def test_cp3_slice_leaf_drops_dead_internal_links():
    b = io.BytesIO()
    c = canvas.Canvas(b)
    for i in range(4):
        c.bookmarkPage(f"p{i}")
        c.drawString(100, 700, f"S{i}")
        c.linkRect("", f"p{(i + 2) % 4}", (10, 10, 100, 40))
        c.linkURL("https://example.org", (10, 100, 100, 140))
        c.showPage()
    c.save()
    leaf = PDFNode(name="d", pdf_data=b.getvalue())
    part = _slice_leaf(leaf, [0, 1])
    with pikepdf.open(io.BytesIO(part.current_pdf_data)) as p:
        n_uri = 0
        own = {pg.obj.objgen for pg in p.pages}
        for pg in p.pages:
            for a in pg.obj.get("/Annots", []):
                dest = a.get("/Dest")
                if dest is not None:
                    assert dest[0] is not None and dest[0].objgen in own
                act = a.get("/A")
                if act is not None and act.get("/S") == pikepdf.Name.GoTo:
                    d = act.get("/D")
                    assert d is not None and not isinstance(d, pikepdf.Name) and d[0].objgen in own
                act = a.get("/A")
                if act is not None and act.get("/S") == pikepdf.Name.URI:
                    n_uri += 1
        assert n_uri == 2
