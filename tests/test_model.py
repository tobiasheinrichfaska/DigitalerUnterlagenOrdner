"""Unit tests for the immutable document model (core/model.py)."""

import dataclasses

import pytest

from core.model import (
    Document,
    Node,
    STATUS_DONE,
    STATUS_NONE,
    STATUS_TODO,
    find,
    insert_child,
    move_node,
    parent_of,
    path_to,
    remove_node,
    replace_node,
    update_node,
)


# --- helpers ---------------------------------------------------------------

def sample_tree() -> Node:
    #   root
    #   ├── a (leaf)
    #   └── f (folder)
    #       ├── b (leaf)
    #       └── c (leaf)
    a = Node(name="a", id="a")
    b = Node(name="b", id="b")
    c = Node(name="c", id="c")
    f = Node(name="f", id="f", is_folder=True, children=(b, c))
    return Node(name="root", id="root", is_folder=True, children=(a, f))


# --- Node basics -----------------------------------------------------------

def test_defaults_and_auto_id_unique():
    n1, n2 = Node(name="x"), Node(name="x")
    assert n1.status == STATUS_NONE and n1.is_folder is False  # new default: no status
    assert n1.id and n2.id and n1.id != n2.id  # auto-generated, unique


def test_node_is_immutable():
    n = Node(name="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        n.name = "y"  # type: ignore[misc]


def test_iter_is_preorder_and_find():
    root = sample_tree()
    assert [n.id for n in root.iter()] == ["root", "a", "f", "b", "c"]
    assert find(root, "c").name == "c"
    assert find(root, "missing") is None


# --- serialisation ---------------------------------------------------------

def test_to_dict_structure_and_positions():
    d = sample_tree().to_dict()
    assert d["id"] == "root" and d["position"] is None
    assert [c["position"] for c in d["children"]] == [0, 1]
    assert d["children"][1]["children"][0]["name"] == "b"


def test_to_dict_excludes_bytes():
    n = Node(name="x", original_data=b"%PDF", current_data=b"%PDF2")
    assert "original_data" not in n.to_dict()
    assert "current_data" not in n.to_dict()


def test_from_dict_roundtrip_preserves_structure_and_ids():
    root = sample_tree()
    back = Node.from_dict(root.to_dict())
    assert back.to_dict() == root.to_dict()
    assert [n.id for n in back.iter()] == ["root", "a", "f", "b", "c"]


def test_from_dict_generates_id_when_missing():
    n = Node.from_dict({"name": "x"})
    assert n.id  # generated
    assert n.status == STATUS_NONE and n.children == ()  # new default: no status


def test_document_roundtrip():
    doc = Document(sample_tree())
    assert Document.from_dict(doc.to_dict()).to_dict() == doc.to_dict()


# --- queries ---------------------------------------------------------------

def test_parent_of_and_path_to():
    root = sample_tree()
    assert parent_of(root, "b").id == "f"
    assert parent_of(root, "root") is None
    assert [n.id for n in path_to(root, "b")] == ["root", "f", "b"]
    assert path_to(root, "missing") is None


# --- transforms: purity + structural sharing -------------------------------

def test_update_node_changes_target_and_shares_unchanged():
    root = sample_tree()
    new = update_node(root, "b", name="B!", status=STATUS_DONE)
    assert root.find("b").name == "b"          # original untouched (immutable)
    assert new.find("b").name == "B!" and new.find("b").status == STATUS_DONE
    # sibling subtree 'a' is the *same object* (structural sharing)
    assert new.children[0] is root.children[0]


def test_update_node_noop_returns_same_object():
    root = sample_tree()
    assert update_node(root, "missing", name="x") is root


def test_replace_node_swaps_subtree():
    root = sample_tree()
    new = replace_node(root, "f", Node(name="F", id="f2"))
    assert [n.id for n in new.iter()] == ["root", "a", "f2"]


def test_remove_node():
    root = sample_tree()
    new = remove_node(root, "b")
    assert find(new, "b") is None
    assert [n.id for n in new.find("f").children] == ["c"]
    assert new.children[0] is root.children[0]  # 'a' shared


def test_remove_root_raises():
    with pytest.raises(ValueError):
        remove_node(sample_tree(), "root")


def test_insert_child_append_and_index_and_clamp():
    root = sample_tree()
    x = Node(name="x", id="x")
    assert [n.id for n in insert_child(root, "f", x).find("f").children] == ["b", "c", "x"]
    assert [n.id for n in insert_child(root, "f", x, 0).find("f").children] == ["x", "b", "c"]
    assert [n.id for n in insert_child(root, "f", x, 99).find("f").children] == ["b", "c", "x"]


def test_move_node_relocates_subtree():
    root = sample_tree()
    new = move_node(root, "f", "root", 0)  # move folder f to front under root
    assert [c.id for c in new.children] == ["f", "a"]
    assert [n.id for n in new.find("f").children] == ["b", "c"]  # subtree intact


def test_move_into_own_subtree_raises():
    with pytest.raises(ValueError):
        move_node(sample_tree(), "f", "b")  # f into its own child


def test_move_missing_raises():
    with pytest.raises(KeyError):
        move_node(sample_tree(), "missing", "root")
