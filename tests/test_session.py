"""Unit tests for the editing session (core/session.py)."""

from core.model import Document, Node
from core.commands import (
    AddFolder,
    Compress,
    Move,
    Rename,
    apply_all,
)
from core.session import DocumentSession


class _NoGainEngine:
    def compress(self, b, dpi):
        return None  # never beats the original


def doc() -> Document:
    a = Node(name="a", id="a", original_data=b"DATA-LONG-ENOUGH")
    f = Node(name="f", id="f", is_folder=True)
    return Document(Node(name="root", id="root", is_folder=True, children=(a, f)))


def test_initial_state():
    s = DocumentSession(doc())
    assert s.document is s.initial
    assert not s.can_undo() and not s.can_redo()
    assert s.log == []


def test_dispatch_changes_document_and_records():
    s = DocumentSession(doc())
    s.dispatch(Rename("a", "A!"))
    assert s.document.find("a").name == "A!"
    assert s.can_undo() and not s.can_redo()
    assert s.log == [Rename("a", "A!")]


def test_undo_and_redo():
    s = DocumentSession(doc())
    s.dispatch(Rename("a", "A!"))
    s.undo()
    assert s.document.find("a").name == "a"
    assert not s.can_undo() and s.can_redo()
    s.redo()
    assert s.document.find("a").name == "A!"
    assert s.can_undo() and not s.can_redo()


def test_new_dispatch_clears_redo():
    s = DocumentSession(doc())
    s.dispatch(Rename("a", "A1"))
    s.undo()
    s.dispatch(Rename("a", "A2"))
    assert not s.can_redo()
    assert s.document.find("a").name == "A2"


def test_noop_command_is_not_recorded():
    s = DocumentSession(doc(), engine=_NoGainEngine())
    before = s.document
    s.dispatch(Compress("a"))  # engine returns None → no change
    assert s.document is before
    assert not s.can_undo()
    assert s.log == []


def test_undo_redo_when_empty_is_safe():
    s = DocumentSession(doc())
    assert s.undo() is s.document  # nothing to undo
    assert s.redo() is s.document  # nothing to redo


def test_replay_invariant_holds_through_undo_redo():
    s = DocumentSession(doc())
    s.dispatch(AddFolder(parent_id="root", name="G", new_id="g"))
    s.dispatch(Move("a", "g"))
    s.dispatch(Rename("g", "Group"))
    s.undo()                      # drop the rename
    s.dispatch(Rename("a", "AA"))  # diverge
    # the event log replays from the initial document to the current state
    replayed = apply_all(s.initial, s.log)
    assert replayed.to_dict() == s.document.to_dict()
    assert [type(c).__name__ for c in s.log] == ["AddFolder", "Move", "Rename"]
