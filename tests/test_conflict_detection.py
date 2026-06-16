import pytest
from formats.pdf_node import PDFNode
from formats.pdf_storage import PDFStorage
from helpers import create_valid_pdf


def make_tree():
    """Build: root -> folder -> [child1, child2]"""
    root = PDFNode("root", is_folder=True)
    folder = PDFNode("folder", is_folder=True)
    child1 = PDFNode("child1", pdf_data=create_valid_pdf(pages=1))
    child2 = PDFNode("child2", pdf_data=create_valid_pdf(pages=1))
    root.add_child(folder)
    folder.add_child(child1)
    folder.add_child(child2)
    return root, folder, child1, child2


# --- has_parent_child_conflict ---

def test_no_conflict_siblings():
    _, _, child1, child2 = make_tree()
    assert not PDFStorage.has_parent_child_conflict([child1, child2])


def test_conflict_parent_and_child():
    _, folder, child1, _ = make_tree()
    assert PDFStorage.has_parent_child_conflict([folder, child1])


def test_no_conflict_single_node():
    _, folder, _, _ = make_tree()
    assert not PDFStorage.has_parent_child_conflict([folder])


def test_conflict_grandparent_and_grandchild():
    root, _, child1, _ = make_tree()
    assert PDFStorage.has_parent_child_conflict([root, child1])


# --- filter_keep_ancestors ---

def test_filter_ancestors_removes_descendant():
    _, folder, child1, child2 = make_tree()
    result = PDFStorage.filter_keep_ancestors([folder, child1, child2])
    assert result == [folder]


def test_filter_ancestors_keeps_all_when_no_conflict():
    _, _, child1, child2 = make_tree()
    result = PDFStorage.filter_keep_ancestors([child1, child2])
    assert set(result) == {child1, child2}


def test_filter_ancestors_single_node():
    _, folder, _, _ = make_tree()
    result = PDFStorage.filter_keep_ancestors([folder])
    assert result == [folder]


# --- filter_keep_descendants ---

def test_filter_descendants_removes_ancestor():
    _, folder, child1, child2 = make_tree()
    result = PDFStorage.filter_keep_descendants([folder, child1, child2])
    assert set(result) == {child1, child2}


def test_filter_descendants_keeps_all_siblings():
    _, _, child1, child2 = make_tree()
    result = PDFStorage.filter_keep_descendants([child1, child2])
    assert set(result) == {child1, child2}


def test_filter_descendants_single_node():
    _, _, child1, _ = make_tree()
    result = PDFStorage.filter_keep_descendants([child1])
    assert result == [child1]


# --- multi-level skip (intermediate node NOT selected): root + grandchild only,
#     folder excluded. Locks the O(n*depth) ancestor-walk across an unselected level.
def test_filter_descendants_drops_grandancestor_skipping_unselected_level():
    root, _, child1, _ = make_tree()
    result = PDFStorage.filter_keep_descendants([root, child1])
    assert result == [child1]  # root dropped (has a selected descendant 2 levels down)


def test_filter_ancestors_keeps_grandancestor_skipping_unselected_level():
    root, _, child1, _ = make_tree()
    result = PDFStorage.filter_keep_ancestors([root, child1])
    assert result == [root]  # child1 dropped (a selected ancestor 2 levels up)
