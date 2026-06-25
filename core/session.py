"""Editing session: a current Document + undo/redo + an event log.

Wraps the pure reducer with the stateful bits a UI needs. Undo/redo store
immutable document snapshots (cheap — structural sharing means unchanged
subtrees are reused). The **event log** is the list of commands on the current
path, with the invariant:

    apply_all(session.initial, session.log, engine) == session.document

so a session is fully reconstructable / persistable from its initial document
plus its command log (the basis for the core service's audit / sync).

``apply_silent`` is the one deliberate exception: it applies a *derived* fact (the
compression "no gain" verdict) straight onto the current document without touching
undo/redo, the dirty flag, or the log. The replay invariant therefore holds only up
to those derived fields — they are recomputable from the bytes, so losing them on
replay/undo is harmless.
"""

from __future__ import annotations

from typing import List, Optional

from core.commands import Command, apply
from core.model import Document


class DocumentSession:
    def __init__(self, document: Document, engine=None):
        self._initial = document
        self._doc = document
        self._engine = engine
        self._undo: List[tuple] = []  # (previous_doc, command)
        self._redo: List[tuple] = []  # (next_doc, command)
        self._dirty = False  # unsaved changes since open/save

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_saved(self) -> None:
        self._dirty = False

    # --- state -------------------------------------------------------------
    @property
    def document(self) -> Document:
        return self._doc

    @property
    def initial(self) -> Document:
        return self._initial

    @property
    def log(self) -> List[Command]:
        """Commands on the current path (shrinks on undo, grows on redo)."""
        return [cmd for (_prev, cmd) in self._undo]

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    # --- editing -----------------------------------------------------------
    def dispatch(self, cmd: Command) -> Document:
        """Apply a command; record it for undo unless it changed nothing."""
        new = apply(self._doc, cmd, self._engine)
        if new == self._doc:
            return self._doc  # no-op (e.g. compress that didn't help) — no history
        self._undo.append((self._doc, cmd))
        self._doc = new
        self._redo.clear()
        self._dirty = True
        return new

    def apply_silent(self, cmd: Command) -> Document:
        """Apply a DERIVED, non-user mutation (the no-gain verdict) onto the current
        document WITHOUT recording undo/redo, marking dirty, or logging it. Use only
        for facts recomputable from the bytes — it intentionally relaxes the replay
        invariant for those fields (see module docstring)."""
        self._doc = apply(self._doc, cmd, self._engine)
        return self._doc

    def undo(self) -> Document:
        if not self._undo:
            return self._doc
        prev, cmd = self._undo.pop()
        self._redo.append((self._doc, cmd))
        self._doc = prev
        self._dirty = True
        return self._doc

    def redo(self) -> Document:
        if not self._redo:
            return self._doc
        nxt, cmd = self._redo.pop()
        self._undo.append((self._doc, cmd))
        self._doc = nxt
        self._dirty = True
        return self._doc
