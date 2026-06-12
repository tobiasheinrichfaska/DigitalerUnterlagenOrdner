"""Stateless per-format converters: each turns one file (path or text/bytes)
into a single PDF (`ConvertedPDF`). No detection/dispatch logic lives here — the
`UniversalImporter` class decides *which* converter to call.
"""

import io
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Optional, Union

import pikepdf
import pythoncom
import win32com.client
from PIL import Image
from pillow_heif import register_heif_opener
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from xhtml2pdf import pisa

from infra.log_config import logger


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


# --- OOXML remote-reference pre-scan ---------------------------------------
# COM kann den Abruf einer „angehängten Vorlage" (attachedTemplate) bzw. extern
# verknüpfter Inhalte beim Öffnen nicht vollständig blockieren — Word löst eine
# UNC-/HTTP-Vorlage schon beim Open auf (NTLMv2-Hash-Leak / SSRF-Callback), bevor
# unsere ReadOnly-/UpdateLinks-Guards greifen. Billige Gegenmaßnahme: die *.rels
# der OOXML-Datei VOR dem Öffnen auf externe Ziele prüfen und solche Dateien
# ablehnen. Hyperlinks bleiben erlaubt (werden beim Öffnen nicht abgerufen).
# Restrisiko (dokumentiert): Legacy-OLE-Formate (.doc/.xls/.ppt) sind kein ZIP
# und werden hier nicht erfasst; dort verbleibt der COM-seitige Schutz
# (AutomationSecurity=3, ReadOnly, UpdateLinks aus).
_RELS_EXTERNAL_PREFIXES = (b"http://", b"https://", b"ftp://", b"ftps://",
                           b"file:", b"\\\\", b"//")
_RELS_MAX_BYTES = 4 * 1024 * 1024  # ein .rels ist winzig; Cap gegen Zip-Bomben
_RELS_MAX_ENTRIES = 10_000  # ein .docx hat Dutzende Einträge; Cap gegen Entry-Bomben
_REL_TAG_RE = re.compile(rb"<Relationship\b[^>]*>", re.IGNORECASE)
_REL_ATTR_RE = re.compile(rb'(\w+)\s*=\s*"([^"]*)"')

# Sentinel: die Datei IST ein ZIP, aber der Scan konnte sie nicht prüfen → der
# Aufrufer muss ABLEHNEN (fail closed). Words toleranter OPC-Parser könnte ein
# externes Ziel auflösen, das unser zipfile nicht lesen konnte (Bypass).
SCAN_UNREADABLE = "<.rels nicht prüfbar>"


def scan_ooxml_external_targets(path: str) -> Optional[str]:
    """Erstes verdächtiges externes Ziel in den ``*.rels`` einer OOXML-Datei
    (sonst ``None``). Nur ``TargetMode="External"``-Beziehungen, Hyperlinks
    ausgenommen; geflaggt werden http(s)/ftp(s)-, file:- und UNC-Ziele.

    Fail-closed: Ist die Datei ein ZIP, aber der Scan schlägt fehl (defektes
    Local-Header, exotische Methode, Entry-Bombe), wird ``SCAN_UNREADABLE``
    zurückgegeben und der Aufrufer lehnt ab. Nur echtes Nicht-ZIP (Legacy-OLE
    .doc/.xls/.ppt — dort gibt es kein .rels) bleibt fail-open."""
    try:
        if not zipfile.is_zipfile(path):
            return None  # Legacy-OLE (.doc/.xls/.ppt) — kein .rels vorhanden
    except Exception:
        return None  # nicht mal lesbar → das COM-Open scheitert von selbst
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if len(names) > _RELS_MAX_ENTRIES:
                return SCAN_UNREADABLE  # kein plausibles Office-Dokument
            for name in names:
                if not name.lower().endswith(".rels"):
                    continue
                with z.open(name) as f:
                    xml = f.read(_RELS_MAX_BYTES)
                for tag in _REL_TAG_RE.findall(xml):
                    attrs = {k.lower(): v for k, v in _REL_ATTR_RE.findall(tag)}
                    if attrs.get(b"targetmode", b"").lower() != b"external":
                        continue
                    if attrs.get(b"type", b"").lower().endswith(b"/hyperlink"):
                        continue  # nicht beim Öffnen aufgelöst → erlaubt
                    target = attrs.get(b"target", b"").strip()
                    if target.lower().startswith(_RELS_EXTERNAL_PREFIXES):
                        return target.decode("utf-8", errors="replace")
    except Exception:
        # ZIP, aber nicht prüfbar → fail CLOSED (sonst öffnet Word ungeprüft,
        # und sein toleranter Parser könnte die externe Vorlage doch auflösen).
        logger.warning("OOXML-.rels-Scan fehlgeschlagen für %s", path, exc_info=True)
        return SCAN_UNREADABLE
    return None


