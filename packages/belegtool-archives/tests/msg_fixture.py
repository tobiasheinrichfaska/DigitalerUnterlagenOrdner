"""Synthetic Outlook .msg files for tests (stdlib only): a minimal Compound File Binary (CFB v3) writer and an
MSG layout on top — subject, body, attachments with long/short file names, an optional content id (inline
image). Fictitious content only; nothing here comes from a real mailbox (Outlook is never touched)."""
from __future__ import annotations

import struct

SECTOR, MINI, CUTOFF = 512, 64, 4096
FREE, END, FATSECT, NOSTREAM = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFF


def _utf16(text: str) -> bytes:
    return text.encode("utf-16-le")


def cfb(tree: dict) -> bytes:
    """A CFB file from a nested dict: {name: bytes (stream) | dict (storage)}."""
    entries = [{"name": "Root Entry", "type": 5, "kids": tree}]
    queue = [0]
    while queue:                                    # flatten breadth-first, children chained as right siblings
        parent = queue.pop(0)
        kids = entries[parent].get("kids") or {}
        ids = []
        for name, value in kids.items():
            entries.append({"name": name, "type": 1 if isinstance(value, dict) else 2,
                            "kids": value if isinstance(value, dict) else None,
                            "data": value if isinstance(value, bytes) else None})
            ids.append(len(entries) - 1)
            if isinstance(value, dict):
                queue.append(len(entries) - 1)
        entries[parent]["child"] = ids[0] if ids else NOSTREAM
        for a, b in zip(ids, ids[1:] + [NOSTREAM]):
            entries[a]["right"] = b

    mini, minifat, big = bytearray(), [], []
    for e in entries:
        data = e.get("data")
        if data is None:
            continue
        if len(data) == 0:
            e["start"], e["size"] = END, 0
        elif len(data) < CUTOFF:
            first = len(mini) // MINI
            n = -(-len(data) // MINI)
            mini += data + b"\0" * (n * MINI - len(data))
            minifat += [first + i + 1 for i in range(n - 1)] + [END]
            e["start"], e["size"] = first, len(data)
        else:
            big.append(e)
            e["size"] = len(data)

    def nsec(nbytes):
        return -(-nbytes // SECTOR)

    n_dir = nsec(len(entries) * 128)
    n_minifat = nsec(len(minifat) * 4)
    n_mini = nsec(len(mini))
    n_big = [nsec(e["size"]) for e in big]
    n_other = n_dir + n_minifat + n_mini + sum(n_big)
    n_fat = 1
    while n_fat * 128 < n_other + n_fat:
        n_fat += 1
    fat, pos = [], 0

    def chain(n):
        nonlocal pos
        start = pos
        fat.extend([pos + i + 1 for i in range(n - 1)] + [END] if n else [])
        pos += n
        return start if n else END

    dir_start = chain(n_dir)
    minifat_start = chain(n_minifat)
    mini_start = chain(n_mini)
    for e, n in zip(big, n_big):
        e["start"] = chain(n)
    fat_start = pos
    fat.extend([FATSECT] * n_fat)
    fat.extend([FREE] * (n_fat * 128 - len(fat)))
    entries[0]["start"], entries[0]["size"] = (mini_start, len(mini)) if mini else (END, 0)

    header = bytearray(SECTOR)
    struct.pack_into("<8s16sHHHHH6sIIIIIIIII", header, 0, bytes.fromhex("D0CF11E0A1B11AE1"), b"\0" * 16,
                     0x3E, 3, 0xFFFE, 9, 6, b"\0" * 6, 0, n_fat, dir_start, 0, CUTOFF,
                     minifat_start if minifat else END, n_minifat, END, 0)
    difat = [fat_start + i for i in range(n_fat)] + [FREE] * (109 - n_fat)
    struct.pack_into("<109I", header, 76, *difat)

    directory = bytearray()
    for e in entries:
        name = _utf16(e["name"]) + b"\0\0"
        d = bytearray(128)
        d[0:len(name)] = name
        struct.pack_into("<HBBIII", d, 64, len(name), e["type"], 1, NOSTREAM, e.get("right", NOSTREAM),
                         e.get("child", NOSTREAM))
        struct.pack_into("<II", d, 116, e.get("start", END) if e["type"] != 1 else 0, e.get("size", 0))
        directory += d
    while len(directory) % SECTOR:
        empty = bytearray(128)
        struct.pack_into("<III", empty, 68, NOSTREAM, NOSTREAM, NOSTREAM)
        directory += empty

    def padded(data):
        return bytes(data) + b"\0" * (nsec(len(data)) * SECTOR - len(data))

    body = padded(directory) + padded(struct.pack("<%dI" % len(minifat), *minifat)) + padded(mini)
    for e in big:
        body += padded(e["data"])
    body += struct.pack("<%dI" % len(fat), *fat)
    return bytes(header) + body


def _props(entries, header: int) -> bytes:
    out = b"\0" * header
    for tag, value in entries:
        out += struct.pack("<IIQ", tag, 6, value)
    return out


def filetime(dt) -> int:
    """FILETIME (100 ns ticks since 1601-01-01 UTC) of a timezone-aware datetime."""
    import datetime as _dt
    return int((dt - _dt.datetime(1601, 1, 1, tzinfo=_dt.timezone.utc)) / _dt.timedelta(microseconds=1)) * 10


def lzfu_uncompressed(rtf: bytes) -> bytes:
    """A 'MELA' (stored, uncompressed) compressed-RTF container, MS-OXRTFCP 2.1.3.1 — stdlib only, so the
    reader's stored-path is tested without the compressed_rtf library."""
    return struct.pack("<II4sI", len(rtf) + 12, len(rtf), b"MELA", 0) + rtf


def lzfu_compressed(rtf: bytes) -> bytes:
    """A real LZFu container (compressed with the MIT `compressed_rtf` package; test dependency)."""
    import compressed_rtf
    return compressed_rtf.compress(rtf)


class _Strings:
    """Writes string properties either as UTF-16 (…001F) or as an ANSI code page (…001E)."""

    def __init__(self, ansi: bool, codepage: str):
        self.ansi, self.codepage = ansi, codepage

    def put(self, tree: dict, tag: str, text: str) -> None:
        if self.ansi:
            tree["__substg1.0_%s001E" % tag] = text.encode(self.codepage)
        else:
            tree["__substg1.0_%s001F" % tag] = _utf16(text)


def _attachment(spec, i: int, strings: _Strings) -> dict:
    """One `__attach_version1.0_#…` storage. `spec` is a tuple (name, data[, content id]) or a dict with keys
    name (long name or None), short (8.3 name; default = name[:12]), data, cid, method (default 1 = by value),
    embedded (a message tree from `message_tree`, stored as `__substg1.0_3701000D`), display (PidTagDisplayName)."""
    if not isinstance(spec, dict):
        spec = {"name": spec[0], "data": spec[1], "cid": spec[2] if len(spec) > 2 else None}
    name = spec.get("name")
    method = spec.get("method", 5 if spec.get("embedded") is not None else 1)
    storage = {"__properties_version1.0": _props([(0x37050003, method), (0x0E210003, i), (0x370B0003, 0xFFFFFFFF)], 8)}
    short = spec.get("short", name[:12] if name else None)
    if name:
        strings.put(storage, "3707", name)
    if short:
        strings.put(storage, "3704", short)
    if name and "." in name:
        strings.put(storage, "3703", "." + name.rsplit(".", 1)[-1])
    if spec.get("display"):
        strings.put(storage, "3001", spec["display"])
    if spec.get("embedded") is not None:
        storage["__substg1.0_3701000D"] = spec["embedded"]
    elif spec.get("data") is not None:
        storage["__substg1.0_37010102"] = spec["data"]
    if spec.get("cid"):
        strings.put(storage, "3712", spec["cid"])
    return storage


def message_tree(subject="Belege", body="Anbei die Belege.", attachments=(), *, html=None, rtf=None, ansi=False,
                 codepage="cp1252", sent=None, unsent=False, header=32, class_="IPM.Note", extra_props=()) -> dict:
    """The storage tree of one message (the root of a .msg, or the sub-storage of an embedded message).

    body        plain text (PidTagBody 0x1000) or None to omit it
    html        PidTagHtml 0x1013 (binary): str is encoded with `codepage`, bytes are stored as given
    rtf         PidTagRtfCompressed 0x1009: the already compressed bytes (see lzfu_compressed/lzfu_uncompressed)
    ansi        write all strings as …001E in `codepage` (+ PidTagMessageCodepage 0x3FFD) instead of UTF-16 …001F
    sent        timezone-aware datetime for PidTagClientSubmitTime 0x0039; unsent=True sets MSGFLAG_UNSENT
    header      size of the message's property-stream header: 32 for a root message, 24 for an embedded one
    """
    import encodings
    strings = _Strings(ansi, codepage)
    tree = {"__nameid_version1.0": {"__substg1.0_00020102": b"", "__substg1.0_00030102": b"",
                                   "__substg1.0_00040102": b""}} if header == 32 else {}
    strings.put(tree, "001A", class_)
    if subject is not None:
        strings.put(tree, "0037", subject)
    if body is not None:
        strings.put(tree, "1000", body)
    if html is not None:
        tree["__substg1.0_10130102"] = html if isinstance(html, bytes) else html.encode(codepage if ansi else "utf-8")
    if rtf is not None:
        tree["__substg1.0_10090102"] = rtf
    for i, att in enumerate(attachments):
        tree["__attach_version1.0_#%08X" % i] = _attachment(att, i, strings)
    n = len(attachments)
    props = list(extra_props)
    if ansi:
        props.append((0x3FFD0003, _CODEPAGE_IDS[codepage]))
    if sent is not None:
        props.append((0x00390040, filetime(sent)))
    if unsent:
        props.append((0x0E070003, 8))
    if header == 32:
        head = struct.pack("<8xIIII8x", 0, n, 0, n)
    else:
        head = struct.pack("<8xIIII", 0, n, 0, n)
    tree["__properties_version1.0"] = head + _props(props, 0)
    return tree


_CODEPAGE_IDS = {"cp1252": 1252, "cp1250": 1250, "cp1251": 1251, "cp437": 437, "utf-8": 65001, "iso-8859-15": 28605}


def msg(subject: str = "Belege", body: str = "Anbei die Belege.", attachments=(), **kw) -> bytes:
    """An Outlook message: `attachments` = [(file name, bytes)] / [(file name, bytes, content id)] / dict specs
    (see `_attachment`); keyword options: see `message_tree`."""
    return cfb(message_tree(subject, body, attachments, **kw))
