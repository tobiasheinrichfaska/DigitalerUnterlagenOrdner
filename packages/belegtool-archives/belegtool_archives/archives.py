"""Container extraction: turn a .zip / .tar / .eml / .msg into a nested
structure of importable members. Carries the zip/tar bomb guards (member-count +
uncompressed-size caps).

Converting a member (image / Office / HTML ... -> PDF) is NOT done here: the host
injects a ``convert_member(content: bytes, name: str) -> bytes | io.BytesIO`` callable
(PDF bytes out; raise on failure). Without one, only ``.pdf`` members are accepted
(passed through); everything else degrades to "nicht importierbar".

A member that is itself a container (a nested .zip/.tar/.eml/.msg) is **recursed**
into rather than degraded to "nicht importierbar" (#12). Recursion is
**depth-bounded** (``_ARCHIVE_MAX_DEPTH`` — anti zip-quine) and the bomb budget
(decoded bytes + member count) is **shared across all nesting levels** via a
:class:`_Budget` so nested containers cannot compound the per-container caps.
"""

import io
import logging
import os
import re
import zipfile
from email import policy
from email.parser import BytesParser
from typing import Any, Callable, Dict, List, Optional, Union

from . import msg_reader
from .limits import BOMB_CAP_BYTES, BOMB_CAP_ENTRIES, unsupported_zip_member

logger = logging.getLogger("belegtool_archives")

#: ``convert_member(content, name) -> PDF bytes | io.BytesIO``; raises on failure.
ConvertMember = Callable[[bytes, str], Union[bytes, io.BytesIO]]


def _default_convert_member(content: bytes, name: str) -> io.BytesIO:
    """Fallback without a host converter: only PDFs pass through."""
    if os.path.splitext(name or "")[1].lower() != ".pdf":
        raise ValueError("kein Konverter für dieses Format")
    return io.BytesIO(content)


def _convert(budget: "_Budget", content: bytes, name: str) -> io.BytesIO:
    out = (budget.convert_member or _default_convert_member)(content, name)
    return out if isinstance(out, io.BytesIO) else io.BytesIO(out)


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
# bounding zip-quine / mail-loop recursion. The shared _Budget already bounds the
# total bytes and members, so a generous depth costs nothing extra.
_ARCHIVE_MAX_DEPTH = 10

# TOTAL folder depth one import may build, across container nesting AND member
# paths combined. Without this, 10 nesting levels × 23 path folders each could
# exceed the .belegtool loader's _MAX_TREE_DEPTH (200): the save would succeed
# and the REOPEN would refuse the whole document (audit 2026-11-03, M4). Overflow
# folds into the leaf name / a "zu tief verschachtelt" stub, exactly like the
# per-member _MAX_PATH_DEPTH cap. Guarded by tests/test_archive_total_depth.py.
_MAX_TOTAL_FOLDER_DEPTH = 120

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

    def __init__(self, max_bytes: int, max_members: int, max_depth: int,
                 convert_member: Optional[ConvertMember] = None):
        self.convert_member = convert_member
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


def _new_budget(convert_member: Optional[ConvertMember] = None) -> "_Budget":
    # Read the module constants at call time so monkeypatched caps take effect.
    return _Budget(_ARCHIVE_MAX_UNCOMPRESSED_BYTES, _ARCHIVE_MAX_MEMBERS, _ARCHIVE_MAX_DEPTH,
                   convert_member)


def _budget_for(budget: Optional["_Budget"], convert_member: Optional[ConvertMember]) -> "_Budget":
    """The shared budget of one import; carries the injected converter to every level."""
    if budget is None:
        return _new_budget(convert_member)
    if convert_member is not None and budget.convert_member is None:
        budget.convert_member = convert_member
    return budget


def _is_nestable(name: str) -> bool:
    return os.path.splitext(name or "")[1].lower() in _NESTABLE_EXTS


