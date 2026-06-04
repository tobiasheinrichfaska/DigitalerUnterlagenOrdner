"""Unit tests for the structural command reducer (core/commands.py)."""

import pytest

from core.model import Document, Node, STATUS_DONE
from core.commands import (
    AddFolder,
    CommandError,
    Delete,
    GroupIntoFolder,
    InsertNodes,
    Move,
    MoveMany,
    Rename,
    SetPeriod,
    SetStatus,
    SetTags,
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


# --- MoveMany --------------------------------------------------------------

def test_move_many_into_folder_preserves_order():
    d = apply(doc(), MoveMany(node_ids=["a", "b"], new_parent_id="f"))
    assert [c.id for c in d.find("f").children] == ["a", "b"]
    assert [c.id for c in d.root.children] == ["f"]


def test_move_many_skips_nested_member():
    # select a folder and a node inside it → only the folder moves (child rides along)
    d0 = apply(doc(), AddFolder(parent_id="root", name="g", new_id="g"))
    d = apply(d0, MoveMany(node_ids=["f", "b"], new_parent_id="g"))
    assert [c.id for c in d.find("g").children] == ["f"]            # only f moved
    assert [c.id for c in d.find("f").children] == ["b"]            # b still inside f


def test_move_many_into_own_subtree_raises():
    with pytest.raises(CommandError):
        apply(doc(), MoveMany(node_ids=["f"], new_parent_id="f"))


def test_move_many_honours_drop_index():
    # index is the pre-removal drop position; moved-out siblings before it are discounted
    kids = tuple(Node(name=n, id=n) for n in ("x0", "x1", "x2", "x3"))
    d = Document(Node(name="root", id="root", is_folder=True, children=kids))
    d1 = apply(d, MoveMany(node_ids=["x0", "x2"], new_parent_id="root", index=3))
    assert [c.id for c in d1.root.children] == ["x1", "x0", "x2", "x3"]


# --- GroupIntoFolder -------------------------------------------------------

def test_group_into_folder_moves_all_in_order():
    d = apply(doc(), GroupIntoFolder(node_ids=["a", "b"], parent_id="root", name="G", new_id="grp"))
    g = d.find("grp")
    assert g.is_folder and g.name == "G"
    assert [c.id for c in g.children] == ["a", "b"]
    root_ids = [c.id for c in d.root.children]
    assert "grp" in root_ids and "a" not in root_ids and "f" in root_ids
    assert "b" not in [c.id for c in d.find("f").children]  # pulled out of f


def test_group_into_non_folder_or_empty_raises():
    with pytest.raises(CommandError):
        apply(doc(), GroupIntoFolder(node_ids=["a"], parent_id="a"))   # 'a' is a leaf
    with pytest.raises(CommandError):
        apply(doc(), GroupIntoFolder(node_ids=[], parent_id="root"))   # nothing to group


# --- InsertNodes -----------------------------------------------------------

def test_insert_nodes_under_folder_and_at_index():
    d = apply(doc(), InsertNodes(parent_id="f", nodes=(Node(name="n1", id="n1"), Node(name="n2", id="n2"))))
    assert [c.id for c in d.find("f").children] == ["b", "n1", "n2"]
    d2 = apply(doc(), InsertNodes(parent_id="root", nodes=(Node(name="x", id="x"),), index=0))
    assert [c.id for c in d2.root.children][0] == "x"


def test_insert_nodes_into_non_folder_raises():
    with pytest.raises(CommandError):
        apply(doc(), InsertNodes(parent_id="a", nodes=(Node(name="y"),)))  # 'a' is a leaf


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


# --- SetTags ---------------------------------------------------------------

def test_set_tags_on_leaf_and_folder():
    d1 = apply(doc(), SetTags(node_id="a", tags=("Steuer", "2023")))
    assert d1.find("a").tags == ("Steuer", "2023")
    d2 = apply(d1, SetTags(node_id="f", tags=("Belege",)))      # folders too
    assert d2.find("f").tags == ("Belege",)
    assert d2.find("a").tags == ("Steuer", "2023")             # unchanged


def test_set_tags_normalises_trim_dedup_empty():
    d1 = apply(doc(), SetTags(node_id="a", tags=("  Steuer ", "", "Steuer", "  ", "2023")))
    assert d1.find("a").tags == ("Steuer", "2023")             # trimmed, deduped, empties dropped


def test_set_tags_replaces_and_can_clear():
    d1 = apply(doc(), SetTags(node_id="a", tags=("x", "y")))
    d2 = apply(d1, SetTags(node_id="a", tags=()))              # clear
    assert d2.find("a").tags == ()


def test_set_tags_missing_node_raises():
    with pytest.raises(CommandError):
        apply(doc(), SetTags(node_id="nope", tags=("x",)))


# --- command serialisation -------------------------------------------------

@pytest.mark.parametrize("cmd", [
    AddFolder(parent_id="f", name="X", index=1, new_id="x"),
    Rename(node_id="b", name="B"),
    SetStatus(node_id="a", status=STATUS_DONE),
    SetPeriod(node_id="a", vz_start=2023, vz_end=None),
    SetTags(node_id="a", tags=("Steuer", "2023")),
    Delete(node_id="b"),
    Move(node_id="a", new_parent_id="f", index=0),
    MoveMany(node_ids=("a", "b"), new_parent_id="f", index=1),
    GroupIntoFolder(node_ids=("a", "b"), parent_id="root", name="G", new_id="g"),
])
def test_command_serialisation_roundtrip(cmd):
    assert command_from_dict(command_to_dict(cmd)) == cmd


def test_command_from_dict_unknown_type_raises():
    with pytest.raises(CommandError):
        command_from_dict({"type": "Nope"})
