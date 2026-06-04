from infra.tools import sanitize_pdf

def test_sanitize_pdf_returns_bytes():
    cleaned = sanitize_pdf(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF")
    assert isinstance(cleaned, bytes)
    assert cleaned.startswith(b"%PDF")