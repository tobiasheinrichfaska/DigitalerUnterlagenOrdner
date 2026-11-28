# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
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
from PIL import Image, ImageOps
from pi_heif import register_heif_opener
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from xhtml2pdf import pisa

from infra.limits import BOMB_CAP_BYTES, unsupported_zip_member
from infra.log_config import logger


@dataclass
class ConvertedPDF:
    name: str
    data: io.BytesIO


def passthrough(path: str) -> ConvertedPDF:
    with open(path, "rb") as f:
        return ConvertedPDF(name=os.path.basename(path), data=io.BytesIO(f.read()))


def _to_rgb(img: Image.Image) -> Image.Image:
    """Apply EXIF orientation and flatten transparency onto WHITE (a plain
    convert("RGB") shows the colour stored under alpha=0, often black)."""
    img = ImageOps.exif_transpose(img)
    if img.mode.startswith("I"):
        # 16/32-bit grey (scanner PNG/TIFF): a plain convert("RGB") clips every
        # value > 255 to white -> scale the 16-bit range down to 8 bit first.
        img = img.point(lambda v: v * (1 / 256)).convert("L")
    if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return img.convert("RGB")


_A4_W, _A4_H = 595.28, 841.89


def _image_to_a4_pdf(path: str) -> io.BytesIO:
    """One A4 page (portrait/landscape by image shape) with the image fitted
    and centred, never distorted/cropped. Lossless sources stay Flate;
    an un-rotated JPEG keeps its original DCT bytes (no re-encode)."""
    import zlib

    src = Image.open(path)  # Pillow's decompression-bomb guard applies here
    orientation = src.getexif().get(0x0112, 1)
    raw_jpeg = None
    if src.format == "JPEG" and src.mode in ("RGB", "L") and orientation in (0, 1, None):
        with open(path, "rb") as f:
            raw_jpeg = f.read()
    grey = src.mode in ("L", "1", "I;16", "I", "LA")
    img = _to_rgb(src)
    if grey:
        img = img.convert("L")
    w, h = img.size
    pw, ph = (_A4_W, _A4_H) if h >= w else (_A4_H, _A4_W)
    scale = min(pw / w, ph / h)
    dw, dh = w * scale, h * scale
    x, y = (pw - dw) / 2, (ph - dh) / 2

    pdf = pikepdf.new()
    if raw_jpeg is not None:
        stream = pikepdf.Stream(pdf, raw_jpeg)
        stream.Filter = pikepdf.Name.DCTDecode
    else:
        stream = pikepdf.Stream(pdf, zlib.compress(img.tobytes(), 6))
        stream.Filter = pikepdf.Name.FlateDecode
    stream.Type = pikepdf.Name.XObject
    stream.Subtype = pikepdf.Name.Image
    stream.Width, stream.Height = w, h
    stream.ColorSpace = pikepdf.Name.DeviceGray if img.mode == "L" else pikepdf.Name.DeviceRGB
    stream.BitsPerComponent = 8
    page = pdf.add_blank_page(page_size=(pw, ph))
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=stream))
    page.Contents = pikepdf.Stream(pdf, f"q {dw:.4f} 0 0 {dh:.4f} {x:.4f} {y:.4f} cm /Im0 Do Q".encode())
    buffer = io.BytesIO()
    pdf.save(buffer)
    buffer.seek(0)
    return buffer


def standard_image(path: str) -> ConvertedPDF:
    return ConvertedPDF(name=os.path.basename(path) + ".pdf", data=_image_to_a4_pdf(path))


def modern_image(path: str) -> ConvertedPDF:
    register_heif_opener()
    return ConvertedPDF(name=os.path.basename(path) + ".pdf", data=_image_to_a4_pdf(path))


def _exceeds_byte_cap(data: Union[str, bytes]) -> bool:
    """True if a text/HTML payload is over the decoded BYTE budget. Bytes are
    measured directly; a str is measured by its UTF-8 byte length — a str's char
    count is a unit mismatch against a byte cap (a multibyte str of N chars can be
    several N bytes). The char count short-circuits the encode: chars > cap already
    implies bytes > cap (UTF-8 is ≥ 1 byte/char), so the encode only runs when the
    string is already within the cap by characters (bounded work)."""
    if isinstance(data, (bytes, bytearray)):
        return len(data) > BOMB_CAP_BYTES
    return len(data) > BOMB_CAP_BYTES or len(data.encode("utf-8")) > BOMB_CAP_BYTES


