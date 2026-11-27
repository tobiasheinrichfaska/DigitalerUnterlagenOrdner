# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Audit m3 Y-6 (AcroForm survives .belegtool save/load) and Y-4 (TOC text, no boxes)."""
import io
import os

import pikepdf
from pypdf import PdfReader

from formats import toc_export as T
from formats.pdf_node import PDFNode

FORM = os.path.join(os.path.dirname(__file__), "..", "webui", "public", "spike-form.pdf")


def _blank(n=1):
    p = pikepdf.Pdf.new()
    for _ in range(n):
        p.add_blank_page(page_size=(200, 300))
    b = io.BytesIO()
    p.save(b)
    return b.getvalue()


def test_acroform_survives_belegtool_roundtrip(tmp_path):
    data = open(FORM, "rb").read()
    with pikepdf.open(io.BytesIO(data)) as src:
        nfields = len(src.Root.AcroForm.Fields)
    assert nfields >= 1
    from core.model import Document, Node
    from core.bridge import load_belegtool, save_belegtool
    form = Node(name="form", original_data=data, pdf_length=1)
    plain = Node(name="plain", original_data=_blank(2), pdf_length=2)
    doc = Document(Node(name="root", is_folder=True, children=(plain, form)))
    out = str(tmp_path / "f.belegtool")
    save_belegtool(doc, out)
    back = load_belegtool(out)
    nodes = {c.name: c for c in back.root.children}
    for name, expect in (("form", True), ("plain", False)):
        n = nodes[name]
        with pikepdf.open(io.BytesIO(n.current_data or n.original_data)) as q:
            assert ("/AcroForm" in q.Root) == expect
            if expect:
                assert len(q.Root.AcroForm.Fields) == nfields


def test_toc_text_has_no_box_glyphs(tmp_path):
    p = str(tmp_path / "a.pdf")
    T.export_pdf([PDFNode(name="Łódź Привет 日本 a\tb", pdf_data=_blank(1))], p)
    text = PdfReader(p).pages[0].extract_text()
    assert "■" not in text and "■" not in text
    assert "\t" not in text


def _text_form(name, value):
    from reportlab.pdfgen import canvas
    b = io.BytesIO()
    c = canvas.Canvas(b)
    c.acroForm.textfield(name=name, x=50, y=700, width=100, height=20, value=value)
    c.showPage()
    c.save()
    return b.getvalue()


def test_z1_colliding_field_names_are_made_unique():
    from formats.pdf_storage import PDFStorage
    root = PDFNode(name="r", is_folder=True)
    for nm, v in (("n1", "AAA"), ("n2", "BBB"), ("n3", "CCC")):
        n = PDFNode(name=nm, parent=root, pdf_data=_text_form("name", v))
        root.children.append(n)
    st = PDFStorage()
    st.root = root
    r = PdfReader(io.BytesIO(st.to_bytes()))
    tops = [f.get_object() for f in r.trailer["/Root"]["/AcroForm"]["/Fields"]]
    names = [str(f["/T"]) for f in tops]
    assert names[0] == "name" and len(set(names)) == 3
    assert {str(f["/V"]) for f in tops} == {"AAA", "BBB", "CCC"}
    assert {k: v.get("/V") for k, v in r.get_fields().items()}.__len__() == 3
