# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Immutable document model — the data-driven core.

A `Document` is an immutable tree of `Node`s. Nothing here renders, threads, or
touches a GUI; every transform is a **pure function: state -> new state** with
structural sharing (unchanged subtrees are reused). Commands (core/commands.py)
build on these primitives; the GUI / core service hold a `Document` + history.

Canonical fields mirror the data contract (docs/DATA_CONTRACT.md). Page bytes
(`original_data` / `current_data`) live on the node but are **not** serialised by
`to_dict` — the JSON is structure only; bytes travel separately.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterator, List, Optional, Tuple

# Status values. NO_STATUS ("" — the new default) means the node has no status
# yet: nothing is set on a freshly drawn/imported/generated node. The three
# positive states are set explicitly (yellow=todo, green=done, red=prior-year);
# the empty value clears back to "no status". The vocabulary is data-driven: the
# UI builds its status menu from STATUSES (config()).
STATUS_NONE = ""
STATUS_DONE = "erfasst"
STATUS_TODO = "zu erfassen"
STATUS_PRIOR_YEAR = "vorjahreswert"
STATUSES = (STATUS_NONE, STATUS_TODO, STATUS_DONE, STATUS_PRIOR_YEAR)


def new_id() -> str:
    return uuid.uuid4().hex


def scrub_surrogates(text):
    """Replace lone UTF-16 surrogates (a JS half-emoji arrives as a JSON \\ud83d escape)
    with U+FFFD: they cannot be UTF-8/UTF-16 encoded, which broke save/export (u4 BP-4)."""
    if not isinstance(text, str):
        return text
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        return "".join("\ufffd" if "\ud800" <= ch <= "\udfff" else ch for ch in text)


@dataclass(frozen=True)
class Node:
    """An immutable tree node (folder or leaf document)."""

    name: str
    is_folder: bool = False
    id: str = field(default_factory=new_id)
    status: str = STATUS_NONE  # new nodes start with no status (see STATUS_NONE)
    vz_start: Optional[int] = None
    vz_end: Optional[int] = None
    pdf_length: int = 0
    is_compressed: bool = False
    dpi_original: Optional[int] = None
    dpi_current: Optional[int] = None
    no_compression: bool = False
    # Evaluated and nothing smaller was found → no compression decision is pending
    # (auto-confirmed). Persisted so it isn't re-evaluated on every load and the leaf
    # shows no "undecided" (red) dot. Cleared when the source changes (rotate/new node).
    compression_no_gain: bool = False
    collapsed: bool = False  # folder collapsed in the tree view (persisted)
    tags: Tuple[str, ...] = ()  # free-form labels for search / sort / group (persisted)
    # DATEV provenance (DATEV mode only): which DATEV document this working file came
    # from — {doc_guid, file_id, structure_item_id, source_name?}. Set on open from a
    # checkout path, lives on the ROOT node, persisted so a reopened .belegtool still
    # shows the "from DATEV" link; None ⇒ not DATEV-connected. The runtime write-back
    # baseline (opened bytes' sha256, change_date_time, checked_out) is NOT persisted —
    # it is re-established from the live server at save time (see CoreApi datev_* ops).
    datev: Optional[Dict[str, Any]] = None
    children: Tuple["Node", ...] = ()
    original_data: Optional[bytes] = None
    current_data: Optional[bytes] = None
    compression_method: Optional[str] = None  # jpg/png/pikepdf chosen for current_data; None = none/auto

    def __post_init__(self):
        # model boundary: names/tags must always be encodable (u4 BP-4)
        clean = scrub_surrogates(self.name)
        if clean != self.name:
            object.__setattr__(self, "name", clean)
        if any(isinstance(t, str) and scrub_surrogates(t) != t for t in self.tags):
            object.__setattr__(self, "tags", tuple(scrub_surrogates(t) for t in self.tags))

    # --- serialisation (structure only — no bytes) ------------------------
    def to_dict(self, position: Optional[int] = None) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "is_folder": self.is_folder,
            "status": self.status,
            "position": position,
            "vz_start": self.vz_start,
            "vz_end": self.vz_end,
            "pdf_length": self.pdf_length,
            "is_compressed": self.is_compressed,
            "dpi_original": self.dpi_original,
            "dpi_current": self.dpi_current,
            "no_compression": self.no_compression,
            "compression_no_gain": self.compression_no_gain,
            "collapsed": self.collapsed,
            "compression_method": self.compression_method,
            "tags": list(self.tags),
            "datev": self.datev,  # DATEV provenance (root only; None elsewhere)
            # UI hint: a committed node reloaded from disk has no source bytes
            # (the original was dropped on save), so it can't be re-compressed/reset.
            "has_source": self.original_data is not None,
            "children": [c.to_dict(i) for i, c in enumerate(self.children)],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Node":
        return cls(
            name=d["name"],
            is_folder=d.get("is_folder", False),
            id=d.get("id") or new_id(),
            status=d.get("status", STATUS_NONE),
            vz_start=d.get("vz_start"),
            vz_end=d.get("vz_end"),
            pdf_length=d.get("pdf_length", 0),
            is_compressed=d.get("is_compressed", False),
            dpi_original=d.get("dpi_original"),
            dpi_current=d.get("dpi_current"),
            no_compression=d.get("no_compression", False),
            compression_no_gain=d.get("compression_no_gain", False),
            collapsed=d.get("collapsed", False),
            compression_method=d.get("compression_method"),
            tags=tuple(d.get("tags") or ()),
            datev=d.get("datev"),
            children=tuple(Node.from_dict(c) for c in d.get("children", [])),
        )

    # --- queries ----------------------------------------------------------
    def iter(self) -> Iterator["Node"]:
        """Pre-order traversal including self."""
        yield self
        for child in self.children:
            yield from child.iter()

    def find(self, node_id: str) -> Optional["Node"]:
        for n in self.iter():
            if n.id == node_id:
                return n
        return None


