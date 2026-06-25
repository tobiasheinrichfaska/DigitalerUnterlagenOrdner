"""Unit tests for the editing session (core/session.py)."""

from core.model import Document, Node
from core.commands import (
    AddFolder,
    Compress,
    Move,
    Rename,
    apply_all,
    command_from_dict,
)
from core.session import DocumentSession


def _set_no_gain(*ids):
    return command_from_dict({"type": "SetNoGain", "node_ids": list(ids)})


class _NoGainEngine:
    def compress(self, b, dpi, method=None):
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


# --- apply_silent: the derived no-gain verdict, applied WITHOUT undo/dirty ---

def test_apply_silent_updates_doc_without_undo_or_dirty():
    s = DocumentSession(doc())
    s.apply_silent(_set_no_gain("a"))
    assert s.document.find("a").compression_no_gain is True
    assert not s.can_undo()          # not a human edit → no undo entry
    assert not s.dirty               # not a human edit → does not dirty the document
    assert s.log == []               # not part of the replayable command log


def test_apply_silent_verdict_survives_a_real_command_and_its_undo():
    s = DocumentSession(doc())
    s.apply_silent(_set_no_gain("a"))         # verdict set before any history exists
    s.dispatch(Rename("a", "A!"))             # a real, undoable edit afterwards
    assert s.document.find("a").compression_no_gain is True
    s.undo()                                  # back to the pre-rename snapshot
    # the undo snapshot was captured AFTER the silent verdict → it is preserved
    assert s.document.find("a").compression_no_gain is True
    assert s.document.find("a").name == "a"


def test_apply_silent_does_not_break_a_later_real_dispatch():
    s = DocumentSession(doc())
    s.apply_silent(_set_no_gain("a"))
    s.dispatch(Rename("a", "A!"))
    assert s.can_undo() and s.dirty
    assert [type(c).__name__ for c in s.log] == ["Rename"]   # silent op stays out of the log


def test_replay_invariant_relaxed_only_for_no_gain():
    # Replaying the logged commands reproduces the document EXCEPT for the derived
    # compression_no_gain field, which is applied silently (out of the log by design).
    s = DocumentSession(doc())
    s.apply_silent(_set_no_gain("a"))
    s.dispatch(Rename("a", "A!"))

    replayed = apply_all(s.initial, s.log)
    assert replayed.find("a").compression_no_gain is False        # log alone never sets it
    assert replayed.find("a").name == "A!"                        # everything else matches
    # re-applying the silent verdict on top of the replay reproduces the live document
    reconstructed = apply_all(replayed, [_set_no_gain("a")])
    assert reconstructed.to_dict() == s.document.to_dict()
