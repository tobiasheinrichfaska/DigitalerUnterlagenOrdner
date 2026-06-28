"""Unit tests for the in-process core façade (core/api.py) — no pipe, no GUI."""

import os

from core.api import CoreApi, sweep_stale_view_dirs
from core.bridge import save_belegtool
from core.model import Document, Node
from helpers import create_valid_pdf


def test_hello_creates_session():
    api = CoreApi()
    resp = api.hello()
    assert resp["ok"] and resp["session"] and "core_version" in resp


def test_open_empty_document():
    api = CoreApi()
    resp = api.open()
    assert resp["ok"] is True
    assert resp["tree"]["name"].startswith("Dokument") and resp["tree"]["children"] == []
    assert resp["can_undo"] is False and resp["can_redo"] is False


def test_open_belegtool(tmp_path):
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="doc1", pdf_length=1, no_compression=True,
             original_data=create_valid_pdf(pages=1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)

    resp = CoreApi().open(path=str(path))
    assert resp["ok"] is True
    assert [c["name"] for c in resp["tree"]["children"]] == ["doc1"]


def test_dispatch_undo_redo():
    api = CoreApi()
    opened = api.open()
    sid, root_id = opened["session"], opened["tree"]["id"]

    after = api.dispatch(sid, {"type": "AddFolder", "parent_id": root_id,
                               "name": "Neu", "index": None, "new_id": "f1"})
    assert [c["name"] for c in after["tree"]["children"]] == ["Neu"]
    assert after["can_undo"] is True

    assert api.undo(sid)["tree"]["children"] == []
    assert [c["name"] for c in api.redo(sid)["tree"]["children"]] == ["Neu"]


def test_dispatch_invalid_command_and_unknown_session():
    api = CoreApi()
    sid = api.open()["session"]
    bad = api.dispatch(sid, {"type": "Rename", "node_id": "missing", "name": "x"})
    assert bad["ok"] is False and "not found" in bad["error"]
    assert api.dispatch("nope", {"type": "Reset", "node_id": "x"})["ok"] is False


def test_independent_sessions():
    api = CoreApi()
    oa = api.open()
    a, a_root = oa["session"], oa["tree"]["id"]
    b = api.open()["session"]
    assert a != b and api.session_count() >= 2

    api.dispatch(a, {"type": "AddFolder", "parent_id": a_root,
                     "name": "X", "index": None, "new_id": "x"})
    # session a changed; session b is independent and still empty
    assert api.undo(b)["tree"]["children"] == []


def _doc_with_leaf(pages=1):
    return Document(Node(name="root", is_folder=True, children=(
        Node(name="doc1", pdf_length=pages, no_compression=True,
             original_data=create_valid_pdf(pages=pages)),
    )))


def test_render_leaf_returns_png_pages(tmp_path):
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_leaf(pages=2), path)
    api = CoreApi()
    opened = api.open(path=str(path))
    leaf_id = opened["tree"]["children"][0]["id"]
    resp = api.render(opened["session"], leaf_id)
    assert resp["ok"] is True and len(resp["pages"]) == 2
    assert resp["pages"][0].startswith("data:image/png;base64,")


def test_render_folder_is_empty_and_errors():
    api = CoreApi()
    opened = api.open()
    sid, root_id = opened["session"], opened["tree"]["id"]
    assert api.render(sid, root_id)["pages"] == []        # folder: no bytes
    assert api.render(sid, "missing")["ok"] is False
    assert api.render("nope", "x")["ok"] is False


def test_save_roundtrip(tmp_path):
    src = tmp_path / "src.belegtool"
    save_belegtool(_doc_with_leaf(pages=1), src)
    api = CoreApi()
    opened = api.open(path=str(src))
    sid, root_id = opened["session"], opened["tree"]["id"]
    api.dispatch(sid, {"type": "AddFolder", "parent_id": root_id,
                       "name": "G", "index": None, "new_id": "g"})
    out = tmp_path / "out.belegtool"
    assert api.save(sid, str(out))["ok"] is True and out.exists()

    reopened = CoreApi().open(path=str(out))
    assert {"doc1", "G"}.issubset({c["name"] for c in reopened["tree"]["children"]})


