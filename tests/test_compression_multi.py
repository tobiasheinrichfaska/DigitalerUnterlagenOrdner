import time
import pytest
from pdf_node import PDFNode
from compress_pdf_bytes import compress_all_methods, recompress_with_pikepdf
from helpers import create_valid_pdf, wait_for_ready


# ---------------------------------------------------------------------------
# compress_all_methods (unit — no threading)
# ---------------------------------------------------------------------------

def test_compress_all_methods_returns_dict():
    data = create_valid_pdf(pages=1)
    results = compress_all_methods(data, dpi=72)
    assert isinstance(results, dict)


def test_compress_all_methods_all_smaller_than_input():
    data = create_valid_pdf(pages=1)
    results = compress_all_methods(data, dpi=72)
    for method, compressed in results.items():
        assert len(compressed) < len(data), f"{method} result is not smaller than input"


def test_compress_all_methods_sorted_smallest_first():
    data = create_valid_pdf(pages=1)
    results = compress_all_methods(data, dpi=72)
    sizes = [len(v) for v in results.values()]
    assert sizes == sorted(sizes), "Results are not sorted smallest-first"


def test_compress_all_methods_known_keys():
    data = create_valid_pdf(pages=1)
    results = compress_all_methods(data, dpi=72)
    allowed = {"jpg", "jpg_color", "png", "pikepdf"}
    assert set(results.keys()).issubset(allowed)


def test_compress_all_methods_empty_when_no_gain():
    # A near-empty PDF (blank page) may already be minimal; the function must
    # still return a dict (possibly empty) without raising.
    data = create_valid_pdf(pages=1)
    results = compress_all_methods(data, dpi=300)
    assert isinstance(results, dict)


# ---------------------------------------------------------------------------
# recompress_with_pikepdf (fixed API — no CompressionLevel)
# ---------------------------------------------------------------------------

def test_recompress_with_pikepdf_returns_bytes():
    data = create_valid_pdf(pages=1)
    result = recompress_with_pikepdf(data)
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF")


def test_recompress_with_pikepdf_valid_pdf():
    from pypdf import PdfReader
    import io
    data = create_valid_pdf(pages=2)
    result = recompress_with_pikepdf(data)
    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 2


# ---------------------------------------------------------------------------
# PDFNode.compress_multi_lazy (integration)
# ---------------------------------------------------------------------------

def _wait_for_results(node, timeout=20.0):
    """Wait until _compression_results is populated or timeout."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if node._compression_results:
            return
        time.sleep(0.1)
    raise TimeoutError("compress_multi_lazy did not complete in time")


def test_compress_multi_lazy_populates_results():
    data = create_valid_pdf(pages=1)
    node = PDFNode("multi_test", pdf_data=data)
    _wait_for_results(node)
    assert len(node._compression_results) >= 1


def test_compress_multi_lazy_sets_current_pdf_data():
    data = create_valid_pdf(pages=1)
    node = PDFNode("multi_data", pdf_data=data)
    _wait_for_results(node)
    assert node._current_pdf_data is not None
    assert node._current_pdf_data.startswith(b"%PDF")


def test_compress_multi_lazy_best_is_smallest():
    data = create_valid_pdf(pages=1)
    node = PDFNode("multi_best", pdf_data=data)
    _wait_for_results(node)
    results = node._compression_results
    if len(results) >= 2:
        best_size = len(node._current_pdf_data)
        for method, compressed in results.items():
            assert len(compressed) >= best_size, (
                f"Method '{method}' is smaller than the chosen best"
            )


# ---------------------------------------------------------------------------
# PDFNode.select_compression_method
# ---------------------------------------------------------------------------

def test_select_compression_method_switches_data():
    data = create_valid_pdf(pages=1)
    node = PDFNode("select_test", pdf_data=data)
    _wait_for_results(node)
    results = node._compression_results
    if len(results) < 2:
        pytest.skip("Only one compression method produced a result — cannot test switching")

    methods = list(results.keys())
    node.select_compression_method(methods[0])
    assert node._current_pdf_data == results[methods[0]]

    node.select_compression_method(methods[1])
    assert node._current_pdf_data == results[methods[1]]


def test_select_compression_method_unknown_raises():
    data = create_valid_pdf(pages=1)
    node = PDFNode("select_err", pdf_data=data)
    _wait_for_results(node)
    with pytest.raises(ValueError, match="nicht verfügbar"):
        node.select_compression_method("nonexistent_method")


def test_select_compression_method_updates_pdf_length():
    data = create_valid_pdf(pages=1)
    node = PDFNode("select_len", pdf_data=data)
    _wait_for_results(node)
    results = node._compression_results
    if not results:
        pytest.skip("No compression results available")
    method = next(iter(results))
    node.select_compression_method(method)
    from pypdf import PdfReader
    import io
    expected_pages = len(PdfReader(io.BytesIO(results[method])).pages)
    assert node.pdf_length == expected_pages
