"""Phase 2 of the file lock: the save→bytes pipeline must produce the same result as
the existing path-based save/embed (so the locked single-write path is faithful)."""

import io

import fitz
import pikepdf

from core.api import CoreApi
from core.bridge import document_to_storage
from services.variant_store import embed_variants, embed_variants_bytes


def _pdf(n=1):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=300, height=300).insert_text((40, 60), f"p{i}" * 20)
    b = d.tobytes()
    d.close()
    return b


def test_to_bytes_matches_save_on_disk(tmp_path):
    api = CoreApi()
    sid = api.open()["session"]
    p = str(tmp_path / "src.pdf")
    with open(p, "wb") as f:
        f.write(_pdf(2))
    api.import_paths(sid, [p])
    storage = document_to_storage(api._sessions[sid].document)

    on_disk = str(tmp_path / "viaSave.belegtool")
    storage.save(on_disk)
    with open(on_disk, "rb") as f:
        assert f.read() == storage.to_bytes()  # save() writes exactly to_bytes()


def _structure_and_attachments(data: bytes):
    with pikepdf.open(io.BytesIO(data)) as pdf:
        meta = pdf.open_metadata()  # noqa: F841 (smoke that it opens)
        names = sorted(n for n in pdf.attachments)
        pages = len(pdf.pages)
    return names, pages


def test_embed_variants_bytes_matches_path_embed(tmp_path):
    # one leaf with a seeded (real-PDF) variant → both embed paths attach the same blob
    api = CoreApi()
    sid = api.open()["session"]
    p = str(tmp_path / "src.pdf")
    with open(p, "wb") as f:
        f.write(_pdf(1))
    api.import_paths(sid, [p])
    leaf = next(n for n in api._sessions[sid].document.root.iter() if not n.is_folder)
    api._engine.seed_variants(leaf.original_data, {150: {"jpg": _pdf(1)}})
    doc = api._sessions[sid].document
    storage = document_to_storage(doc)
    base = storage.to_bytes()

    # path-based embed
    on_disk = str(tmp_path / "withvar.belegtool")
    with open(on_disk, "wb") as f:
        f.write(base)
    n_path = embed_variants(on_disk, doc, api._engine)
    with open(on_disk, "rb") as f:
        names_path, pages_path = _structure_and_attachments(f.read())

    # bytes-based embed
    out, n_bytes = embed_variants_bytes(base, doc, api._engine)
    names_bytes, pages_bytes = _structure_and_attachments(out)

    assert n_path == n_bytes == 1
    assert names_path == names_bytes              # same attachment keys (variant_<id>)
    assert pages_path == pages_bytes              # same page count
    assert any(nm.startswith("variant_") for nm in names_bytes)


def test_embed_variants_bytes_noop_without_variants(tmp_path):
    api = CoreApi()
    sid = api.open()["session"]
    p = str(tmp_path / "src.pdf")
    with open(p, "wb") as f:
        f.write(_pdf(1))
    api.import_paths(sid, [p])
    doc = api._sessions[sid].document
    base = document_to_storage(doc).to_bytes()
    out, n = embed_variants_bytes(base, doc, api._engine)
    assert n == 0 and out is base  # nothing to embed → unchanged input