def test_materialize_subset_keeps_only_displayed_in_normal_order(tmp_path):
    # root → F[a, b], c ; a tag view displays F, a, c (b hidden) → expect F[a], c
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="F", is_folder=True, id="F", children=(
            Node(name="a", id="a", pdf_length=1, no_compression=True, original_data=create_valid_pdf(1)),
            Node(name="b", id="b", pdf_length=1, no_compression=True, original_data=create_valid_pdf(1)),
        )),
        Node(name="c", id="c", pdf_length=1, no_compression=True, original_data=create_valid_pdf(1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]

    res = api.materialize_subset(sid, ["F", "a", "c"], name="Spende - root")
    assert res["ok"] is True and res["count"] == 3 and res["path"].endswith(".belegtool")

    tree = CoreApi().open(path=res["path"])["tree"]
    assert tree["name"] == "Spende - root"  # new doc named: used tag prefixed onto old name
    # normal order preserved (F then c); the hidden sibling b is dropped
    assert [n["name"] for n in tree["children"]] == ["F", "c"]
    assert [n["name"] for n in tree["children"][0]["children"]] == ["a"]


def test_close_session_frees_session_state(tmp_path):
    # Closing a window must free its session — otherwise the document bytes + undo
    # log live for the process and its node ids keep blocking render-cache eviction.
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_leaf(pages=1), path)
    api = CoreApi()
    a = api.open(path=str(path))
    sid_a, leaf_id = a["session"], a["tree"]["children"][0]["id"]
    sid_b = api.open()["session"]
    api._pcount[(leaf_id, 0)] = 1  # simulate a prefetch-cached page count for the leaf
    assert any(k[0] == leaf_id for k in api._pcount)
    assert leaf_id in api._all_live_node_ids()

    assert api.close_session(sid_a)["ok"] is True
    assert sid_a not in api._sessions and sid_a not in api._paths
    assert leaf_id not in api._all_live_node_ids()        # node no longer counts as live
    assert not any(k[0] == leaf_id for k in api._pcount)  # page-count entries gone
    assert sid_b in api._sessions                          # other window untouched
    assert api.close_session(sid_a)["ok"] is True          # idempotent


def test_close_session_keeps_shared_uid_nodes_of_the_surviving_window(tmp_path):
    # Node uids persist in .belegtool, so the SAME file opened in two windows shares
    # node ids. Closing one window must not evict the survivor's state: its ids stay
    # live and its page-count cache entries are kept (the guard in close_session).
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_leaf(pages=1), path)
    api = CoreApi()
    a = api.open(path=str(path))
    b = api.open(path=str(path))  # same file → same persisted node uids
    sid_a, sid_b = a["session"], b["session"]
    leaf_a = a["tree"]["children"][0]["id"]
    leaf_b = b["tree"]["children"][0]["id"]
    assert sid_a != sid_b and leaf_a == leaf_b  # shared uid across both windows

    api._pcount[(leaf_a, 0)] = 1  # simulate a cached page count for the shared leaf
    assert api.close_session(sid_a)["ok"] is True

    assert leaf_b in api._all_live_node_ids()       # survivor's node still counts as live
    assert (leaf_b, 0) in api._pcount               # its page-count entry was NOT dropped
    assert sid_b in api._sessions                   # survivor session untouched
    # the survivor keeps working: rendering its leaf through the shared cache succeeds
    assert api.render(sid_b, leaf_b)["ok"] is True
    # closing the last window then really frees the shared state
    api.close_session(sid_b)
    assert leaf_b not in api._all_live_node_ids()
    assert not any(k[0] == leaf_b for k in api._pcount)


def test_materialized_view_tempdir_deleted_when_its_window_closes(tmp_path):
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="a", id="a", pdf_length=1, no_compression=True, original_data=create_valid_pdf(1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]
    res = api.materialize_subset(sid, ["a"], name="Ansicht")
    view_dir = os.path.dirname(res["path"])
    assert os.path.isdir(view_dir)
    # the new window opens the temp file → the dir binds to the NEW session …
    new_sid = api.open(path=res["path"])["session"]
    assert api._view_dirs.get(new_sid) == view_dir
    assert view_dir not in api._pending_view_dirs
    # … and closing that window deletes it
    api.close_session(new_sid)
    assert not os.path.exists(view_dir)


