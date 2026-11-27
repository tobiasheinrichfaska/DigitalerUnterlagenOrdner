#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Add (or verify) SPDX headers in the Python sources of the separable packages under packages/*/ and of the main repo.

Every ``.py`` file gets, at the very top (after a shebang and/or an encoding line, before any docstring / ``from __future__``)::

    # SPDX-License-Identifier: AGPL-3.0-or-later
    # SPDX-FileCopyrightText: <the "Copyright ..." line of /LICENSE, verbatim>

Idempotent (a file that already has the identifier is left byte-for-byte untouched), line endings and a UTF-8 BOM are preserved.

    python scripts/add_spdx_headers.py            # add the missing headers in packages/*/ AND the main repo
    python scripts/add_spdx_headers.py --check    # exit 1 and list the files that lack one (writes nothing)
    python scripts/add_spdx_headers.py --paths core services   # restrict to the given directories/files
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LICENSE_ID = "AGPL-3.0-or-later"
_SKIP_DIRS = {"__pycache__", "build", "dist", ".git", ".venv", "venv", "node_modules"}
_ID_RE = re.compile(r"^#\s*SPDX-License-Identifier:\s*(\S+)", re.MULTILINE)
_CODING_RE = re.compile(r"^[ \t\f]*#.*?coding[:=][ \t]*[-\w.]+")


def copyright_line(license_path: Path = ROOT / "LICENSE") -> str:
    """The exact ``Copyright ...`` line of the project LICENSE (the single source of the holder/year)."""
    for line in license_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Copyright"):
            return line.strip()
    raise SystemExit(f"no 'Copyright' line in {license_path}")


def header_lines(copyright: str) -> list[str]:
    return [f"# SPDX-License-Identifier: {LICENSE_ID}", f"# SPDX-FileCopyrightText: {copyright}"]


MAIN_PATHS = ["core", "services", "formats", "infra", "universal_importer", "tools", "scripts", "tests",
              "host.py", "version_info.py", "datev_probe.py"]


def main_roots() -> list[Path]:
    """The main repo's own Python sources (directories and single files; released by the owner 2026-11-26)."""
    return [ROOT / p for p in MAIN_PATHS if (ROOT / p).exists()]


def source_files(roots: list[Path]) -> list[Path]:
    out: list[Path] = []
    for r in roots:
        if r.is_file():
            out.append(r)
            continue
        for p in sorted(r.rglob("*.py")):
            rel = p.relative_to(r).parts
            if any(part in _SKIP_DIRS or part.endswith(".egg-info") for part in rel):
                continue
            out.append(p)
    return out


def default_roots() -> list[Path]:
    """The three separable packages AND the main repo."""
    return package_roots() + main_roots()


def package_roots() -> list[Path]:
    # The packages moved to their own repos on 2026-11-27; kept for a checkout that still vendors some under packages/.
    pk = ROOT / "packages"
    return sorted(d for d in pk.iterdir() if d.is_dir()) if pk.is_dir() else []


def has_header(text: str) -> bool:
    head = "\n".join(text.splitlines()[:15])
    return bool(_ID_RE.search(head))


def conflicting_id(text: str) -> str | None:
    m = _ID_RE.search("\n".join(text.splitlines()[:15]))
    return m.group(1) if m and m.group(1) != LICENSE_ID else None


def add_header(text: str, copyright: str) -> str:
    """Return ``text`` with the header inserted (unchanged if it already has one). Pure, newline/BOM preserving."""
    if has_header(text):
        return text
    bom = "﻿" if text.startswith("﻿") else ""
    body = text[len(bom):]
    nl = "\r\n" if "\r\n" in body else "\n"
    lines = body.split(nl) if body else []
    keep = 0
    if lines and lines[0].startswith("#!"):
        keep = 1
    if len(lines) > keep and _CODING_RE.match(lines[keep]):
        keep += 1
    head = nl.join(lines[:keep])
    rest = nl.join(lines[keep:])
    hdr = nl.join(header_lines(copyright))
    parts = []
    if keep:
        parts.append(head + nl)
    parts.append(hdr + nl)
    if rest:
        parts.append(rest)
    return bom + "".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="only verify; exit 1 if a header is missing")
    ap.add_argument("--paths", nargs="*", default=None, help="directories (relative to the repo root) instead of packages/*")
    args = ap.parse_args(argv)

    roots = [ROOT / p for p in args.paths] if args.paths else default_roots()
    cr = copyright_line()
    missing: list[Path] = []
    conflicts: list[tuple[Path, str]] = []
    for f in source_files(roots):
        text = f.read_bytes().decode("utf-8")
        other = conflicting_id(text)
        if other:
            conflicts.append((f, other))
            continue
        if not has_header(text):
            missing.append(f)
            if not args.check:
                f.write_bytes(add_header(text, cr).encode("utf-8"))
    for f, other in conflicts:
        print(f"KONFLIKT: {f.relative_to(ROOT)} traegt SPDX-Id {other} (nicht angefasst)", file=sys.stderr)
    if args.check:
        for f in missing:
            print(f"SPDX-Kopf fehlt: {f.relative_to(ROOT)}", file=sys.stderr)
        print(f"{len(missing)} Datei(en) ohne SPDX-Kopf")
        return 1 if missing or conflicts else 0
    print(f"{len(missing)} Datei(en) ergaenzt")
    return 1 if conflicts else 0


if __name__ == "__main__":
    raise SystemExit(main())
