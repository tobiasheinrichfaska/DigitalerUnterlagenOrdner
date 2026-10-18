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


def msg(subject: str = "Belege", body: str = "Anbei die Belege.", attachments=()) -> bytes:
    """An Outlook message: `attachments` = [(file name, bytes)] or [(file name, bytes, content id)]."""
    tree = {
        "__substg1.0_001A001F": _utf16("IPM.Note"),
        "__substg1.0_0037001F": _utf16(subject),
        "__substg1.0_1000001F": _utf16(body),
        "__nameid_version1.0": {"__substg1.0_00020102": b"", "__substg1.0_00030102": b"",
                                "__substg1.0_00040102": b""},
    }
    for i, att in enumerate(attachments):
        name, data = att[0], att[1]
        storage = {
            "__properties_version1.0": _props([(0x37050003, 1), (0x0E210003, i), (0x370B0003, 0xFFFFFFFF)], 8),
            "__substg1.0_3707001F": _utf16(name),
            "__substg1.0_3704001F": _utf16(name[:12]),
            "__substg1.0_3703001F": _utf16("." + name.rsplit(".", 1)[-1] if "." in name else ""),
            "__substg1.0_37010102": data,
        }
        if len(att) > 2 and att[2]:
            storage["__substg1.0_3712001F"] = _utf16(att[2])
        tree["__attach_version1.0_#%08X" % i] = storage
    header = struct.pack("<8xIIII8x", 0, len(attachments), 0, len(attachments))
    tree["__properties_version1.0"] = header + _props([], 0)
    return cfb(tree)
