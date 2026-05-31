import io
import time
import threading
import uuid
from typing import Optional, List, Union, Dict, Any
from compress_pdf_bytes import compress_pdf_bytes, compress_all_methods
import fitz
from PIL import Image
from tools import sanitize_pdf
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from status_display import register_task, unregister_task
from preview_page import PreviewPage
from log_config import logger



class PDFNode:
    def __init__(self, name: str, parent: Optional['PDFNode'] = None,
                 is_folder: bool = False, pdf_data: Optional[bytes] = None):
        """Initialisiert einen neuen PDFNode mit Name, Elternbezug und optionalen PDF-Daten."""

        self._original_preview_pages = []
        self._current_preview_pages = []

        self._preview_task_running = False
        self._preview_task_lock = threading.Lock()
        self._preview_task_requested: bool = False
        self._preview_done = threading.Event()
        self._preview_done.set()

        self._compression_task_running: bool = False
        self._compression_task_lock = threading.Lock()
        self._compression_task_requested: bool = False
        self._compression_task_dpi: int = 120
        self._compression_results: Dict[str, bytes] = {}  # method → bytes, populated by compress_multi_lazy


        self._cached_preview_images: Optional[List[Image.Image]] = None
        self._cached_preview_task_running: bool = False

        if isinstance(pdf_data, io.BytesIO):
            pdf_data = pdf_data.getvalue()

        self.name = name
        self.parent = parent
        self.uid = str(uuid.uuid4())
        self.is_folder = is_folder
        self.children: List[PDFNode] = []
        self.pdf_length: int = 0  # immer vorhanden, auch für Folder
        self.status = "zu erfassen"
        self.position: Optional[int] = None
        self.vz_start: Optional[int] = None
        self.vz_end: Optional[int] = None
        self.is_compressed: bool = False
        self.dpi_original: Optional[int] = None
        self.dpi_current: Optional[int] = None
        self.no_compression: bool = False

        # Zentralisierte Verarbeitung via set_original_and_current_data
        if pdf_data and not is_folder:
            try:
                self.set_original_and_current_data(
                    original_data=pdf_data,
                    current_data=None,
                    dpi_original=None,
                    dpi_current=None,
                    no_compression=False
                )
            except Exception as e:
                logger.warning("Fehlerhafte PDF beim Erstellen von '%s': %s", name, e)
                self.original_pdf_data = pdf_data
                self.current_pdf_data = pdf_data
                self.pdf_length = self._get_pdf_length(pdf_data)
        else:
            self.original_pdf_data = pdf_data
            self.current_pdf_data = pdf_data
            self.pdf_length = self._get_pdf_length(pdf_data)


    def is_valid(self) -> bool:
        return self.current_pdf_data is not None


    @classmethod
    def from_pdf(cls, name: str, source: Union[str, bytes, io.BytesIO]) -> 'PDFNode':
        """Erzeugt einen PDFNode aus Pfad, Bytes oder BytesIO. Raises ValueError/TypeError on failure."""
        if isinstance(source, str):
            with open(source, 'rb') as f:
                data = f.read()
        elif isinstance(source, bytes):
            data = source
        elif isinstance(source, io.BytesIO):
            data = source.getvalue()
        else:
            raise TypeError("Unsupported source type")

        # Reparatur zentral durchführen
        data = sanitize_pdf(data)

        # Validierung durch PdfReader
        try:
            PdfReader(io.BytesIO(data))
        except PdfReadError as e:
            raise ValueError(f"[from_pdf] PDF konnte nicht gelesen werden: {e}")

        # Konstruktor aufrufen
        node = cls(name=name, pdf_data=data)

        return node

    def change_parent(self, new_parent, index=None):
        if self.parent and self in self.parent.children:
            self.parent.children.remove(self)
        self.parent = new_parent
        if index is None:
            new_parent.children.append(self)
        else:
            new_parent.children.insert(index, self)



    def _get_pdf_length(self, data: Optional[bytes]) -> int:
        if not data:
            return 0
        try:
            reader = PdfReader(io.BytesIO(data))
            return len(reader.pages)
        except Exception:
            return 0


    def _create_previews(self, data: Optional[bytes]) -> List[Image.Image]:

        if not data:
            logger.warning("Leere PDF-Daten – Vorschau abgebrochen.")
            return []

        try:
            raw = data.getvalue() if isinstance(data, io.BytesIO) else data
            if not raw:
                return []

            try:
                doc = fitz.open(stream=raw, filetype="pdf")
            except Exception as e:
                logger.warning("PDF konnte nicht geöffnet werden (fitz): %s", e)
                return []

            previews = []
            for page in doc:
                try:
                    pix = page.get_pixmap(dpi=100)
                    ppm_bytes = pix.tobytes("ppm")
                    if not ppm_bytes.startswith(b"P6"):
                        logger.warning("Ungültiger PPM-Header auf Seite %d – Vorschau abgebrochen.", page.number)
                        continue
                    with Image.open(io.BytesIO(ppm_bytes)) as im:
                        img = im.convert("RGB").copy()
                    previews.append(img)
                except Exception as e:
                    logger.warning("Vorschaufehler auf Seite %d: %s", page.number, e)
                    continue

            if not previews:
                logger.warning("Keine Seitenvorschau möglich – alle Seiten fehlerhaft?")
                raise ValueError("Ungültige PDF-Daten: keine gültige Vorschau erzeugt.")

            return previews

        except Exception as e:
            logger.error("FEHLER bei Vorschau-Erzeugung: %s", e)
            return []


    def preview_folder(self):
        """
        Erzeugt synchron eine zusammengesetzte Vorschau für alle Children dieses Folder-Knotens.
        Diese Methode wird sofort ausgeführt, ohne Lazy-Mechanismus oder Threads.
        """
        logger.debug("FolderPreview: Starte Vorschauaufbau für '%s'", self.name)
        self._cached_preview_task_running = True
        self._cached_preview_images = []

        for child in self.children:
            if child.is_folder:
                child.preview_folder()
            else:
                child.update_preview()

            self._cached_preview_images.extend(child.current_preview_images)

        self._cached_preview_task_running = False
        logger.debug("FolderPreview: Fertig mit Vorschau für '%s'", self.name)


    def preview_lazy(self):
        """
        Erzeugt die Vorschau asynchron im Hintergrund.
        Wenn bereits eine Vorschauerzeugung läuft, wird genau ein Folge-Task vorgemerkt.
        Bei Foldern wird die Vorschau für alle Kinder angestoßen und der Cache invalidiert.
        """
        if self.is_folder:
            self._cached_preview_images = None
            self.preview_folder()
            return

        if not self.current_pdf_data:
            return

        with self._preview_task_lock:
            if self._preview_task_running:
                if not self._preview_task_requested:
                    self._preview_task_requested = True
                    logger.debug("Preview '%s': Vorschau läuft – Folge-Task vorgemerkt", self.name)
                else:
                    logger.debug("Preview '%s': Vorschau läuft – Folge-Task bereits vorgemerkt", self.name)
                return
            else:
                self._preview_task_running = True
                self._preview_task_requested = False
                self._preview_done.clear()

        register_task(f"Vorschau: {self.name}")

        def run():
            try:
                # Original-Vorschau
                if self.original_pdf_data:
                    images = self._create_previews(self.original_pdf_data)
                    self._original_preview_pages = [
                        PreviewPage(img, i) for i, img in enumerate(images)
                    ]
                else:
                    self._original_preview_pages = []

                # Aktuelle Vorschau
                if self._current_pdf_data:
                    images = self._create_previews(self._current_pdf_data)
                    self._current_preview_pages = [
                        PreviewPage(img, i) for i, img in enumerate(images)
                    ]
                else:
                    self._current_preview_pages = self._original_preview_pages[:]

            except Exception as e:
                logger.error("Preview-Fehler bei '%s': %s", self.name, e)

            finally:
                unregister_task(f"Vorschau: {self.name}")
                with self._preview_task_lock:
                    self._preview_task_running = False
                    self._preview_done.set()
                    if self._preview_task_requested:
                        logger.debug("Preview '%s': Starte vorgemerkten Folge-Task", self.name)
                        self._preview_task_requested = False

                        def delayed_restart():
                            time.sleep(0.01)
                            with self._preview_task_lock:
                                if not self._preview_task_running:
                                    threading.Thread(target=self.preview_lazy, daemon=True).start()

                        threading.Thread(target=delayed_restart, daemon=True).start()

        threading.Thread(target=run, daemon=True).start()

    def compress_lazy(self, dpi: int = 120):
        """
        Startet eine Hintergrund-Kompression mit dem gegebenen DPI-Wert.
        Wenn bereits eine Kompression läuft, wird kein weiterer Task gestartet.

        Der Zugriff auf _compression_task_running ist durch _compression_task_lock
        geschützt, damit zwei gleichzeitige Aufrufe nicht beide einen Task starten.
        """
        if self.is_folder or not self.original_pdf_data:
            logger.debug("Kompression '%s': übersprungen (Ordner oder keine Daten)", self.name)
            return

        with self._compression_task_lock:
            if self._compression_task_running:
                logger.debug("Kompression '%s': übersprungen – bereits laufend", self.name)
                return
            self._compression_task_running = True

        register_task(f"Kompression: {self.name}")

        def run():
            try:
                self.compress(dpi=dpi)
            except Exception as e:
                logger.error("Kompression bei '%s' fehlgeschlagen: %s", self.name, e)
            finally:
                unregister_task(f"Kompression: {self.name}")
                self._compression_task_running = False

        threading.Thread(target=run, daemon=True).start()



    def compress_multi_lazy(self, dpi: int = 120):
        """Runs all available compression methods in background.

        On completion, _compression_results is populated with every method that
        produced a file smaller than the original. current_pdf_data is set to the
        smallest result. If called while already running, the new DPI is queued
        and a second run starts automatically when the first finishes.
        """
        if self.is_folder or not self.original_pdf_data:
            return
        with self._compression_task_lock:
            if self._compression_task_running:
                self._compression_task_requested = True
                self._compression_task_dpi = dpi
                return
            self._compression_task_running = True
            self._compression_task_dpi = dpi

        register_task(f"Kompression: {self.name}")

        def run():
            run_dpi = self._compression_task_dpi
            try:
                results = compress_all_methods(self.original_pdf_data, dpi=run_dpi)
                self._compression_results = results
                if results:
                    best_method = next(iter(results))
                    best_bytes = results[best_method]
                    self.current_pdf_data = best_bytes
                    self.is_compressed = True
                    self.pdf_length = self._get_pdf_length(best_bytes)
                    self.current_preview_images = self._create_previews(best_bytes)
                    self.dpi_current = run_dpi
            except Exception as e:
                logger.error("Multi-Kompression bei '%s' fehlgeschlagen: %s", self.name, e)
            finally:
                unregister_task(f"Kompression: {self.name}")
                with self._compression_task_lock:
                    self._compression_task_running = False
                    if self._compression_task_requested:
                        self._compression_task_requested = False
                        next_dpi = self._compression_task_dpi
                        threading.Thread(
                            target=lambda: self.compress_multi_lazy(next_dpi),
                            daemon=True
                        ).start()

        threading.Thread(target=run, daemon=True).start()

    def select_compression_method(self, method: str):
        """Switch current_pdf_data to a previously computed compression result."""
        if method not in self._compression_results:
            raise ValueError(f"Methode '{method}' nicht verfügbar.")
        data = self._compression_results[method]
        self.current_pdf_data = data
        self.is_compressed = True
        self.pdf_length = self._get_pdf_length(data)
        self.current_preview_images = self._create_previews(data)

    def compress(self, dpi: int = 120) -> None:
        """Komprimiert synchron mit allen verfügbaren Methoden und wählt das beste Ergebnis.

        Probiert JPG, PNG und pikepdf; übernimmt das kleinste Ergebnis, das kleiner als
        das Original ist. Wenn keine Methode eine Verkleinerung liefert, bleiben
        current_pdf_data und is_compressed unverändert.
        """
        if self.is_folder:
            raise ValueError("Ordner können nicht komprimiert werden.")

        if not self.is_valid() or not self.original_pdf_data:
            raise ValueError("Knoten enthält keine gültigen PDF-Daten zur Komprimierung.")

        try:
            results = compress_all_methods(self.original_pdf_data, dpi=dpi)
            if results:
                best_method = next(iter(results))
                compressed = results[best_method]
                self._compression_results = results
                self.current_pdf_data = compressed
                self.is_compressed = True
                self.pdf_length = self._get_pdf_length(compressed)
                self.current_preview_images = self._create_previews(compressed)
                self.dpi_current = dpi
            # If no method produced a smaller result, leave the node as-is.
        except Exception as e:
            raise RuntimeError("Komprimierung fehlgeschlagen") from e

    def _rotate_pdf_data(self, data: bytes, angle: int) -> bytes:
        reader = PdfReader(io.BytesIO(data))
        writer = PdfWriter()
        for page in reader.pages:
            page.rotate(angle)
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    def rotate(self, direction: str = "right") -> None:
        """
        Dreht Blattknoten (PDFs) oder rekursiv alle Blattknoten unterhalb eines Folders.
        Folderknoten selbst drehen sich nicht.
        direction: "right", "left", "180"
        """
        angle_map = {
            "right": 90,
            "left": -90,
            "180": 180
        }
        angle = angle_map.get(direction)
        if angle is None:
            raise ValueError(f"Ungültige Dreh-Richtung: {direction}")

        if self.is_folder:
            for child in self.children:
                child.rotate(direction)
            return

        if not self.original_pdf_data:
            logger.warning("Kein Original vorhanden bei '%s' – Rotation übersprungen.", self.name)
            return

        try:
            self.original_pdf_data = self._rotate_pdf_data(self.original_pdf_data, angle)
            self.current_pdf_data = None
            self.is_compressed = False
            self.dpi_current = None
            self.update_preview()

            if not self.no_compression:
                self.compress_lazy()

        except Exception as e:
            raise RuntimeError(f"Rotation fehlgeschlagen bei {self.name}: {e}")


    def update_preview(self):
        if self.current_pdf_data:
            self.current_preview_images = self._create_previews(self.current_pdf_data)
        else:
            self._current_preview_pages = []

        if self.original_pdf_data:
            self.original_preview_images = self._create_previews(self.original_pdf_data)
        else:
            self._original_preview_pages = []

    def to_dict(self) -> Dict[str, Any]:
        return {
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
            "children": [child.to_dict() for child in self.children]
        }

    def add_child(self, child: 'PDFNode'):
        """Fügt dem aktuellen Knoten ein untergeordnetes Kindelement hinzu und setzt dessen Parent-Verweis."""
        child.parent = self
        child.position = len(self.children)
        self.children.append(child)

    def merge(self, other: 'PDFNode', nopreview: bool = False) -> None:

        """
        Führt zwei gleichartige Knoten (Ordner oder PDFs) zusammen.
        Leitet weiter an _merge_folder oder _merge_pdf.
        """
        if self.is_folder != other.is_folder:
            raise ValueError("Nur gleichartige Knoten können zusammengeführt werden.")

        if not self.is_valid() or not other.is_valid():
            raise ValueError("Einer der Knoten enthält keine gültigen PDF-Daten.")

        if self.is_folder:
            self._merge_folder(other)
        else:
            self._merge_pdf(other, nopreview=nopreview)



    @staticmethod
    def _concat_two_pdfs(a: bytes, b: bytes) -> bytes:
        writer = PdfWriter()
        for page in PdfReader(io.BytesIO(a)).pages:
            writer.add_page(page)
        for page in PdfReader(io.BytesIO(b)).pages:
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    def _merge_folder(self, other: 'PDFNode') -> None:
        """
        Führt zwei Ordnerknoten zusammen, indem die Children von `other`
        in diesen Knoten übernommen werden.
        """
        for child in other.children:
            self.add_child(child)

        # Vorschau bei Ordnern wird automatisch neu erzeugt,
        # Vorschau neu starten
        self.preview_lazy()

    def _merge_pdf(self, other: 'PDFNode', nopreview: bool = False) -> None:
        try:
            PdfReader(io.BytesIO(self.current_pdf_data))
            PdfReader(io.BytesIO(other.current_pdf_data))
            fitz.open(stream=self.current_pdf_data, filetype="pdf").close()
            fitz.open(stream=other.current_pdf_data, filetype="pdf").close()
        except Exception as e:
            raise ValueError("Mindestens ein Knoten enthält kein gültiges PDF") from e

        dpi_orig_set = {self.dpi_original, other.dpi_original} - {None}
        dpi_curr_set = {self.dpi_current, other.dpi_current} - {None}
        dpi_conflict = len(dpi_orig_set) > 1 or len(dpi_curr_set) > 1

        if dpi_conflict:
            # DPI-Konflikt: komprimierte Daten verwerfen, keine erneute Kompression.
            # dpi_current bleibt None — wird weiter unten NICHT überschrieben.
            self.current_pdf_data = None
            self.dpi_current = None
            self.no_compression = True

        if self.current_pdf_data and other.current_pdf_data:
            self.current_pdf_data = self._concat_two_pdfs(self.current_pdf_data, other.current_pdf_data)

        if self.original_pdf_data and other.original_pdf_data:
            self.original_pdf_data = self._concat_two_pdfs(self.original_pdf_data, other.original_pdf_data)

        if not nopreview:
            self.update_preview()

        if dpi_conflict:
            # Finding 8: on a DPI conflict the compressed data was discarded and
            # no_compression set above. is_compressed must follow suit, otherwise
            # the node reports the contradictory combination
            # no_compression=True AND is_compressed=True.
            self.is_compressed = False
        else:
            self.is_compressed = self.is_compressed and other.is_compressed
        self.no_compression = self.no_compression or other.no_compression
        self.dpi_original = max(filter(None, [self.dpi_original, other.dpi_original]), default=None)
        # Only update dpi_current when there was no conflict.  In the conflict path
        # dpi_current was already set to None above and must stay None so that the
        # semantics remain consistent (no_compression=True AND dpi_current=None).
        if not dpi_conflict:
            self.dpi_current = max(filter(None, [self.dpi_current, other.dpi_current]), default=None)

        self.pdf_length = self._get_pdf_length(self.current_pdf_data)


    def commit_changes(self) -> None:
        """
        Speichert den aktuellen Zustand als neuen Originalzustand.
        Bei Ordnern wird rekursiv auf alle Kinder angewendet.
        """
        if self.is_folder:
            for child in self.children:
                child.commit_changes()
            return

        # Guard: ein leerer Knoten hat ggf. kein current_pdf_data — dann gibt es
        # nichts zu commiten (slicing None würde TypeError werfen).
        if self.current_pdf_data is None:
            return

        self.original_pdf_data = self.current_pdf_data[:]

        # Platzhalter-Vorschau nicht als Original übernehmen — sonst geht das
        # echte Original-Preview verloren, wenn gerade ein Preview-Task läuft.
        current_imgs = self.current_preview_images
        is_placeholder = (
            len(current_imgs) == 1
            and getattr(current_imgs[0], "_is_placeholder", False)
        )
        if not is_placeholder:
            self.original_preview_images = [img.copy() for img in current_imgs]

        self.pdf_length = self._get_pdf_length(self.original_pdf_data)

        self.current_pdf_data = None
        self.is_compressed = False
        self.no_compression = True

        if self.dpi_current:
            self.dpi_original = self.dpi_current
        self.dpi_current = None



    def reset_compression(self) -> None:
        if self.is_folder:
            for child in self.children:
                child.reset_compression()
            return

        self.current_pdf_data = None
        self.is_compressed = False
        self._current_preview_pages = []

        if not hasattr(self, "_original_preview_pages") or self._original_preview_pages is None:
            self._original_preview_pages = []

    def delete(self):
        """Entfernt diesen Knoten aus seinem Elternknoten (sofern vorhanden)."""
        if self.parent:
            self.parent.children = [c for c in self.parent.children if c != self]
            self.parent = None

    def _is_descendant_of(self, node: 'PDFNode') -> bool:
        current = self.parent
        while current:
            if current is node:
                return True
            current = current.parent
        return False

    def move(self, new_parent: 'PDFNode') -> None:
        if new_parent is self or new_parent._is_descendant_of(self):
            raise ValueError("Zyklische Einfügung nicht erlaubt.")

        if self.parent:
            self.parent.children = [c for c in self.parent.children if c != self]
        new_parent.add_child(self)

    def copy(self, keep_name: bool = False) -> 'PDFNode':
        """Erstellt eine Kopie des Knotens mit allen Kindknoten und eigenem Speicher."""
        copied = PDFNode(
            name=self.name if keep_name else f"{self.name}_copy",
            is_folder=self.is_folder,
            pdf_data=None
        )

        copied.status = self.status
        copied.vz_start = self.vz_start
        copied.vz_end = self.vz_end

        copied.current_pdf_data = self.current_pdf_data[:] if self.current_pdf_data else None
        copied.original_pdf_data = self.original_pdf_data[:] if self.original_pdf_data else None

        if self._preview_task_running or self._preview_task_requested:
            copied.preview_lazy()
        else:
            copied._current_preview_pages = [
                PreviewPage(p.pil_image.copy(), i) for i, p in enumerate(self._current_preview_pages)
            ]
            copied._original_preview_pages = [
                PreviewPage(p.pil_image.copy(), i) for i, p in enumerate(self._original_preview_pages)
            ]

        copied.pdf_length = self.pdf_length
        copied.is_compressed = self.is_compressed
        copied.no_compression = self.no_compression
        copied.dpi_original = self.dpi_original
        copied.dpi_current = self.dpi_current

        for child in self.children:
            copied.add_child(child.copy(keep_name=keep_name))

        return copied



    def _concat_children_data(self, attr: str) -> Optional[bytes]:
        """
        Hängt die PDF-Daten aller Child-Knoten zusammen (z. B. für Vorschau bei Ordnern).

        Args:
            attr: Name der Property ("current_pdf_data" oder "original_pdf_data").
                Bewusst die Property, nicht das private Attribut: so liefert jedes
                Kind seine effektiven Daten (current → original Fallback bei
                Blättern, rekursiv bei Unterordnern). Sonst entfielen noch nicht
                komprimierte Blätter, no_compression-Knoten und Unterordner.

        Returns:
            Zusammengefügte PDF-Daten oder None
        """
        writer = PdfWriter()
        for child in self.children:
            data = getattr(child, attr, None)
            if not isinstance(data, bytes):
                continue
            try:
                reader = PdfReader(io.BytesIO(data))
                for page in reader.pages:
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
            # Read each child's *property* (effective data), not the private
            # attribute: a leaf falls back current → original, a sub-folder
            # recurses. Reading "_current_pdf_data" directly would silently drop
            # not-yet-compressed leaves, no_compression nodes (e.g. split nodes)
            # and sub-folders, leaving the folder "invalid" / missing pages.
            return self._concat_children_data("current_pdf_data")
        return self._current_pdf_data or self._original_pdf_data

    @current_pdf_data.setter
    def current_pdf_data(self, value: Optional[bytes]):
        if self.is_folder:
            return
        self._current_pdf_data = value
        if value is None:
            self._current_preview_pages = []



    @property
    def original_pdf_data(self) -> Optional[bytes]:
        if self.is_folder:
            # Read the child property (recurses into sub-folders) rather than the
            # private attribute, which is never set on folder children.
            return self._concat_children_data("original_pdf_data")
        return self._original_pdf_data

    @original_pdf_data.setter
    def original_pdf_data(self, value: Optional[bytes]):
        if self.is_folder:
            return
        self._original_pdf_data = value

    
    @property
    def current_preview_images(self) -> List[Image.Image]:
        if self.is_folder:
            if self._cached_preview_images is None:
                self.preview_folder()
            return self._cached_preview_images or []

        if self._preview_task_running:
            from tools import PLACEHOLDER_PREVIEW
            return [PLACEHOLDER_PREVIEW]

        return [p.pil_image for p in self._current_preview_pages] or \
               [p.pil_image for p in self._original_preview_pages]


    @current_preview_images.setter
    def current_preview_images(self, images: List[Image.Image]):
        if self._current_pdf_data is None:
            # Kein echtes Current vorhanden → Anzeige erfolgt sowieso über Original
            self._current_preview_pages = []  # Vorschaubilder aktiv löschen
            return
        from preview_page import PreviewPage
        self._current_preview_pages = [
            PreviewPage(img, i) for i, img in enumerate(images)
        ]



    @property
    def original_preview_images(self) -> List[Image.Image]:
        if self.is_folder:
            images = []
            for child in self.children:
                images.extend(child.original_preview_images)
            return images

        if self._preview_task_running:
            from tools import PLACEHOLDER_PREVIEW
            return [PLACEHOLDER_PREVIEW]

        return [p.pil_image for p in self._original_preview_pages]
    

    @original_preview_images.setter
    def original_preview_images(self, images: List[Image.Image]):
        from preview_page import PreviewPage
        self._original_preview_pages = [
            PreviewPage(img, i) for i, img in enumerate(images)
        ]



    @classmethod
    def from_recursive_array(cls, name: str, structure: List[Dict[str, Any]]) -> 'PDFNode':
        """
        Erzeugt einen übergeordneten Ordnerknoten aus einer rekursiven Datenstruktur.

        Args:
            name: Name des Wurzelknotens (z. B. "ZIP-Inhalt", "E-Mail").
            structure: Liste aus Dictionaries mit "name", "content" oder "children".

        Returns:
            Ein PDFNode-Objekt mit is_folder=True und rekursiv aufgebauten Kindknoten.
        """
        root = cls(name=name, is_folder=True)

        for entry in structure:
            content = entry.get("content")
            if isinstance(content, io.BytesIO):
                entry["content"] = content.getvalue()

            node = cls._from_structure_entry(entry, parent=root)
            root.add_child(node)

        return root

    def set_original_and_current_data(
        self,
        original_data: Optional[bytes],
        current_data: Optional[bytes],
        dpi_original: Optional[int],
        dpi_current: Optional[int],
        no_compression: bool
    ) -> None:
        """Setzt Original- und Current-Daten, erzeugt Originalvorschau sofort, startet ggf. Lazy-Kompression."""
        if self.is_folder:
            return

        self.dpi_original = dpi_original
        self.dpi_current = dpi_current if current_data else None
        self.no_compression = no_compression
        self.current_pdf_data = current_data
        self.original_pdf_data = original_data

        # Vorschau für Original **immer** erzeugen
        try:
            preview = self._create_previews(original_data)
            if not preview:
                raise ValueError("Ungültige PDF-Daten: keine Vorschau erzeugt")
        except Exception as e:
            raise ValueError("Ungültige PDF-Daten") from e

        self._original_preview_pages = [
            PreviewPage(img, i) for i, img in enumerate(preview)
        ]
        self.pdf_length = self._get_pdf_length(original_data)

        should_lazy_compress = (
            original_data and
            current_data is None and
            dpi_original is None and
            dpi_current is None and
            not no_compression
        )

        if should_lazy_compress:
            self._current_preview_pages = []
            self.compress_multi_lazy()
        elif current_data:
            try:
                current_preview = self._create_previews(current_data)
                self._current_preview_pages = [
                    PreviewPage(img, i) for i, img in enumerate(current_preview)
                ]
                self.is_compressed = True  # ✅ Korrektur: komprimiert, weil current_data gesetzt
            except Exception:
                self._current_preview_pages = []

    @staticmethod
    def _from_structure_entry(entry: Dict[str, Any], parent: Optional['PDFNode'] = None) -> 'PDFNode':
        """
        Wandelt einen einzelnen Dictionary-Eintrag in einen PDFNode um (rekursiv bei children).

        Args:
            entry: Ein Dictionary mit mindestens "name", optional "content" oder "children".
            parent: Der übergeordnete PDFNode-Knoten.

        Returns:
            Ein vollständig verlinkter PDFNode (Blatt oder Ordner).
        """
        name = entry.get("name", "Unbenannt")

        if "children" in entry:
            # Ordnerknoten erzeugen
            node = PDFNode(name=name, is_folder=True)
            for child_entry in entry["children"]:
                child_node = PDFNode._from_structure_entry(child_entry, parent=node)
                node.add_child(child_node)
        else:
            # Blattknoten mit PDF-Inhalt (content kann auch None sein)
            content = entry.get("content")
            if isinstance(content, io.BytesIO):
                content = content.getvalue()
            node = PDFNode(name=name, is_folder=False, pdf_data=content)

        node.parent = parent
        return node

    def split(self) -> List['PDFNode']:
        """
        Zerteilt einen mehrseitigen PDF-Knoten oder einen Folder-Knoten.

        Bei PDFs: Der Knoten wird auf Seite 1 reduziert, weitere Seiten als Knoten zurückgegeben.
        Bei Foldern: Der Knoten behält das erste Kind, alle weiteren werden in neue Folder-Knoten gelegt.
        """
        if self.is_folder:
            return self._split_folder()
        return self._split_pdf()


    def _split_folder(self) -> List['PDFNode']:
        """
        Zerteilt einen Folder-Knoten in einzelne Folder-Knoten mit je einem Kind.
        Der aktuelle Knoten behält nur das erste Kind.
        """
        new_nodes: List[PDFNode] = []
        for i, child in enumerate(self.children[1:], start=1):
            new_node = PDFNode(name=f"{self.name}_split_{i}", is_folder=True)
            new_node.children.append(child)
            child.parent = new_node
            new_nodes.append(new_node)
        self.children = self.children[:1]
        return new_nodes


    def _split_pdf(self) -> List['PDFNode']:
        """
        Zerteilt einen PDF-Knoten in Einzelknoten pro Seite.
        Der aktuelle Knoten wird auf die erste Seite reduziert.

        Nebeneffekte (bewusst so gestaltet):
        - Jeder erzeugte Knoten (inkl. self nach der Rückwandlung) erhält
          ``no_compression=True``, weil die Scheiben bereits aus einem
          (ggf. komprimierten) Elternknoten stammen und nicht erneut
          gerendert werden sollen.
        - ``self`` wird in-place durch set_original_and_current_data mit den
          Daten der ersten Seite überschrieben.
        """
        if not self.original_pdf_data:
            return []

        try:
            reader_orig = PdfReader(io.BytesIO(self.original_pdf_data))
            reader_curr = PdfReader(io.BytesIO(self.current_pdf_data)) if self.current_pdf_data else None
        except Exception:
            return []

        if not self._preview_done.wait(timeout=30):
            logger.warning(
                "Split '%s': Vorschau-Event nicht innerhalb von 30 s abgeschlossen – "
                "fahre mit möglicherweise veralteter Vorschau fort.", self.name)

        new_nodes = []

        for i, page_orig in enumerate(reader_orig.pages):
            writer_orig = PdfWriter()
            writer_orig.add_page(page_orig)
            buf_orig = io.BytesIO()
            writer_orig.write(buf_orig)
            data_orig = buf_orig.getvalue()

            data_curr = None
            if reader_curr:
                try:
                    writer_curr = PdfWriter()
                    writer_curr.add_page(reader_curr.pages[i])
                    buf_curr = io.BytesIO()
                    writer_curr.write(buf_curr)
                    data_curr = buf_curr.getvalue()
                except Exception as e:
                    logger.debug("Split '%s' Seite %d: current-Daten nicht extrahierbar: %s",
                                 self.name, i + 1, e)
                    data_curr = None

            new_node = PDFNode(name=f"{self.name}_page_{i+1}")
            new_node.set_original_and_current_data(
                original_data=data_orig,
                current_data=data_curr,
                dpi_original=self.dpi_original,
                dpi_current=self.dpi_current if data_curr else None,
                no_compression=True
            )

            try:
                if i < len(self._original_preview_pages):
                    orig_page = self._original_preview_pages[i]
                    new_node._original_preview_pages = [PreviewPage(orig_page.pil_image.copy(), 0)]
                if data_curr and i < len(self._current_preview_pages):
                    curr_page = self._current_preview_pages[i]
                    new_node._current_preview_pages = [PreviewPage(curr_page.pil_image.copy(), 0)]
            except Exception as e:
                logger.debug("Split '%s' Seite %d: Vorschau-Übernahme fehlgeschlagen, "
                             "erzeuge neu: %s", self.name, i + 1, e)
                new_node.update_preview()

            new_nodes.append(new_node)

        if new_nodes:
            first = new_nodes[0]
            self.set_original_and_current_data(
                original_data=first.original_pdf_data,
                current_data=first._current_pdf_data,
                dpi_original=first.dpi_original,
                dpi_current=first.dpi_current,
                no_compression=True
            )
            self._original_preview_pages = first._original_preview_pages
            self._current_preview_pages = first._current_preview_pages
            return new_nodes[1:]

        return []
