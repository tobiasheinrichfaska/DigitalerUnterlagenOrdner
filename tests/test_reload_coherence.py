"""Step A: committed nodes reload coherently (current_data=bytes, no original).

A "Lesbarkeit geprüft" node saves only its compressed result (the source is
dropped). On reload it must come back as current_data with NO original, so:
  * rendering still works (uses current_data),
  * re-compress is blocked (Compress guards on original_data) — no double compression,
  * reset is blocked (nothing to revert to),
  * the UI gets has_source=False.
Uncommitted nodes keep their original and stay fully editable.
"""

import os

import pytest

from helpers import create_valid_pdf
from core.model import Document, Node
from core.bridge import save_belegtool, load_belegtool
from core.commands import Compress, Reset, CommandError, apply
from core.engine import RealEngine


def _doc(tmp_path):
    orig = create_valid_pdf(pages=3)
    comp = create_valid_pdf(pages=2)  # smaller stand-in for the chosen compression
    committed = Node(name="committed", is_folder=False,
                     original_data=orig, current_data=comp,
                     is_compressed=True, compression_method="jpg",
                     dpi_current=150, pdf_length=2)
    uncommitted = Node(name="uncommitted", is_folder=False,
                       original_data=orig, pdf_length=3)
    doc = Document(Node(name="root", is_folder=True, children=(committed, uncommitted)))
    path = str(tmp_path / "doc.belegtool")
    save_belegtool(doc, path)
    return load_belegtool(path), path


def test_committed_reloads_as_current_no_original(tmp_path):
    doc, _ = _doc(tmp_path)
    committed = next(n for n in doc.root.children if n.name == "committed")
    assert committed.current_data, "compressed bytes must come back as current_data"
    assert committed.original_data is None, "source must be gone after commit+reload"
    assert committed.is_compressed
    assert committed.to_dict()["has_source"] is False


def test_uncommitted_keeps_source(tmp_path):
    doc, _ = _doc(tmp_path)
    un = next(n for n in doc.root.children if n.name == "uncommitted")
    assert un.original_data and un.current_data is None
    assert un.to_dict()["has_source"] is True


def test_recompress_blocked_on_reloaded_committed(tmp_path):
    doc, _ = _doc(tmp_path)
    committed = next(n for n in doc.root.children if n.name == "committed")
    with pytest.raises(CommandError):
        apply(doc, Compress(node_id=committed.id, dpi=150, method="jpg"), engine=RealEngine())


def test_reset_blocked_on_reloaded_committed(tmp_path):
    doc, _ = _doc(tmp_path)
    committed = next(n for n in doc.root.children if n.name == "committed")
    with pytest.raises(CommandError):
        apply(doc, Reset(node_id=committed.id), engine=RealEngine())


def test_render_still_works_for_committed(tmp_path):
    from core.api import CoreApi
    from core.session import DocumentSession
    doc, _ = _doc(tmp_path)
    committed = next(n for n in doc.root.children if n.name == "committed")
    api = CoreApi()
    api._sessions["s"] = DocumentSession(doc, engine=api._engine)
    r = api.render("s", committed.id, dpi=72)
    assert r["ok"] and len(r["pages"]) == 2  # renders from current_data
