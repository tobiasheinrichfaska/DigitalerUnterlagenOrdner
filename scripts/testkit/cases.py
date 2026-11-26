# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Manual test cases as data: parse ``manual_tests/NN_<area>.md`` into areas and cases.

Pure logic (no rendering, no file output). The Markdown files stay the single source
of truth; the PDFs and the per-test sample folders are derived from this model.

Source format of one case::

    ## MT-01: Titel

    **Ab Version:** 3.10.0                      (optional)
    **Beispieldateien:** `a.pdf`, `b.zip`       (optional)

    **Voraussetzungen:** ...
    **Schritte:** ...                           (may repeat, e.g. "Schritte (A – ...)")
    **Erwartet:** ...
"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# Section label in the Markdown → kind. Adding a section type means adding a row here
# (and its presentation in page.SECTION_STYLE).
SECTION_LABELS = {
    "Voraussetzungen": "voraussetzungen",
    "Schritte": "schritte",
    "Erwartet": "erwartet",
    "Hinweis": "hinweis",
}
REQUIRED_KINDS = ("schritte", "erwartet")
SINCE_LABEL = "Ab Version"
SAMPLES_LABEL = "Beispieldateien"

_AREA_FILE = re.compile(r"^(\d{2})_([a-z0-9_]+)\.md$")
_AREA_TITLE = re.compile(r"^# (?:\d{2}\s*[—–-]\s*)?(.+)$")  # "# 01 — Import" → "Import"
_CASE_HEADING = re.compile(r"^## (MT-[A-Za-z0-9-]+): (.+)$")
_FIELD = re.compile(
    r"^\*\*(" + "|".join([*SECTION_LABELS, SINCE_LABEL, SAMPLES_LABEL]) + r")"
    r"(?: \(([^)]*)\))?:\*\*\s*(.*)$")
_RULE = re.compile(r"^-{3,}\s*$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_BACKTICKED = re.compile(r"`([^`]+)`")
_TRANSLIT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


@dataclass(frozen=True)
class Section:
    kind: str
    qualifier: str  # "" unless the label carries one, e.g. "Schritte (A – Zuklappen)"
    body: str       # Markdown


@dataclass(frozen=True)
class Case:
    area_number: str
    id: str
    title: str
    since: Optional[str]
    samples: Tuple[str, ...]
    intro: str  # Markdown before the first section
    sections: Tuple[Section, ...]

    @property
    def folder_name(self) -> str:
        # a parenthetical in the title ("… (JPG / PNG / WEBP)") only clutters the name
        return f"{self.id}_{slugify(self.title.split(' (')[0])}"

    @property
    def pdf_name(self) -> str:
        # Area-prefixed: test ids repeat across areas, the PDF name must not.
        return f"{self.area_number}_{self.folder_name}.pdf"


@dataclass(frozen=True)
class Area:
    number: str
    slug: str
    title: str
    intro: str  # Markdown before the first case
    source: str  # file name, shown in the PDF footer
    cases: Tuple[Case, ...]

    @property
    def folder_name(self) -> str:
        return f"{self.number}_{self.slug}"


def slugify(text: str, limit: int = 48) -> str:
    """File-system-safe ASCII name part (German umlauts transliterated)."""
    ascii_text = unicodedata.normalize("NFKD", text.translate(_TRANSLIT)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-")
    if len(slug) > limit:
        # cut at a word boundary rather than mid-word
        slug = slug[:limit + 1].rsplit("-", 1)[0]
    return slug


def _strip_rules(lines: Iterable[str]) -> str:
    return "\n".join(line for line in lines if not _RULE.match(line)).strip()


def _parse_case(area_number: str, case_id: str, title: str, lines: List[str]) -> Case:
    since = None
    samples: Tuple[str, ...] = ()
    intro: List[str] = []
    sections: List[Tuple[str, str, List[str]]] = []
    for line in lines:
        field = _FIELD.match(line)
        if not field:
            (sections[-1][2] if sections else intro).append(line)
            continue
        label, qualifier, rest = field.group(1), field.group(2) or "", field.group(3)
        if label == SINCE_LABEL:
            since = rest.strip()
        elif label == SAMPLES_LABEL:
            samples = tuple(_BACKTICKED.findall(rest))
        else:
            sections.append((SECTION_LABELS[label], qualifier, [rest]))
    return Case(
        area_number=area_number, id=case_id, title=title.strip(), since=since, samples=samples,
        intro=_strip_rules(intro),
        sections=tuple(Section(kind, qualifier, _strip_rules(body)) for kind, qualifier, body in sections))


def parse_area(filename: str, text: str) -> Area:
    """Parse one ``NN_<area>.md`` file. Raises ValueError on a malformed file name/title."""
    name = _AREA_FILE.match(filename)
    if not name:
        raise ValueError(f"{filename}: erwartet wird NN_<bereich>.md")
    lines = text.replace("\r\n", "\n").split("\n")
    title = next((m.group(1).strip() for m in map(_AREA_TITLE.match, lines) if m), None)
    if title is None:
        raise ValueError(f"{filename}: Überschrift '# NN — Titel' fehlt")

    intro: List[str] = []
    blocks: List[Tuple[str, str, List[str]]] = []
    for line in lines:
        heading = _CASE_HEADING.match(line)
        if heading:
            blocks.append((heading.group(1), heading.group(2), []))
        elif blocks:
            blocks[-1][2].append(line)
        elif not _AREA_TITLE.match(line):
            intro.append(line)
    return Area(
        number=name.group(1), slug=name.group(2), title=title, intro=_strip_rules(intro),
        source=filename,
        cases=tuple(_parse_case(name.group(1), cid, ctitle, body) for cid, ctitle, body in blocks))


def load_areas(directory: Path) -> List[Area]:
    """All areas under ``directory``, ordered by their number."""
    files = sorted(p for p in Path(directory).glob("*.md") if _AREA_FILE.match(p.name))
    return [parse_area(p.name, p.read_text(encoding="utf-8")) for p in files]


def validate(areas: Iterable[Area], known_samples: Iterable[str]) -> List[str]:
    """Problems that would make the kit incomplete or ambiguous; empty list = valid."""
    known = set(known_samples)
    problems: List[str] = []
    for area in areas:
        where = area.source
        if not area.cases:
            problems.append(f"{where}: enthält keinen Testfall")
        seen = set()
        for case in area.cases:
            ref = f"{where} {case.id}"
            if case.id in seen:
                problems.append(f"{ref}: Test-ID kommt im Bereich doppelt vor")
            seen.add(case.id)
            if "`" in case.title or "*" in case.title:
                # the title also becomes a folder name, a file name and the PDF title
                problems.append(f"{ref}: Titel enthält Markdown-Zeichen")
            kinds = [s.kind for s in case.sections]
            for kind in REQUIRED_KINDS:
                if kind not in kinds:
                    problems.append(f"{ref}: Abschnitt '{kind}' fehlt")
            for section in case.sections:
                if not section.body:
                    problems.append(f"{ref}: Abschnitt '{section.kind}' ist leer")
            if case.since is not None and not _VERSION.match(case.since):
                problems.append(f"{ref}: 'Ab Version' ist keine Version X.Y.Z ({case.since!r})")
            for sample in case.samples:
                if sample not in known:
                    problems.append(f"{ref}: Beispieldatei '{sample}' ist nicht im Katalog")
    return problems


def unused_samples(areas: Iterable[Area], known_samples: Iterable[str]) -> List[str]:
    used = {sample for area in areas for case in area.cases for sample in case.samples}
    return sorted(set(known_samples) - used)
