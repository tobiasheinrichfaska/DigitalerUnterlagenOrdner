# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
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

from dataclasses import replace

from core.commands import Command, SetDatev, apply
from core.model import Document


class DocumentSession:
    def __init__(self, document: Document, engine=None):
        self._initial = document
        self._doc = document
        self._engine = engine
        self._undo: List[tuple] = []  # (previous_doc, command)
        self._redo: List[tuple] = []  # (next_doc, command)
        self._dirty = False  # unsaved changes since open/save
        # Identity marker of the document AS SAVED/OPENED: undo/redo compare against
        # it (snapshots restore the SAME object), so undoing back to the saved state
        # clears dirty instead of asking about "unsaved changes" that no longer exist
        # (I-6, QS 2026-11-04).
        self._saved_doc = document

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_saved(self) -> None:
        self._dirty = False
        self._saved_doc = self._doc

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
        if isinstance(cmd, SetDatev):
            # origin metadata must survive undo/redo: carry it into every snapshot too
            # (identity of the saved-state marker is preserved via the memo) (C-3)
            memo: dict = {id(self._doc): self._doc}

            def carry(d: Document) -> Document:
                nd = memo.get(id(d))
                if nd is None:
                    nd = Document(replace(d.root, datev=cmd.provenance))
                    memo[id(d)] = nd
                return nd
            self._undo = [(carry(d), c) for d, c in self._undo]
            self._redo = [(carry(d), c) for d, c in self._redo]
            if self._saved_doc is not self._doc:
                self._saved_doc = carry(self._saved_doc)
        if not self._dirty:
            # a silent fact on a clean document keeps it clean — move the marker along
            # so a later undo/redo identity check still recognises the saved state
            self._saved_doc = self._doc
        return self._doc

    def undo(self) -> Document:
        if not self._undo:
            return self._doc
        prev, cmd = self._undo.pop()
        self._redo.append((self._doc, cmd))
        self._doc = prev
        self._dirty = self._doc is not self._saved_doc  # back at the saved state → clean
        return self._doc

    def redo(self) -> Document:
        if not self._redo:
            return self._doc
        nxt, cmd = self._redo.pop()
        self._undo.append((self._doc, cmd))
        self._doc = nxt
        self._dirty = self._doc is not self._saved_doc  # forward to the saved state → clean
        return self._doc
