# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""u4 audit (BP-1..BP-4, BP-7): CoreApi.open is transactional + validates loaded fields."""

import io
import json
import uuid
from unittest import mock

import pytest
from pypdf import PdfWriter

from core.api import CoreApi


def _leaf(name="a", n=1, **kw):
    d = dict(uid=uuid.uuid4().hex, name=name, is_folder=False, status="", position=0,
             vz_start=None, vz_end=None, pdf_length=n, is_compressed=False, dpi_original=None,
             dpi_current=None, no_compression=False, compression_no_gain=False,
             collapsed=False, compression_method=None, tags=[], datev=None, children=[])
    d.update(kw)
    return d


def _root(children, **kw):
    d = _leaf("root", 0, is_folder=True, children=list(children))
    d.update(kw)
    return d


def _make(structure, npages, path):
    w = PdfWriter()
    for i in range(npages):
        w.add_blank_page(200 + i, 300)
    w.add_metadata({"/JSONStructure": json.dumps(structure)})
    with open(path, "wb") as f:
        w.write(f)


def _names(tree):
    yield tree["name"]
    for c in tree.get("children", []):
        yield from _names(c)


def _open_good(api, tmp_path):
    p = tmp_path / "good.belegtool"
    _make(_root([_leaf("mine", 1)]), 1, p)
    r = api.open(None, str(p))
    sid = r["session"]
    api.dispatch(sid, {"type": "Rename", "node_id": r["tree"]["children"][0]["id"],
                       "name": "unsaved edit"})
    return sid, p


@pytest.mark.parametrize("uid", [["u"], {"a": 1}, 5, 1.5, True])
def test_bad_uid_is_regenerated_with_warning_and_unbound(tmp_path, uid):
    p = tmp_path / "bad.belegtool"
    _make(_root([_leaf("x", 1, uid=uid)]), 1, p)
    api = CoreApi()
    sid0, _ = _open_good(api, tmp_path)
    r = api.open(sid0, str(p))
    assert r["ok"] is True and r.get("warning")
    assert api._paths.get(r["session"]) is None
    assert isinstance(r["tree"]["children"][0]["id"], str)
    api.get_state(r["session"])  # session healthy


def test_failed_open_leaves_previous_session_untouched(tmp_path):
    api = CoreApi()
    sid, good = _open_good(api, tmp_path)
    bad = tmp_path / "bad.belegtool"
    _make(_root([_leaf("x", 1)]), 1, bad)
    with mock.patch.object(CoreApi, "_doc_response_locked", side_effect=[TypeError("boom")]):
        r = api.open(sid, str(bad))
    assert r["ok"] is False and r["error"]
    st = api.get_state(sid)
    assert "unsaved edit" in list(_names(st["tree"])) and st["dirty"] is True
    assert api._paths.get(sid) is None or api._paths[sid] != str(bad)


def _nested(depth):
    node = _leaf("leaf", 1)
    for _ in range(depth):
        node = dict(_leaf("f", 0, is_folder=True), children=[node])
    return _root([node])


def test_open_never_raises_on_too_deep_or_garbage(tmp_path):
    api = CoreApi()
    sid, _ = _open_good(api, tmp_path)
    deep = tmp_path / "deep.belegtool"
    _make(_nested(250), 1, deep)
    empty = tmp_path / "empty.belegtool"
    empty.write_bytes(b"")
    junk = tmp_path / "junk.belegtool"
    junk.write_bytes(b"not a pdf at all")
    for p in (deep, empty, junk):
        r = api.open(sid, str(p))
        assert r["ok"] is False and isinstance(r["error"], str) and r["error"]
    assert "unsaved edit" in list(_names(api.get_state(sid)["tree"]))


def test_field_validation_coerces_and_warns(tmp_path):
    p = tmp_path / "f.belegtool"
    s = _root([
        _leaf("a", 1, tags=[1, "ok", None, {"k": 1}], status="bogus", collapsed="false",
              no_compression="false"),
        _leaf(None, 1, tags="abc"),
        _leaf(["n"], 1),
    ])
    _make(s, 3, p)
    api = CoreApi()
    r = api.open(None, str(p))
    assert r["ok"] and r.get("warning")
    assert api._paths.get(r["session"]) is None
    kids = r["tree"]["children"]
    assert kids[0]["tags"] == ["ok"] and kids[0]["status"] == ""
    assert kids[1]["tags"] == [] and isinstance(kids[1]["name"], str) and kids[1]["name"]
    assert isinstance(kids[2]["name"], str)
    # exportable + savable
    assert api.save(r["session"], str(tmp_path / "re.belegtool"))["ok"]
    assert api.export(r["session"], str(tmp_path / "e.pdf"))["ok"]


def test_duplicate_uids_are_reidentified(tmp_path):
    p = tmp_path / "d.belegtool"
    _make(_root([_leaf("a", 1, uid="X"), _leaf("b", 1, uid="X")]), 2, p)
    api = CoreApi()
    r = api.open(None, str(p))
    ids = [c["id"] for c in r["tree"]["children"]]
    assert len(set(ids)) == 2 and r.get("warning")


def test_clean_file_has_no_warning_and_is_bound(tmp_path):
    p = tmp_path / "c.belegtool"
    _make(_root([_leaf("a", 1, tags=["t"], status="erfasst", collapsed=True)]), 1, p)
    api = CoreApi()
    r = api.open(None, str(p))
    assert r["ok"] and not r.get("warning") and api._paths[r["session"]] == str(p)


def test_lone_surrogate_name_survives_rename_save_export_reopen(tmp_path):
    p = tmp_path / "s.belegtool"
    _make(_root([_leaf("a", 1)]), 1, p)
    api = CoreApi()
    r = api.open(None, str(p))
    sid = r["session"]
    nid = r["tree"]["children"][0]["id"]
    api.dispatch(sid, {"type": "Rename", "node_id": nid, "name": "bad\ud83dname"})
    out = tmp_path / "o.belegtool"
    assert api.save(sid, str(out))["ok"]
    assert api.export(sid, str(tmp_path / "o.pdf"))["ok"]
    r2 = api.open(None, str(out))
    assert r2["ok"] and r2["tree"]["children"][0]["name"] == "bad�name"


def test_lone_surrogate_in_file_name_is_normalised(tmp_path):
    p = tmp_path / "s2.belegtool"
    raw = json.dumps(_root([_leaf("a\ud83db", 1)]))
    _make(json.loads(raw), 1, p)
    api = CoreApi()
    r = api.open(None, str(p))
    assert r["ok"] and r["tree"]["children"][0]["name"] == "a�b"
    assert api.save(r["session"], str(tmp_path / "x.belegtool"))["ok"]


@pytest.mark.parametrize("dv", ["x", 5, [1]])
def test_non_dict_root_datev_ignored(tmp_path, dv):
    p = tmp_path / "dv.belegtool"
    _make(_root([_leaf("a", 1)], datev=dv), 1, p)
    api = CoreApi()
    r = api.open(None, str(p))
    assert r["ok"] and r.get("warning")
    api._datev_mode = True
    api._datev_get_service = lambda block=False: mock.MagicMock()
    out = api.datev_export(r["session"], None, {})  # must not raise
    assert isinstance(out, dict)
