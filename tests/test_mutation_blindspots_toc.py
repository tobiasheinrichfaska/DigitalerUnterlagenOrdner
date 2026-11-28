# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Mutation blind spots in formats/toc_export.py page-numbering helpers (MU-15..MU-20)."""

import os

import fitz
import pikepdf

from formats.pdf_node import PDFNode
from formats.toc_export import (
    _build_toc_items, _part_paths, empty_leaf_names, export_pdf, export_pdf_split_with_toc,
)


def _pdf(n=1):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=300, height=300).insert_text((40, 60), f"p{i}")
    b = d.tobytes()
    d.close()
    return b


def _leaf(name, pages=1):
    n = PDFNode(name=name, pdf_data=_pdf(pages))
    n.pdf_length = pages
    return n


def _empty_leaf(name):
    return PDFNode(name=name)          # no data, no pages


def _folder(name, children=()):
    f = PDFNode(name=name, is_folder=True)
    for c in children:
        f.add_child(c)
    return f


# MU-15  toc_export.py:97/98  empty_leaf_names reports exactly the page-less LEAVES
def test_empty_leaf_names_lists_only_pageless_leaves_recursively():
    forest = [_leaf("A", 2), _empty_leaf("E1"), _folder("F", [_empty_leaf("E2"), _leaf("B", 1)]),
              _folder("EmptyFolder")]
    assert empty_leaf_names(forest) == ["E1", "E2"]       # folders are never "empty leaves"
    assert empty_leaf_names([_leaf("A", 1)]) == []
    assert empty_leaf_names([]) == []


# MU-16  toc_export.py:117/118  TOC items: empty leaves are skipped, page ranges are exact
def test_build_toc_items_numbers_pages_and_skips_empty_leaves():
    forest = [_leaf("A", 2), _empty_leaf("E"), _folder("F", [_leaf("B", 3), _leaf("C", 1)])]
    items = [(i.depth, i.name, i.page_start, i.page_end, i.is_folder)
             for i in _build_toc_items(forest)]
    assert items == [
        (0, "A", 1, 2, False),
        (0, "F", 3, 3, True),        # a folder points at the first page that follows it
        (1, "B", 3, 5, False),
        (1, "C", 6, 6, False),
    ]


# MU-17  toc_export.py:737  part naming: one part keeps the base path, n>1 gets _Teil_i
def test_part_paths_single_and_multi():
    assert _part_paths("out.pdf", 1) == ["out.pdf"]
    assert _part_paths("out.pdf", 0) == ["out.pdf"]
    assert _part_paths(os.path.join("d", "out.pdf"), 3) == [
        os.path.join("d", f"out_Teil_{i}.pdf") for i in (1, 2, 3)]
    assert _part_paths("noext", 2) == ["noext_Teil_1.pdf", "noext_Teil_2.pdf"]


# MU-18  toc_export.py:565/769/770/766  single-group + empty branches of the split export
def test_split_export_with_one_group_writes_a_single_file_and_returns_its_path(tmp_path):
    base = str(tmp_path / "all.pdf")
    paths = export_pdf_split_with_toc([_leaf("A", 2), _leaf("B", 1)], base, max_pages=100)
    assert paths == [base]
    assert os.path.exists(base)
    assert not os.path.exists(str(tmp_path / "all_Teil_1.pdf"))
    with pikepdf.open(base) as pdf:
        assert len(pdf.pages) == 1 + 3            # one TOC page + 3 content pages


def test_split_export_of_an_empty_forest_writes_nothing(tmp_path):
    base = str(tmp_path / "none.pdf")
    assert export_pdf_split_with_toc([], base, max_pages=10) == []
    assert not os.path.exists(base)


# MU-19  toc_export.py:469  bookmark of a folder without any document points at the first content page
def test_bookmark_for_a_folder_without_documents_points_at_first_content_page(tmp_path):
    out = str(tmp_path / "bm.pdf")
    export_pdf([_folder("Leer"), _leaf("A", 2)], out,
               {"toc": True, "bookmarks": True, "index": False})
    with pikepdf.open(out) as pdf:
        with pdf.open_outline() as outline:
            titles = [o.title for o in outline.root]
            assert titles == ["Leer", "A"]
            dest_pages = [[p.objgen for p in pdf.pages].index(o.destination[0].objgen)
                          for o in outline.root]
        # 1 TOC page in front: "Leer" and "A" both land on content page 0 (= page index 1)
        assert dest_pages == [1, 1]


# MU-20  toc_export.py:244/378/381/385  printed-TOC content stream: black text, dotted grey
#        leader that ends 6 pt before the right-aligned page number
def test_toc_page_uses_black_text_and_a_dotted_leader_before_the_page_number():
    import io
    import re
    from formats.toc_export import _render_toc_pdf
    items = _build_toc_items([_folder("Ordner", [_leaf("Doc", 2)])])
    toc_bytes, _recs = _render_toc_pdf(items, toc_offset=1)
    with pikepdf.open(io.BytesIO(toc_bytes)) as pdf:
        stream = pdf.pages[0].Contents.read_bytes().decode("latin-1")
    assert set(re.findall(r"^(\S+ \S+ \S+) rg$", stream, re.M)) == {"0 0 0"}   # never coloured text
    assert "[1 3] 0 d" in stream and ".4 w" in stream and ".65 .65 .65 RG" in stream
    assert "[] 0 d" in stream and "0 0 0 RG" in stream                          # state is reset after
    leader = re.search(r"n ([\d.]+) ([\d.]+) m ([\d.]+) ([\d.]+) l S\n\[\] 0 d", stream)
    assert leader and leader.group(2) == leader.group(4)                      # horizontal line
    page_x = float(re.search(r"1 0 0 1 ([\d.]+) [\d.]+ Tm \(S\. 2\)", stream).group(1))
    assert abs(float(leader.group(3)) - (page_x - 6)) < 0.01                   # ends 6 pt before "S. 2"
    assert float(leader.group(1)) > 72                                         # starts after the name


# MU-20b  toc_export.py:378/381/385 (_render_index_pdf)  the tag-index page has the same leader contract
def test_tag_index_page_uses_a_dotted_leader_ending_6pt_before_the_page_number():
    import io
    import re
    from formats.toc_export import _build_index_items, _render_index_pdf
    doc = _leaf("Doc", 1)
    doc.tags = ["Steuer"]
    idx_bytes, _recs = _render_index_pdf(_build_index_items([doc]), toc_offset=1)
    with pikepdf.open(io.BytesIO(idx_bytes)) as pdf:
        stream = pdf.pages[0].Contents.read_bytes().decode("latin-1")
    assert set(re.findall(r"^(\S+ \S+ \S+) rg$", stream, re.M)) == {"0 0 0"}
    assert "[1 3] 0 d" in stream and ".4 w" in stream and ".65 .65 .65 RG" in stream
    assert "[] 0 d" in stream and "0 0 0 RG" in stream
    leader = re.search(r"n ([\d.]+) ([\d.]+) m ([\d.]+) ([\d.]+) l S\n\[\] 0 d", stream)
    assert leader and leader.group(2) == leader.group(4)
    page_x = float(re.search(r"1 0 0 1 ([\d.]+) [\d.]+ Tm \(S\. 2\)", stream).group(1))
    assert abs(float(leader.group(3)) - (page_x - 6)) < 0.01
    assert float(leader.group(1)) > 72