def test_binding_a_view_dir_refreshes_its_mtime_so_a_sweep_keeps_it(tmp_path):
    # Edge: a SECOND running instance's startup sweep deletes beleg_view_* dirs
    # older than 24 h. A live view dir's mtime used to stay at creation time, so a
    # window open >24 h could lose its dir. open() now touches the dir on bind.
    import time
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="a", id="a", pdf_length=1, no_compression=True, original_data=create_valid_pdf(1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]
    res = api.materialize_subset(sid, ["a"], name="Ansicht")
    view_dir = os.path.dirname(res["path"])

    # simulate the dir having been created >24 h ago (mtime = creation time)
    stale = time.time() - 2 * 24 * 3600
    os.utime(view_dir, (stale, stale))

    new_sid = api.open(path=res["path"])["session"]  # binding touches the mtime …
    assert api._view_dirs.get(new_sid) == view_dir
    assert time.time() - os.path.getmtime(view_dir) < 3600

    # … so another instance's sweep no longer considers it stale
    removed = sweep_stale_view_dirs(root=str(os.path.dirname(view_dir)))
    assert view_dir not in removed and os.path.isdir(view_dir)


def test_saving_through_a_view_dir_refreshes_its_mtime(tmp_path):
    import time
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="a", id="a", pdf_length=1, no_compression=True, original_data=create_valid_pdf(1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]
    res = api.materialize_subset(sid, ["a"], name="Ansicht")
    view_dir = os.path.dirname(res["path"])
    new_sid = api.open(path=res["path"])["session"]

    stale = time.time() - 2 * 24 * 3600
    os.utime(view_dir, (stale, stale))  # window has been open >24 h since the bind
    assert api.save(new_sid, res["path"])["ok"] is True  # in-place Speichern
    assert time.time() - os.path.getmtime(view_dir) < 3600  # sweep-safe again


def test_sweep_stale_view_dirs_removes_only_old_view_dirs(tmp_path):
    import time
    old = tmp_path / "beleg_view_old"
    old.mkdir()
    (old / "x.belegtool").write_bytes(b"x")
    fresh = tmp_path / "beleg_view_fresh"
    fresh.mkdir()
    other = tmp_path / "unrelated"
    other.mkdir()
    stale = time.time() - 3 * 24 * 3600
    os.utime(old, (stale, stale))

    removed = sweep_stale_view_dirs(root=str(tmp_path))
    assert str(old) in removed and not old.exists()  # stale view dir swept
    assert fresh.exists()                            # a possibly-live view is kept
    assert other.exists()                            # non-view dirs never touched


def test_materialize_subset_empty_selection_is_rejected():
    api = CoreApi()
    sid = api.open()["session"]
    assert api.materialize_subset(sid, [])["ok"] is False
    assert api.materialize_subset("nope", ["x"])["ok"] is False


def test_orphan_view_dir_swept_when_never_opened(tmp_path):
    # materialize_subset, but the new window never opens (open_session not called):
    # the temp dir + its _pending_view_dirs entry are orphaned. The instance sweep
    # removes the dir and keeps _pending_view_dirs consistent.
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="a", id="a", pdf_length=1, no_compression=True, original_data=create_valid_pdf(1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]
    res = api.materialize_subset(sid, ["a"], name="Ansicht")
    view_dir = os.path.dirname(res["path"])
    assert view_dir in api._pending_view_dirs and os.path.isdir(view_dir)

    removed = api.sweep_stale_view_dirs(root=os.path.dirname(view_dir), max_age_s=0)
    assert view_dir in removed
    assert not os.path.exists(view_dir)
    assert view_dir not in api._pending_view_dirs  # pending set stays consistent


