"""Parity suite for the Outlook .msg reader (2026-11-26).

Written FIRST against the extract-msg based implementation (GPLv3) and kept green across the switch to the
own olefile reader — so every expectation below is the behaviour extract-msg 0.58.3 showed on the SAME
synthetic files (tests/msg_fixture.py; no real Outlook mail was available). Expected values are literals,
not a runtime comparison, so the suite needs no extract-msg once the swap is done.

What is compared is what the host sees: names + order of the produced nodes and the exact bytes handed to the
injected converter (mail body, attachment bytes). Deliberate deviations of the own reader live in
test_msg_reader.py, NOT here (e.g. embedded .msg, an attachment without data).
"""
import datetime as dt

import pytest

from belegtool_archives import archives
from helpers import create_valid_pdf
from msg_fixture import cfb, lzfu_compressed, lzfu_uncompressed, message_tree, msg

PDF = create_valid_pdf()
UTC = dt.timezone.utc
SENT = dt.datetime(2026, 11, 25, 23, 30, tzinfo=UTC)          # late evening UTC: the date must stay UTC

RTF = rb"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0 Arial;}}\f0 Hello \b world\b0\par}"
HTML_RTF = (rb"{\rtf1\ansi\ansicpg1252\fromhtml1 \deff0{\fonttbl{\f0\fswiss Arial;}}"
            rb"{\*\htmltag19 <html>}\htmlrtf {\htmlrtf0 {\*\htmltag64 <body>}Hello {\*\htmltag72 </body>}"
            rb"\htmlrtf }\htmlrtf0 {\*\htmltag27 </html>}}")
TEXT_RTF = rb"{\rtf1\ansi\ansicpg1252\fromtext \deff0{\fonttbl{\f0\fswiss Arial;}}Hello text\par}"


def extract(data):
    """-> (shape, handed): shape = nested [(name, children | None)], handed = [(name, bytes)] as given to the converter."""
    handed = []

    def convert(content, name):
        handed.append((name, content))
        return create_valid_pdf()

    def shape(nodes):
        return [(n["name"], shape(n["children"]) if "children" in n else None) for n in nodes]

    return shape(archives.extract_email_to_structure(data, convert_member=convert)), handed


def names(data):
    return [n for n, _ in extract(data)[0]]


def body_of(data):
    """(name, bytes) of the FIRST thing handed to the converter = the mail body."""
    return extract(data)[1][0]


# --- subject / plain body / date -------------------------------------------------------------------------

def test_plain_body_becomes_generated_html_with_attachment_in_order():
    shape, handed = extract(msg("Rechnung", "Hallo Welt\r\nZeile2 äöü", [("a.pdf", PDF), ("b.pdf", PDF)]))
    assert shape == [("Rechnung.html", None), ("a.pdf", None), ("b.pdf", None)]
    assert handed[0] == ("Rechnung.html", b"<html><body>Hallo Welt<br />Zeile2 &#228;&#246;&#252;</body></html>")
    assert handed[1:] == [("a.pdf", PDF), ("b.pdf", PDF)]


def test_plain_body_is_html_escaped():
    assert body_of(msg("S", "a < b & \"c\" 'd'\nnext"))[1] == \
        b"<html><body>a &lt; b &amp; &quot;c&quot; &#x27;d&#x27;<br />next</body></html>"


def test_sent_date_is_appended_in_utc():
    assert names(msg("Rechnung", "Hallo", sent=SENT)) == ["Rechnung 2026-11-25.html"]


def test_unsent_flag_drops_the_date():
    assert names(msg("Rechnung", "Hallo", sent=SENT, unsent=True)) == ["Rechnung.html"]


def test_no_date_property_no_date():
    assert names(msg("Rechnung", "Hallo")) == ["Rechnung.html"]


def test_missing_subject_is_called_email():
    assert names(msg(None, "x")) == ["E-Mail.html"]


def test_subject_is_sanitised_for_a_file_name():
    assert names(msg("AW: a/b", "x", sent=SENT)) == ["AW- a-b 2026-11-25.html"]


def test_no_body_at_all_is_not_importable():
    assert extract(msg("R", None))[0] == [("R – nicht importierbar", [])]


def test_empty_body_is_not_importable():
    assert extract(msg("R", ""))[0] == [("R – nicht importierbar", [])]


def test_empty_html_stream_and_no_body_is_not_importable():
    assert extract(msg("R", None, html=b""))[0] == [("R – nicht importierbar", [])]


