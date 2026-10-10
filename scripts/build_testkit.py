"""Build the human-tester kit from manual_tests/*.md.

    python scripts/build_testkit.py            # sample files + all PDFs
    python scripts/build_testkit.py --check    # validate the sources only
    python scripts/build_testkit.py --no-pdf   # sample files only (no Edge needed)

Writes one folder per test case under manual_tests/testpakete/ (instruction PDF plus a
"Beispieldateien" folder), the overview 00_Start_hier.pdf, and the Microsoft Store
installation guide (docs/Installation_Microsoft_Store.pdf, copied into the kit).
The kit folder is owned by this script: files it did not write are removed.
"""

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.testkit import cases, page, pdf  # noqa: E402
from scripts.testkit.samples import SAMPLES  # noqa: E402
from version_info import VERSION  # noqa: E402

MANUAL = ROOT / "manual_tests"
KIT = MANUAL / "testpakete"
# What each PDF was printed from. Lets a test tell a stale PDF from a current one
# without needing a browser (tests/test_testkit.py).
MANIFEST = MANUAL / "testpakete.manifest.json"
SCRATCH = ROOT / ".tmp" / "testkit"
OVERVIEW_SRC = MANUAL / "README.md"
OVERVIEW_CUT = "<!-- testkit:entwickler -->"  # the README continues with maintainer notes
GUIDE_SRC = ROOT / "docs" / "installation-microsoft-store.md"
GUIDE_PDF = ROOT / "docs" / "Installation_Microsoft_Store.pdf"
OVERVIEW_NAME = "00_Start_hier.pdf"
GUIDE_NAME = "00_Installation_Microsoft_Store.pdf"
SAMPLE_DIR = "Beispieldateien"


@dataclass(frozen=True)
class Doc:
    name: str  # scratch file stem
    html: str
    pdf: Path
    title: str


def case_folder(area: cases.Area, case: cases.Case) -> Path:
    return KIT / area.folder_name / case.folder_name


def documents(areas: List[cases.Area]) -> List[Doc]:
    """Every PDF of the kit with the HTML it is printed from."""
    docs = [Doc(f"{area.number}_{case.id}", page.case_page(area, case, SAMPLES, VERSION),
                case_folder(area, case) / case.pdf_name, f"{case.id} – {case.title}")
            for area in areas for case in area.cases]
    overview = OVERVIEW_SRC.read_text(encoding="utf-8").split(OVERVIEW_CUT)[0]
    docs.append(Doc("00_overview",
                    page.document_page("Manuelle Tests – Start hier", overview, VERSION, "Manuelle Tests",
                                       extra_html=page.index_html(areas, SAMPLES)),
                    KIT / OVERVIEW_NAME, "BelegTool – Manuelle Tests"))
    docs.append(Doc("00_guide",
                    page.document_page("Installation aus dem Microsoft Store",
                                       GUIDE_SRC.read_text(encoding="utf-8"), VERSION, "Installation"),
                    GUIDE_PDF, "BelegTool – Installation aus dem Microsoft Store"))
    return docs


def manifest(docs: List[Doc]) -> Dict[str, str]:
    return {doc.pdf.relative_to(ROOT).as_posix(): hashlib.sha256(doc.html.encode("utf-8")).hexdigest()
            for doc in docs}


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _prune(root: Path, keep) -> int:
    """Remove everything under ``root`` that this run did not produce."""
    removed = 0
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file() and path not in keep:
            path.unlink()
            removed += 1
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return removed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="nur die Quellen prüfen")
    parser.add_argument("--no-pdf", action="store_true", help="keine PDFs drucken")
    args = parser.parse_args(argv)

    areas = cases.load_areas(MANUAL)
    problems = cases.validate(areas, SAMPLES)
    for problem in problems:
        print("FEHLER:", problem)
    for name in cases.unused_samples(areas, SAMPLES):
        print("Hinweis: Beispieldatei wird von keinem Test benutzt:", name)
    total = sum(len(area.cases) for area in areas)
    print(f"{len(areas)} Bereiche, {total} Testfälle, {len(SAMPLES)} Beispieldateien im Katalog")
    if problems:
        return 1
    if args.check:
        return 0

    built = {name: sample.build() for name, sample in SAMPLES.items()}
    written = {_write(case_folder(area, case) / SAMPLE_DIR / name, built[name])
               for area in areas for case in area.cases for name in case.samples}
    if args.no_pdf:
        print(f"{len(written)} Beispieldateien geschrieben; PDFs übersprungen (--no-pdf)")
        return 0

    docs = documents(areas)
    jobs = [(_write(SCRATCH / "html" / f"{doc.name}.html", doc.html.encode("utf-8")), doc.pdf, doc.title)
            for doc in docs]
    pdf.print_all(jobs, SCRATCH)
    written.update(doc.pdf for doc in docs if KIT in doc.pdf.parents)
    written.add(_write(KIT / GUIDE_NAME, GUIDE_PDF.read_bytes()))
    removed = _prune(KIT, written)
    MANIFEST.write_text(json.dumps(manifest(docs), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    size = sum(path.stat().st_size for path in written) / 1024 / 1024
    print(f"{len(docs)} PDFs gedruckt, {len(written)} Dateien im Testpaket ({size:.1f} MB), {removed} veraltete entfernt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
