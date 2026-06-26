"""Container extraction: turn a .zip / .tar / .eml / .msg into a nested
structure of importable members, each converted to a PDF via
:class:`universal_importer.importer.UniversalImporter`. Carries the zip/tar bomb
guards (member-count + uncompressed-size caps).

A member that is itself a container (a nested .zip/.tar/.eml/.msg) is **recursed**
into rather than degraded to "nicht importierbar" (#12). Recursion is
**depth-bounded** (``_ARCHIVE_MAX_DEPTH`` — anti zip-quine) and the bomb budget
(decoded bytes + member count) is **shared across all nesting levels** via a
:class:`_Budget` so nested containers cannot compound the per-container caps.
"""

import io
import os
import zipfile
from email import policy
from email.parser import BytesParser
from typing import Any, Dict, List, Optional, Union

import extract_msg

from infra.limits import BOMB_CAP_BYTES, BOMB_CAP_ENTRIES
from infra.log_config import logger

from .importer import UniversalImporter


def _not_importable(name: str, reason: str = "") -> Dict[str, Any]:
    label = f"{name} – nicht importierbar"
    if reason:
        label += f" ({reason})"
    return {
        "name": label,
        "children": []  # ⬅ macht daraus einen Ordner!
    }


# Schutz vor Bomben / riesigen Containern — shared across ALL container paths
# (zip, tar AND email): cap the number of members/parts processed and a running
# total of decoded bytes.
_ARCHIVE_MAX_UNCOMPRESSED_BYTES = BOMB_CAP_BYTES  # 500 MB
_ARCHIVE_MAX_MEMBERS = BOMB_CAP_ENTRIES

# How deep we follow a container nested inside another container (#12). The
# imported top-level container is depth 0; each level down adds 1. A container
# found at this depth is NOT opened (it lands as "zu tief verschachtelt"),
# bounding zip-quine / mail-loop recursion.
_ARCHIVE_MAX_DEPTH = 3

# Member extensions that are themselves containers — recursed into, not converted.
_NESTABLE_EXTS = {".zip", ".tar", ".tgz", ".eml", ".msg"}


class _ArchiveTooLarge(ValueError):
    """Tatsächlich entpackte Archivgröße überschreitet das Limit (Bomben-Schutz).
    Eigener Typ, damit der Per-Member-Catch ihn nicht verschluckt."""


class _Budget:
    """Bomb budget shared across every nesting level of one import.

    Tracks actually-decoded bytes and the number of materialized members so that
    nested containers add to the SAME running totals instead of each getting a
    fresh cap (which would let a tree of small archives compound far past the
    intended limit). Constructed once at the top level from the current module
    constants (so the bomb-guard tests' monkeypatching still applies) and threaded
    unchanged into every recursive call.
    """

    def __init__(self, max_bytes: int, max_members: int, max_depth: int):
        self.max_bytes = max_bytes
        self.max_members = max_members
        self.max_depth = max_depth
        self.bytes = 0
        self.members = 0

    @property
    def bytes_remaining(self) -> int:
        return self.max_bytes - self.bytes

    def can_take_member(self) -> bool:
        return self.members < self.max_members

    def take_member(self) -> None:
        self.members += 1

    def would_exceed(self, n: int) -> bool:
        return self.bytes + n > self.max_bytes

    def take_bytes(self, n: int) -> None:
        self.bytes += n


def _new_budget() -> "_Budget":
    # Read the module constants at call time so monkeypatched caps take effect.
    return _Budget(_ARCHIVE_MAX_UNCOMPRESSED_BYTES, _ARCHIVE_MAX_MEMBERS, _ARCHIVE_MAX_DEPTH)


def _is_nestable(name: str) -> bool:
    return os.path.splitext(name or "")[1].lower() in _NESTABLE_EXTS


def _extract_nested(content: bytes, name: str, depth: int, budget: "_Budget") -> Dict[str, Any]:
    """A member that is itself a container → recurse into it (#12).

    Returns a folder dict ``{"name", "children"}``. Beyond the depth limit, or on
    any failure (corrupt/oversized nested container), degrades to a
    ``_not_importable`` folder so one bad inner container never aborts the import.
    The shared ``budget`` is threaded in so nested decoding can't compound the caps.
    """
    if depth + 1 > budget.max_depth:
        return _not_importable(name, reason="zu tief verschachtelt")
    ext = os.path.splitext(name)[1].lower()
    try:
        if ext == ".zip":
            children = extract_zip_to_structure(content, _depth=depth + 1, _budget=budget)
        elif ext in (".tar", ".tgz"):
            children = extract_tar_to_structure(content, _depth=depth + 1, _budget=budget)
        else:  # .eml / .msg
            children = extract_email_to_structure(content, _depth=depth + 1, _budget=budget)
    except Exception as e:  # corrupt/oversized nested container — degrade, don't abort
        return _not_importable(name, reason=str(e) or "Container nicht lesbar")
    return {"name": name, "children": children}


