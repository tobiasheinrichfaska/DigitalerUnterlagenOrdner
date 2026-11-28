# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Regression tests for the s3 second-pass audit (SV-1/2/3/5/6)."""

import io
import json
import os
import threading
import zipfile
from types import SimpleNamespace

import pikepdf

from infra import file_lock, settings, window_geometry
from services import variant_store
from services.render_service import RenderService


def _deflate_blob(n_bytes):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("150/jpg", b"\0" * n_bytes)
    return buf.getvalue()


def test_sv3_decoded_total_is_shared_across_attachments(tmp_path, monkeypatch):
    monkeypatch.setattr(variant_store, "MAX_TOTAL_DECODED_BYTES", 250_000, raising=False)
    path = str(tmp_path / "f.pdf")
    with pikepdf.new() as pdf:
        pdf.add_blank_page()
        for i in range(8):
            pdf.attachments[f"variant_n{i}"] = pikepdf.AttachedFileSpec(
                pdf, _deflate_blob(100_000), mime_type="application/zip")
        pdf.save(path)
    nodes = [SimpleNamespace(id=f"n{i}", is_folder=False, original_data=b"src%d" % i)
             for i in range(8)]
    doc = SimpleNamespace(root=SimpleNamespace(iter=lambda: iter(nodes)))
    retained = []
    engine = SimpleNamespace(seed_variants=lambda src, v: retained.append(
        sum(len(b) for m in v.values() for b in m.values())))
    variant_store.seed_variants_from_file(path, doc, engine)
    assert sum(retained) <= 250_000


def test_sv1_deeply_nested_settings_fall_back_to_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("[" * 100000 + "]" * 100000)
    assert settings.load_settings(str(p)) == dict(settings.DEFAULTS)


def test_sv2_infinity_geometry_is_invalid_not_raising():
    g = {"x": float("inf"), "y": 0, "width": 500, "height": 500}
    assert window_geometry.valid_geometry(g) is False
    g = {"x": 0, "y": 0, "width": float("inf"), "height": 500}
    assert window_geometry.valid_geometry(g) is False


def test_sv5_failed_restore_keeps_bak_and_wip(tmp_path, monkeypatch):
    import shutil
    target = tmp_path / "a.belegtool"
    target.write_bytes(b"half")
    (tmp_path / "a.belegtool.bak").write_bytes(b"%PDF good %%EOF")
    (tmp_path / "a.belegtool.wip").write_bytes(b"")

    def boom(*a, **k):
        raise PermissionError("held")
    monkeypatch.setattr(shutil, "copyfile", boom)
    try:
        file_lock.restore_from_bak(str(target))
    except Exception:
        pass
    assert (tmp_path / "a.belegtool.bak").exists()
    assert (tmp_path / "a.belegtool.wip").exists()


def test_sv6_inflight_render_does_not_reinsert_dead_node():
    started, go = threading.Event(), threading.Event()

    def slow(d, p, dpi):
        started.set()
        go.wait()
        return b"y" * 100

    rs = RenderService(slow, budget_bytes=10 ** 6, cpu_load=lambda: 0.0, max_workers=2)
    t = threading.Thread(target=lambda: rs.fill_until_idle(
        [("dead", 1, 3)], "dead", 0, lambda x: b"", 150))
    t.start()
    started.wait()
    rs.invalidate("dead")
    rs.prune([])
    go.set()
    t.join()
    assert list(rs.cache._store) == []