def _extract_nested(content: bytes, name: str, depth: int, budget: "_Budget",
                    folder_depth: int = 0) -> Dict[str, Any]:
    """A member that is itself a container → recurse into it (#12).

    Returns a folder dict ``{"name", "children"}``. Beyond the depth limit — the
    nesting cap OR the TOTAL folder-depth cap — or on any failure (corrupt/
    oversized nested container), degrades to a ``_not_importable`` folder so one
    bad inner container never aborts the import. The shared ``budget`` is
    threaded in so nested decoding can't compound the caps; ``folder_depth`` is
    the folder depth already above this container's own folder node.
    """
    if depth + 1 > budget.max_depth or folder_depth + 1 >= _MAX_TOTAL_FOLDER_DEPTH:
        return _not_importable(name, reason="zu tief verschachtelt")
    ext = os.path.splitext(name)[1].lower()
    try:
        if ext == ".zip":
            children = extract_zip_to_structure(content, _depth=depth + 1, _budget=budget,
                                                _folder_depth=folder_depth + 1)
        elif ext in (".tar", ".tgz"):
            children = extract_tar_to_structure(content, _depth=depth + 1, _budget=budget,
                                                _folder_depth=folder_depth + 1)
        else:  # .eml / .msg
            children = extract_email_to_structure(content, _depth=depth + 1, _budget=budget,
                                                  _folder_depth=folder_depth + 1)
    except Exception as e:  # corrupt/oversized nested container — degrade, don't abort
        return _not_importable(name, reason=str(e) or "Container nicht lesbar")
    return {"name": name, "children": children}


def _member_result(content: bytes, name: str, depth: int, budget: "_Budget",
                   folder_depth: int = 0) -> Dict[str, Any]:
    """Convert a freshly-read member to a PDF leaf, OR recurse if it is a nested
    container (#12). Conversion failures degrade to a ``_not_importable`` folder."""
    if _is_nestable(name):
        return _extract_nested(content, name, depth, budget, folder_depth)
    try:
        data = _convert(budget, content, name)
        if not data.getvalue().strip().startswith(b"%PDF"):
            raise ValueError("PDF-Inhalt ungültig")
        return {"name": name, "content": data}
    except Exception as e:
        # Show the WHY (workspace rule: errors reach the user with their reason) —
        # the mail-attachment path already does; zip/tar members must too.
        return _not_importable(name, reason=str(e) or "Konvertierung fehlgeschlagen")


# Guard the folder depth built from a single member path. A crafted member name
# (zip names allow up to 64 KB) like "a/a/.../x.pdf" would otherwise spawn thousands
# of nested folder nodes from ONE member — amplification the byte/member bomb caps
# don't catch — and could blow the recursion limit in from_recursive_array. Beyond
# the cap the overflow collapses back into the leaf name (no data lost, depth bounded).
_MAX_PATH_DEPTH = 24

# A bare drive-letter path segment ("C:", "d:") — dropped when building folder nodes.
_DRIVE_SEG = re.compile(r"^[A-Za-z]:$")


