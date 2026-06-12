"""Compression variants persist in the .belegtool (embedded per-node attachments)
and are rehydrated into the engine on reopen — no recompute."""

import fitz

from core.api import CoreApi
from core.engine import RealEngine
from services import variant_blobs


def _make_pdf(n=2):
    doc = fitz.open()
    for i in range(n):
        p = doc.new_page(width=595, height=842)
        p.insert_text((50, 90), f"Seite {i + 1} " * 40)
    data = doc.tobytes()
    doc.close()
    return data


def test_variant_blobs_roundtrip():
    v = {150: {"jpg": b"AAA", "png": b"BBB"}, 100: {"jpg": b"CCC"}}
    assert variant_blobs.unpack(variant_blobs.pack(v)) == v
    assert variant_blobs.unpack(b"not a zip") == {}  # robust to garbage


def test_engine_seed_serves_without_recompute():
    eng = RealEngine()
    src = _make_pdf()
    eng.seed_variants(src, {150: {"jpg": b"X", "png": b"YY"}})
    assert eng.compress_methods(src, 150) == {"jpg": 1, "png": 2}  # from persisted layer
    assert eng.variants_for(src) == {150: {"jpg": b"X", "png": b"YY"}}


def _first_leaf(tree):
    if not tree.get("is_folder"):
        return tree
    for c in tree.get("children", []):
        r = _first_leaf(c)
        if r:
            return r
    return None


def test_save_reload_persists_variants(tmp_path):
    pdf_path = tmp_path / "src.pdf"
    pdf_path.write_bytes(_make_pdf(2))
    bel = str(tmp_path / "doc.belegtool")

    # build a document with one imported node, seed it with (fake) variants, save
    api = CoreApi()
    sid = api.open()["session"]
    resp = api.import_paths(sid, [str(pdf_path)])
    node = _first_leaf(resp["tree"])
    assert node is not None
    src = api._sessions[sid].document.find(node["id"]).original_data
    api._engine.seed_variants(src, {150: {"jpg": b"VARIANT-JPG", "pikepdf": b"VARIANT-PK"}})
    assert api.save(sid, bel)["ok"]

    # reopen in a FRESH engine → variants must be back, keyed to the reloaded source
    api2 = CoreApi()
    sid2 = api2.open(path=bel)["session"]
    reloaded = api2._sessions[sid2].document
    leaf = next(n for n in reloaded.root.iter() if not n.is_folder and n.original_data)
    got = api2._engine.variants_for(leaf.original_data)
    assert got == {150: {"jpg": b"VARIANT-JPG", "pikepdf": b"VARIANT-PK"}}


def test_no_variants_means_no_attachment(tmp_path):
    import pikepdf
    pdf_path = tmp_path / "src.pdf"
    pdf_path.write_bytes(_make_pdf(2))
    bel = str(tmp_path / "doc.belegtool")
    api = CoreApi()
    sid = api.open()["session"]
    api.import_paths(sid, [str(pdf_path)])  # no compression browsed → no variants
    api.save(sid, bel)
    with pikepdf.open(bel) as pdf:
        assert not any(str(n).startswith("variant_") for n in pdf.attachments)


def test_engine_variants_auto_invalidate_on_content_change():
    eng = RealEngine()
    src = _make_pdf(2)
    eng.seed_variants(src, {150: {"jpg": b"X"}})
    assert eng.variants_for(src)                 # present for the seeded source
    assert eng.variants_for(_make_pdf(3)) == {}  # different bytes (an edit) → no stale hit


def test_document_path_is_remembered(tmp_path):
    bel = str(tmp_path / "doc.belegtool")
    api = CoreApi()
    sid = api.open()["session"]
    assert api.document_path(sid) is None       # a fresh doc has no path → Save prompts
    api.save(sid, bel)
    assert api.document_path(sid) == bel         # after a save, Speichern saves in place
    api2 = CoreApi()
    sid2 = api2.open(path=bel)["session"]
    assert api2.document_path(sid2) == bel        # opening binds the path too


def _seed_one_variant(api, sid):
    """Seed a (fake) compression alternative on the first leaf; return its source."""
    src = next(n for n in api._sessions[sid].document.root.iter()
               if not n.is_folder and n.original_data).original_data
    api._engine.seed_variants(src, {150: {"jpg": b"VARIANT-JPG"}})
    return src


def test_save_info_detects_alternatives(tmp_path):
    pdf_path = tmp_path / "src.pdf"
    pdf_path.write_bytes(_make_pdf(2))
    api = CoreApi()
    sid = api.open()["session"]
    api.import_paths(sid, [str(pdf_path)])
    # nothing computed yet → no alternatives to store, no dialog
    assert api.save_info(sid) == {"ok": True, "has_alternatives": False, "count": 0}
    # a computed variant appears → the save dialog should be offered
    _seed_one_variant(api, sid)
    info = api.save_info(sid)
    assert info["ok"] and info["has_alternatives"] is True and info["count"] == 1


