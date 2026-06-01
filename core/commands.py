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
from typing import Optional, Tuple, Union

from core.model import Document, Node, STATUSES

# Fixed core defaults (the model/logic layer owns these — not the UI).
DEFAULT_COMPRESSION_DPI = 150


class CommandError(Exception):
    """A command could not be applied (bad target, invalid value, …)."""


class PendingChangeError(CommandError):
    """The command would discard/clash with a pending (uncommitted) change.

    Blocked by ``apply``'s preflight; re-issue the same command with ``force=True``
    to proceed anyway. Subclass of CommandError so existing handlers still catch it.
    """


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


# --- engine-backed commands (single-node; D3a) -----------------------------

@dataclass(frozen=True)
class Compress:
    node_id: str
    dpi: int = DEFAULT_COMPRESSION_DPI
    method: Optional[str] = None  # jpg/png/pikepdf; None = best


@dataclass(frozen=True)
class Commit:
    node_id: str


@dataclass(frozen=True)
class Reset:
    node_id: str


@dataclass(frozen=True)
class Rotate:
    node_id: str
    direction: str = "right"  # "right" | "left" | "180"
    force: bool = False  # override the pending-change preflight (see preflight)


# --- engine-backed multi-node commands (D3b) -------------------------------

@dataclass(frozen=True)
class Split:
    node_id: str  # a leaf -> one page-leaf per page
    force: bool = False  # override the pending-change preflight


@dataclass(frozen=True)
class Merge:
    node_ids: Tuple[str, ...]  # >= 2 sibling leaves -> one leaf
    force: bool = False  # override the pending-change preflight

    def __post_init__(self):
        if not isinstance(self.node_ids, tuple):
            object.__setattr__(self, "node_ids", tuple(self.node_ids))


Command = Union[AddFolder, Rename, SetStatus, SetPeriod, Delete, Move,
                Compress, Commit, Reset, Rotate, Split, Merge]

_COMMAND_TYPES = {c.__name__: c for c in (
    AddFolder, Rename, SetStatus, SetPeriod, Delete, Move,
    Compress, Commit, Reset, Rotate, Split, Merge,
)}

_ROTATE_ANGLES = {"right": 90, "left": -90, "180": 180}


# --------------------------------------------------------------------------- #
# Reducer
# --------------------------------------------------------------------------- #

_HANDLERS = {}


def _handler(cmd_type):
    def deco(fn):
        _HANDLERS[cmd_type] = fn
        return fn
    return deco


def apply(doc: Document, cmd: Command, engine=None) -> Document:
    """Apply a command, returning a new Document. Pure given the engine.

    Structural commands ignore ``engine``; engine-backed commands
    (Compress/Rotate/…) require it and raise CommandError if it is missing.

    Before running, a **preflight** blocks commands that would discard or clash
    with a pending (uncommitted) change, unless the command carries ``force``.
    """
    handler = _HANDLERS.get(type(cmd))
    if handler is None:
        raise CommandError(f"unknown command: {type(cmd).__name__}")
    if not getattr(cmd, "force", False):
        risk = preflight(doc, cmd)
        if risk is not None:
            raise PendingChangeError(risk)
    return handler(doc, cmd, engine)


def apply_all(doc: Document, cmds, engine=None) -> Document:
    """Fold a sequence of commands over a document."""
    for cmd in cmds:
        doc = apply(doc, cmd, engine)
    return doc


# --------------------------------------------------------------------------- #
# Preflight: block a change that would clobber an incomplete (pending) one
# --------------------------------------------------------------------------- #

# A node is "pending" when it holds an uncommitted compression — i.e. a
# `current_data` variant that has not been committed (Commit) or discarded
# (Reset). These commands consume a node's *original* bytes (or recombine
# siblings), silently throwing that pending variant away, so the result differs
# depending on whether the compression was finished first. Pure & data-driven.
_PENDING_CLASH_VERBS = {"Rotate": "Rotating", "Split": "Splitting", "Merge": "Merging"}


def _is_pending(node: Optional[Node]) -> bool:
    return node is not None and node.current_data is not None


def _merge_compression_state(nodes):
    """Hypothetical compression outcome of merging ``nodes``:
    ``(preserves, dpi_current, no_compression)``. Single source of truth shared
    by ``_merge`` (to build the node) and ``preflight`` (to judge data loss)."""
    dpi_set = {n.dpi_current for n in nodes if n.is_compressed and n.dpi_current is not None}
    all_compressed = all(n.is_compressed for n in nodes)
    no_compression = any(n.no_compression for n in nodes) or len(dpi_set) > 1
    preserves = (not no_compression) and all_compressed and len(dpi_set) == 1
    return preserves, (next(iter(dpi_set)) if preserves else None), no_compression


