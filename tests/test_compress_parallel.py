"""Parallel compression must match the sequential path exactly (same per-page
content, same order) and actually use multiple workers. The legacy fixtures are
all <8 pages (below _PARALLEL_MIN_PAGES), so this is the only test exercising the
multi-worker code path."""

import hashlib
import threading

import fitz

import compress_pdf_bytes as C


def _make_pdf(n_pages: int) -> bytes:
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page(width=300, height=400)
        # distinct content per page so a mis-ordered assembly is detectable
        page.insert_text((40, 80 + (i % 5) * 30), f"PAGE {i + 1} of {n_pages}")
    data = doc.tobytes()
    doc.close()
    return data


def _page_hashes(pdf_bytes: bytes):
    """Visual content hash per page — immune to any PDF-container nondeterminism."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [hashlib.md5(doc[i].get_pixmap(dpi=72).tobytes("png")).hexdigest()
                for i in range(doc.page_count)]
    finally:
        doc.close()


def test_parallel_matches_sequential_content_and_order(monkeypatch):
    data = _make_pdf(12)
    monkeypatch.setattr(C.cpu, "worker_count", lambda: 4)

    # forced-sequential reference (raise the floor above the page count)
    monkeypatch.setattr(C, "_PARALLEL_MIN_PAGES", 10_000)
    seq = C._render_pdf_as_images(data, dpi=100, method="jpg")

    # parallel (floor back to default)
    monkeypatch.setattr(C, "_PARALLEL_MIN_PAGES", 8)
    par = C._render_pdf_as_images(data, dpi=100, method="jpg")

    assert fitz.open(stream=par, filetype="pdf").page_count == 12
    assert _page_hashes(par) == _page_hashes(seq)  # identical content, identical order


def test_parallel_uses_multiple_workers(monkeypatch):
    data = _make_pdf(12)
    monkeypatch.setattr(C.cpu, "worker_count", lambda: 4)
    monkeypatch.setattr(C, "_PARALLEL_MIN_PAGES", 8)

    seen = set()
    lock = threading.Lock()
    orig = C._render_one_page

    def spy(*args, **kwargs):
        with lock:
            seen.add(threading.current_thread().name)
        return orig(*args, **kwargs)

    monkeypatch.setattr(C, "_render_one_page", spy)
    C._render_pdf_as_images(data, dpi=100, method="jpg")

    pool_threads = [n for n in seen if "compress-pool" in n]
    assert len(pool_threads) >= 2  # genuinely spread across workers


def test_small_pdf_stays_sequential(monkeypatch):
    """Below the floor: rendered inline on the calling thread (no pool)."""
    data = _make_pdf(3)
    monkeypatch.setattr(C.cpu, "worker_count", lambda: 4)
    seen = set()
    orig = C._render_one_page

    def spy(*args, **kwargs):
        seen.add(threading.current_thread().name)
        return orig(*args, **kwargs)

    monkeypatch.setattr(C, "_render_one_page", spy)
    C._render_pdf_as_images(data, dpi=100, method="jpg")
    assert all("compress-pool" not in n for n in seen)  # never touched the pool
