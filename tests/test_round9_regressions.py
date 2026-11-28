# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Round-9 review (w1): regressions of the round-8 hardening (R9-1..R9-5)."""
import base64
import io
import json
import os
import shutil
import sys
import tempfile
import time
import types
import uuid
from unittest import mock

import pytest

for _m in ("pythoncom", "win32com", "win32com.client"):
    if _m not in sys.modules:
        try:
            __import__(_m)
        except ImportError:
            sys.modules[_m] = types.ModuleType(_m)
if not hasattr(sys.modules["win32com"], "client"):
    sys.modules["win32com"].client = sys.modules["win32com.client"]

from pypdf import PdfWriter  # noqa: E402

from core.api import CoreApi  # noqa: E402
from universal_importer import converters  # noqa: E402


def _ok(html):
    out = converters.html_to_pdf(html)
    assert out.data.getvalue().startswith(b"%PDF")
    return out


# --- R9-1 ---------------------------------------------------------------
def test_r9_1_inline_data_uri_does_not_count_against_html_cap():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    big = "A" * (3 * 1024 * 1024)  # 3 MB payload, as a mail with a big inline image
    html = f'<html><body><p>Hallo</p><img src="data:image/png;base64,{b64}{big}"></body></html>'
    assert len(html) > converters._HTML_MAX_BYTES
    _ok(html)


def test_r9_1_real_markup_is_still_capped():
    with pytest.raises(ValueError, match="zu groß"):
        converters.html_to_pdf("<p>" + "a" * (converters._HTML_MAX_BYTES + 10))


# --- R9-2 ---------------------------------------------------------------
@pytest.mark.parametrize("html", [
    "".join(f"<p>Zeile {i}\n" for i in range(150)),
    "<ul>" + "".join(f"<li>Punkt {i}\n" for i in range(150)) + "</ul>",
    "<dl>" + "".join(f"<dt>a{i}<dd>b{i}" for i in range(150)) + "</dl>",
    "<table>" + "".join(f"<tr><td>{i}<td>x" for i in range(150)) + "</table>",
    "<div><blockquote>Antwort " * 60 + "</blockquote></div>" * 60,
])
def test_r9_2_implied_end_tags_are_not_nesting(html):
    t = time.time()
    converters._check_html_complexity(html)
    assert time.time() - t < 5


def test_r9_2_real_deep_nesting_still_refused_fast():
    for html in ("<div>" * 5000 + "x" + "</div>" * 5000, "<div>" * 50_000):
        t = time.time()
        with pytest.raises(ValueError, match="tief verschachtelt"):
            converters.html_to_pdf(html)
        assert time.time() - t < 3


def test_r9_2_accepted_worst_case_nesting_converts_in_bounded_time():
    t = time.time()
    _ok("<div><blockquote>Antwort " * 60 + "x" + "</blockquote></div>" * 60)
    assert time.time() - t < 30


# --- R9-3 ---------------------------------------------------------------
def test_r9_3_big_ordinary_table_passes_tag_cap():
    html = "<table>" + "".join(
        f"<tr><td>a{i}</td><td>b</td><td>c</td><td>d</td></tr>" for i in range(1200)) + "</table>"
    converters._check_html_complexity(html)
    t = time.time()
    _ok(html)
    assert time.time() - t < 30


def test_r9_3_tag_flood_still_refused():
    with pytest.raises(ValueError, match="zu komplex"):
        converters.html_to_pdf("<p>" + "<b>x</b>" * 60_000)


# --- R9-4 ---------------------------------------------------------------
def _leaf(name="a", n=1):
    return dict(uid=uuid.uuid4().hex, name=name, is_folder=False, status="", position=0,
                vz_start=None, vz_end=None, pdf_length=n, is_compressed=False, dpi_original=None,
                dpi_current=None, no_compression=False, compression_no_gain=False,
                collapsed=False, compression_method=None, tags=[], datev=None, children=[])


def _make(path, name="a"):
    root = dict(_leaf("root", 0), is_folder=True, children=[_leaf(name)])
    w = PdfWriter()
    w.add_blank_page(200, 300)
    w.add_metadata({"/JSONStructure": json.dumps(root)})
    with open(path, "wb") as f:
        w.write(f)


def test_r9_4_failed_replacing_open_keeps_cancel_tokens_of_surviving_doc(tmp_path):
    import threading
    api = CoreApi()
    a, b = tmp_path / "a.belegtool", tmp_path / "b.belegtool"
    _make(a, "a")
    _make(b, "b")
    sid = api.open(None, str(a))["session"]
    leaf = [n for n in api._sessions[sid].document.root.iter() if not n.is_folder][0]
    tok = api._cancel_tokens.setdefault(leaf.id, threading.Event())
    with mock.patch.object(CoreApi, "_doc_response_locked", side_effect=[RuntimeError("boom")]):
        r = api.open(sid, str(b))
    assert r["ok"] is False
    assert not tok.is_set()
    assert api._cancel_tokens.get(leaf.id) is tok


def test_r9_4_failed_open_of_view_session_cleans_view_dir(tmp_path):
    api = CoreApi()
    d = tempfile.mkdtemp(prefix="beleg_view_")
    try:
        vf = os.path.join(d, "v.belegtool")
        _make(vf)
        api._pending_view_dirs.add(d)
        with mock.patch.object(CoreApi, "_doc_response_locked", side_effect=[RuntimeError("boom")]):
            r = api.open(None, vf)
        assert r["ok"] is False
        assert api._view_dirs == {}
        assert d not in api._pending_view_dirs
        assert not os.path.isdir(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --- R9-5 ---------------------------------------------------------------
def _pages_is_page_pdf():
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Page /MediaBox [0 0 200 200] >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xo = len(out)
    out += b"xref\n0 3\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % xo


def test_r9_5_pdfium_readable_file_is_accepted_when_pikepdf_reads_zero():
    from formats.pdf_storage import PDFStorage
    st = PDFStorage(_pages_is_page_pdf())
    assert len(st.root.children) == 1


def test_r9_5_unreadable_file_still_refused():
    from formats.pdf_storage import PDFStorage
    with pytest.raises(ValueError, match="keine lesbaren Seiten"):
        PDFStorage(b"%PDF-1.4\n<< /Type /Catalog >>\n%%EOF")