def _decode_text(data: bytes, html: bool = False) -> str:
    """BOM sniff, strict UTF-8, then (HTML: declared charset, then) cp1252."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if html:
        m = re.search(rb"charset\s*=\s*[\"']?\s*([A-Za-z0-9_\-]+)", data[:4096], re.I)
        if m:
            try:
                return data.decode(m.group(1).decode("ascii"))
            except (LookupError, UnicodeDecodeError):
                pass
    return data.decode("cp1252", errors="replace")


# Control / bidi-override / zero-width characters removed from imported text and names.
# A translate table (not a regex range) keeps the intent explicit and is faster.
_BIDI_AND_ZW = list(range(0x200B, 0x2010)) + list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A)) + [0xFEFF]
_CTRL_DELETE = dict.fromkeys(
    [c for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)] + [0x7F] + _BIDI_AND_ZW)
_NAME_CTRL_DELETE = dict.fromkeys(list(range(0x20)) + [0x7F] + _BIDI_AND_ZW)
_TXT_MAX_CHARS = 1_000_000   # layout is O(n) per char in Python: ~3 s per MB
_HTML_MAX_BYTES = 2 * 1024 * 1024
_HTML_MAX_DEPTH = 100        # xhtml2pdf is quadratic in nesting depth / element count
_HTML_MAX_TAGS = 10_000
_HTML_VOID = frozenset("br hr img input meta link area base col embed param source track wbr".split())
_TAG_RE = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9]*)[^>]*?(/?)>")


def sanitize_node_name(name, strip_path: bool = True, max_len: int = 200) -> str:
    """A safe display name: basename (both separators), no control/bidi chars, <=200 chars."""
    n = str(name or "")
    if strip_path:
        n = n.replace("\\", "/").rsplit("/", 1)[-1]
    n = n.translate(_NAME_CTRL_DELETE).strip()
    if n in ("", ".", ".."):
        return "Datei"
    return n[:max_len]


def _check_html_complexity(html: str) -> None:
    depth = maxd = tags = 0
    for m in _TAG_RE.finditer(html):
        tags += 1
        if tags > _HTML_MAX_TAGS:
            raise ValueError("HTML-Datei zu komplex (zu groß)")
        tag = m.group(2).lower()
        if m.group(1):
            depth = max(0, depth - 1)
        elif not m.group(3) and tag not in _HTML_VOID:
            depth += 1
            maxd = max(maxd, depth)
            if maxd > _HTML_MAX_DEPTH:
                raise ValueError("HTML-Datei zu tief verschachtelt (zu groß)")


def _printable(text: str) -> str:
    """Expand tabs and replace characters the built-in Helvetica (cp1252) cannot
    draw with '?' (they would render as black boxes)."""
    return text.expandtabs(4).encode("cp1252", errors="replace").decode("cp1252")


def txt_to_pdf(text: Union[str, bytes], name: str = "text.pdf") -> ConvertedPDF:
    # Cap before decode/render: an oversized text file would otherwise pin the
    # worker (the wrap + per-page canvas work is linear but unbounded). Mirrors
    # the archive/email bomb cap so a single huge .txt can't DoS the import.
    if _exceeds_byte_cap(text):
        raise ValueError("Textdatei zu groß")
    if isinstance(text, bytes):
        text = _decode_text(bytes(text))
    text = text.translate(_CTRL_DELETE)
    truncated = len(text) > _TXT_MAX_CHARS
    if truncated:
        text = text[:_TXT_MAX_CHARS] + "\n\n[Text gekürzt: Datei zu groß für den Import]"
    text = _printable(text)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 50
    font_name, font_size = "Helvetica", 10
    max_width = width - 2 * margin
    c.setFont(font_name, font_size)
    y = height - margin

    def _wrap(line: str) -> list:
        # Wrap by MEASURED width, not a fixed character count — a long line (e.g. a
        # plain-text e-mail body) must neither be truncated nor run off the page edge
        # (off-page glyphs are clipped → effectively lost). An empty line stays one
        # blank row. Width is accumulated PER CHARACTER (Helvetica has no kerning in
        # reportlab's canvas, so stringWidth is additive) — O(n), not the O(n²) of
        # re-measuring the whole prefix each step.
        if not line:
            return [""]
        out, cur, cur_w = [], "", 0.0
        for ch in line:
            ch_w = c.stringWidth(ch, font_name, font_size)
            if cur and cur_w + ch_w > max_width:
                out.append(cur)
                cur, cur_w = "", 0.0
            cur += ch
            cur_w += ch_w
        out.append(cur)
        return out

    for line in text.splitlines():
        for chunk in _wrap(line):
            c.drawString(margin, y, chunk)
            y -= 14
            if y < margin:
                c.showPage()
                c.setFont(font_name, font_size)  # font resets on a new page
                y = height - margin

    c.save()
    buffer.seek(0)
    return ConvertedPDF(name=name, data=buffer)


# Harmloser Ersatz für jede blockierte Ressource: ein 1×1-transparentes PNG als data:-URI.
# WICHTIG: ``None`` zurückzugeben blockiert in xhtml2pdf NICHTS — ``pisaFileObject`` fällt bei
# falsy Callback-Ergebnis auf die ORIGINAL-URI zurück (Sicherheitsreview 2026-11-25, H-1:
# Remote-Abruf + Einbetten lokaler Dateien trotz „Blockade"). Darum liefern wir einen
# self-contained Platzhalter, der nie ein Netzwerk-/Dateisystemziel hat.
_BLOCKED_PLACEHOLDER = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="
)


def block_remote_link(uri: str, rel: str):
    """link_callback für xhtml2pdf: erlaubt NUR selbst-enthaltene Inline-
    Ressourcen (``data:`` / ``cid:``); alles andere wird durch einen inerten
    ``data:``-Platzhalter ersetzt (nie ``None`` — siehe ``_BLOCKED_PLACEHOLDER``).

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
    return _BLOCKED_PLACEHOLDER  # block remote + local/file/relative


