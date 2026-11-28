# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Mutation blind spots in core/api.py (MU-10..MU-14)."""

import os

import pytest

from core.api import _friendly_import_error


class com_error(Exception):  # noqa: N801 - name is matched by type(exc).__name__
    pass


# MU-10  core/api.py:80-90  every branch of the per-file import-error mapping
@pytest.mark.parametrize("path,exc,expected", [
    ("C:/x/a.docx", com_error("boom"),
     "a.docx: Office-Programm zum Konvertieren nicht verfügbar (Word/Excel/PowerPoint erforderlich)"),
    ("a.docx", Exception("Class not registered"),
     "a.docx: Office-Programm zum Konvertieren nicht verfügbar (Word/Excel/PowerPoint erforderlich)"),
    ("a.xyz", Exception("Dateityp nicht unterstützt"), "a.xyz: Dateityp .xyz wird nicht unterstützt"),
    ("a", Exception("unsupported"), "a: Dateityp ? wird nicht unterstützt"),
    ("a.docx", Exception("Dokument verweist auf eine externe Vorlage/Quelle"),
     "a.docx: Dokument verweist auf eine externe Vorlage/Quelle und wird aus Sicherheitsgründen nicht importiert"),
    ("a.pdf", Exception("file is Encrypted"), "a.pdf: Datei ist passwortgeschützt"),
    ("a.pdf", Exception("Passwort falsch"), "a.pdf: Datei ist passwortgeschützt"),
    ("a.pdf", Exception("keine lesbaren Seiten"), "a.pdf: Datei enthält keine lesbaren Seiten"),
    ("a.ZIP", Exception("x" * 100), "a.ZIP: Archiv/E-Mail konnte nicht gelesen werden (" + "x" * 80 + ")"),
    ("m.msg", Exception("kaputt"), "m.msg: Archiv/E-Mail konnte nicht gelesen werden (kaputt)"),
    ("a.belegtool", Exception("Datei beschädigt – nicht importiert: Dokumentstruktur fehlt"),
     "a.belegtool: Datei beschädigt – nicht importiert: Dokumentstruktur fehlt"),
    ("b.belegtool", Exception("foo – Datei beschädigt – nicht importiert: z"),
     "b.belegtool: Datei beschädigt – nicht importiert: z"),
    ("a.pdf", Exception("No /Root object! - Is this really a PDF? EOF marker not found"),
     "a.pdf: beschädigte oder ungültige Datei"),
    ("a.pdf", Exception("startxref missing"), "a.pdf: beschädigte oder ungültige Datei"),
    ("a.pdf", Exception("Kein gültiges PDF"), "a.pdf: beschädigte oder ungültige Datei"),
    ("a.pdf", Exception("not a pdf"), "a.pdf: beschädigte oder ungültige Datei"),
    ("a.pdf", Exception("something else entirely"), "a.pdf: something else entirely"),
])
def test_friendly_import_error_branches(path, exc, expected):
    assert _friendly_import_error(path, exc) == expected


def test_friendly_import_error_tail_is_everything_after_the_FIRST_marker():
    # core/api.py:88  msg.split("nicht importiert: ", 1)[-1]  (maxsplit must stay 1)
    exc = Exception("Datei beschädigt – nicht importiert: x nicht importiert: y")
    assert _friendly_import_error("a.belegtool", exc) == \
        "a.belegtool: Datei beschädigt – nicht importiert: x nicht importiert: y"


# MU-11  core/api.py:979-980  Save-As must NOT touch the file lock while the lock feature is off
def _lock_api(tmp_path, enabled):
    from core.api import CoreApi
    from core.model import Document, Node
    from core.session import DocumentSession
    api = CoreApi()
    api._file_lock_enabled = enabled
    sid = api.open()["session"]
    leaf = Node(name="n", id="L", pdf_length=0, original_data=b"x")
    api._sessions[sid] = DocumentSession(
        Document(Node(name="root", id="r", is_folder=True, children=(leaf,))), engine=api._engine)
    return api, sid


def test_save_as_does_not_lock_the_new_file_when_locking_is_off(tmp_path, monkeypatch):
    from infra import file_lock
    calls = []
    monkeypatch.setattr(file_lock, "acquire_lock", lambda p: calls.append(p))
    api, sid = _lock_api(tmp_path, enabled=False)
    api._relock_after_save_as(sid, str(tmp_path / "new.belegtool"))
    assert calls == [] and sid not in api._locks


def test_save_as_relocks_the_new_file_and_releases_the_old_lock_when_on(tmp_path, monkeypatch):
    from infra import file_lock

    class _Held:
        def __init__(self, path):
            self.path, self.released = path, False

        def release(self):
            self.released = True

    acquired = []

    def fake_acquire(p):
        h = _Held(p)
        acquired.append(h)
        return h

    monkeypatch.setattr(file_lock, "acquire_lock", fake_acquire)
    api, sid = _lock_api(tmp_path, enabled=True)
    old = _Held("old")
    api._locks[sid] = old
    api._paths[sid] = "old"
    new_path = str(tmp_path / "new.belegtool")
    api._relock_after_save_as(sid, new_path)
    assert old.released and api._locks[sid] is acquired[0] and acquired[0].path == new_path
    # same path as the bound file -> nothing to do (no release, no second acquire)
    api._paths[sid] = new_path
    api._relock_after_save_as(sid, new_path)
    assert len(acquired) == 1 and not acquired[0].released and api._locks[sid] is acquired[0]


