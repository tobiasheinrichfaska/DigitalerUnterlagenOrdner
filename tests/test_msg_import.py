"""Outlook .msg import with SYNTHETIC .msg files (tests/msg_fixture.py writes real CFB/MSG files; extract_msg
reads them). Found 2026-10-18 while adding .msg support to a sibling tool:

`archives.extract_email_to_structure` used to decide .eml vs .msg by searching the raw bytes for
b"Content-Type:" or b"From:". A .msg carries its attachments' bytes unencoded inside the OLE container, so a
.msg with an attached mail (forwarded "as attachment") was routed to the EML parser and every attachment was
lost, silently. Fixed 2026-11-04: the OLE/CFB signature (D0 CF 11 E0 A1 B1 1A E1) is checked FIRST.
"""
import email.message

from universal_importer import archives
from helpers import create_valid_pdf
from msg_fixture import msg

OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")


def _names(nodes):
    out = []
    for n in nodes:
        out.append(n.get("name"))
        out += _names(n.get("children") or [])
    return out


def _forwarded_mail() -> bytes:
    m = email.message.EmailMessage()
    m["From"], m["To"], m["Subject"] = "a@example.org", "b@example.org", "Weitergeleitet"
    m.set_content("Originaltext")
    return m.as_bytes()


def test_the_fixture_is_a_real_msg():
    data = msg("Rechnung", "Anbei.", [("Rechnung.pdf", create_valid_pdf())])
    assert data[:8] == OLE_SIGNATURE


def test_a_plain_msg_imports_its_body_and_attachment():
    data = msg("Rechnung", "Anbei.", [("Rechnung.pdf", create_valid_pdf())])
    names = _names(archives.extract_email_to_structure(data))
    assert "Rechnung.pdf" in names and any(n.startswith("Rechnung") and n != "Rechnung.pdf" for n in names)


def test_a_forwarded_msg_keeps_its_attachments():
    # FIXED 2026-11-04 (audit fix round): routing now checks the CFB signature first,
    # so the b"From:" inside the container no longer misroutes the .msg to the EML
    # parser. Was a strict xfail from 2026-10-18 until the fix turned it red.
    data = msg("WG: Rechnung", "Siehe unten.", [("Rechnung.pdf", create_valid_pdf()),
                                                ("Original.eml", _forwarded_mail())])
    assert b"From:" in data and data[:8] == OLE_SIGNATURE           # the old trigger, inside a genuine .msg
    names = _names(archives.extract_email_to_structure(data))
    assert "Rechnung.pdf" in names