def html_to_pdf(html: Union[str, bytes], name: str = "html.pdf") -> ConvertedPDF:
    if _exceeds_byte_cap(html):  # bound the parse/render like txt_to_pdf (byte-accurate)
        raise ValueError("HTML-Datei zu groß")
    if (len(html) if isinstance(html, bytes) else len(html.encode("utf-8", "replace"))) > _HTML_MAX_BYTES:
        raise ValueError("HTML-Datei zu groß")
    if isinstance(html, bytes):
        html = _decode_text(bytes(html), html=True)

    html = html.translate(_CTRL_DELETE)
    _check_html_complexity(html)
    html = _printable(html)

    def _render(src: str):
        out = io.BytesIO()
        try:
            return pisa.CreatePDF(src=src, dest=out, link_callback=block_remote_link), out
        except Exception:  # e.g. ZeroDivisionError on an empty SVG data-URI
            return None, out

    pisa_status, buffer = _render(html)
    if pisa_status is None:  # retry once without the (SVG) data-URI images
        stripped = re.sub(r"<img\b[^>]*data:image/svg[^>]*>", "", html, flags=re.I)
        pisa_status, buffer = _render(stripped)

    if pisa_status is None or pisa_status.err:
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
_RELS_EXTERNAL_PREFIXES = ("http://", "https://", "ftp://", "ftps://",
                           "file:", "\\\\", "//")
_RELS_EXTERNAL_NORM_PREFIXES = ("\\\\", "http:\\", "https:\\", "ftp:\\", "ftps:\\", "file:")
_RELS_MAX_BYTES = 4 * 1024 * 1024  # ein .rels ist winzig; Cap gegen Zip-Bomben
_RELS_MAX_ENTRIES = 10_000  # ein .docx hat Dutzende Einträge; Cap gegen Entry-Bomben

# Sentinel: die Datei IST ein ZIP, aber der Scan konnte sie nicht prüfen → der
# Aufrufer muss ABLEHNEN (fail closed). Words toleranter OPC-Parser könnte ein
# externes Ziel auflösen, das unser zipfile nicht lesen konnte (Bypass).
SCAN_UNREADABLE = "<.rels nicht prüfbar>"


