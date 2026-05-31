"""Merge behaviour when the two nodes were compressed at different DPI.

Was previously a module-level script that ran at *collection* time, slept,
asserted nothing and wrote two PDFs into the current working directory. Now a
proper test: it asserts the DPI-conflict semantics and touches no files.

DPI-conflict contract (see PDFNode._merge_pdf):
  - the previously compressed data is discarded (current falls back to original),
  - dpi_current is cleared to None,
  - no_compression becomes True,
  - is_compressed becomes False (no contradictory "compressed but no_compression").
"""

from pypdf import PdfReader
import io

from pdf_node import PDFNode
from helpers import create_valid_pdf, wait_for_ready


def _page_count(data: bytes) -> int:
    return len(PdfReader(io.BytesIO(data)).pages)


def test_merge_with_dpi_conflict_discards_compression():
    a = PDFNode("a", pdf_data=create_valid_pdf(pages=1))
    b = PDFNode("b", pdf_data=create_valid_pdf(pages=1))

    # The constructor kicks off a background compress_multi_lazy(120). Let it
    # settle FIRST, otherwise it can finish after the synchronous compress()
    # below and overwrite dpi_current back to 120 (flaky).
    wait_for_ready(a)
    wait_for_ready(b)

    # Now compress synchronously at deliberately different DPI to force a conflict.
    a.compress(dpi=100)
    b.compress(dpi=200)

    assert a.is_compressed and a.dpi_current == 100
    assert b.is_compressed and b.dpi_current == 200

    a.merge(b, nopreview=True)

    # Conflict resolution: compression discarded, flags consistent.
    assert a.no_compression is True
    assert a.dpi_current is None
    assert a.is_compressed is False, "no_compression and is_compressed must not both be True"

    # Both original pages survive the merge.
    assert a.original_pdf_data is not None
    assert _page_count(a.original_pdf_data) == 2