def preflight(doc: Document, cmd: Command) -> Optional[str]:
    """Return a human-readable reason if ``cmd`` would discard/clash with a
    pending (uncommitted) change, else None. ``apply`` blocks on a non-None
    result unless the command sets ``force=True``."""
    name = type(cmd).__name__
    if name in ("Rotate", "Split"):
        ids = [cmd.node_id]
    elif name == "Merge":
        nodes = [doc.find(nid) for nid in cmd.node_ids]
        # A merge that preserves the compression carries it forward — nothing is
        # discarded, so it is not a clash. Only a dropping merge clobbers a pending one.
        if all(n is not None for n in nodes) and _merge_compression_state(nodes)[0]:
            return None
        ids = list(cmd.node_ids)
    else:
        return None
    pending = [n for n in (doc.find(nid) for nid in ids) if _is_pending(n)]
    if not pending:
        return None
    names = ", ".join(n.name for n in pending)
    verb = _PENDING_CLASH_VERBS.get(name, "This operation")
    return (f"{verb} would discard an unconfirmed compression on: {names}. "
            f"Commit it (“Lesbarkeit geprüft”) first, or force.")


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


def _require_leaf(doc: Document, node_id: str) -> Node:
    node = _require(doc, node_id)
    if node.is_folder:
        raise CommandError(f"not a leaf document: {node_id}")
    return node


def _require_engine(engine):
    if engine is None:
        raise CommandError("this command requires a PDF engine")
    return engine


# --- handlers --------------------------------------------------------------

@_handler(AddFolder)
def _add_folder(doc: Document, cmd: AddFolder, engine=None) -> Document:
    _require_folder(doc, cmd.parent_id)
    folder = Node(name=cmd.name, is_folder=True,
                  **({"id": cmd.new_id} if cmd.new_id else {}))
    return doc.insert_child(cmd.parent_id, folder, cmd.index)


@_handler(Rename)
def _rename(doc: Document, cmd: Rename, engine=None) -> Document:
    _require(doc, cmd.node_id)
    if not cmd.name:
        raise CommandError("name must not be empty")
    return doc.update_node(cmd.node_id, name=cmd.name)


@_handler(SetStatus)
def _set_status(doc: Document, cmd: SetStatus, engine=None) -> Document:
    _require(doc, cmd.node_id)
    if cmd.status not in STATUSES:
        raise CommandError(f"invalid status: {cmd.status!r}")
    return doc.update_node(cmd.node_id, status=cmd.status)


@_handler(SetPeriod)
def _set_period(doc: Document, cmd: SetPeriod, engine=None) -> Document:
    _require(doc, cmd.node_id)
    return doc.update_node(cmd.node_id, vz_start=cmd.vz_start, vz_end=cmd.vz_end)


@_handler(Delete)
def _delete(doc: Document, cmd: Delete, engine=None) -> Document:
    _require(doc, cmd.node_id)
    _reject_root(doc, cmd.node_id, "delete")
    return doc.remove_node(cmd.node_id)


@_handler(Move)
def _move(doc: Document, cmd: Move, engine=None) -> Document:
    node = _require(doc, cmd.node_id)
    _require_folder(doc, cmd.new_parent_id)
    _reject_root(doc, cmd.node_id, "move")
    if node.find(cmd.new_parent_id) is not None:
        raise CommandError("cannot move a node into itself or its own subtree")
    return doc.move_node(cmd.node_id, cmd.new_parent_id, cmd.index)


# --- engine-backed handlers ------------------------------------------------

@_handler(Compress)
def _compress(doc: Document, cmd: Compress, engine=None) -> Document:
    node = _require_leaf(doc, cmd.node_id)
    _require_engine(engine)
    if node.no_compression:
        raise CommandError("node is marked no_compression")
    if not node.original_data:
        raise CommandError("node has no data to compress")
    result = engine.compress(node.original_data, cmd.dpi, cmd.method)
    if result is None:
        return doc  # this method / the best didn't beat the original → unchanged
    return doc.update_node(cmd.node_id, current_data=result,
                           is_compressed=True, dpi_current=cmd.dpi,
                           compression_method=cmd.method)