def _split_member_path(name: str, max_parts: int = _MAX_PATH_DEPTH):
    """Split an archive member path into (folder_parts, basename). Honors both
    POSIX and Windows separators. ``"rechnungen/2024/beleg.pdf"`` →
    ``(["rechnungen", "2024"], "beleg.pdf")``; a bare name → ``([], name)``.
    Folder depth is capped at ``max_parts`` (≤ ``_MAX_PATH_DEPTH``; the caller
    lowers it when the TOTAL import depth budget runs low — overflow folds into
    the name).
    Traversal-style segments from a hostile member name (``.``, ``..``, a bare drive
    letter like ``C:``) are dropped so they can't become folder nodes named ``..``;
    the tree is in-memory only, so this is cosmetic hardening, not a path-write fix."""
    parts = [p for p in (name or "").replace("\\", "/").split("/")
             if p and p not in (".", "..") and not _DRIVE_SEG.match(p)]
    if not parts:
        # Nothing usable survived sanitizing → fall back to the raw basename so the
        # member still imports under some name instead of vanishing.
        raw = (name or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        return [], (raw or (name or ""))
    cap = max(1, min(_MAX_PATH_DEPTH, max_parts))
    if len(parts) > cap:
        return parts[:cap - 1], "/".join(parts[cap - 1:])
    return parts[:-1], parts[-1]


def _ensure_folder(children: List[Dict[str, Any]], folder_name: str) -> Dict[str, Any]:
    """Find an existing folder dict named ``folder_name`` in ``children`` (so siblings
    merge under one folder), else create and append one. Returns the folder dict."""
    for c in children:
        if "children" in c and c.get("name") == folder_name:
            return c
    folder = {"name": folder_name, "children": []}
    children.append(folder)
    return folder


def _insert_by_path(root_children: List[Dict[str, Any]], folder_parts: List[str],
                    node: Dict[str, Any]) -> None:
    """Place ``node`` under the nested folders named by ``folder_parts`` (created /
    merged on demand), so an archive's own subfolders become real folder nodes
    instead of a path baked into the leaf name."""
    cur = root_children
    for part in folder_parts:
        cur = _ensure_folder(cur, part)["children"]
    cur.append(node)


def extract_zip_to_structure(path_or_bytes: Union[str, bytes, io.BytesIO],
                             _depth: int = 0, _budget: Optional["_Budget"] = None,
                             _folder_depth: int = 0,
                             convert_member: Optional[ConvertMember] = None) -> List[Dict[str, Any]]:
    result = []
    budget = _budget_for(_budget, convert_member)

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
                # A member path like "ordner/datei.pdf" becomes a folder node + leaf,
                # not a leaf literally named "ordner/datei.pdf"; siblings merge. The
                # per-member path cap shrinks as the TOTAL depth budget runs out.
                folders, base = _split_member_path(
                    info.filename, _MAX_TOTAL_FOLDER_DEPTH - _folder_depth)
                if not budget.can_take_member():
                    result.append(_not_importable("Weitere Einträge", reason="Limit überschritten"))
                    break
                budget.take_member()
                # Budget already spent (e.g. an earlier nested container overflowed and
                # was charged): degrade THIS member visibly — reading on would raise
                # _ArchiveTooLarge at the top level and abort the whole import.
                if budget.bytes_remaining <= 0:
                    _insert_by_path(result, folders, _not_importable(base, reason="Limit überschritten"))
                    continue
                # bzip2/LZMA members decompress UNBOUNDED before any read cap applies
                # (CPython zipfile) — refuse them instead of trusting the declared size.
                unsafe = unsupported_zip_member(info)
                if unsafe:
                    _insert_by_path(result, folders, _not_importable(base, reason=unsafe))
                    continue
                # One bad member (encrypted, corrupt stream) degrades WITH its reason
                # instead of aborting the whole archive — mirrors the tar loop.
                try:
                    # Open by the ZipInfo, NOT the name string: duplicate member names are
                    # legal in a zip, and zf.open(name) resolves every read to the LAST such
                    # entry (earlier duplicates would import the wrong bytes).
                    with zf.open(info) as f:
                        remaining = budget.bytes_remaining
                        content = f.read(remaining + 1)
                        if len(content) > remaining:
                            # Charge what was decoded BEFORE failing, so repeated nested
                            # attempts cannot redo ~budget-sized work for free (the nested
                            # caller degrades this error and carries on).
                            budget.take_bytes(remaining)
                            raise _ArchiveTooLarge(
                                f"ZIP-Archiv überschreitet beim Entpacken das Limit von "
                                f"{budget.max_bytes // (1024 * 1024)} MB."
                            )
                        budget.take_bytes(len(content))
                except _ArchiveTooLarge:
                    raise
                except Exception as e:
                    _insert_by_path(result, folders, _not_importable(base, reason=str(e)))
                    continue
                _insert_by_path(result, folders, _member_result(
                    content, base, _depth, budget, _folder_depth + len(folders)))
    except zipfile.BadZipFile as e:
        raise ValueError("Ungültiges ZIP-Archiv") from e

    return result


def _tar_decompressor_factory(head: bytes):
    """Factory for the matching decompressor, or None for plain tar. The bz2 check
    is STRICT (level digit + block magic "1AY&SY"): a plain tar whose first member
    is named "BZh9_…" must not be mistaken for bzip2."""
    if head.startswith(b"\x1f\x8b"):
        import zlib
        return lambda: zlib.decompressobj(wbits=47)  # gzip container
    if (head.startswith(b"BZh") and head[3:4].isdigit() and head[3:4] != b"0"
            and head[4:10] == b"1AY&SY"):
        import bz2
        return bz2.BZ2Decompressor
    if head.startswith(b"\xfd7zXZ\x00"):
        import lzma
        return lzma.LZMADecompressor
    return None


def _inflate_one_stream(dec, buf: bytes, room: int):
    """Inflate ONE compressed stream, never materialising more than ``room + 1``
    bytes. Returns ``(bytes, truncated)`` — truncated means the input ended before
    the stream did. Handles both input-styles: zlib re-feeds ``unconsumed_tail``,
    bz2/lzma buffer internally and continue on ``decompress(b"", n)``."""
    out = bytearray()
    data = buf
    while True:
        space = room + 1 - len(out)
        if space <= 0:
            return bytes(out), False  # over the cap — the caller raises
        chunk = dec.decompress(data, min(space, 1 << 20))
        out += chunk
        if dec.eof:
            return bytes(out), False
        data = getattr(dec, "unconsumed_tail", b"")
        if not data and not chunk:
            return bytes(out), True  # no progress, nothing pending → truncated
        if not getattr(dec, "unconsumed_tail", b""):
            data = b""


def _inflate_tar_stream(data: bytes, budget: "_Budget") -> bytes:
    """A gz/bz2/xz-compressed tar stream, inflated bounded and CHARGED to the
    shared budget.

    ``tarfile.open`` with auto-detection walks the WHOLE stream in ``getmembers``
    BEFORE any declared-size pre-check can run — so the inflation itself must be
    bounded (by the REMAINING budget, and charged, or nested retries redo the work
    for free). Multi-stream archives (pigz/pbzip2 concatenate streams) are drained
    stream by stream; plain tar passes through untouched (members are charged on
    read as before). The result is parsed as PLAIN tar only (mode "r:"), so a
    double-compressed gz(bz2(tar)) cannot re-open the unbounded tarfile path."""
    make = _tar_decompressor_factory(data[:10])
    if make is None:
        return data
    limit = budget.bytes_remaining
    out = bytearray()
    buf = data
    while True:
        dec = make()
        try:
            part, truncated = _inflate_one_stream(dec, buf, limit - len(out))
        except _ArchiveTooLarge:
            raise
        except Exception as e:
            raise ValueError("Ungültiges TAR-Archiv") from e
        out += part
        if len(out) > limit:
            budget.take_bytes(limit)  # charge the inflation work before failing
            raise _ArchiveTooLarge(
                f"TAR-Archiv überschreitet beim Entpacken das Limit von "
                f"{budget.max_bytes // (1024 * 1024)} MB.")
        if truncated:
            raise ValueError("Ungültiges TAR-Archiv (unvollständig komprimiert)")
        buf = dec.unused_data
        if not buf or _tar_decompressor_factory(buf[:10]) is None:
            break  # drained (trailing bytes, if any, are the tar parser's problem)
    budget.take_bytes(len(out))
    return bytes(out)


def extract_tar_to_structure(path_or_bytes: Union[str, bytes, io.BytesIO],
                             _depth: int = 0, _budget: Optional["_Budget"] = None,
                             _folder_depth: int = 0,
                             convert_member: Optional[ConvertMember] = None) -> List[Dict[str, Any]]:
    import tarfile
    result = []
    budget = _budget_for(_budget, convert_member)

    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as f:
            data = f.read()
    elif isinstance(path_or_bytes, io.BytesIO):
        data = path_or_bytes.read()
    else:
        data = path_or_bytes

    try:
        data = _inflate_tar_stream(data, budget)
    except _ArchiveTooLarge as e:
        raise ValueError(str(e)) from e

    try:
        # PLAIN tar only: the stream above is already inflated; auto-detection
        # ("r:*") would inflate a still-compressed inner layer UNBOUNDED again.
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tf:
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
                # Keep the tar's own subfolders as folder nodes (and distinct basenames
                # across folders) instead of flattening every member to its basename.
                folders, base = _split_member_path(
                    member.name, _MAX_TOTAL_FOLDER_DEPTH - _folder_depth)
                if not budget.can_take_member():
                    result.append(_not_importable("Weitere Einträge", reason="Limit überschritten"))
                    break
                budget.take_member()
                if budget.bytes_remaining <= 0:  # spent budget degrades, never aborts
                    _insert_by_path(result, folders, _not_importable(base, reason="Limit überschritten"))
                    continue
                try:
                    f = tf.extractfile(member)
                    if f is None:
                        _insert_by_path(result, folders, _not_importable(base))
                        continue
                    remaining = budget.bytes_remaining
                    content = f.read(remaining + 1)
                    if len(content) > remaining:
                        # Charge what was decoded BEFORE failing (parity with the zip
                        # loop): nested retries must not redo budget-sized work free.
                        budget.take_bytes(remaining)
                        raise _ArchiveTooLarge(
                            f"TAR-Archiv überschreitet beim Entpacken das Limit von "
                            f"{budget.max_bytes // (1024 * 1024)} MB."
                        )
                    budget.take_bytes(len(content))
                    _insert_by_path(result, folders, _member_result(
                        content, base, _depth, budget, _folder_depth + len(folders)))
                except _ArchiveTooLarge:
                    raise
                except Exception as e:
                    _insert_by_path(result, folders, _not_importable(base, reason=str(e)))
    except tarfile.TarError as e:
        raise ValueError("Ungültiges TAR-Archiv") from e

    return result


def extract_email_to_structure(path_or_bytes: Union[str, bytes, io.BytesIO],
                               _depth: int = 0, _budget: Optional["_Budget"] = None,
                               _folder_depth: int = 0,
                             convert_member: Optional[ConvertMember] = None) -> List[Dict[str, Any]]:
    budget = _budget_for(_budget, convert_member)

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
            return {"name": filename, "content": _convert(budget, content, filename)}
        except Exception:
            return _not_importable(filename)

    def _member_for_attachment(content: bytes, name: str, depth: int = _depth,
                               folder_depth: int = _folder_depth) -> Dict[str, Any]:
        # #12: a nested container attachment is recursed; otherwise convert to PDF.
        if _is_nestable(name):
            return _extract_nested(content, name, depth, budget, folder_depth)
        try:
            return {"name": name, "content": _convert(budget, content, name)}
        except Exception as e:
            logger.warning("Anhang '%s' nicht importierbar: %s", name, e)
            return _not_importable(name, reason=str(e))

    def _msg_children(message, depth: int, folder_depth: int) -> List[Dict[str, Any]]:
        """Body + attachments of one Outlook message (the file itself or an embedded message)."""
        out: List[Dict[str, Any]] = []
        base_name = _build_base_name(message.subject, message.date)

        try:
            body = message.main_body()
        except msg_reader.MsgTooLarge:
            body = None
            out.append(_not_importable(base_name, reason="zu groß"))
        if body:
            ext, body_bytes = body
            file_name = f"{base_name}{ext}"
            if not budget.can_take_member():  # member cap first (parity with zip/tar)
                out.append(_not_importable(file_name, reason="Limit überschritten"))
            else:
                budget.take_member()
                if not budget.would_exceed(len(body_bytes)):
                    budget.take_bytes(len(body_bytes))
                    out.append(_convert_mail_body(body_bytes, file_name))
                else:
                    out.append(_not_importable(file_name, reason="zu groß"))
        elif not out:
            out.append(_not_importable(base_name))

        # Anhänge
        for att in message.attachments():
            if not budget.can_take_member():
                out.append(_not_importable("Weitere Anhänge", reason="Limit überschritten"))
                break
            fname = "Anhang"  # gebunden, bevor att-Zugriffe werfen können
            try:
                fname = att.name or "Anhang"
                if att.kind == "embedded":
                    out.append(_embedded_message(att, fname, depth, folder_depth))
                elif att.kind != "data":
                    out.append(_not_importable(fname, reason=att.reason))
                elif att.size:
                    budget.take_member()
                    if budget.would_exceed(att.size):
                        out.append(_not_importable(fname, reason="zu groß"))
                    else:
                        data_att = att.read(cap=budget.bytes_remaining)
                        budget.take_bytes(len(data_att))
                        out.append(_member_for_attachment(data_att, fname, depth, folder_depth))
                else:
                    out.append(_not_importable(fname))
            except Exception as e:
                logger.warning("MSG-Anhang konnte nicht gelesen werden: %s", e)
                out.append(_not_importable(fname if fname else "Anhang"))
        return out

    def _embedded_message(att, fname: str, depth: int, folder_depth: int) -> Dict[str, Any]:
        """An attached Outlook message is recursed into a folder of ITS body + attachments (extract-msg
        degraded it to "nicht importierbar"); same depth/budget rules as every nested container."""
        budget.take_member()
        if not _is_nestable(fname):
            fname = (att.display_name or fname) + ".msg"
        if depth + 1 > budget.max_depth or folder_depth + 1 >= _MAX_TOTAL_FOLDER_DEPTH:
            return _not_importable(fname, reason="zu tief verschachtelt")
        try:
            children = _msg_children(att.message(), depth + 1, folder_depth + 1)
        except Exception as e:
            return _not_importable(fname, reason=str(e) or "Nachricht nicht lesbar")
        return {"name": fname, "children": children}

    result = []

    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as f:
            data = f.read()
    elif isinstance(path_or_bytes, (bytes, io.BytesIO)):
        data = path_or_bytes.read() if isinstance(path_or_bytes, io.BytesIO) else path_or_bytes
    else:
        raise TypeError("Pfad, Bytes oder BytesIO erwartet")

    # Routing: ein .msg ist ein CFB-Container — dessen Signatur entscheidet ZUERST.
    # Der Marker-Schnüffler allein leitete ein .msg fehl, sobald irgendwo in den
    # rohen Bytes b"From:" steht (z. B. "<b>From:</b>" im HTML-Rumpf einer
    # englischen Outlook-Antwort) — BytesParser erzeugt dann Müll statt der Mail.
    is_cfb = data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")

    # .eml
    if not is_cfb and (b"Content-Type:" in data or b"From:" in data):
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
            # (an oversized body alone can be a DoS). Check the member cap FIRST —
            # like zip/tar/attachments — so nested mails can't overshoot it.
            body_bytes = body_content.encode("utf-8") if isinstance(body_content, str) else (body_content or b"")
            if not budget.can_take_member():
                result.append(_not_importable(file_name, reason="Limit überschritten"))
            else:
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
            message = msg_reader.open_msg(data)
            result.extend(_msg_children(message, _depth, _folder_depth))
        except Exception as e:
            # Ursache mitgeben (Log + __cause__) — "Ungültige MSG-Datei" allein ließ
            # den eigentlichen Fehler (defekter CFB, Reader-Bug) unsichtbar.
            logger.warning("MSG-Parsing fehlgeschlagen: %s", e)
            if not msg_reader.AVAILABLE:
                raise ValueError("MSG-Unterstützung nicht installiert (optionale Pakete olefile, compressed-rtf)") from e
            raise ValueError("Ungültige MSG-Datei") from e

    return result
