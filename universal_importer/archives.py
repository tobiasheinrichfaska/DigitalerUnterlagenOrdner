"""Container extraction: turn a .zip / .tar / .eml / .msg into a nested
structure of importable members, each converted to a PDF via
:class:`universal_importer.importer.UniversalImporter`. Carries the zip/tar bomb
guards (member-count + uncompressed-size caps).
"""

import io
import os
import zipfile
from email import policy
from email.parser import BytesParser
from typing import Any, Dict, List, Optional, Union

import extract_msg

from log_config import logger

from .importer import UniversalImporter


def _not_importable(name: str, reason: str = "") -> Dict[str, Any]:
    label = f"{name} – nicht importierbar"
    if reason:
        label += f" ({reason})"
    return {
        "name": label,
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
        except Exception as e:
            logger.warning("Anhang '%s' nicht importierbar: %s", name, e)
            return _not_importable(name, reason=str(e))

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
        except Exception:
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