def test_materialize_subset_rejects_reserved_basename(tmp_path):
    # A tag named like a Windows reserved device must not become a "CON.belegtool" path.
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="a", id="a", pdf_length=1, no_compression=True, original_data=create_valid_pdf(1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]
    res = api.materialize_subset(sid, ["a"], name="CON")
    assert res["ok"] and os.path.basename(res["path"]) == "Ansicht.belegtool"
    res2 = api.materialize_subset(sid, ["a"], name="  ...  ")
    assert res2["ok"] and os.path.basename(res2["path"]) == "Ansicht.belegtool"


def test_effective_version_token_changes_with_bytes():
    api = CoreApi()
    a = create_valid_pdf(1)
    n1 = Node(name="x", id="x", original_data=a)
    n2 = Node(name="x", id="x", original_data=bytes(a))  # identical content, new object
    _, v1 = api._effective(n1)
    _, v2 = api._effective(n2)
    assert v1 == v2  # same bytes → same token
    mutated = a + b"%mutated"
    n3 = Node(name="x", id="x", original_data=mutated)
    _, v3 = api._effective(n3)
    assert v3 != v1  # different bytes → different token


def test_export_pdf_with_toc(tmp_path):
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="A", pdf_length=1, original_data=create_valid_pdf(1)),
        Node(name="B", pdf_length=1, original_data=create_valid_pdf(1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]
    out = tmp_path / "Export.pdf"
    r = api.export(sid, str(out))
    assert r["ok"] and r["count"] == 2
    assert out.exists() and out.read_bytes().startswith(b"%PDF")
    assert "warning" not in r  # nothing skipped → no warning
    assert r["paths"] == [str(out)]  # single file by default


def test_export_split_writes_multiple_files(tmp_path):
    # 6 pages over a 3-page threshold → several part files, each a valid PDF (#13).
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="A", pdf_length=2, original_data=create_valid_pdf(2)),
        Node(name="B", pdf_length=2, original_data=create_valid_pdf(2)),
        Node(name="C", pdf_length=2, original_data=create_valid_pdf(2)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]
    out = tmp_path / "Export.pdf"
    r = api.export(sid, str(out), options={"split_pages": 3, "split_level": "top"})
    assert r["ok"] and len(r["paths"]) >= 2
    for p in r["paths"]:
        assert os.path.exists(p)
        with open(p, "rb") as f:
            assert f.read(4) == b"%PDF"


def test_export_no_split_when_under_threshold(tmp_path):
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="A", pdf_length=1, original_data=create_valid_pdf(1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]
    out = tmp_path / "Export.pdf"
    r = api.export(sid, str(out), options={"split_pages": 100, "split_level": "top"})
    assert r["ok"] and r["paths"] == [str(out)]  # below threshold → single file
    assert out.exists()


def test_export_split_refuses_overwrite_without_confirm(tmp_path):
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="A", pdf_length=2, original_data=create_valid_pdf(2)),
        Node(name="B", pdf_length=2, original_data=create_valid_pdf(2)),
        Node(name="C", pdf_length=2, original_data=create_valid_pdf(2)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]
    out = tmp_path / "Export.pdf"
    opts = {"split_pages": 3, "split_level": "top"}
    r1 = api.export(sid, str(out), options=opts)            # first run writes the parts
    assert r1["ok"] and len(r1["paths"]) >= 2
    r2 = api.export(sid, str(out), options=opts)            # parts exist → refused, nothing written
    assert r2["ok"] is False and r2["code"] == "exists" and r2["existing"]
    r3 = api.export(sid, str(out), options={**opts, "overwrite": True})  # confirmed → overwrites
    assert r3["ok"] and len(r3["paths"]) >= 2


def test_dirty_tracking_cleared_on_save(tmp_path):
    # per-session dirty flag (the host's close guard uses its own per-window flag)
    api = CoreApi()
    opened = api.open()
    sid, root_id = opened["session"], opened["tree"]["id"]
    assert api._sessions[sid].dirty is False
    api.dispatch(sid, {"type": "AddFolder", "parent_id": root_id, "name": "X", "index": None, "new_id": "x"})
    assert api._sessions[sid].dirty is True   # an edit makes it dirty (close should warn)
    api.save(sid, str(tmp_path / "d.belegtool"))
    assert api._sessions[sid].dirty is False  # saving clears it


