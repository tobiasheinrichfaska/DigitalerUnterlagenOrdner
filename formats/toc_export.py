"""
PDF-Export mit gedrucktem Inhaltsverzeichnis und optionaler Aufteilung.
- Gedruckter TOC als erste Seite(n) mit Seitenangaben
- Anklickbare Einträge im TOC (Link-Annotierungen)
- PDF-Lesezeichen (Sidebar-Navigation) im exportierten Dokument
- Aufteilung ab konfigurierbarer Seitenzahl mit gegenseitigen Querverweisen
"""
import io
import os
from infra.log_config import logger
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pikepdf
from pypdf import PdfWriter, PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import cm

from formats.pdf_node import PDFNode
from formats.pdf_storage import PDFStorage

# Seitenabmessungen A4 in Punkten
_A4_W, _A4_H = A4
_ML = 2.2 * cm
_MR = 2.2 * cm
_MT = 2.8 * cm
_MB = 2.2 * cm
_ROW = 14.0  # Zeilenhöhe in Punkten
_INDENT = 10.0  # Einrückung pro Tiefenstufe


@dataclass
class _TocItem:
    depth: int
    name: str
    page_start: int      # 1-basiert im Inhalt (ohne TOC-Seiten)
    page_end: int
    is_folder: bool
    other_file: str = None  # gesetzt wenn in anderer Split-Datei


@dataclass
class _LinkRecord:
    toc_page_idx: int    # 0-basiert in der TOC-PDF
    y_baseline: float    # y-Koordinate des Textes (PDF-Einheiten, von unten)
    content_page_0: int  # 0-basierter Index im Inhalts-PDF (vor Merge)


# ─────────────────────────────────────────────────────────────────────────────
# Interne Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────

def count_node_pages(node: PDFNode) -> int:
    if node.is_folder:
        return sum(count_node_pages(c) for c in node.children)
    return node.pdf_length or 0


def count_total_pages(nodes: List[PDFNode]) -> int:
    return sum(count_node_pages(n) for n in nodes)


def empty_leaf_names(nodes: List[PDFNode]) -> List[str]:
    """Names of leaf nodes with no pages — these are silently dropped from the
    export/TOC, so callers can warn the user about what was left out."""
    names: List[str] = []

    def _walk(node: PDFNode) -> None:
        if node.is_folder:
            for child in node.children:
                _walk(child)
        elif count_node_pages(node) == 0:
            names.append(node.name)

    for n in nodes:
        _walk(n)
    return names


def _build_toc_items(nodes: List[PDFNode], depth: int = 0,
                     counter: Optional[List[int]] = None) -> List[_TocItem]:
    if counter is None:
        counter = [1]
    items: List[_TocItem] = []
    for node in nodes:
        if node.is_folder:
            items.append(_TocItem(depth, node.name, counter[0], counter[0], True))
            items.extend(_build_toc_items(node.children, depth + 1, counter))
        else:
            n = count_node_pages(node)
            if n == 0:
                continue
            items.append(_TocItem(depth, node.name, counter[0], counter[0] + n - 1, False))
            counter[0] += n
    return items


def _get_pdf_page_count(data: bytes) -> int:
    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return 1


def _export_nodes_to_bytes(nodes: List[PDFNode]) -> bytes:
    """Rendert alle Knoten als flaches PDF ohne Metadaten.

    Limitation (audit finding 7): pages are copied via ``PdfWriter.add_page``,
    which drops source named destinations, link annotations and outlines. Fine
    for image-only receipts; lossy for structured text PDFs.
    """
    writer = PdfWriter()

    def _append(node: PDFNode):
        if node.is_folder:
            for child in node.children:
                _append(child)
        else:
            data = node.current_pdf_data
            if data:
                try:
                    for page in PdfReader(io.BytesIO(data)).pages:
                        writer.add_page(page)
                except Exception as e:
                    logger.warning("Export: Seiten von '%s' konnten nicht angehängt werden: %s",
                                   node.name, e)

    for n in nodes:
        _append(n)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# TOC-Seiten rendern (mit Positions-Tracking für Links)