# MU-12  core/api.py:98,105  _clamp_int / set_render_budget bounds (untrusted bridge numbers)
def test_clamp_int_rejects_bool_nan_inf_and_clamps():
    from core.api import _clamp_int
    assert _clamp_int(True, 0, 10, 5) == 5 and _clamp_int(False, 0, 10, 5) == 5
    assert _clamp_int(float("nan"), 0, 10, 5) == 5 and _clamp_int(float("inf"), 0, 10, 5) == 5
    assert _clamp_int(None, 0, 10, 5) == 5 and _clamp_int("x", 0, 10, 5) == 5
    assert _clamp_int("7", 0, 10, 5) == 7 and _clamp_int(7.9, 0, 10, 5) == 7
    assert _clamp_int(99, 0, 10, 5) == 10 and _clamp_int(-3, 0, 10, 5) == 0
    assert _clamp_int(10, 0, 10, 5) == 10 and _clamp_int(0, 0, 10, 5) == 0


def test_set_render_budget_is_clamped_to_16_mb_and_4_gb():
    from core.api import CoreApi
    api = CoreApi()
    got = []
    r = api._renderer()
    r.set_budget = lambda b: got.append(b)
    api._last_seed = None
    api.set_render_budget(1)
    api.set_render_budget(16)
    api.set_render_budget(10**9)
    api.set_render_budget(4096)
    assert got == [16 * 2**20, 16 * 2**20, 4096 * 2**20, 4096 * 2**20]
    got.clear()
    for bad in ("x", None, True):
        assert api.set_render_budget(bad) == {"ok": False, "error": "ungültiger Wert"}
    assert got == []


# MU-13  core/api.py:928/930/932  Save-As detection when a file lock is held (lock.path vs. bound path)
def _datev_api(tmp_path, monkeypatch, bound, lock_path):
    from core.api import CoreApi
    from core.commands import SetDatev
    from core.model import Document, Node
    from core.session import DocumentSession
    from infra import file_lock
    api = CoreApi()
    sid = api.open()["session"]
    leaf = Node(name="n", id="L", pdf_length=0, original_data=b"x")
    doc = Document(Node(name="root", id="r", is_folder=True, children=(leaf,)))
    s = DocumentSession(doc, engine=api._engine)
    s.apply_silent(SetDatev({"doc_guid": "g", "file_id": 1}))
    api._sessions[sid] = s
    if bound is not None:
        api._paths[sid] = bound

    class _Lock:
        path = lock_path

        def release(self):
            pass

    api._locks[sid] = _Lock()
    seen = []
    monkeypatch.setattr(file_lock, "write_through_lock", lambda lk, p, data: seen.append(p))
    monkeypatch.setattr(api, "_save_through_lock", lambda lk, p, d, a: seen.append((p, d.root.datev)))
    return api, sid, seen


def test_save_onto_the_locked_file_keeps_datev_provenance(tmp_path, monkeypatch):
    target = str(tmp_path / "a.belegtool")
    # degraded/unbound session: _paths is None, only the lock knows the file
    api, sid, seen = _datev_api(tmp_path, monkeypatch, bound=None, lock_path=target)
    assert api.save(sid, target)["ok"]
    # written through the lock, in place, WITH the provenance in the saved bytes
    assert seen == [(target, {"doc_guid": "g", "file_id": 1})]
    assert api._sessions[sid].document.root.datev == {"doc_guid": "g", "file_id": 1}


def test_save_to_a_different_file_drops_datev_provenance(tmp_path, monkeypatch):
    locked = str(tmp_path / "a.belegtool")
    other = str(tmp_path / "b.belegtool")
    api, sid, seen = _datev_api(tmp_path, monkeypatch, bound=locked, lock_path=locked)
    monkeypatch.setattr("core.bridge.save_belegtool", lambda doc, p: seen.append(("save", p, doc.root.datev)))
    monkeypatch.setattr("services.variant_store.embed_variants", lambda *a, **k: None)
    assert api.save(sid, other)["ok"]
    # not written through the old lock; the file written to disk carries NO provenance
    assert seen == [("save", other, None)]
    assert api._sessions[sid].document.root.datev is None      # Save As breaks the DATEV link


# MU-14  core/api.py:506  _same_path: empty/None never equals anything, spellings do
def test_same_path_semantics(tmp_path):
    from core.api import CoreApi
    same = CoreApi._same_path
    p = tmp_path / "a.belegtool"
    p.write_bytes(b"x")
    q = tmp_path / "b.belegtool"
    q.write_bytes(b"y")
    assert same(None, None) is False and same(None, str(p)) is False and same(str(p), None) is False
    assert same("", "") is False and same("", str(p)) is False
    assert same(str(p), str(p)) is True
    assert same(str(p), str(tmp_path / "sub" / ".." / "a.belegtool")) is True
    assert same(str(p), str(q)) is False
    assert same(str(p), str(tmp_path / "missing.belegtool")) is False
    link = tmp_path / "link.belegtool"
    try:
        os.link(str(p), str(link))
    except OSError:
        return                                   # no hard links on this filesystem
    assert same(str(p), str(link)) is True       # samefile(): a different spelling of the same file
