"""Own Outlook ``.msg`` reader on ``olefile`` (BSD-2) + ``compressed-rtf`` (MIT) — replaces ``extract-msg``
(GPLv3) and its LGPL dependency RTFDE. Reads only what the importer needs: subject, sent date, the body in
the order HTML > plain text > RTF, and the attachments (by value, embedded message). Never imports the host.

Format references: MS-OXMSG (message layout, property streams), MS-OXPROPS (tags), MS-OXRTFCP (compressed
RTF), MS-CFB (via olefile). Behaviour deliberately mirrors what the extract-msg based importer produced — see
``tests/test_msg_parity.py``; where it differs on purpose see ``tests/test_msg_reader.py`` and the README.

Robustness: every failure of the container surfaces as :class:`MsgError` (a ``ValueError``); nothing here loops
on file-controlled data without a bound (olefile detects FAT/directory cycles itself), stream sizes are read
from the directory and checked BEFORE a stream is loaded, and compressed RTF is bounded by its input size.
"""
import datetime as _dt
import codecs
import html as _html
import io
import struct
from typing import Iterator, List, Optional, Tuple

try:  # optional extra "msg": without it .msg degrades to "nicht importierbar"
    import olefile
    import compressed_rtf
    AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by test_msg_optional
    olefile = None
    compressed_rtf = None
    AVAILABLE = False

from . import rtf_deencap

#: Largest single stream the reader loads without being told otherwise (bodies; the importer passes the
#: remaining byte budget for attachments).
MAX_BODY_BYTES = 64 * 1024 * 1024
#: Compressed RTF may inflate ~8x; bound its (compressed) input so the output stays far below the bomb cap.
MAX_RTF_BYTES = 32 * 1024 * 1024

_UNSENT = 0x8                      # PidTagMessageFlags MSGFLAG_UNSENT
_STORE_UNICODE_OK = 0x00040000     # PidTagStoreSupportMask
_FILETIME_EPOCH = _dt.datetime(1601, 1, 1, tzinfo=_dt.timezone.utc)

_PT_INT32, _PT_TIME = 0x0003, 0x0040


class MsgError(ValueError):
    """The file is not a readable Outlook message (corrupt/truncated container, not a .msg at all)."""


class MsgTooLarge(MsgError):
    """A stream is larger than the caller allows."""


def _codec_for(codepage: int) -> str:
    """Python codec name of a Windows code page id (fallback: latin-1, decoding never raises)."""
    special = {65001: "utf-8", 1200: "utf-16-le", 20127: "ascii", 20866: "koi8-r", 21866: "koi8-u",
               10000: "mac-roman", 51932: "euc-jp", 54936: "gb18030", 936: "gbk", 950: "big5"}
    if codepage in special:
        name = special[codepage]
    elif 28591 <= codepage <= 28599 or 28603 <= codepage <= 28605:
        name = "iso-8859-%d" % (codepage - 28590)
    else:
        name = "cp%d" % codepage
    try:
        codecs.lookup(name)
        return name
    except LookupError:
        return "latin-1"


def _parse_props(stream: Optional[bytes], header: int) -> dict:
    """{(tag_id, prop_type): 8 value bytes} of a ``__properties_version1.0`` stream (fixed-size values only
    are interpreted; variable-length ones live in their own ``__substg1.0_`` streams)."""
    props = {}
    if not stream:
        return props
    for off in range(header, len(stream) - 15, 16):
        tag, _flags, value = struct.unpack_from("<II8s", stream, off)
        props[(tag >> 16, tag & 0xFFFF)] = value
    return props


def _int32(props: dict, tag_id: int) -> Optional[int]:
    v = props.get((tag_id, _PT_INT32))
    return None if v is None else struct.unpack("<I", v[:4])[0]