def test_save_unknown_session(tmp_path):
    assert CoreApi().save("nope", str(tmp_path / "x.belegtool"))["ok"] is False


def _doc_with_compressible_leaf():
    return Document(Node(name="root", is_folder=True, children=(
        Node(name="doc1", pdf_length=1, original_data=create_valid_pdf(pages=1)),
    )))


def test_config_reports_default_dpi():
    resp = CoreApi().config()
    assert resp["ok"] is True and resp["default_dpi"] == 150


def test_render_compressed_is_read_only(tmp_path):
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_compressible_leaf(), path)
    api = CoreApi()
    opened = api.open(path=str(path))
    sid = opened["session"]
    leaf_id = opened["tree"]["children"][0]["id"]

    resp = api.render_compressed(sid, leaf_id, dpi=150)
    assert resp["ok"] is True and len(resp["pages"]) == 1
    assert resp["pages"][0].startswith("data:image/png;base64,")
    # crucially: the document was NOT mutated and no undo entry was created
    state = api.undo(sid)  # nothing to undo
    assert state["tree"]["children"][0]["is_compressed"] is False
    assert state["can_undo"] is False and state["can_redo"] is False


def test_import_paths_pdf_and_belegtool_with_undo(tmp_path):
    pdf = tmp_path / "rechnung.pdf"
    pdf.write_bytes(create_valid_pdf(pages=2))
    bt = tmp_path / "sammlung.belegtool"
    save_belegtool(_doc_with_leaf(pages=1), bt)

    api = CoreApi()
    sid = api.open()["session"]
    r = api.import_paths(sid, [str(pdf)], None)
    assert r["ok"] and [c["name"] for c in r["tree"]["children"]] == ["rechnung"]

    r2 = api.import_paths(sid, [str(bt)], None)
    assert "doc1" in [c["name"] for c in r2["tree"]["children"]]  # belegtool's child imported

    # one undoable step per import
    assert [c["name"] for c in api.undo(sid)["tree"]["children"]] == ["rechnung"]


def test_import_at_index_inserts_between(tmp_path):
    a = tmp_path / "a.pdf"; a.write_bytes(create_valid_pdf(1))
    b = tmp_path / "b.pdf"; b.write_bytes(create_valid_pdf(1))
    mid = tmp_path / "mid.pdf"; mid.write_bytes(create_valid_pdf(1))
    api = CoreApi()
    sid = api.open()["session"]
    api.import_paths(sid, [str(a)], None)
    api.import_paths(sid, [str(b)], None)
    r = api.import_paths(sid, [str(mid)], None, 1)
    assert [c["name"] for c in r["tree"]["children"]] == ["a", "mid", "b"]


def test_untitled_documents_get_numbered_names():
    api = CoreApi()
    assert api.open()["tree"]["name"] == "Dokument 1"
    assert api.open()["tree"]["name"] == "Dokument 2"  # process-wide counter


def test_opened_file_is_named_after_the_file(tmp_path):
    p = tmp_path / "Rechnungen 2024.belegtool"
    save_belegtool(_doc_with_leaf(pages=1), p)
    api = CoreApi()
    r = api.open(path=str(p))
    assert r["tree"]["name"] == "Rechnungen 2024"
    assert api.document_name(r["session"]) == "Rechnungen 2024"


def test_corrupt_archive_import_surfaces_archive_error(tmp_path):
    # a broken .zip must report the real cause, not fall through to an opaque "not a PDF"
    z = tmp_path / "kaputt.zip"
    z.write_bytes(b"PK\x03\x04 this is not a real zip archive")
    api = CoreApi()
    sid = api.open()["session"]
    r = api.import_paths(sid, [str(z)], None)
    assert r["ok"] is False
    assert "kaputt.zip" in r["error"] and "Archiv" in r["error"]


def test_friendly_import_error_for_unsupported_type(tmp_path):
    f = tmp_path / "daten.xyz"
    f.write_bytes(b"not a known format")
    api = CoreApi()
    sid = api.open()["session"]
    r = api.import_paths(sid, [str(f)], None)
    assert r["ok"] is False and "daten.xyz" in r["error"]


