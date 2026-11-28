# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Q-1 (NUL gate on the path branch sees 4 KB) and Q-2 (negative render cache expires)."""
from services.render_service import RenderService
import sys
import types



def test_q1_path_branch_nul_gate_sees_4k(tmp_path, monkeypatch):
    for m in ("pythoncom", "win32com", "win32com.client", "pywintypes"):
        if m not in sys.modules:
            try:
                __import__(m)
            except ImportError:
                monkeypatch.setitem(sys.modules, m, types.ModuleType(m))
    from universal_importer import UniversalImporter
    p = tmp_path / "x.txt"
    p.write_bytes(b"MZ" + b"A" * 14 + b"\x00" * 200)
    try:
        UniversalImporter.convert(str(p))
    except ValueError:
        return
    raise AssertionError("binary content with MZ header accepted as .txt")


def test_q2_transient_failure_is_retried_after_ttl():
    state = {"fail": 2, "t": 1000.0}

    def render(data, page, dpi):
        if state["fail"] > 0:
            state["fail"] -= 1
            return b""
        return b"PNG"
    svc = RenderService(render, cpu_load=lambda: 0.0, max_workers=1)
    svc._clock = lambda: state["t"]
    assert [svc.render_window("n", 1, b"x", 0, 1, 100)[0] for _ in range(3)] == [b"", b"", b""]
    state["t"] += svc.FAILURE_TTL + 1
    assert svc.render_window("n", 1, b"x", 0, 1, 100) == [b"PNG"]
