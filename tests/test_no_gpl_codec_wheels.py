# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Licence guard: no GPL HEVC encoder (x265) may ride along in the HEIC dependency.

pillow-heif's Windows wheel bundles ``libx265`` (GPLv2) -> docs/licence-audit.md (red).
pi-heif's wheel carries only libheif/libde265 (LGPLv3). This test keeps it that way:
it fails when any file named like ``*x265*`` belongs to the installed ``pi-heif``
distribution or sits in its package / ``pi_heif.libs`` / ``.libs`` neighbour folders.
delvewheel wheels (pi-heif on Windows) install their DLLs next to the package in
site-packages, so the distribution's file list (RECORD) is checked as well.
"""
import importlib.util
import warnings
from importlib import metadata
from pathlib import Path

import pytest


def _pi_heif_dirs():
    spec = importlib.util.find_spec("pi_heif")
    if spec is None or not spec.submodule_search_locations:
        return []
    pkg = Path(list(spec.submodule_search_locations)[0])
    site = pkg.parent
    return [pkg, site / "pi_heif.libs", site / "pi_heif.libs".replace("_", "-"), site / ".libs"]


def _x265_hits():
    hits = []
    for d in _pi_heif_dirs():
        if d.is_dir():
            hits += [str(p) for p in d.rglob("*") if "x265" in p.name.lower()]
    try:
        dist = metadata.distribution("pi-heif")
    except metadata.PackageNotFoundError:
        dist = None
    if dist is not None:
        hits += [str(f) for f in (dist.files or []) if "x265" in f.name.lower()]
    return sorted(set(hits))


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("pi_heif") is None, reason="pi_heif not installed"
)


def test_pi_heif_ships_no_x265():
    hits = _x265_hits()
    assert not hits, f"GPL x265 found in the HEIC dependency (see docs/licence-audit.md): {hits}"


def test_pi_heif_has_no_hevc_encoder_registered():
    import pi_heif

    info = pi_heif.libheif_info()
    assert "x265" not in str(info.get("HEIF", "")).lower(), info


def test_pillow_heif_is_not_installed():
    """pillow-heif replaced by pi-heif (x265 in its Windows wheel). Not a hard failure:
    a dev machine may keep it as an HEVC encoder, but it must never be in the
    requirements/build venv."""
    if importlib.util.find_spec("pillow_heif") is not None:
        warnings.warn(
            "pillow_heif is installed; it bundles GPL x265 in its Windows wheel and must "
            "not be in the build venv (use pi-heif, see docs/licence-audit.md).",
            stacklevel=1,
        )
    reqs = (Path(__file__).resolve().parent.parent / "requirements.txt").read_text(encoding="utf-8")
    assert "pillow-heif" not in reqs.lower().replace("_", "-")
