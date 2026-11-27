# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
import io
import json
import datetime
from typing import Optional, List, Union
from pypdf import PdfReader, PdfWriter
from formats.pdf_node import PDFNode
import os
# NOTE: universal_importer is imported lazily inside the archive/e-mail branches
# below — it pulls in win32com/COM, pi-heif, the .msg reader (~2.6 s) which a plain
# .belegtool/PDF load does not need. Keeping it out of module import makes loading
# (and the headless core's startup) fast.
from pikepdf import open as pike_open
import pikepdf
from infra.tools import sanitize_pdf
from infra.log_config import logger

# Reject pathologically deep .belegtool trees at parse time: to_dict/export/prune
# re-walk the tree recursively outside the load guard, so a hostile file could blow
# Python's recursion limit downstream. A real tree is a handful of levels deep.
_MAX_TREE_DEPTH = 200


class StructureTooDeep(ValueError):
    """The serialized .belegtool tree nests deeper than _MAX_TREE_DEPTH."""

def create_wrapper_node(storage: 'PDFStorage', filename: str) -> PDFNode:
    """
    Erzeugt bei Bedarf einen Wrapper-Ordner für die übergebenen root.children,
    z. B. beim Import einer Einzeldatei oder wenn keine passende Ordnerstruktur vorhanden ist.
    """
    children = storage.root.children

    # A single document (e.g. a plain PDF) is imported as exactly that one node —
    # no superfluous folder wrapper around it.
    if len(children) == 1 and not children[0].is_folder:
        return children[0]

    # An archive/e-mail whose single top folder already matches the file name:
    # don't double-wrap it.
    if (
        len(children) == 1 and
        children[0].is_folder and
        children[0].name.lower() in os.path.basename(filename).lower()
    ):
        return children[0]

    # Otherwise group the imported structure under a folder named after the file.
    wrapper = PDFNode(name=os.path.splitext(os.path.basename(filename))[0], is_folder=True)
    wrapper.children = children
    for child in wrapper.children:
        child.parent = wrapper
    return wrapper

def _carry_acroform(writer: PdfWriter, sources) -> None:
    """Y-6: pypdf copies pages (widgets survive) but never the catalog /AcroForm.
    Rebuild it from the widgets on the writer's pages; /DR /DA /NeedAppearances come
    from the first source form. ``sources`` = readers whose /AcroForm may be carried."""
    try:
        from pypdf.generic import (ArrayObject, BooleanObject, DictionaryObject,
                                   NameObject)
        base = None
        for r in sources:
            af = r.trailer["/Root"].get("/AcroForm")
            if af is not None:
                base = af.get_object()
                break
        if base is None:
            return
        fields, seen = [], set()
        for page in writer.pages:
            for a in page.get("/Annots") or []:
                w = a.get_object()
                if w.get("/Subtype") != "/Widget":
                    continue
                top = a
                while "/Parent" in top.get_object():
                    top = top.get_object()["/Parent"]
                key = top.idnum if hasattr(top, "idnum") and top.idnum else id(top)
                if key not in seen:
                    seen.add(key)
                    fields.append(top)
        if not fields:
            return
        form = DictionaryObject()
        form[NameObject("/Fields")] = ArrayObject(fields)
        for k in ("/DR", "/DA", "/Q", "/NeedAppearances"):
            if k in base:
                v = base[k]
                form[NameObject(k)] = v.clone(writer) if hasattr(v, "clone") and not isinstance(v, BooleanObject) else v
        writer._root_object[NameObject("/AcroForm")] = writer._add_object(form)
    except Exception as e:  # never fail a save over form metadata
        logger.warning("[save] AcroForm konnte nicht übernommen werden: %s", e)