def test_import_sets_pdf_length_for_converted_files(tmp_path):
    # converted files (.md/images/Office) must get a real pdf_length — otherwise
    # count_node_pages()==0 drops them from the export TOC and misaligns page numbers.
    md = tmp_path / "notiz.md"
    md.write_text("# Titel\n\nHallo Welt\n", encoding="utf-8")
    api = CoreApi()
    sid = api.open()["session"]
    r = api.import_paths(sid, [str(md)], None)
    assert r["tree"]["children"][0]["pdf_length"] >= 1


def test_import_bytes_pdf(tmp_path):
    import base64
    api = CoreApi()
    sid = api.open()["session"]
    b64 = "data:application/pdf;base64," + base64.b64encode(create_valid_pdf(pages=1)).decode()
    r = api.import_bytes(sid, "scan.pdf", b64, None)
    assert r["ok"] and [c["name"] for c in r["tree"]["children"]] == ["scan"]


def test_import_into_selected_folder(tmp_path):
    pdf = tmp_path / "beleg.pdf"
    pdf.write_bytes(create_valid_pdf(pages=1))
    api = CoreApi()
    opened = api.open()
    sid, root_id = opened["session"], opened["tree"]["id"]
    folder = api.dispatch(sid, {"type": "AddFolder", "parent_id": root_id, "name": "Ordner", "index": None, "new_id": "f1"})
    assert folder["ok"]
    r = api.import_paths(sid, [str(pdf)], "f1")
    f = next(c for c in r["tree"]["children"] if c["id"] == "f1")
    assert [c["name"] for c in f["children"]] == ["beleg"]


def test_compress_options_survive_delete_undo(tmp_path):
    # Regression: dispatch(Delete) set the node's cancel token and nothing cleared
    # it on undo → every later compression aborted instantly and compress_options
    # returned [] forever (the "undecided" dot never resolved).
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_compressible_leaf(), path)
    api = CoreApi()
    opened = api.open(path=str(path))
    sid, leaf_id = opened["session"], opened["tree"]["children"][0]["id"]
    assert api.compress_options(sid, leaf_id, dpi=150)["options"]  # creates the token
    assert api.dispatch(sid, {"type": "Delete", "node_id": leaf_id})["ok"]
    assert api.undo(sid)["ok"]
    # different dpi → bypasses the engine memo, so a stale set token WOULD cancel
    assert api.compress_options(sid, leaf_id, dpi=100)["options"]


def test_delete_in_one_window_keeps_other_windows_compression(tmp_path):
    # Same file open twice → shared node uids. Deleting the node in window A must
    # not set the cancel token while window B still holds the node (the same
    # "still live elsewhere" guard close_session uses).
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_compressible_leaf(), path)
    api = CoreApi()
    a = api.open(path=str(path))
    b = api.open(path=str(path))
    leaf_id = a["tree"]["children"][0]["id"]
    assert api.compress_options(b["session"], leaf_id, dpi=150)["options"]
    assert api.dispatch(a["session"], {"type": "Delete", "node_id": leaf_id})["ok"]
    assert not api._cancel_tokens[leaf_id].is_set()  # B still owns the node
    assert api.compress_options(b["session"], leaf_id, dpi=100)["options"]


def test_failed_command_revives_cancel_tokens(tmp_path):
    # N2: dispatch SETS removed nodes' cancel tokens BEFORE the mutate; a command
    # that fails removed nothing, so the still-present node's token must be revived
    # (else its compress_options return [] until the next successful edit).
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_compressible_leaf(), path)
    api = CoreApi()
    opened = api.open(path=str(path))
    sid, leaf_id = opened["session"], opened["tree"]["children"][0]["id"]
    assert api.compress_options(sid, leaf_id, dpi=150)["options"]  # creates the token
    r = api.dispatch(sid, {"type": "Merge", "node_ids": [leaf_id]})  # < 2 nodes → fails
    assert r["ok"] is False
    assert leaf_id not in api._cancel_tokens or not api._cancel_tokens[leaf_id].is_set()
    assert api.compress_options(sid, leaf_id, dpi=100)["options"]  # not cancelled