def office_via_com(path: str, ext: str) -> ConvertedPDF:
    ext = ext.lower()
    path = os.path.normpath(os.path.abspath(path))
    base_name = os.path.splitext(os.path.basename(path))[0]

    if ext not in [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]:
        raise ValueError(f"Nicht unterstützter Office-Typ: {ext}")

    # VOR dem Öffnen: OOXML mit externer Vorlage/Verknüpfung ablehnen (Office würde
    # das Ziel beim Open auflösen — Hash-Leak/SSRF; siehe scan_ooxml_external_targets).
    target = scan_ooxml_external_targets(path)
    if target:
        logger.warning("Office-Import abgelehnt, externes Ziel in .rels: %s", target)
        raise ValueError("verweist auf eine externe Vorlage/Quelle"
                         " – aus Sicherheitsgründen abgelehnt")

    # COM nur pro Thread (STA) initialisieren — das genügt. Im headless Core /
    # pywebview läuft die Konvertierung auf einem Worker-Thread (die js_api-Aufrufe
    # sind nicht im Hauptthread); mit CoInitialize ist das zulässig, daher keine
    # harte Hauptthread-Beschränkung mehr.
    try:
        pythoncom.CoInitialize()
    except pythoncom.com_error:
        pass  # COM war bereits initialisiert – kein Problem

    # Sicheres temporäres Verzeichnis mit garantiertem Cleanup verwenden,
    # statt eines vorhersagbaren Pfads in %TEMP%.
    tmp_dir = tempfile.mkdtemp(prefix="belegtool_office_")
    out_path = os.path.join(tmp_dir, base_name + ".pdf")

    try:
        if ext in [".doc", ".docx"]:
            word = win32com.client.Dispatch("Word.Application")
            try:
                # Makros/DDE-Ausführung deaktivieren (msoAutomationSecurityForceDisable = 3)
                word.AutomationSecurity = 3
                # Externe Verknüpfungen beim Öffnen NICHT automatisch aktualisieren
                try:
                    word.Options.UpdateLinksAtOpen = False
                except Exception:
                    pass
                # Schreibgeschützt öffnen, nicht in „zuletzt verwendet" aufnehmen
                doc = word.Documents.Open(path, ReadOnly=True, AddToRecentFiles=False)
                try:
                    doc.SaveAs(out_path, FileFormat=17)  # 17 = PDF
                finally:
                    doc.Close()
            finally:
                word.Quit()  # immer — sonst leakt ein fehlgeschlagener Import WINWORD

        elif ext in [".xls", ".xlsx"]:
            excel = win32com.client.Dispatch("Excel.Application")
            try:
                excel.AutomationSecurity = 3
                try:
                    excel.AskToUpdateLinks = False
                except Exception:
                    pass
                # UpdateLinks=0 → externe Verknüpfungen nicht aktualisieren; schreibgeschützt
                wb = excel.Workbooks.Open(path, UpdateLinks=0, ReadOnly=True)
                try:
                    wb.ExportAsFixedFormat(0, out_path)  # 0 = PDF
                finally:
                    wb.Close(False)
            finally:
                excel.Quit()

        elif ext in [".ppt", ".pptx"]:
            powerpoint = win32com.client.Dispatch("PowerPoint.Application")
            try:
                powerpoint.AutomationSecurity = 3
                # PowerPoint kennt kein UpdateLinks-Argument beim Open; verknüpfte
                # Inhalte deckt der .rels-Pre-Scan oben ab (Restrisiko: Legacy .ppt).
                ppt = powerpoint.Presentations.Open(path, ReadOnly=True, WithWindow=False)
                try:
                    ppt.SaveAs(out_path, 32)  # 32 = PDF
                finally:
                    ppt.Close()
            finally:
                powerpoint.Quit()

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
