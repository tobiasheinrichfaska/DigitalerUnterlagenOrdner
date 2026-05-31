"""Test mode: side-by-side review of golden-master datasets.

Activated from the GUI (Ansicht -> Testmodus). For each golden-master operation
(compression, split, merge) it shows three columns per item:

    INPUT          |  LIVE result        |  EXPECTED reference
    (the fixture)  |  (op run right now)  |  (tests/data/expected)

so that live-vs-golden drift is visible at a glance.

The data layer (``build_all_datasets`` and the per-operation builders) is pure
and headless-testable; the Tk widgets live in ``TestModeView`` further down and
import lazily so this module can be used without a display.

The live computations deliberately mirror the corresponding tests
(test_pdf_node_compression / _split / _merge_files) so that, with unchanged
code, LIVE == EXPECTED byte-for-byte.
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import fitz

from pdf_node import PDFNode
from log_config import logger

TEST_DATA_DIR = Path(__file__).parent / "tests" / "data"
INPUT_DIR = TEST_DATA_DIR / "input"
EXPECTED_DIR = TEST_DATA_DIR / "expected"


# --------------------------------------------------------------------------- #
# Data layer (pure / headless-testable)
# --------------------------------------------------------------------------- #

# Status values for a single comparison row.
STATUS_MATCH = "match"            # live == expected
STATUS_DIFFER = "differ"          # live != expected
STATUS_NO_EXPECTED = "no-expected"  # reference not yet adopted
STATUS_NO_LIVE = "no-live"        # the operation produced nothing


@dataclass
class ComparisonItem:
    """One reviewable artifact: an input next to its live and expected result."""
    label: str
    input_pdf: Optional[bytes]
    live_pdf: Optional[bytes]
    expected_pdf: Optional[bytes]

    @property
    def status(self) -> str:
        if self.live_pdf is None:
            return STATUS_NO_LIVE
        if self.expected_pdf is None:
            return STATUS_NO_EXPECTED
        return STATUS_MATCH if self.live_pdf == self.expected_pdf else STATUS_DIFFER


@dataclass
class Dataset:
    name: str
    description: str
    items: List[ComparisonItem] = field(default_factory=list)
    error: Optional[str] = None


def fixtures_available() -> bool:
    """True if the input fixtures the golden-master ops need are present."""
    required = ("compress_sample.pdf", "split_sample.pdf", "merge1_a.pdf", "merge1_b.pdf")
    return INPUT_DIR.is_dir() and all((INPUT_DIR / n).exists() for n in required)


def _read_optional(path: Path) -> Optional[bytes]:
    return path.read_bytes() if path.exists() else None


def _wait_until(predicate: Callable[[], bool], timeout: float = 20.0,
                interval: float = 0.05) -> bool:
    """Block until ``predicate()`` is true or ``timeout`` seconds elapse."""
    start = time.time()
    while not predicate():
        if time.time() - start > timeout:
            return False
        time.sleep(interval)
    return True


def build_compression_dataset() -> Dataset:
    """Mirror test_pdf_node_compression: from_pdf -> background multi-compress."""
    ds = Dataset("Kompression", "compress_sample.pdf -> komprimiert (DPI 120, beste Methode)")
    src = INPUT_DIR / "compress_sample.pdf"
    if not src.exists():
        ds.error = f"Eingabedatei fehlt: {src.name}"
        return ds

    input_bytes = src.read_bytes()
    node = PDFNode.from_pdf(name=src.name, source=input_bytes)
    # Constructor starts compress_multi_lazy(120) in the background; wait for the
    # compressed result to materialise (mirrors wait_for_real_preview).
    if not _wait_until(lambda: node._current_pdf_data is not None and node.dpi_current is not None):
        logger.warning("Testmodus: Kompression von %s nicht rechtzeitig fertig", src.name)
    live = node._current_pdf_data
    expected = _read_optional(EXPECTED_DIR / "compress_sample_compressed.pdf")
    ds.items.append(ComparisonItem(src.name, input_bytes, live, expected))
    return ds


def build_split_dataset() -> Dataset:
    """Mirror test_pdf_node_split: split into one node per page."""
    ds = Dataset("Splitten", "split_sample.pdf -> ein Knoten pro Seite")
    src = INPUT_DIR / "split_sample.pdf"
    if not src.exists():
        ds.error = f"Eingabedatei fehlt: {src.name}"
        return ds

    input_bytes = src.read_bytes()
    node = PDFNode.from_pdf(src.name, input_bytes)
    split_nodes = node.split()
    all_nodes = [node] + split_nodes
    for i, n in enumerate(all_nodes, start=1):
        n.no_compression = True
        n.current_pdf_data = None  # fall back to the original page
        n.dpi_current = None
        n.update_preview()
        live = n.current_pdf_data
        expected = _read_optional(EXPECTED_DIR / f"split_{src.stem}_{i:02}.pdf")
        ds.items.append(ComparisonItem(f"Seite {i}", live, live, expected))
    return ds


def build_merge_dataset() -> Dataset:
    """Mirror test_pdf_node_merge_files: concatenate merge1_a + merge1_b."""
    ds = Dataset("Zusammenführen", "merge1_a.pdf + merge1_b.pdf -> merge1")
    parts = [INPUT_DIR / "merge1_a.pdf", INPUT_DIR / "merge1_b.pdf"]
    if not all(p.exists() for p in parts):
        ds.error = "Eingabedateien merge1_a.pdf / merge1_b.pdf fehlen"
        return ds

    nodes = []
    for p in parts:
        n = PDFNode(name=p.name, pdf_data=None)
        n.no_compression = True
        n.set_original_and_current_data(
            original_data=p.read_bytes(), current_data=None,
            dpi_original=None, dpi_current=None, no_compression=True,
        )
        nodes.append(n)

    base = nodes[0]
    for other in nodes[1:]:
        base.merge(other, nopreview=True)

    live = base.current_pdf_data
    expected = _read_optional(EXPECTED_DIR / "merge1.pdf")
    # Show both source PDFs as the "input" reference plus the merged result.
    ds.items.append(ComparisonItem("merge1_a.pdf", parts[0].read_bytes(), None, None))
    ds.items.append(ComparisonItem("merge1_b.pdf", parts[1].read_bytes(), None, None))
    ds.items.append(ComparisonItem("merge1 (Ergebnis)", live, live, expected))
    return ds


def build_all_datasets() -> List[Dataset]:
    """Run every golden-master operation and collect the comparison data."""
    builders = (build_compression_dataset, build_split_dataset, build_merge_dataset)
    datasets = []
    for build in builders:
        try:
            datasets.append(build())
        except Exception as e:  # one broken dataset must not kill the whole view
            logger.error("Testmodus: Dataset-Aufbau fehlgeschlagen: %s", e)
            ds = Dataset(build.__name__, "")
            ds.error = str(e)
            datasets.append(ds)
    return datasets


# --------------------------------------------------------------------------- #
# Rendering helper (PDF bytes -> thumbnails)
# --------------------------------------------------------------------------- #

def render_thumbnails(data: Optional[bytes], dpi: int = 60, max_pages: int = 3,
                      max_width: int = 230):
    """Render up to ``max_pages`` pages of ``data`` to PIL images (scaled).

    Returns an empty list for missing/invalid data so callers can show a
    placeholder.
    """
    from PIL import Image

    if not data:
        return []
    images = []
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        logger.warning("Testmodus: Vorschau fehlgeschlagen: %s", e)
        return []
    try:
        for page_index in range(min(len(doc), max_pages)):
            pix = doc.load_page(page_index).get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("ppm"))).convert("RGB")
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)))
            images.append(img)
    finally:
        doc.close()
    return images


# --------------------------------------------------------------------------- #
# Tk view
# --------------------------------------------------------------------------- #

STATUS_STYLE = {
    STATUS_MATCH:       ("✓ stimmt mit Referenz überein", "#1a7f37"),
    STATUS_DIFFER:      ("✗ weicht von Referenz ab",       "#cf222e"),
    STATUS_NO_EXPECTED: ("⚠ keine Referenz (noch nicht übernommen)", "#9a6700"),
    STATUS_NO_LIVE:     ("–", "#57606a"),
}


def _build_tk():
    import tkinter as tk
    from tkinter import ttk
    from PIL import ImageTk
    return tk, ttk, ImageTk


class TestModeView:
    """Wraps a scrollable Frame showing the input/live/expected comparison.

    Instantiated lazily by the GUI. Construct with a parent widget, then call
    ``frame`` to embed it. ``refresh()`` rebuilds the datasets.
    """

    COLS = ("Input", "Live", "Erwartet (Referenz)")

    def __init__(self, parent):
        tk, ttk, _ = _build_tk()
        self._tk, self._ttk = tk, ttk
        self._image_refs = []  # keep ImageTk refs alive

        self.frame = ttk.Frame(parent)
        self._canvas = tk.Canvas(self.frame, bg="white", highlightthickness=0)
        vbar = ttk.Scrollbar(self.frame, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = ttk.Frame(self._canvas)
        self._win = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",
                         lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Enter>", lambda e: self._canvas.bind_all("<MouseWheel>", self._on_wheel))
        self._canvas.bind("<Leave>", lambda e: self._canvas.unbind_all("<MouseWheel>"))

    def _on_wheel(self, event):
        self._canvas.yview_scroll(int(-event.delta / 120), "units")

    def refresh(self):
        """(Re)compute the datasets and render them."""
        for child in self._inner.winfo_children():
            child.destroy()
        self._image_refs.clear()

        ttk = self._ttk
        if not fixtures_available():
            ttk.Label(
                self._inner, padding=20, foreground="#cf222e",
                text=("Testdaten nicht gefunden unter tests/data/input/.\n"
                      "Bitte zuerst  python tests/make_fixtures.py  ausführen."),
            ).pack(anchor="nw")
            return

        for ds in build_all_datasets():
            self._render_dataset(ds)

    def _render_dataset(self, ds: Dataset):
        tk, ttk, ImageTk = self._tk, self._ttk, _build_tk()[2]

        header = ttk.Frame(self._inner, padding=(8, 12, 8, 4))
        header.pack(fill="x", anchor="nw")
        ttk.Label(header, text=ds.name, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(header, text=ds.description, foreground="#57606a").pack(anchor="w")

        if ds.error:
            ttk.Label(self._inner, padding=(16, 2), foreground="#cf222e",
                      text=f"Fehler: {ds.error}").pack(anchor="nw")
            return

        for item in ds.items:
            row = ttk.Frame(self._inner, padding=(16, 4), relief="groove", borderwidth=1)
            row.pack(fill="x", anchor="nw", padx=8, pady=3)

            label_text, color = STATUS_STYLE[item.status]
            top = ttk.Frame(row)
            top.pack(fill="x")
            ttk.Label(top, text=item.label, font=("Segoe UI", 10, "bold")).pack(side="left")
            ttk.Label(top, text=label_text, foreground=color).pack(side="right")

            cols = ttk.Frame(row)
            cols.pack(fill="x", pady=(4, 0))
            for col_index, (title, data) in enumerate((
                (self.COLS[0], item.input_pdf),
                (self.COLS[1], item.live_pdf),
                (self.COLS[2], item.expected_pdf),
            )):
                cell = ttk.Frame(cols, padding=4)
                cell.grid(row=0, column=col_index, sticky="nw", padx=4)
                ttk.Label(cell, text=title, foreground="#57606a").pack(anchor="w")
                images = render_thumbnails(data)
                if not images:
                    ttk.Label(cell, text="(keine Daten)", foreground="#8c959f").pack(anchor="w")
                for img in images:
                    photo = ImageTk.PhotoImage(img)
                    self._image_refs.append(photo)
                    tk.Label(cell, image=photo, borderwidth=1, relief="solid").pack(anchor="w", pady=2)
