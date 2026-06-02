"""Test mode (Testmodus) — headless golden-master comparison data.

Runs each golden-master operation (compression, split, merge) and produces, per
item, three PDFs side by side:

    INPUT (fixture)  |  LIVE (op run now)  |  EXPECTED (tests/data/expected)

so live-vs-golden drift is visible. This module is **pure / headless**: it
returns PDF bytes + a status, no rendering and no UI. The pywebview host renders
thumbnails (``CoreApi.test_mode``) and the React ``TestMode`` view displays them.

The live computations deliberately mirror the corresponding tests
(test_pdf_node_compression / _split / _merge_files) so that, with unchanged
code, LIVE == EXPECTED byte-for-byte.

Named ``testmode`` (no ``test_`` prefix) so pytest does not auto-collect it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from log_config import logger
from pdf_node import PDFNode

TEST_DATA_DIR = Path(__file__).parent / "tests" / "data"
INPUT_DIR = TEST_DATA_DIR / "input"
EXPECTED_DIR = TEST_DATA_DIR / "expected"

# Status values for a single comparison row.
STATUS_MATCH = "match"              # live == expected
STATUS_DIFFER = "differ"            # live != expected
STATUS_NO_EXPECTED = "no-expected"  # reference not yet adopted
STATUS_NO_LIVE = "no-live"          # the operation produced nothing


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
