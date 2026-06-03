"""Folder `collapsed` is a persisted Node field, set via SetCollapsed/SetAllCollapsed."""

import pytest

from helpers import create_valid_pdf
from core.model import Document, Node
from core.commands import SetCollapsed, SetAllCollapsed, CommandError, apply
from core.bridge import save_belegtool, load_belegtool


def _doc():
    f = Node(name="F", is_folder=True, children=(
        Node(name="sub", is_folder=True, children=()),
        Node(name="leaf", is_folder=False, original_data=create_valid_pdf(1), pdf_length=1),
    ))
    return Document(Node(name="root", is_folder=True, children=(f,)))


def test_set_collapsed_toggles_folder():
    doc = _doc()
    fid = doc.root.children[0].id
    doc = apply(doc, SetCollapsed(node_id=fid, collapsed=True))
    assert doc.find(fid).collapsed is True
    doc = apply(doc, SetCollapsed(node_id=fid, collapsed=False))
    assert doc.find(fid).collapsed is False


def test_set_collapsed_rejects_leaf():
    doc = _doc()
    leaf = doc.root.children[0].children[1].id
    with pytest.raises(CommandError):
        apply(doc, SetCollapsed(node_id=leaf, collapsed=True))


def test_set_all_collapsed():
    doc = _doc()
    doc2 = apply(doc, SetAllCollapsed(collapsed=True))
    folders = [n for n in doc2.root.iter() if n.is_folder and n is not doc2.root]
    assert folders and all(f.collapsed for f in folders)
    doc3 = apply(doc2, SetAllCollapsed(collapsed=False))
    assert all(not f.collapsed for f in doc3.root.iter() if f.is_folder)


def test_collapsed_persists_round_trip(tmp_path):
    doc = _doc()
    fid = doc.root.children[0].id
    doc = apply(doc, SetCollapsed(node_id=fid, collapsed=True))
    path = str(tmp_path / "c.belegtool")
    save_belegtool(doc, path)
    reloaded = load_belegtool(path)
    f = next(n for n in reloaded.root.children if n.name == "F")
    assert f.collapsed is True