# ─────────────────────────────────────────────────────────────────────────────

def _render_toc_pdf(items: List[_TocItem],
                    toc_offset: int = 0,
                    title: str = "Inhaltsverzeichnis",
                    subtitle: str = "") -> Tuple[bytes, List[_LinkRecord]]:
    """
    Erzeugt die TOC-Seiten.
    Gibt (PDF-Bytes, Liste von LinkRecords) zurück.
    toc_offset: Anzahl der TOC-Seiten selbst (wird zu Seitennummern addiert).
    """
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    link_records: List[_LinkRecord] = []
    current_toc_page = 0

    y = _A4_H - _MT

    # ── Titel ────────────────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 15)
    c.drawString(_ML, y, title)
    y -= 22
    if subtitle:
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(_ML, y, subtitle)
        c.setFillColorRGB(0, 0, 0)
        y -= 14
    c.setLineWidth(0.6)
    c.line(_ML, y, _A4_W - _MR, y)
    y -= 14

    in_this_shown = False
    in_other_shown = False

    for item in items:
        if y < _MB + 15:
            c.showPage()
            current_toc_page += 1
            y = _A4_H - _MT

        x = _ML + item.depth * _INDENT
        name = item.name if len(item.name) <= 74 else item.name[:72] + "…"

        if item.other_file:
            # ── Querverweis auf andere Datei ─────────────────────────────────
            if not in_other_shown and in_this_shown:
                y -= 4
                c.setFont("Helvetica-BoldOblique", 8)
                c.setFillColorRGB(0.45, 0.45, 0.45)
                c.drawString(_ML, y, "In anderen Dateien:")
                c.setFillColorRGB(0, 0, 0)
                y -= _ROW
                in_other_shown = True
            c.setFont("Helvetica-Oblique", 9)
            c.setFillColorRGB(0.55, 0.55, 0.55)
            c.drawString(x, y, name)
            # every part's TOC lists the SAME full item set, so all parts share one
            # TOC page count → the entry's page in the other file is page_start+toc_offset.
            ref = item.other_file if item.is_folder else f"{item.other_file}, S. {item.page_start + toc_offset}"
            c.drawRightString(_A4_W - _MR, y, f"→ {ref}")

        elif item.is_folder:
            # ── Ordner-Überschrift ────────────────────────────────────────────
            if not in_this_shown and subtitle:
                c.setFont("Helvetica-BoldOblique", 8)
                c.setFillColorRGB(0.45, 0.45, 0.45)
                c.drawString(_ML, y, "In dieser Datei:")
                c.setFillColorRGB(0, 0, 0)
                y -= _ROW
                in_this_shown = True
            c.setFont("Helvetica-Bold", 10)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(x, y, name)

        else:
            # ── Dokumenteintrag mit Seitennummer und Link ─────────────────────
            if not in_this_shown and subtitle:
                c.setFont("Helvetica-BoldOblique", 8)
                c.setFillColorRGB(0.45, 0.45, 0.45)
                c.drawString(_ML, y, "In dieser Datei:")
                c.setFillColorRGB(0, 0, 0)
                y -= _ROW
                in_this_shown = True
            c.setFont("Helvetica", 10)
            c.setFillColorRGB(0, 0, 0)
            page_text = f"S. {item.page_start + toc_offset}"
            nw = c.stringWidth(name, "Helvetica", 10)
            pw = c.stringWidth(page_text, "Helvetica", 10)

            c.drawString(x, y, name)

            # Punktlinie
            dx1 = x + nw + 5
            dx2 = _A4_W - _MR - pw - 6
            if dx2 > dx1 + 8:
                c.setDash([1, 3], 0)
                c.setLineWidth(0.4)
                c.setStrokeColorRGB(0.65, 0.65, 0.65)
                c.line(dx1, y + 2.5, dx2, y + 2.5)
                c.setDash([], 0)
                c.setStrokeColorRGB(0, 0, 0)

            c.drawRightString(_A4_W - _MR, y, page_text)

            # Link-Daten für spätere Annotierung (0-basiert im Inhaltsteil)
            link_records.append(_LinkRecord(
                toc_page_idx=current_toc_page,
                y_baseline=y,
                content_page_0=item.page_start - 1,
            ))

        c.setFillColorRGB(0, 0, 0)
        y -= _ROW

    c.save()
    return buf.getvalue(), link_records


