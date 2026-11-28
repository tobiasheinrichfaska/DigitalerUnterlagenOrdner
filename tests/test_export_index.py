# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Tag index in the PDF export + the export-options toggles (TOC / index / bookmarks)."""

import fitz
import pikepdf

from formats.pdf_node import PDFNode
from formats.toc_export import _build_index_items, export_pdf


def _pdf(n=1):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=300, height=300).insert_text((40, 60), f"p{i}")
    b = d.tobytes()
    d.close()
    return b


def _leaf(name, tags=(), pages=1):
    n = PDFNode(name=name, pdf_data=_pdf(pages))
    n.tags = list(tags)
    n.pdf_length = pages
    return n


def _folder(name, children, tags=()):
    f = PDFNode(name=name, is_folder=True)
    f.tags = list(tags)
    for c in children:
        f.add_child(c)
    return f


def _index_map(items):
    """Flat index entries → {tag: [(name, page), …]} in order."""
    m, cur = {}, None
    for it in items:
        if it.is_header:
            cur = it.text
            m[cur] = []
        else:
            m[cur].append((it.text, it.page))
    return m


# --- index builder ----------------------------------------------------------

def test_index_groups_documents_by_tag_with_pages():
    a = _leaf("A", ["Steuer"], 2)          # pages 1-2
    b = _leaf("B", ["Steuer", "2024"], 1)  # page 3
    c = _leaf("C", [], 1)                   # page 4, no tags → not indexed
    m = _index_map(_build_index_items([a, b, c]))
    assert m == {"2024": [("B", 3)], "Steuer": [("A", 1), ("B", 3)]}  # tags alpha, entries in page order


def test_index_inherits_folder_tags():
    leaf = _leaf("Doc", [], 1)
    folder = _folder("Ordner", [leaf], tags=["Projekt"])
    assert _index_map(_build_index_items([folder])) == {"Projekt": [("Doc", 1)]}


def test_index_empty_without_tags():
    assert _build_index_items([_leaf("A", [], 1), _leaf("B", [], 1)]) == []


# --- export-options toggles -------------------------------------------------

def _pages(path):
    with pikepdf.open(path) as p:
        return len(p.pages)


def test_export_front_matter_toggles(tmp_path):
    nodes = [_leaf("A", ["Steuer"], 1), _leaf("B", [], 1)]  # 2 content pages, has a tag
    content_only = str(tmp_path / "none.pdf")
    toc_only = str(tmp_path / "toc.pdf")
    full = str(tmp_path / "full.pdf")
    export_pdf(nodes, content_only, {"toc": False, "index": False, "bookmarks": False})
    export_pdf(nodes, toc_only, {"toc": True, "index": False})
    export_pdf(nodes, full)  # toc + index + bookmarks
    assert _pages(content_only) == 2          # just the content
    assert _pages(toc_only) > _pages(content_only)   # TOC adds front matter
    assert _pages(full) > _pages(toc_only)           # index adds more


def test_export_index_skipped_when_no_tags(tmp_path):
    nodes = [_leaf("A", [], 1)]  # no tags → index auto-skipped even if requested
    with_idx = str(tmp_path / "a.pdf")
    no_idx = str(tmp_path / "b.pdf")
    export_pdf(nodes, with_idx, {"toc": True, "index": True})
    export_pdf(nodes, no_idx, {"toc": True, "index": False})
    assert _pages(with_idx) == _pages(no_idx)  # nothing to index → identical front matter


def test_export_bookmarks_toggle(tmp_path):
    nodes = [_leaf("A", [], 1)]
    bm = str(tmp_path / "bm.pdf")
    nobm = str(tmp_path / "nobm.pdf")
    export_pdf(nodes, bm, {"toc": True, "bookmarks": True})
    export_pdf(nodes, nobm, {"toc": True, "bookmarks": False})
    with pikepdf.open(bm) as p:
        assert len(list(p.open_outline().root)) > 0
    with pikepdf.open(nobm) as p:
        assert len(list(p.open_outline().root)) == 0


# --- audit regressions (EX-1, EX-3) -------------------------------------------

def test_export_only_empty_folder_no_toc_with_bookmarks_does_not_crash(tmp_path):
    """EX-1: zero content pages + toc off + bookmarks on used to raise
    'Accessing nonexistent PDF page number' (dest clamped to -1)."""
    out = tmp_path / "e.pdf"
    export_pdf([_folder("F001", [])], str(out), {"toc": False})
    with pikepdf.open(str(out)) as pdf:
        assert len(pdf.pages) == 0


def test_export_folder_with_only_zero_page_leaf_no_toc(tmp_path):
    out = tmp_path / "e.pdf"
    empty = PDFNode(name="L", pdf_data=b"")
    empty.pdf_length = 0
    export_pdf([_folder("F", [empty])], str(out),
               {"toc": False, "bookmarks": True})
    with pikepdf.open(str(out)) as pdf:
        assert len(pdf.pages) == 0


def test_index_tag_order_is_deterministic_for_case_variants():
    """EX-3: tags differing only by case must sort by (casefold, original)."""
    a = _build_index_items([_leaf("D", tags=["alpha", "Alpha", "ALPHA"])])
    b = _build_index_items([_leaf("D", tags=["ALPHA", "Alpha", "alpha"])])
    heads = lambda items: [i.text for i in items if i.is_header]
    assert heads(a) == heads(b) == ["ALPHA", "Alpha", "alpha"]


def test_index_tag_order_independent_of_hash_seed():
    import os, subprocess, sys
    code = ("from tests.test_export_index import _leaf\n"
            "from formats.toc_export import _build_index_items\n"
            "print([i.text for i in _build_index_items([_leaf('D', tags=['alpha','Alpha','ALPHA','Beta'])]) if i.is_header])")
    outs = set()
    for seed in ("0", "1", "2", "3", "4", "5"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                           cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        assert r.returncode == 0, r.stderr
        outs.add(r.stdout.strip())
    assert len(outs) == 1