def test_zero_attachments():
    assert extract(msg("R", "x"))[0] == [("R.html", None)]


# --- HTML body 0x1013 ---------------------------------------------------------------------------------------

def test_html_body_is_passed_through_byte_for_byte_and_beats_plain():
    html = "<html><body>Grüße €</body></html>"
    assert body_of(msg("Rechnung", "plain", html=html, sent=SENT)) == \
        ("Rechnung 2026-11-25.html", html.encode("utf-8"))


def test_html_only_message():
    assert body_of(msg("R", None, html=b"<html>x</html>")) == ("R.html", b"<html>x</html>")


def test_html_body_in_a_legacy_codepage_is_not_recoded():
    raw = "<html><body>Käse €</body></html>".encode("cp1252")
    assert body_of(msg("R", None, html=raw, ansi=True, codepage="cp1252"))[1] == raw


def test_html_beats_rtf_and_plain():
    assert body_of(msg("R", "plain", html="<p>H</p>", rtf=lzfu_compressed(HTML_RTF)))[1] == b"<p>H</p>"


# --- compressed RTF body 0x1009 ----------------------------------------------------------------------------------

def test_plain_rtf_only_is_delivered_as_rtf_file_decompressed():
    assert body_of(msg("R", None, rtf=lzfu_compressed(RTF))) == ("R.rtf", RTF)


def test_stored_mela_rtf_container_is_read_too():
    assert body_of(msg("R", None, rtf=lzfu_uncompressed(RTF))) == ("R.rtf", RTF)


def test_plain_rtf_with_a_plain_text_body_prefers_the_generated_html():
    assert body_of(msg("R", "plain body", rtf=lzfu_compressed(RTF))) == \
        ("R.html", b"<html><body>plain body</body></html>")


def test_html_encapsulated_in_rtf_is_deencapsulated():
    assert body_of(msg("R", None, rtf=lzfu_compressed(HTML_RTF))) == \
        ("R.html", b"<html><body>Hello </body></html>")


def test_html_encapsulated_in_rtf_beats_the_plain_body():
    assert body_of(msg("R", "plain body", rtf=lzfu_compressed(HTML_RTF))) == \
        ("R.html", b"<html><body>Hello </body></html>")


def test_text_encapsulated_in_rtf_becomes_generated_html():
    assert body_of(msg("R", None, rtf=lzfu_compressed(TEXT_RTF))) == \
        ("R.html", b"<html><body>Hello text<br /></body></html>")


# --- strings: Unicode (…001F) vs ANSI (…001E) + code page ------------------------------------------------------------

def test_unicode_streams():
    shape, handed = extract(msg("Bäume €", "Größe €", [("Käse €.pdf", PDF)]))
    assert shape == [("Bäume €.html", None), ("Käse €.pdf", None)]
    assert handed[0][1] == b"<html><body>Gr&#246;&#223;e &#8364;</body></html>"


@pytest.mark.parametrize("codepage, subject, body, att, expected_html", [
    ("cp1252", "Bäume €", "Größe äöü €", "Käse.pdf",
     b"<html><body>Gr&#246;&#223;e &#228;&#246;&#252; &#8364;</body></html>"),
    ("cp1250", "Łódź", "żółć", "Łódź.pdf",
     b"<html><body>&#380;&#243;&#322;&#263;</body></html>"),
    ("cp1251", "Привет", "Счёт № 5", "Счёт.pdf",
     b"<html><body>&#1057;&#1095;&#1105;&#1090; &#8470; 5</body></html>"),
])
def test_ansi_streams_use_the_message_codepage(codepage, subject, body, att, expected_html):
    shape, handed = extract(msg(subject, body, [(att, PDF)], ansi=True, codepage=codepage))
    assert shape == [(f"{subject}.html", None), (att, None)]
    assert handed[0][1] == expected_html


def test_ansi_streams_without_a_codepage_property_default_to_iso_8859_15():
    # PidTagMessageCodepage 0x3FFD absent: the spec says MAY-be ISO-8859-1, extract-msg used ISO-8859-15.
    tree = message_tree("Euro €", "€ und Käse", ansi=True, codepage="iso-8859-15", extra_props=[])
    # drop the codepage property the fixture adds for ansi=True
    tree["__properties_version1.0"] = tree["__properties_version1.0"][:32]
    assert body_of(cfb(tree)) == ("Euro €.html", b"<html><body>&#8364; und K&#228;se</body></html>")


# --- attachments --------------------------------------------------------------------------------------------------------

