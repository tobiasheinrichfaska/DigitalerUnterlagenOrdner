"""End-to-end .belegtool round-trip fidelity. Locks down the PDFNode/PDFStorage I/O
path (the part the app actually uses) so a future data-model cleanup of the dead
preview machinery cannot silently break load/save."""

import fitz

from core.model import Document, Node
from core.bridge import load_belegtool, save_belegtool


def _pdf(n):
    d = fitz.open()
    for i in range(n):
        p = d.new_page(width=595, height=842)
        p.insert_text((50, 80), f"Page {i + 1}")
    b = d.tobytes()
    d.close()
    return b


def _build_doc():
    plain = Node(name="plain", original_data=_pdf(3), pdf_length=3,
                 status="zu erfassen", vz_start=2023, vz_end=2024, tags=("Steuer", "2023"))
    comp = Node(name="comp", original_data=_pdf(1), current_data=_pdf(1),
                is_compressed=True, compression_method="jpg", dpi_current=150,
                dpi_original=300, pdf_length=1, status="erfasst")
    nocomp = Node(name="nocomp", original_data=_pdf(2), pdf_length=2,
                  no_compression=True, status="vorjahreswert")
    sub = Node(name="sub", is_folder=True, collapsed=True, children=(comp, nocomp))
    folder = Node(name="folder", is_folder=True, children=(plain, sub), tags=("Belege",))
    return Document(Node(name="root", is_folder=True, children=(folder,)))


def test_belegtool_roundtrip_fidelity(tmp_path):
    doc = _build_doc()
    path = str(tmp_path / "d.belegtool")
    save_belegtool(doc, path)
    back = load_belegtool(path)

    by_name = {n.name: n for n in back.root.iter()}

    # structure preserved
    assert [n.name for n in back.root.children[0].children] == ["plain", "sub"]
    assert by_name["folder"].is_folder and by_name["sub"].is_folder
    assert by_name["sub"].collapsed is True            # collapse persists
    assert by_name["folder"].collapsed is False

    # ids survive (needed for variant attachments to match)
    saved_ids = {n.name: n.id for n in doc.root.iter()}
    for name, node in by_name.items():
        assert node.id == saved_ids[name], f"id of {name} not preserved"

    # leaf fields
    pl = by_name["plain"]
    assert (pl.status, pl.vz_start, pl.vz_end, pl.pdf_length) == ("zu erfassen", 2023, 2024, 3)
    assert pl.is_compressed is False and pl.original_data and pl.current_data is None

    nc = by_name["nocomp"]
    assert nc.no_compression is True and nc.status == "vorjahreswert" and nc.pdf_length == 2

    # tags persist on both a leaf and a folder
    assert by_name["plain"].tags == ("Steuer", "2023")
    assert by_name["folder"].tags == ("Belege",)

    cm = by_name["comp"]
    assert cm.is_compressed is True and cm.compression_method == "jpg"
    assert cm.dpi_current == 150 and cm.status == "erfasst" and cm.pdf_length == 1
    # committed-on-save: the source is dropped, the compressed bytes become the effective
    assert cm.current_data and cm.original_data is None


def test_belegtool_roundtrip_is_stable(tmp_path):
    """A second save/reload of the reloaded document keeps the same structure + ids."""
    p1 = str(tmp_path / "a.belegtool")
    p2 = str(tmp_path / "b.belegtool")
    save_belegtool(_build_doc(), p1)
    once = load_belegtool(p1)
    save_belegtool(once, p2)
    twice = load_belegtool(p2)
    sig = lambda d: [(n.name, n.is_folder, n.id, n.pdf_length) for n in d.root.iter()]
    assert sig(once) == sig(twice)
