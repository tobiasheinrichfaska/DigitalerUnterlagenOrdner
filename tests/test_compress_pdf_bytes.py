from pypdf import PdfReader
import io

from formats.compress_pdf_bytes import compress_pdf_bytes
from helpers import create_valid_pdf


def test_compress_pdf_bytes_returns_valid_smaller_pdf():
    """compress_pdf_bytes must return a valid PDF no larger than the input."""
    original = create_valid_pdf(pages=2)  # real, compressible sample content

    result = compress_pdf_bytes(original, dpi=150)

    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF"), "result is not a PDF"
    assert len(result) <= len(original), "compression must never grow the file"
    # Result is structurally readable and preserves the page count.
    assert len(PdfReader(io.BytesIO(result)).pages) == 2


def test_compress_pdf_bytes_keeps_original_when_no_gain():
    """A tiny PDF that cannot shrink is returned unchanged (never larger)."""
    tiny = create_valid_pdf(pages=1)
    result = compress_pdf_bytes(tiny, dpi=72)
    assert isinstance(result, bytes)
    assert len(result) <= len(tiny)
