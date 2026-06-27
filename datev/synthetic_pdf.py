"""A tiny, hand-assembled one-page PDF — stdlib only, so the onefile probe needs no
PDF library. Round 2 uploads THIS (never a real document) as the throwaway test file, so a
create/exchange against the live box can never touch real client content."""


def make_test_pdf(text="DATEV-Probe Testdokument — bitte loeschen"):
    """A minimal valid single-page PDF showing ``text`` (ASCII; Helvetica). Returned as bytes,
    ready to POST to ``/document-files``."""
    # Keep the content ASCII — a hand-built PDF has no font embedding, and WinAnsi/Helvetica
    # covers Latin-1; we sanitize to stay safe.
    safe = "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in text)
    safe = safe.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    stream = f"BT /F1 14 Tf 72 720 Td ({safe}) Tj ET".encode("latin-1")

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"

    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objs) + 1)
    out += b"startxref\n%d\n%%%%EOF" % xref_pos
    return bytes(out)
