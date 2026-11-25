"""Synthetic PDFs with deliberately tricky page geometry (test-only, pikepdf-built).

Used by the non-raster parity tests (page count / page size / split). Every page
carries a unique text label (``PAGE-007``) so the tests can check order and
content of split parts via text extraction (done with fitz *in the test only*).
"""

import io
from typing import Dict, List, Optional

import pikepdf
from pikepdf import Array, Dictionary, Name, Pdf


def label(i: int) -> str:
    return "PAGE-%03d" % i


def make_pdf(specs: Optional[List[Dict]] = None, *, pages: int = 0,
             inherit: Optional[Dict] = None, encrypt: bool = False,
             objstm: bool = False, link_uri: bool = False,
             link_goto: bool = False, size: tuple = (595, 842)) -> bytes:
    """Build a PDF.

    ``specs``: one dict per page with optional ``mediabox`` / ``cropbox`` (4 numbers),
    ``rotate`` (int), ``userunit`` (float), ``no_mediabox`` (True drops the box).
    ``pages``: shortcut for N default pages (sizes from ``size``).
    ``inherit``: keys (``MediaBox``/``Rotate``/``CropBox``/``Resources``) put on the
    ``/Pages`` root and REMOVED from the leaf pages (inherited page-tree attributes).
    """
    if specs is None:
        specs = [{} for _ in range(pages)]
    pdf = Pdf.new()
    font = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1,
                                        BaseFont=Name.Helvetica))
    resources = Dictionary(Font=Dictionary(F1=font))
    for i, spec in enumerate(specs):
        mb = spec.get("mediabox") or [0, 0, size[0], size[1]]
        pdf.add_blank_page(page_size=(100, 100))
        page = pdf.pages[-1]
        page.obj.MediaBox = Array(mb)
        if spec.get("no_mediabox"):
            del page.obj["/MediaBox"]
        if spec.get("cropbox"):
            page.obj.CropBox = Array(spec["cropbox"])
        if spec.get("rotate"):
            page.obj.Rotate = spec["rotate"]
        if spec.get("userunit"):
            page.obj.UserUnit = spec["userunit"]
        x0, y0 = (mb[0], mb[1])
        text = "BT /F1 24 Tf %s %s Td (%s) Tj ET" % (x0 + 72, y0 + 100, label(i))
        page.obj.Contents = pdf.make_stream(text.encode())
        if not (inherit and "Resources" in inherit):
            page.obj.Resources = resources
        else:
            if "/Resources" in page.obj:
                del page.obj["/Resources"]
        if link_uri or link_goto:
            annots = Array()
            if link_uri:
                annots.append(pdf.make_indirect(Dictionary(
                    Type=Name.Annot, Subtype=Name.Link, Rect=Array([72, 60, 200, 90]),
                    Border=Array([0, 0, 0]),
                    A=Dictionary(S=Name.URI, URI=pikepdf.String("https://example.com/")))))
            if link_goto and len(specs) > 1:
                target = pdf.pages[(i + 1) % len(specs)] if i + 1 < len(pdf.pages) else pdf.pages[0]
                annots.append(pdf.make_indirect(Dictionary(
                    Type=Name.Annot, Subtype=Name.Link, Rect=Array([72, 20, 200, 50]),
                    Border=Array([0, 0, 0]),
                    Dest=Array([target.obj, Name.Fit]), P=page.obj)))
            page.obj.Annots = annots
    root = pdf.Root.Pages
    if inherit:
        for k, v in inherit.items():
            if k == "Resources":
                root["/Resources"] = resources
                continue
            root["/" + k] = Array(v) if isinstance(v, (list, tuple)) else v
            for p in pdf.pages:
                if "/" + k in p.obj:
                    del p.obj["/" + k]
    buf = io.BytesIO()
    kw = {}
    if objstm:
        kw["object_stream_mode"] = pikepdf.ObjectStreamMode.generate
    if encrypt:
        kw["encryption"] = pikepdf.Encryption(user="", owner="owner", R=6)
    pdf.save(buf, **kw)
    return buf.getvalue()


def broken_startxref(data: bytes) -> bytes:
    """Corrupt the xref pointer + truncate the tail → readers must reconstruct."""
    i = data.rfind(b"startxref")
    return data[:i] + b"startxref\n999999\n%%EOF\n"


def page_labels_fitz(data: bytes) -> List[str]:
    """Text per page via fitz (test-only oracle)."""
    import fitz
    with fitz.open(stream=data, filetype="pdf") as d:
        return [p.get_text().strip() for p in d]
