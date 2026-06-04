"""Stateless per-format converters: each turns one file (path or text/bytes)
into a single PDF (`ConvertedPDF`). No detection/dispatch logic lives here — the
`UniversalImporter` class decides *which* converter to call.
"""

import io
import os
import tempfile
from dataclasses import dataclass
from typing import Union

import pikepdf
import pythoncom
import win32com.client
from PIL import Image
from pillow_heif import register_heif_opener
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from xhtml2pdf import pisa

from log_config import logger


@dataclass
class ConvertedPDF:
    name: str
    data: io.BytesIO


def passthrough(path: str) -> ConvertedPDF:
    with open(path, "rb") as f:
        return ConvertedPDF(name=os.path.basename(path), data=io.BytesIO(f.read()))


def standard_image(path: str) -> ConvertedPDF:
    img = Image.open(path).convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="PDF")
    buffer.seek(0)
    return ConvertedPDF(name=os.path.basename(path) + ".pdf", data=buffer)


def modern_image(path: str) -> ConvertedPDF:
    register_heif_opener()
    img = Image.open(path).convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="PDF")
    buffer.seek(0)
    return ConvertedPDF(name=os.path.basename(path) + ".pdf", data=buffer)


def txt_to_pdf(text: Union[str, bytes], name: str = "text.pdf") -> ConvertedPDF:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 50
    y = height - margin

    for line in text.splitlines():
        c.drawString(margin, y, line[:120])  # Zeilenlänge begrenzt
        y -= 14
        if y < margin:
            c.showPage()
            y = height - margin

    c.save()
    buffer.seek(0)
    return ConvertedPDF(name=name, data=buffer)


def block_remote_link(uri: str, rel: str):
    """link_callback für xhtml2pdf: erlaubt NUR selbst-enthaltene Inline-
    Ressourcen (``data:`` / ``cid:``) und blockiert alles andere.

    Blockiert damit zwei Klassen von Angriffen aus einer importierten
    HTML-/E-Mail-Datei:
      1. Remote-URLs (``http(s)://``, ``//``) → kein Netzwerkaufruf, keine
         Tracking-Pixel / SSRF.
      2. **Lokale Pfade** (``file://``, absolute/relative Pfade) → eine
         bösartige Mail mit ``<img src="file:///C:/.../geheim.pdf">`` kann
         keine lokale Datei laden und in das erzeugte PDF einbetten
         (Local File Inclusion / Datenabfluss beim Teilen des Exports).
    """
    u = (uri or "").strip().lower()
    if u.startswith(("data:", "cid:")):
        return uri  # self-contained inline content only
    return None  # block remote + local/file/relative


def html_to_pdf(html: Union[str, bytes], name: str = "html.pdf") -> ConvertedPDF:
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=buffer, link_callback=block_remote_link)

    if pisa_status.err:
        # Fallback als leeres Dummy-PDF mit Hinweis
        fallback = io.BytesIO()
        c = canvas.Canvas(fallback, pagesize=A4)
        c.drawString(50, A4[1] - 100, "HTML konnte nicht konvertiert werden.")
        c.drawString(50, A4[1] - 120, f"Dateiname: {name}")
        c.save()
        fallback.seek(0)
        return ConvertedPDF(name=f"{name} – nicht konvertierbar", data=fallback)

    buffer.seek(0)
    raw = buffer.read()
    try:
        with pikepdf.open(io.BytesIO(raw)) as pdf:
            normalized = io.BytesIO()
            pdf.save(normalized, compress_streams=True)
        normalized.seek(0)
        return ConvertedPDF(name=name, data=normalized)
    except Exception:
        return ConvertedPDF(name=name, data=io.BytesIO(raw))


def office_via_com(path: str, ext: str) -> ConvertedPDF:
    # COM nur pro Thread (STA) initialisieren — das genügt. Im headless Core /
    # pywebview läuft die Konvertierung auf einem Worker-Thread (die js_api-Aufrufe
    # sind nicht im Hauptthread); mit CoInitialize ist das zulässig, daher keine
    # harte Hauptthread-Beschränkung mehr.
    try:
        pythoncom.CoInitialize()
    except pythoncom.com_error:
        pass  # COM war bereits initialisiert – kein Problem

    ext = ext.lower()
    path = os.path.normpath(os.path.abspath(path))
    base_name = os.path.splitext(os.path.basename(path))[0]

    # Sicheres temporäres Verzeichnis mit garantiertem Cleanup verwenden,
    # statt eines vorhersagbaren Pfads in %TEMP%.
    tmp_dir = tempfile.mkdtemp(prefix="belegtool_office_")
    out_path = os.path.join(tmp_dir, base_name + ".pdf")

    try:
        if ext in [".doc", ".docx"]:
            word = win32com.client.Dispatch("Word.Application")
            # Makros/DDE-Ausführung deaktivieren (msoAutomationSecurityForceDisable = 3)
            word.AutomationSecurity = 3
            doc = word.Documents.Open(path)
            doc.SaveAs(out_path, FileFormat=17)  # 17 = PDF
            doc.Close()
            word.Quit()

        elif ext in [".xls", ".xlsx"]:
            excel = win32com.client.Dispatch("Excel.Application")
            excel.AutomationSecurity = 3
            wb = excel.Workbooks.Open(path)
            wb.ExportAsFixedFormat(0, out_path)  # 0 = PDF
            wb.Close(False)
            excel.Quit()

        elif ext in [".ppt", ".pptx"]:
            powerpoint = win32com.client.Dispatch("PowerPoint.Application")
            powerpoint.AutomationSecurity = 3
            ppt = powerpoint.Presentations.Open(path, WithWindow=False)
            ppt.SaveAs(out_path, 32)  # 32 = PDF
            ppt.Close()
            powerpoint.Quit()

        else:
            raise ValueError(f"Nicht unterstützter Office-Typ: {ext}")

        with open(out_path, "rb") as f:
            buffer = io.BytesIO(f.read())

    finally:
        # Temp-Datei und Verzeichnis immer bereinigen
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
            os.rmdir(tmp_dir)
        except Exception as cleanup_err:
            logger.warning("Office-Temp-Datei konnte nicht gelöscht werden: %s", cleanup_err)
        # COM auf diesem (Worker-)Thread wieder freigeben, um die CoInitialize
        # oben auszugleichen.
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    if not buffer.getvalue().startswith(b"%PDF"):
        raise ValueError(f"Konvertiertes Dokument scheint kein gültiges PDF zu sein: {path}")

    return ConvertedPDF(name=base_name + ".pdf", data=buffer)