def _has_dtd_declaration(xml: bytes) -> bool:
    """ST-1: DOCTYPE/ENTITY (entity expansion) — also in UTF-16 or other odd encodings."""
    needles = ("<!doctype", "<!entity")
    low = xml.lower()
    for n in needles:
        for enc in ("utf-8", "utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"):
            if n.encode(enc) in low or n.encode(enc) in xml:
                return True
    for enc in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text = xml.decode(enc).lower()
        except Exception:
            continue
        if any(n in text for n in needles):
            return True
    return False


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
            if len(names) != len(set(names)):
                # A-1 (QS-Delta-Review 2026-11-04): bei Duplikatnamen liest CPythons
                # zipfile den LETZTEN Eintrag, Words OPC-Leser womöglich einen anderen —
                # der Scan darf nicht wetten, welchen. Kein legitimes Office-Werkzeug
                # erzeugt Duplikate → fail CLOSED.
                return SCAN_UNREADABLE
            for name in names:
                if not name.lower().endswith(".rels"):
                    continue
                # bzip2/LZMA inflate unbounded before the read cap (CPython zipfile);
                # no legitimate OOXML uses them → fail CLOSED like the other caps.
                if unsupported_zip_member(z.getinfo(name)):
                    return SCAN_UNREADABLE
                with z.open(name) as f:
                    xml = f.read(_RELS_MAX_BYTES)
                if len(xml) >= _RELS_MAX_BYTES:
                    # truncated read → ein externes Ziel könnte JENSEITS des Caps liegen
                    # und der Parser sähe es nie. Ein legitimes .rels ist winzig, also ist
                    # ein übergroßes selbst verdächtig → fail CLOSED (wie der Entry-Cap).
                    return SCAN_UNREADABLE
                # Echter XML-Parser statt Regex (Audit 2026-11-03, M5): der Regex ließ
                # sich mit einfachen Anführungszeichen, Zeichenreferenzen (&#92;) und
                # Präfix-Elementen (<r:Relationship>) umgehen — Word parst all das.
                # Elemente namensraum-unabhängig über den LOKALEN Namen; nicht parsebares
                # XML → fail CLOSED (Words toleranter Parser könnte es trotzdem auflösen).
                if _has_dtd_declaration(xml):
                    return SCAN_UNREADABLE  # ST-1: kein legitimes .rels hat eine DTD
                try:
                    from xml.etree import ElementTree as ET
                    root_el = ET.fromstring(xml)
                except Exception:
                    return SCAN_UNREADABLE
                for el in root_el.iter():
                    local = el.tag.rsplit("}", 1)[-1]
                    if local != "Relationship":
                        if local.lower() == "relationship":
                            # A-3: ein case-variantes <relationship> — nicht raten, ob
                            # Words Parser es auswertet → fail CLOSED (wie bei Attributen)
                            return SCAN_UNREADABLE
                        continue
                    # OPC-Attributnamen sind unqualifiziert und case-sensitiv — EXAKT so
                    # lesen wie Word. Ein qualifiziertes/case-variantes Duplikat
                    # (x:TargetMode, targetMode) ließe Scan und Word unterschiedliche
                    # Werte sehen (QS-Gegenprüfung 2026-11-04, M-1) → fail CLOSED.
                    for k in el.attrib:
                        if (k.rsplit("}", 1)[-1].lower() in ("targetmode", "type", "target")
                                and k not in ("TargetMode", "Type", "Target")):
                            return SCAN_UNREADABLE
                    # A-2: der WERT ist ein OPC-Enum (Internal/External, Default Internal).
                    # " External"/"External\t" usw. als „intern" zu werten wäre fail-OPEN,
                    # falls Words Parser trimmt — jeder nicht-exakte Wert → fail CLOSED.
                    mode = el.attrib.get("TargetMode", "Internal")
                    if mode not in ("Internal", "External"):
                        return SCAN_UNREADABLE
                    if mode != "External":
                        continue
                    if el.attrib.get("Type", "").lower().endswith("/hyperlink"):
                        continue  # nicht beim Öffnen aufgelöst → erlaubt
                    target = el.attrib.get("Target", "").strip()
                    # F-5: Windows treats "/" like "\\" — normalise before the prefix test
                    # so "/\\h\\s", "http:\\\\h" etc. are caught too.
                    norm = target.lower().replace("/", "\\")
                    if (target.lower().startswith(_RELS_EXTERNAL_PREFIXES)
                            or norm.startswith(_RELS_EXTERNAL_NORM_PREFIXES)):
                        return target
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

    # ODF (.odt/.ods/.odp) is advertised in get_supported_extensions/the file dialog and
    # opens through the matching Office app (Word/Excel/PowerPoint) — route it like the OOXML
    # twin. The .rels external-target pre-scan below is a no-op for ODF (a ZIP without .rels →
    # scan returns None, fail-open like legacy OLE), so the COM guards (AutomationSecurity=3,
    # ReadOnly, UpdateLinks off) are the active protection for this format.
    if ext not in [".doc", ".docx", ".odt", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp"]:
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
        if ext in [".doc", ".docx", ".odt"]:
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

        elif ext in [".xls", ".xlsx", ".ods"]:
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

        elif ext in [".ppt", ".pptx", ".odp"]:
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
