# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""u3 IM-2/IM-3/IM-5/IM-6: HTML/text DoS caps and sane names (COM modules stubbed)."""
import base64
import sys
import time
import types

import pytest

for _m in ("pythoncom", "win32com", "win32com.client"):
    if _m not in sys.modules:
        try:
            __import__(_m)
        except ImportError:
            sys.modules[_m] = types.ModuleType(_m)
if not hasattr(sys.modules["win32com"], "client"):
    sys.modules["win32com"].client = sys.modules["win32com.client"]

from universal_importer import converters  # noqa: E402


def test_im2_deeply_nested_html_refused_fast():
    t = time.time()
    with pytest.raises(ValueError):
        converters.html_to_pdf(b"<div>" * 3000 + b"x")
    assert time.time() - t < 3


def test_im2_many_table_rows_refused_fast():
    t = time.time()
    with pytest.raises(ValueError):
        converters.html_to_pdf(b"<table>" + b"<tr><td>c</td><td>d</td></tr>" * 30000 + b"</table>")
    assert time.time() - t < 3


def test_im2_html_size_cap():
    with pytest.raises(ValueError):
        converters.html_to_pdf(b"a" * (3 * 1024 * 1024))


def test_im2_normal_html_still_converts():
    assert converters.html_to_pdf(b"<html><body><p>Hallo</p><table><tr><td>a</td></tr></table></body></html>").data.getvalue().startswith(b"%PDF")


def test_im3_nul_text_fast():
    t = time.time()
    conv = converters.txt_to_pdf(b"\0" * 5_000_000)
    assert conv.data.getvalue().startswith(b"%PDF")
    assert time.time() - t < 5


def test_im3_huge_text_truncated_with_note_fast():
    import io
    import pypdf
    t = time.time()
    conv = converters.txt_to_pdf(b"x" * 3_000_000)
    assert time.time() - t < 6
    txt = "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(conv.data.getvalue())).pages[-1:])
    assert "gekürzt" in txt


@pytest.mark.parametrize("name", [".", "..", "a\x00b.txt", "y" * 400 + ".txt", "..\\..\\x.txt", "‮gpj.exe.txt", "a\nb.txt", ""])
def test_im6_import_bytes_odd_names_never_raise(name):
    from core.api import CoreApi
    api = CoreApi()
    sid = api.open()["session"]
    r = api.import_bytes(sid, name, base64.b64encode(b"hello").decode())
    assert isinstance(r, dict) and "ok" in r


def test_im5_sanitize_name():
    from universal_importer.converters import sanitize_node_name as s
    assert s("../../x.pdf") == "x.pdf"
    assert s("..\\..\\x.pdf") == "x.pdf"
    assert s("a\nb\x00c‮d.txt") == "abcd.txt"
    assert len(s("y" * 5000 + ".txt")) <= 200
    assert s("..") == "Datei" and s(".") == "Datei" and s("") == "Datei"


def test_im5_archive_leaf_names_sanitized():
    import zipfile, io
    from universal_importer.archives import extract_email_to_structure, extract_zip_to_structure
    from tests.helpers import create_valid_pdf
    from email.message import EmailMessage
    m = EmailMessage()
    m["Subject"] = "S" * 5000
    m.set_content("hi")
    m.add_attachment(create_valid_pdf(pages=1), maintype="application", subtype="pdf", filename="../../x\u202e.pdf")
    st = extract_email_to_structure(m.as_bytes())
    def names(ns):
        for n in ns:
            yield n["name"]
            yield from names(n.get("children", []))
    for n in names(st):
        assert "/" not in n and "\u202e" not in n and len(n) <= 200