class PDFStorage:
    def __init__(self, source: Optional[Union[str, bytes, io.BytesIO]] = None):
        self.filename: Optional[str] = None
        self.import_time = datetime.datetime.now()
        self.is_dirty: bool = False
        # Degradations while LOADING a .belegtool (corrupt structure, nodes past the
        # page end, hostile pdf_length …). Loading stays tolerant, but these must
        # reach the user (CoreApi.open surfaces them and refuses to bind the path) —
        # a silently degraded open followed by Ctrl+S would destroy the original.
        self.load_warnings: List[str] = []
        self.root = PDFNode(name="root", is_folder=True)
        if source:
            self._load_pdf(source)
        ext = os.path.splitext(self.filename)[1].lower() if self.filename else ""
        self.save_path: Optional[str] = self.filename if ext == ".belegtool" else None

    def mark_dirty(self):
        self.is_dirty = True

    def clear_dirty(self):
        self.is_dirty = False

    def _load_pdf(self, source: Union[str, bytes, io.BytesIO]):
        if isinstance(source, str):
            self.filename = source
            with open(source, 'rb') as f:
                data = f.read()
        elif isinstance(source, bytes):
            data = source
        elif isinstance(source, io.BytesIO):
            data = source.getvalue()
        else:
            raise TypeError("Unsupported source type")


        # Strukturierter Spezialimport: ZIP oder E-Mail
        filename = self.filename.lower() if isinstance(self.filename, str) else ""

        try:
            if filename.endswith(".zip"):
                from universal_importer import extract_zip_to_structure
                struktur = extract_zip_to_structure(data)
                node = PDFNode.from_recursive_array(name=os.path.basename(filename), structure=struktur)
                node.konstruktor_ergebnis = "ZIP-Datei erfolgreich geladen"
                self.root = PDFNode(name="root", is_folder=True)
                self.root.add_child(node)
                return

            if filename.endswith((".tar", ".tar.gz", ".tgz")):
                from universal_importer import extract_tar_to_structure
                struktur = extract_tar_to_structure(data)
                node = PDFNode.from_recursive_array(name=os.path.basename(filename), structure=struktur)
                node.konstruktor_ergebnis = "TAR-Archiv erfolgreich geladen"
                self.root = PDFNode(name="root", is_folder=True)
                self.root.add_child(node)
                return

            if filename.endswith((".eml", ".msg")):
                from universal_importer import extract_email_to_structure
                struktur = extract_email_to_structure(data)
                node = PDFNode.from_recursive_array(name=os.path.basename(filename), structure=struktur)
                node.konstruktor_ergebnis = "E-Mail erfolgreich geladen"
                self.root = PDFNode(name="root", is_folder=True)
                self.root.add_child(node)
                return
        except Exception as e:
            logger.warning("Strukturierter Import fehlgeschlagen (%s): %s", filename, e)
            # For genuine archive/e-mail files, surface the real cause instead of
            # silently falling through to PDF parsing (which then fails with an
            # opaque "not a PDF"). Other extensions still fall back to PDF import.
            if filename.endswith((".zip", ".tar", ".tgz", ".tar.gz", ".eml", ".msg")):
                raise
            # → Fallback auf regulären PDF-Import




        try:
            # Only the app's own exports carry an embedded /JSONStructure tree. A
            # cheap raw-bytes check avoids a full pypdf parse of every plain PDF on
            # import (that parse, not page-counting, dominated headless load time).
            # pypdf writes the marker uncompressed, so the substring is reliable
            # (asserted by test_pdf_storage_additional) — for OUR writer. H-1b
            # (QS 2026-11-04): a .belegtool rewritten by another tool (qpdf, Acrobat
            # "optimize") can move the Info dict into a compressed object stream, so
            # the raw marker vanishes while the structure is still there — for the
            # app's OWN extension always do the full metadata read (rare + already
            # paying a structure parse); only plain .pdf imports keep the fast path.
            is_belegtool = bool(self.filename and self.filename.lower().endswith(".belegtool"))
            json_str = None
            if b"/JSONStructure" in data or is_belegtool:
                reader = PdfReader(io.BytesIO(data))
                metadata = reader.metadata or {}
                json_data = metadata.get('/JSONStructure')
                if isinstance(json_data, bytes):
                    json_str = json_data.decode("utf-8", errors="replace")
                elif isinstance(json_data, str):
                    json_str = json_data
            if not json_str and is_belegtool:
                # a .belegtool ALWAYS carries a structure when our writer produced it —
                # a missing one means the file was damaged/stripped: degrade LOUDLY
                # (CoreApi.open won't bind the path) instead of silently flattening.
                self.load_warnings.append(
                    "Dokumentstruktur fehlt – Datei als einzelnes Dokument geladen")

            if json_str:
                try:
                    structure = json.loads(json_str)
                    self._parse_json_structure(structure, data)
                    return  # ✅ Struktur erfolgreich geladen
                except StructureTooDeep:
                    raise  # refuse a bomb cleanly; don't silently degrade to a single node
                except Exception as e:
                    logger.warning("JSON-Struktur ungültig oder nicht lesbar: %s", e)
                    self.load_warnings.append(
                        "Dokumentstruktur nicht lesbar – Datei als einzelnes Dokument geladen")

            # Kein oder ungültiges JSON → einfacher Import als ein Knoten.
            # Bytes only — the headless core renders/compresses on demand, and
            # node_from_pdfnode snapshots only the bytes, so any eager render or
            # compression here would be pure wasted CPU (it dominated import time
            # on large color PDFs).
            #
            # Repair malformed PDFs first (broken xref/object streams): a no-op
            # when the file already reads cleanly, so .belegtool/structured PDFs
            # (handled above) never reach this and valid plain PDFs are untouched.
            data = sanitize_pdf(data)
            self.root = PDFNode(name="root", is_folder=True)
            name = os.path.splitext(os.path.basename(self.filename))[0] if self.filename else "importiert"
            node = PDFNode(name=name)
            node.set_original_and_current_data(
                original_data=data,
                current_data=None,
                dpi_original=None,
                dpi_current=None,
                no_compression=False,
            )
            self.root.add_child(node)

        except Exception as e:
            raise ValueError(f"Fehler beim Laden des PDFs: {e}")






    def _parse_json_structure(self, structure, data):
        self.root = PDFNode(name="root", is_folder=True)
        if structure.get("uid"):
            self.root.uid = structure["uid"]  # restore the root's id too (not just children)
        if structure.get("collapsed"):
            self.root.collapsed = bool(structure["collapsed"])
        if structure.get("datev"):
            self.root.datev = structure["datev"]  # restore DATEV provenance (root only)
        current_start = [0]  # mutable Seitenzähler

        reader = None
        total_pages = 0
        repair_reason = None
        try:
            reader = PdfReader(io.BytesIO(data))
            total_pages = len(reader.pages)
        except Exception as e:
            repair_reason = str(e)
        if repair_reason is None and total_pages == 0 and self._structure_has_leaves(structure):
            # pypdf is TOLERANT of some page-tree damage (broken /Count, dangling Kids):
            # it reports 0 pages without raising — but the structure says there are
            # documents, so the tree is damaged, not empty (QS-Bewertung 2026-11-04).
            repair_reason = "0 lesbare Seiten trotz Dokumentknoten"
        if repair_reason is not None:
            # Broken page tree: try a REAL repair before degrading. sanitize_pdf is the
            # wrong tool here — it returns unchanged bytes whenever PdfReader CONSTRUCTS.
            # A full pikepdf rewrite regenerates the page tree (QS follow-up, H-1a).
            logger.warning("Seitenbaum nicht lesbar – versuche Reparatur: %s", repair_reason)
            orig_reader = reader  # None when the ORIGINAL parse already failed (B-4)
            try:
                with pike_open(io.BytesIO(data)) as pdf:
                    buf = io.BytesIO()
                    pdf.save(buf)
                repaired = buf.getvalue()
                reader = PdfReader(io.BytesIO(repaired))
                total_pages = len(reader.pages)
                if total_pages == 0:
                    raise ValueError("Reparatur ergab 0 Seiten")
            except Exception as e2:
                if orig_reader is None:
                    # H-1 (QS 2026-11-04): this used to be a silent `return` — the file
                    # opened as an EMPTY document (ok:true) and the next save destroyed
                    # the original. Degrade LOUDLY; CoreApi.open won't bind the path.
                    # (Checked against the ORIGINAL reader — B-4: the repair attempt may
                    # have reassigned `reader` before failing, which used to slip a
                    # folder-only file through without any warning.)
                    logger.error("PDF konnte nicht gelesen werden: %s", e2)
                    self.load_warnings.append(
                        "Seitenbaum nicht lesbar – Dokumentinhalt konnte nicht geladen werden")
                    return
                # the original reader works but sees 0 pages and the repair failed →
                # continue on the ORIGINAL reader; the per-node skip warnings below
                # report every loss.
                logger.warning("Reparatur fehlgeschlagen: %s", e2)
                reader = orig_reader
                total_pages = 0
            else:
                # the repaired content (NOT the on-disk file) is what `reader` now
                # serves — treat as degraded (warn, don't bind the path) so the user
                # saves the rescue as a NEW file. All slicing below reads from `reader`.
                self.load_warnings.append(
                    "Seitenbaum repariert – bitte als neue Datei speichern")

        # Parse the source PDF ONCE and reuse the reader for every node — slicing
        # used to re-parse the whole file per node (O(nodes) full parses = slow load).
        for child_data in structure.get("children", []):
            node = self._parse_node(child_data, reader, current_start, total_pages, depth=1)
            if node:
                self.root.add_child(node)

        # H-1c (QS follow-up 2026-11-04): pages BEYOND what the structure describes used
        # to be dropped silently on the next save (externally appended/edited file).
        if current_start[0] < total_pages:
            extra = total_pages - current_start[0]
            self.load_warnings.append(
                f"{extra} Seiten mehr als die Struktur beschreibt – nicht zugeordnet")

    def _append_pages_with_outline(
        self,
        writer: PdfWriter,
        node: PDFNode,
        page_offset: int = 0,
        parent_outline: Optional[object] = None
    ) -> int:
        """Fügt Seiten und Lesezeichen rekursiv in das PDF ein.

        Args:
            writer: PyPDF2 PdfWriter-Instanz zum Schreiben.
            node: Aktueller PDFNode.
            page_offset: Startseite im Writer.
            parent_outline: Optionaler Elterneintrag für verschachtelte Bookmarks.

        Returns:
            Neue Seitenzahl nach Einfügen der Inhalte.
        """
        current_page_index = page_offset

        if not node.is_folder and node.current_pdf_data:
            reader = PdfReader(io.BytesIO(node.current_pdf_data))
            num_pages = len(reader.pages)

            for page in reader.pages:
                writer.add_page(page)
            if not hasattr(writer, '_beleg_forms'):
                writer._beleg_forms = []
            writer._beleg_forms.append(reader)

            # Lesezeichen für Dokument
            outline_entry = writer.add_outline_item(
                title=node.name,
                page_number=current_page_index,
                parent=parent_outline
            )
            current_page_index += num_pages

        else:
            # Lesezeichen für Ordner, wenn nicht Root
            outline_entry = writer.add_outline_item(
                title=node.name,
                page_number=current_page_index,
                parent=parent_outline
            ) if node != self.root else None

        for child in node.children:
            current_page_index = self._append_pages_with_outline(
                writer, child, current_page_index, outline_entry
            )

        return current_page_index


    def to_bytes(self) -> bytes:
        """Build the .belegtool PDF bytes (pages + /JSONStructure + lossless pikepdf
        recompression) **without writing**. The single source of truth for the file
        content; ``save`` just writes these bytes, and the locked save path writes them
        through the held handle."""
        # 1. Struktur als JSON extrahieren
        structure_json = json.dumps(self.root.to_dict())

        # 2. PDF in den RAM schreiben über PdfWriter (interner Aufbau bleibt)
        buffer = io.BytesIO()
        writer = PdfWriter()
        self._append_pages_with_outline(writer, self.root)
        _carry_acroform(writer, getattr(writer, '_beleg_forms', []))
        writer.add_metadata({"/JSONStructure": structure_json})
        writer.write(buffer)
        raw_pdf = buffer.getvalue()

        # 3. Versuch: verlustfreie Re-Komprimierung via pikepdf
        try:
            with pikepdf.open(io.BytesIO(raw_pdf)) as pdf:
                optimized = io.BytesIO()
                pdf.save(
                    optimized,
                    compress_streams=True,
                    recompress_flate=True,
                    linearize=True  # optional: besser strukturierte Ausgabe
                )
                final_pdf = optimized.getvalue()

                if len(final_pdf) >= len(raw_pdf):
                    final_pdf = raw_pdf
        except Exception as e:
            logger.warning("[save] pikepdf-Komprimierung fehlgeschlagen: %s", e)
            final_pdf = raw_pdf
        return final_pdf

    def save(self, path: Optional[str] = None):
        """Speichert das PDF als Datei mit eingebetteter JSON-Struktur und vollständigem
        Outline (verlustfreie Re-Komprimierung via pikepdf, wenn sinnvoll).

        M-1 (QS 2026-11-04): the write is ATOMIC — a sibling temp file is written and
        ``os.replace``d over the target, so a crash/full disk mid-write can no longer
        destroy the previous on-disk state. When the replace is impossible (the target
        is held open by another process without FILE_SHARE_DELETE — Acrobat, a scanner)
        it falls back to the legacy in-place write rather than failing the save.
        The locked save path (BELEG_FILE_LOCK=1) is separate and keeps its .bak scheme."""
        final_pdf = self.to_bytes()
        target = path or self.filename
        if not target:
            raise ValueError("No path specified and no original filename stored.")
        tmp = f"{target}.tmp-{os.getpid()}"
        try:
            with open(tmp, 'wb') as f:
                f.write(final_pdf)
                f.flush()
                os.fsync(f.fileno())
            try:
                os.replace(tmp, target)  # atomic on the same NTFS volume
            except OSError:
                # target held open elsewhere → legacy in-place write (non-atomic, but
                # the save must not start failing where it used to succeed)
                logger.warning("[save] atomic replace refused for %s – in-place fallback", target)
                with open(target, 'wb') as f:
                    f.write(final_pdf)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    logger.warning("[save] temp file could not be removed: %s", tmp)

        self.clear_dirty()
        if path:
            self.save_path = path



    # NOTE: export_selection() was removed (I-2, QS 2026-11-04): the app exports
    # exclusively through formats.toc_export (CoreApi.export); the method was dead
    # code whose PDFNode.copy() silently dropped tags/collapsed/datev.

    def get_all_nodes(self) -> List[PDFNode]:
        def collect_nodes(node: PDFNode) -> List[PDFNode]:
            result = [node]
            for child in node.children:
                result.extend(collect_nodes(child))
            return result
        return collect_nodes(self.root)


    @staticmethod
    def _structure_has_leaves(structure) -> bool:
        """Whether the persisted tree contains at least one DOCUMENT node — a 0-page
        file is only plausible when it doesn't (folder-only .belegtool)."""
        def walk(children):
            for c in children:
                if not isinstance(c, dict):
                    continue
                if c.get("is_folder"):
                    if walk(c.get("children", []) or []):
                        return True
                else:
                    return True
            return False
        return walk(structure.get("children", []) or [])

    @staticmethod
    def _vz(value):
        """Veranlagungszeitraum field from persisted JSON: int or None. Hand-edited/
        foreign files may carry other types — a later Merge spans vz via min/max, so
        mixed types would crash it (QS-Bewertung 2026-11-04). Coerce or drop; a
        non-integer number drops like the equivalent string does (B-1: 2024.5 must
        never silently truncate to 2024)."""
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, float):
            return int(value) if value.is_integer() else None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _slice_pages(reader: PdfReader, start: int, end: int) -> bytes:
        """Slice pages [start, end] from an already-parsed reader (no re-parse)."""
        writer = PdfWriter()
        for i in range(start, end + 1):
            if 0 <= i < len(reader.pages):
                writer.add_page(reader.pages[i])
        _carry_acroform(writer, [reader])
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    def _parse_node(self, node_data: dict, reader: PdfReader, current_start: List[int], total_pages: int, depth: int = 0) -> Optional['PDFNode']:
        if depth > _MAX_TREE_DEPTH:
            raise StructureTooDeep(f"Baumtiefe überschreitet das Limit von {_MAX_TREE_DEPTH} Ebenen.")
        name = node_data.get("name", "unnamed")
        is_folder = node_data.get("is_folder", False)

        if is_folder:
            node = PDFNode(name=name, is_folder=True)
            if node_data.get("uid"):
                node.uid = node_data["uid"]  # restore persisted id
            node.status = node_data.get("status", "")  # default: no status
            node.vz_start = self._vz(node_data.get("vz_start"))
            node.vz_end = self._vz(node_data.get("vz_end"))
            node.collapsed = bool(node_data.get("collapsed", False))
            node.tags = list(node_data.get("tags") or [])
            for child_data in node_data.get("children", []):
                child_node = self._parse_node(child_data, reader, current_start, total_pages, depth + 1)
                if child_node:
                    node.add_child(child_node)
            return node

        length = node_data.get("pdf_length", 1)
        # N-4 (QS 2026-11-04): a hostile/corrupt pdf_length must never rewind the page
        # counter (negative → following nodes get DUPLICATE page slices) or crash the
        # parse into the silent one-node fallback (non-int). 0 is a legitimate value
        # (0-page leaves exist, see Known Limitations) and stays warning-free.
        if isinstance(length, bool) or not isinstance(length, int) or length < 0:
            self.load_warnings.append(f"{name}: ungültige Seitenanzahl ({length})")
            length = 0
        start = current_start[0]
        end = start + length - 1

        if length > 0 and start >= total_pages:
            logger.warning("Knoten '%s' beginnt bei Seite %d, PDF hat nur %d Seiten – übersprungen.", name, start, total_pages)
            self.load_warnings.append(f"{name}: beginnt hinter dem Seitenende – übersprungen")
            return None

        if end >= total_pages:
            # M-3a (QS 2026-11-04): this clamp used to be completely silent — the node
            # lost pages and the next save persisted the loss without any hint.
            self.load_warnings.append(f"{name}: ragt über das Seitenende hinaus – gekürzt")
            end = total_pages - 1
            length = end - start + 1

        pages = self._slice_pages(reader, start, end)



        node = PDFNode(name=name)
        if node_data.get("uid"):
            node.uid = node_data["uid"]  # restore persisted id
        node.status = node_data.get("status", "")  # default: no status
        node.vz_start = self._vz(node_data.get("vz_start"))  # Veranlagungszeitraum (was dropped on reload)
        node.vz_end = self._vz(node_data.get("vz_end"))
        node.tags = list(node_data.get("tags") or [])
        node.compression_no_gain = bool(node_data.get("compression_no_gain", False))
        is_compressed = bool(node_data.get("is_compressed", False))

        node.set_original_and_current_data(
            original_data=pages,
            current_data=None,
            dpi_original=node_data.get("dpi_original"),
            dpi_current=node_data.get("dpi_current"),
            no_compression=node_data.get("no_compression", False),
        )
        # Restore the persisted is_compressed flag instead of unconditionally resetting it.
        # set_original_and_current_data only sets is_compressed=True when current_data is
        # provided; loading from disk always passes current_data=None, so we must read the
        # flag back from the serialised structure explicitly.
        node.is_compressed = is_compressed
        node.compression_method = node_data.get("compression_method")
        node.dpi_current = node_data.get("dpi_current")    # was lost when current_data=None
        node.dpi_original = node_data.get("dpi_original")

        # Reload coherence: a committed ("Lesbarkeit geprüft") node's persisted
        # pages ARE the chosen compression — its source was dropped on save.
        # Expose them as current_data with NO original, so the model is honest:
        # the Compress handler's `original_data` guard then blocks re-compressing
        # (double compression) and Reset has nothing to revert to.
        if is_compressed:
            node.current_pdf_data = pages
            node.original_pdf_data = None
        node.pdf_length = length

        current_start[0] = end + 1  # Seitenzähler fortschreiben
        return node


    # These three resolve parent/child overlaps in a selection. Each walks every
    # selected node's ancestor chain ONCE against an identity (id()) membership set —
    # O(n·depth) — rather than the former O(n²·depth) all-pairs `_is_descendant_of`
    # scan (F-5). Identity matches the parent-pointer `is` comparison _is_descendant_of
    # used, so behaviour is unchanged.
    @staticmethod
    def has_parent_child_conflict(nodes: List[PDFNode]) -> bool:
        """Returns True if any node in the list is an ancestor of another node in the list."""
        selected = {id(n) for n in nodes}
        for node in nodes:
            cur = node.parent
            while cur is not None:
                if id(cur) in selected:  # a selected ancestor of `node` → overlap
                    return True
                cur = cur.parent
        return False

    @staticmethod
    def filter_keep_ancestors(nodes: List[PDFNode]) -> List[PDFNode]:
        """Keep only root-level selections; remove nodes whose ancestor is also selected."""
        selected = {id(n) for n in nodes}

        def has_selected_ancestor(node: PDFNode) -> bool:
            cur = node.parent
            while cur is not None:
                if id(cur) in selected:
                    return True
                cur = cur.parent
            return False

        return [node for node in nodes if not has_selected_ancestor(node)]

    @staticmethod
    def filter_keep_descendants(nodes: List[PDFNode]) -> List[PDFNode]:
        """Keep only leaf-level selections; remove nodes whose descendant is also selected."""
        selected = {id(n) for n in nodes}
        # Mark every selected node that is an ancestor of another selected node — those
        # have a selected descendant and are the ones to drop.
        has_selected_descendant = set()
        for node in nodes:
            cur = node.parent
            while cur is not None:
                if id(cur) in selected:
                    has_selected_descendant.add(id(cur))
                cur = cur.parent
        return [node for node in nodes if id(node) not in has_selected_descendant]


