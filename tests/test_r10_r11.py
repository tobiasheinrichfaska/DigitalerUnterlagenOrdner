# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""R-10 (embed_variants when os.replace fails) and R-11 (bounded negative render cache)."""
import os
import pikepdf

from services import variant_store
from services.render_service import RenderService


def test_r10_embed_falls_back_in_place_when_replace_denied(tmp_path, monkeypatch):
    p = tmp_path / "a.belegtool"
    pdf = pikepdf.new(); pdf.add_blank_page(); pdf.save(p); pdf.close()
    monkeypatch.setattr(variant_store, "_collect_variant_blobs", lambda *a, **k: {"variant_x": b"zz"})

    def deny(*a, **k):
        raise PermissionError(5, "held open")
    monkeypatch.setattr(os, "replace", deny)
    assert variant_store.embed_variants(str(p), None, None) == 1
    with pikepdf.open(p) as q:
        assert "variant_x" in q.attachments
    assert not [f for f in os.listdir(tmp_path) if ".tmp-" in f]


def test_r11_failing_page_is_not_rerendered_forever():
    calls = []

    def fail(data, page, dpi):
        calls.append(page)
        return b""
    svc = RenderService(fail, cpu_load=lambda: 0.0, max_workers=1)
    for _ in range(10):
        svc.render_window("n", 1, b"x", 0, 1, 100)
    assert len(calls) <= 3
    # background fill must not re-submit known failures either
    n = len(calls)
    svc.fill_until_idle([("n", 1, 3)], "n", 0, lambda nid: b"x", 100)
    svc.fill_until_idle([("n", 1, 3)], "n", 0, lambda nid: b"x", 100)
    assert calls.count(0) <= 3 and len(calls) - n <= 2
    svc.invalidate("n")
    svc.render_window("n", 1, b"x", 0, 1, 100)
    assert len(calls) > n
