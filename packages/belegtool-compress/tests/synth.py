# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""PDFs built with pikepdf only (no PyMuPDF), so the pdfium backend tests run without the oracle."""

import io
from typing import Dict, List, Optional

import pikepdf
from pikepdf import Array, Dictionary, Name, Pdf


def _content(rects) -> bytes:
    """Black/colour rectangles + one text line; rects = [(x, y, w, h, (r, g, b))]."""
    out = []
    for x, y, w, h, (r, g, b) in rects:
        out.append("%g %g %g rg %g %g %g %g re f" % (r, g, b, x, y, w, h))
    out.append("BT /F1 12 Tf 0 g 60 780 Td (Rechnung 4711 Betrag 1234 EUR) Tj ET")
    return " ".join(out).encode("latin-1")


def make_pdf(specs: Optional[List[Dict]] = None, *, pages: int = 1, size=(595, 842),
             rects=None, encrypt: bool = False, objstm: bool = False,
             annot: bool = False, widget: bool = False) -> bytes:
    """One page per spec dict: ``mediabox``, ``cropbox``, ``rotate``, ``userunit``.

    The default content has a red 100x100 square in the lower-left corner (0, 0) of the
    unrotated page - handy to verify orientation after /Rotate."""
    if specs is None:
        specs = [{} for _ in range(pages)]
    rects = rects if rects is not None else [(0, 0, 100, 100, (1, 0, 0))]
    pdf = Pdf.new()
    font = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    for spec in specs:
        mb = spec.get("mediabox") or [0, 0, size[0], size[1]]
        page = pdf.make_indirect(Dictionary(
            Type=Name.Page, MediaBox=Array(mb),
            Resources=Dictionary(Font=Dictionary(F1=font)),
            Contents=pdf.make_stream(_content(rects))))
        if spec.get("cropbox"):
            page.CropBox = Array(spec["cropbox"])
        if spec.get("rotate"):
            page.Rotate = spec["rotate"]
        if spec.get("userunit"):
            page.UserUnit = spec["userunit"]
        pdf.pages.append(pikepdf.Page(page))
    if annot:  # a green square annotation WITH an appearance stream, at (200, 200) 100x100
        ap = pdf.make_stream(b"0 1 0 rg 0 0 100 100 re f")
        ap.Type, ap.Subtype = Name.XObject, Name.Form
        ap.BBox = Array([0, 0, 100, 100])
        ann = pdf.make_indirect(Dictionary(Type=Name.Annot, Subtype=Name.Square, F=4,
                                           Rect=Array([200, 200, 300, 300]), AP=Dictionary(N=ap)))
        pdf.pages[0].obj.Annots = Array([ann])
    if widget:  # a form field (blue box) at (400, 200) 100x100, registered in the AcroForm
        ap = pdf.make_stream(b"0 0 1 rg 0 0 100 100 re f")
        ap.Type, ap.Subtype = Name.XObject, Name.Form
        ap.BBox = Array([0, 0, 100, 100])
        w = pdf.make_indirect(Dictionary(Type=Name.Annot, Subtype=Name.Widget, FT=Name.Tx, F=4,
                                         T=pikepdf.String("box"), Rect=Array([400, 200, 500, 300]),
                                         AP=Dictionary(N=ap)))
        pdf.pages[0].obj.Annots = Array(list(pdf.pages[0].obj.get("/Annots", [])) + [w])
        pdf.Root.AcroForm = Dictionary(Fields=Array([w]))
    buf = io.BytesIO()
    kw = {}
    if encrypt:
        kw["encryption"] = pikepdf.Encryption(user="", owner="owner", R=4)
    if objstm:
        kw["object_stream_mode"] = pikepdf.ObjectStreamMode.generate
    else:
        kw["object_stream_mode"] = pikepdf.ObjectStreamMode.disable
    pdf.save(buf, **kw)
    return buf.getvalue()


def encrypted_with_password(password: str = "geheim") -> bytes:
    pdf = Pdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    buf = io.BytesIO()
    pdf.save(buf, encryption=pikepdf.Encryption(user=password, owner=password, R=4))
    return buf.getvalue()


def broken_xref(data: bytes) -> bytes:
    bad = bytearray(data)
    i = bad.rfind(b"startxref")
    bad[i:] = b"startxref\n999999\n%%EOF\n"
    return bytes(bad)
