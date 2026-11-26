# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""The own .msg reader (olefile + compressed-rtf): deliberate deviations from extract-msg, robustness against
hostile/corrupt files, and the small RTF de-encapsulation. The behaviour shared with extract-msg is pinned in
test_msg_parity.py. Synthetic files only (tests/msg_fixture.py) — no real Outlook mail was available."""
import random
import struct
import time

import pytest

from belegtool_archives import archives, msg_reader, rtf_deencap
from helpers import create_valid_pdf
from msg_fixture import cfb, lzfu_compressed, message_tree, msg

PDF = create_valid_pdf()


def run(data, **kw):
    handed = []

    def convert(content, name):
        handed.append((name, content))
        return create_valid_pdf()

    def shape(nodes):
        return [(n["name"], shape(n["children"]) if "children" in n else None) for n in nodes]

    return shape(archives.extract_email_to_structure(data, convert_member=convert, **kw)), handed


def embedded(subject="Innen", body="Inneres", attachments=(), **kw):
    return message_tree(subject, body, attachments, header=24, **kw)


# --- deliberate deviation 1: an attached Outlook message is recursed (extract-msg: "nicht importierbar") ---------------

def test_embedded_message_becomes_a_folder_with_its_body_and_attachments():
    shape, handed = run(msg("R", "x", [{"name": "Innen.msg", "embedded": embedded("Innen", "Inneres", [("in.pdf", PDF)])},
                                       ("danach.pdf", PDF)]))
    assert shape == [("R.html", None), ("Innen.msg", [("Innen.html", None), ("in.pdf", None)]), ("danach.pdf", None)]
    assert (("Innen.html", b"<html><body>Inneres</body></html>")) in handed and ("in.pdf", PDF) in handed


def test_embedded_message_without_file_name_uses_its_display_name():
    shape, _ = run(msg("R", "x", [{"name": None, "display": "Weitergeleitet", "embedded": embedded()}]))
    assert shape[1][0] == "Weitergeleitet.msg" and shape[1][1] is not None


def test_embedded_message_with_a_non_msg_name_still_gets_the_msg_suffix():
    shape, _ = run(msg("R", "x", [{"name": "Innen", "embedded": embedded()}]))
    assert shape[1][0].endswith(".msg")


def test_embedded_message_inherits_the_ansi_codepage_of_its_parent():
    inner = message_tree("Łódź", "żółć", header=24, ansi=True, codepage="cp1250")
    inner["__properties_version1.0"] = inner["__properties_version1.0"][:24]      # no own 0x3FFD
    shape, handed = run(msg("Łódź", "x", [{"name": "i.msg", "embedded": inner}], ansi=True, codepage="cp1250"))
    assert shape[1][1][0][0] == "Łódź.html"                                        # decoded with the PARENT's cp1250
    assert b"&#380;&#243;&#322;&#263;" in handed[1][1]


def test_deeply_nested_embedded_messages_stop_at_the_depth_limit():
    tree = embedded("tief", "x")
    for i in range(archives._ARCHIVE_MAX_DEPTH + 3):
        tree = embedded("L%d" % i, "x", [{"name": "n.msg", "embedded": tree}])
    shape, _ = run(cfb(message_tree("Top", "x", [{"name": "n.msg", "embedded": tree}])))

    def flat(nodes):
        for name, kids in nodes:
            yield name
            yield from flat(kids or [])
    assert any("zu tief verschachtelt" in n for n in flat(shape))


def test_embedded_message_respects_the_member_budget(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_MEMBERS", 4)
    shape, _ = run(msg("R", "x", [{"name": "i.msg", "embedded": embedded(attachments=[("a%d.pdf" % i, PDF) for i in range(10)])}]))
    inner = shape[1][1]
    assert inner[-1][0].startswith("Weitere Anhänge")
    assert len(inner) <= 4


# --- deliberate deviation 2: one unusable attachment no longer fails the whole mail ---------------------------------------

@pytest.mark.parametrize("method, reason", [(2, "Verknüpfung"), (4, "Verknüpfung"), (7, "Web-Verweis"), (1, "ohne Daten"),
                                            (0, "ohne Daten")])
def test_attachment_without_data_is_marked_and_the_rest_survives(method, reason):
    shape, _ = run(msg("R", "x", [{"name": "ref.pdf", "method": method}, ("ok.pdf", PDF)]))
    assert shape[0] == ("R.html", None) and shape[-1] == ("ok.pdf", None)
    assert shape[1][0].startswith("ref.pdf – nicht importierbar") and reason in shape[1][0]


def test_custom_attachment_storage_is_marked_not_importable():
    att = {"name": "ole.bin", "method": 6, "embedded": {"__substg1.0_00010102": b"x"}}
    shape, _ = run(msg("R", "x", [att, ("ok.pdf", PDF)]))
    assert "nicht importierbar" in shape[1][0] and shape[2] == ("ok.pdf", None)


# --- bomb guards ---------------------------------------------------------------------------------------------------------------

def test_an_oversized_attachment_is_refused_before_it_is_loaded(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 5000)

    def boom(self, cap=None):
        raise AssertionError("stream was loaded although it exceeds the budget")

    monkeypatch.setattr(msg_reader.MsgAttachment, "read", boom)
    shape, _ = run(msg("R", "x", [("riesig.bin", b"z" * 6000)]))
    assert shape[1][0] == "riesig.bin – nicht importierbar (zu groß)"


def test_an_oversized_body_stream_is_refused_not_loaded(monkeypatch):
    monkeypatch.setattr(msg_reader, "MAX_BODY_BYTES", 100)
    shape, _ = run(msg("R", None, html=b"<p>" + b"z" * 500 + b"</p>"))
    assert shape == [("R – nicht importierbar (zu groß)", [])]


def test_read_with_a_cap_raises_without_loading():
    message = msg_reader.open_msg(msg("R", "x", [("a.bin", b"z" * 6000)]))
    att = next(message.attachments())
    assert att.size == 6000
    with pytest.raises(msg_reader.MsgTooLarge):
        att.read(cap=100)
    assert att.read(cap=6000) == b"z" * 6000


def test_attachments_are_listed_lazily_and_in_numeric_order():
    message = msg_reader.open_msg(msg("R", "x", [("a%d.pdf" % i, PDF) for i in range(12)]))
    assert [a.name for a in message.attachments()] == ["a%d.pdf" % i for i in range(12)]


# --- robustness: never anything but a clean ValueError / a result, never a hang ----------------------------------------------

def _sample():
    return msg("Rechnung", "Hallo äöü", [("a.pdf", PDF), {"name": "i.msg", "embedded": embedded("In", "x", [("b.pdf", PDF)])},
                                         ("c.bin", bytes(range(256)) * 30)],
               html="<p>x</p>", rtf=lzfu_compressed(rb"{\rtf1\ansi{\fonttbl{\f0 A;}}x}"))


def test_truncated_and_bit_flipped_files_only_fail_cleanly():
    good = _sample()
    rnd = random.Random(20261126)
    cases = [good[:n] for n in range(0, len(good), max(1, len(good) // 60))]
    for _ in range(300):
        b = bytearray(good)
        for _ in range(rnd.randint(1, 6)):
            b[rnd.randrange(len(b))] = rnd.randrange(256)
        cases.append(bytes(b))
    started = time.monotonic()
    for data in cases:
        try:
            archives.extract_email_to_structure(data, convert_member=lambda c, n: create_valid_pdf())
        except ValueError:
            pass
    assert time.monotonic() - started < 60


def test_a_directory_cycle_terminates():
    data = bytearray(msg("R", "x", [("a.pdf", PDF)]))
    dir_start = struct.unpack_from("<I", data, 48)[0]
    off = 512 + dir_start * 512                    # first directory sector; entry 1 = first child of Root
    struct.pack_into("<I", data, off + 128 + 72, 1)   # entry 1: right sibling = itself
    started = time.monotonic()
    try:
        archives.extract_email_to_structure(bytes(data), convert_member=lambda c, n: create_valid_pdf())
    except ValueError:
        pass
    assert time.monotonic() - started < 10


def test_short_garbage_is_rejected_cleanly():
    for data in (b"", b"abc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"\x00" * 100):
        with pytest.raises(ValueError):
            archives.extract_email_to_structure(data)


def test_a_corrupt_rtf_container_falls_back_to_the_plain_text():
    bad = bytearray(lzfu_compressed(rb"{\rtf1\ansi{\fonttbl{\f0 A;}}x}"))
    bad[-3] ^= 0xFF                                                # CRC no longer matches
    shape, handed = run(msg("R", "plain", rtf=bytes(bad)))
    assert shape == [("R.html", None)] and b"plain" in handed[0][1]


def test_a_corrupt_rtf_container_without_plain_text_is_not_importable():
    shape, _ = run(msg("R", None, rtf=b"\x00" * 40))
    assert shape == [("R – nicht importierbar", [])]


def test_the_other_string_type_is_used_when_the_declared_one_is_missing():
    tree = message_tree("R", None)                                  # Unicode streams …
    tree["__properties_version1.0"] = tree["__properties_version1.0"] + struct.pack("<IIQ", 0x340D0003, 6, 0)  # … but "ANSI store"
    assert run(cfb(tree))[0] == [("R – nicht importierbar", [])]     # subject read (…001F fallback), no body


def test_unknown_codepage_id_does_not_crash():
    shape, _ = run(msg("Käse", "x", ansi=True, codepage="cp1252", extra_props=[(0x3FFD0003, 99999)]))
    assert shape[0][0].endswith(".html")


def test_utf8_codepage_for_ansi_strings():
    shape, _ = run(msg("Bäume", "x", ansi=True, codepage="utf-8"))
    assert shape[0][0] == "Bäume.html"


def test_an_out_of_range_date_is_ignored():
    shape, _ = run(msg("R", "x", extra_props=[(0x00390040, 0x7FFFFFFFFFFFFFFF)]))
    assert shape == [("R.html", None)]


def test_without_the_optional_packages_the_reader_reports_it(monkeypatch):
    monkeypatch.setattr(msg_reader, "AVAILABLE", False)
    with pytest.raises(msg_reader.MsgError, match="nicht installiert"):
        msg_reader.open_msg(msg("R", "x"))


def test_the_reader_does_not_import_extract_msg_or_rtfde():
    import sys
    assert not any(mod is not None and (m == "extract_msg" or m.startswith(("extract_msg.", "RTFDE")))
                   for m, mod in sys.modules.items())


# --- RTF de-encapsulation ----------------------------------------------------------------------------------------------------------

HTML = (rb"{\rtf1\ansi\ansicpg1252\fromhtml1 \deff0{\fonttbl{\f0\fswiss Arial;}}{\colortbl;\red0\green0\blue0;}"
        rb"{\*\htmltag19 <html>}\htmlrtf {\htmlrtf0 {\*\htmltag64 <p>}K\'e4se \u8364?uro{\*\htmltag72 </p>}"
        rb"\htmlrtf \par\htmlrtf0 }{\*\htmltag27 </html>}}")


def test_deencapsulate_html_keeps_tags_text_and_codepage_bytes():
    kind, html = rtf_deencap.deencapsulate(HTML)
    assert kind == "html"
    assert html == b"<html><p>K\xe4se &#8364;uro</p></html>"           # \'e4 = one cp1252 byte, \u8364 -> char ref


def test_deencapsulate_text():
    rtf = rb"{\rtf1\ansi\ansicpg1252\fromtext {\fonttbl{\f0 A;}}Zeile 1\par Gr\'fc\'dfe\tab ok\par}"
    assert rtf_deencap.deencapsulate(rtf) == ("text", "Zeile 1\r\nGrüße\tok\r\n")


def test_ordinary_rtf_is_not_deencapsulated():
    assert rtf_deencap.deencapsulate(rb"{\rtf1\ansi{\fonttbl{\f0 A;}}Hello}") is None
    assert rtf_deencap.deencapsulate(b"not rtf at all") is None
    assert rtf_deencap.deencapsulate(b"") is None


def test_hostile_rtf_is_bounded():
    started = time.monotonic()
    assert rtf_deencap.deencapsulate(b"{\\rtf1\\fromhtml1 " + b"{" * 200000) is None
    deep = b"{\\rtf1\\fromhtml1 " + b"{\\*\\htmltag1 x}" * 50000 + b"}"
    out = rtf_deencap.deencapsulate(deep)
    assert out is not None and len(out[1]) <= len(deep)
    assert time.monotonic() - started < 10


def test_skipped_destinations_do_not_leak_into_the_text():
    rtf = rb"{\rtf1\fromtext {\fonttbl{\f0 Arial;}}{\*\generator Word;}{\info{\title T}}body}"
    assert rtf_deencap.deencapsulate(rtf) == ("text", "body")
