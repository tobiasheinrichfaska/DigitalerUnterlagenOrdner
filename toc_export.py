"""
PDF-Export mit gedrucktem Inhaltsverzeichnis und optionaler Aufteilung.
- Gedruckter TOC als erste Seite(n) mit Seitenangaben
- Anklickbare Einträge im TOC (Link-Annotierungen)
- PDF-Lesezeichen (Sidebar-Navigation) im exportierten Dokument
- Aufteilung ab konfigurierbarer Seitenzahl mit gegenseitigen Querverweisen
"""
import io
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pikepdf
from pypdf import PdfWriter, PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import cm

from pdf_node import PDFNode
from pdf_storage import PDFStorage

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
    """Rendert alle Knoten als flaches PDF ohne Metadaten."""
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
                except Exception:
                    pass

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
            c.drawRightString(_A4_W - _MR, y, f"→ {item.other_file}")

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
# PDF-Assembly: Merge + Annotierungen + Lesezeichen
# ─────────────────────────────────────────────────────────────────────────────

def _assemble_pdf(toc_bytes: bytes, content_bytes: bytes,
                  link_records: List[_LinkRecord],
                  toc_items: List[_TocItem],
                  toc_page_count: int) -> bytes:
    """
    Merged TOC + Inhalt, fügt Link-Annotierungen und Sidebar-Lesezeichen ein.
    """
    # 1. Merge
    with pikepdf.Pdf.new() as pdf:
        with pikepdf.open(io.BytesIO(toc_bytes)) as toc_pdf:
            pdf.pages.extend(toc_pdf.pages)
        with pikepdf.open(io.BytesIO(content_bytes)) as content_pdf:
            pdf.pages.extend(content_pdf.pages)

        # 2. Link-Annotierungen auf TOC-Seiten
        for rec in link_records:
            if rec.toc_page_idx >= len(pdf.pages):
                continue
            dest_page_abs = toc_page_count + rec.content_page_0
            if dest_page_abs >= len(pdf.pages):
                continue

            toc_page = pdf.pages[rec.toc_page_idx]
            dest_page_obj = pdf.pages[dest_page_abs].obj

            rect = pikepdf.Array([
                pikepdf.Real(_ML - 2),
                pikepdf.Real(rec.y_baseline - 3),
                pikepdf.Real(_A4_W - _MR + 2),
                pikepdf.Real(rec.y_baseline + 11),
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

        # 3. Sidebar-Lesezeichen (Outline)
        def _first_leaf_page(start_idx: int, folder_depth: int) -> int:
            for it in toc_items[start_idx:]:
                if it.depth <= folder_depth:
                    break
                if not it.is_folder and not it.other_file:
                    return toc_page_count + it.page_start - 1
            return toc_page_count

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
                    dest = toc_page_count + item.page_start - 1
                    if 0 <= dest < len(pdf.pages):
                        oi = pikepdf.OutlineItem(item.name, dest)
                        parent.append(oi)

        out = io.BytesIO()
        pdf.save(out)
        return out.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Öffentliche Export-Funktionen
# ─────────────────────────────────────────────────────────────────────────────

def export_pdf_with_toc(nodes: List[PDFNode], path: str) -> None:
    """Exportiert als einzelne PDF-Datei mit TOC-Seite, Links und Lesezeichen."""
    top = PDFStorage.filter_keep_ancestors(nodes)
    items = _build_toc_items(top)

    # Erster Durchlauf: TOC-Seitenanzahl bestimmen
    draft_toc, _ = _render_toc_pdf(items, toc_offset=0)
    toc_page_count = _get_pdf_page_count(draft_toc)

    # Zweiter Durchlauf: korrekte Seitennummern
    final_toc, link_records = _render_toc_pdf(items, toc_offset=toc_page_count)
    content = _export_nodes_to_bytes(top)

    result = _assemble_pdf(final_toc, content, link_records, items, toc_page_count)
    with open(path, "wb") as f:
        f.write(result)


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


def export_pdf_split_with_toc(nodes: List[PDFNode], base_path: str,
                               max_pages: int) -> List[str]:
    """
    Aufteilen in mehrere Dateien. Jede Datei hat einen TOC mit Querverweisen
    auf die anderen Dateien. Gibt Liste der erstellten Pfade zurück.
    """
    top = PDFStorage.filter_keep_ancestors(nodes)
    groups = _split_at_boundaries(top, max_pages)

    if len(groups) == 1:
        export_pdf_with_toc(top, base_path)
        return [base_path]

    base_name = os.path.splitext(base_path)[0]
    ext = os.path.splitext(base_path)[1] or ".pdf"
    paths = [f"{base_name}_Teil_{i + 1}{ext}" for i in range(len(groups))]
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
                        page_start=0, page_end=0,
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
