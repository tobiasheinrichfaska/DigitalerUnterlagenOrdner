# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""IM-1: a plain PDF that yields no readable page is refused per file, never a 0-page ghost leaf."""
import io

import pikepdf
import pytest

from core.api import CoreApi
from formats.pdf_storage import PDFStorage
from helpers import create_valid_pdf

P2 = create_valid_pdf(pages=2)


def _cyclic():
    d = pikepdf.new()
    d.add_blank_page()
    r = d.Root.Pages
    r.Kids = pikepdf.Array([r])
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def _zero_pages():
    d = pikepdf.open(io.BytesIO(P2))
    del d.pages[1]
    del d.pages[0]
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def _encrypted():
    d = pikepdf.open(io.BytesIO(P2))
    b = io.BytesIO()
    d.save(b, encryption=pikepdf.Encryption(user="x", owner="o"))
    return b.getvalue()


BAD = {
    "trunc": (P2[:100], "keine lesbaren Seiten"),
    "cyclic": (_cyclic(), "keine lesbaren Seiten"),
    "zero": (_zero_pages(), "keine lesbaren Seiten"),
    "encrypted": (_encrypted(), "passwortgeschützt"),
}


@pytest.mark.parametrize("key", list(BAD))
def test_storage_refuses_unreadable_plain_pdf(key):
    with pytest.raises(ValueError):
        PDFStorage()._load_pdf(BAD[key][0])


@pytest.mark.parametrize("key", list(BAD))
def test_import_paths_reports_per_file_error(tmp_path, key):
    f = tmp_path / "bad.pdf"
    f.write_bytes(BAD[key][0])
    api = CoreApi()
    sid = api.open()["session"]
    resp = api.import_paths(sid, [str(f)])
    assert resp["ok"] is False
    assert BAD[key][1] in resp["error"]


def test_mixed_batch_imports_good_and_warns_bad(tmp_path):
    good = tmp_path / "good.pdf"
    good.write_bytes(P2)
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(BAD["trunc"][0])
    api = CoreApi()
    sid = api.open()["session"]
    resp = api.import_paths(sid, [str(good), str(bad)])
    assert resp["ok"] is True
    assert "keine lesbaren Seiten" in resp.get("warning", "")


def test_valid_pdf_still_loads():
    s = PDFStorage()
    s._load_pdf(P2)
    assert len(s.root.children) == 1
