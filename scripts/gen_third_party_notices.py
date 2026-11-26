#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Collect the licence texts of every runtime dependency and (re)generate THIRD_PARTY_NOTICES.md.

Reproducible and offline: standard library only (``importlib.metadata`` + ``json`` + ``tomllib``), no timestamps
in the output. Run it inside the venv the app is built from (``build.ps1`` does so before PyInstaller):

    python scripts/gen_third_party_notices.py                 # writes ./licenses/ and updates THIRD_PARTY_NOTICES.md
    python scripts/gen_third_party_notices.py --check-only    # collect + verify, write nothing but a temp dir

What is collected
-----------------
* Python: every distribution named in ``requirements.txt`` (``name==ver`` or ``./packages/<p>``) plus, recursively,
  its ``Requires-Dist`` runtime dependencies as far as they are INSTALLED (``extra ==`` requirements are skipped;
  any other environment marker counts as "needed if installed" so the result does not depend on the build host's OS).
  For each: name, version, licence expression and every shipped licence file (``dist-info/licenses/**`` incl. e.g.
  pypdfium2's ``BUILD_LICENSES`` = pdfium/Skia/FreeType/... third-party texts, ``LICENSE*``/``COPYING*``/``NOTICE*``
  anywhere in the distribution's RECORD) copied to ``licenses/<dist>/``.
* npm: runtime packages (not ``dev``, not ``optional``) from ``webui/package-lock.json``; the licence files are copied
  from ``webui/node_modules`` when it exists, otherwise the row is marked "nicht erfasst".

A distribution WITHOUT a findable licence text is an ERROR (exit code 1) unless it is listed, with a reason, in
``NO_LICENSE_TEXT_EXCEPTIONS``. The generated table lives between the markers ``<!-- BEGIN GENERATED -->`` and
``<!-- END GENERATED -->`` of ``THIRD_PARTY_NOTICES.md``; the hand-written part above it is never touched.
"""
from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import re
import shutil
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BEGIN = "<!-- BEGIN GENERATED (scripts/gen_third_party_notices.py) -->"
END = "<!-- END GENERATED -->"

# Distribution (canonical name) -> reason why no licence TEXT file can be shipped. Empty on purpose: add an entry
# only with a verified reason (the error is there to be seen, not to be silenced).
NO_LICENSE_TEXT_EXCEPTIONS: dict[str, str] = {
    # pywebview dependency; PyPI offers only an sdist (proxy_tools-0.1.0.tar.gz, checked 2026-11-26) that contains
    # no licence file at all - only the metadata (`License: MIT`, classifier, setup.py; author Jonathan Tushman).
    "proxy-tools": "Sdist ohne Lizenzdatei; Metadaten: MIT (Jonathan Tushman), siehe docs/licence-audit.md",
}

_LICENSE_NAME = re.compile(r"^(licen[cs]e|copying|notice|copyright)", re.IGNORECASE)
_MAX_LICENSE_FILE_BYTES = 2_000_000  # a licence text is never this big; protects against odd RECORD entries


def _is_license_file(name: str) -> bool:
    return bool(_LICENSE_NAME.match(name)) and not name.lower().endswith((".py", ".pyc", ".pyi", ".pyd", ".dll", ".so"))


def canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# ---------------------------------------------------------------------------------------------- requirements

def parse_requirements(path: Path) -> list[str]:
    """Distribution names named in requirements.txt (pins, local ``./packages/x`` paths, ``name @ url``)."""
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith(("#", "-")):
            continue
        if line.startswith((".", "/")) and not re.match(r"^[A-Za-z]:", line):
            pyproject = (path.parent / line / "pyproject.toml")
            if pyproject.is_file():
                names.append(tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["name"])
            else:
                names.append(Path(line).name)
            continue
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", line)
        if m:
            names.append(m.group(1))
    return names


def _requires(dist: md.Distribution) -> list[str]:
    out = []
    for req in dist.requires or []:
        spec, _, marker = req.partition(";")
        if re.search(r"\bextra\b", marker):
            continue
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
        if m:
            out.append(m.group(1))
    return out


# ---------------------------------------------------------------------------------------------- python dists

@dataclass
class PyEntry:
    name: str
    version: str = ""
    license: str = ""
    files: list[str] = field(default_factory=list)  # relative to licenses/<dist>/
    installed: bool = True
    via: str = ""  # "requirements.txt" or the dependant


def license_expression(meta) -> str:
    expr = (meta.get("License-Expression") or "").strip()
    if expr:
        return expr
    lic = (meta.get("License") or "").strip()
    if lic and "\n" not in lic and len(lic) <= 120 and lic.upper() != "UNKNOWN":
        return lic
    classifiers = [c.split("::")[-1].strip() for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")]
    if classifiers:
        return "; ".join(classifiers)
    if lic and lic.upper() != "UNKNOWN":
        return lic.splitlines()[0].strip()[:120] + " (...)"
    return "unbekannt"


def _license_candidates(dist: md.Distribution) -> list[tuple[Path, str]]:
    """(absolute file, path relative to licenses/<dist>/) for every licence-looking file of the distribution."""
    found: dict[str, Path] = {}
    files = list(dist.files or [])
    for pp in files:
        parts = pp.parts
        in_info = len(parts) > 1 and parts[0].endswith((".dist-info", ".egg-info"))
        rel: str | None = None
        if in_info and len(parts) > 2 and parts[1] == "licenses":
            rel = "/".join(parts[2:])  # dist-info/licenses/**: take everything (incl. BUILD_LICENSES/*)
        elif _is_license_file(pp.name) and (in_info or len(parts) <= 4):
            rel = pp.name if in_info else "__".join(parts)
        if rel:
            found.setdefault(rel, pp.locate())
    if not files:  # no RECORD (hand-made / legacy dist): look inside the metadata directory itself
        info = getattr(dist, "_path", None)
        if info is not None and Path(info).is_dir():
            base = Path(info)
            for f in sorted(base.rglob("*")):
                if f.is_file() and (_is_license_file(f.name) or "licenses" in f.relative_to(base).parts[:1]):
                    r = f.relative_to(base).as_posix()
                    found.setdefault(r[len("licenses/"):] if r.startswith("licenses/") else r, f)
    out = []
    for rel, p in sorted(found.items()):
        p = Path(p)
        if p.is_file() and p.stat().st_size <= _MAX_LICENSE_FILE_BYTES:
            out.append((p, rel))
    return out


def collect_python(req_names: list[str], search_path: list[str] | None = None):
    paths = list(search_path or []) + list(sys.path)
    index: dict[str, md.Distribution] = {}
    for d in md.distributions(path=paths):
        n = d.metadata["Name"]
        if n:
            index.setdefault(canon(n), d)

    entries: dict[str, PyEntry] = {}
    texts: dict[str, list[tuple[Path, str]]] = {}
    queue = [(n, "requirements.txt") for n in req_names]
    while queue:
        name, via = queue.pop(0)
        key = canon(name)
        if key in entries:
            continue
        dist = index.get(key)
        if dist is None:
            entries[key] = PyEntry(name=name, installed=False, via=via)
            continue
        cands = _license_candidates(dist)
        entries[key] = PyEntry(name=dist.metadata["Name"], version=dist.version, license=license_expression(dist.metadata),
                               files=[r for _, r in cands], via=via)
        texts[key] = cands
        queue.extend((r, dist.metadata["Name"]) for r in _requires(dist))
    # A transitive dep that is simply not installed on this host (marker not applicable) is not an error.
    for key, e in list(entries.items()):
        if not e.installed and e.via != "requirements.txt":
            del entries[key]
    return entries, texts


# ---------------------------------------------------------------------------------------------- npm

@dataclass
class NpmEntry:
    name: str
    version: str
    license: str
    files: list[str] = field(default_factory=list)
    captured: bool = False


def collect_npm(webui: Path):
    lock = webui / "package-lock.json"
    if not lock.is_file():
        return [], {}
    packages = json.loads(lock.read_text(encoding="utf-8")).get("packages", {})
    entries: list[NpmEntry] = []
    texts: dict[str, list[tuple[Path, str]]] = {}
    for key, info in sorted(packages.items()):
        if not key or info.get("dev") or info.get("optional") or info.get("devOptional"):
            continue
        name = key.split("node_modules/")[-1] if "node_modules/" in key else key
        e = NpmEntry(name=name, version=info.get("version", "?"), license=str(info.get("license") or "unbekannt"))
        pkgdir = webui / key
        if pkgdir.is_dir():
            cands = [(f, f.name) for f in sorted(pkgdir.iterdir()) if f.is_file() and _is_license_file(f.name)]
            e.files = [r for _, r in cands]
            e.captured = True
            texts[name] = cands
        entries.append(e)
    return entries, texts


# ---------------------------------------------------------------------------------------------- output

def _cell(s: str) -> str:
    return re.sub(r"\s+", " ", s).replace("|", "\\|").strip()


def render_generated(py: dict[str, PyEntry], npm: list[NpmEntry]) -> str:
    L = [BEGIN, "",
         "## Automatisch erfasste Distributionen",
         "",
         "Erzeugt von [`scripts/gen_third_party_notices.py`](scripts/gen_third_party_notices.py) aus `requirements.txt` (+ rekursiven",
         "Laufzeit-Abhängigkeiten laut installierten Metadaten) und `webui/package-lock.json`. Die vollständigen Lizenztexte liegen im",
         "Ordner `licenses/<Distribution>/` (im Programmverzeichnis neben der exe; im Repo nicht eingecheckt, vom Build erzeugt).",
         "Die Tabelle gilt für das venv, in dem das Skript lief (die eingecheckte Fassung stammt aus einem Entwicklungs-venv; Versionen",
         "können von den Pins in `requirements.txt` abweichen). Maßgeblich ist die beim Build im Build-venv erzeugte Fassung (`build.ps1`).", "",
         "### Python", "",
         "| Distribution | Version | Lizenz | Lizenzdateien | Herkunft |", "|---|---|---|---|---|"]
    for key in sorted(py):
        e = py[key]
        if not e.installed:
            L.append(f"| {_cell(e.name)} | - | - | nicht im Erzeugungs-venv installiert (nicht erfasst) | {_cell(e.via)} |")
            continue
        n = len(e.files)
        exc = NO_LICENSE_TEXT_EXCEPTIONS.get(key)
        files = f"{n} (`licenses/{key}/`)" if n else f"keine ({_cell(exc)})" if exc else "FEHLT"
        L.append(f"| {_cell(e.name)} | {_cell(e.version)} | {_cell(e.license)} | {files} | {_cell(e.via)} |")
    L += ["", "### npm (Laufzeit, in `webui/dist` gebündelt)", ""]
    if npm:
        L += ["| Paket | Version | Lizenz | Lizenzdateien |", "|---|---|---|---|"]
        for e in npm:
            files = f"{len(e.files)} (`licenses/npm/{e.name}/`)" if e.captured and e.files else \
                "keine gefunden" if e.captured else "nicht erfasst (`webui/node_modules` fehlt)"
            L.append(f"| {_cell(e.name)} | {_cell(e.version)} | {_cell(e.license)} | {files} |")
        L += ["", "Optionale Node-only-Pakete (`@napi-rs/canvas*`, optionale Abhängigkeit von pdfjs-dist) landen nicht im Browser-Bundle und sind nicht erfasst."]
    else:
        L.append("`webui/package-lock.json` nicht gefunden - nicht erfasst.")
    L += ["", "PDF.js-Beipack (wasm/cmaps/Schriften): deren `LICENSE*`-Dateien liegen in `webui/dist/pdfjs/*/` (siehe oben).", "", END]
    return "\n".join(L)


def update_notices(path: Path, generated: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else "# Third-Party Notices\n"
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        tail = rest.split(END, 1)[1]
        new = head + generated + tail
    else:
        new = text.rstrip("\n") + "\n\n" + generated + "\n"
    if new != text:
        path.write_text(new, encoding="utf-8", newline="\n")


def write_licenses(out_dir: Path, py_texts, py: dict[str, PyEntry], npm_texts) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    for key, cands in py_texts.items():
        for src, rel in cands:
            dst = out_dir / key / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    for name, cands in npm_texts.items():
        for src, rel in cands:
            dst = out_dir / "npm" / name / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)


def problems(py: dict[str, PyEntry]) -> list[str]:
    errs = []
    for key, e in sorted(py.items()):
        if e.installed and not e.files and key not in NO_LICENSE_TEXT_EXCEPTIONS:
            errs.append(f"{e.name} {e.version}: kein Lizenztext gefunden (Ausnahme nur mit Begründung in NO_LICENSE_TEXT_EXCEPTIONS)")
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this repo)")
    ap.add_argument("--out-dir", type=Path, default=None, help="licence folder (default: <root>/licenses)")
    ap.add_argument("--notices", type=Path, default=None, help="notices file (default: <root>/THIRD_PARTY_NOTICES.md)")
    ap.add_argument("--path", action="append", default=[], help="extra directory searched for installed distributions "
                    "(e.g. an unzipped wheel folder); repeatable")
    ap.add_argument("--no-npm", action="store_true", help="skip the npm part")
    ap.add_argument("--check-only", action="store_true", help="collect + verify into a temp dir; do not touch the repo")
    args = ap.parse_args(argv)

    root: Path = args.root
    names = parse_requirements(root / "requirements.txt")
    py, py_texts = collect_python(names, args.path)
    npm, npm_texts = ([], {}) if args.no_npm else collect_npm(root / "webui")

    out_dir = args.out_dir or root / "licenses"
    notices = args.notices or root / "THIRD_PARTY_NOTICES.md"
    if args.check_only:
        tmp = Path(tempfile.mkdtemp(prefix="beleg_licenses_"))
        try:
            write_licenses(tmp / "licenses", py_texts, py, npm_texts)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        write_licenses(out_dir, py_texts, py, npm_texts)
        update_notices(notices, render_generated(py, npm))

    for e in py.values():
        if not e.installed:
            print(f"WARNUNG: {e.name} aus requirements.txt ist in diesem venv nicht installiert - nicht erfasst", file=sys.stderr)
    errs = problems(py)
    for m in errs:
        print("FEHLER:", m, file=sys.stderr)
    print(f"{sum(1 for e in py.values() if e.installed)} Python-Distributionen, {len(npm)} npm-Pakete erfasst; {len(errs)} Fehler")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
