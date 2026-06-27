"""#13 configurable export split — grouping engine (top-folder / any-folder levels).

Locks the previously-untested top-level boundary split and adds the any-folder level
(a large folder may be split across parts at child boundaries; a leaf is never split).
The page level is covered separately. Grouping is pure (page counts only); the actual
multi-file assembly is exercised lightly for validity.
"""
import pikepdf
import fitz

from formats.pdf_node import PDFNode
from formats.toc_export import (
    _split_at_boundaries, _pack_units, _plan_groups, count_node_pages,
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


def _folder(name, children):
    f = PDFNode(name=name, is_folder=True)
    for c in children:
        f.add_child(c)
    return f


def _names(groups):
    return [[n.name for n in g] for g in groups]


# ------------------------------------------------ pure packing (regression + new)
def test_pack_units_greedy_with_oversized_alone():
    units = [('a', 2), ('b', 2), ('c', 2)]
    assert _pack_units(units, 3) == [['a'], ['b'], ['c']]          # 2+2>3 each time
    assert _pack_units(units, 4) == [['a', 'b'], ['c']]            # 2+2=4 fits
    assert _pack_units([('big', 10), ('x', 1)], 3) == [['big'], ['x']]  # oversized alone


def test_split_at_boundaries_matches_top_level_packing():
    a, b, c = _leaf('a', 2), _leaf('b', 2), _leaf('c', 2)
    assert _names(_split_at_boundaries([a, b, c], 3)) == [['a'], ['b'], ['c']]
    assert _names(_split_at_boundaries([a, b, c], 4)) == [['a', 'b'], ['c']]


# --------------------------------------------------------------- top-folder level
def test_top_level_never_splits_a_folder():
    # F has 4 pages; at threshold 2 the TOP level keeps it whole (its own oversized part).
    f = _folder('F', [_leaf('l1'), _leaf('l2'), _leaf('l3'), _leaf('l4')])
    groups = _plan_groups([f, _leaf('x')], 2, 'top')
    assert _names(groups) == [['F'], ['x']]
    assert count_node_pages(groups[0][0]) == 4                     # whole folder in one part


# --------------------------------------------------------------- any-folder level
def test_any_folder_splits_a_large_folder_at_child_boundaries():
    f = _folder('F', [_leaf('l1'), _leaf('l2'), _leaf('l3'), _leaf('l4')])
    groups = _plan_groups([f], 2, 'folder')
    assert len(groups) == 2                                        # 4 leaves / 2 per part
    # each part rebuilds folder F holding its 2 leaves (a leaf is never split)
    for g in groups:
        assert len(g) == 1 and g[0].name == 'F' and g[0].is_folder
        assert [c.name for c in g[0].children] in (['l1', 'l2'], ['l3', 'l4'])


def test_any_folder_keeps_nested_paths():
    inner = _folder('inner', [_leaf('a'), _leaf('b')])
    outer = _folder('outer', [inner])
    groups = _plan_groups([outer], 1, 'folder')                   # 1 page per part → 2 parts
    assert len(groups) == 2
    for g in groups:
        assert g[0].name == 'outer' and g[0].children[0].name == 'inner'
        assert len(g[0].children[0].children) == 1                # one leaf per part


def test_any_folder_single_part_when_under_threshold():
    f = _folder('F', [_leaf('l1'), _leaf('l2')])
    groups = _plan_groups([f], 10, 'folder')
    assert len(groups) == 1 and _names(groups) == [['F']]


# ------------------------------------------------------------- mid-document level
def test_page_level_splits_a_leaf_across_parts():
    big = _leaf('big', 4)
    groups = _plan_groups([big], 3, 'page')                # 4 pages / 3 → 3 + 1
    assert len(groups) == 2
    assert count_node_pages(groups[0][0]) == 3
    assert count_node_pages(groups[1][0]) == 1
    # both parts reference the same source document (name carries the page range)
    assert groups[0][0].name.startswith('big') and groups[1][0].name.startswith('big')


def test_page_level_does_not_slice_a_leaf_that_fits():
    a, b = _leaf('a', 2), _leaf('b', 2)
    groups = _plan_groups([a, b], 2, 'page')
    assert len(groups) == 2
    assert groups[0][0] is a and groups[1][0] is b          # whole leaves, untouched


def test_page_level_keeps_folder_structure():
    f = _folder('F', [_leaf('l', 3)])
    groups = _plan_groups([f], 2, 'page')                   # 3 pages / 2 → 2 parts
    assert len(groups) == 2
    for g in groups:
        assert g[0].name == 'F' and g[0].is_folder and len(g[0].children) == 1


def test_page_level_export_produces_the_right_number_of_parts(tmp_path):
    from formats.toc_export import export_pdf_split_with_toc
    paths = export_pdf_split_with_toc([_leaf('big', 5)], str(tmp_path / 'out.pdf'), 2, 'page')
    assert len(paths) == 3                                  # 5 pages / 2 → 3 parts
    for p in paths:
        with pikepdf.open(p) as pdf:
            assert len(pdf.pages) >= 1


# --------------------------------------------------------------- multi-file export
def test_export_split_writes_valid_part_files(tmp_path):
    from formats.toc_export import export_pdf_split_with_toc
    nodes = [_leaf('a', 2), _leaf('b', 2), _leaf('c', 2)]
    paths = export_pdf_split_with_toc(nodes, str(tmp_path / 'out.pdf'), 3)
    assert len(paths) >= 2                                         # actually split
    for p in paths:
        with pikepdf.open(p) as pdf:
            assert len(pdf.pages) >= 1                             # each part is a valid PDF
