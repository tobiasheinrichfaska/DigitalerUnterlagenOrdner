import io
import json
import datetime
from typing import Optional, List, Union, Dict, Any
from pypdf import PdfReader, PdfWriter
from pdf_node import PDFNode
import os
from universal_importer import extract_zip_to_structure, extract_email_to_structure
from pikepdf import open as pike_open
import pikepdf

def create_wrapper_node(storage: 'PDFStorage', filename: str) -> PDFNode:
    """
    Erzeugt bei Bedarf einen Wrapper-Ordner für die übergebenen root.children,
    z. B. beim Import einer Einzeldatei oder wenn keine passende Ordnerstruktur vorhanden ist.
    """
    if (
        len(storage.root.children) == 1 and
        storage.root.children[0].is_folder and
        storage.root.children[0].name.lower() in os.path.basename(filename).lower()
    ):
        return storage.root.children[0]
    else:
        wrapper = PDFNode(name=os.path.splitext(os.path.basename(filename))[0], is_folder=True)
        wrapper.children = storage.root.children
        for child in wrapper.children:
            child.parent = wrapper
        return wrapper

class PDFStorage:
    def __init__(self, source: Optional[Union[str, bytes, io.BytesIO]] = None):
        self.filename: Optional[str] = None
        self.import_time = datetime.datetime.now()
        self.is_dirty: bool = False
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

            if filename.endswith((".eml", ".msg")):
                struktur = extract_email_to_structure(data)
                node = PDFNode.from_recursive_array(name=os.path.basename(filename), structure=struktur)
                node.konstruktor_ergebnis = "E-Mail erfolgreich geladen"
                self.root = PDFNode(name="root", is_folder=True)
                self.root.add_child(node)
                return
        except Exception as e:
            print(f"[WARNUNG] Strukturierter Import fehlgeschlagen ({filename}): {e}")
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
                    print(f"⚠️ JSON-Struktur ungültig oder nicht lesbar: {e}")

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
        """Komprimiert alle nicht-komprimierten Blatt-Nodes im Speicher."""
        for node in self.get_all_nodes():
            if not node.is_folder and not node.is_compressed:
                try:
                    node.compress()
                except Exception as e:
                    print(f"⚠️ Komprimierung fehlgeschlagen für {node.name}: {e}")


    @staticmethod
    def extract_pages(data: bytes, start: int, end: int) -> bytes:
        if start is None or end is None:
            print(f"⚠️ Kein gültiger Seitenbereich angegeben.")
            return b""

        reader = PdfReader(io.BytesIO(data))
        writer = PdfWriter()

        for i in range(start, end + 1):
            if 0 <= i < len(reader.pages):
                writer.add_page(reader.pages[i])
            else:
                print(f"⚠️ Seite {i} liegt außerhalb des gültigen Bereichs ({len(reader.pages)} Seiten)")

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
            print(f"❌ PDF konnte nicht gelesen werden: {e}")
            return

        for child_data in structure.get("children", []):
            node = self._parse_node(child_data, data, current_start, total_pages)
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
            print(f"[save] pikepdf-Komprimierung fehlgeschlagen: {e}")
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


    def _parse_node(self, node_data: dict, data: bytes, current_start: List[int], total_pages: int) -> Optional['PDFNode']:
        name = node_data.get("name", "unnamed")
        is_folder = node_data.get("is_folder", False)

        if is_folder:
            node = PDFNode(name=name, is_folder=True)
            for child_data in node_data.get("children", []):
                child_node = self._parse_node(child_data, data, current_start, total_pages)
                if child_node:
                    node.add_child(child_node)
            return node

        length = node_data.get("pdf_length", 1)
        start = current_start[0]
        end = start + length - 1

        if start >= total_pages:
            print(f"⚠️ Knoten {name} beginnt bei Seite {start}, PDF hat nur {total_pages} Seiten. Übersprungen.")
            return None

        if end >= total_pages:
            end = total_pages - 1
            length = end - start + 1

        pages = self.extract_pages(data, start, end)



        node = PDFNode(name=name)
        node.status = node_data.get("status", "zu erfassen")  # ✅ Hier ergänzen!

        node.set_original_and_current_data(
            original_data=pages,
            current_data=None,
            dpi_original=node_data.get("dpi_original"),
            dpi_current=node_data.get("dpi_current"),
            no_compression=node_data.get("no_compression", False)
        )
        node.is_compressed = False
        node.pdf_length = length

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


    def _get_clean_selection(self, nodes: List[PDFNode], target_parent: PDFNode) -> List[PDFNode]:
        """
        Entfernt Nachfahren UND bereits korrekt platzierte Knoten aus der Selektion.
        """
        def is_descendant_of_any(node):
            return any(ancestor._is_descendant_of(node) for ancestor in nodes)

        result = []
        for node in nodes:
            if is_descendant_of_any(node):
                continue
            result.append(node)
        return result

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
                    print(f"[WARNUNG] Knoten '{node.name}' war nicht in Parent '{node.parent.name}' enthalten.")

            node.parent = new_parent
            new_index = insert_pos + i + insert_offset
            new_parent.children.insert(new_index, node)
            for i, child in enumerate(new_parent.children):
                child.position = i
                print(f" - {child.name}: Position {i}")

        for i, child in enumerate(new_parent.children):
            child.position = i
            print(f" - {child.name}: Position {i}")