def test_open_after_cross_window_delete_revives_token(tmp_path):
    # N3: delete WITHOUT save in window A sets the node's token (no other session
    # holds the uid); opening the same file in window B (uids persist) must revive
    # it, or the node is uncompressable in B until B's first edit.
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_compressible_leaf(), path)
    api = CoreApi()
    a = api.open(path=str(path))
    sid_a, leaf_id = a["session"], a["tree"]["children"][0]["id"]
    assert api.compress_options(sid_a, leaf_id, dpi=150)["options"]  # creates the token
    assert api.dispatch(sid_a, {"type": "Delete", "node_id": leaf_id})["ok"]
    assert api._cancel_tokens[leaf_id].is_set()  # gone everywhere → token set
    b = api.open(path=str(path))  # fresh window of the same file → same uid
    assert api.compress_options(b["session"], leaf_id, dpi=100)["options"]


def test_import_paths_revives_token_for_reimported_uid(tmp_path):
    # import_paths shares _revive_cancel_tokens with open() (only the open() edge is
    # locked by test_open_after_cross_window_delete_revives_token). A persisted uid
    # whose token is SET (deleted elsewhere) must come back compressible on re-import.
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_compressible_leaf(), path)
    api = CoreApi()
    a = api.open(path=str(path))
    sid_a, leaf_id = a["session"], a["tree"]["children"][0]["id"]
    assert api.compress_options(sid_a, leaf_id, dpi=150)["options"]  # creates the token
    assert api.dispatch(sid_a, {"type": "Delete", "node_id": leaf_id})["ok"]
    assert api._cancel_tokens[leaf_id].is_set()  # gone everywhere → token set
    # re-IMPORT the same file (uids persist) into a fresh window → token must revive
    b = api.open()["session"]
    assert api.import_paths(b, [str(path)])["ok"]
    assert leaf_id not in api._cancel_tokens  # revived (dropped), not left set
    assert api.compress_options(b, leaf_id, dpi=100)["options"]


def test_close_session_prunes_view_touched_entry(tmp_path):
    # A materialized tag view binds its temp dir to the new window's session; render
    # traffic records a keep-alive timestamp in _view_touched. close_session must drop
    # BOTH the view-dir binding and its keep-alive entry (no leak across closes).
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_leaf(pages=1), path)
    api = CoreApi()
    opened = api.open(path=str(path))
    sid, leaf_id = opened["session"], opened["tree"]["children"][0]["id"]
    res = api.materialize_subset(sid, [leaf_id], name="Ansicht")
    assert res["ok"]
    view_sid = api.open(path=res["path"])["session"]
    view_dir = api._view_dirs[view_sid]
    api._view_touched[view_dir] = 123.0  # as a render-traffic keep-alive touch would
    assert api.close_session(view_sid)["ok"]
    assert view_sid not in api._view_dirs
    assert view_dir not in api._view_touched  # pruned on close


def test_count_for_is_safe_against_concurrent_close_session(tmp_path, monkeypatch):
    # Regression: _count_for inserted into _pcount unlocked while close_session
    # iterated it under the lock → RuntimeError (swallowed by the host) → silent
    # session leak. Hammer both concurrently; nothing may raise and the closed
    # session's entries must be gone.
    import threading
    from services import render as render_mod
    monkeypatch.setattr(render_mod, "page_count", lambda data: 1)
    api = CoreApi()
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_leaf(pages=1), path)
    errors = []

    def hammer():
        try:
            for i in range(4000):
                api._count_for(f"x{i}", 0, b"%PDF-fake")
        except Exception as e:  # pragma: no cover - only on regression
            errors.append(e)

    t = threading.Thread(target=hammer)
    t.start()
    for _ in range(20):
        sid = api.open(path=str(path))["session"]
        leaf = api._sessions[sid].document.root.children[0]
        api._pcount[(leaf.id, 0)] = 1
        assert api.close_session(sid)["ok"]
    t.join()
    assert errors == []


