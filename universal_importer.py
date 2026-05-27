import io
import os
from dataclasses import dataclass
from log_config import logger
from PIL import Image
import zipfile
from typing import List, Optional, Callable, Dict, Any, Union
import extract_msg
from email import policy
from email.parser import BytesParser
import tempfile
import pythoncom
import win32com.client
from pillow_heif import register_heif_opener
import pikepdf
# import cairosvg
import threading
from tkinter import _default_root
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
# Kein weasyprint mehr nötig
from xhtml2pdf import pisa


@dataclass
class ConvertedPDF:
    name: str
    data: io.BytesIO


class UniversalImporter:
    PDF_EXTENSIONS = [".pdf", ".belegtool"]
    IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"]
    CUSTOM_EXTENSIONS = [".dbeleg"]
    MODERN_IMAGE_EXTENSIONS = [".webp", ".heic"]
    # VECTOR_EXTENSIONS = [".svg"] 
    ARCHIVE_AND_EMAIL_EXTENSIONS = [".zip", ".tar", ".tgz", ".eml", ".msg"]
    TEXT_EXTENSIONS = [".txt", ".rtf"]
    HTML_EXTENSIONS = [".html"]
    OFFICE_WORD_EXT = [".doc", ".docx", ".odt"]
    OFFICE_EXCEL_EXT = [".xls", ".xlsx", ".ods"]
    OFFICE_POWERPOINT_EXT = [".ppt", ".pptx", ".odp"]
    OFFICE_EXTENSIONS = OFFICE_WORD_EXT + OFFICE_EXCEL_EXT + OFFICE_POWERPOINT_EXT
    _is_initialized = False  # wird auf True gesetzt, wenn Office-Erkennung abgeschlossen ist
    _has_word = False
    _has_excel = False
    _has_powerpoint = False

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        exts = (
            cls.PDF_EXTENSIONS +
            cls.IMAGE_EXTENSIONS +
            cls.CUSTOM_EXTENSIONS +
            cls.MODERN_IMAGE_EXTENSIONS +
            cls.ARCHIVE_AND_EMAIL_EXTENSIONS +
            cls.TEXT_EXTENSIONS +
            cls.HTML_EXTENSIONS
        )
        if cls._has_word:
            exts += cls.OFFICE_WORD_EXT
        if cls._has_excel:
            exts += cls.OFFICE_EXCEL_EXT
        if cls._has_powerpoint:
            exts += cls.OFFICE_POWERPOINT_EXT
        return exts

    @classmethod
    def get_filetypes_for_dialog(cls) -> List[tuple]:
        def pattern(exts):
            return " ".join(f"*{ext}" for ext in exts)

        filetypes = [
            ("Alle unterstützten Formate", pattern(cls.get_supported_extensions())),
            ("PDF",                        "*.pdf"),
            ("BelegTool-Dateien",          "*.belegtool"),
            ("Archive",                    "*.zip *.tar *.tgz"),
            ("E-Mails",                    "*.eml *.msg"),
            ("Bilder",                     pattern(cls.IMAGE_EXTENSIONS + cls.MODERN_IMAGE_EXTENSIONS)),
        ]

        if cls._has_word:
            filetypes.append(("Word / OpenDocument Text",   pattern(cls.OFFICE_WORD_EXT)))
        if cls._has_excel:
            filetypes.append(("Excel / OpenDocument Tabelle", pattern(cls.OFFICE_EXCEL_EXT)))
        if cls._has_powerpoint:
            filetypes.append(("PowerPoint / OpenDocument Präsentation", pattern(cls.OFFICE_POWERPOINT_EXT)))

        return filetypes

    @classmethod
    def is_supported(cls, path: str) -> bool:
        p = path.lower()
        if p.endswith(".tar.gz") or p.endswith(".tgz"):
            return True
        ext = os.path.splitext(p)[1]
        return ext in cls.get_supported_extensions()

    @classmethod
    def convert(cls, source: Union[str, bytes, io.BytesIO], name: Optional[str] = None) -> ConvertedPDF:
        """
        Konvertiert eine Datei (Pfad oder Bytes) in ein PDF.
        Unterstützt Pfade, Bytes oder BytesIO. Nutzt intern COM oder Bild-Konvertierung.

        Args:
            source: Pfad zur Datei oder Daten im RAM.
            name: Optionaler Dateiname zur Typ-Erkennung (z. B. bei Bytes notwendig).

        Returns:
            ConvertedPDF-Objekt mit PDF-Inhalt.
        """
        if isinstance(source, str):
            path = source
            ext = os.path.splitext(path)[1].lower()
        else:
            # Bytes oder BytesIO: Temporäre Datei erzeugen
            if isinstance(source, io.BytesIO):
                data = source.getvalue()
            elif isinstance(source, bytes):
                data = source
            else:
                raise TypeError("convert() erwartet Pfad, Bytes oder BytesIO")

            if not name:
                raise ValueError("Bei Daten ohne Pfad muss ein Dateiname angegeben werden.")

            ext = os.path.splitext(name)[1].lower()
            if ext not in cls.get_supported_extensions():
                raise ValueError(f"Nicht unterstützter Dateityp: {ext}")

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(data)
                path = tmp.name

            try:
                result = cls.convert(path)
                result.name = name  # Originalname beibehalten

                # Reparatur und Validierung
                pdf_bytes = result.data.getvalue()
                result.data = io.BytesIO(pdf_bytes)

                if not pdf_bytes.strip().startswith(b"%PDF"):
                    raise ValueError(f"Ungültige PDF-Daten erzeugt für: {name}")
                return result
            finally:
                os.unlink(path)

        # Verarbeitung über bekannten Pfad
        if ext in cls.PDF_EXTENSIONS + cls.CUSTOM_EXTENSIONS:
            result = cls._convert_passthrough(path)
        elif ext in cls.IMAGE_EXTENSIONS:
            result = cls._convert_standard_image(path)
        elif ext in cls.MODERN_IMAGE_EXTENSIONS:
            result = cls._convert_modern_image(path)
        # elif ext in getattr(cls, 'VECTOR_EXTENSIONS', []):  # falls SVG deaktiviert
        #     result = cls._convert_svg(path)
        elif ext in cls.TEXT_EXTENSIONS:
            with open(path, "rb") as f:
                content = f.read()
            _n = name or os.path.basename(path)
            result = cls._convert_txt_to_pdf(content, name=os.path.splitext(_n)[0] + ".pdf")
        elif ext in cls.HTML_EXTENSIONS:
            with open(path, "rb") as f:
                content = f.read()
            _n = name or os.path.basename(path)
            result = cls._convert_html_to_pdf(content, name=os.path.splitext(_n)[0] + ".pdf")

        elif ext in cls.OFFICE_EXTENSIONS:
            result = cls._convert_office_via_com(path, ext)
        else:
            raise ValueError(f"Nicht unterstützter Dateityp: {ext}")

        # Reparatur und Validierung (Pfad-Zweig)
        pdf_bytes = result.data.getvalue()
        result.data = io.BytesIO(pdf_bytes)

        if not pdf_bytes.strip().startswith(b"%PDF"):
            raise ValueError(f"Ungültige PDF-Daten erzeugt aus Datei: {path}")

        return result


    @staticmethod
    def _convert_passthrough(path: str) -> ConvertedPDF:
        with open(path, "rb") as f:
            return ConvertedPDF(name=os.path.basename(path), data=io.BytesIO(f.read()))

    @staticmethod
    def _convert_standard_image(path: str) -> ConvertedPDF:
        img = Image.open(path).convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, format="PDF")
        buffer.seek(0)
        return ConvertedPDF(name=os.path.basename(path) + ".pdf", data=buffer)

    @staticmethod
    def _convert_modern_image(path: str) -> ConvertedPDF:
        register_heif_opener()
        img = Image.open(path).convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, format="PDF")
        buffer.seek(0)
        return ConvertedPDF(name=os.path.basename(path) + ".pdf", data=buffer)

    # @staticmethod
    # def _convert_svg(path: str) -> ConvertedPDF:
    #     buffer = io.BytesIO()
    #     cairosvg.svg2pdf(url=path, write_to=buffer)
    #     buffer.seek(0)
    #     return ConvertedPDF(name=os.path.basename(path) + ".pdf", data=buffer)


    @staticmethod
    def _convert_txt_to_pdf(text: Union[str, bytes], name: str = "text.pdf") -> ConvertedPDF:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

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

    @staticmethod
    def _block_remote_link(uri: str, rel: str):
        """link_callback für xhtml2pdf: blockiert alle Remote-URLs.

        Verhindert, dass HTML-Mails mit eingebetteten <img src="http://...">
        beim Import eine Netzwerkverbindung aufbauen und die IP-Adresse des
        Nutzers an den Absender weiterleiten (Tracking-Pixel).
        """
        if uri.startswith(("http://", "https://", "//")):
            return None  # Remote-Ressource verweigern
        return uri

    @staticmethod
    def _convert_html_to_pdf(html: Union[str, bytes], name: str = "html.pdf") -> ConvertedPDF:
        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="replace")

        buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            src=html,
            dest=buffer,
            link_callback=UniversalImporter._block_remote_link,
        )

        if pisa_status.err:
            # Fallback als leeres Dummy-PDF mit Hinweis
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4

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


    @staticmethod
    def _convert_office_via_com(path: str, ext: str) -> ConvertedPDF:
        # Sicherheitsprüfung: Office-Konvertierung nur im Hauptthread
        if threading.current_thread() != threading.main_thread():
            raise RuntimeError("Office-Konvertierung darf nur im Hauptthread erfolgen.")

        # COM initialisieren, wenn nicht bereits erfolgt
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

        if not buffer.getvalue().startswith(b"%PDF"):
            raise ValueError(f"Konvertiertes Dokument scheint kein gültiges PDF zu sein: {path}")

        return ConvertedPDF(name=base_name + ".pdf", data=buffer)

    @classmethod
    def _detect_office_support(cls):
        try:
            cls._has_word = bool(win32com.client.gencache.EnsureDispatch("Word.Application"))
        except Exception:
            cls._has_word = False
        try:
            cls._has_excel = bool(win32com.client.gencache.EnsureDispatch("Excel.Application"))
        except Exception:
            cls._has_excel = False
        try:
            cls._has_powerpoint = bool(win32com.client.gencache.EnsureDispatch("PowerPoint.Application"))
        except Exception:
            cls._has_powerpoint = False

    @classmethod
    def initialize(cls):
        cls._detect_office_support()
        cls._is_initialized = True


    @classmethod
    def initialize_async(cls, on_complete: Optional[Callable[[], None]] = None):

        def task():
            pythoncom.CoInitialize()
            cls._detect_office_support()
            cls._is_initialized = True
            # print("✅ Office-Erkennung abgeschlossen.")

            if on_complete:
                # Aufruf im Hauptthread mit tkinter.after()
                try:
                    if _default_root:
                        _default_root.after(0, on_complete)
                except Exception as e:
                    logger.warning("Callback-Fehler: %s", e)

        thread = threading.Thread(target=task, daemon=True)
        thread.start()


