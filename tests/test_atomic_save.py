# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Atomic unlocked save (QS-Gegenprüfung 2026-11-04, M-1).

``PDFStorage.save`` used to ``open(target, 'wb')`` the existing file directly —
a crash / full disk mid-write destroyed the previous state irrecoverably. The
fix writes a sibling temp file and ``os.replace``s it over the target; when the
replace is impossible (target held open without FILE_SHARE_DELETE) it falls back
to the legacy in-place write so saving never regresses.
"""

import os
from pathlib import Path

import fitz
import pytest

import formats.pdf_storage as ps
from core.bridge import save_belegtool
from core.model import Document, Node
from formats.pdf_storage import PDFStorage


def _pdf(n=1):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=200, height=200).insert_text((50, 80), f"P{i}")
    b = d.tobytes()
    d.close()
    return b


def _belegtool(tmp_path, name="doc"):
    doc = Document(Node(name="root", is_folder=True,
                        children=(Node(name="leaf", original_data=_pdf(2), pdf_length=2),)))
    path = str(tmp_path / f"{name}.belegtool")
    save_belegtool(doc, path)
    return path


class _PartialWriter:
    """Wraps a REAL writable file: the open truncates the target exactly like a real
    'wb' open, then the write fails mid-way (disk full) after a 100-byte prefix —
    the failure mode that destroys the old on-disk state with a direct overwrite."""

    def __init__(self, f):
        self._f = f

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self._f.close()
        return False

    def write(self, data):
        self._f.write(data[:100])
        self._f.flush()
        raise OSError(28, "No space left on device")

    def flush(self):
        pass

    def close(self):
        self._f.close()


def test_failed_write_keeps_the_original(tmp_path, monkeypatch):
    path = _belegtool(tmp_path)
    before = Path(path).read_bytes()

    real_open = open

    def fake_open(file, mode="r", *a, **k):
        if isinstance(mode, str) and "w" in mode and str(file).startswith(str(tmp_path)):
            return _PartialWriter(real_open(file, mode, *a, **k))
        return real_open(file, mode, *a, **k)

    storage = PDFStorage(path)
    monkeypatch.setattr(ps, "open", fake_open, raising=False)
    with pytest.raises(Exception):
        storage.save(path)
    monkeypatch.undo()

    assert Path(path).read_bytes() == before  # the original survives the failed save
    leftovers = [p for p in os.listdir(tmp_path) if p != os.path.basename(path)]
    assert leftovers == []  # no temp-file litter


def test_replace_failure_falls_back_to_in_place_write(tmp_path, monkeypatch):
    """A target held open without FILE_SHARE_DELETE makes os.replace fail — the save
    must still succeed (legacy in-place write) instead of erroring out."""
    path = _belegtool(tmp_path)
    storage = PDFStorage(path)

    def deny_replace(src, dst):
        raise PermissionError(13, "held open by another process")

    monkeypatch.setattr(ps.os, "replace", deny_replace)
    storage.save(path)
    monkeypatch.undo()

    reloaded = PDFStorage(path)
    assert [c.name for c in reloaded.root.children] == ["leaf"]
    leftovers = [p for p in os.listdir(tmp_path) if p != os.path.basename(path)]
    assert leftovers == []  # fallback cleaned its temp file


def test_normal_save_roundtrips_and_leaves_no_temp(tmp_path):
    path = _belegtool(tmp_path)
    storage = PDFStorage(path)
    storage.save(path)
    reloaded = PDFStorage(path)
    assert [c.name for c in reloaded.root.children] == ["leaf"]
    assert not getattr(reloaded, "load_warnings", [])
    leftovers = [p for p in os.listdir(tmp_path) if p != os.path.basename(path)]
    assert leftovers == []