@dataclass(frozen=True)
class Document:
    """An immutable document: a root folder node."""

    root: Node

    @classmethod
    def empty(cls, root_name: str = "root") -> "Document":
        return cls(Node(name=root_name, is_folder=True))

    # --- serialisation ----------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return self.root.to_dict()

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Document":
        return cls(Node.from_dict(d))

    # --- queries ----------------------------------------------------------
    def find(self, node_id: str) -> Optional[Node]:
        return self.root.find(node_id)

    def parent_of(self, node_id: str) -> Optional[Node]:
        return parent_of(self.root, node_id)

    def path_to(self, node_id: str) -> Optional[List[Node]]:
        return path_to(self.root, node_id)

    # --- transforms (pure: return a new Document) -------------------------
    def update_node(self, node_id: str, **changes) -> "Document":
        return Document(update_node(self.root, node_id, **changes))

    def update_nodes(self, changes_by_id: Dict[str, Dict[str, Any]]) -> "Document":
        return Document(update_nodes(self.root, changes_by_id))

    def remove_nodes(self, node_ids) -> "Document":
        return Document(remove_nodes(self.root, node_ids))

    def insert_children(self, parent_id: str, children, index: Optional[int] = None) -> "Document":
        return Document(insert_children(self.root, parent_id, children, index))

    def replace_node(self, node_id: str, new_node: Node) -> "Document":
        return Document(replace_node(self.root, node_id, new_node))

    def remove_node(self, node_id: str) -> "Document":
        return Document(remove_node(self.root, node_id))

    def insert_child(self, parent_id: str, child: Node, index: Optional[int] = None) -> "Document":
        return Document(insert_child(self.root, parent_id, child, index))

    def move_node(self, node_id: str, new_parent_id: str, index: Optional[int] = None) -> "Document":
        return Document(move_node(self.root, node_id, new_parent_id, index))


# --------------------------------------------------------------------------- #
# Pure tree transforms (structural sharing: unchanged subtrees are reused)
# --------------------------------------------------------------------------- #

def find(root: Node, node_id: str) -> Optional[Node]:
    return root.find(node_id)


def parent_of(root: Node, node_id: str) -> Optional[Node]:
    for n in root.iter():
        if any(c.id == node_id for c in n.children):
            return n
    return None


def path_to(root: Node, node_id: str) -> Optional[List[Node]]:
    """Ancestors-then-self path to ``node_id`` (root first), or None."""
    if root.id == node_id:
        return [root]
    for child in root.children:
        sub = path_to(child, node_id)
        if sub is not None:
            return [root] + sub
    return None


def update_node(root: Node, node_id: str, **changes) -> Node:
    """Return a tree where ``node_id``'s scalar fields are updated."""
    def rec(n: Node) -> Node:
        if n.id == node_id:
            return replace(n, **changes)
        if not n.children:
            return n
        new_children = tuple(rec(c) for c in n.children)
        if all(nc is oc for nc, oc in zip(new_children, n.children)):
            return n
        return replace(n, children=new_children)
    return rec(root)


def replace_node(root: Node, node_id: str, new_node: Node) -> Node:
    """Replace the whole subtree rooted at ``node_id`` with ``new_node``."""
    def rec(n: Node) -> Node:
        if n.id == node_id:
            return new_node
        if not n.children:
            return n
        new_children = tuple(rec(c) for c in n.children)
        if all(nc is oc for nc, oc in zip(new_children, n.children)):
            return n
        return replace(n, children=new_children)
    return rec(root)


