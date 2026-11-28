# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Round-10 review: R10-1 (HTML cap bypass) and R10-4 (engine identity memo pinning bytes)."""
import gc
import os
import sys
import time
import tracemalloc
import types

import pytest

for _m in ("pythoncom", "win32com", "win32com.client"):
    if _m not in sys.modules:
        try:
            __import__(_m)
        except ImportError:
            sys.modules[_m] = types.ModuleType(_m)
if not hasattr(sys.modules["win32com"], "client"):
    sys.modules["win32com"].client = sys.modules["win32com.client"]

from core.engine import RealEngine  # noqa: E402
from universal_importer import converters  # noqa: E402

N = 8000


def _refused_fast(html):
    t = time.time()
    with pytest.raises(ValueError):
        converters.html_to_pdf(html)
    assert time.time() - t < 3


def test_r10_1_data_prefix_does_not_swallow_markup():
    _refused_fast(("data:" + "A" * 64 + "<div>") * N)


def test_r10_1_svg_script_cdata_difference():
    _refused_fast("<svg><script>" + "<div>" * N)


@pytest.mark.parametrize("ctx", ["<svg><style>", "<textarea>", "<svg><script>"])
def test_r10_1_cdata_like_contexts(ctx):
    _refused_fast(ctx + "<div>" * 500)


@pytest.mark.parametrize("body", [
    "<img src='data:image/png;base64," + "QUJD" * 5000 + "'><p>hi</p>",
    "<p>x" * 150,
    "<ul>" + "<li>y" * 150 + "</ul>",
    "<div><blockquote>" * 60 + "</blockquote></div>" * 60,
    "<table>" + "<tr><td>a</td><td>b</td><td>c</td><td>d</td></tr>" * 1200 + "</table>",
    "<svg>" + "<path/>" * 300 + "</svg>",
])
def test_r10_1_legit_mail_still_passes(body):
    out = converters.html_to_pdf("<html><body>" + body + "</body></html>")
    assert out.data.getvalue().startswith(b"%PDF")


def test_r10_4_digest_memo_does_not_pin_dead_bytes():
    eng = RealEngine()
    gc.collect()
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    for _ in range(400):
        b = os.urandom(5_000_000)
        eng._digest(b)
        del b
    gc.collect()
    cur = tracemalloc.get_traced_memory()[0] - base
    tracemalloc.stop()
    assert cur < 150 * 1024 * 1024, cur / 1e6
