# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""HTML pages for the tester documents — presentation only.

Takes the parsed model (cases.py) and already-built HTML fragments; knows nothing about
files, parsing or the browser. Printed to A4 by pdf.py.
"""

import html
import re

from . import cases
from .markdown import to_html

REPO_URL = "https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner"

# kind → (heading, CSS class). One row per section type in cases.SECTION_LABELS.
SECTION_STYLE = {
    "voraussetzungen": ("Voraussetzungen", "pre"),
    "schritte": ("Schritte", "steps"),
    "erwartet": ("Erwartetes Ergebnis", "expected"),
    "hinweis": ("Hinweis", "note"),
}

CSS = """
@page {
  size: A4;
  margin: 17mm 16mm 19mm 16mm;
  @bottom-left { content: "%(footer)s"; font: 8pt "Segoe UI", Arial, sans-serif; color: #6b7280; }
  @bottom-right { content: "Seite " counter(page) " von " counter(pages);
                  font: 8pt "Segoe UI", Arial, sans-serif; color: #6b7280; }
}
html { font-size: 10.5pt; }
body { margin: 0; color: #1c2333; line-height: 1.45;
       font-family: "Segoe UI", "Segoe UI Emoji", "Segoe UI Symbol", Arial, sans-serif;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
p { margin: 0 0 5pt; }
a { color: #24407a; }
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 9.5pt;
       background: #eef1f5; padding: 0 3pt; border-radius: 2pt; }
pre { background: #eef1f5; padding: 6pt 9pt; border-radius: 3pt; white-space: pre-wrap; }
pre code { background: none; padding: 0; }
ul, ol { margin: 0 0 5pt; padding-left: 17pt; }
li { margin: 3pt 0; break-inside: avoid; }
li > ul, li > ol { margin-top: 2pt; }
table { border-collapse: collapse; width: 100%%; font-size: 9.5pt; margin: 4pt 0 7pt; }
th, td { border: .5pt solid #cbd2dc; padding: 3pt 6pt; text-align: left; vertical-align: top; }
th { background: #eef1f5; }
tr { break-inside: avoid; }
blockquote { margin: 6pt 0; padding: 6pt 10pt 2pt; border-left: 3pt solid #b7791f; background: #fdf6e3; }
hr { border: 0; border-top: .5pt solid #cbd2dc; margin: 10pt 0; }

.head { display: flex; justify-content: space-between; align-items: baseline;
        border-bottom: 2pt solid #24407a; padding-bottom: 4pt; font-size: 9pt; color: #24407a; }
.head .brand { font-weight: 700; text-transform: uppercase; letter-spacing: .05em; }
h1 { font-size: 19pt; line-height: 1.2; margin: 12pt 0 5pt; }
h1 .id { display: inline-block; background: #24407a; color: #fff; border-radius: 4pt; padding: 1pt 7pt;
         font-size: 12pt; vertical-align: 2pt; margin-right: 6pt; white-space: nowrap; }
.meta { font-size: 9pt; color: #4b5563; margin-bottom: 9pt; }
.meta span + span::before { content: "  ·  "; }
.meta .since { color: #9a3412; font-weight: 600; }

section { margin: 9pt 0; }
section > h2 { font-size: 9pt; text-transform: uppercase; letter-spacing: .07em; margin: 0 0 3pt;
               break-after: avoid; }
.block { border-left: 3pt solid; padding: 6pt 10pt 2pt; border-radius: 0 4pt 4pt 0; }
.pre h2, .samples h2 { color: #475569; }
.pre .block, .samples .block { border-color: #64748b; background: #f3f5f8; }
.area { font-size: 9pt; color: #4b5563; margin: 0 0 8pt; }
.area blockquote { color: #1c2333; }
.steps h2 { color: #24407a; }
.steps .block { border-color: #24407a; }
.steps ol > li::marker { font-weight: 700; color: #24407a; }
.expected h2 { color: #1e7a46; }
.expected .block { border-color: #1e7a46; background: #eef7f1; }
.note h2 { color: #92600c; }
.note .block { border-color: #b7791f; background: #fdf6e3; }
.samples td:first-child { white-space: nowrap; font-family: Consolas, monospace; font-size: 9pt; }

.protocol { break-inside: avoid; border: .75pt solid #9aa4b2; border-radius: 4pt; padding: 6pt 10pt 8pt;
            margin-top: 12pt; }
.protocol h2 { color: #1c2333; }
.protocol .choices span { margin-right: 16pt; }
.protocol .box { display: inline-block; width: 9pt; height: 9pt; border: .75pt solid #1c2333;
                 margin-right: 4pt; vertical-align: -1pt; }
.protocol .fields { display: flex; gap: 14pt; margin-top: 4pt; }
.protocol .field { flex: 1; border-top: .5pt solid #6b7280; margin-top: 14pt; padding-top: 1pt;
                   font-size: 8pt; color: #6b7280; }
.protocol .lines div { border-bottom: .5pt solid #b6bdc8; height: 17pt; }
.feedback { font-size: 8.5pt; color: #4b5563; margin-top: 8pt; }

.doc h1 { margin-bottom: 8pt; }
.doc h2 { font-size: 13.5pt; color: #24407a; margin: 14pt 0 5pt; break-after: avoid; }
.doc h3 { font-size: 11pt; margin: 10pt 0 4pt; break-after: avoid; }
.index { table-layout: fixed; }
.index th:nth-child(1) { width: 14%%; }
.index th:nth-child(2) { width: 37%%; }
.index th:nth-child(3) { width: 9%%; }
.index td:first-child { white-space: nowrap; }
.index td:last-child { font-size: 8.5pt; overflow-wrap: anywhere; }
"""

_PAGE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body{body_class}>
<div class="head"><span class="brand">{brand}</span><span>{context}</span></div>
{body}
</body>
</html>
"""

_LOCAL_LINK = re.compile(r'<a href="(?!https?:|mailto:)[^"]*">(.*?)</a>')

_PROTOCOL = """<section class="protocol">
<h2>Testprotokoll</h2>
<p class="choices"><span><i class="box"></i>Bestanden</span><span><i class="box"></i>Fehlgeschlagen</span>
<span><i class="box"></i>Nicht durchführbar</span></p>
<div class="fields"><div class="field">Getestete Version</div><div class="field">Datum</div>
<div class="field">Tester/in</div></div>
<p style="margin:5pt 0 0;font-size:8pt;color:#6b7280">Beobachtungen / Abweichungen</p>
<div class="lines"><div></div><div></div></div>
</section>"""


def _page(title: str, brand: str, context: str, body: str, footer: str, doc: bool = False) -> str:
    css = CSS % {"footer": footer.replace("\\", "\\\\").replace('"', '\\"')}
    return _PAGE.format(title=html.escape(title), css=css, brand=html.escape(brand),
                        context=html.escape(context), body=body, body_class=' class="doc"' if doc else "")


def _body_html(markdown: str) -> str:
    """Markdown → HTML; links that only work inside the repository become plain text."""
    return _LOCAL_LINK.sub(r"\1", to_html(markdown))


def _section(title: str, css_class: str, inner: str) -> str:
    return f'<section class="{css_class}"><h2>{html.escape(title)}</h2><div class="block">{inner}</div></section>'


def _samples_table(names, catalog) -> str:
    rows = "".join(f"<tr><td>{html.escape(name)}</td><td>{html.escape(catalog[name].description)}</td></tr>"
                   for name in names)
    return ("<p>Liegen im Ordner <code>Beispieldateien</code> neben dieser Anleitung.</p>"
            f"<table><thead><tr><th>Datei</th><th>Inhalt</th></tr></thead><tbody>{rows}</tbody></table>")


def case_page(area: cases.Area, case: cases.Case, catalog, version: str) -> str:
    """One printable page set for a single test case."""
    area_label = f"Bereich {area.number} · {area.title}"
    meta = [f"<span>Beschreibt BelegTool {html.escape(version)}</span>"]
    if case.since:
        meta.append(f'<span class="since">erst ab Version {html.escape(case.since)} testbar</span>')
    parts = [
        f'<h1><span class="id">{html.escape(case.id)}</span>{html.escape(case.title)}</h1>',
        f'<div class="meta">{"".join(meta)}</div>',
    ]
    if case.intro:
        parts.append(_body_html(case.intro))
    if area.intro:
        parts.append(f'<div class="area">{_body_html(area.intro)}</div>')
    if case.samples:
        parts.append(_section("Beispieldateien", "samples", _samples_table(case.samples, catalog)))
    for section in case.sections:
        title, css_class = SECTION_STYLE[section.kind]
        if section.qualifier:
            title = f"{title}: {section.qualifier}"
        parts.append(_section(title, css_class, _body_html(section.body)))
    parts.append(_PROTOCOL)
    parts.append(f'<p class="feedback">Abweichung gefunden? Bitte mit Bereich und Test-ID '
                 f'(<strong>{html.escape(area.number)} · {html.escape(case.id)}</strong>), der getesteten Version '
                 f'und Ihrer Beobachtung melden: <a href="{REPO_URL}/issues">{REPO_URL}/issues</a></p>')
    footer = f"BelegTool {version} · {area.source} · {case.id}"
    return _page(f"{case.id} – {case.title}", "BelegTool · Manueller Test", area_label, "\n".join(parts), footer)


def index_html(areas, catalog) -> str:
    """Table of every test case, appended to the overview document."""
    rows = []
    for area in areas:
        rows.append(f'<tr><th colspan="4">Bereich {html.escape(area.number)} · {html.escape(area.title)} '
                    f'— Ordner <code>{html.escape(area.folder_name)}</code></th></tr>')
        for case in area.cases:
            files = "<br>".join(html.escape(name) for name in case.samples) or "–"
            rows.append(f"<tr><td>{html.escape(case.id)}</td><td>{html.escape(case.title)}</td>"
                        f"<td>{html.escape(case.since or '')}</td><td>{files}</td></tr>")
    total = sum(len(area.cases) for area in areas)
    return (f"<h2>Alle {total} Tests im Überblick</h2>"
            '<table class="index"><thead><tr><th>ID</th><th>Test</th><th>ab Version</th><th>Beispieldateien</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table>")


def document_page(title: str, markdown: str, version: str, context: str, extra_html: str = "") -> str:
    """A free-form document (installation guide, kit overview)."""
    body = _body_html(markdown) + extra_html
    return _page(title, "BelegTool", context, body, f"BelegTool {version} · {title}", doc=True)
