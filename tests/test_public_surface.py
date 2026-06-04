"""Regression net for the upcoming structure refactors (see the 2026-06-04
structure audit). These lock the *observable* behaviour and the public import
surface so that moving/renaming/splitting modules (formats/, infra/, importers/,
core/ipc/, src/lib/) can only break loudly, never silently.

- `test_public_entry_points_import` documents the public surface. When a module
  legitimately moves, update the import here *and* fix every caller — if a caller
  is missed, the behavioural test below fails.
- The end-to-end `CoreApi` flow is import-path-agnostic at the call site: it
  drives import → save → reload → export through the façade, exercising the
  lazy internal imports in `core/api` that a careless move would break.
"""

import base64
import importlib
import io

import pytest
from pypdf import PdfWriter

from helpers import create_valid_pdf


# --- public import surface (update deliberately when a module moves) --------

PUBLIC_SURFACE = {
    "core.api": ["CoreApi"],
    "core.bridge": ["save_belegtool", "load_belegtool",
                    "document_to_storage", "document_from_storage"],
    "core.engine": ["RealEngine"],
    "core.model": ["Document", "Node", "STATUSES"],
    "core.commands": ["apply", "command_from_dict"],
    "pdf_storage": ["PDFStorage", "create_wrapper_node"],
    "pdf_node": ["PDFNode"],
    "toc_export": ["export_pdf_with_toc", "empty_leaf_names"],
    "compress_pdf_bytes": ["compress_all_methods", "compress_pdf_bytes"],
    "universal_importer": ["UniversalImporter", "extract_zip_to_structure",
                           "extract_email_to_structure"],
    "tasks": ["submit", "run_on_ui_thread"],
    "tools": ["sanitize_pdf"],
    "log_config": ["logger"],
}


@pytest.mark.parametrize("module, names", PUBLIC_SURFACE.items())
def test_public_entry_points_import(module, names):
    mod = importlib.import_module(module)
    for n in names:
        assert hasattr(mod, n), f"{module}.{n} is part of the public surface"


def test_headless_entry_points_import():
    # the GUI host and the CLI server entry import cleanly (no UI needed)
    importlib.import_module("host")
    importlib.import_module("core.server")
    importlib.import_module("core.cli")


# --- end-to-end behaviour through the façade (import-path-agnostic) ---------

def _b64_pdf(pages=2):
    return base64.b64encode(create_valid_pdf(pages=pages)).decode()


def _first_leaf(node):
    if not node.get("is_folder"):
        return node
    for c in node.get("children", []):
        hit = _first_leaf(c)
        if hit:
            return hit
    return None


def test_import_save_reload_export_roundtrip(tmp_path):
    from core.api import CoreApi
    api = CoreApi()
    opened = api.open()
    sid, root_id = opened["session"], opened["tree"]["id"]

    # import a PDF as bytes → a leaf appears
    r = api.import_bytes(sid, "smoke.pdf", _b64_pdf(2), parent_id=root_id)
    assert r["ok"], r
    leaf = _first_leaf(r["tree"])
    assert leaf is not None and leaf["name"].startswith("smoke")

    # render a page (exercises the engine path)
    rendered = api.render_window(sid, leaf["id"], 0, 1, 100)
    assert rendered["ok"] and len(rendered["pages"]) == 1

    # save .belegtool in place → reopen → structure survives
    out = tmp_path / "doc.belegtool"
    assert api.save(sid, str(out))["ok"] and out.exists()
    reopened = CoreApi().open(path=str(out))
    assert _first_leaf(reopened["tree"])["name"].startswith("smoke")

    # export the document to a PDF with TOC
    exp = tmp_path / "export.pdf"
    er = api.export(sid, str(exp), None)
    assert er["ok"] and exp.exists()
    assert exp.read_bytes().startswith(b"%PDF")


def test_belegtool_bridge_roundtrip(tmp_path):
    # the carrier path on its own (bridge → pdf_storage → pdf_node)
    from core.bridge import save_belegtool, load_belegtool
    from core.model import Document, Node

    doc = Document(Node(name="root", is_folder=True, children=(
        Node(name="a", pdf_length=1, no_compression=True,
             original_data=create_valid_pdf(pages=1)),
        Node(name="F", is_folder=True, children=(
            Node(name="b", pdf_length=2, no_compression=True,
                 original_data=create_valid_pdf(pages=2)),)),
    )))
    path = tmp_path / "x.belegtool"
    save_belegtool(doc, path)
    back = load_belegtool(path)
    assert [c.name for c in back.root.children] == ["a", "F"]