# ─────────────────────────────────────────────────────────────────────────────
# Stichwortverzeichnis (Tag-Index) — Tags → Dokumente mit Seitenangabe
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _IndexEntry:
    is_header: bool      # True = Tag-Überschrift; False = Dokumenteintrag
    text: str            # Tag-Name (Header) oder Dokumentname (Eintrag)
    page: int = 0        # 1-basierte Inhaltsseite (nur Einträge)


def _index_leaves(nodes: List[PDFNode]):
    """Leaves in Inhaltsreihenfolge als (name, page_start, effective_tags), wobei die
    effektiven Tags = eigene ∪ alle Tags der Eltern-/Vorfahren-Ordner sind (wie die
    Tag-Ansicht). Leere Blätter werden übersprungen (wie im TOC)."""
    counter = [1]
    out = []

    def walk(node: PDFNode, inherited: set):
        eff = inherited | set(getattr(node, "tags", None) or [])
        if node.is_folder:
            for c in node.children:
                walk(c, eff)
        else:
            n = count_node_pages(node)
            if n == 0:
                return
            out.append((node.name, counter[0], eff))
            counter[0] += n

    for n in nodes:
        walk(n, set())
    return out


def _build_index_items(nodes: List[PDFNode]) -> List[_IndexEntry]:
    """Flache Liste für das Stichwortverzeichnis: pro Tag eine Überschrift, darunter die
    zugehörigen Dokumente (in Inhaltsreihenfolge). Tags alphabetisch (case-insensitiv).
    Leer, wenn keine Tags vergeben sind."""
    tag_map: dict = {}
    for name, page, tags in _index_leaves(nodes):
        for tag in tags:
            tag_map.setdefault(tag, []).append((name, page))
    items: List[_IndexEntry] = []
    for tag in sorted(tag_map, key=lambda s: s.lower()):
        items.append(_IndexEntry(True, tag))
        for name, page in tag_map[tag]:
            items.append(_IndexEntry(False, name, page))
    return items