def _member_result(content: bytes, name: str, depth: int, budget: "_Budget") -> Dict[str, Any]:
    """Convert a freshly-read member to a PDF leaf, OR recurse if it is a nested
    container (#12). Conversion failures degrade to a ``_not_importable`` folder."""
    if _is_nestable(name):
        return _extract_nested(content, name, depth, budget)
    try:
        converted = UniversalImporter.convert(content, name=name)
        if not converted.data.getvalue().strip().startswith(b"%PDF"):
            raise ValueError("PDF-Inhalt ungültig")
        return {"name": name, "content": converted.data}
    except Exception:
        return _not_importable(name)


def extract_zip_to_structure(path_or_bytes: Union[str, bytes, io.BytesIO],
                             _depth: int = 0, _budget: Optional["_Budget"] = None) -> List[Dict[str, Any]]:
    result = []
    budget = _budget or _new_budget()

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

            # Per-container cheap pre-checks against ZIP-Bomben (declared sizes).
            if len(members) > budget.max_members:
                raise ValueError(
                    f"ZIP-Archiv enthält zu viele Einträge ({len(members)} > {budget.max_members})."
                )
            total_uncompressed = sum(info.file_size for info in members)
            if total_uncompressed > budget.max_bytes:
                raise ValueError(
                    f"ZIP-Archiv würde unkomprimiert {total_uncompressed // (1024*1024)} MB belegen "
                    f"(Limit: {budget.max_bytes // (1024*1024)} MB)."
                )

            # Tatsächlich entpackte Bytes deckeln (shared budget) — die deklarierte
            # file_size oben ist nur ein billiger Vorab-Check; ein Eintrag kann eine
            # kleine Größe angeben und beim Lesen trotzdem aufblähen.
            for info in members:
                name = info.filename
                if not budget.can_take_member():
                    result.append(_not_importable("Weitere Einträge", reason="Limit überschritten"))
                    break
                budget.take_member()
                # Open by the ZipInfo, NOT the name string: duplicate member names are
                # legal in a zip, and zf.open(name) resolves every read to the LAST such
                # entry (earlier duplicates would import the wrong bytes).
                with zf.open(info) as f:
                    remaining = budget.bytes_remaining
                    content = f.read(remaining + 1)
                    if len(content) > remaining:
                        raise _ArchiveTooLarge(
                            f"ZIP-Archiv überschreitet beim Entpacken das Limit von "
                            f"{budget.max_bytes // (1024 * 1024)} MB."
                        )
                    budget.take_bytes(len(content))
                result.append(_member_result(content, name, _depth, budget))
    except zipfile.BadZipFile as e:
        raise ValueError("Ungültiges ZIP-Archiv") from e

    return result


def extract_tar_to_structure(path_or_bytes: Union[str, bytes, io.BytesIO],
                             _depth: int = 0, _budget: Optional["_Budget"] = None) -> List[Dict[str, Any]]:
    import tarfile
    result = []
    budget = _budget or _new_budget()

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

            # Per-container cheap pre-checks against TAR-Bomben (declared sizes).
            if len(file_members) > budget.max_members:
                raise ValueError(
                    f"TAR-Archiv enthält zu viele Einträge ({len(file_members)} > {budget.max_members})."
                )
            total_uncompressed = sum(m.size for m in file_members)
            if total_uncompressed > budget.max_bytes:
                raise ValueError(
                    f"TAR-Archiv würde unkomprimiert {total_uncompressed // (1024*1024)} MB belegen "
                    f"(Limit: {budget.max_bytes // (1024*1024)} MB)."
                )

            for member in file_members:
                name = os.path.basename(member.name) or member.name
                if not budget.can_take_member():
                    result.append(_not_importable("Weitere Einträge", reason="Limit überschritten"))
                    break
                budget.take_member()
                try:
                    f = tf.extractfile(member)
                    if f is None:
                        result.append(_not_importable(name))
                        continue
                    remaining = budget.bytes_remaining
                    content = f.read(remaining + 1)
                    if len(content) > remaining:
                        raise _ArchiveTooLarge(
                            f"TAR-Archiv überschreitet beim Entpacken das Limit von "
                            f"{budget.max_bytes // (1024 * 1024)} MB."
                        )
                    budget.take_bytes(len(content))
                    result.append(_member_result(content, name, _depth, budget))
                except _ArchiveTooLarge:
                    raise
                except Exception:
                    result.append(_not_importable(name))
    except tarfile.TarError as e:
        raise ValueError("Ungültiges TAR-Archiv") from e

    return result