def remove_node(root: Node, node_id: str) -> Node:
    """Return a tree with ``node_id`` removed (the root itself cannot be removed)."""
    if root.id == node_id:
        raise ValueError("cannot remove the root node")

    def rec(n: Node) -> Node:
        kept: List[Node] = []
        changed = False
        for c in n.children:
            if c.id == node_id:
                changed = True
                continue
            nc = rec(c)
            if nc is not c:
                changed = True
            kept.append(nc)
        if not changed:
            return n
        return replace(n, children=tuple(kept))
    return rec(root)


def update_nodes(root: Node, changes_by_id: Dict[str, Dict[str, Any]]) -> Node:
    """Batch ``update_node``: one bottom-up pass applying ``changes_by_id[id]`` (a
    ``replace`` kwargs dict) to every listed node. Only paths that contain a target are
    rebuilt (structural sharing), so k targets cost O(n), not O(k*n). Unknown ids are
    ignored, like ``update_node``."""
    if not changes_by_id:
        return root

    def rec(n: Node) -> Node:
        kids = n.children
        if kids:
            new_kids = tuple(rec(c) for c in kids)
            if all(nc is oc for nc, oc in zip(new_kids, kids)):
                new_kids = kids
        else:
            new_kids = kids
        ch = changes_by_id.get(n.id)
        if ch is not None:
            return replace(n, children=new_kids, **ch) if new_kids is not kids else replace(n, **ch)
        if new_kids is kids:
            return n
        return replace(n, children=new_kids)
    return rec(root)


def remove_nodes(root: Node, node_ids) -> Node:
    """Batch ``remove_node``: remove every id in ``node_ids`` in ONE pass (the root
    itself cannot be removed). Children of a removed node go with it."""
    ids = set(node_ids)
    if root.id in ids:
        raise ValueError("cannot remove the root node")
    if not ids:
        return root

    def rec(n: Node) -> Node:
        kept: List[Node] = []
        changed = False
        for c in n.children:
            if c.id in ids:
                changed = True
                continue
            nc = rec(c)
            if nc is not c:
                changed = True
            kept.append(nc)
        if not changed:
            return n
        return replace(n, children=tuple(kept))
    return rec(root)


def insert_children(root: Node, parent_id: str, children, index: Optional[int] = None) -> Node:
    """Batch ``insert_child``: insert ``children`` in order, the i-th at ``index + i``
    (each clamped like ``insert_child``; append when ``index`` is None), in ONE pass.
    Raises ``KeyError`` when ``parent_id`` does not exist."""
    children = list(children)
    found = [False]

    def rec(n: Node) -> Node:
        if n.id == parent_id:
            found[0] = True
            kids = list(n.children)
            for off, child in enumerate(children):
                idx = None if index is None else index + off
                at = len(kids) if idx is None else max(0, min(idx, len(kids)))
                kids.insert(at, child)
            return replace(n, children=tuple(kids))
        if not n.children:
            return n
        new_children = tuple(rec(c) for c in n.children)
        if all(nc is oc for nc, oc in zip(new_children, n.children)):
            return n
        return replace(n, children=new_children)
    out = rec(root)
    if not found[0]:
        raise KeyError(parent_id)
    return out


def insert_child(root: Node, parent_id: str, child: Node, index: Optional[int] = None) -> Node:
    """Insert ``child`` under ``parent_id`` at ``index`` (append if None).

    Raises ``KeyError`` when ``parent_id`` does not exist (I-1, QS 2026-11-04): the old
    silent no-op made the child VANISH — callers validate the parent today, but a future
    caller that forgets must fail loudly, not lose a node. (``update_node``'s no-op on a
    missing id is unchanged — fixed by tests as tolerated behaviour.)"""
    if find(root, parent_id) is None:
        raise KeyError(parent_id)

    def rec(n: Node) -> Node:
        if n.id == parent_id:
            kids = list(n.children)
            at = len(kids) if index is None else max(0, min(index, len(kids)))
            kids.insert(at, child)
            return replace(n, children=tuple(kids))
        if not n.children:
            return n
        new_children = tuple(rec(c) for c in n.children)
        if all(nc is oc for nc, oc in zip(new_children, n.children)):
            return n
        return replace(n, children=new_children)
    return rec(root)


def move_node(root: Node, node_id: str, new_parent_id: str, index: Optional[int] = None) -> Node:
    """Move ``node_id`` (with its subtree) under ``new_parent_id`` at ``index``."""
    node = find(root, node_id)
    if node is None:
        raise KeyError(node_id)
    if find(node, new_parent_id) is not None:
        raise ValueError("cannot move a node into itself or its own subtree")
    without = remove_node(root, node_id)
    return insert_child(without, new_parent_id, node, index)