class MsgAttachment:
    """One ``__attach_version1.0_#…`` storage."""

    def __init__(self, owner: "MsgMessage", storage: str):
        self._owner = owner
        self._path = owner._prefix + [storage]
        ole = owner._ole
        props = _parse_props(owner._stream_path(self._path + ["__properties_version1.0"], cap=1 << 20), 8)
        self._method = (_int32(props, 0x3705) or 0) & 7
        self.long_name = owner._string("3707", self._path)
        self.short_name = owner._string("3704", self._path)
        self.display_name = owner._string("3001", self._path)
        self.content_id = owner._string("3712", self._path)
        data_path = self._path + ["__substg1.0_37010102"]
        emb_path = self._path + ["__substg1.0_3701000D"]
        self.kind, self.reason, self.size = "unsupported", "", 0
        if ole.exists(data_path):
            self.kind, self.size = "data", ole.get_size(data_path)
        elif ole.exists(emb_path) and ole.get_type(emb_path) == olefile.STGTY_STORAGE:
            if self._method == 5 or ole.exists(emb_path + ["__properties_version1.0"]):
                self.kind = "embedded"
            else:
                self.reason = "benutzerdefinierter Anhang nicht unterstützt"
        elif self._method in (2, 3, 4):
            self.reason = "Verknüpfung statt Datei nicht unterstützt"
        elif self._method == 7:
            self.reason = "Web-Verweis nicht unterstützt"
        else:
            self.reason = "Anhang ohne Daten"

    @property
    def name(self) -> str:
        """Long file name, else 8.3 name (same priority as before; may be empty)."""
        return self.long_name or self.short_name or ""

    def read(self, cap: Optional[int] = None) -> bytes:
        """Bytes of a ``data`` attachment; raises :class:`MsgTooLarge` (without loading) above ``cap``."""
        return self._owner._stream_path(self._path + ["__substg1.0_37010102"], cap=cap)

    def message(self) -> "MsgMessage":
        """The embedded message of an ``embedded`` attachment (a view on its sub-storage, no copy)."""
        return MsgMessage(self._owner._ole, self._path + ["__substg1.0_3701000D"], parent=self._owner)