def _render_index_pdf(items: List[_IndexEntry], toc_offset: int,
                      title: str = "Stichwortverzeichnis") -> Tuple[bytes, List[_LinkRecord]]:
    """Rendert die Index-Seiten (Tags fett, Dokumente mit Seitenzahl + Punktlinie).
    Gibt (PDF-Bytes, LinkRecords relativ zum Index-Abschnitt) zurück."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    link_records: List[_LinkRecord] = []
    current_page = 0
    y = _A4_H - _MT

    c.setFont("Helvetica-Bold", 15)
    c.drawString(_ML, y, title)
    y -= 22
    c.setLineWidth(0.6)
    c.line(_ML, y, _A4_W - _MR, y)
    y -= 14

    for item in items:
        if y < _MB + 15:
            c.showPage()
            current_page += 1
            y = _A4_H - _MT

        if item.is_header:
            y -= 4
            c.setFont("Helvetica-Bold", 11)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(_ML, y, item.text)
            y -= _ROW
            continue

        name = item.text if len(item.text) <= 74 else item.text[:72] + "…"
        c.setFont("Helvetica", 10)
        page_text = f"S. {item.page + toc_offset}"
        nw = c.stringWidth(name, "Helvetica", 10)
        pw = c.stringWidth(page_text, "Helvetica", 10)
        x = _ML + _INDENT
        c.drawString(x, y, name)
        dx1 = x + nw + 5
        dx2 = _A4_W - _MR - pw - 6
        if dx2 > dx1 + 8:
            c.setDash([1, 3], 0)
            c.setLineWidth(0.4)
            c.setStrokeColorRGB(0.65, 0.65, 0.65)
            c.line(dx1, y + 2.5, dx2, y + 2.5)
            c.setDash([], 0)
            c.setStrokeColorRGB(0, 0, 0)
        c.drawRightString(_A4_W - _MR, y, page_text)
        link_records.append(_LinkRecord(
            toc_page_idx=current_page, y_baseline=y, content_page_0=item.page - 1))
        y -= _ROW

    c.save()
    return buf.getvalue(), link_records


# ─────────────────────────────────────────────────────────────────────────────
# PDF-Assembly: Merge + Annotierungen + Lesezeichen
# ─────────────────────────────────────────────────────────────────────────────

def _assemble_pdf(toc_bytes: bytes, content_bytes: bytes,
                  link_records: List[_LinkRecord],
                  toc_items: List[_TocItem],
                  toc_page_count: int) -> bytes:
    """Back-compat single-TOC assembly (used by the split path)."""
    return _assemble([toc_bytes], content_bytes, link_records, toc_items,
                     toc_page_count, with_bookmarks=True)


def _assemble(prepend_pdfs: List[bytes], content_bytes: bytes,
              link_records: List[_LinkRecord],
              toc_items: List[_TocItem],
              prepend_count: int, with_bookmarks: bool = True) -> bytes:
    """
    Merged Vorspann-Seiten (TOC und/oder Index) + Inhalt, fügt Link-Annotierungen
    (für alle ``link_records``, deren ``toc_page_idx`` absolut im Vorspann ist) und
    optional Sidebar-Lesezeichen ein. ``prepend_count`` = Gesamtzahl der Vorspann-Seiten.
    """
    # 1. Merge
    with pikepdf.Pdf.new() as pdf:
        for b in prepend_pdfs:
            with pikepdf.open(io.BytesIO(b)) as p:
                pdf.pages.extend(p.pages)
        with pikepdf.open(io.BytesIO(content_bytes)) as content_pdf:
            pdf.pages.extend(content_pdf.pages)

        # 2. Link-Annotierungen auf Vorspann-Seiten (TOC + Index)
        for rec in link_records:
            if rec.toc_page_idx >= len(pdf.pages):
                continue
            dest_page_abs = prepend_count + rec.content_page_0
            if dest_page_abs >= len(pdf.pages):
                continue

            toc_page = pdf.pages[rec.toc_page_idx]
            dest_page_obj = pdf.pages[dest_page_abs].obj

            # pikepdf >= 8 dropped pikepdf.Real — plain Python floats are coerced.
            rect = pikepdf.Array([
                float(_ML - 2),
                float(rec.y_baseline - 3),
                float(_A4_W - _MR + 2),
                float(rec.y_baseline + 11),
            ])

            annot = pdf.make_indirect(pikepdf.Dictionary(
                Type=pikepdf.Name("/Annot"),
                Subtype=pikepdf.Name("/Link"),
                Rect=rect,
                Border=pikepdf.Array([0, 0, 0]),
                Dest=pikepdf.Array([dest_page_obj, pikepdf.Name("/Fit")]),
            ))

            if "/Annots" in toc_page:
                toc_page["/Annots"].append(annot)
            else:
                toc_page["/Annots"] = pikepdf.Array([annot])

        # 3. Sidebar-Lesezeichen (Outline) — optional
        def _first_leaf_page(start_idx: int, folder_depth: int) -> int:
            for it in toc_items[start_idx:]:
                if it.depth <= folder_depth:
                    break
                if not it.is_folder and not it.other_file:
                    return prepend_count + it.page_start - 1
            return prepend_count

        if with_bookmarks and toc_items:
            with pdf.open_outline() as outline:
                outline.root.clear()
                depth_parents: dict = {-1: outline.root}

                for idx, item in enumerate(toc_items):
                    if item.other_file:
                        continue
                    parent = depth_parents.get(item.depth - 1, outline.root)

                    if item.is_folder:
                        dest = _first_leaf_page(idx + 1, item.depth)
                        dest = min(dest, len(pdf.pages) - 1)
                        oi = pikepdf.OutlineItem(item.name, dest)
                        parent.append(oi)
                        depth_parents[item.depth] = oi.children
                    else:
                        dest = prepend_count + item.page_start - 1
                        if 0 <= dest < len(pdf.pages):
                            oi = pikepdf.OutlineItem(item.name, dest)
                            parent.append(oi)

        out = io.BytesIO()
        pdf.save(out)
        return out.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Öffentliche Export-Funktionen
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_EXPORT_OPTIONS = {
    "toc": True,          # printed table of contents
    "toc_links": True,    # clickable TOC entries
    "index": True,        # printed tag index (only if tags exist)
    "index_links": True,  # clickable index entries
    "bookmarks": True,    # PDF sidebar bookmarks (outline)
}


def export_pdf(nodes: List[PDFNode], path: str, options: Optional[dict] = None) -> None:
    """Single-file export. ``options`` (see DEFAULT_EXPORT_OPTIONS) toggles the printed
    TOC (+links), the tag index (+links, only when tags exist) and the PDF bookmarks.
    Front matter is [TOC][index] before the content; page numbers and links account for it."""
    opts = {**DEFAULT_EXPORT_OPTIONS, **(options or {})}
    top = PDFStorage.filter_keep_ancestors(nodes)
    toc_items = _build_toc_items(top)
    index_items = _build_index_items(top) if opts["index"] else []
    want_toc = bool(opts["toc"])
    want_index = bool(index_items)  # only if tags actually produced entries

    # Pass 1: count front-matter pages (render drafts at offset 0).
    prepend_count = 0
    if want_toc:
        prepend_count += _get_pdf_page_count(_render_toc_pdf(toc_items, toc_offset=0)[0])
    if want_index:
        prepend_count += _get_pdf_page_count(_render_index_pdf(index_items, toc_offset=0)[0])

    # Pass 2: render final front matter with correct page numbers; collect link records
    # with absolute page indices within the front matter.
    prepend_pdfs: List[bytes] = []
    link_records: List[_LinkRecord] = []
    page_cursor = 0
    if want_toc:
        toc_bytes, recs = _render_toc_pdf(toc_items, toc_offset=prepend_count)
        prepend_pdfs.append(toc_bytes)
        if opts["toc_links"]:
            for r in recs:
                r.toc_page_idx += page_cursor
                link_records.append(r)
        page_cursor += _get_pdf_page_count(toc_bytes)
    if want_index:
        idx_bytes, recs = _render_index_pdf(index_items, toc_offset=prepend_count)
        prepend_pdfs.append(idx_bytes)
        if opts["index_links"]:
            for r in recs:
                r.toc_page_idx += page_cursor
                link_records.append(r)
        page_cursor += _get_pdf_page_count(idx_bytes)

    content = _export_nodes_to_bytes(top)
    result = _assemble(prepend_pdfs, content, link_records, toc_items,
                       prepend_count, with_bookmarks=bool(opts["bookmarks"]))
    with open(path, "wb") as f:
        f.write(result)


def export_pdf_with_toc(nodes: List[PDFNode], path: str) -> None:
    """Back-compat: full export (TOC + index + links + bookmarks)."""
    export_pdf(nodes, path)


def _split_at_boundaries(nodes: List[PDFNode], max_pages: int) -> List[List[PDFNode]]:
    """
    Teilt auf Knotengrenzen auf — nie mitten in einem Knoten oder Ordner.
    Ein Knoten, der allein > max_pages ist, bekommt eine eigene Datei.
    """
    groups: List[List[PDFNode]] = []
    current: List[PDFNode] = []
    current_count = 0

    for node in nodes:
        n = count_node_pages(node)
        if current and current_count + n > max_pages:
            groups.append(current)
            current = []
            current_count = 0
        current.append(node)
        current_count += n

    if current:
        groups.append(current)
    return groups


def _pack_units(units, max_pages):
    """Greedy: pack ``(ref, pages)`` units into ordered groups whose page sums stay
    ``<= max_pages``; a single oversized unit gets its own group. Returns the refs
    grouped: ``List[List[ref]]``. Shared by every break level (#13)."""
    groups, cur, cur_n = [], [], 0
    for ref, n in units:
        if cur and cur_n + n > max_pages:
            groups.append(cur)
            cur, cur_n = [], 0
        cur.append(ref)
        cur_n += n
    if cur:
        groups.append(cur)
    return groups


def _leaves_with_path(nodes, _path=()):
    """All non-empty leaves in document order, each paired with its folder-name path
    (so a split part can be rebuilt with the document's folder structure)."""
    out = []
    for node in nodes:
        if node.is_folder:
            out.extend(_leaves_with_path(node.children, _path + (node.name,)))
        elif count_node_pages(node) > 0:
            out.append((node, _path))
    return out


def _subtree_from_leaves(items):
    """Rebuild a pruned forest of folders holding the given ``(leaf, folder_path)``
    items — preserving order and merging shared folders — so a split part keeps the
    document's structure. Folder nodes are fresh; leaf nodes are reused as-is."""
    roots = []
    index = {}  # path tuple -> folder PDFNode

    def ensure(path):
        if not path:
            return None
        if path in index:
            return index[path]
        parent = ensure(path[:-1])
        folder = PDFNode(name=path[-1], is_folder=True)
        index[path] = folder
        if parent is None:
            roots.append(folder)
        else:
            parent.add_child(folder)
        return folder

    for leaf, path in items:
        parent = ensure(path)
        if parent is None:
            roots.append(leaf)
        else:
            parent.add_child(leaf)
    return roots


def _slice_leaf(leaf, indices):
    """A new leaf holding only ``indices`` (0-based) of ``leaf``'s pages — for the
    page-level split, where a document is cut across files. The name carries the
    original page range so each part stays identifiable."""
    writer = PdfWriter()
    try:
        reader = PdfReader(io.BytesIO(leaf.current_pdf_data or b""))
        for i in indices:
            writer.add_page(reader.pages[i])
    except Exception as e:  # keep the export going; a broken slice becomes empty
        logger.warning("Seiten-Split von '%s' fehlgeschlagen: %s", leaf.name, e)
    buf = io.BytesIO()
    writer.write(buf)
    part = PDFNode(name=f"{leaf.name} (S. {indices[0] + 1}–{indices[-1] + 1})",
                   pdf_data=buf.getvalue())
    part.pdf_length = len(indices)
    part.tags = list(getattr(leaf, "tags", []) or [])
    return part


def _subtree_from_pages(group):
    """Rebuild a part's forest from page units, coalescing consecutive same-leaf
    pages into one (possibly partial) leaf and keeping folder paths. A run that
    covers all of a leaf's pages reuses the leaf untouched; a partial run is sliced."""
    runs = []  # [leaf, path, [indices]]
    for leaf, path, pi in group:
        if runs and runs[-1][0] is leaf and runs[-1][2][-1] == pi - 1:
            runs[-1][2].append(pi)
        else:
            runs.append([leaf, path, [pi]])
    items = []
    for leaf, path, indices in runs:
        part = leaf if len(indices) == count_node_pages(leaf) else _slice_leaf(leaf, indices)
        items.append((part, path))
    return _subtree_from_leaves(items)


def _plan_groups(nodes, max_pages, level):
    """Split the export forest into ordered parts of ``<= max_pages`` pages (#13).

    ``level``:
      ``'top'``    — units are the top-level nodes; a top folder is never split.
      ``'folder'`` — units are leaves; a folder may be split across parts at child
                     boundaries, but a leaf is never split.
      ``'page'``   — units are pages; a leaf may be split across parts (mid-document).

    Returns ``List[List[PDFNode]]`` — a pruned forest per part, ready for
    ``_build_toc_items`` / ``_export_nodes_to_bytes``."""
    if level == 'top':
        return _split_at_boundaries(nodes, max_pages)
    if level == 'folder':
        leaves = _leaves_with_path(nodes)
        units = [((leaf, path), count_node_pages(leaf)) for leaf, path in leaves]
        return [_subtree_from_leaves(grp) for grp in _pack_units(units, max_pages)]
    if level == 'page':
        units = []
        for leaf, path in _leaves_with_path(nodes):
            for pi in range(count_node_pages(leaf)):
                units.append(((leaf, path, pi), 1))
        return [_subtree_from_pages(grp) for grp in _pack_units(units, max_pages)]
    raise ValueError(f"unknown split level: {level!r}")


def _part_paths(base_path, n):
    """Output paths for an ``n``-part split — the base for a single part, else
    ``<base>_Teil_<i>.<ext>``. Single source of truth for the part naming."""
    if n <= 1:
        return [base_path]
    base_name = os.path.splitext(base_path)[0]
    ext = os.path.splitext(base_path)[1] or ".pdf"
    return [f"{base_name}_Teil_{i + 1}{ext}" for i in range(n)]


def plan_split_paths(nodes: List[PDFNode], base_path: str, max_pages: int,
                     level: str = 'top') -> List[str]:
    """The file paths an export split WOULD write — without writing anything. Lets the
    caller check for overwrites and confirm before clobbering existing files (#13)."""
    top = PDFStorage.filter_keep_ancestors(nodes)
    return _part_paths(base_path, len(_plan_groups(top, max_pages, level)))


def export_pdf_split_with_toc(nodes: List[PDFNode], base_path: str,
                               max_pages: int, level: str = 'top') -> List[str]:
    """
    Aufteilen in mehrere Dateien. Jede Datei hat einen TOC mit Querverweisen
    auf die anderen Dateien. Gibt Liste der erstellten Pfade zurück.
    ``level`` ('top'/'folder'/'page') wählt die Bruchgrenze — siehe ``_plan_groups``.
    """
    top = PDFStorage.filter_keep_ancestors(nodes)
    groups = _plan_groups(top, max_pages, level)

    if not groups:
        return []  # nothing to export (empty forest) — write no file, report no paths

    if len(groups) == 1:
        export_pdf_with_toc(top, base_path)
        return [base_path]

    paths = _part_paths(base_path, len(groups))
    file_names = [os.path.basename(p) for p in paths]

    group_items = [_build_toc_items(g) for g in groups]

    for idx, (group, items, path) in enumerate(zip(groups, group_items, paths)):
        subtitle = f"Teil {idx + 1} von {len(groups)}"

        # Einträge für diese Datei + graue Querverweise auf andere
        full_items: List[_TocItem] = []
        for other_idx, (other_items, other_name) in enumerate(zip(group_items, file_names)):
            if other_idx == idx:
                full_items.extend(other_items)
            else:
                for it in other_items:
                    full_items.append(_TocItem(
                        depth=it.depth, name=it.name,
                        page_start=it.page_start, page_end=it.page_end,  # keep the page for the cross-ref
                        is_folder=it.is_folder, other_file=other_name,
                    ))

        draft, _ = _render_toc_pdf(full_items, toc_offset=0, subtitle=subtitle)
        toc_page_count = _get_pdf_page_count(draft)
        final_toc, link_records = _render_toc_pdf(
            full_items, toc_offset=toc_page_count, subtitle=subtitle)
        content = _export_nodes_to_bytes(group)

        result = _assemble_pdf(final_toc, content, link_records, full_items, toc_page_count)
        with open(path, "wb") as f:
            f.write(result)

    return paths
