# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Engine-level cancellation of compression (needs core.engine, so it stays in the host repo)."""

import fitz


def _make_pdf(n_pages: int) -> bytes:
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page(width=300, height=400)
        page.insert_text((40, 80 + (i % 5) * 30), f"PAGE {i + 1} of {n_pages}")
    data = doc.tobytes()
    doc.close()
    return data


def test_engine_does_not_memoise_cancelled():
    """A cancelled compress returns None and doesn't poison the memo."""
    from core.engine import RealEngine
    eng = RealEngine()
    data = _make_pdf(6)
    assert eng.compress(data, 100, cancel=lambda: True) is None  # cancelled immediately
    eng.compress(data, 100)  # uncancelled run must still work (memo wasn't poisoned)