class MsgMessage:
    """A message: the root of a .msg file or an embedded message (sub-storage)."""

    def __init__(self, ole, prefix: List[str], parent: Optional["MsgMessage"] = None):
        self._ole = ole
        self._prefix = prefix
        self._parent = parent
        self._depth = 0 if parent is None else parent._depth + 1
        self._cache = {}
        header = 32 if parent is None else 24
        self._props = _parse_props(self._stream_path(prefix + ["__properties_version1.0"], cap=MAX_BODY_BYTES), header)
        if not self._props and not ole.exists(prefix + ["__properties_version1.0"]):
            raise MsgError("keine Nachrichten-Eigenschaften (kein Outlook-.msg)")

    # -- low level ---------------------------------------------------------------------------------------------------
    def _stream_path(self, path: List[str], cap: Optional[int]) -> Optional[bytes]:
        ole = self._ole
        if not ole.exists(path) or ole.get_type(path) != olefile.STGTY_STREAM:
            return None
        if cap is not None and ole.get_size(path) > cap:
            raise MsgTooLarge("Stream größer als erlaubt")
        return ole.openstream(path).read()

    def _stream(self, name: str, cap: Optional[int] = -1) -> Optional[bytes]:
        return self._stream_path(self._prefix + [name], MAX_BODY_BYTES if cap == -1 else cap)

    @property
    def strings_unicode(self) -> bool:
        if "unicode" not in self._cache:
            mask = _int32(self._props, 0x340D)
            if mask is not None:
                value = bool(mask & _STORE_UNICODE_OK)
            elif self._parent is not None:
                value = self._parent.strings_unicode
            else:
                value = any(e[-1].upper().endswith("001F") for e in self._ole.listdir(True, False)
                            if e[:len(self._prefix)] == self._prefix)
            self._cache["unicode"] = value
        return self._cache["unicode"]

    @property
    def _encoding(self) -> str:
        """Code page of ANSI (…001E) strings: PidTagMessageCodepage, else the parent's, else ISO-8859-15."""
        cp = _int32(self._props, 0x3FFD)
        if cp:
            return _codec_for(cp)
        return self._parent._encoding if self._parent is not None else "iso-8859-15"

    def _string(self, tag: str, path: Optional[List[str]] = None) -> Optional[str]:
        base = (self._prefix if path is None else path) + ["__substg1.0_" + tag]
        uni, ansi = (base[:-1] + [base[-1] + "001F"]), (base[:-1] + [base[-1] + "001E"])
        order = (uni, ansi) if self.strings_unicode else (ansi, uni)
        for p in order:                               # the other type is a fallback for sloppy writers
            raw = self._stream_path(p, cap=MAX_BODY_BYTES)
            if raw is not None:
                enc = "utf-16-le" if p is uni else self._encoding
                return raw.decode(enc, "replace")
        return None

    # -- content ------------------------------------------------------------------------------------------------------
    @property
    def subject(self) -> Optional[str]:
        return self._string("0037")

    @property
    def date(self) -> Optional[_dt.datetime]:
        """Client submit time (UTC) — only for a sent message, like before."""
        if (_int32(self._props, 0x0E07) or 0) & _UNSENT:
            return None
        raw = self._props.get((0x0039, _PT_TIME))
        if raw is None:
            return None
        ticks = struct.unpack("<Q", raw)[0]
        if not ticks:
            return None
        try:
            return _FILETIME_EPOCH + _dt.timedelta(microseconds=ticks // 10)
        except OverflowError:
            return None

    @property
    def rtf_body(self) -> Optional[bytes]:
        """Decompressed RTF (PidTagRtfCompressed 0x1009, LZFu/MELA); ``None`` if absent or unreadable."""
        if "rtf" not in self._cache:
            value = None
            try:
                raw = self._stream("__substg1.0_10090102", cap=MAX_RTF_BYTES)
                if raw:
                    value = compressed_rtf.decompress(raw)
            except Exception:                         # bad CRC / truncated container: body just absent
                value = None
            self._cache["rtf"] = value
        return self._cache["rtf"]

    @property
    def _deencapsulated(self):
        if "deencap" not in self._cache:
            rtf = self.rtf_body
            try:
                self._cache["deencap"] = rtf_deencap.deencapsulate(rtf) if rtf else None
            except Exception:
                self._cache["deencap"] = None
        return self._cache["deencap"]

    @property
    def text_body(self) -> Optional[str]:
        """Plain text body (0x1000); without one, text unwrapped from a ``\\fromtext`` RTF."""
        if "text" not in self._cache:
            body = self._string("1000")
            if body is None:
                d = self._deencapsulated
                body = d[1] if d and d[0] == "text" else None
            self._cache["text"] = body
        return self._cache["text"]

    @property
    def html_body(self) -> Optional[bytes]:
        """HTML body: the 0x1013 stream as stored (not re-coded); else HTML unwrapped from the RTF; else the
        plain text body turned into minimal HTML (same markup as before)."""
        if "html" not in self._cache:
            html = self._stream("__substg1.0_10130102")
            if html is None:
                d = self._deencapsulated
                if d and d[0] == "html":
                    html = d[1]
            if not html and self.text_body:
                escaped = _html.escape(self.text_body).replace("\r", "").replace("\n", "<br />")
                html = f"<html><body>{escaped}</body></html>".encode("ascii", "xmlcharrefreplace")
            self._cache["html"] = html
        return self._cache["html"]

    def main_body(self) -> Optional[Tuple[str, bytes]]:
        """``(extension, bytes)`` of the body to import — HTML, else text, else the raw RTF — or ``None``."""
        if self.html_body:
            return ".html", self.html_body
        if self.text_body:
            return ".txt", self.text_body.encode("utf-8")
        if self.rtf_body:
            return ".rtf", self.rtf_body
        return None

    def attachments(self) -> Iterator[MsgAttachment]:
        """Attachments in directory order, created lazily (a hostile file with thousands of them costs only
        what the caller consumes). An attachment storage that cannot be read is yielded as ``unsupported``."""
        seen = set()
        n = len(self._prefix)
        for entry in self._ole.listdir(False, True):
            if len(entry) <= n or entry[:n] != self._prefix:
                continue
            name = entry[n]
            if not name.startswith("__attach") or name in seen:
                continue
            seen.add(name)
            yield MsgAttachment(self, name)


def open_msg(data: bytes) -> MsgMessage:
    """Parse ``data`` as an Outlook .msg. Raises :class:`MsgError` for anything that is not a readable one."""
    if not AVAILABLE:
        raise MsgError("MSG-Unterstützung nicht installiert (optionale Pakete olefile, compressed-rtf)")
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))   # BytesIO: bytes < 1536 would be taken as a file NAME
    except Exception as e:
        raise MsgError(str(e) or "kein OLE-Container") from e
    try:
        return MsgMessage(ole, [])
    except MsgError:
        ole.close()
        raise
    except Exception as e:
        ole.close()
        raise MsgError(str(e) or "Nachricht nicht lesbar") from e
