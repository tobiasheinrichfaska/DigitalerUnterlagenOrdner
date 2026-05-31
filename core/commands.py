"""Structural commands + a pure reducer over the immutable Document.

Commands are **plain data** (frozen dataclasses) so they can be logged, replayed
and serialised. The reducer ``apply(doc, cmd) -> doc`` is a pure function with no
side effects — it only rearranges structure / metadata. Operations that need the
PDF engine (split/merge/compress/…) live in a separate layer (D3) so this one
stays engine-free and exhaustively unit-testable.

Invalid targets raise ``CommandError`` (uniform, catchable) rather than leaking
KeyError/ValueError from the low-level transforms.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Optional, Union

from core.model import Document, Node, STATUSES


class CommandError(Exception):
    """A command could not be applied (bad target, invalid value, …)."""


# --------------------------------------------------------------------------- #
# Command value objects (pure data)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class AddFolder:
    parent_id: str
    name: str = "Neuer Ordner"
    index: Optional[int] = None
    new_id: Optional[str] = None  # set for deterministic ids (tests / replay)


@dataclass(frozen=True)
class Rename:
    node_id: str
    name: str


@dataclass(frozen=True)
class SetStatus:
    node_id: str
    status: str


@dataclass(frozen=True)
class SetPeriod:
    node_id: str
    vz_start: Optional[int]
    vz_end: Optional[int]


@dataclass(frozen=True)
class Delete:
    node_id: str


@dataclass(frozen=True)
class Move:
    node_id: str
    new_parent_id: str
    index: Optional[int] = None


Command = Union[AddFolder, Rename, SetStatus, SetPeriod, Delete, Move]

_COMMAND_TYPES = {c.__name__: c for c in (AddFolder, Rename, SetStatus, SetPeriod, Delete, Move)}


# --------------------------------------------------------------------------- #
# Reducer
# --------------------------------------------------------------------------- #

_HANDLERS = {}


def _handler(cmd_type):
    def deco(fn):
        _HANDLERS[cmd_type] = fn
        return fn
    return deco


def apply(doc: Document, cmd: Command) -> Document:
    """Apply a command, returning a new Document. Pure; raises CommandError."""
    handler = _HANDLERS.get(type(cmd))
    if handler is None:
        raise CommandError(f"unknown command: {type(cmd).__name__}")
    return handler(doc, cmd)


def apply_all(doc: Document, cmds) -> Document:
    """Fold a sequence of commands over a document."""
    for cmd in cmds:
        doc = apply(doc, cmd)
    return doc


# --- validation helpers ----------------------------------------------------

def _require(doc: Document, node_id: str) -> Node:
    node = doc.find(node_id)
    if node is None:
        raise CommandError(f"node not found: {node_id}")
    return node


def _require_folder(doc: Document, node_id: str) -> Node:
    node = _require(doc, node_id)
    if not node.is_folder:
        raise CommandError(f"not a folder: {node_id}")
    return node


def _reject_root(doc: Document, node_id: str, what: str) -> None:
    if node_id == doc.root.id:
        raise CommandError(f"cannot {what} the root node")


# --- handlers --------------------------------------------------------------

@_handler(AddFolder)
def _add_folder(doc: Document, cmd: AddFolder) -> Document:
    _require_folder(doc, cmd.parent_id)
    folder = Node(name=cmd.name, is_folder=True,
                  **({"id": cmd.new_id} if cmd.new_id else {}))
    return doc.insert_child(cmd.parent_id, folder, cmd.index)


@_handler(Rename)
def _rename(doc: Document, cmd: Rename) -> Document:
    _require(doc, cmd.node_id)
    if not cmd.name:
        raise CommandError("name must not be empty")
    return doc.update_node(cmd.node_id, name=cmd.name)


@_handler(SetStatus)
def _set_status(doc: Document, cmd: SetStatus) -> Document:
    _require(doc, cmd.node_id)
    if cmd.status not in STATUSES:
        raise CommandError(f"invalid status: {cmd.status!r}")
    return doc.update_node(cmd.node_id, status=cmd.status)


@_handler(SetPeriod)
def _set_period(doc: Document, cmd: SetPeriod) -> Document:
    _require(doc, cmd.node_id)
    return doc.update_node(cmd.node_id, vz_start=cmd.vz_start, vz_end=cmd.vz_end)


@_handler(Delete)
def _delete(doc: Document, cmd: Delete) -> Document:
    _require(doc, cmd.node_id)
    _reject_root(doc, cmd.node_id, "delete")
    return doc.remove_node(cmd.node_id)


@_handler(Move)
def _move(doc: Document, cmd: Move) -> Document:
    node = _require(doc, cmd.node_id)
    _require_folder(doc, cmd.new_parent_id)
    _reject_root(doc, cmd.node_id, "move")
    if node.find(cmd.new_parent_id) is not None:
        raise CommandError("cannot move a node into itself or its own subtree")
    return doc.move_node(cmd.node_id, cmd.new_parent_id, cmd.index)


# --------------------------------------------------------------------------- #
# Command serialisation (for the event log / replay)
# --------------------------------------------------------------------------- #

def command_to_dict(cmd: Command) -> dict:
    return {"type": type(cmd).__name__, **dataclasses.asdict(cmd)}


def command_from_dict(d: dict) -> Command:
    data = dict(d)
    type_name = data.pop("type")
    cmd_type = _COMMAND_TYPES.get(type_name)
    if cmd_type is None:
        raise CommandError(f"unknown command type: {type_name!r}")
    return cmd_type(**data)
