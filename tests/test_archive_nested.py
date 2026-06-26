"""#12 — nested archive *and* mail extraction (depth-bounded, shared budget).

A `.zip`/`.tar` or a `.msg`/`.eml` nested *inside* another container used to degrade
to "nicht importierbar" (UniversalImporter.convert has no container branch). These
tests lock the new behaviour: an inner container becomes a FOLDER whose children are
the extracted members, recursion is depth-bounded (anti zip-quine), and the bomb
budget (decoded bytes + member count) is SHARED across all nesting levels so nested
containers can't compound the per-container caps.
"""
import io
import tarfile
import zipfile

import pytest

from universal_importer import archives
from helpers import create_valid_pdf


def _zip_bytes(members: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, payload in members.items():
            z.writestr(name, payload)
    return buf.getvalue()


def _tar_bytes(members: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


def _eml_bytes(subject="Mail", attachments=()):
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "a@b.test"
    msg.set_content("Body")
    for fname, payload, (maintype, subtype) in attachments:
        msg.add_attachment(payload, maintype=maintype, subtype=subtype, filename=fname)
    return msg.as_bytes()


def _walk(struct):
    """Yield every node (leaf or folder) in a nested extraction structure."""
    for node in struct:
        yield node
        if "children" in node:
            yield from _walk(node["children"])


def _pdf_leaves(struct):
    return [n for n in _walk(struct)
            if "content" in n and n["content"].getvalue().startswith(b"%PDF")]


# ----------------------------------------------------------------- zip in zip
def test_zip_in_zip_becomes_folder_with_extracted_child():
    pdf = create_valid_pdf(pages=1)
    inner = _zip_bytes({"doc.pdf": pdf})
    outer = _zip_bytes({"inner.zip": inner})

    struct = archives.extract_zip_to_structure(outer)
    # the inner zip is a FOLDER, not a "nicht importierbar" leaf
    folders = [n for n in struct if n["name"] == "inner.zip" and "children" in n]
    assert len(folders) == 1
    # its child is the extracted PDF
    assert any(c["name"] == "doc.pdf" and c["content"].getvalue().startswith(b"%PDF")
               for c in folders[0]["children"])


# ----------------------------------------------------- cross kind: eml in zip
def test_eml_in_zip_is_recursed():
    pdf = create_valid_pdf(pages=1)
    eml = _eml_bytes(attachments=[("beleg.pdf", pdf, ("application", "pdf"))])
    outer = _zip_bytes({"mail.eml": eml})

    struct = archives.extract_zip_to_structure(outer)
    folder = next(n for n in struct if n["name"] == "mail.eml")
    assert "children" in folder
    # the mail's pdf attachment is reachable through the recursion
    assert any(c.get("name") == "beleg.pdf" for c in _walk(folder["children"]))


# ----------------------------------------------------- cross kind: zip in eml
def test_zip_attachment_in_eml_is_recursed():
    pdf = create_valid_pdf(pages=1)
    inner = _zip_bytes({"rechnung.pdf": pdf})
    eml = _eml_bytes(attachments=[("anhang.zip", inner, ("application", "zip"))])

    struct = archives.extract_email_to_structure(eml)
    folder = next((n for n in _walk(struct) if n.get("name") == "anhang.zip"), None)
    assert folder is not None and "children" in folder
    assert any(c.get("name") == "rechnung.pdf" for c in _walk(folder["children"]))


# --------------------------------------------------------- zip in tar (mixed)
def test_zip_in_tar_is_recursed():
    pdf = create_valid_pdf(pages=1)
    inner = _zip_bytes({"x.pdf": pdf})
    outer = _tar_bytes({"inner.zip": inner})

    struct = archives.extract_tar_to_structure(outer)
    folder = next(n for n in struct if n["name"].endswith("inner.zip"))
    assert "children" in folder
    assert any(c.get("name") == "x.pdf" for c in _walk(folder["children"]))


# --------------------------------------------------------- tar in zip (mixed)
def test_tar_in_zip_is_recursed():
    pdf = create_valid_pdf(pages=1)
    inner = _tar_bytes({"t.pdf": pdf})
    outer = _zip_bytes({"inner.tar": inner})

    struct = archives.extract_zip_to_structure(outer)
    folder = next(n for n in struct if n["name"] == "inner.tar")
    assert "children" in folder
    assert any(c.get("name") == "t.pdf" for c in _walk(folder["children"]))


# ------------------------------------------------ forwarded mail (.eml in .eml)
def test_forwarded_eml_attachment_is_recursed():
    from email.message import EmailMessage
    pdf = create_valid_pdf(pages=1)
    inner = _eml_bytes(subject="Inner", attachments=[("rg.pdf", pdf, ("application", "pdf"))])
    outer = EmailMessage()
    outer["Subject"] = "Outer"
    outer["From"] = "a@b.test"
    outer.set_content("siehe Weiterleitung")
    # attach the inner mail as a .eml file → recursion must open it and reach its pdf
    outer.add_attachment(inner, maintype="application", subtype="octet-stream",
                         filename="weiterleitung.eml")

    struct = archives.extract_email_to_structure(outer.as_bytes())
    folder = next((n for n in _walk(struct) if n.get("name") == "weiterleitung.eml"), None)
    assert folder is not None and "children" in folder
    assert any(c.get("name") == "rg.pdf" for c in _walk(folder["children"]))


# ----------------------------------------------- cross kind: zip inside a .msg
def test_zip_attachment_in_msg_is_recursed(monkeypatch):
    pdf = create_valid_pdf(pages=1)
    inner = _zip_bytes({"m.pdf": pdf})

    class _Att:
        longFilename = "anhang.zip"
        shortFilename = None
        data = inner

    class _Msg:
        subject = "Mit Zip"
        date = "2024-01-01"
        htmlBody = None
        body = "Text"
        rtfBody = None
        attachments = [_Att()]

    # bytes must NOT contain Content-Type:/From: so routing picks the .msg branch
    monkeypatch.setattr(archives.extract_msg, "Message", lambda *a, **k: _Msg())
    struct = archives.extract_email_to_structure(b"\xd0\xcf\x11\xe0not-an-eml")

    folder = next((n for n in _walk(struct) if n.get("name") == "anhang.zip"), None)
    assert folder is not None and "children" in folder
    assert any(c.get("name") == "m.pdf" for c in _walk(folder["children"]))


# ------------------------------------------------------------- depth bounding
def test_recursion_is_depth_bounded():
    pdf = create_valid_pdf(pages=1)
    blob = _zip_bytes({"doc.pdf": pdf})
    # wrap far deeper than _ARCHIVE_MAX_DEPTH so the limit must trigger
    for i in range(_max_depth() + 3):
        blob = _zip_bytes({f"lvl{i}.zip": blob})

    struct = archives.extract_zip_to_structure(blob)
    names = [n["name"] for n in _walk(struct)]
    assert any("zu tief verschachtelt" in n for n in names)


def _max_depth() -> int:
    return getattr(archives, "_ARCHIVE_MAX_DEPTH")


def test_depth_limit_constant_exists_and_is_sane():
    d = _max_depth()
    assert isinstance(d, int) and 1 <= d <= 8


# --------------------------------------------- shared budget (no compounding)
def test_decoded_byte_budget_is_shared_across_nesting(monkeypatch):
    pdf = create_valid_pdf(pages=1)
    p = len(pdf)
    inner1 = _zip_bytes({"one.pdf": pdf})
    inner2 = _zip_bytes({"two.pdf": pdf})
    outer = _zip_bytes({"i1.zip": inner1, "i2.zip": inner2})

    # Enough to read both inner-zip blobs + the FIRST pdf + only half the second.
    # Per-call budgets would reset to max for each nested call and import BOTH pdfs;
    # a shared budget runs out and degrades the second → exactly one PDF survives.
    budget = len(inner1) + len(inner2) + p + p // 2
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", budget)

    struct = archives.extract_zip_to_structure(outer)
    assert len(_pdf_leaves(struct)) == 1
    assert any("nicht importierbar" in n["name"] for n in _walk(struct))


def test_shared_member_budget_bounds_total(monkeypatch):
    # 2 inner zips, each 2 members; a shared member cap of 3 can't admit all 4.
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_MEMBERS", 3)
    pdf = create_valid_pdf(pages=1)
    inner1 = _zip_bytes({"a.pdf": pdf, "b.pdf": pdf})
    inner2 = _zip_bytes({"c.pdf": pdf, "d.pdf": pdf})
    outer = _zip_bytes({"i1.zip": inner1, "i2.zip": inner2})

    struct = archives.extract_zip_to_structure(outer)
    # fewer than the 4 leaf PDFs are materialized, and a limit marker appears.
    assert len(_pdf_leaves(struct)) < 4
    assert any("Limit überschritten" in n["name"] for n in _walk(struct))


# -------------------------------------------- nested container that is corrupt
def test_corrupt_nested_zip_degrades_not_raises():
    # A bogus inner ".zip" must degrade to "nicht importierbar", not abort the import.
    outer = _zip_bytes({"good.pdf": create_valid_pdf(pages=1),
                        "bad.zip": b"PK-not-really-a-zip"})
    struct = archives.extract_zip_to_structure(outer)
    assert any(n["name"].startswith("bad.zip") and "nicht importierbar" in n["name"]
               for n in _walk(struct))
    # the sibling good.pdf still imported
    assert any(n.get("name") == "good.pdf" for n in _pdf_leaves(struct))