def test_applied_compression_offers_no_alternatives(tmp_path):
    """Once a node's compression is applied ("Lesbarkeit geprüft" → Compress), its
    other alternatives are dead (source dropped on save, re-compress blocked) → the
    save dialog must NOT be offered and nothing is embedded for it. Regression: a
    fully-committed document used to still prompt because the source is retained
    in memory until save and the variant memo was keyed off it."""
    import pikepdf
    pdf_path = tmp_path / "src.pdf"
    pdf_path.write_bytes(_make_pdf(2))
    api = CoreApi()
    sid = api.open()["session"]
    api.import_paths(sid, [str(pdf_path)])
    leaf = next(n for n in api._sessions[sid].document.root.iter()
                if not n.is_folder and n.original_data)
    variant_pdf = _make_pdf(1)  # a real PDF so the applied bytes can be saved as a page
    api._engine.seed_variants(leaf.original_data, {150: {"jpg": variant_pdf}})

    # uncommitted node with a computed alternative → the dialog IS offered
    assert api.save_info(sid)["has_alternatives"] is True

    # apply the compression (uses the seeded variant deterministically) → is_compressed
    assert api.dispatch(sid, {"type": "Compress", "node_id": leaf.id,
                              "dpi": 150, "method": "jpg"})["ok"]

    # now compressed → no live alternatives to offer or embed
    assert api.save_info(sid) == {"ok": True, "has_alternatives": False, "count": 0}
    bel = str(tmp_path / "out.belegtool")
    assert api.save(sid, bel, store_alternatives=True)["ok"]
    with pikepdf.open(bel) as pdf:
        assert not any(str(n).startswith("variant_") for n in pdf.attachments)


def test_save_without_alternatives_skips_embed(tmp_path):
    import pikepdf
    pdf_path = tmp_path / "src.pdf"
    pdf_path.write_bytes(_make_pdf(2))
    api = CoreApi()
    sid = api.open()["session"]
    api.import_paths(sid, [str(pdf_path)])
    _seed_one_variant(api, sid)

    # 'Original speichern' → no variant_ attachments despite a pending variant
    plain = str(tmp_path / "plain.belegtool")
    assert api.save(sid, plain, store_alternatives=False)["ok"]
    with pikepdf.open(plain) as pdf:
        assert not any(str(n).startswith("variant_") for n in pdf.attachments)

    # 'Wie geplant speichern' (default) → the alternative IS embedded
    full = str(tmp_path / "full.belegtool")
    assert api.save(sid, full, store_alternatives=True)["ok"]
    with pikepdf.open(full) as pdf:
        assert any(str(n).startswith("variant_") for n in pdf.attachments)


def test_unpack_rejects_deflate_bomb_without_allocating_it():
    # A hostile blob declares small but inflates on read. With the actual-read cap
    # the bomb is detected after at most cap+1 bytes — the whole blob is discarded.
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("150/jpg", b"\0" * (1024 * 1024))  # ~1 KB compressed, 1 MB unpacked
    assert variant_blobs.unpack(buf.getvalue(), max_total_bytes=1024) == {}


def test_unpack_running_total_cap_spans_entries():
    blob = variant_blobs.pack({150: {"jpg": b"a" * 600, "png": b"b" * 600}})
    assert variant_blobs.unpack(blob, max_total_bytes=1000) == {}    # 600+600 > 1000
    assert variant_blobs.unpack(blob, max_total_bytes=2000) != {}    # within budget


def test_unpack_rejects_too_many_entries():
    blob = variant_blobs.pack({150: {f"m{i}": b"x" for i in range(5)}})
    assert variant_blobs.unpack(blob, max_entries=4) == {}
    assert len(variant_blobs.unpack(blob, max_entries=5)[150]) == 5


def test_seed_variants_from_file_caps_attachment_count(tmp_path, monkeypatch):
    # More variant_* attachments than the cap → only the cap is processed on open.
    from services import variant_store
    pdf_a = tmp_path / "a.pdf"; pdf_a.write_bytes(_make_pdf(1))
    pdf_b = tmp_path / "b.pdf"; pdf_b.write_bytes(_make_pdf(2))
    bel = str(tmp_path / "doc.belegtool")
    api = CoreApi()
    sid = api.open()["session"]
    api.import_paths(sid, [str(pdf_a)])
    api.import_paths(sid, [str(pdf_b)])
    for n in api._sessions[sid].document.root.iter():
        if not n.is_folder and n.original_data:
            api._engine.seed_variants(n.original_data, {150: {"jpg": b"V-" + n.id.encode()}})
    assert api.save(sid, bel)["ok"]

    monkeypatch.setattr(variant_store, "MAX_ATTACHMENTS", 1)
    from core.bridge import load_belegtool
    eng = RealEngine()
    document = load_belegtool(bel)
    seeded = variant_store.seed_variants_from_file(bel, document, eng)
    assert seeded == 1  # capped (2 attachments exist in the file)


def test_node_id_survives_save_reload(tmp_path):
    pdf_path = tmp_path / "src.pdf"
    pdf_path.write_bytes(_make_pdf(1))
    bel = str(tmp_path / "doc.belegtool")
    api = CoreApi()
    sid = api.open()["session"]
    resp = api.import_paths(sid, [str(pdf_path)])
    saved_id = _first_leaf(resp["tree"])["id"]
    api.save(sid, bel)
    api2 = CoreApi()
    sid2 = api2.open(path=bel)["session"]
    leaf = next(n for n in api2._sessions[sid2].document.root.iter() if not n.is_folder)
    assert leaf.id == saved_id  # uid persisted → attachments match
