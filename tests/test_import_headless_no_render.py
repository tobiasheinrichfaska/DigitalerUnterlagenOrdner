"""Regression: headless import of a plain PDF must do no rendering/compression.

The plain-PDF import branch in PDFStorage._load_pdf used to ignore
generate_previews=False — it built the node via the eager PDFNode constructor
(full-document PIL render) and fired two background compressions. In the core /
React path node_from_pdfnode snapshots only the bytes, so all of that work was
discarded; on large color PDFs it dominated import time (~100x overhead).

These tests lock the fix: generate_previews=False stores bytes only.
"""

import pytest

import pdf_node
import services.render as render_mod
from helpers import create_valid_pdf
from pdf_node import PDFNode


@pytest.fixture
def count_renders(monkeypatch):
    """Count render_pdf_to_images calls made *synchronously on the import thread*.

    Only main-thread renders count: a background compression daemon left running
    by another test must not poison this counter (the headless import path never
    renders on any thread, sync or async — that is exactly what we assert)."""
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

    # patch both the source module and the name imported into pdf_node
    monkeypatch.setattr(render_mod, "render_pdf_to_images", counting)
    monkeypatch.setattr(pdf_node, "render_pdf_to_images", counting)
    return calls


def _write_plain_pdf(tmp_path, pages=3):
    """A real PDF with no embedded /JSONStructure → the plain-PDF import branch."""
    p = tmp_path / "plain.pdf"
    p.write_bytes(create_valid_pdf(pages=pages))
    return str(p)


def test_headless_import_renders_nothing(tmp_path, count_renders):
    from pdf_storage import PDFStorage

    path = _write_plain_pdf(tmp_path, pages=3)
    storage = PDFStorage(path, generate_previews=False)

    # no page was rendered during the headless import
    assert count_renders["n"] == 0, f"unexpected renders: {count_renders}"

    node = storage.root.children[0]
    assert node._original_preview_pages == []      # no eager preview kept
    assert node._current_preview_pages == []
    assert not node.is_compressed                  # no throwaway compression committed
    assert not node._compression_task_running      # no background compression spawned
    # bytes and page count still load correctly
    assert node.original_pdf_data
    assert node.pdf_length == 3


def test_headless_archive_import_renders_nothing(tmp_path, count_renders):
    """ZIP/email import must also honor generate_previews=False (E)."""
    import zipfile

    from pdf_storage import PDFStorage

    zpath = tmp_path / "docs.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("a.pdf", create_valid_pdf(pages=2))
        z.writestr("b.pdf", create_valid_pdf(pages=1))

    storage = PDFStorage(str(zpath), generate_previews=False)

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
        assert leaf._original_preview_pages == []   # bytes only, no eager render
        assert leaf.original_pdf_data


def test_structured_pdf_import_honors_json(tmp_path, count_renders):
    """The /JSONStructure byte-gate must NOT flatten structured imports.

    A saved .belegtool/PDF carries its tree in /JSONStructure (through pikepdf's
    compress+linearize). Re-import must restore the folders, and still render
    nothing in headless mode.
    """
    from pdf_storage import PDFStorage

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
    re = PDFStorage(path, generate_previews=False)

    assert count_renders["n"] == 0                       # headless: no render
    names = [c.name for c in re.root.children]
    assert "Ordner A" in names and "doc3" in names       # structure honored, not flattened
    folder_back = next(c for c in re.root.children if c.is_folder)
    assert [c.name for c in folder_back.children] == ["doc1", "doc2"]


def test_tk_import_still_renders(tmp_path, count_renders):
    """The legacy Tk path (generate_previews=True) must keep eager previews."""
    from pdf_storage import PDFStorage

    path = _write_plain_pdf(tmp_path, pages=2)
    storage = PDFStorage(path, generate_previews=True)

    assert count_renders["n"] >= 1                 # eager render happened
    node = storage.root.children[0]
    assert node._original_preview_pages            # previews kept for the canvas
