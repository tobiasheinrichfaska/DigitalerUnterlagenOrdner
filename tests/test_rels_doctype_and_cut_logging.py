# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""ST-1: .rels with DOCTYPE/ENTITY fail closed; ST-2: _cut_page_cross_references logs."""
import io
import logging
import sys
import types
import zipfile

import pytest

for _m in ("pythoncom", "win32com", "win32com.client"):
    if _m not in sys.modules:
        try:
            __import__(_m)
        except ImportError:
            sys.modules[_m] = types.ModuleType(_m)
if not hasattr(sys.modules["win32com"], "client"):
    sys.modules["win32com"].client = sys.modules["win32com.client"]

import pikepdf  # noqa: E402

from core import engine  # noqa: E402
from universal_importer import converters  # noqa: E402

_BODY = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="r1" Type="x/styles" Target="styles.xml"/></Relationships>')
_BOMB = ('<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
         + _BODY)


def _docx(tmp_path, rels: bytes):
    p = tmp_path / "t.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("word/_rels/document.xml.rels", rels)
    return str(p)


@pytest.mark.parametrize("raw", [
    _BOMB.encode("utf-8"),
    _BOMB.replace("DOCTYPE", "doctype").replace("ENTITY", "entity").encode("utf-8"),
    b"\xff\xfe" + _BOMB.encode("utf-16-le"),
    b"\xfe\xff" + _BOMB.encode("utf-16-be"),
    _BOMB.encode("utf-16-le"),
    _BOMB.encode("utf-16-be"),
])
def test_rels_with_doctype_is_refused(tmp_path, raw):
    assert converters.scan_ooxml_external_targets(_docx(tmp_path, raw)) == converters.SCAN_UNREADABLE


def test_plain_rels_still_ok(tmp_path):
    assert converters.scan_ooxml_external_targets(_docx(tmp_path, _BODY.encode())) is None


class _Boom:
    def __contains__(self, k):
        raise RuntimeError("inner-boom")


class _Page:
    def __init__(self, obj):
        self.obj = obj


class _BadObj(dict):
    def get(self, k, d=None):
        raise RuntimeError("outer-boom")


def test_cut_cross_refs_logs_inner_and_outer_failures(caplog):
    class Pdf:
        pages = [_Page({"/Annots": [_Boom()]}), _Page(_BadObj())]
    with caplog.at_level(logging.DEBUG, logger="core.engine"):
        engine._cut_page_cross_references(Pdf())
    text = " ".join(r.getMessage() + (r.exc_text or "") + repr(r.exc_info) for r in caplog.records)
    assert "inner-boom" in text and "outer-boom" in text