def extract_email_to_structure(path_or_bytes: Union[str, bytes, io.BytesIO],
                               _depth: int = 0, _budget: Optional["_Budget"] = None) -> List[Dict[str, Any]]:
    budget = _budget or _new_budget()

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

    def _member_for_attachment(content: bytes, name: str) -> Dict[str, Any]:
        # #12: a nested container attachment is recursed; otherwise convert to PDF.
        if _is_nestable(name):
            return _extract_nested(content, name, _depth, budget)
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

            # Kein From/Subject ins Log (PII) — nur dass das Parsing lief.
            logger.debug("EML-Parsing abgeschlossen")

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

            # Nur Struktur protokollieren, nie den Mail-Inhalt (PII).
            logger.debug("Body-Länge: %d Zeichen", len(body_content))

            file_name = f"{base_name}{extension}"

            logger.debug("Aufruf _convert_mail_body mit Datei: %s", file_name)

            # Bomb budget (shared): the body counts as a member + against the byte cap
            # (an oversized body alone can be a DoS).
            body_bytes = body_content.encode("utf-8") if isinstance(body_content, str) else (body_content or b"")
            budget.take_member()
            if not budget.would_exceed(len(body_bytes)):
                budget.take_bytes(len(body_bytes))
                result.append(_convert_mail_body(body_content, file_name))
            else:
                result.append(_not_importable(file_name, reason="zu groß"))

            # Anhänge + eingebettete Bilder — walk() durchläuft auch verschachtelte MIME-Strukturen
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part is body_part:
                    continue
                if not budget.can_take_member():
                    result.append(_not_importable("Weitere Teile", reason="Limit überschritten"))
                    break

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
                            "application/zip": ".zip",
                            "message/rfc822": ".eml",
                            "text/plain": ".txt", "text/html": ".html",
                        }.get(part.get_content_type(), "")
                        fname = (fname or "Anhang") + _ctype_ext
                    content = part.get_payload(decode=True)
                    if content:
                        budget.take_member()
                        # Refuse before converting: an oversized part must not push the
                        # running total past the cap (mirrors the zip/tar early-abort).
                        if budget.would_exceed(len(content)):
                            result.append(_not_importable(fname, reason="zu groß"))
                        else:
                            budget.take_bytes(len(content))
                            result.append(_member_for_attachment(content, fname))
                elif maintype == "image":
                    cid = (part.get("Content-ID") or "").strip("<>")
                    if "inline" in disp or cid:
                        fname = fname or f"Bild_{cid or 'inline'}.png"
                        content = part.get_payload(decode=True)
                        if content:
                            budget.take_member()
                            if budget.would_exceed(len(content)):
                                result.append(_not_importable(fname, reason="zu groß"))
                            else:
                                budget.take_bytes(len(content))
                                result.append(_member_for_attachment(content, fname))
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
                    body_bytes = content.encode("utf-8") if isinstance(content, str) else content
                    budget.take_member()
                    file_name = f"{base_name}{ext}"
                    if not budget.would_exceed(len(body_bytes)):
                        budget.take_bytes(len(body_bytes))
                        result.append(_convert_mail_body(content, file_name))
                    else:
                        result.append(_not_importable(file_name, reason="zu groß"))
                    break
            else:
                result.append(_not_importable(base_name))

            # Anhänge
            for att in msg.attachments:
                if not budget.can_take_member():
                    result.append(_not_importable("Weitere Anhänge", reason="Limit überschritten"))
                    break
                fname = "Anhang"  # gebunden, bevor att-Zugriffe werfen können
                try:
                    fname = att.longFilename or att.shortFilename or "Anhang"
                    data_att = att.data
                    if data_att:
                        budget.take_member()
                        att_len = len(data_att) if isinstance(data_att, (bytes, bytearray)) else 0
                        if budget.would_exceed(att_len):
                            result.append(_not_importable(fname, reason="zu groß"))
                        else:
                            budget.take_bytes(att_len)
                            result.append(_member_for_attachment(data_att, fname))
                    else:
                        result.append(_not_importable(fname))
                except Exception as e:
                    logger.warning("MSG-Anhang konnte nicht gelesen werden: %s", e)
                    result.append(_not_importable(fname if fname else "Anhang"))

        except Exception:
            raise ValueError("Ungültige MSG-Datei")

    return result
