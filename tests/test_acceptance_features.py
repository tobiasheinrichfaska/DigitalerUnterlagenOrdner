# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Black-box ACCEPTANCE tests for every numbered feature of FEATURES_REQUIRED.md.

Everything goes through ``CoreApi`` -- the same calls ``HostApi`` / the SPA make -- and asserts the
OBSERVABLE outcome the acceptance bullet states (tree shape, dirty flag, files on disk, what DATEV
was sent), never an implementation detail.  Windows COM modules are stubbed so this runs anywhere;
DATEV runs against a fake client / fake service (no network).

UI-only bullets (cannot be asserted without a browser) are listed at the bottom with the manual test
or the vitest/Playwright suite that covers them.
"""
import base64
import io
import os
import sys
import threading
import time
import types
import zipfile
from email.message import EmailMessage

import pytest

for _m in ("pythoncom", "win32com", "win32com.client"):
    if _m not in sys.modules:
        try:
            __import__(_m)
        except ImportError:
            sys.modules[_m] = types.ModuleType(_m)
if not hasattr(sys.modules["win32com"], "client"):
    sys.modules["win32com"].client = sys.modules["win32com.client"]

import fitz  # noqa: E402  (test-only PDF generator / oracle)
import pikepdf  # noqa: E402
from PIL import Image  # noqa: E402

from core.api import CoreApi  # noqa: E402
from core.bridge import load_belegtool, save_belegtool  # noqa: E402
from core.model import Document, Node  # noqa: E402

HERE = os.path.dirname(__file__)
COMPRESS_SAMPLE = os.path.join(HERE, "data", "input", "compress_sample.pdf")  # 2 pages, 672 KB scan
GUID = "0a0a0a01-0000-4000-8000-000000000001"


# --------------------------------------------------------------------------- helpers
def _pdf(n=1, tag="S", size=(300, 300)):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=size[0], height=size[1]).insert_text((40, 60), f"{tag}-{i + 1} " * 20)
    b = d.tobytes()
    d.close()
    return b


def _labelled(n, tag):
    """n pages, each carrying a unique text label ``<tag>p<i>`` (to check order / content)."""
    d = fitz.open()
    for i in range(n):
        d.new_page(width=300, height=300).insert_text((40, 80), f"{tag}p{i + 1}")
    b = d.tobytes()
    d.close()
    return b


def _pages(data):
    with fitz.open(stream=data, filetype="pdf") as d:
        return d.page_count


def _text(data, page):
    with fitz.open(stream=data, filetype="pdf") as d:
        return d[page].get_text()


def _put(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def _flat(tree, out=None, parent=None):
    out = {} if out is None else out
    out[tree["id"]] = dict(tree, _parent=parent)
    for c in tree["children"]:
        _flat(c, out, tree["id"])
    return out


def _by_name(resp, name):
    hits = [n for n in _flat(resp["tree"]).values() if n["name"] == name]
    assert hits, f"no node {name!r} in {[n['name'] for n in _flat(resp['tree']).values()]}"
    return hits[0]


def _leaves(tree):
    return [n for n in _flat(tree).values() if not n["is_folder"]]


def _names(tree):
    return [c["name"] for c in tree["children"]]


class Win:
    """One window: a CoreApi session plus tiny conveniences (what App.jsx does)."""

    def __init__(self, api=None, path=None):
        self.api = api or CoreApi()
        r = self.api.open(path=path)
        assert r["ok"], r
        self.sid = r["session"]
        self.last = r

    @property
    def tree(self):
        return self.last["tree"]

    def d(self, **cmd):
        r = self.api.dispatch(self.sid, cmd)
        if r.get("ok"):
            self.last = r
        return r

    def undo(self):
        r = self.api.undo(self.sid)
        if r.get("ok"):
            self.last = r
        return r

    def redo(self):
        r = self.api.redo(self.sid)
        if r.get("ok"):
            self.last = r
        return r

    def imp(self, tmp_path, name, data, parent_id=None, index=None):
        before = set(_flat(self.tree))
        r = self.api.import_paths(self.sid, [_put(tmp_path, name, data)], parent_id, index)
        assert r["ok"], r
        self.last = r
        return [n for i, n in _flat(r["tree"]).items() if i not in before]

    def leaf(self, tmp_path, name, pages=1, parent_id=None, **kw):
        (n,) = self.imp(tmp_path, name + ".pdf", kw.pop("data", None) or _labelled(pages, name), parent_id)
        return n["id"]

    def folder(self, name, parent_id=None):
        r = self.d(type="AddFolder", parent_id=parent_id or self.tree["id"], name=name)
        assert r["ok"], r
        return _by_name(r, name)["id"]

    def save(self, path, **kw):
        r = self.api.save(self.sid, path, **kw)
        assert r["ok"], r
        self.last = self.api.get_state(self.sid) if hasattr(self.api, "get_state") else self.last
        return r

    def node(self, nid):
        return _flat(self.last["tree"])[nid]

    def doc(self):
        return self.api._sessions[self.sid].document


def _wait(cond, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


# =========================================================================== 1. Import -> tree
class TestImport:
    def test_pdf_becomes_leaf_under_selected_folder_and_marks_dirty(self, tmp_path):
        w = Win()
        assert w.last["dirty"] is False
        f = w.folder("Bank")
        (n,) = w.imp(tmp_path, "Kontoauszug.pdf", _pdf(2), parent_id=f)
        assert n["_parent"] == f and n["pdf_length"] == 2 and not n["is_folder"]
        assert w.last["dirty"] is True and w.last["can_undo"] is True

    def test_import_without_target_lands_under_root_and_index_is_honoured(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        b = w.leaf(tmp_path, "b")
        (c,) = w.imp(tmp_path, "c.pdf", _pdf(1), index=0)
        assert [x["id"] for x in w.tree["children"]][0] == c["id"]
        assert _names(w.tree) == ["c", "a", "b"] and {a, b} <= set(_flat(w.tree))

    def test_import_into_a_leaf_target_falls_back_to_root(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        (n,) = w.imp(tmp_path, "z.pdf", _pdf(1), parent_id=a)
        assert n["_parent"] == w.tree["id"]

    def test_import_is_undoable_in_one_step(self, tmp_path):
        w = Win()
        w.imp(tmp_path, "x.pdf", _pdf(1))
        assert w.undo()["tree"]["children"] == []
        assert w.last["dirty"] is False

    def test_belegtool_import_restores_its_whole_tree(self, tmp_path):
        src = Win()
        f = src.folder("Ordner")
        src.leaf(tmp_path, "inner", 2, parent_id=f)
        src.leaf(tmp_path, "outer", 1)
        p = str(tmp_path / "src.belegtool")
        src.save(p)
        dst = Win()
        r = dst.api.import_paths(dst.sid, [p])
        assert r["ok"]
        assert _names(r["tree"]) == ["Ordner", "outer"]
        assert _names(_by_name(r, "Ordner")) == ["inner"]
        assert _by_name(r, "inner")["pdf_length"] == 2

    def test_images_convert_to_pdf_leaves(self, tmp_path):
        w = Win()
        for ext, fmt in (("png", "PNG"), ("jpg", "JPEG")):
            buf = io.BytesIO()
            Image.new("RGB", (120, 80), (30, 120, 200)).save(buf, fmt)
            (n,) = w.imp(tmp_path, f"scan.{ext}", buf.getvalue())
            assert n["pdf_length"] == 1
            data = w.doc().find(n["id"]).original_data
            assert data.startswith(b"%PDF") and _pages(data) == 1

    def test_text_and_html_convert_to_pdf_leaves(self, tmp_path):
        w = Win()
        (t,) = w.imp(tmp_path, "notiz.txt", "Grüße vom Beleg".encode("utf-8"))
        (h,) = w.imp(tmp_path, "mail.html", b"<html><body><p>Hallo HTML Welt</p></body></html>")
        assert "Grüße" in _text(w.doc().find(t["id"]).original_data, 0)
        assert "Hallo HTML" in _text(w.doc().find(h["id"]).original_data, 0)

    def test_zip_becomes_nested_folders_and_nested_zip_is_recursed(self, tmp_path):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            z.writestr("tief.pdf", _pdf(1, "tief"))
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as z:
            z.writestr("rechnungen/2024/beleg.pdf", _pdf(2, "beleg"))
            z.writestr("rechnungen/zweite.pdf", _pdf(1, "zweite"))
            z.writestr("paket.zip", inner.getvalue())
        w = Win()
        w.imp(tmp_path, "archiv.zip", outer.getvalue())
        beleg = _by_name(w.last, "beleg.pdf")
        flat = _flat(w.tree)
        assert flat[beleg["_parent"]]["name"] == "2024"
        assert flat[flat[beleg["_parent"]]["_parent"]]["name"] == "rechnungen"
        tief = _by_name(w.last, "tief.pdf")  # zip in a zip -> sub-folder
        assert flat[tief["_parent"]]["name"] == "paket.zip"
        assert tief["pdf_length"] == 1

    def test_zip_over_the_member_cap_degrades_without_aborting(self, tmp_path):
        from infra.limits import BOMB_CAP_ENTRIES
        buf = io.BytesIO()
        pdf = _pdf(1, "m")
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for i in range(BOMB_CAP_ENTRIES + 5):
                z.writestr(f"m{i:04d}.pdf", pdf)
        w = Win()
        r = w.api.import_paths(w.sid, [_put(tmp_path, "bomb.zip", buf.getvalue())])
        # the guard is on: either refused outright or truncated -- never BOMB_CAP_ENTRIES+5 real nodes
        if r["ok"]:
            leaves = [n for n in _leaves(r["tree"]) if n["pdf_length"] > 0]
            assert len(leaves) <= BOMB_CAP_ENTRIES
        else:
            assert r["error"]

    def test_deeply_nested_zip_is_bounded(self, tmp_path):
        data = _pdf(1, "kern")
        name = "kern.pdf"
        for lvl in range(14):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr(name, data)
            data, name = buf.getvalue(), f"l{lvl}.zip"
        w = Win()
        r = w.api.import_paths(w.sid, [_put(tmp_path, "tief.zip", data)])
        assert r["ok"]
        assert not [n for n in _flat(r["tree"]).values() if n["name"] == "kern.pdf"]  # depth cap hit
        assert any("tief" in n["name"] and "verschachtelt" in n["name"]
                   for n in _flat(r["tree"]).values())

    def test_eml_becomes_body_plus_attachment_subtree(self, tmp_path):
        m = EmailMessage()
        m["Subject"] = "Rechnung Mai"
        m["From"] = "a@example.org"
        m["To"] = "b@example.org"
        m.set_content("Anbei die Rechnung.")
        m.add_attachment(_pdf(1, "anhang"), maintype="application", subtype="pdf", filename="Rechnung.pdf")
        w = Win()
        w.imp(tmp_path, "mail.eml", m.as_bytes())
        att = _by_name(w.last, "Rechnung.pdf")
        flat = _flat(w.tree)
        assert flat[att["_parent"]]["is_folder"]            # the mail is a folder ...
        assert len(flat[att["_parent"]]["children"]) >= 2   # ... holding body + attachment

    def test_import_bytes_drop_path_equals_import_path(self, tmp_path):
        w = Win()
        r = w.api.import_bytes(w.sid, "gedroppt.pdf",
                               "data:application/pdf;base64," + base64.b64encode(_pdf(3)).decode())
        assert r["ok"] and _by_name(r, "gedroppt")["pdf_length"] == 3 and r["dirty"] is True

    def test_import_bad_base64_is_reported_not_raised(self):
        w = Win()
        r = w.api.import_bytes(w.sid, "x.pdf", "@@@")
        assert r["ok"] is False

    def test_exe_disguised_as_txt_is_refused_but_other_files_import(self, tmp_path):
        w = Win()
        bad = _put(tmp_path, "evil.docx", b"MZ\x90\x00\x03" + b"\x00" * 64)
        good = _put(tmp_path, "ok.pdf", _pdf(1))
        r = w.api.import_paths(w.sid, [bad, good])
        assert r["ok"] and _names(r["tree"]) == ["ok"]
        assert r.get("warning")

    def test_render_cache_starts_warming_by_itself_after_import(self, tmp_path):
        w = Win()
        w.imp(tmp_path, "warm.pdf", _pdf(4))
        assert _wait(lambda: w.api.render_stats()["cache_pages"] >= 4)   # no node click needed


# =========================================================================== 2. Tree editing
class TestTreeEditing:
    def test_split_per_page_makes_one_leaf_per_page_in_order_inheriting_status(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "mappe", 3)
        w.d(type="SetStatus", node_id=a, status="erfasst")
        r = w.d(type="Split", node_id=a)
        assert r["ok"]
        parts = _leaves(r["tree"])
        assert len(parts) == 3 and all(p["pdf_length"] == 1 for p in parts)
        assert all(p["status"] == "erfasst" for p in parts)
        texts = [_text(w.doc().find(p["id"]).original_data, 0) for p in parts]
        assert [t.strip() for t in texts] == ["mappep1", "mappep2", "mappep3"]

    def test_split_into_chunks_of_n_pages(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "x", 5)
        r = w.d(type="SplitInto", node_id=a, size=2, into_folder=False)
        assert [p["pdf_length"] for p in _leaves(r["tree"])] == [2, 2, 1]

    def test_split_into_folder_wraps_the_parts_in_a_folder(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "x", 4)
        r = w.d(type="SplitInto", node_id=a, size=1, into_folder=True)
        assert r["ok"]
        (folder,) = [c for c in r["tree"]["children"] if c["is_folder"]]
        assert len(folder["children"]) == 4 and all(not c["is_folder"] for c in folder["children"])

    def test_split_is_one_undo_step(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "x", 3)
        w.d(type="Split", node_id=a)
        r = w.undo()
        assert [c["id"] for c in r["tree"]["children"]] == [a]

    def test_merge_siblings_concatenates_pages_in_order(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "A", 2)
        b = w.leaf(tmp_path, "B", 1)
        r = w.d(type="Merge", node_ids=[a, b])
        assert r["ok"]
        (m,) = _leaves(r["tree"])
        data = w.doc().find(m["id"]).original_data
        assert m["pdf_length"] == 3 and [_text(data, i).strip() for i in range(3)] == ["Ap1", "Ap2", "Bp1"]

    def test_merge_with_different_status_drops_status_same_status_keeps_it(self, tmp_path):
        w = Win()
        a, b, c = (w.leaf(tmp_path, n) for n in "abc")
        w.d(type="SetStatus", node_id=a, status="erfasst")
        w.d(type="SetStatus", node_id=b, status="erfasst")
        r = w.d(type="Merge", node_ids=[a, b])
        (m,) = [n for n in _leaves(r["tree"]) if n["id"] not in (c,)]
        assert m["status"] == "erfasst"
        w.d(type="SetStatus", node_id=c, status="zu erfassen")
        r = w.d(type="Merge", node_ids=[m["id"], c])
        assert _leaves(r["tree"])[0]["status"] == ""

    def test_merge_dpi_conflict_is_handled_and_disables_compression(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "scan1", data=open(COMPRESS_SAMPLE, "rb").read())
        b = w.leaf(tmp_path, "scan2", data=open(COMPRESS_SAMPLE, "rb").read() + b"\n%x")
        w.d(type="Compress", node_id=a, dpi=100, method="jpg")
        w.d(type="Compress", node_id=b, dpi=150, method="jpg")
        r = w.d(type="Merge", node_ids=[a, b])
        assert r["ok"]
        (m,) = _leaves(r["tree"])
        assert m["no_compression"] is True and m["is_compressed"] is False
        assert m["pdf_length"] == 4

    def test_merge_needs_two_siblings(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        assert w.d(type="Merge", node_ids=[a])["ok"] is False

    def test_create_folder_rename_and_empty_name_is_refused(self, tmp_path):
        w = Win()
        f = w.folder("Neu")
        assert w.d(type="Rename", node_id=f, name="Umbenannt")["tree"]["children"][0]["name"] == "Umbenannt"
        bad = w.d(type="Rename", node_id=f, name="")
        assert bad["ok"] is False and w.last["tree"]["children"][0]["name"] == "Umbenannt"

    def test_new_folder_at_index_and_inside_folder(self, tmp_path):
        w = Win()
        w.leaf(tmp_path, "a")
        top = w.folder("Oben")
        sub = w.folder("Unter", parent_id=top)
        assert _flat(w.last["tree"])[sub]["_parent"] == top

    def test_move_into_before_after_and_single_undo(self, tmp_path):
        w = Win()
        a, b, c = (w.leaf(tmp_path, n) for n in "abc")
        f = w.folder("F")
        r = w.d(type="Move", node_id=a, new_parent_id=f)           # into
        assert _flat(r["tree"])[a]["_parent"] == f
        r = w.d(type="Move", node_id=c, new_parent_id=w.tree["id"], index=0)   # before
        assert _names(r["tree"])[0] == "c"
        assert w.undo()["ok"] and _names(w.last["tree"])[0] == "b"   # one drop == one undo
        assert _flat(w.last["tree"])[a]["_parent"] == f

    def test_move_into_own_descendant_is_rejected_and_nothing_changes(self, tmp_path):
        w = Win()
        f = w.folder("F")
        g = w.folder("G", parent_id=f)
        before = w.last["tree"]
        r = w.d(type="Move", node_id=f, new_parent_id=g)
        assert r["ok"] is False
        assert w.api.get_state(w.sid)["tree"] == before

    def test_move_many_keeps_relative_order_as_one_undo(self, tmp_path):
        w = Win()
        a, b, c = (w.leaf(tmp_path, n) for n in "abc")
        f = w.folder("F")
        r = w.d(type="MoveMany", node_ids=[a, b], new_parent_id=f)
        assert [c_["id"] for c_ in _by_name(r, "F")["children"]] == [a, b]
        w.undo()
        assert [x["id"] for x in w.last["tree"]["children"]][:3] == [a, b, c]

    def test_group_into_folder(self, tmp_path):
        w = Win()
        a, b = w.leaf(tmp_path, "a"), w.leaf(tmp_path, "b")
        r = w.d(type="GroupIntoFolder", node_ids=[a, b], parent_id=w.tree["id"], name="Gruppe")
        assert r["ok"]
        assert sorted(_names(_by_name(r, "Gruppe"))) == ["a", "b"]

    def test_multi_delete_is_one_undo_and_frees_cached_renders(self, tmp_path):
        w = Win()
        a, b, c = (w.leaf(tmp_path, n, 2) for n in "abc")
        for nid in (a, b, c):
            w.api.render_window(w.sid, nid, 0, 2, 60)
        assert _wait(lambda: w.api.render_stats()["cache_pages"] >= 6)
        used = w.api.render_stats()["cache_used"]
        r = w.d(type="DeleteMany", node_ids=[a, b])
        assert r["ok"] and _names(r["tree"]) == ["c"]
        assert _wait(lambda: w.api.render_stats()["cache_used"] < used)   # deleted nodes' renders freed
        r = w.undo()
        assert sorted(_names(r["tree"])) == ["a", "b", "c"]               # ONE undo restores both

    def test_data_layer_rejects_a_mixed_folder_and_child_selection(self, tmp_path):
        w = Win()
        f = w.folder("F")
        child = w.leaf(tmp_path, "kind", parent_id=f)
        r = w.d(type="DeleteMany", node_ids=[f, child])
        assert r["ok"] is False and "Gemischte Auswahl" in r["error"]
        assert child in _flat(w.api.get_state(w.sid)["tree"])             # nothing was lost
        # a move never guesses either: the nested child rides along with its folder (no split-up)
        g = w.folder("Ziel")
        r = w.d(type="MoveMany", node_ids=[f, child], new_parent_id=g)
        assert r["ok"] and _flat(r["tree"])[child]["_parent"] == f and _flat(r["tree"])[f]["_parent"] == g

    def test_ui_resolution_include_all_exclude_folder_both_work(self, tmp_path):
        """The UI resolves a mixed selection first; both resolutions must be accepted."""
        w = Win()
        f = w.folder("F")
        child = w.leaf(tmp_path, "kind", parent_id=f)
        other = w.leaf(tmp_path, "other")
        r = w.d(type="DeleteMany", node_ids=[f, other])             # 'include all': folder subsumes child
        assert r["ok"] and r["tree"]["children"] == []
        w.undo()
        r = w.d(type="DeleteMany", node_ids=[child, other])         # 'exclude folder'
        assert r["ok"] and _names(r["tree"]) == ["F"] and _by_name(r, "F")["children"] == []

    def test_delete_root_is_refused(self):
        w = Win()
        assert w.d(type="Delete", node_id=w.tree["id"])["ok"] is False

    def test_undo_redo_chain_replays_exactly(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a", 2)
        snaps = [w.api.get_state(w.sid)["tree"]]
        for cmd in (dict(type="Rename", node_id=a, name="b"),
                    dict(type="SetStatus", node_id=a, status="erfasst"),
                    dict(type="Split", node_id=a)):
            assert w.d(**cmd)["ok"]
            snaps.append(w.api.get_state(w.sid)["tree"])
        for want in reversed(snaps[:-1]):
            assert w.undo()["tree"] == want
        assert w.last["can_undo"] is True   # the import is still undoable
        for want in snaps[1:]:
            assert w.redo()["tree"] == want
        assert w.last["can_redo"] is False

    def test_a_new_edit_after_undo_discards_the_redo_branch(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        w.d(type="Rename", node_id=a, name="x")
        w.undo()
        assert w.last["can_redo"] is True
        w.d(type="Rename", node_id=a, name="y")
        assert w.last["can_redo"] is False

    def test_collapse_is_persisted_in_the_file_and_undoable(self, tmp_path):
        w = Win()
        f = w.folder("F")
        g = w.folder("G")
        w.leaf(tmp_path, "k", parent_id=f)
        r = w.d(type="SetCollapsed", node_id=f, collapsed=True)
        assert r["dirty"] and w.node(f)["collapsed"] is True
        p = str(tmp_path / "c.belegtool")
        w.save(p)
        w2 = Win(path=p)
        names = {n["name"]: n for n in _flat(w2.tree).values()}
        assert names["F"]["collapsed"] is True and names["G"]["collapsed"] is False
        r = w2.d(type="SetAllCollapsed", collapsed=True)
        assert all(n["collapsed"] for n in _flat(r["tree"]).values() if n["is_folder"] and n["id"] != r["tree"]["id"])
        w2.undo()
        assert {n["name"]: n["collapsed"] for n in _flat(w2.last["tree"]).values()}["F"] is True
        _ = g

    def test_carry_and_drop_commits_a_single_undoable_move(self, tmp_path):
        """Insert-grab -> arrows -> Insert-drop is optical until the drop; the drop is ONE Move."""
        w = Win()
        a, b, c = (w.leaf(tmp_path, n) for n in "abc")
        f = w.folder("F")
        undo_before = w.last["can_undo"]
        r = w.d(type="Move", node_id=c, new_parent_id=f)
        assert r["ok"]
        w.undo()
        assert _flat(w.last["tree"])[c]["_parent"] == w.tree["id"] and undo_before

    def test_locked_node_edits_do_not_corrupt_model(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        assert w.d(type="Move", node_id=a, new_parent_id="missing")["ok"] is False
        assert a in _flat(w.api.get_state(w.sid)["tree"])


# =========================================================================== 3. Preview & compression
@pytest.fixture(scope="module")
def scan_bytes():
    with open(COMPRESS_SAMPLE, "rb") as f:
        return f.read()


class TestPreview:
    def test_first_page_loads_without_scrolling(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "doc", 12)
        r = w.api.render_window(w.sid, a, 0, 3, 80)
        assert r["ok"] and len(r["pages"]) == 3
        assert all(p.startswith("data:image/png;base64,") for p in r["pages"])

    def test_page_count_dims_and_windows_are_consistent(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "doc", 7)
        assert w.api.page_count(w.sid, a)["count"] == 7
        assert len(w.api.page_dims(w.sid, a)["dims"]) == 7
        tail = w.api.render_window(w.sid, a, 5, 10, 60)
        assert all(tail["pages"][:2]) and not any(tail["pages"][2:])   # only 2 real pages remain
        assert not any(w.api.render_window(w.sid, a, 99, 3, 60)["pages"])

    def test_warm_cache_serves_repeat_requests_and_neighbours_warm_in_background(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "doc", 6)
        b = w.leaf(tmp_path, "nachbar", 6)
        w.api.render_window(w.sid, a, 0, 1, 60)
        # the middleware keeps filling: the OTHER node warms without being requested. Node `a` has
        # only 6 pages, so more than 6 cached pages means pages of `b` were warmed in the
        # background. (The filler backs off under system load by design — the Windows CI runner is
        # slow — so assert the property, not full warm-up, with a generous timeout.)
        assert _wait(lambda: w.api.render_stats()["cache_pages"] > 6, timeout=40.0)
        assert b in _flat(w.tree)

    def test_render_budget_grow_and_shrink_evicts_immediately(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "doc", 8)
        w.api.render_window(w.sid, a, 0, 8, 100)
        assert _wait(lambda: w.api.render_stats()["cache_pages"] >= 8)
        big = w.api.render_stats()
        r = w.api.set_render_budget(big["cache_budget"] // (1024 * 1024) + 64)
        assert r["cache_budget"] > big["cache_budget"]                    # ＋ grows
        r = w.api.set_render_budget(1)                                    # − (clamped to the minimum)
        assert r["cache_budget"] < big["cache_budget"] and r["cache_used"] <= r["cache_budget"]
        assert w.api.set_render_budget("kaputt")["ok"] is False
        w.api.set_render_budget(128)

    def test_unknown_session_or_node_is_an_error_not_a_crash(self):
        w = Win()
        assert w.api.render_window("nope", "x")["ok"] is False
        assert w.api.render_window(w.sid, "nope")["ok"] is False
        assert w.api.compress_options(w.sid, "nope")["ok"] is False


class TestCompression:
    def _imp_scan(self, w, tmp_path, scan_bytes, name="scan"):
        return w.leaf(tmp_path, name, data=scan_bytes)

    def test_options_are_smallest_first_larger_hidden_and_source_size_reported(self, tmp_path, scan_bytes):
        w = Win()
        a = self._imp_scan(w, tmp_path, scan_bytes)
        r = w.api.compress_options(w.sid, a, 100)
        assert r["ok"] and r["original_size"] == len(scan_bytes)
        sizes = [o["size"] for o in r["options"]]
        assert sizes == sorted(sizes) and sizes
        assert all(s < len(scan_bytes) for s in sizes)                    # larger-than-original hidden
        assert {"jpg", "jpg_color"} <= {o["method"] for o in r["options"]}

    def test_dpi_slider_range_50_to_300_is_accepted_and_hostile_values_are_clamped(self, tmp_path, scan_bytes):
        w = Win()
        a = self._imp_scan(w, tmp_path, scan_bytes)
        for dpi in (50, 300):
            r = w.api.compress_options(w.sid, a, dpi)
            assert r["ok"] and r["dpi"] == dpi
        tiny = w.leaf(tmp_path, "tiny", data=_pdf(1, "t"))                  # clamp check on a cheap node
        assert w.api.compress_options(w.sid, tiny, 10**9)["dpi"] <= 600     # core clamp, never unbounded
        assert w.api.compress_options(w.sid, tiny, -5)["dpi"] >= 30

    def test_apply_is_coherent_then_committed_node_survives_save_without_source(self, tmp_path, scan_bytes):
        w = Win()
        a = self._imp_scan(w, tmp_path, scan_bytes)
        r = w.d(type="Compress", node_id=a, dpi=100, method="jpg")
        n = _flat(r["tree"])[a]
        assert r["ok"] and n["is_compressed"] is True and n["dpi_current"] == 100
        assert n["compression_method"] == "jpg" and n["has_source"] is True
        before = len(w.doc().find(a).current_data)
        assert before < len(scan_bytes)
        p = str(tmp_path / "comp.belegtool")
        w.save(p)
        w2 = Win(path=p)
        (leaf,) = _leaves(w2.tree)
        assert leaf["is_compressed"] is True and leaf["has_source"] is False   # "keine Quelle"
        node = w2.doc().find(leaf["id"])
        assert node.original_data is None and node.current_data
        assert w2.d(type="Compress", node_id=leaf["id"], dpi=100, method="jpg")["ok"] is False
        assert w2.d(type="Reset", node_id=leaf["id"])["ok"] is False
        assert w2.api.compress_options(w2.sid, leaf["id"])["options"] == []

    def test_reset_before_save_returns_to_source_and_apply_is_undoable(self, tmp_path, scan_bytes):
        w = Win()
        a = self._imp_scan(w, tmp_path, scan_bytes)
        w.d(type="Compress", node_id=a, dpi=100, method="jpg")
        r = w.d(type="Reset", node_id=a)
        assert r["ok"] and _flat(r["tree"])[a]["is_compressed"] is False
        assert w.doc().find(a).current_data in (None, scan_bytes) or \
            len(w.doc().find(a).current_data) == len(scan_bytes)
        w.undo()
        assert w.node(a)["is_compressed"] is True

    def test_split_carries_an_applied_compression_verbatim_into_the_parts(self, tmp_path, scan_bytes):
        w = Win()
        a = self._imp_scan(w, tmp_path, scan_bytes)
        w.d(type="Compress", node_id=a, dpi=100, method="jpg")
        r = w.d(type="Split", node_id=a)
        parts = _leaves(r["tree"])
        assert len(parts) == 2
        assert all(p["is_compressed"] and p["dpi_current"] == 100 for p in parts)
        assert all(w.doc().find(p["id"]).current_data for p in parts)

    def test_variants_persist_in_the_file_and_reopen_does_not_recompute(self, tmp_path, scan_bytes, monkeypatch):
        w = Win()
        a = self._imp_scan(w, tmp_path, scan_bytes)
        first = w.api.compress_options(w.sid, a, 100)["options"]
        assert first
        info = w.api.save_info(w.sid)
        assert info["has_alternatives"] is True and info["count"] >= 1
        p = str(tmp_path / "v.belegtool")
        w.save(p)
        with pikepdf.open(p) as pdf:                                       # hidden per-node attachment
            assert any(k.startswith("variant_") for k in pdf.attachments.keys())
        from belegtool_compress import raster
        calls = []
        real = raster.open_pdf
        monkeypatch.setattr(raster, "open_pdf", lambda *a_, **k: (calls.append(1), real(*a_, **k))[1])
        w2 = Win(path=p)
        (leaf,) = _leaves(w2.tree)
        again = w2.api.compress_options(w2.sid, leaf["id"], 100)["options"]
        assert again == first
        assert calls == []                                                  # rehydrated, not recomputed

    def test_variants_of_a_deleted_node_are_not_stored_but_come_back_with_undo(self, tmp_path, scan_bytes):
        w = Win()
        a = self._imp_scan(w, tmp_path, scan_bytes)
        w.leaf(tmp_path, "keep", 1)
        w.api.compress_options(w.sid, a, 100)
        w.d(type="Delete", node_id=a)
        assert w.api.save_info(w.sid)["has_alternatives"] is False
        p = str(tmp_path / "gone.belegtool")
        w.save(p)
        with pikepdf.open(p) as pdf:
            assert not any(k.startswith("variant_") for k in pdf.attachments.keys())
        w.undo()
        assert w.api.save_info(w.sid)["has_alternatives"] is True
        p2 = str(tmp_path / "back.belegtool")
        w.save(p2)
        with pikepdf.open(p2) as pdf:
            assert any(k.startswith("variant_") for k in pdf.attachments.keys())

    def test_original_only_save_embeds_no_variants(self, tmp_path, scan_bytes):
        w = Win()
        a = self._imp_scan(w, tmp_path, scan_bytes)
        w.api.compress_options(w.sid, a, 100)
        p = str(tmp_path / "o.belegtool")
        w.save(p, store_alternatives=False)
        with pikepdf.open(p) as pdf:
            assert not any(k.startswith("variant_") for k in pdf.attachments.keys())

    def test_deleting_a_node_cancels_its_in_flight_compression(self, tmp_path, scan_bytes):
        w = Win()
        a = self._imp_scan(w, tmp_path, scan_bytes)
        started, result = threading.Event(), {}
        eng = w.api._engine
        real = eng.compress_methods

        def slow(data, dpi, cancel=None, **kw):
            started.set()
            end = time.monotonic() + 8
            while time.monotonic() < end and not (cancel and cancel()):
                time.sleep(0.01)
            return {}

        eng.compress_methods = slow
        try:
            t = threading.Thread(target=lambda: result.update(r=w.api.compress_options(w.sid, a, 100)))
            t.start()
            assert started.wait(5)
            t0 = time.monotonic()
            assert w.d(type="Delete", node_id=a)["ok"]
            t.join(5)
            assert not t.is_alive() and time.monotonic() - t0 < 4          # cancelled, not run to the end
        finally:
            eng.compress_methods = real
        assert result["r"]["options"] == []
        # a cancelled evaluation is NOT a no-gain verdict: undo brings the node back compressible
        w.undo()
        assert w.node(a)["compression_no_gain"] is False
        assert w.api.compress_options(w.sid, a, 100)["options"]

    def test_split_and_merge_cancel_in_flight_compression_too(self, tmp_path, scan_bytes):
        for op in ("Split", "Merge"):
            w = Win()
            a = self._imp_scan(w, tmp_path, scan_bytes, "n1")
            b = self._imp_scan(w, tmp_path, scan_bytes + b"\n%" + op.encode(), "n2")
            started, result = threading.Event(), {}
            eng = w.api._engine
            real = eng.compress_methods

            def slow(data, dpi, cancel=None, **kw):
                started.set()
                end = time.monotonic() + 8
                while time.monotonic() < end and not (cancel and cancel()):
                    time.sleep(0.01)
                return {}

            eng.compress_methods = slow
            try:
                t = threading.Thread(target=lambda: result.update(r=w.api.compress_options(w.sid, a, 100)))
                t.start()
                assert started.wait(5)
                cmd = ({"type": "Split", "node_id": a} if op == "Split"
                       else {"type": "Merge", "node_ids": [a, b]})
                assert w.d(**cmd)["ok"]
                t.join(5)
                assert not t.is_alive(), op
            finally:
                eng.compress_methods = real

    def test_delete_then_undo_leaves_the_node_compressible(self, tmp_path, scan_bytes):
        w = Win()
        a = self._imp_scan(w, tmp_path, scan_bytes)
        w.d(type="Delete", node_id=a)
        w.undo()
        assert w.api.compress_options(w.sid, a, 100)["options"]


# =========================================================================== 4. Status
class TestStatus:
    def test_vocabulary_comes_from_the_core(self):
        st = CoreApi().config()["statuses"]
        assert {"erfasst", "zu erfassen", "vorjahreswert"} <= set(st)

    def test_leaf_status_and_clearing_and_invalid_value(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        assert w.node(a)["status"] == ""                                    # default: no status
        for s in ("erfasst", "zu erfassen", "vorjahreswert", ""):
            assert w.d(type="SetStatus", node_id=a, status=s)["ok"]
            assert w.node(a)["status"] == s
        assert w.d(type="SetStatus", node_id=a, status="bogus")["ok"] is False

    def test_status_on_a_folder_cascades_to_every_descendant_document(self, tmp_path):
        w = Win()
        f = w.folder("F")
        g = w.folder("G", parent_id=f)
        a = w.leaf(tmp_path, "a", parent_id=f)
        b = w.leaf(tmp_path, "b", parent_id=g)
        r = w.d(type="SetStatus", node_id=f, status="zu erfassen")
        flat = _flat(r["tree"])
        assert flat[a]["status"] == flat[b]["status"] == "zu erfassen"
        r = w.d(type="SetStatus", node_id=f, status="")
        assert _flat(r["tree"])[b]["status"] == ""

    def test_status_many_is_one_undo_step_and_round_trips_through_save(self, tmp_path):
        w = Win()
        a, b = w.leaf(tmp_path, "a"), w.leaf(tmp_path, "b")
        w.d(type="SetStatusMany", node_ids=[a, b], status="vorjahreswert")
        w.undo()
        assert w.node(a)["status"] == "" == w.node(b)["status"]
        w.redo()
        p = str(tmp_path / "s.belegtool")
        w.save(p)
        w2 = Win(path=p)
        assert {n["name"]: n["status"] for n in _leaves(w2.tree)} == {"a": "vorjahreswert", "b": "vorjahreswert"}


# =========================================================================== 5. Export
def _outline_titles(pdf, items=None, acc=None):
    acc = [] if acc is None else acc
    for it in (pdf.open_outline().root if items is None else items):
        acc.append(it.title)
        _outline_titles(pdf, it.children, acc)
    return acc


def _link_target_pages(path):
    """(page index of the link's destination) for every internal link annotation."""
    out = []
    with pikepdf.open(path) as pdf:
        ids = {p.objgen: i for i, p in enumerate(pdf.pages)}
        for page in pdf.pages:
            for an in page.obj.get("/Annots", []):
                an = an.get_object() if hasattr(an, "get_object") else an
                dest = an.get("/Dest")
                if dest is None and "/A" in an and "/D" in an["/A"]:
                    dest = an["/A"]["/D"]
                if dest is not None and len(dest) and isinstance(dest[0], pikepdf.Object):
                    try:
                        out.append(ids[dest[0].objgen])
                    except KeyError:
                        pass
    return out


class TestExport:
    def _tree(self, w, tmp_path):
        f1 = w.folder("Bank")
        w.leaf(tmp_path, "Auszug", 2, parent_id=f1)
        w.leaf(tmp_path, "Zins", 1, parent_id=f1)
        f2 = w.folder("Steuer")
        w.leaf(tmp_path, "Bescheid", 3, parent_id=f2)
        return f1, f2

    def test_single_pdf_has_toc_bookmarks_and_links_that_hit_the_right_pages(self, tmp_path):
        w = Win()
        self._tree(w, tmp_path)
        out = str(tmp_path / "e.pdf")
        r = w.api.export(w.sid, out)
        assert r["ok"] and r["paths"] == [out] and os.path.getsize(out) > 0
        with fitz.open(out) as d:
            total = d.page_count
            content_first = next(i for i in range(total) if "Auszugp1" in d[i].get_text())
            assert total == content_first + 6 and content_first >= 1          # printed TOC in front
            assert "Auszug" in d[0].get_text() and "Bescheid" in d[0].get_text()
            titles = [t[1] for t in d.get_toc()]
            assert {"Bank", "Auszug", "Steuer", "Bescheid"} <= set(titles)
            toc = {t[1]: t[2] for t in d.get_toc()}                           # bookmark -> 1-based page
            assert "Auszugp1" in d[toc["Auszug"] - 1].get_text()
            assert "Bescheidp1" in d[toc["Bescheid"] - 1].get_text()
            targets = _link_target_pages(out)
            assert targets, "TOC has no clickable links"
            hit = {d[i].get_text().strip().split()[0] for i in targets}
            assert {"Auszugp1", "Zinsp1", "Bescheidp1"} <= hit

    def test_options_switch_toc_and_bookmarks_off(self, tmp_path):
        w = Win()
        self._tree(w, tmp_path)
        out = str(tmp_path / "plain.pdf")
        r = w.api.export(w.sid, out, options={"toc": False, "toc_links": False, "bookmarks": False,
                                              "index": False})
        assert r["ok"]
        with fitz.open(out) as d:
            assert d.page_count == 6 and d.get_toc() == []

    def test_export_of_selection_only_contains_selected_subtrees(self, tmp_path):
        w = Win()
        f1, f2 = self._tree(w, tmp_path)
        out = str(tmp_path / "sel.pdf")
        r = w.api.export(w.sid, out, node_ids=[f2])
        assert r["ok"] and r["count"] == 1
        with fitz.open(out) as d:
            alltext = "".join(p.get_text() for p in d)
            assert "Bescheidp1" in alltext and "Auszugp1" not in alltext

    def test_selection_with_folder_and_its_child_exports_the_child_once(self, tmp_path):
        w = Win()
        f1, _ = self._tree(w, tmp_path)
        child = _by_name(w.last, "Auszug")["id"]
        out = str(tmp_path / "dedupe.pdf")
        r = w.api.export(w.sid, out, node_ids=[f1, child], options={"toc": False, "bookmarks": False,
                                                                     "index": False})
        assert r["ok"]
        with fitz.open(out) as d:
            assert d.page_count == 3                                         # Auszug(2)+Zins(1), no dup

    def test_nothing_to_export_and_unknown_session_are_reported(self, tmp_path):
        w = Win()
        assert w.api.export(w.sid, str(tmp_path / "x.pdf"))["ok"] is False   # empty doc
        assert w.api.export("nope", str(tmp_path / "x.pdf"))["ok"] is False
        w.leaf(tmp_path, "a")
        assert w.api.export(w.sid, str(tmp_path / "x.pdf"), node_ids=["ghost"])["ok"] is False

    def test_tag_index_only_when_tags_exist_and_lists_documents_alphabetically(self, tmp_path):
        w = Win()
        a, b = w.leaf(tmp_path, "Alpha"), w.leaf(tmp_path, "Beta")
        no = str(tmp_path / "no_idx.pdf")
        w.api.export(w.sid, no)
        w.d(type="TagMany", node_ids=[a], tag="Zebra", add=True)
        w.d(type="TagMany", node_ids=[b], tag="Apfel", add=True)
        yes = str(tmp_path / "idx.pdf")
        assert w.api.export(w.sid, yes)["ok"]
        with fitz.open(no) as d1:
            n_no = d1.page_count
        with fitz.open(yes) as d2:
            assert d2.page_count > n_no                                       # index page(s) added
            txt = "".join(p.get_text() for p in d2)
            assert "Stichwortverzeichnis" in txt and txt.index("Apfel") < txt.index("Zebra")
        off = str(tmp_path / "idx_off.pdf")
        w.api.export(w.sid, off, options={"index": False})
        with fitz.open(off) as d3:
            assert d3.page_count == n_no

    def test_empty_leaves_are_skipped_with_a_warning(self, tmp_path):
        w = Win()
        w.leaf(tmp_path, "voll", 1)
        empty = Node(name="leer", pdf_length=0)
        from core.commands import InsertNodes
        w.api._sessions[w.sid].dispatch(InsertNodes(parent_id=w.tree["id"], nodes=(empty,)))
        r = w.api.export(w.sid, str(tmp_path / "w.pdf"))
        assert r["ok"] and "leer" in r.get("warning", "")

    def _split_doc(self, w, tmp_path):
        a = w.folder("A")
        w.leaf(tmp_path, "a1", 3, parent_id=a)
        w.leaf(tmp_path, "a2", 3, parent_id=a)
        b = w.folder("B")
        w.leaf(tmp_path, "b1", 4, parent_id=b)

    @pytest.mark.parametrize("level", ["top", "folder", "page"])
    def test_split_export_writes_multiple_valid_parts_with_cross_references(self, tmp_path, level):
        w = Win()
        self._split_doc(w, tmp_path)
        out = str(tmp_path / f"s_{level}.pdf")
        r = w.api.export(w.sid, out, options={"split_pages": 5, "split_level": level})
        assert r["ok"] and len(r["paths"]) >= 2
        total = 0
        for p in r["paths"]:
            assert os.path.exists(p)
            with fitz.open(p) as d:
                assert d.page_count >= 1
                total += d.page_count
        # every content page appears exactly once across the parts
        text = ""
        for p in r["paths"]:
            with fitz.open(p) as d:
                text += "".join(pg.get_text() for pg in d)
        for lab in ("a1p1", "a1p2", "a1p3", "a2p1", "a2p3", "b1p1", "b1p4"):
            assert text.count(lab) == 1, (level, lab)            # every page exactly once, none lost
        with fitz.open(r["paths"][0]) as d0:
            assert "a1" in d0[0].get_text() or "A" in d0[0].get_text()          # per-file TOC

    def test_split_part_toc_page_numbers_and_cross_references_point_at_the_right_pages(self, tmp_path):
        import re
        w = Win()
        self._split_doc(w, tmp_path)
        out = str(tmp_path / "x.pdf")
        r = w.api.export(w.sid, out, options={"split_pages": 5, "split_level": "top"})
        p1, p2 = r["paths"]
        with fitz.open(p1) as d1, fitz.open(p2) as d2:
            toc1 = d1[0].get_text()
            # "a1 / S. 2": the printed page number of a1 in THIS file
            assert "a1p1" in d1[int(re.search(r"a1\nS\. (\d+)", toc1).group(1)) - 1].get_text()
            assert "a2p1" in d1[int(re.search(r"a2\nS\. (\d+)", toc1).group(1)) - 1].get_text()
            # "b1 -> <other file>, S. n": the TARGET file's page, not this file's
            m = re.search(r"b1\n→ (\S+?\.pdf), S\. (\d+)", toc1)
            assert m and m.group(1) == os.path.basename(p2)
            assert "b1p1" in d2[int(m.group(2)) - 1].get_text()
            assert "Teil 1 von 2" in toc1 and "Teil 2 von 2" in d2[0].get_text()
        for p in (p1, p2):
            targets = _link_target_pages(p)
            with fitz.open(p) as d:
                assert targets and all(0 < t < d.page_count for t in targets)      # in-file links land on content

    def test_export_reflects_applied_compression_and_rotation(self, tmp_path, scan_bytes):
        w = Win()
        a = w.leaf(tmp_path, "scan", data=scan_bytes)
        bare = {"toc": False, "bookmarks": False, "index": False}
        o1, o2, o3 = (str(tmp_path / f"o{i}.pdf") for i in (1, 2, 3))
        w.api.export(w.sid, o1, options=bare)
        w.d(type="Compress", node_id=a, dpi=100, method="jpg")
        w.api.export(w.sid, o2, options=bare)
        assert os.path.getsize(o2) < os.path.getsize(o1) / 2                     # the compressed bytes are exported
        w.d(type="Rotate", node_id=a, direction="right")
        w.api.export(w.sid, o3, options=bare)
        with fitz.open(o3) as d:
            assert d.page_count == 2 and all(p.rotation == 90 or p.rect.width > p.rect.height for p in d)

    def test_top_level_split_never_splits_a_top_folder_but_page_level_may(self, tmp_path):
        w = Win()
        f = w.folder("Gross")
        w.leaf(tmp_path, "g1", 4, parent_id=f)
        w.leaf(tmp_path, "g2", 4, parent_id=f)
        top = w.api.export(w.sid, str(tmp_path / "t.pdf"), options={"split_pages": 5, "split_level": "top"})
        assert len(top["paths"]) == 1                                         # one atomic top folder
        page = w.api.export(w.sid, str(tmp_path / "p.pdf"), options={"split_pages": 5, "split_level": "page"})
        assert len(page["paths"]) >= 2

    def test_below_threshold_stays_a_single_file_and_existing_parts_are_not_clobbered(self, tmp_path):
        w = Win()
        self._split_doc(w, tmp_path)
        one = w.api.export(w.sid, str(tmp_path / "o.pdf"), options={"split_pages": 500})
        assert len(one["paths"]) == 1
        out = str(tmp_path / "s.pdf")
        first = w.api.export(w.sid, out, options={"split_pages": 5, "split_level": "page"})
        assert first["ok"]
        again = w.api.export(w.sid, out, options={"split_pages": 5, "split_level": "page"})
        assert again["ok"] is False and again["code"] == "exists" and again["existing"]
        ok = w.api.export(w.sid, out, options={"split_pages": 5, "split_level": "page", "overwrite": True})
        assert ok["ok"]

    def test_default_export_name_is_the_document_name_taken_from_the_file(self, tmp_path):
        w = Win()
        w.leaf(tmp_path, "a")
        assert w.api.document_name(w.sid).startswith("Dokument")             # untitled
        p = str(tmp_path / "Mappe 2024.belegtool")
        w.save(p)
        reopened = Win(path=p)
        assert reopened.api.document_name(reopened.sid) == "Mappe 2024"


# =========================================================================== 6. Persistence
class TestPersistence:
    def test_save_in_place_clears_dirty_and_second_save_needs_no_path_change(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        assert w.last["dirty"] is True and w.api.document_path(w.sid) is None
        p = str(tmp_path / "doc.belegtool")
        w.save(p)
        assert w.api.document_path(w.sid) == p
        assert w.api.get_state(w.sid)["dirty"] is False
        w.d(type="Rename", node_id=a, name="b")
        assert w.last["dirty"] is True
        w.save(w.api.document_path(w.sid))                                    # "Speichern" == same path
        assert w.api.get_state(w.sid)["dirty"] is False
        assert [c.name for c in load_belegtool(p).root.children] == ["b"]

    def test_save_as_rebinds_and_leaves_the_old_file_untouched(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        p1, p2 = str(tmp_path / "one.belegtool"), str(tmp_path / "two.belegtool")
        w.save(p1)
        w.d(type="Rename", node_id=a, name="neu")
        w.save(p2)
        assert w.api.document_path(w.sid) == p2
        assert [c.name for c in load_belegtool(p1).root.children] == ["a"]
        assert [c.name for c in load_belegtool(p2).root.children] == ["neu"]
        assert not [f for f in os.listdir(tmp_path) if ".tmp" in f]

    def test_undo_back_to_the_saved_state_clears_dirty(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        w.save(str(tmp_path / "d.belegtool"))
        w.d(type="Rename", node_id=a, name="x")
        assert w.last["dirty"] is True
        assert w.undo()["dirty"] is False

    def test_node_ids_status_tags_period_and_names_round_trip_losslessly(self, tmp_path):
        w = Win()
        f = w.folder("Ordner")
        a = w.leaf(tmp_path, "a", 2, parent_id=f)
        b = w.leaf(tmp_path, "b")
        w.d(type="SetStatus", node_id=a, status="erfasst")
        w.d(type="SetTags", node_id=b, tags=["x", "y"])
        w.d(type="SetPeriod", node_id=b, vz_start=2023, vz_end=2024)
        w.d(type="SetCollapsed", node_id=f, collapsed=True)
        p = str(tmp_path / "rt.belegtool")
        w.save(p)
        w2 = Win(path=p)
        f1, f2 = _flat(w.api.get_state(w.sid)["tree"]), _flat(w2.tree)
        assert set(f2) - {w2.tree["id"]} == set(f1) - {w.tree["id"]}         # node ids round-trip
        for nid in (a, b, f):
            n1, n2 = f1[nid], f2[nid]
            for k in ("name", "status", "tags", "vz_start", "vz_end", "collapsed", "pdf_length", "is_folder"):
                assert n1[k] == n2[k], (nid, k)
        assert w2.last["dirty"] is False
        assert w2.api.document_name(w2.sid) == "rt"

    def test_page_content_round_trips_byte_equivalent_pages(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "inhalt", 3)
        p = str(tmp_path / "c.belegtool")
        w.save(p)
        w2 = Win(path=p)
        (leaf,) = _leaves(w2.tree)
        data = w2.doc().find(leaf["id"]).current_data or w2.doc().find(leaf["id"]).original_data
        assert [_text(data, i).strip() for i in range(3)] == ["inhaltp1", "inhaltp2", "inhaltp3"]
        _ = a

    def test_a_saved_belegtool_is_a_normal_pdf_with_the_pages(self, tmp_path):
        w = Win()
        w.leaf(tmp_path, "a", 2)
        w.leaf(tmp_path, "b", 3)
        p = str(tmp_path / "plain.belegtool")
        w.save(p)
        assert _pages(open(p, "rb").read()) == 5

    def test_unreadable_file_reports_an_error_and_a_damaged_one_opens_unbound_with_a_warning(self, tmp_path):
        w = Win()
        w.leaf(tmp_path, "a", 2)
        w.leaf(tmp_path, "b", 3, parent_id=w.folder("F"))
        p = str(tmp_path / "gut.belegtool")
        w.save(p)
        good = open(p, "rb").read()
        api = CoreApi()
        garbage = api.open(path=_put(tmp_path, "m.belegtool", b"%PDF-1.4\nnot really\n"))
        assert garbage["ok"] is False and garbage["error"]
        assert api.open(path=_put(tmp_path, "leer.belegtool", b""))["ok"] is False
        assert api.open(path=str(tmp_path / "fehlt.belegtool"))["ok"] is False
        cut = api.open(path=_put(tmp_path, "cut.belegtool", good[: len(good) // 2]))
        assert cut["ok"] and cut["warning"]                                       # degraded -> loud
        assert api.document_path(cut["session"]) is None                          # never bound: Ctrl+S can't overwrite
        assert api.session_degraded(cut["session"]) is True
        rescue = str(tmp_path / "gerettet.belegtool")
        assert api.save(cut["session"], rescue)["ok"]                             # Save-As = the rescue
        assert api.document_path(cut["session"]) == rescue and not api.session_degraded(cut["session"])

    def test_failed_open_keeps_the_previous_document(self, tmp_path):
        w = Win()
        w.leaf(tmp_path, "bleibt")
        bad = api_r = w.api.open(session=w.sid, path=str(tmp_path / "nix.belegtool"))
        assert bad["ok"] is False
        assert _names(w.api.get_state(w.sid)["tree"]) == ["bleibt"]
        _ = api_r


# =========================================================================== 7. DATEV mode
class FakeService:
    """A fake DatevService (see test_datev_coreapi) -- records what would have gone to DATEV."""

    def __init__(self, *, prov=None, writeback_result=None, fail_parts=(), client_guid="same-client"):
        self.prov = prov
        self.writeback_result = writeback_result
        self.client_guid = client_guid
        self.fail_parts = set(fail_parts)
        self.filed, self.writebacks = [], []

    def status(self):
        return {"ok": True, "connected": True, "feature": "DokAb", "keeps_revisions": False}

    def capture_provenance(self, path, opened):
        base = {"open_change_dt": "t0", "was_checked_out_at_open": False, "opened_sha256": "h0"}
        return (self.prov, base) if self.prov else (None, None)

    def writeback(self, prov, baseline, edited, *, user_confirmed=True, comment=None, backup_dir=None):
        self.writebacks.append(edited)
        return self.writeback_result

    def file_document(self, data, *, client_guid, description, **kw):
        idx = len(self.filed)
        self.filed.append({"data": data, "client_guid": client_guid, "description": description, **kw})
        if idx in self.fail_parts:
            return {"ok": False, "error": "boom"}
        return {"ok": True, "provenance": {"doc_guid": f"{idx:08d}-0000-4000-8000-000000000000",
                                           "file_id": 100 + idx, "structure_item_id": 200 + idx,
                                           "correspondence_partner_guid": client_guid}}

    def resolve_client(self, number):
        return {"guid": self.client_guid, "name": "Muster", "number": number}

    def list_clients(self):
        return [{"guid": self.client_guid, "number": "10001", "name": "Muster GmbH"}]

    def list_placements(self, domain_id=1):
        return [{"id": 1, "name": "Stammakte", "registers": [{"id": 2, "name": "Korrespondenz"}]}]


def _datev_core(svc, monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))      # backups + settings stay in tmp
    core = CoreApi()
    core._datev_mode = True
    core._datev_service = svc
    return core


def _belegtool_file(tmp_path, name="d", leaves=2):
    w = Win()
    for i in range(leaves):
        w.leaf(tmp_path, f"{name}{i}", 2)
    p = str(tmp_path / f"{name}.belegtool")
    w.save(p)
    return p


class _Client:
    """Fake DATEVconnect client for the REAL DatevService (guard logic runs for real)."""

    def __init__(self, raw, *, checked_out=False, checkout_computer=None, change_dt="t0",
                 server_bytes=None, fid=9085411):
        self.raw, self.fid = raw, fid
        self.doc = {"change_date_time": change_dt, "checked_out": checked_out,
                    "correspondence_partner_guid": "client-x"}
        if checkout_computer:
            self.doc["checkout_computer"] = checkout_computer
        self.server_bytes = raw if server_bytes is None else server_bytes
        self.uploaded, self.puts = [], []

    def get_document(self, g):
        return dict(self.doc)

    def get_document_file(self, f):
        return self.server_bytes

    def list_structure_items(self, g):
        return [{"id": 9085409, "document_file_id": self.fid}]

    def upload_document_file(self, data):
        self.uploaded.append(data)
        return 9001

    def update_structure_item(self, g, sid, f, revision_comment=None):
        self.puts.append((g, sid, f))
        return {"http_status": 204}


def _checkout(tmp_path, raw, fid=9085411, ext="pdf"):
    p = tmp_path / GUID / f"{fid}.{ext}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    return str(p)


def _real_service_core(client, monkeypatch, tmp_path):
    from datev.inapp import DatevService
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("USERNAME", "tester")
    monkeypatch.setenv("COMPUTERNAME", "TESTBOX")
    core = CoreApi()
    core._datev_mode = True
    core._datev_service = DatevService(client)
    return core


class TestDatev:
    def test_mode_off_never_touches_datev_and_nothing_is_reachable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(CoreApi, "_datev_start_connect",
                            lambda self, *a, **k: (_ for _ in ()).throw(AssertionError("must not connect")))
        core = CoreApi()
        assert core._datev_mode is False
        assert core.datev_status() == {"ok": True, "datev_mode": False, "connected": False}
        r = core.open(path=_belegtool_file(tmp_path))
        assert r["ok"] and "datev" not in r and r["tree"]["datev"] is None     # no badge
        assert core.datev_save_back(r["session"])["ok"] is False
        assert core.datev_file(r["session"], client_guid="c")["ok"] is False

    def test_toggle_persists_per_user_and_reports_status(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        from datev import inapp
        fake = FakeService()
        monkeypatch.setattr(inapp.DatevService, "connect", classmethod(lambda cls, *a, **k: fake))
        core = CoreApi()
        assert core.set_datev_mode(True)["datev_mode"] is True
        assert _wait(lambda: core.datev_status().get("connected") is True)
        from infra.settings import load_settings
        assert load_settings()["datev_mode"] is True
        off = core.set_datev_mode(False)
        assert off == {"ok": True, "datev_mode": False, "connected": False}
        assert load_settings()["datev_mode"] is False
        assert CoreApi()._datev_mode is False                                # fresh start: persisted off

    def test_no_connection_refuses_every_write(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path / "ad"))
        core = CoreApi()
        core._datev_mode = True
        core._datev_attempted = True            # connect already failed
        core._datev_service = None
        sid = core.open(path=_belegtool_file(tmp_path))["session"]
        assert core.datev_file(sid, client_guid="c")["ok"] is False
        assert core.datev_export(sid, client_guid="c")["ok"] is False
        assert core.datev_save_back(sid)["ok"] is False
        assert core.datev_clients()["ok"] is False                          # no client list -> UI blocks filing

    def test_opening_a_checkout_shows_the_linked_badge_with_provenance(self, tmp_path, monkeypatch):
        prov = {"doc_guid": GUID, "file_id": 9085411, "structure_item_id": 9085409,
                "correspondence_partner_guid": "client-x", "source_name": "Rechnung.pdf"}
        core = _datev_core(FakeService(prov=prov), monkeypatch, tmp_path)
        r = core.open(path=_belegtool_file(tmp_path))
        assert r["datev"]["connected"] is True and r["datev"]["source_name"] == "Rechnung.pdf"
        assert r["tree"]["datev"]["doc_guid"] == GUID

    def test_connected_belegtool_writeback_ok_saves_local_in_parallel_and_keeps_structure(self, tmp_path, monkeypatch):
        prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2}
        wb = {"ok": True, "verdict": "ok", "new_file_id": 9001, "new_change_dt": "t1",
              "new_sha256": "h", "provenance": {**prov, "file_id": 9001}}
        svc = FakeService(prov=prov, writeback_result=wb)
        core = _datev_core(svc, monkeypatch, tmp_path)
        p = _belegtool_file(tmp_path, leaves=2)
        sid = core.open(path=p)["session"]
        core.dispatch(sid, {"type": "Rename", "node_id": core.get_state(sid)["tree"]["children"][0]["id"],
                            "name": "geaendert"})
        res = core.datev_save_back(sid, confirmed=True)
        assert res["ok"] and res["verdict"] == "ok"
        assert res["local_kind"] == "belegtool" and res["local_saved"] == p     # no Save-As prompt
        assert core.get_state(sid)["dirty"] is False
        assert b"/JSONStructure" in svc.writebacks[0]                           # structure travels to DATEV
        assert "geaendert" in [c.name for c in load_belegtool(p).root.children]
        assert core._datev_provenance(sid)["file_id"] == 9001               # link advanced, same document
        assert load_belegtool(p).root.datev["file_id"] == 9001              # ... and persisted

    @pytest.mark.parametrize("case", ["declined", "locked", "conflict_changed", "conflict_content",
                                      "no_structure_item"])
    def test_every_non_ok_verdict_writes_nothing_to_datev_and_leaves_the_checkout_alone(
            self, tmp_path, monkeypatch, case):
        raw = _pdf(2, "orig")
        kw = {}
        if case == "locked":
            kw = dict(checked_out=True, checkout_computer="WTS (some_other_person_zz)")
        if case == "conflict_changed":
            kw = dict(change_dt="t-newer")
        if case == "conflict_content":
            kw = dict(server_bytes=b"%PDF-1.4 someone else's version")
        newer = kw.pop("change_dt", None)
        client = _Client(raw, **kw)
        if case == "no_structure_item":
            client.list_structure_items = lambda g: []
        core = _real_service_core(client, monkeypatch, tmp_path)
        path = _checkout(tmp_path, raw)
        sid = core.open(path=path)["session"]
        if newer:
            client.doc["change_date_time"] = newer                             # changed AFTER we opened
        edited = base64.b64encode(_pdf(5, "edit")).decode()
        assert core.update_pdf_bytes(sid, edited)["ok"]
        res = core.datev_save_back(sid, confirmed=(case != "declined"))
        assert res["ok"] is False
        assert res["verdict"] == case, res
        assert client.uploaded == [] and client.puts == []                      # server untouched
        assert open(path, "rb").read() == raw                                    # local checkout untouched
        assert not os.path.exists(tmp_path / "appdata") or not any(
            f.endswith(".pdf") for _, _, fs in os.walk(tmp_path / "appdata") for f in fs) or case in (
            "no_structure_item",)

    def test_ok_writeback_backs_up_the_server_bytes_first_then_overwrites(self, tmp_path, monkeypatch):
        raw = _pdf(2, "orig")
        client = _Client(raw)
        core = _real_service_core(client, monkeypatch, tmp_path)
        path = _checkout(tmp_path, raw)
        sid = core.open(path=path)["session"]
        core.update_pdf_bytes(sid, base64.b64encode(_pdf(3, "new")).decode())
        res = core.datev_save_back(sid, confirmed=True)
        assert res["ok"] and res["verdict"] == "ok"
        assert len(client.uploaded) == 1 and len(client.puts) == 1
        assert _pages(client.uploaded[0]) == 3
        backups = [os.path.join(r, f) for r, _, fs in os.walk(tmp_path / "appdata") for f in fs]
        assert backups and open(backups[0], "rb").read() == raw                 # the OLD server bytes
        assert res["local_kind"] == "pdf" and open(path, "rb").read() == client.uploaded[0]

    def test_checked_out_document_is_saved_locally_never_written_through_the_api(self, tmp_path, monkeypatch):
        raw = _pdf(1, "orig")
        client = _Client(raw, checked_out=True, checkout_computer="WTS (TESTER)")
        core = _real_service_core(client, monkeypatch, tmp_path)
        path = _checkout(tmp_path, raw)
        sid = core.open(path=path)["session"]
        core.update_pdf_bytes(sid, base64.b64encode(_pdf(4, "edit")).decode())
        res = core.datev_save_back(sid, confirmed=True)
        assert res["verdict"] == "checked_out_self" and res["ok"] is True
        assert client.uploaded == [] and client.puts == []
        assert _pages(open(path, "rb").read()) == 4                             # local working copy saved

    def test_unedited_checkout_first_writeback_is_not_a_false_conflict(self, tmp_path, monkeypatch):
        raw = _pdf(2, "orig")
        client = _Client(raw)
        core = _real_service_core(client, monkeypatch, tmp_path)
        sid = core.open(path=_checkout(tmp_path, raw))["session"]
        assert core.datev_save_back(sid, confirmed=True)["verdict"] == "ok"

    def test_save_as_clears_provenance_and_breaks_the_link(self, tmp_path, monkeypatch):
        prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2}
        core = _datev_core(FakeService(prov=prov), monkeypatch, tmp_path)
        p = _belegtool_file(tmp_path)
        sid = core.open(path=p)["session"]
        assert core.get_state(sid)["tree"]["datev"] is not None
        assert core.save(sid, p)["ok"]                                           # in place keeps the link
        assert core._datev_provenance(sid) is not None
        assert core.save(sid, str(tmp_path / "kopie.belegtool"))["ok"]           # Save As
        assert core._datev_provenance(sid) is None
        assert core.get_state(sid)["tree"]["datev"] is None
        assert load_belegtool(str(tmp_path / "kopie.belegtool")).root.datev is None
        assert load_belegtool(p).root.datev is not None
        assert core.datev_save_back(sid)["ok"] is False                           # not connected any more

    def test_filing_a_not_connected_document_creates_a_new_document_then_links_it(self, tmp_path, monkeypatch):
        svc = FakeService(prov=None)
        core = _datev_core(svc, monkeypatch, tmp_path)
        p = _belegtool_file(tmp_path)
        sid = core.open(path=p)["session"]
        res = core.datev_file(sid, mandant_number=10001, description="Eingangsrechnung",
                              fiscal_year=2024, fiscal_month=5, document_date="2024-05-02")
        assert res["ok"]
        f = svc.filed[0]
        assert f["description"] == "Eingangsrechnung" and f["fiscal_year"] == 2024 and f["document_date"] == "2024-05-02"
        assert f["client_guid"] == "same-client"
        st = core.get_state(sid)["tree"]["datev"]
        assert st and st["file_id"] == 100                                       # now "verknüpft"
        assert res["local_kind"] == "belegtool"
        assert load_belegtool(p).root.datev["file_id"] == 100                    # link survives a reopen

    def test_filing_without_any_client_is_refused_and_nothing_is_sent(self, tmp_path, monkeypatch):
        svc = FakeService(prov=None)
        core = _datev_core(svc, monkeypatch, tmp_path)
        sid = core.open(path=_belegtool_file(tmp_path))["session"]
        res = core.datev_file(sid)
        assert res["ok"] is False and svc.filed == []

    def test_export_to_datev_without_a_known_client_is_refused_and_selection_is_honoured(self, tmp_path, monkeypatch):
        svc = FakeService(prov=None)
        core = _datev_core(svc, monkeypatch, tmp_path)
        sid = core.open(path=_belegtool_file(tmp_path, leaves=2))["session"]
        assert core.datev_export(sid)["ok"] is False and svc.filed == []        # not connected, no Mandant given
        first = core.get_state(sid)["tree"]["children"][0]["id"]
        res = core.datev_export(sid, node_ids=[first], client_guid="gx")
        assert res["ok"] and len(svc.filed) == 1 and svc.filed[0]["client_guid"] == "gx"
        assert _pages(svc.filed[0]["data"]) >= 2

    def test_export_to_datev_files_every_part_under_the_same_client(self, tmp_path, monkeypatch):
        prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2,
                "correspondence_partner_guid": "mandant-7"}
        svc = FakeService(prov=prov)
        core = _datev_core(svc, monkeypatch, tmp_path)
        w = Win()
        for n in ("a", "b", "c"):
            w.leaf(tmp_path, n, 3)
        p = str(tmp_path / "split.belegtool")
        w.save(p)
        sid = core.open(path=p)["session"]
        single = core.datev_export(sid)
        assert single["ok"] and single["parts"] == 1
        assert svc.filed[0]["client_guid"] == "mandant-7"                        # same Mandant, no prompt
        res = core.datev_export(sid, options={"split_pages": 4, "split_level": "top"})
        assert res["ok"] and res["parts"] >= 2 and res["filed_ok"] == res["parts"]
        assert len(svc.filed) == 1 + res["parts"]
        assert all(f["data"].startswith(b"%PDF") for f in svc.filed)

    def test_partial_export_failure_reports_only_x_of_y(self, tmp_path, monkeypatch):
        prov = {"doc_guid": GUID, "file_id": 1, "structure_item_id": 2,
                "correspondence_partner_guid": "m"}
        svc = FakeService(prov=prov, fail_parts={1})
        core = _datev_core(svc, monkeypatch, tmp_path)
        w = Win()
        for n in ("a", "b", "c"):
            w.leaf(tmp_path, n, 3)
        p = str(tmp_path / "split2.belegtool")
        w.save(p)
        sid = core.open(path=p)["session"]
        res = core.datev_export(sid, options={"split_pages": 4, "split_level": "top"})
        assert res["ok"] is False and res["error"].startswith("Nur ") and " von " in res["error"]
        assert res["filed_ok"] == res["parts"] - 1

    def test_pdf_tool_checkout_pdf_edit_reaches_datev_and_node_binding_files_anew(self, tmp_path, monkeypatch):
        # (a) a checkout .pdf opened directly: bake -> guarded write-back uploads the EDIT
        raw = _pdf(1, "orig")
        client = _Client(raw)
        core = _real_service_core(client, monkeypatch, tmp_path)
        sid = core.open(path=_checkout(tmp_path, raw))["session"]
        core.update_pdf_bytes(sid, base64.b64encode(_pdf(4, "edit")).decode())
        assert core.datev_save_back(sid)["verdict"] == "ok" and _pages(client.uploaded[0]) == 4
        # (b) a node opened in the PDF-Tool: file-anew pushes the baked bytes to the owner node
        svc = FakeService(prov=None)
        core2 = _datev_core(svc, monkeypatch, tmp_path)
        owner = core2.open(path=_belegtool_file(tmp_path, "n"))["session"]
        leaf = _leaves(core2.get_state(owner)["tree"])[0]["id"]
        pt = core2.open_node_in_pdftool(owner, leaf)["session"]
        core2.update_pdf_bytes(pt, base64.b64encode(_pdf(3, "baked")).decode())
        res = core2.datev_file(pt, client_guid="cli", description="Beleg")
        assert res["ok"] and res["local_kind"] == "node"
        node = core2._sessions[owner].document.find(leaf)
        assert _pages(node.current_data or node.original_data) == 3

    def test_connect_is_non_blocking_while_the_handshake_runs(self, tmp_path, monkeypatch):
        raw = _pdf(1, "orig")
        monkeypatch.setenv("APPDATA", str(tmp_path / "ad"))
        core = CoreApi()
        core._datev_mode = True
        core._datev_connecting = True
        core._datev_service = None
        assert core.datev_status() == {"ok": True, "datev_mode": True, "connected": False, "connecting": True}
        t0 = time.monotonic()
        r = core.open(path=_checkout(tmp_path, raw))
        assert time.monotonic() - t0 < 3 and r["datev"]["connected"] is True


# =========================================================================== 8. Windows / status bar
class TestWindows:
    def test_two_windows_share_one_core_but_have_independent_documents(self, tmp_path):
        api = CoreApi()
        w1, w2 = Win(api), Win(api)
        assert w1.sid != w2.sid and api.session_count() >= 2
        w1.leaf(tmp_path, "nur_in_eins")
        assert w2.api.get_state(w2.sid)["tree"]["children"] == []
        assert w2.api.get_state(w2.sid)["dirty"] is False
        assert api.undo(w2.sid)["tree"]["children"] == []

    def test_untitled_documents_get_distinct_names(self):
        api = CoreApi()
        assert Win(api).tree["name"] != Win(api).tree["name"]

    def test_closing_a_window_frees_its_session_and_renders(self, tmp_path):
        api = CoreApi()
        w1, w2 = Win(api), Win(api)
        a = w1.leaf(tmp_path, "weg", 3)
        api.render_window(w1.sid, a, 0, 3, 60)
        assert _wait(lambda: api.render_stats()["cache_pages"] >= 3)
        n = api.session_count()
        assert api.close_session(w1.sid)["ok"]
        assert api.session_count() == n - 1
        assert _wait(lambda: api.render_stats()["cache_pages"] == 0)
        assert api.get_state(w2.sid)["ok"]

    def test_render_stats_gauge_reports_used_budget_and_pages(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "g", 2)
        w.api.render_window(w.sid, a, 0, 2, 60)
        s = w.api.render_stats()
        assert s["ok"] and s["cache_budget"] > 0 and s["cache_used"] > 0 and s["cache_pages"] >= 1
        assert "prefetch_active" in s                                  # background-activity indicator


# =========================================================================== 9. Tags
class TestTags:
    def test_multi_select_tag_add_remove_is_one_undo_and_keeps_other_tags(self, tmp_path):
        w = Win()
        a, b, c = (w.leaf(tmp_path, n) for n in "abc")
        w.d(type="SetTags", node_id=a, tags=["alt"])
        r = w.d(type="TagMany", node_ids=[a, b, c], tag="neu", add=True)
        flat = _flat(r["tree"])
        assert flat[a]["tags"] == ["alt", "neu"] or set(flat[a]["tags"]) == {"alt", "neu"}
        assert flat[b]["tags"] == ["neu"] == flat[c]["tags"]
        r = w.d(type="TagMany", node_ids=[a, b, c], tag="neu", add=False)
        assert _flat(r["tree"])[a]["tags"] == ["alt"] and _flat(r["tree"])[b]["tags"] == []
        w.undo()
        assert "neu" in _flat(w.last["tree"])[b]["tags"]                      # remove was ONE step
        w.undo()
        assert _flat(w.last["tree"])[b]["tags"] == []                         # add was ONE step

    def test_tags_persist_and_a_loaded_file_reports_them_for_auto_enable(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        w.d(type="SetTags", node_id=a, tags=["Miete", "2024"])
        p = str(tmp_path / "t.belegtool")
        w.save(p)
        w2 = Win(path=p)
        assert any(n["tags"] for n in _flat(w2.tree).values())                # UI auto-enables on this
        assert set(_leaves(w2.tree)[0]["tags"]) == {"Miete", "2024"}

    def test_open_view_in_new_window_writes_only_the_displayed_nodes_in_tree_order(self, tmp_path):
        w = Win()
        f = w.folder("Bank")
        a = w.leaf(tmp_path, "zeta", parent_id=f)
        b = w.leaf(tmp_path, "alpha", parent_id=f)
        c = w.leaf(tmp_path, "anders")
        w.d(type="TagMany", node_ids=[a, b], tag="Miete", add=True)
        # what the tag search displays: the matches plus the path to them (ancestors)
        shown = [f, a, b]
        r = w.api.materialize_subset(w.sid, shown, name="Miete - Mappe")
        assert r["ok"] and os.path.basename(r["path"]) == "Miete - Mappe.belegtool"
        view = Win(w.api, path=r["path"])
        assert view.tree["name"] == "Miete - Mappe"
        assert _names(view.tree) == ["Bank"]                                   # 'anders' hidden
        assert _names(_by_name(view.last, "Bank")) == ["zeta", "alpha"]       # NORMAL order, not sorted/grouped
        view.d(type="Rename", node_id=_by_name(view.last, "zeta")["id"], name="editierbar")  # fully editable
        assert view.last["dirty"] is True
        d = os.path.dirname(r["path"])
        assert os.path.isdir(d)
        w.api.close_session(view.sid)
        assert not os.path.exists(d)                                            # temp view dir cleaned up
        _ = c

    def test_materialize_with_nothing_displayed_is_refused(self, tmp_path):
        w = Win()
        w.leaf(tmp_path, "a")
        assert w.api.materialize_subset(w.sid, [])["ok"] is False
        assert w.api.materialize_subset(w.sid, ["ghost"])["ok"] is False

    def test_hostile_tag_as_view_name_is_a_safe_file_name(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "a")
        r = w.api.materialize_subset(w.sid, [a], name="NUL")
        assert r["ok"] and os.path.basename(r["path"]).upper() != "NUL.BELEGTOOL"
        r2 = w.api.materialize_subset(w.sid, [a], name="../../x")
        assert os.path.dirname(r2["path"]).startswith(os.path.dirname(os.path.dirname(r["path"])))


# =========================================================================== 10. PDF-Tool surface
class TestPdfTool:
    def _setup(self, tmp_path, pages=2):
        w = Win()
        a = w.leaf(tmp_path, "a", pages)
        w.save(str(tmp_path / "o.belegtool"))
        pt = w.api.open_node_in_pdftool(w.sid, a)
        assert pt["ok"]
        return w, a, pt["session"]

    def test_bytes_served_to_pdfjs_are_the_nodes_effective_bytes(self, tmp_path):
        w, a, pt = self._setup(tmp_path)
        got = base64.b64decode(w.api.get_pdf_bytes(pt)["data_b64"])
        assert _pages(got) == 2 and "ap1" in _text(got, 0)

    def test_folders_cannot_be_opened_in_the_pdf_tool_and_double_open_is_refused(self, tmp_path):
        w, a, pt = self._setup(tmp_path)
        f = w.folder("F")
        assert w.api.open_node_in_pdftool(w.sid, f)["ok"] is False
        again = w.api.open_node_in_pdftool(w.sid, a)
        assert again["ok"] is False and again["code"] == "node_locked"

    def test_lock_blocks_content_edits_and_history_but_not_rename_or_move(self, tmp_path):
        w, a, pt = self._setup(tmp_path)
        assert w.api.node_locked(w.sid, a) is True
        for cmd in ({"type": "Split", "node_id": a}, {"type": "Delete", "node_id": a},
                    {"type": "Rotate", "node_id": a}, {"type": "Compress", "node_id": a, "dpi": 100}):
            r = w.d(**cmd)
            assert r["ok"] is False and r["code"] == "node_locked", cmd
        f = w.folder("F")
        assert w.d(type="Rename", node_id=a, name="neuer name")["ok"]
        assert w.d(type="Move", node_id=a, new_parent_id=f)["ok"]
        assert w.undo()["code"] == "node_locked"                                 # undo could reverse the edit
        assert w.d(type="Delete", node_id=f)["code"] == "node_locked"           # ancestor of the locked node

    def test_save_writes_back_to_the_owner_node_dirty_and_undoable(self, tmp_path):
        w, a, pt = self._setup(tmp_path)
        w.api.dispatch(w.sid, {"type": "Rename", "node_id": a, "name": "a"})
        w.save(str(tmp_path / "o2.belegtool"))
        edited = _pdf(5, "edit")
        r = w.api.save_node_back(pt, base64.b64encode(edited).decode())
        assert r["ok"] and r["node"] == a
        st = w.api.get_state(w.sid)
        assert st["dirty"] is True and _flat(st["tree"])[a]["pdf_length"] == 5
        assert w.api.close_pdftool(pt)["ok"]                                    # release the lock first
        w.api.undo(w.sid)
        assert w.api.get_state(w.sid)["tree"]["children"][0]["pdf_length"] == 2

    def test_unedited_or_invalid_save_leaves_the_owner_untouched(self, tmp_path):
        w, a, pt = self._setup(tmp_path)
        w.save(str(tmp_path / "o3.belegtool"))
        r = w.api.save_node_back(pt)                                              # nothing edited
        assert r["ok"] and r.get("unchanged") is True
        assert w.api.get_state(w.sid)["dirty"] is False
        assert w.api.save_node_back(pt, base64.b64encode(b"not a pdf").decode())["ok"] is False
        assert w.api.save_node_back(pt, "@@@")["ok"] is False
        assert w.api.get_state(w.sid)["dirty"] is False

    def test_edited_save_resets_compression_decision_of_the_node(self, tmp_path, scan_bytes):
        w = Win()
        a = w.leaf(tmp_path, "scan", data=scan_bytes)
        w.d(type="Compress", node_id=a, dpi=100, method="jpg")
        pt = w.api.open_node_in_pdftool(w.sid, a)["session"]
        w.api.save_node_back(pt, base64.b64encode(_pdf(2, "edit")).decode())
        assert w.api.get_state(w.sid)["tree"]["children"][0]["is_compressed"] is False

    def test_closing_the_tool_releases_the_lock_and_break_binding_does_too(self, tmp_path):
        w, a, pt = self._setup(tmp_path)
        w.api.close_pdftool(pt)
        assert w.api.node_locked(w.sid, a) is False
        assert w.d(type="Rotate", node_id=a)["ok"]
        pt2 = w.api.open_node_in_pdftool(w.sid, a)["session"]
        assert w.api.break_node_binding(w.sid, a)["ok"] and w.api.node_locked(w.sid, a) is False
        assert w.api.save_node_back(pt2, base64.b64encode(_pdf(1)).decode())["ok"] is False  # detached

    def test_directly_opened_pdf_saves_to_disk_and_a_node_session_cannot_use_that_path(self, tmp_path):
        p = _put(tmp_path, "beleg.pdf", _pdf(1))
        api = CoreApi()
        sid = api.open(path=p)["session"]
        r = api.save_pdf_bytes(sid, base64.b64encode(_pdf(3, "neu")).decode())
        assert r["ok"] and r["local_kind"] == "pdf" and _pages(open(p, "rb").read()) == 3
        assert api.save_node_back(sid, base64.b64encode(_pdf(1)).decode())["ok"] is False


# =========================================================================== 11. Marker & no-gain
class TestCompressionMarker:
    def test_undecided_until_applied_and_no_gain_verdict_persists_silently(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "klein", data=_pdf(1, "nix"))                      # tiny text PDF: nothing smaller
        assert w.node(a)["compression_undecided"] is True                        # red dot at the front
        w.api._sessions[w.sid].mark_saved()
        assert w.api.compress_options(w.sid, a, 150)["options"] == []
        st = w.api.get_state(w.sid)
        assert _flat(st["tree"])[a]["compression_no_gain"] is True
        assert _flat(st["tree"])[a]["compression_undecided"] is False           # dot resolved
        assert st["dirty"] is False                                              # silent: not an edit
        p = str(tmp_path / "ng.belegtool")
        w.save(p)
        w2 = Win(path=p)
        (leaf,) = _leaves(w2.tree)
        assert leaf["compression_no_gain"] is True and leaf["compression_undecided"] is False

    def test_no_gain_verdict_survives_a_move_and_rotate_clears_it(self, tmp_path):
        w = Win()
        a = w.leaf(tmp_path, "klein", data=_pdf(1, "nix2"))
        f = w.folder("F")
        w.api.compress_options(w.sid, a, 150)
        w.d(type="Move", node_id=a, new_parent_id=f)
        assert w.node(a)["compression_no_gain"] is True
        w.d(type="Rotate", node_id=a, direction="right")
        assert w.node(a)["compression_no_gain"] is False
        assert w.node(a)["compression_undecided"] is True

    def test_applied_or_no_compression_marked_nodes_are_decided(self, tmp_path, scan_bytes):
        w = Win()
        a = w.leaf(tmp_path, "scan", data=scan_bytes)
        assert w.node(a)["compression_undecided"] is True
        w.api.compress_options(w.sid, a, 100)
        assert w.api.get_state(w.sid) and _flat(w.api.get_state(w.sid)["tree"])[a]["compression_undecided"] is True  # smaller version exists, not applied
        r = w.d(type="Compress", node_id=a, dpi=100, method="jpg")
        assert _flat(r["tree"])[a]["compression_undecided"] is False

    def test_a_cancelled_evaluation_is_not_flagged_no_gain(self, tmp_path, scan_bytes):
        w = Win()
        a = w.leaf(tmp_path, "scan", data=scan_bytes)
        w.api._cancel_token(a).set()
        assert w.api.compress_options(w.sid, a, 100)["options"] == []
        assert w.api.get_state(w.sid)["tree"]["children"][0]["compression_no_gain"] is False

    def test_folder_row_aggregation_inputs_are_available_per_leaf(self, tmp_path):
        w = Win()
        f = w.folder("F")
        a = w.leaf(tmp_path, "a", data=_pdf(1, "u1"), parent_id=f)
        b = w.leaf(tmp_path, "b", data=_pdf(1, "u2"), parent_id=f)
        w.api.compress_options(w.sid, a, 150)
        st = _flat(w.api.get_state(w.sid)["tree"])
        assert st[a]["compression_undecided"] is False and st[b]["compression_undecided"] is True
        assert any(st[c["id"]]["compression_undecided"] for c in st[f]["children"])   # folder shows it


# =========================================================================== 12. File lock
class TestFileLock:
    @pytest.mark.skipif(sys.platform == "win32", reason="Windows runs the real handle tests in test_file_lock_integration")
    def test_lock_is_off_by_default_and_a_second_open_succeeds(self, tmp_path):
        p = _belegtool_file(tmp_path)
        a, b = CoreApi(), CoreApi()
        assert a._file_lock_enabled is False
        assert a.open(path=p)["ok"] and b.open(path=p)["ok"]
        assert a._locks == {}

    def test_lock_enabled_only_through_the_environment_variable(self, monkeypatch):
        for val, want in (("1", True), ("true", True), ("yes", True), ("0", False), ("", False), ("no", False)):
            monkeypatch.setenv("BELEG_FILE_LOCK", val)
            assert CoreApi()._file_lock_enabled is want, val

    def test_interrupted_locked_save_is_restored_from_bak_on_the_next_open(self, tmp_path):
        from infra.file_lock import restore_from_bak
        p = _belegtool_file(tmp_path)
        good = open(p, "rb").read()
        open(p + ".bak", "wb").write(good)
        open(p + ".wip", "wb").write(b"")                                          # in-flight marker
        open(p, "wb").write(good[: len(good) // 3])                                # truncated by a crash
        restore_from_bak(p)
        assert open(p, "rb").read() == good
        r = CoreApi().open(path=p)
        assert r["ok"] and len(_leaves(r["tree"])) == 2

    def test_release_and_close_are_idempotent(self, tmp_path):
        api = CoreApi()
        sid = api.open(path=_belegtool_file(tmp_path))["session"]
        assert api.release(sid)["ok"] and api.release(sid)["ok"]
        assert api.close_session(sid)["ok"]


# =========================================================================== not headless-testable
# UI-only acceptance (the Python layer cannot observe them) -> where they are covered:
#
#  1. Import   "render cache starts warming" is asserted here; the visual drop-zone feedback and
#              the OS file-drop gesture are UI: manual_tests/02 (MT-09 drag-drop), 01 MT-05;
#              vitest hooks/useOsFileDrop.test.*, Tree.test.jsx.
#  2. Editing  inline rename by "click a selected name again", F2, keyboard structuring (arrows,
#              Insert grab/drop, Esc revert), "focus the next node after Entf", the mixed
#              folder+child RESOLVER DIALOG (include all / exclude folder / abort):
#              manual_tests/02_baum.md (MT-07..MT-09b), vitest lib/treeNav.test.js,
#              App.select.test.jsx, App.moveresolver.test.jsx, useKeyboard tests, e2e drag-drop spec.
#  3. Preview  virtualized windowing/IntersectionObserver, "<=5 pages default to the smallest
#              variant on display", per-node remembered method + DPI slider, the
#              "bereits komprimiert (keine Quelle)" dropdown label: manual_tests/03 MT-10..MT-12,
#              05 MT-33, 06 MT-43; vitest PreviewControls.test.jsx, Preview*.test.jsx, e2e preview spec.
#  4. Status   context-menu entries and the dot rendering / folder aggregation (lib/status.js):
#              manual_tests/08 MT-50; vitest status.test.js, ContextMenu.test.jsx.
#  5. Export   the export-options dialog (toggles, split level radio, count notice) and the native
#              save dialog: manual_tests/04 MT-14, 05 MT-36; vitest ExportDialog.test.jsx.
#  6. Persist  the "•" dirty marker in the Save split-button: vitest SaveSplitButton.test.jsx.
#  7. DATEV    badge/toolbar buttons, filing dialog (searchable Mandant, required Bezeichnung,
#              validateFiling), the confirm dialog, PDF-Tool button visibility (datevAction):
#              manual_tests/10_datev.md; vitest DatevBar.test.jsx, lib/datev*.test.js,
#              pdftool/fileDialog.test.js, source.test.js. Live behaviour needs a DATEVconnect box.
#  8. Language switcher (22 entries, live translation, persisted choice): vitest i18n.test.js,
#              manual_tests/01..; status-bar rendering and the +/- buttons: StatusBar.test.jsx;
#              a real second WebView2 window ("bridge waits for each method"): manual_tests/00/01,
#              vitest lib/core.test.js.
#  9. Tags     toolbar toggle (off by default), search filter by tag only / group-by-tag views
#              (lib/tags.js: filterTree, groupByTag, displayedNodeIds) and the edit-lock while a view
#              is active: vitest lib/tags.test.js, TagViewBar/TagEditor/Toolbar tests,
#              manual_tests/07 (tags). The "open in new window" file content IS asserted here.
# 10. PDF-Tool selectable text layer, AcroForm fields, FreeText tool, system-browser links,
#              scanned-PDF rendering: manual_tests/09 MT-5x, e2e pdftool specs (spike-form/link
#              fixtures), pdftool/main.test.js.
# 11. Red front dot rendering and the background "proactive sweep" of <=5-page leaves after load
#              (App.jsx): vitest App.sweep tests, manual_tests/06 MT-44/MT-47.
# 12. A real exclusive Win32 handle / "in use" message for a second user, locked in-place save and
#              save-as re-lock: Windows-only -> tests/test_file_lock_integration.py (skipped on
#              Linux), manual_tests/ (file lock case).
