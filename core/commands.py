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
class SetCollapsed:
    node_id: str
    collapsed: bool


@dataclass(frozen=True)
class SetAllCollapsed:
    collapsed: bool


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


@dataclass(frozen=True)
class MoveMany:
    """Move several nodes (any depth) under one folder, preserving their order.
    Nested members are de-duplicated (a node already moving inside a selected
    ancestor is skipped)."""
    node_ids: Tuple[str, ...]
    new_parent_id: str
    index: Optional[int] = None

    def __post_init__(self):
        if not isinstance(self.node_ids, tuple):
            object.__setattr__(self, "node_ids", tuple(self.node_ids))


@dataclass(frozen=True)
class InsertNodes:
    """Insert already-built nodes (e.g. freshly imported files) under a folder.
    Carries Node objects (with bytes), so it is created in-process by the import
    API and dispatched directly — it is not part of the wire/JSON command set."""
    parent_id: str
    nodes: Tuple[Node, ...]
    index: Optional[int] = None

    def __post_init__(self):
        if not isinstance(self.nodes, tuple):
            object.__setattr__(self, "nodes", tuple(self.nodes))


@dataclass(frozen=True)
class GroupIntoFolder:
    """Create a new folder under ``parent_id`` and move every selected node into
    it (preserving order). The other half of "merge": keeps the nodes as separate
    documents inside a folder instead of concatenating them into one PDF."""
    node_ids: Tuple[str, ...]
    parent_id: str
    name: str = "Neue Gruppe"
    new_id: Optional[str] = None
    index: Optional[int] = None

    def __post_init__(self):
        if not isinstance(self.node_ids, tuple):
            object.__setattr__(self, "node_ids", tuple(self.node_ids))


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


# --- engine-backed multi-node commands (D3b) -------------------------------

@dataclass(frozen=True)
class Split:
    node_id: str  # a leaf -> one page-leaf per page


@dataclass(frozen=True)
class SplitInto:
    """Split a leaf into chunks of ``size`` pages (size=1 -> per page). When
    ``into_folder`` is set, the parts go into a NEW folder named after the node;
    otherwise they replace the node in place."""
    node_id: str
    size: int = 1
    into_folder: bool = False


@dataclass(frozen=True)
class Merge:
    node_ids: Tuple[str, ...]  # >= 2 sibling leaves -> one leaf

    def __post_init__(self):
        if not isinstance(self.node_ids, tuple):
            object.__setattr__(self, "node_ids", tuple(self.node_ids))


Command = Union[AddFolder, Rename, SetStatus, SetCollapsed, SetAllCollapsed, SetPeriod,
                Delete, Move, MoveMany, GroupIntoFolder, InsertNodes, Compress, Commit,
                Reset, Rotate, Split, SplitInto, Merge]