def _not_importable(name: str) -> Dict[str, Any]:
    return {
        "name": f"{name} – nicht importierbar",
        "children": []  # ⬅ macht daraus einen Ordner!
    }

# Schutz vor ZIP-Bomben / riesigen Archiven
_ARCHIVE_MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 MB
_ARCHIVE_MAX_MEMBERS = 500


def extract_zip_to_structure(path_or_bytes: Union[str, bytes, io.BytesIO]) -> List[Dict[str, Any]]:
    result = []

    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, 'rb') as f:
            data = f.read()
    elif isinstance(path_or_bytes, (bytes, io.BytesIO)):
        data = path_or_bytes.read() if isinstance(path_or_bytes, io.BytesIO) else path_or_bytes
    else:
        raise TypeError("Pfad, Bytes oder BytesIO erwartet")

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            members = [info for info in zf.infolist() if not info.filename.endswith("/")]

            # Sicherheits-Checks gegen ZIP-Bomben
            if len(members) > _ARCHIVE_MAX_MEMBERS:
                raise ValueError(
                    f"ZIP-Archiv enthält zu viele Einträge ({len(members)} > {_ARCHIVE_MAX_MEMBERS})."
                )
            total_uncompressed = sum(info.file_size for info in members)
            if total_uncompressed > _ARCHIVE_MAX_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"ZIP-Archiv würde unkomprimiert {total_uncompressed // (1024*1024)} MB belegen "
                    f"(Limit: {_ARCHIVE_MAX_UNCOMPRESSED_BYTES // (1024*1024)} MB)."
                )

            for info in members:
                name = info.filename
                with zf.open(name) as f:
                    content = f.read()
                    try:
                        converted = UniversalImporter.convert(content, name=name)
                        if not converted.data.getvalue().strip().startswith(b"%PDF"):
                            raise ValueError("PDF-Inhalt ungültig")
                        result.append({"name": name, "content": converted.data})
                    except Exception:
                        result.append(_not_importable(name))
    except zipfile.BadZipFile as e:
        raise ValueError("Ungültiges ZIP-Archiv") from e

    return result

