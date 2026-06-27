"""DATEV provenance survives the model + .belegtool round-trip, and the SetDatev
command sets/clears it on the root (DATEV-mode in-app gate)."""

import fitz

from core.bridge import load_belegtool, save_belegtool
from core.commands import SetDatev, apply
from core.model import Document, Node

PROV = {"doc_guid": "fa89ad42-8cd4-4828-8234-143161d41985",
        "file_id": 1085411, "structure_item_id": 1085409, "source_name": "Rechnung.pdf"}


def _pdf(n=1):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=595, height=842).insert_text((50, 80), f"P{i}")
    b = d.tobytes()
    d.close()
    return b


def test_node_to_from_dict_roundtrips_datev():
    root = Node(name="root", is_folder=True, datev=PROV,
                children=(Node(name="leaf", original_data=_pdf()),))
    d = root.to_dict()
    assert d["datev"] == PROV
    back = Node.from_dict(d)
    assert back.datev == PROV
    # a non-root node carries None and round-trips as None
    assert back.children[0].datev is None


def test_belegtool_roundtrip_preserves_root_provenance(tmp_path):
    doc = Document(Node(name="root", is_folder=True, datev=PROV,
                        children=(Node(name="leaf", original_data=_pdf(2), pdf_length=2),)))
    path = str(tmp_path / "d.belegtool")
    save_belegtool(doc, path)
    back = load_belegtool(path)
    assert back.root.datev == PROV
    assert back.root.datev["doc_guid"] == PROV["doc_guid"]
    assert back.root.datev["file_id"] == 1085411


def test_belegtool_roundtrip_no_provenance_stays_none(tmp_path):
    doc = Document(Node(name="root", is_folder=True,
                        children=(Node(name="leaf", original_data=_pdf()),)))
    path = str(tmp_path / "d.belegtool")
    save_belegtool(doc, path)
    assert load_belegtool(path).root.datev is None


def test_set_datev_command_sets_and_clears_on_root():
    doc = Document(Node(name="root", is_folder=True,
                        children=(Node(name="leaf", original_data=_pdf()),)))
    connected = apply(doc, SetDatev(PROV))
    assert connected.root.datev == PROV
    assert connected.root.children[0].datev is None  # only the root carries it
    # Save As clears it
    disconnected = apply(connected, SetDatev(None))
    assert disconnected.root.datev is None