@_handler(Commit)
def _commit(doc: Document, cmd: Commit, engine=None) -> Document:
    node = _require_leaf(doc, cmd.node_id)
    if node.current_data is None:
        raise CommandError("nothing to commit (no current/compressed data)")
    new_dpi_original = node.dpi_current if node.dpi_current is not None else node.dpi_original
    return doc.update_node(
        cmd.node_id,
        original_data=node.current_data,
        current_data=None,
        dpi_original=new_dpi_original,
        dpi_current=None,
        is_compressed=False,
        compression_method=None,
    )


@_handler(Reset)
def _reset(doc: Document, cmd: Reset, engine=None) -> Document:
    _require(doc, cmd.node_id)
    return doc.update_node(cmd.node_id, current_data=None,
                           is_compressed=False, dpi_current=None,
                           compression_method=None)


@_handler(Rotate)
def _rotate(doc: Document, cmd: Rotate, engine=None) -> Document:
    node = _require_leaf(doc, cmd.node_id)
    _require_engine(engine)
    if cmd.direction not in _ROTATE_ANGLES:
        raise CommandError(f"invalid direction: {cmd.direction!r}")
    if not node.original_data:
        raise CommandError("node has no data to rotate")
    rotated = engine.rotate(node.original_data, _ROTATE_ANGLES[cmd.direction])
    # Rotating invalidates any compressed variant.
    return doc.update_node(cmd.node_id, original_data=rotated,
                           current_data=None, is_compressed=False, dpi_current=None,
                           compression_method=None)


@_handler(Split)
def _split(doc: Document, cmd: Split, engine=None) -> Document:
    node = _require_leaf(doc, cmd.node_id)
    _require_engine(engine)
    if not node.original_data:
        raise CommandError("node has no data to split")
    parent = doc.parent_of(cmd.node_id)
    if parent is None:
        raise CommandError("cannot split the root node")
    parts = engine.split(node.original_data)
    if len(parts) < 2:
        return doc  # single page → nothing to split
    # Split parts come from an already-processed document → not re-compressed.
    new_leaves = [
        Node(name=f"{node.name}_{i + 1}", pdf_length=1, no_compression=True,
             original_data=part)
        for i, part in enumerate(parts)
    ]
    index = [c.id for c in parent.children].index(cmd.node_id)
    doc = doc.remove_node(cmd.node_id)
    for offset, leaf in enumerate(new_leaves):
        doc = doc.insert_child(parent.id, leaf, index + offset)
    return doc


@_handler(Merge)
def _merge(doc: Document, cmd: Merge, engine=None) -> Document:
    _require_engine(engine)
    ids = list(cmd.node_ids)
    if len(ids) < 2:
        raise CommandError("merge needs at least two nodes")
    nodes = [_require_leaf(doc, nid) for nid in ids]

    parents = {(doc.parent_of(nid).id if doc.parent_of(nid) else None) for nid in ids}
    if len(parents) != 1 or None in parents:
        raise CommandError("merge nodes must share one parent")
    parent_id = parents.pop()
    parent = doc.find(parent_id)

    merged_original = engine.merge([n.original_data or b"" for n in nodes])

    # DPI-conflict invariant (see DATA_CONTRACT): differing compressed DPIs ->
    # drop compression and mark no_compression.
    preserves, dpi_current, no_compression = _merge_compression_state(nodes)
    method_set = {n.compression_method for n in nodes if n.is_compressed}
    if preserves:
        current_data = engine.merge([n.current_data for n in nodes])
        is_compressed = True
        compression_method = next(iter(method_set)) if len(method_set) == 1 else None
    else:
        current_data = None
        is_compressed = False
        compression_method = None

    merged = Node(
        name=nodes[0].name,
        pdf_length=sum(n.pdf_length for n in nodes),
        original_data=merged_original,
        current_data=current_data,
        is_compressed=is_compressed,
        dpi_original=max((n.dpi_original for n in nodes if n.dpi_original is not None), default=None),
        dpi_current=dpi_current,
        no_compression=no_compression,
        compression_method=compression_method,
    )

    id_set = set(ids)
    first_pos = [c.id for c in parent.children].index(ids[0])
    insert_at = sum(1 for c in parent.children[:first_pos] if c.id not in id_set)
    for nid in ids:
        doc = doc.remove_node(nid)
    return doc.insert_child(parent_id, merged, insert_at)


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