def extract_tar_to_structure(path_or_bytes: Union[str, bytes, io.BytesIO]) -> List[Dict[str, Any]]:
    import tarfile
    result = []

    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as f:
            data = f.read()
    elif isinstance(path_or_bytes, io.BytesIO):
        data = path_or_bytes.read()
    else:
        data = path_or_bytes

    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            file_members = [m for m in tf.getmembers() if m.isfile()]

            # Sicherheits-Checks gegen TAR-Bomben
            if len(file_members) > _ARCHIVE_MAX_MEMBERS:
                raise ValueError(
                    f"TAR-Archiv enthält zu viele Einträge ({len(file_members)} > {_ARCHIVE_MAX_MEMBERS})."
                )
            total_uncompressed = sum(m.size for m in file_members)
            if total_uncompressed > _ARCHIVE_MAX_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"TAR-Archiv würde unkomprimiert {total_uncompressed // (1024*1024)} MB belegen "
                    f"(Limit: {_ARCHIVE_MAX_UNCOMPRESSED_BYTES // (1024*1024)} MB)."
                )

            for member in file_members:
                name = os.path.basename(member.name) or member.name
                try:
                    f = tf.extractfile(member)
                    if f is None:
                        result.append(_not_importable(name))
                        continue
                    content = f.read()
                    converted = UniversalImporter.convert(content, name=name)
                    if not converted.data.getvalue().strip().startswith(b"%PDF"):
                        raise ValueError("PDF-Inhalt ungültig")
                    result.append({"name": name, "content": converted.data})
                except Exception:
                    result.append(_not_importable(name))
    except tarfile.TarError as e:
        raise ValueError("Ungültiges TAR-Archiv") from e

    return result