# Wire/JSON-serialisable commands (command_from_dict). InsertNodes is deliberately
# excluded — it carries Node objects with bytes and is only dispatched in-process.
_COMMAND_TYPES = {c.__name__: c for c in (
    AddFolder, Rename, SetStatus, SetCollapsed, SetAllCollapsed, SetPeriod, Delete, Move,
    MoveMany, GroupIntoFolder, Compress, Commit, Reset, Rotate, Split, SplitInto, Merge,
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
    """
    handler = _HANDLERS.get(type(cmd))
    if handler is None:
        raise CommandError(f"unknown command: {type(cmd).__name__}")
    return handler(doc, cmd, engine)


def apply_all(doc: Document, cmds, engine=None) -> Document:
    """Fold a sequence of commands over a document."""
    for cmd in cmds:
        doc = apply(doc, cmd, engine)
    return doc


def _merge_compression_state(nodes):
    """Hypothetical compression outcome of merging ``nodes``:
    ``(preserves, dpi_current, no_compression)``. Same DPI on all-compressed leaves
    keeps the merged compression; otherwise it is dropped and no_compression set."""
    dpi_set = {n.dpi_current for n in nodes if n.is_compressed and n.dpi_current is not None}
    all_compressed = all(n.is_compressed for n in nodes)
    no_compression = any(n.no_compression for n in nodes) or len(dpi_set) > 1
    preserves = (not no_compression) and all_compressed and len(dpi_set) == 1
    return preserves, (next(iter(dpi_set)) if preserves else None), no_compression


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


@_handler(SetCollapsed)
def _set_collapsed(doc: Document, cmd: SetCollapsed, engine=None) -> Document:
    node = _require(doc, cmd.node_id)
    if not node.is_folder:
        raise CommandError("only folders can be collapsed")
    return doc.update_node(cmd.node_id, collapsed=bool(cmd.collapsed))


@_handler(SetAllCollapsed)
def _set_all_collapsed(doc: Document, cmd: SetAllCollapsed, engine=None) -> Document:
    """Collapse/expand every folder at once (one undo step)."""
    value = bool(cmd.collapsed)

    def walk(n: Node, is_root: bool) -> Node:
        kids = tuple(walk(c, False) for c in n.children)
        if n.is_folder and not is_root:
            return dataclasses.replace(n, collapsed=value, children=kids)
        return dataclasses.replace(n, children=kids)

    return Document(walk(doc.root, True))


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


def _parent_id_map(root: Node) -> dict:
    """One-pass child-id → parent-id map (avoids repeated O(n) parent_of scans)."""
    out = {}
    stack = [root]
    while stack:
        n = stack.pop()
        for c in n.children:
            out[c.id] = n.id
            stack.append(c)
    return out


def _top_level_ids(doc: Document, ids):
    """Drop ids that already sit inside another selected id (so a folder + one of
    its descendants only moves the folder). O(n) via a single parent map."""
    id_set = set(ids)
    pmap = _parent_id_map(doc.root)
    out = []
    for nid in ids:
        pid = pmap.get(nid)
        nested = False
        while pid is not None:
            if pid in id_set:
                nested = True
                break
            pid = pmap.get(pid)
        if not nested:
            out.append(nid)
    return out


def _validate_move_targets(doc: Document, ids, parent_id: str):
    nodes = []
    for nid in ids:
        node = _require(doc, nid)
        _reject_root(doc, nid, "move")
        if node.find(parent_id) is not None:
            raise CommandError("cannot move a node into itself or its own subtree")
        nodes.append(node)
    return nodes


@_handler(MoveMany)
def _move_many(doc: Document, cmd: MoveMany, engine=None) -> Document:
    _require_folder(doc, cmd.new_parent_id)
    ids = _top_level_ids(doc, list(cmd.node_ids))
    if not ids:
        return doc
    nodes = _validate_move_targets(doc, ids, cmd.new_parent_id)
    # `index` is in the pre-removal frame (the UI's drop position). Discount the
    # moved nodes that sit before it in the target parent, since removing them
    # shifts the slot down — so the group lands exactly where it was dropped.
    parent = doc.find(cmd.new_parent_id)
    raw = len(parent.children) if cmd.index is None else max(0, min(cmd.index, len(parent.children)))
    moved = set(ids)
    before = sum(1 for i, c in enumerate(parent.children) if c.id in moved and i < raw)
    at = raw - before
    for nid in ids:
        doc = doc.remove_node(nid)
    for offset, node in enumerate(nodes):
        doc = doc.insert_child(cmd.new_parent_id, node, at + offset)
    return doc


@_handler(InsertNodes)
def _insert_nodes(doc: Document, cmd: InsertNodes, engine=None) -> Document:
    _require_folder(doc, cmd.parent_id)
    if not cmd.nodes:
        return doc
    for offset, node in enumerate(cmd.nodes):
        at = None if cmd.index is None else cmd.index + offset
        doc = doc.insert_child(cmd.parent_id, node, at)
    return doc


@_handler(GroupIntoFolder)
def _group_into_folder(doc: Document, cmd: GroupIntoFolder, engine=None) -> Document:
    _require_folder(doc, cmd.parent_id)
    ids = _top_level_ids(doc, list(cmd.node_ids))
    if not ids:
        raise CommandError("nothing to group")
    _validate_move_targets(doc, ids, cmd.parent_id)
    folder = Node(name=cmd.name or "Neue Gruppe", is_folder=True,
                  **({"id": cmd.new_id} if cmd.new_id else {}))
    fid = folder.id
    doc = doc.insert_child(cmd.parent_id, folder, cmd.index)
    for nid in ids:
        doc = doc.move_node(nid, fid, None)
    return doc


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
    node = _require(doc, cmd.node_id)
    # A committed node reloaded from disk has no source (original dropped on save):
    # there is nothing to reset to, and clearing current_data would blank it.
    if not node.is_folder and node.original_data is None and node.current_data is not None:
        raise CommandError("kein Original vorhanden – Zurücksetzen nicht möglich")
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


@_handler(SplitInto)
def _split_into(doc: Document, cmd: SplitInto, engine=None) -> Document:
    node = _require_leaf(doc, cmd.node_id)
    _require_engine(engine)
    if not node.original_data:
        raise CommandError("node has no data to split")
    parent = doc.parent_of(cmd.node_id)
    if parent is None:
        raise CommandError("cannot split the root node")
    size = max(1, int(cmd.size))
    pages = engine.split(node.original_data)               # per-page parts
    groups = [pages[i:i + size] for i in range(0, len(pages), size)]
    if not cmd.into_folder and len(groups) < 2:
        return doc  # nothing to split in place (single chunk)
    new_leaves = [
        Node(name=f"{node.name}_{i + 1}", pdf_length=len(g), no_compression=True,
             original_data=(g[0] if len(g) == 1 else engine.merge(g)))
        for i, g in enumerate(groups)
    ]
    index = [c.id for c in parent.children].index(cmd.node_id)
    doc = doc.remove_node(cmd.node_id)
    if cmd.into_folder:
        folder = Node(name=node.name, is_folder=True, children=tuple(new_leaves))
        return doc.insert_child(parent.id, folder, index)
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