def test_attachment_bytes_are_delivered_unchanged():
    blob = bytes(range(256)) * 40                          # > 4096 bytes: stored in the regular (not mini) stream
    handed = extract(msg("R", "x", [("big.bin", blob)]))[1]
    assert handed[1] == ("big.bin", blob)


def test_long_file_name_beats_the_8_3_name():
    assert names(msg("R", "x", [{"name": "Rechnung März.pdf", "short": "RECHNU~1.PDF", "data": PDF}])) == \
        ["R.html", "Rechnung März.pdf"]


def test_only_the_8_3_name_is_used_when_there_is_no_long_name():
    assert names(msg("R", "x", [{"name": None, "short": "RECHNU~1.PDF", "data": PDF}])) == \
        ["R.html", "RECHNU~1.PDF"]


def test_attachment_without_any_name_is_called_anhang():
    assert extract(msg("R", "x", [{"name": None, "data": PDF}]))[0] == [("R.html", None), ("Anhang", None)]


def test_attachment_with_empty_data_is_not_importable():
    assert extract(msg("R", "x", [("leer.pdf", b"")]))[0] == [("R.html", None), ("leer.pdf – nicht importierbar", [])]


def test_content_id_inline_image_stays_a_normal_attachment_and_the_html_untouched():
    html = '<html><body><img src="cid:img1"></body></html>'
    shape, handed = extract(msg("R", "x", html=html, attachments=[("logo.png", b"\x89PNG....", "img1")]))
    assert shape == [("R.html", None), ("logo.png", None)]
    assert handed == [("R.html", html.encode()), ("logo.png", b"\x89PNG....")]


def test_nested_container_attachments_are_recursed():
    inner = msg("Innen", "i", [("x.pdf", PDF)])
    shape, _ = extract(msg("R", "x", [("Innen.msg", inner)]))
    assert shape == [("R.html", None), ("Innen.msg", [("Innen.html", None), ("x.pdf", None)])]


def test_embedded_message_attachment_yields_an_entry_next_to_the_body():
    # extract-msg degrades it ("nicht importierbar"), the own reader recurses (test_msg_reader.py) — what both
    # share: the body + the named entry, nothing lost around it.
    emb = message_tree("Innen", "Inneres", [("in.pdf", PDF)], header=24)
    shape, handed = extract(msg("R", "x", [{"name": "Innen.msg", "embedded": emb}, ("danach.pdf", PDF)]))
    assert shape[0] == ("R.html", None)
    assert shape[1][0].startswith("Innen.msg")
    assert shape[-1] == ("danach.pdf", None)
    assert handed[0][0] == "R.html" and ("danach.pdf", PDF) in handed


def test_many_attachments_stop_at_the_member_cap_with_a_visible_marker():
    shape, handed = extract(msg("R", "x", [("a%d.pdf" % i, PDF) for i in range(600)]))
    assert len(shape) == 501                                              # body + 499 attachments + marker
    assert shape[0] == ("R.html", None)
    assert shape[1] == ("a0.pdf", None) and shape[499] == ("a498.pdf", None)
    assert shape[-1] == ("Weitere Anhänge – nicht importierbar (Limit überschritten)", [])
    assert len(handed) == 500


def test_byte_budget_marks_an_oversized_attachment_and_keeps_the_rest(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 5000)
    shape, _ = extract(msg("R", "x", [("riesig.bin", b"z" * 6000), ("klein.pdf", PDF)]))
    assert shape == [("R.html", None), ("riesig.bin – nicht importierbar (zu groß)", []), ("klein.pdf", None)]


def test_byte_budget_marks_an_oversized_body(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 100)
    shape, _ = extract(msg("R", None, html=b"<p>" + b"z" * 500 + b"</p>"))
    assert shape == [("R.html – nicht importierbar (zu groß)", [])]


# --- broken input -------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("data", [
    msg("R", "x", [("a.pdf", PDF * 100)])[:3000],                    # cut inside the sector data
    msg("R", "x", [("a.pdf", PDF)])[:1000],                          # cut right after the header
    msg("R", "x")[:511],                                              # shorter than the CFB header
    bytes.fromhex("D0CF11E0A1B11AE1") + b"\0" * 600,                 # signature, nonsense header
    cfb({"WordDocument": b"abc" * 100}),                              # a valid OLE file that is no message
])
def test_corrupt_or_foreign_ole_files_raise_the_uniform_error(data):
    with pytest.raises(ValueError, match="Ungültige MSG-Datei"):
        archives.extract_email_to_structure(data)
