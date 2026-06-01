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

# Status values (mirror the Tk app).
STATUS_DONE = "erfasst"
STATUS_TODO = "zu erfassen"
STATUS_PRIOR_YEAR = "vorjahreswert"
STATUSES = (STATUS_DONE, STATUS_TODO, STATUS_PRIOR_YEAR)


def new_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class Node:
    """An immutable tree node (folder or leaf document)."""

    name: str
    is_folder: bool = False
    id: str = field(default_factory=new_id)
    status: str = STATUS_TODO
    vz_start: Optional[int] = None
    vz_end: Optional[int] = None
    pdf_length: int = 0
    is_compressed: bool = False
    dpi_original: Optional[int] = None
    dpi_current: Optional[int] = None
    no_compression: bool = False
    children: Tuple["Node", ...] = ()
    original_data: Optional[bytes] = None
    current_data: Optional[bytes] = None
    compression_method: Optional[str] = None  # jpg/png/pikepdf chosen for current_data; None = none/auto

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
            "compression_method": self.compression_method,
            "children": [c.to_dict(i) for i, c in enumerate(self.children)],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Node":
        return cls(
            name=d["name"],
            is_folder=d.get("is_folder", False),
            id=d.get("id") or new_id(),
            status=d.get("status", STATUS_TODO),
            vz_start=d.get("vz_start"),
            vz_end=d.get("vz_end"),
            pdf_length=d.get("pdf_length", 0),
            is_compressed=d.get("is_compressed", False),
            dpi_original=d.get("dpi_original"),
            dpi_current=d.get("dpi_current"),
            no_compression=d.get("no_compression", False),
            compression_method=d.get("compression_method"),
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


def insert_child(root: Node, parent_id: str, child: Node, index: Optional[int] = None) -> Node:
    """Insert ``child`` under ``parent_id`` at ``index`` (append if None)."""
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
