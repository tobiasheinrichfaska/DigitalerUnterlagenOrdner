# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""HTML → PDF through headless Microsoft Edge (the engine the app itself runs in, so the
toolbar emoji in the instructions look exactly like the buttons on screen)."""

import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable, Tuple

import pikepdf

_EDGE = Path("Microsoft") / "Edge" / "Application" / "msedge.exe"
# Fixed document date: regenerating the kit must not rewrite every PDF just for a timestamp.
_FIXED_DATE = "D:20250115120000+00'00'"


def find_browser() -> Path:
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base and (Path(base) / _EDGE).is_file():
            return Path(base) / _EDGE
    raise FileNotFoundError("Microsoft Edge (msedge.exe) nicht gefunden – zum PDF-Druck erforderlich.")


def _print(browser: Path, html_path: Path, pdf_path: Path, profile: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.unlink(missing_ok=True)
    # Own profile dir: with the user's default profile a running Edge would swallow the call.
    subprocess.run(
        [str(browser), "--headless", "--disable-gpu", "--no-first-run", "--disable-extensions",
         "--no-pdf-header-footer", f"--user-data-dir={profile}", f"--print-to-pdf={pdf_path}",
         html_path.as_uri()],
        check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not pdf_path.is_file():
        raise RuntimeError(f"Edge hat kein PDF geschrieben: {pdf_path}")


def _finish(pdf_path: Path, title: str) -> None:
    """Replace the browser's metadata (user agent, print time) with stable, meaningful values."""
    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        pdf.docinfo = pdf.make_indirect(pikepdf.Dictionary(
            Title=title, Author="BelegTool", Creator="BelegTool Testkit",
            CreationDate=_FIXED_DATE, ModDate=_FIXED_DATE))
        if "/Metadata" in pdf.Root:
            del pdf.Root["/Metadata"]
        pdf.save(pdf_path, deterministic_id=True)


def print_all(jobs: Iterable[Tuple[Path, Path, str]], scratch: Path, workers: int = 4) -> None:
    """Print every (html file, pdf file, title) job; one browser profile per worker thread."""
    browser = find_browser()

    def run(job):
        html_path, pdf_path, title = job
        _print(browser, html_path, pdf_path, scratch / f"edge-profile-{threading.get_ident()}")
        _finish(pdf_path, title)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(run, jobs))
