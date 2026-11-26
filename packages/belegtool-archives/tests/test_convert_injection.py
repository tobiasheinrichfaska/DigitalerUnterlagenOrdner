"""The converter interface: `convert_member(content, name) -> bytes | BytesIO`, injected by the host.
This module runs WITHOUT the conftest fake (see conftest) so the library's own fallback is exercised."""

import io
import zipfile

from belegtool_archives import archives, extract_email_to_structure, extract_tar_to_structure, extract_zip_to_structure
from helpers import create_valid_pdf


def _zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, p in members.items():
            z.writestr(n, p)
    return buf.getvalue()


def _walk(nodes):
    for n in nodes:
        yield n
        yield from _walk(n.get("children") or [])


def test_default_accepts_pdf_and_degrades_everything_else():
    out = extract_zip_to_structure(_zip({"a.pdf": create_valid_pdf(), "b.png": b"\x89PNG"}))
    names = [n["name"] for n in out]
    assert "a.pdf" in names
    assert any(n.startswith("b.png – nicht importierbar") for n in names)


def test_injected_converter_is_used_and_may_return_bytes():
    calls = []

    def conv(content, name):
        calls.append(name)
        return create_valid_pdf()  # plain bytes are accepted

    out = extract_zip_to_structure(_zip({"b.png": b"x"}), convert_member=conv)
    assert calls == ["b.png"]
    assert out[0]["content"].getvalue().startswith(b"%PDF")


def test_injected_converter_reaches_nested_containers():
    inner = _zip({"deep.png": b"x"})
    seen = []

    def conv(content, name):
        seen.append(name)
        return io.BytesIO(create_valid_pdf())

    out = extract_zip_to_structure(_zip({"inner.zip": inner}), convert_member=conv)
    assert seen == ["deep.png"]
    assert [n["name"] for n in _walk(out)] == ["inner.zip", "deep.png"]


def test_converter_failure_degrades_with_reason():
    def conv(content, name):
        raise ValueError("kaputt")

    out = extract_zip_to_structure(_zip({"b.png": b"x"}), convert_member=conv)
    assert out[0]["name"] == "b.png – nicht importierbar (kaputt)"


def test_tar_and_eml_take_the_converter_too():
    import tarfile
    from email.message import EmailMessage

    seen = []

    def conv(content, name):
        seen.append(name)
        return create_valid_pdf()

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        info = tarfile.TarInfo("t.png")
        info.size = 1
        tf.addfile(info, io.BytesIO(b"x"))
    extract_tar_to_structure(buf.getvalue(), convert_member=conv)
    msg = EmailMessage()
    msg["Subject"] = "S"
    msg.set_content("hi")
    msg.add_attachment(b"x", maintype="image", subtype="png", filename="m.png")
    extract_email_to_structure(msg.as_bytes(), convert_member=conv)
    assert "t.png" in seen and "m.png" in seen


def test_msg_without_the_optional_msg_packages_degrades(monkeypatch):
    monkeypatch.setattr(archives.msg_reader, "AVAILABLE", False)      # as if olefile/compressed-rtf were missing
    # a bare CFB signature routes to the .msg branch
    cfb = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512
    import pytest
    with pytest.raises(ValueError, match="MSG-Unterstützung nicht installiert"):
        extract_email_to_structure(cfb)
    # nested inside a zip it becomes a "nicht importierbar" node instead of aborting
    out = extract_zip_to_structure(_zip({"x.msg": cfb, "ok.pdf": create_valid_pdf()}))
    names = [n["name"] for n in out]
    assert "ok.pdf" in names
    assert any(n.startswith("x.msg – nicht importierbar") for n in names)
