# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""IO-3: export writes are atomic per file; a failed split leaves no mixed set."""
import builtins
import errno
import os

import pytest
import fitz

from formats.pdf_node import PDFNode
from formats.toc_export import export_pdf, export_pdf_split_with_toc


def _pdf(n=1):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=300, height=300).insert_text((40, 60), f"p{i}")
    b = d.tobytes()
    d.close()
    return b


def _leaf(name, pages=1):
    n = PDFNode(name=name, pdf_data=_pdf(pages))
    n.pdf_length = pages
    return n


def _nodes():
    return [_leaf("a", 2), _leaf("b", 2), _leaf("c", 2)]


class _Fault:
    """Fail the Nth write()/os.replace() touching ``match`` (partial write first)."""
    def __init__(self, mp, kind, n, match=""):
        self.kind, self.n, self.match, self.c, self.fired = kind, n, match, 0, False
        orig_open, orig_replace = builtins.open, os.replace
        me = self

        class W:
            def __init__(w, f, p): w.f, w.p = f, p
            def write(w, b):
                if me.kind == "write" and me.match in str(w.p):
                    me.c += 1
                    if me.c == me.n:
                        me.fired = True
                        w.f.write(b[: len(b) // 2])
                        raise OSError(errno.ENOSPC, "No space left on device")
                return w.f.write(b)
            def __getattr__(w, k): return getattr(w.f, k)
            def __enter__(w): w.f.__enter__(); return w
            def __exit__(w, *a): return w.f.__exit__(*a)

        def fopen(file, mode="r", *a, **k):
            f = orig_open(file, mode, *a, **k)
            if isinstance(file, (str, os.PathLike)) and "b" in mode and "w" in mode:
                return W(f, file)
            return f

        def freplace(src, dst, *a, **k):
            if me.kind == "replace" and me.match in str(dst):
                me.c += 1
                if me.c == me.n:
                    me.fired = True
                    raise OSError(errno.ENOSPC, "boom")
            return orig_replace(src, dst, *a, **k)

        mp.setattr(builtins, "open", fopen)
        mp.setattr(os, "replace", freplace)


def test_single_export_failure_keeps_previous_file(tmp_path, monkeypatch):
    out = str(tmp_path / "exp.pdf")
    export_pdf(_nodes(), out)
    old = open(out, "rb").read()
    _Fault(monkeypatch, "write", 1, "exp.pdf")
    with pytest.raises(OSError):
        export_pdf(_nodes(), out)
    monkeypatch.undo()
    assert open(out, "rb").read() == old
    assert os.listdir(tmp_path) == ["exp.pdf"]


@pytest.mark.parametrize("kind", ["write", "replace"])
@pytest.mark.parametrize("n", [1, 2, 3])
def test_split_failure_leaves_no_mixed_set(tmp_path, monkeypatch, kind, n):
    out = str(tmp_path / "sp.pdf")
    paths = export_pdf_split_with_toc(_nodes(), out, 2)
    assert len(paths) == 3
    before = {p: open(p, "rb").read() for p in paths}
    fault = _Fault(monkeypatch, kind, n, "sp_")
    with pytest.raises(OSError) as ei:
        export_pdf_split_with_toc(_nodes(), out, 2)
    monkeypatch.undo()
    assert fault.fired
    assert "sp_Teil_" in str(ei.value)  # names the failing file
    for p, b in before.items():
        assert open(p, "rb").read() == b, os.path.basename(p)
    assert sorted(os.listdir(tmp_path)) == sorted(os.path.basename(p) for p in paths)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_fresh_split_failure_removes_new_parts(tmp_path, monkeypatch, n):
    out = str(tmp_path / "sp.pdf")
    _Fault(monkeypatch, "replace", n, "sp_")
    with pytest.raises(OSError):
        export_pdf_split_with_toc(_nodes(), out, 2)
    monkeypatch.undo()
    assert os.listdir(tmp_path) == []
