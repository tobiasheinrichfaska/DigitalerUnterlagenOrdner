"""The `UniversalImporter` dispatcher: detect a file's type (extension + leading
magic / dangerous-signature checks), then route it to the matching converter in
:mod:`universal_importer.converters`. Container formats (zip/tar/email) are
handled separately in :mod:`universal_importer.archives`.
"""

import io
import os
import tempfile
from typing import List, Optional, Union

from infra.log_config import logger

from . import converters
from .converters import ConvertedPDF


class UniversalImporter:
    PDF_EXTENSIONS = [".pdf", ".belegtool"]
    IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"]
    CUSTOM_EXTENSIONS = [".dbeleg"]
    MODERN_IMAGE_EXTENSIONS = [".webp", ".heic"]
    ARCHIVE_AND_EMAIL_EXTENSIONS = [".zip", ".tar", ".tgz", ".eml", ".msg"]
    TEXT_EXTENSIONS = [".txt", ".rtf", ".md"]
    HTML_EXTENSIONS = [".html"]
    OFFICE_WORD_EXT = [".doc", ".docx", ".odt"]
    OFFICE_EXCEL_EXT = [".xls", ".xlsx", ".ods"]
    OFFICE_POWERPOINT_EXT = [".ppt", ".pptx", ".odp"]
    OFFICE_EXTENSIONS = OFFICE_WORD_EXT + OFFICE_EXCEL_EXT + OFFICE_POWERPOINT_EXT

    # Executable / script signatures we refuse to import whatever the extension
    # claims — guards against an EXE/script masquerading as a benign attachment.
    _DANGEROUS_SIGNATURES = [
        (b"MZ", "Windows-Programm (EXE/DLL)"),
        (b"\x7fELF", "ELF-Binärdatei"),
        (b"\xca\xfe\xba\xbe", "Mach-O-/Java-Binärdatei"),
        (b"#!", "Skript (Shebang)"),
    ]

    # Extensions whose real content has an unambiguous leading magic number we
    # can verify up front (so a mismatch fails clearly instead of degrading
    # later to an opaque "%PDF"-check failure).
    _EXPECTED_MAGIC = {
        ".pdf":  [b"%PDF"],
        ".png":  [b"\x89PNG\r\n\x1a\n"],
        ".jpg":  [b"\xff\xd8\xff"],
        ".jpeg": [b"\xff\xd8\xff"],
        ".bmp":  [b"BM"],
        ".tif":  [b"II*\x00", b"MM\x00*"],
        ".tiff": [b"II*\x00", b"MM\x00*"],
    }

    @classmethod
    def verify_content_matches_extension(cls, data: bytes, ext: str, name: str) -> None:
        """Reject dangerous content and obvious magic-byte/extension mismatches.

        Raises ValueError with a user-readable reason; routes by real content
        rather than trusting the extension alone (audit finding 4). Types
        without a reliable leading signature (office/zip/text/email/heic/webp)
        are left to their converters, which fail gracefully.
        """
        head = data[:16] if data else b""
        for sig, label in cls._DANGEROUS_SIGNATURES:
            if head.startswith(sig):
                raise ValueError(f"'{name}' sieht aus wie {label}, nicht wie {ext} – abgelehnt.")

        expected = cls._EXPECTED_MAGIC.get(ext)
        if expected and not any(head.startswith(sig) for sig in expected):
            raise ValueError(
                f"Unerwarteter Inhalt für '{name}': die Datei beginnt nicht wie ein {ext}.")

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        # Office/ODF are ALWAYS advertised: conversion runs through office_via_com
        # (COM) and degrades gracefully to "nicht importierbar" if Office isn't
        # installed — exactly like the path branch of convert(), which routes by
        # OFFICE_EXTENSIONS unconditionally. (The old runtime COM probe — _has_word
        # etc. — launched Word/Excel/PowerPoint just to detect them AND was never
        # wired in, so it stayed False forever; that made the bytes branch reject
        # every Office/ODF member inside a zip/email. Removed.)
        return (
            cls.PDF_EXTENSIONS +
            cls.IMAGE_EXTENSIONS +
            cls.CUSTOM_EXTENSIONS +
            cls.MODERN_IMAGE_EXTENSIONS +
            cls.ARCHIVE_AND_EMAIL_EXTENSIONS +
            cls.TEXT_EXTENSIONS +
            cls.HTML_EXTENSIONS +
            cls.OFFICE_EXTENSIONS
        )

    @classmethod
    def get_filetypes_for_dialog(cls) -> List[tuple]:
        def pattern(exts):
            return " ".join(f"*{ext}" for ext in exts)

        return [
            ("Alle unterstützten Formate", pattern(cls.get_supported_extensions())),
            ("PDF",                        "*.pdf"),
            ("BelegTool-Dateien",          "*.belegtool"),
            ("Archive",                    "*.zip *.tar *.tgz"),
            ("E-Mails",                    "*.eml *.msg"),
            ("Bilder",                     pattern(cls.IMAGE_EXTENSIONS + cls.MODERN_IMAGE_EXTENSIONS)),
            ("Word / OpenDocument Text",   pattern(cls.OFFICE_WORD_EXT)),
            ("Excel / OpenDocument Tabelle", pattern(cls.OFFICE_EXCEL_EXT)),
            ("PowerPoint / OpenDocument Präsentation", pattern(cls.OFFICE_POWERPOINT_EXT)),
        ]

    @classmethod
    def is_supported(cls, path: str) -> bool:
        p = path.lower()
        if p.endswith(".tar.gz") or p.endswith(".tgz"):
            return True
        ext = os.path.splitext(p)[1]
        return ext in cls.get_supported_extensions()

    @classmethod
    def convert(cls, source: Union[str, bytes, io.BytesIO], name: Optional[str] = None) -> ConvertedPDF:
        """Konvertiert eine Datei (Pfad, Bytes oder BytesIO) in ein PDF.

        Routet anhand der Endung (für Bytes nach einer Inhalts-/Signaturprüfung)
        an die passende Funktion in :mod:`universal_importer.converters`.
        """
        if isinstance(source, str):
            path = source
            ext = os.path.splitext(path)[1].lower()
            # Same signature/magic gate as the bytes branch — so single-file imports
            # (import dialog / OS drag) refuse an EXE/script up front too, instead of
            # degrading to an opaque "%PDF"-check failure later.
            try:
                with open(path, "rb") as f:
                    head = f.read(16)
            except OSError:
                head = b""
            cls.verify_content_matches_extension(head, ext, os.path.basename(path))
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

            # Content-based safety/type check before we trust the extension and
            # hand the bytes to a converter (covers e-mail attachments).
            cls.verify_content_matches_extension(data, ext, name)

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(data)
                path = tmp.name

            try:
                result = cls.convert(path)
                result.name = name  # Originalname beibehalten

                pdf_bytes = result.data.getvalue()
                result.data = io.BytesIO(pdf_bytes)

                if not pdf_bytes.strip().startswith(b"%PDF"):
                    raise ValueError(f"Ungültige PDF-Daten erzeugt für: {name}")
                return result
            finally:
                os.unlink(path)

        # Verarbeitung über bekannten Pfad
        if ext in cls.PDF_EXTENSIONS + cls.CUSTOM_EXTENSIONS:
            result = converters.passthrough(path)
        elif ext in cls.IMAGE_EXTENSIONS:
            result = converters.standard_image(path)
        elif ext in cls.MODERN_IMAGE_EXTENSIONS:
            result = converters.modern_image(path)
        elif ext in cls.TEXT_EXTENSIONS:
            with open(path, "rb") as f:
                content = f.read()
            _n = name or os.path.basename(path)
            result = converters.txt_to_pdf(content, name=os.path.splitext(_n)[0] + ".pdf")
        elif ext in cls.HTML_EXTENSIONS:
            with open(path, "rb") as f:
                content = f.read()
            _n = name or os.path.basename(path)
            result = converters.html_to_pdf(content, name=os.path.splitext(_n)[0] + ".pdf")
        elif ext in cls.OFFICE_EXTENSIONS:
            result = converters.office_via_com(path, ext)
        else:
            raise ValueError(f"Nicht unterstützter Dateityp: {ext}")

        # Reparatur und Validierung (Pfad-Zweig)
        pdf_bytes = result.data.getvalue()
        result.data = io.BytesIO(pdf_bytes)

        if not pdf_bytes.strip().startswith(b"%PDF"):
            raise ValueError(f"Ungültige PDF-Daten erzeugt aus Datei: {path}")

        return result
