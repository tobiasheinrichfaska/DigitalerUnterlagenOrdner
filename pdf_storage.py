import io
import json
import datetime
from typing import Optional, List, Union, Dict, Any
from pypdf import PdfReader, PdfWriter
from pdf_node import PDFNode
import os
from universal_importer import extract_zip_to_structure, extract_tar_to_structure, extract_email_to_structure
from pikepdf import open as pike_open
import pikepdf
from log_config import logger

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

class PDFStorage:
    def __init__(self, source: Optional[Union[str, bytes, io.BytesIO]] = None,
                 generate_previews: bool = True):
        self.filename: Optional[str] = None
        self.import_time = datetime.datetime.now()
        self.is_dirty: bool = False
        # The Tk app needs PIL previews eagerly; the headless core renders on
        # demand, so it loads with generate_previews=False (skips the per-node
        # PyMuPDF render that dominates load time).
        self._generate_previews = generate_previews
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
                struktur = extract_zip_to_structure(data)
                node = PDFNode.from_recursive_array(name=os.path.basename(filename), structure=struktur)
                node.konstruktor_ergebnis = "ZIP-Datei erfolgreich geladen"
                self.root = PDFNode(name="root", is_folder=True)
                self.root.add_child(node)
                return

            if filename.endswith((".tar", ".tar.gz", ".tgz")):
                struktur = extract_tar_to_structure(data)
                node = PDFNode.from_recursive_array(name=os.path.basename(filename), structure=struktur)
                node.konstruktor_ergebnis = "TAR-Archiv erfolgreich geladen"
                self.root = PDFNode(name="root", is_folder=True)
                self.root.add_child(node)
                return

            if filename.endswith((".eml", ".msg")):
                struktur = extract_email_to_structure(data)
                node = PDFNode.from_recursive_array(name=os.path.basename(filename), structure=struktur)
                node.konstruktor_ergebnis = "E-Mail erfolgreich geladen"
                self.root = PDFNode(name="root", is_folder=True)
                self.root.add_child(node)
                return
        except Exception as e:
            logger.warning("Strukturierter Import fehlgeschlagen (%s): %s", filename, e)
            # → Fallback auf regulären PDF-Import




        try:
            reader = PdfReader(io.BytesIO(data))
            metadata = reader.metadata or {}
            json_data = metadata.get('/JSONStructure')

            # Robustes Parsen des JSON-Feldes
            if isinstance(json_data, bytes):
                json_str = json_data.decode("utf-8", errors="replace")
            elif isinstance(json_data, str):
                json_str = json_data
            else:
                json_str = None

            if json_str:
                try:
                    structure = json.loads(json_str)
                    self._parse_json_structure(structure, data)
                    return  # ✅ Struktur erfolgreich geladen
                except Exception as e:
                    logger.warning("JSON-Struktur ungültig oder nicht lesbar: %s", e)

            # Kein oder ungültiges JSON → einfacher Import als ein Knoten
            self.root = PDFNode(name="root", is_folder=True)
            name = os.path.splitext(os.path.basename(self.filename))[0] if self.filename else "importiert"
            node = PDFNode(name=name, pdf_data=data)
            # Lazy-Kompression aktivieren, falls erlaubt
            if (
                node.original_pdf_data and
                node.current_pdf_data == node.original_pdf_data and
                node.dpi_original is None and
                node.dpi_current is None and
                not node.no_compression
            ):
                node.compress_lazy(dpi=150)

            self.root.add_child(node)

        except Exception as e:
            raise ValueError(f"Fehler beim Laden des PDFs: {e}")

    def compress(self):
        """Komprimiert alle nicht-komprimierten Blatt-Nodes im Speicher.

        Nodes mit gesetztem no_compression-Flag werden übersprungen.
        """
        for node in self.get_all_nodes():
            if not node.is_folder and not node.is_compressed and not node.no_compression:
                try:
                    node.compress()
                except Exception as e:
                    logger.warning("Komprimierung fehlgeschlagen für '%s': %s", node.name, e)


    @staticmethod
    def extract_pages(data: bytes, start: int, end: int) -> bytes:
        if start is None or end is None:
            logger.warning("Kein gültiger Seitenbereich angegeben.")
            return b""

        reader = PdfReader(io.BytesIO(data))
        writer = PdfWriter()

        for i in range(start, end + 1):
            if 0 <= i < len(reader.pages):
                writer.add_page(reader.pages[i])
            else:
                logger.warning("Seite %d liegt außerhalb des gültigen Bereichs (%d Seiten)", i, len(reader.pages))

        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()






    def _parse_json_structure(self, structure, data):
        self.root = PDFNode(name="root", is_folder=True)
        current_start = [0]  # mutable Seitenzähler

        try:
            reader = PdfReader(io.BytesIO(data))
            total_pages = len(reader.pages)
        except Exception as e:
            logger.error("PDF konnte nicht gelesen werden: %s", e)
            return

        # Parse the source PDF ONCE and reuse the reader for every node — slicing
        # used to re-parse the whole file per node (O(nodes) full parses = slow load).
        for child_data in structure.get("children", []):
            node = self._parse_node(child_data, reader, current_start, total_pages)
            if node:
                self.root.add_child(node)

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


    def save(self, path: Optional[str] = None):
        """
        Speichert das PDF als Datei mit eingebetteter JSON-Struktur und vollständigem Outline.
        Führt eine verlustfreie Re-Komprimierung mit pikepdf durch, wenn sinnvoll.
        """

        # 1. Struktur als JSON extrahieren
        structure_json = json.dumps(self.root.to_dict())

        # 2. PDF in den RAM schreiben über PdfWriter (interner Aufbau bleibt)
        buffer = io.BytesIO()
        writer = PdfWriter()
        self._append_pages_with_outline(writer, self.root)
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

        # 4. PDF speichern
        if path:
            with open(path, 'wb') as f:
                f.write(final_pdf)
        elif self.filename:
            with open(self.filename, 'wb') as f:
                f.write(final_pdf)
        else:
            raise ValueError("No path specified and no original filename stored.")

        self.clear_dirty()
        if path:
            self.save_path = path



    def export_selection(self, nodes: List[PDFNode], path: str):
        """Export only the selected nodes to a file.

        If a parent and its child are both selected, the parent takes precedence
        (the full subtree is exported). Saves as .belegtool (with embedded structure)
        or .pdf (same content, no structure metadata); the format is chosen by path extension.
        """
        top_level = self.filter_keep_ancestors(nodes)
        copies = [node.copy(keep_name=True) for node in top_level]

        temp_storage = PDFStorage()
        for c in copies:
            temp_storage.root.add_child(c)
        temp_storage.save(path)

    # def export_as_bytes(self) -> bytes:
    #     buffer = io.BytesIO()
    #     writer = PdfWriter()

    #     def append_pages(node: PDFNode):
    #         if not node.is_folder and node.current_pdf_data:
    #             reader = PdfReader(io.BytesIO(node.current_pdf_data))
    #             for page in reader.pages:
    #                 writer.add_page(page)
    #         for child in node.children:
    #             append_pages(child)

    #     append_pages(self.root)
    #     writer.write(buffer)
    #     return buffer.getvalue()

    def get_structure_json(self) -> str:
        """Gibt die JSON-Struktur der PDF-Nodes zurück – inklusive automatisch gesetzter Seitenbereiche."""
        return json.dumps(self.root.to_dict(), indent=2)

    def get_all_nodes(self) -> List[PDFNode]:
        def collect_nodes(node: PDFNode) -> List[PDFNode]:
            result = [node]
            for child in node.children:
                result.extend(collect_nodes(child))
            return result
        return collect_nodes(self.root)


    @staticmethod
    def _slice_pages(reader: PdfReader, start: int, end: int) -> bytes:
        """Slice pages [start, end] from an already-parsed reader (no re-parse)."""
        writer = PdfWriter()
        for i in range(start, end + 1):
            if 0 <= i < len(reader.pages):
                writer.add_page(reader.pages[i])
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    def _parse_node(self, node_data: dict, reader: PdfReader, current_start: List[int], total_pages: int) -> Optional['PDFNode']:
        name = node_data.get("name", "unnamed")
        is_folder = node_data.get("is_folder", False)

        if is_folder:
            node = PDFNode(name=name, is_folder=True)
            for child_data in node_data.get("children", []):
                child_node = self._parse_node(child_data, reader, current_start, total_pages)
                if child_node:
                    node.add_child(child_node)
            return node

        length = node_data.get("pdf_length", 1)
        start = current_start[0]
        end = start + length - 1

        if start >= total_pages:
            logger.warning("Knoten '%s' beginnt bei Seite %d, PDF hat nur %d Seiten – übersprungen.", name, start, total_pages)
            return None

        if end >= total_pages:
            end = total_pages - 1
            length = end - start + 1

        pages = self._slice_pages(reader, start, end)



        node = PDFNode(name=name)
        node.status = node_data.get("status", "zu erfassen")  # ✅ Hier ergänzen!

        node.set_original_and_current_data(
            original_data=pages,
            current_data=None,
            dpi_original=node_data.get("dpi_original"),
            dpi_current=node_data.get("dpi_current"),
            no_compression=node_data.get("no_compression", False),
            generate_preview=self._generate_previews,
        )
        # Restore the persisted is_compressed flag instead of unconditionally resetting it.
        # set_original_and_current_data only sets is_compressed=True when current_data is
        # provided; loading from disk always passes current_data=None, so we must read the
        # flag back from the serialised structure explicitly.
        node.is_compressed = bool(node_data.get("is_compressed", False))
        node.compression_method = node_data.get("compression_method")
        node.pdf_length = length

        if self._generate_previews:
            node.update_preview()
        current_start[0] = end + 1  # Seitenzähler fortschreiben
        return node


    def perform_move(self, nodes: List[PDFNode], target_node: PDFNode) -> List[Dict[str, Any]]:
        """
        Führt bereinigte Verschiebung durch. Gibt GUI-Umbauplan für gesamte Struktur zurück.
        """
        self._move_nodes_to_parent(nodes, target_node)  # ✅ korrekt, interne Methode
        self.mark_dirty()
        return self.get_full_gui_plan()

    def get_full_gui_plan(self) -> List[Dict[str, Any]]:
        """
        Gibt die komplette Struktur als UID-Zuordnung für den TreeView zurück,
        sortiert nach Tiefe und Index.
        """
        result = []

        def recurse(node: PDFNode, depth: int = 0):
            for i, child in enumerate(node.children):
                result.append({
                    "uid": child.uid,
                    "parent_uid": node.uid,
                    "index": i,
                    "depth": depth
                })
                recurse(child, depth + 1)

        recurse(self.root)
        return sorted(result, key=lambda e: (e["depth"], e["index"]))


    @staticmethod
    def has_parent_child_conflict(nodes: List[PDFNode]) -> bool:
        """Returns True if any node in the list is an ancestor of another node in the list."""
        return any(
            node._is_descendant_of(other)
            for node in nodes
            for other in nodes
            if other is not node
        )

    @staticmethod
    def filter_keep_ancestors(nodes: List[PDFNode]) -> List[PDFNode]:
        """Keep only root-level selections; remove nodes whose ancestor is also selected."""
        return [
            node for node in nodes
            if not any(node._is_descendant_of(other) for other in nodes if other is not node)
        ]

    @staticmethod
    def filter_keep_descendants(nodes: List[PDFNode]) -> List[PDFNode]:
        """Keep only leaf-level selections; remove nodes whose descendant is also selected."""
        return [
            node for node in nodes
            if not any(other._is_descendant_of(node) for other in nodes if other is not node)
        ]

    def _get_clean_selection(self, nodes: List[PDFNode], target_parent: PDFNode) -> List[PDFNode]:
        """Entfernt Nachfahren aus der Selektion (behält Vorfahren)."""
        return self.filter_keep_ancestors(nodes)

    def _move_nodes_to_parent(self, nodes: List[PDFNode], target_node: PDFNode):
        """
        Führt die Verschiebung der Nodes im Baum durch.
        - Wenn target_node Ordner: → Einfügen ans Ende
        - Wenn PDF: → Einfügen direkt unterhalb (im selben Parent)
        """
        if not target_node:
            # print("[ABBRUCH] Kein Zielknoten angegeben.")
            return

        if target_node.is_folder:
            new_parent = target_node
            insert_pos = len(new_parent.children)
        else:
            new_parent = target_node.parent
            if not new_parent:
                return
            insert_pos = new_parent.children.index(target_node) + 1
        clean = self._get_clean_selection(nodes, new_parent)
        insert_offset = 0
        for i, node in enumerate(clean):
            if node.parent:
                try:
                    # innerhalb gleichen Parents und nach unten? → Index korrigieren
                    if node.parent == new_parent and node.position is not None and node.position < insert_pos:
                        insert_offset -= 1
                    node.parent.children.remove(node)
                except ValueError:
                    logger.warning("Knoten '%s' war nicht in Parent '%s' enthalten.", node.name, node.parent.name)

            node.parent = new_parent
            new_index = insert_pos + i + insert_offset
            new_parent.children.insert(new_index, node)

        for idx, child in enumerate(new_parent.children):
            child.position = idx


