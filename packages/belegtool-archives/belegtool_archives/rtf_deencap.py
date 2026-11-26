"""Small RTF de-encapsulation (MS-OXRTFEX) for the .msg reader — pure stdlib, no host imports.

Outlook stores a mail body as *compressed RTF* (property 0x1009). That RTF is either an ordinary RTF document
(``\\rtf1 ... Hello \\b world``) or an **encapsulated** body: the original HTML (``\\fromhtml1``) or plain text
(``\\fromtext``) wrapped into RTF control words. :func:`deencapsulate` unwraps the two encapsulated flavours and
returns ``None`` for everything else (an ordinary RTF is NOT converted to HTML/text — that is what the LGPL
package RTFDE did lazily and what this reader deliberately does not reproduce; the caller then falls back to
the plain text body or hands the RTF over as ``.rtf``).

It is a *simplified* reading of the spec (htmltag groups + text outside ``\\htmlrtf`` runs): no mhtml tags, no
nested-object handling. Hostile input is bounded: group nesting is capped, tokenizing is a single linear regex
pass and output size never exceeds the input size.
"""
import codecs
import re
from typing import Optional, Tuple, Union

_MAX_DEPTH = 500

_TOKEN = re.compile(
    rb"(?P<open>\{)|(?P<close>\})"
    rb"|\\(?P<word>[A-Za-z]{1,32})(?P<param>-?\d{1,10})? ?"
    rb"|\\'(?P<hex>[0-9A-Fa-f]{2})"
    rb"|\\(?P<sym>[^A-Za-z0-9\r\n])"
    rb"|\\(?P<nl>\r?\n)"
    rb"|(?P<text>[^\\{}]+)")

# Groups whose content is never body text.
_SKIP_DESTINATIONS = {b"fonttbl", b"colortbl", b"stylesheet", b"info", b"pict", b"object", b"header", b"footer",
                      b"listtable", b"listoverridetable", b"rsidtbl", b"generator", b"themedata", b"datastore"}

_CTRL_SYMBOLS = {b"\\": b"\\", b"{": b"{", b"}": b"}", b"~": b"\xa0", b"_": b"-", b"-": b""}


def _codec(cp: int) -> str:
    name = "cp%d" % cp
    try:
        codecs.lookup(name)
        return name
    except LookupError:
        return "cp1252"


class _State:
    __slots__ = ("htmlrtf", "skip", "tag", "star", "uc")

    def __init__(self, htmlrtf=False, skip=False, tag=False, star=False, uc=1):
        self.htmlrtf, self.skip, self.tag, self.star, self.uc = htmlrtf, skip, tag, star, uc

    def copy(self):
        return _State(self.htmlrtf, self.skip, self.tag, False, self.uc)


def _kind(rtf: bytes) -> Tuple[Optional[str], int]:
    """('html' | 'text' | None, ANSI code page) from the RTF header control words."""
    head = rtf[:2048]
    cp = 1252
    m = re.search(rb"\\ansicpg(\d{1,5})", head)
    if m:
        cp = int(m.group(1))
    if not head.lstrip().startswith(b"{\\rtf"):
        return None, cp
    if re.search(rb"\\fromhtml(?!0)\d*", head):
        return "html", cp
    if re.search(rb"\\fromtext\b", head):
        return "text", cp
    return None, cp


def deencapsulate(rtf: bytes) -> Optional[Tuple[str, Union[bytes, str]]]:
    """``("html", bytes)`` / ``("text", str)`` for an encapsulated RTF body, else ``None``.

    The HTML bytes keep the RTF's own code page (``\\'e4`` becomes the single byte 0xE4, exactly as the
    ``<meta charset>`` inside the encapsulated tags says); the plain text is decoded.
    """
    kind, cp = _kind(rtf)
    if kind is None:
        return None
    codec = _codec(cp)
    html = kind == "html"
    out = bytearray() if html else []
    stack = []
    st = _State()
    skip_after_u = 0

    def emit_bytes(b: bytes):
        if html:
            out.extend(b)
        else:
            out.append(b.decode(codec, "replace"))

    for m in _TOKEN.finditer(rtf):
        kind_ = "word" if m.group("word") is not None else m.lastgroup   # lastgroup would say "param"
        if kind_ == "open":
            if len(stack) >= _MAX_DEPTH:
                return None
            stack.append(st)
            st = st.copy()
        elif kind_ == "close":
            if not stack:
                break
            st = stack.pop()
        elif kind_ == "word":
            word, param = m.group("word"), m.group("param")
            if st.star:
                st.star = False
                # "\*\htmltag64 <body>" lexes as word "htmltag" + param 64; "mhtmltag" and every other
                # starred destination is dropped.
                if html and word == b"htmltag":
                    st.tag, st.skip = True, False
                else:
                    st.skip = True
                continue
            if word in _SKIP_DESTINATIONS:
                st.skip = True
            elif word == b"htmlrtf":
                st.htmlrtf = param is None or int(param) != 0
            elif word == b"uc" and param is not None:
                st.uc = max(0, int(param))
            elif word == b"u" and param is not None:
                if not st.skip and (not html or st.tag or not st.htmlrtf):
                    code = int(param) & 0xFFFF
                    if html:
                        out.extend(b"&#%d;" % code)
                    else:
                        out.append(chr(code))
                skip_after_u = st.uc
            elif not html and not st.skip:
                if word in (b"par", b"line"):
                    out.append("\r\n")
                elif word == b"tab":
                    out.append("\t")
        elif kind_ == "hex":
            if skip_after_u:
                skip_after_u -= 1
            elif not st.skip and (not html or st.tag or not st.htmlrtf):
                emit_bytes(bytes([int(m.group("hex"), 16)]))
        elif kind_ == "sym":
            sym = m.group("sym")
            if sym == b"*":
                st.star = True
            elif not st.skip and (not html or st.tag or not st.htmlrtf):
                emit_bytes(_CTRL_SYMBOLS.get(sym, b""))
        elif kind_ == "text":
            text = m.group("text").replace(b"\r", b"").replace(b"\n", b"")
            if skip_after_u:
                take = min(skip_after_u, len(text))
                skip_after_u -= take
                text = text[take:]
            if text and not st.skip and (not html or st.tag or not st.htmlrtf):
                emit_bytes(text)
    if html:
        return ("html", bytes(out)) if out else None
    text = "".join(out)
    return ("text", text) if text else None
