"""Regression: importing through the PDFStorage carrier must do no rendering.

The plain-PDF / archive import branches build PDFNode carriers that store bytes
only — the headless core renders on demand and node_from_pdfnode snapshots just
the bytes, so any eager render here is pure wasted work (it dominated import time
on large colour PDFs, ~100x overhead). These tests lock that: the import path
calls services.render zero times.
"""

import pytest

import services.render as render_mod
from helpers import create_valid_pdf
from formats.pdf_node import PDFNode


@pytest.fixture
def count_renders(monkeypatch):
    """Count render_pdf_to_images calls made *synchronously on the import thread*.

    Only main-thread renders count: a background daemon left running by another
    test must not poison this counter (the carrier import path never renders on
    any thread, sync or async — that is exactly what we assert)."""
    import threading
    main = threading.main_thread()
    calls = {"n": 0, "pages": 0}
    real = render_mod.render_pdf_to_images

    def counting(data, dpi=100):
        out = real(data, dpi=dpi)
        if threading.current_thread() is main:
            calls["n"] += 1
            calls["pages"] += len(out)
        return out

    monkeypatch.setattr(render_mod, "render_pdf_to_images", counting)
    return calls


def _write_plain_pdf(tmp_path, pages=3):
    """A real PDF with no embedded /JSONStructure → the plain-PDF import branch."""
    p = tmp_path / "plain.pdf"
    p.write_bytes(create_valid_pdf(pages=pages))
    return str(p)


def test_headless_import_renders_nothing(tmp_path, count_renders):
    from formats.pdf_storage import PDFStorage

    path = _write_plain_pdf(tmp_path, pages=3)
    storage = PDFStorage(path)

    # no page was rendered during the import
    assert count_renders["n"] == 0, f"unexpected renders: {count_renders}"

    node = storage.root.children[0]
    assert not node.is_compressed                  # no throwaway compression committed
    # bytes and page count still load correctly
    assert node.original_pdf_data
    assert node.pdf_length == 3


def test_headless_archive_import_renders_nothing(tmp_path, count_renders):
    """ZIP/email import stores bytes only — no eager render either."""
    import zipfile

    from formats.pdf_storage import PDFStorage

    zpath = tmp_path / "docs.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("a.pdf", create_valid_pdf(pages=2))
        z.writestr("b.pdf", create_valid_pdf(pages=1))

    storage = PDFStorage(str(zpath))

    assert count_renders["n"] == 0, f"archive import rendered: {count_renders}"

    leaves = []

    def walk(n):
        if n.is_folder:
            for c in n.children:
                walk(c)
        else:
            leaves.append(n)

    walk(storage.root)
    assert leaves, "no leaf nodes imported from the zip"
    for leaf in leaves:
        assert leaf.original_pdf_data               # bytes carried, no render

def test_structured_pdf_import_honors_json(tmp_path, count_renders):
    """The /JSONStructure byte-gate must NOT flatten structured imports.

    A saved .belegtool/PDF carries its tree in /JSONStructure (through pikepdf's
    compress+linearize). Re-import must restore the folders, and still render
    nothing.
    """
    from formats.pdf_storage import PDFStorage

    root = PDFNode(name="root", is_folder=True)
    folder = PDFNode(name="Ordner A", is_folder=True)
    folder.add_child(PDFNode(name="doc1", pdf_data=create_valid_pdf(pages=2)))
    folder.add_child(PDFNode(name="doc2", pdf_data=create_valid_pdf(pages=1)))
    root.add_child(folder)
    root.add_child(PDFNode(name="doc3", pdf_data=create_valid_pdf(pages=1)))

    st = PDFStorage()
    st.root = root
    path = str(tmp_path / "structured.belegtool")
    st.save(path)

    # marker must survive pikepdf for the byte-gate to fire
    assert b"/JSONStructure" in (tmp_path / "structured.belegtool").read_bytes()

    count_renders["n"] = 0  # ignore any renders from building the fixture above
    re = PDFStorage(path)

    assert count_renders["n"] == 0                       # no render
    names = [c.name for c in re.root.children]
    assert "Ordner A" in names and "doc3" in names       # structure honored, not flattened
    folder_back = next(c for c in re.root.children if c.is_folder)
    assert [c.name for c in folder_back.children] == ["doc1", "doc2"]
