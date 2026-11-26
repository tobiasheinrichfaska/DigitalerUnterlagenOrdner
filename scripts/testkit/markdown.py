# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Markdown subset → HTML for the tester documents (pure, no I/O).

Covers exactly what ``manual_tests/*.md`` and the installation guide use: headings,
paragraphs, **bold**, *italic*, `code`, links, ordered/unordered lists (nested),
blockquotes, pipe tables, fenced code and rules. Kept dependency-free on purpose —
the build venv ships no Markdown library and the sources are ours to keep simple.
"""

import html
import re

_CODE = re.compile(r"`([^`]+)`")
_STASHED = re.compile("\x00(\\d+)\x00")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
# A URL written out in the text; one already inside a link follows a quote or ">".
_BARE_URL = re.compile(r"""(?<!["=>])\bhttps?://[^\s<]*[^\s<.,;:!?)]""")
_LIST_ITEM = re.compile(r"^(\s*)(\d+\.|[-*])\s+(.*)$")
_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
_RULE = re.compile(r"^-{3,}\s*$")
_TABLE_RULE = re.compile(r":?-{2,}:?")


def inline(text: str) -> str:
    """Inline markup of one text run. Code spans are taken literally."""
    codes = []

    def stash(match):
        # Park code spans so emphasis may wrap them (**Datei `x.pdf`**) without touching them.
        codes.append(match.group(1))
        return f"\x00{len(codes) - 1}\x00"

    s = html.escape(_CODE.sub(stash, text), quote=False)
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    s = _ITALIC.sub(r"<em>\1</em>", s)
    s = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
    s = _BARE_URL.sub(lambda m: f'<a href="{m.group(0)}">{m.group(0)}</a>', s)
    return _STASHED.sub(lambda m: f"<code>{html.escape(codes[int(m.group(1))], quote=False)}</code>", s)


def _is_ordered(marker: str) -> bool:
    return marker[0].isdigit()


def _starts_block(line: str) -> bool:
    return bool(_HEADING.match(line) or _RULE.match(line) or _LIST_ITEM.match(line)
                or line.startswith(("```", ">")) or line.lstrip().startswith("|"))


def _take_list(lines, i):
    """Collect the raw lines of the list starting at ``i``; return (lines, next index)."""
    ordered = _is_ordered(_LIST_ITEM.match(lines[i]).group(2))
    buf = []
    while i < len(lines):
        line = lines[i]
        if line.strip():
            if not (_LIST_ITEM.match(line) or line[:1] in " \t"):
                break
            buf.append(line)
            i += 1
            continue
        # A blank line ends the list unless it visibly continues afterwards.
        j = i
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j == len(lines):
            break
        nxt = _LIST_ITEM.match(lines[j])
        same_list = nxt and not nxt.group(1) and _is_ordered(nxt.group(2)) == ordered
        if not (lines[j][:1] in " \t" or same_list):
            break
        i = j
    return buf, i


def _list(buf) -> str:
    base = len(_LIST_ITEM.match(buf[0]).group(1))
    groups = []  # [ordered, start, [(text lines, child lines)]]
    for line in buf:
        m = _LIST_ITEM.match(line)
        if m and len(m.group(1)) <= base:
            ordered = _is_ordered(m.group(2))
            if not groups or groups[-1][0] != ordered:
                groups.append([ordered, int(m.group(2)[:-1]) if ordered else 1, []])
            groups[-1][2].append(([m.group(3)], []))
            continue
        text, children = groups[-1][2][-1]
        if m or children:
            children.append(line)  # a nested item, or the continuation of one
        else:
            text.append(line.strip())
    out = []
    for ordered, start, items in groups:
        tag = "ol" if ordered else "ul"
        attr = f' start="{start}"' if ordered and start != 1 else ""
        body = "".join(
            f"<li>{inline(' '.join(text))}{_list(children) if children else ''}</li>"
            for text, children in items)
        out.append(f"<{tag}{attr}>{body}</{tag}>")
    return "".join(out)


def _table(buf) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in buf]
    head, body = rows[0], rows[1:]
    if body and all(_TABLE_RULE.fullmatch(cell) for cell in body[0]):
        body = body[1:]
    thead = "".join(f"<th>{inline(c)}</th>" for c in head)
    tbody = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>" for row in body)
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"


def to_html(markdown: str) -> str:
    """Render a Markdown-subset document to an HTML fragment."""
    lines = markdown.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            code = html.escape("\n".join(lines[i + 1:j]), quote=False)
            out.append(f"<pre><code>{code}</code></pre>")
            i = j + 1
        elif _HEADING.match(line):
            m = _HEADING.match(line)
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2).strip())}</h{level}>")
            i += 1
        elif _RULE.match(line):
            out.append("<hr>")
            i += 1
        elif line.startswith(">"):
            j = i
            while j < len(lines) and lines[j].startswith(">"):
                j += 1
            quoted = "\n".join(re.sub(r"^>\s?", "", q) for q in lines[i:j])
            out.append(f"<blockquote>{to_html(quoted)}</blockquote>")
            i = j
        elif line.lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            out.append(_table(lines[i:j]))
            i = j
        elif _LIST_ITEM.match(line):
            buf, i = _take_list(lines, i)
            out.append(_list(buf))
        else:
            j = i + 1
            while j < len(lines) and lines[j].strip() and not _starts_block(lines[j]):
                j += 1
            out.append(f"<p>{inline(' '.join(part.strip() for part in lines[i:j]))}</p>")
            i = j
    return "\n".join(out)
