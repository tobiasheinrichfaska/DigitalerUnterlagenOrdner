"""Unit tests for the structural command reducer (core/commands.py)."""

import pytest

from core.model import Document, Node, STATUS_DONE
from core.commands import (
    AddFolder,
    CommandError,
    Delete,
    Move,
    Rename,
    SetPeriod,
    SetStatus,
    apply,
    apply_all,
    command_from_dict,
    command_to_dict,
)


def doc() -> Document:
    a = Node(name="a", id="a")
    b = Node(name="b", id="b")
    f = Node(name="f", id="f", is_folder=True, children=(b,))
    return Document(Node(name="root", id="root", is_folder=True, children=(a, f)))


# --- AddFolder -------------------------------------------------------------

def test_add_folder_appends_and_is_pure():
    d0 = doc()
    d1 = apply(d0, AddFolder(parent_id="f", name="New", new_id="n"))
    assert [c.id for c in d1.find("f").children] == ["b", "n"]
    assert d1.find("n").is_folder is True and d1.find("n").name == "New"
    # original document is untouched (immutability)
    assert d0.find("n") is None


def test_add_folder_at_index():
    d1 = apply(doc(), AddFolder(parent_id="root", name="X", new_id="x", index=0))
    assert [c.id for c in d1.root.children] == ["x", "a", "f"]


def test_add_folder_into_leaf_or_missing_raises():
    with pytest.raises(CommandError):
        apply(doc(), AddFolder(parent_id="a"))      # 'a' is a leaf
    with pytest.raises(CommandError):
        apply(doc(), AddFolder(parent_id="nope"))   # missing


# --- Rename ----------------------------------------------------------------

def test_rename():
    d1 = apply(doc(), Rename(node_id="b", name="B!"))
    assert d1.find("b").name == "B!"


def test_rename_empty_or_missing_raises():
    with pytest.raises(CommandError):
        apply(doc(), Rename(node_id="b", name=""))
    with pytest.raises(CommandError):
        apply(doc(), Rename(node_id="nope", name="x"))


# --- SetStatus -------------------------------------------------------------

def test_set_status_valid():
    assert apply(doc(), SetStatus("a", STATUS_DONE)).find("a").status == STATUS_DONE


def test_set_status_invalid_raises():
    with pytest.raises(CommandError):
        apply(doc(), SetStatus("a", "bogus"))


# --- SetPeriod -------------------------------------------------------------

def test_set_period():
    d1 = apply(doc(), SetPeriod("a", vz_start=2023, vz_end=2024))
    assert d1.find("a").vz_start == 2023 and d1.find("a").vz_end == 2024


# --- Delete ----------------------------------------------------------------

def test_delete_removes_node():
    d1 = apply(doc(), Delete("b"))
    assert d1.find("b") is None
    assert d1.find("f").children == ()


def test_delete_root_or_missing_raises():
    with pytest.raises(CommandError):
        apply(doc(), Delete("root"))
    with pytest.raises(CommandError):
        apply(doc(), Delete("nope"))


# --- Move ------------------------------------------------------------------

def test_move_relocates():
    d1 = apply(doc(), Move(node_id="a", new_parent_id="f", index=0))
    assert [c.id for c in d1.find("f").children] == ["a", "b"]
    assert "a" not in [c.id for c in d1.root.children]


def test_move_reorder_same_parent_index_is_post_removal():
    # Move's index is interpreted in the list AFTER the source is removed (the UI
    # accounts for this off-by-one when reordering within a parent to a later slot).
    x0, x1, x2 = (Node(name=n, id=n) for n in ("x0", "x1", "x2"))
    d = Document(Node(name="root", id="root", is_folder=True, children=(x0, x1, x2)))
    # remove x0 → [x1, x2]; insert at index 1 → between x1 and x2
    d1 = apply(d, Move("x0", "root", index=1))
    assert [c.id for c in d1.root.children] == ["x1", "x0", "x2"]


def test_move_into_non_folder_or_subtree_or_root_raises():
    with pytest.raises(CommandError):
        apply(doc(), Move("b", "a"))         # 'a' is a leaf
    with pytest.raises(CommandError):
        apply(doc(), Move("f", "b"))         # into own subtree
    with pytest.raises(CommandError):
        apply(doc(), Move("root", "f"))      # cannot move root
    with pytest.raises(CommandError):
        apply(doc(), Move("nope", "f"))      # missing


# --- reducer plumbing ------------------------------------------------------

def test_apply_all_folds_commands():
    d1 = apply_all(doc(), [
        AddFolder(parent_id="root", name="G", new_id="g"),
        Move(node_id="a", new_parent_id="g"),
        Rename(node_id="g", name="Group"),
    ])
    assert d1.find("g").name == "Group"
    assert [c.id for c in d1.find("g").children] == ["a"]


def test_unknown_command_raises():
    class Bogus:
        pass
    with pytest.raises(CommandError):
        apply(doc(), Bogus())


# --- command serialisation -------------------------------------------------

@pytest.mark.parametrize("cmd", [
    AddFolder(parent_id="f", name="X", index=1, new_id="x"),
    Rename(node_id="b", name="B"),
    SetStatus(node_id="a", status=STATUS_DONE),
    SetPeriod(node_id="a", vz_start=2023, vz_end=None),
    Delete(node_id="b"),
    Move(node_id="a", new_parent_id="f", index=0),
])
def test_command_serialisation_roundtrip(cmd):
    assert command_from_dict(command_to_dict(cmd)) == cmd


def test_command_from_dict_unknown_type_raises():
    with pytest.raises(CommandError):
        command_from_dict({"type": "Nope"})
