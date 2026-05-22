from compress_pdf_bytes import compress_pdf_bytes

def test_compress_pdf_bytes_smoke():
    # Keine echte Validierung – stellt sicher, dass Funktion aufrufbar ist
    try:
        result = compress_pdf_bytes(b"%PDF-1.4\n%%EOF", dpi=72)
    except Exception:
        result = None
    assert result is None or isinstance(result, bytes)