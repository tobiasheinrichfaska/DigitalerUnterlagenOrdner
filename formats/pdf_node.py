import io
import uuid
from typing import Optional, List, Dict, Any
import fitz
from pypdf import PdfReader, PdfWriter
from infra.log_config import logger


class PDFNode:
    """Serialisation carrier for the legacy ``.belegtool`` I/O path only.

    The live app performs every PDF operation (split / merge / rotate / compress)
    in the immutable core via ``core.engine``; this class is now solely the
    load/save carrier that ``core.bridge`` converts to and from the
    ``core.model`` tree. It stores bytes plus metadata and **never renders
    previews** — the headless core renders on demand, so eager rendering here was
    pure wasted work (it dominated import time on large colour PDFs).
    """

    def __init__(self, name: str, parent: Optional['PDFNode'] = None,
                 is_folder: bool = False, pdf_data: Optional[bytes] = None):
        if isinstance(pdf_data, io.BytesIO):
            pdf_data = pdf_data.getvalue()

        self.name = name
        self.parent = parent
        self.uid = str(uuid.uuid4())
        self.is_folder = is_folder
        self.children: List[PDFNode] = []
        self.pdf_length: int = 0  # always present, also for folders
        self.status = ""  # no status by default (see core.model.STATUS_NONE)
        self.position: Optional[int] = None
        self.vz_start: Optional[int] = None
        self.vz_end: Optional[int] = None
        self.is_compressed: bool = False
        self.dpi_original: Optional[int] = None
        self.dpi_current: Optional[int] = None
        self.no_compression: bool = False
        self.compression_no_gain: bool = False  # evaluated, nothing smaller found (persisted)
        self.collapsed: bool = False  # folder collapsed in the tree view (persisted)
        self.compression_method: Optional[str] = None  # jpg/png/pikepdf chosen for current_data
        self.tags: List[str] = []  # free-form labels (persisted)

        if pdf_data and not is_folder:
            self.set_original_and_current_data(
                original_data=pdf_data, current_data=None,
                dpi_original=None, dpi_current=None, no_compression=False)
        else:
            self.original_pdf_data = pdf_data
            self.current_pdf_data = pdf_data
            self.pdf_length = self._get_pdf_length(pdf_data)

    def is_valid(self) -> bool:
        return self.current_pdf_data is not None

    def _get_pdf_length(self, data: Optional[bytes]) -> int:
        if not data:
            return 0
        try:
            # fitz page_count is ~ms; pypdf's len(reader.pages) parses the whole
            # page tree and dominated headless import time.
            with fitz.open(stream=data, filetype="pdf") as doc:
                return doc.page_count
        except Exception:
            try:
                return len(PdfReader(io.BytesIO(data)).pages)
            except Exception:
                return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,  # persist node id so attachments (compression variants) match on reload
            "name": self.name,
            "is_folder": self.is_folder,
            "status": self.status,
            "position": self.position,
            "vz_start": self.vz_start,
            "vz_end": self.vz_end,
            "pdf_length": self.pdf_length,
            "is_compressed": self.is_compressed,
            "dpi_original": self.dpi_original,
            "dpi_current": self.dpi_current,
            "no_compression": self.no_compression,
            "compression_no_gain": self.compression_no_gain,
            "collapsed": self.collapsed,
            "compression_method": self.compression_method,
            "tags": list(self.tags),
            "children": [child.to_dict() for child in self.children],
        }

    def add_child(self, child: 'PDFNode'):
        """Hängt ein Kindelement an und setzt dessen Parent-Verweis + Position."""
        child.parent = self
        child.position = len(self.children)
        self.children.append(child)

    def _is_descendant_of(self, node: 'PDFNode') -> bool:
        current = self.parent
        while current:
            if current is node:
                return True
            current = current.parent
        return False

    def copy(self, keep_name: bool = False) -> 'PDFNode':
        """Tiefe Kopie mit eigenen Byte-Puffern — von PDFStorage.export_selection genutzt."""
        copied = PDFNode(
            name=self.name if keep_name else f"{self.name}_copy",
            is_folder=self.is_folder, pdf_data=None)

        copied.status = self.status
        copied.vz_start = self.vz_start
        copied.vz_end = self.vz_end
        copied.current_pdf_data = self.current_pdf_data[:] if self.current_pdf_data else None
        copied.original_pdf_data = self.original_pdf_data[:] if self.original_pdf_data else None
        copied.pdf_length = self.pdf_length
        copied.is_compressed = self.is_compressed
        copied.no_compression = self.no_compression
        copied.compression_no_gain = self.compression_no_gain
        copied.dpi_original = self.dpi_original
        copied.dpi_current = self.dpi_current
        copied.compression_method = self.compression_method

        for child in self.children:
            copied.add_child(child.copy(keep_name=keep_name))

        return copied

    def _concat_children_data(self, attr: str) -> Optional[bytes]:
        """Hängt die effektiven PDF-Daten aller Child-Knoten zusammen.

        Liest bewusst die *Property* jedes Kindes (``current_pdf_data`` /
        ``original_pdf_data``), nicht das private Attribut: so liefert ein Blatt
        seinen current→original-Fallback und ein Unterordner rekursiv seine
        Daten. Sonst entfielen noch nicht komprimierte Blätter, no_compression-
        Knoten und Unterordner.
        """
        writer = PdfWriter()
        for child in self.children:
            data = getattr(child, attr, None)
            if not isinstance(data, bytes):
                continue
            try:
                for page in PdfReader(io.BytesIO(data)).pages:
                    writer.add_page(page)
            except Exception as e:
                logger.warning("Fehler beim Zusammenfügen von %s: %s", child.name, e)

        if writer.pages:
            buf = io.BytesIO()
            writer.write(buf)
            return buf.getvalue()

        return None

    @property
    def current_pdf_data(self) -> Optional[bytes]:
        if self.is_folder:
            # Read each child's *property* (effective data): a leaf falls back
            # current → original, a sub-folder recurses. Reading the private
            # attribute directly would silently drop not-yet-compressed leaves,
            # no_compression nodes and sub-folders.
            return self._concat_children_data("current_pdf_data")
        return self._current_pdf_data or self._original_pdf_data

    @current_pdf_data.setter
    def current_pdf_data(self, value: Optional[bytes]):
        if self.is_folder:
            return
        self._current_pdf_data = value

    @property
    def original_pdf_data(self) -> Optional[bytes]:
        if self.is_folder:
            return self._concat_children_data("original_pdf_data")
        return self._original_pdf_data

    @original_pdf_data.setter
    def original_pdf_data(self, value: Optional[bytes]):
        if self.is_folder:
            return
        self._original_pdf_data = value

    def set_original_and_current_data(
        self,
        original_data: Optional[bytes],
        current_data: Optional[bytes],
        dpi_original: Optional[int],
        dpi_current: Optional[int],
        no_compression: bool,
    ) -> None:
        """Speichert Original-/Current-Bytes + Flags. Bytes-only — kein Rendern.

        ``is_compressed`` wird hier bewusst NICHT gesetzt; der Aufrufer
        (``PDFStorage._parse_node``) restauriert das Flag aus der persistierten
        Struktur, da beim Laden current_data immer None ist.
        """
        if self.is_folder:
            return

        self.dpi_original = dpi_original
        self.dpi_current = dpi_current if current_data else None
        self.no_compression = no_compression
        self.current_pdf_data = current_data
        self.original_pdf_data = original_data
        # pdf_length is a cheap count of this node's own pages (needed for
        # export/TOC and page counts), not a re-render.
        self.pdf_length = self._get_pdf_length(original_data)

    @classmethod
    def from_recursive_array(cls, name: str, structure: List[Dict[str, Any]]) -> 'PDFNode':
        """Baut einen Ordnerknoten aus einer rekursiven Import-Struktur (ZIP/E-Mail).

        Args:
            name: Name des Wurzelknotens (z. B. "ZIP-Inhalt", "E-Mail").
            structure: Liste aus Dicts mit "name", "content" oder "children".
        """
        root = cls(name=name, is_folder=True)

        for entry in structure:
            content = entry.get("content")
            if isinstance(content, io.BytesIO):
                entry["content"] = content.getvalue()
            node = cls._from_structure_entry(entry, parent=root)
            root.add_child(node)

        return root

    @staticmethod
    def _from_structure_entry(entry: Dict[str, Any], parent: Optional['PDFNode'] = None) -> 'PDFNode':
        """Wandelt einen einzelnen Struktur-Eintrag in einen PDFNode um (rekursiv bei children)."""
        name = entry.get("name", "Unbenannt")

        if "children" in entry:
            node = PDFNode(name=name, is_folder=True)
            for child_entry in entry["children"]:
                node.add_child(PDFNode._from_structure_entry(child_entry, parent=node))
        else:
            content = entry.get("content")
            if isinstance(content, io.BytesIO):
                content = content.getvalue()
            node = PDFNode(name=name, is_folder=False)
            if content:
                node.set_original_and_current_data(
                    original_data=content, current_data=None,
                    dpi_original=None, dpi_current=None, no_compression=False)

        node.parent = parent
        return node
