"""DeleteMany: delete several nodes in one step, with parent/child de-duplication."""

import pytest

from core.model import Document, Node
from core.commands import CommandError, DeleteMany, apply, command_from_dict, command_to_dict


def _doc():
    # root
    #   f (folder)
    #     c1, c2
    #   a, b  (leaves)
    f = Node(name="f", id="f", is_folder=True, children=(
        Node(name="c1", id="c1", original_data=b"1"),
        Node(name="c2", id="c2", original_data=b"2"),
    ))
    a = Node(name="a", id="a", original_data=b"A")
    b = Node(name="b", id="b", original_data=b"B")
    return Document(Node(name="root", id="root", is_folder=True, children=(f, a, b)))


def test_delete_many_independent_leaves():
    d = apply(_doc(), DeleteMany(("a", "b")))
    assert [n.id for n in d.root.children] == ["f"]


def test_delete_many_rejects_mixed_parent_and_child():
    # a folder AND an item inside it → rejected (the UI must resolve it first)
    with pytest.raises(CommandError):
        apply(_doc(), DeleteMany(("f", "c1")))


def test_delete_many_children_only_keeps_parent():
    # the "keep parent, delete selected children" case (frontend excludes the parent)
    d = apply(_doc(), DeleteMany(("c1",)))
    assert d.find("f") is not None and d.find("c1") is None and d.find("c2") is not None


def test_delete_many_ignores_missing_and_root():
    d = apply(_doc(), DeleteMany(("a", "nope", "root")))
    assert [n.id for n in d.root.children] == ["f", "b"]  # only 'a' removed


def test_delete_many_serialisation_roundtrip():
    back = command_from_dict(command_to_dict(DeleteMany(("a", "b"))))
    assert back == DeleteMany(("a", "b")) and isinstance(back.node_ids, tuple)