def test_undo_redo_prune_render_cache_and_kick_prewarm():
    # undo/redo must run the same post-mutate cache hygiene as dispatch
    class StubRenderer:
        def __init__(self):
            self.pruned, self.prefetched = 0, 0

        def prune(self, ids):
            self.pruned += 1

        def prefetch(self, build, dpi, pause_if=None):
            self.prefetched += 1

    api = CoreApi()
    stub = api._render_service = StubRenderer()
    opened = api.open()
    sid, root_id = opened["session"], opened["tree"]["id"]
    api.dispatch(sid, {"type": "AddFolder", "parent_id": root_id,
                       "name": "X", "index": None, "new_id": "x"})
    base = stub.pruned
    assert api.undo(sid)["ok"] and stub.pruned == base + 1
    assert api.redo(sid)["ok"] and stub.pruned == base + 2


def test_render_window_touches_a_stale_view_dir(tmp_path):
    # A view window open >24 h WITHOUT saving must stay sweep-safe: rendering
    # refreshes the dir's mtime (rate-limited keep-alive).
    import time
    from core.model import Document, Node
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="a", id="a", pdf_length=1, no_compression=True, original_data=create_valid_pdf(1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)
    api = CoreApi()
    sid = api.open(path=str(path))["session"]
    res = api.materialize_subset(sid, ["a"], name="Ansicht")
    view_dir = os.path.dirname(res["path"])
    new_sid = api.open(path=res["path"])["session"]

    stale = time.time() - 2 * 24 * 3600
    os.utime(view_dir, (stale, stale))     # window has been open >24 h, never saved
    api._view_touched.pop(view_dir, None)  # interval elapsed → next render touches
    assert api.render_window(new_sid, "a", 0, 1)["ok"]
    assert time.time() - os.path.getmtime(view_dir) < 3600  # sweep-safe again


def test_compress_options_lists_methods_smallest_first(tmp_path):
    path = tmp_path / "s.belegtool"
    save_belegtool(_doc_with_leaf(pages=1), path)
    api = CoreApi()
    opened = api.open(path=str(path))
    leaf_id = opened["tree"]["children"][0]["id"]
    resp = api.compress_options(opened["session"], leaf_id, dpi=150)
    assert resp["ok"] is True and resp["original_size"] > 0
    sizes = [o["size"] for o in resp["options"]]
    assert len(sizes) >= 1 and sizes == sorted(sizes)            # best = options[0]
    assert all(s < resp["original_size"] for s in sizes)        # all beat the original
    assert resp["options"][0]["method"]                          # method name present


# --- _version_of memo cache (F-2: thread-safe, LRU-bounded) ----------------
import zlib


def test_version_of_memoizes_and_matches_crc32():
    api = CoreApi()
    data = b"%PDF-1.7\nsome bytes"
    v1 = api._version_of(data)
    assert v1 == zlib.crc32(data)
    assert api._version_of(data) == v1            # cache hit, same object identity
    assert api._vcache[id(data)] == (data, v1)    # held so id() can't be reused


def test_version_of_lru_bound_holds():
    api = CoreApi()
    # Keep references so ids stay alive; the cache must still cap at 64 entries.
    blobs = [f"doc-{i}".encode() for i in range(200)]
    for b in blobs:
        api._version_of(b)
    assert len(api._vcache) <= 64


def test_version_of_is_thread_safe_under_contention():
    # F-2: page_count (caller thread) and the prefetch worker both call _version_of.
    # Hammer it from many threads on shared + distinct data; the locked get/move/set/
    # popitem sequence must never raise and must return the correct crc each time.
    import threading

    api = CoreApi()
    shared = b"shared-payload"
    shared_crc = zlib.crc32(shared)
    errors = []

    def worker(seed):
        try:
            for i in range(300):
                assert api._version_of(shared) == shared_crc
                d = f"t{seed}-{i}".encode()
                assert api._version_of(d) == zlib.crc32(d)
        except Exception as e:  # any KeyError/race surfaces here
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(s,)) for s in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(api._vcache) <= 64