def extract_email_to_structure(path_or_bytes: Union[str, bytes, io.BytesIO]) -> List[Dict[str, Any]]:
    def _build_base_name(subject: Optional[str], date) -> str:
        subject = (subject or "E-Mail").strip()
        if hasattr(date, 'strftime'):
            date = date.strftime("%Y-%m-%d")
        date = str(date or "").strip()
        return f"{subject} {date}".strip().replace(":", "-").replace("/", "-")

    def _convert_mail_body(content: Union[str, bytes], filename: str) -> Dict[str, Any]:
        try:
            if isinstance(content, str):
                content = content.encode("utf-8")
            elif not isinstance(content, bytes):
                content = str(content).encode("utf-8")
            converted = UniversalImporter.convert(content, name=filename)
            return {"name": filename, "content": converted.data}
        except Exception:
            return _not_importable(filename)

    def _convert_attachment(content: bytes, name: str) -> Dict[str, Any]:
        try:
            converted = UniversalImporter.convert(content, name=name)
            return {"name": name, "content": converted.data}
        except Exception:
            return _not_importable(name)

    result = []

    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as f:
            data = f.read()
    elif isinstance(path_or_bytes, (bytes, io.BytesIO)):
        data = path_or_bytes.read() if isinstance(path_or_bytes, io.BytesIO) else path_or_bytes
    else:
        raise TypeError("Pfad, Bytes oder BytesIO erwartet")

    # .eml
    if b"Content-Type:" in data or b"From:" in data:
        try:
            msg = BytesParser(policy=policy.default).parsebytes(data)

            logger.debug("EML-Parsing abgeschlossen")
            logger.debug("From: %s", msg['from'])
            logger.debug("Subject: %s", msg['subject'])

            base_name = _build_base_name(msg["subject"], msg["date"])

            # Body extrahieren
            logger.debug("Suche Mail-Body mit Priorität (html, plain, rtf)")
            body_part = msg.get_body(preferencelist=("html", "plain", "rtf"))
            if body_part:
                logger.debug("Body gefunden: Content-Type = %s", body_part.get_content_type())
            else:
                logger.warning("Kein Body gefunden")

            content_type = body_part.get_content_type() if body_part else "text/plain"
            extension = {
                "text/html": ".html",
                "text/plain": ".txt",
                "text/rtf": ".rtf"
            }.get(content_type, ".txt")
            body_content = body_part.get_content() if body_part else ""

            logger.debug("Inhalt Start (repr): %s", repr(body_content[:200]))

            file_name = f"{base_name}{extension}"

            logger.debug("Aufruf _convert_mail_body mit Datei: %s", file_name)

            result.append(_convert_mail_body(body_content, file_name))

            # Anhänge + eingebettete Bilder — walk() durchläuft auch verschachtelte MIME-Strukturen
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part is body_part:
                    continue

                disp = (part.get("Content-Disposition") or "").lower()
                fname = part.get_filename()
                maintype = part.get_content_maintype()

                if "attachment" in disp or (fname and "inline" not in disp):
                    if not fname or "." not in fname:
                        _ctype_ext = {
                            "application/pdf": ".pdf", "image/jpeg": ".jpg",
                            "image/png": ".png", "image/tiff": ".tif",
                            "application/msword": ".doc",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                            "text/plain": ".txt", "text/html": ".html",
                        }.get(part.get_content_type(), "")
                        fname = (fname or "Anhang") + _ctype_ext
                    content = part.get_payload(decode=True)
                    if content:
                        result.append(_convert_attachment(content, fname))
                elif maintype == "image":
                    cid = (part.get("Content-ID") or "").strip("<>")
                    if "inline" in disp or cid:
                        fname = fname or f"Bild_{cid or 'inline'}.png"
                        content = part.get_payload(decode=True)
                        if content:
                            result.append(_convert_attachment(content, fname))
        except Exception as e:
            logger.exception("[extract_email_to_structure] Ausnahme beim Parsen der EML:")
            result.append(_not_importable("Unbekannte E-Mail"))

    # .msg
    else:
        try:
            msg = extract_msg.Message(io.BytesIO(data))
            base_name = _build_base_name(msg.subject, msg.date)

            # Body: Prioritätsliste
            for attr, ext in [("htmlBody", ".html"), ("body", ".txt"), ("rtfBody", ".rtf")]:
                content = getattr(msg, attr, None)
                if content:
                    file_name = f"{base_name}{ext}"
                    result.append(_convert_mail_body(content, file_name))
                    break
            else:
                result.append(_not_importable(base_name))

            # Anhänge
            for att in msg.attachments:
                try:
                    fname = att.longFilename or att.shortFilename or "Anhang"
                    data_att = att.data
                    if data_att:
                        result.append(_convert_attachment(data_att, fname))
                    else:
                        result.append(_not_importable(fname))
                except Exception as e:
                    logger.warning("MSG-Anhang konnte nicht gelesen werden: %s", e)
                    result.append(_not_importable(fname if fname else "Anhang"))

        except Exception:
            raise ValueError("Ungültige MSG-Datei")

    return result
