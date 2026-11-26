"""PDF rasterizer port + the pdfium backend (the ONLY place that rasterizes).

Replaces PyMuPDF/fitz (AGPL/Artifex) with ``pypdfium2`` (BSD-3-Clause / Apache-2.0, bundled pdfium).
Pure: no host imports. Callers (``belegtool_compress.compress``, the host's ``services.render``) only
see this small interface::

    with raster.open_pdf(raw) as doc:          # one parse, many pages
        doc.page_count                          # int
        doc.page_size(i)                        # (w, h) in points, as displayed (rotation/CropBox/UserUnit)
        doc.render(i, dpi, gray=False)          # PIL image, white background, annotations + form fields drawn

Measured parity with PyMuPDF and the decisions behind the details below: ``docs/pdfium-spike.md``.

* **Thread safety.** pdfium is NOT thread safe. Every pdfium call (open, size, render, close) runs under one
  process-wide ``PriorityLock``. Foreground requests (an interactive preview page) overtake queued background
  work (prefetch fill, compression), so an interactive page waits for at most ONE running render. A plain
  ``threading.Lock`` measured 5x the single-page latency under 4 background threads; the priority lock ~1.8x.
  Consequence: the background pools give fairness, not parallelism (they were GIL-bound under PyMuPDF too).
* **/UserUnit** is ignored by pdfium but honoured by MuPDF/Acrobat: the scale is multiplied by it here.
* **Greyscale** is rendered as RGB and converted with Pillow (``"L"``, ITU-R 601 luminance); pdfium's native
  grayscale flag matched PyMuPDF worse. (MuPDF's own ``csGRAY`` brightens saturated colours - pure red 129
  instead of luminance 76 - so colour stamps in the grey ``jpg``/``png`` variants come out slightly darker.)
* Backend selection: environment variable ``BELEG_RASTER`` (default ``pdfium``). Other backends (the
  PyMuPDF test oracle) register themselves via ``register_backend`` and are never imported by production code.
"""

import io
import logging
import os
import threading
from typing import Callable, Dict, Optional, Tuple

from PIL import Image

from belegtool_compress import cpu

logger = logging.getLogger("belegtool_compress")

# Hard ceiling for ONE bitmap the backend itself will allocate (defence in depth; the callers clamp the DPI to
# ``pixels.MAX_RENDER_PIXELS`` = 64 MP first, so this only trips on a caller that forgot to).
MAX_BITMAP_PIXELS = 256_000_000


class RasterError(Exception):
    """The PDF could not be opened/rendered (damaged, password protected, absurd size)."""


# --------------------------------------------------------------------------- the process-wide lock

class PriorityLock:
    """Mutual exclusion with foreground priority: a background acquirer waits while any foreground
    acquirer is queued; otherwise first come, first served (by the OS condition variable)."""

    def __init__(self):
        self._cv = threading.Condition(threading.Lock())
        self._busy = False
        self._fg_waiting = 0

    def acquire(self, background: bool = False) -> None:
        with self._cv:
            if not background:
                self._fg_waiting += 1
            try:
                while self._busy or (background and self._fg_waiting):
                    self._cv.wait()
            finally:
                if not background:
                    self._fg_waiting -= 1
            self._busy = True

    def release(self) -> None:
        with self._cv:
            self._busy = False
            self._cv.notify_all()


PDFIUM_LOCK = PriorityLock()


# --------------------------------------------------------------------------- /UserUnit (per document, once)

_UU_LOCK = threading.Lock()
_UU_CACHE: list = []  # [(raw, units)] newest last; holds a strong ref so ``is`` identity can't be recycled
_UU_MAX = 4


def _user_units(raw: bytes) -> Tuple[float, ...]:
    """Per-page /UserUnit (1.0 when absent). Costs a pikepdf parse only for documents that contain the
    literal ``UserUnit`` or object streams (where a page dict may hide); looked up once per bytes object."""
    with _UU_LOCK:
        for cached_raw, units in _UU_CACHE:
            if cached_raw is raw:
                return units
    units: Tuple[float, ...] = ()
    if b"UserUnit" in raw or b"ObjStm" in raw:
        try:
            import pikepdf
            with pikepdf.open(io.BytesIO(raw), suppress_warnings=True) as pdf:
                units = tuple(_unit_of(p.obj) for p in pdf.pages)
        except Exception:
            units = ()
    if all(u == 1.0 for u in units):
        units = ()
    with _UU_LOCK:
        _UU_CACHE.append((raw, units))
        del _UU_CACHE[:-_UU_MAX]
    return units


def _unit_of(page_obj) -> float:
    try:
        u = float(page_obj.get("/UserUnit", 1.0))
    except Exception:
        return 1.0
    return u if u > 0 else 1.0


# --------------------------------------------------------------------------- pdfium backend

def _pdfium():
    try:
        import pypdfium2
    except ImportError as e:  # pragma: no cover
        raise RasterError("pypdfium2 ist nicht installiert") from e
    return pypdfium2


class _PdfiumSession:
    def __init__(self, raw: bytes, background: Optional[bool]):
        self._bg = cpu.is_background_thread() if background is None else bool(background)
        self._raw = raw
        self._units = _user_units(raw) if raw else ()
        self._pdf = None
        pdfium = _pdfium()
        PDFIUM_LOCK.acquire(self._bg)
        try:
            try:
                self._pdf = pdfium.PdfDocument(raw)
                try:  # form fields only draw when the form environment exists; documents without forms: no-op
                    self._pdf.init_forms()
                except Exception:
                    pass
                self._count = len(self._pdf)
            except Exception as e:
                self._close_locked()
                raise RasterError(f"PDF konnte nicht geöffnet werden: {e}") from e
        finally:
            PDFIUM_LOCK.release()

    # -- helpers
    def _unit(self, index: int) -> float:
        return self._units[index] if index < len(self._units) else 1.0

    def _check(self, index: int) -> None:
        if self._pdf is None:
            raise RasterError("Dokument ist geschlossen")
        if not 0 <= index < self._count:
            raise IndexError(f"Seite {index} außerhalb 0..{self._count - 1}")

    def _close_locked(self) -> None:
        pdf, self._pdf = self._pdf, None
        if pdf is not None:
            try:
                pdf.close()
            except Exception:  # pragma: no cover
                pass

    # -- port
    @property
    def page_count(self) -> int:
        return self._count if self._pdf is not None else 0

    def page_size(self, index: int) -> Tuple[float, float]:
        self._check(index)
        PDFIUM_LOCK.acquire(self._bg)
        try:
            page = self._pdf[index]
            try:
                w, h = page.get_size()
            finally:
                page.close()
        except Exception as e:
            raise RasterError(f"Seitengröße nicht lesbar: {e}") from e
        finally:
            PDFIUM_LOCK.release()
        u = self._unit(index)
        return (w * u, h * u)

    def render(self, index: int, dpi: float, gray: bool = False) -> Image.Image:
        self._check(index)
        scale = dpi * self._unit(index) / 72.0
        PDFIUM_LOCK.acquire(self._bg)
        try:
            page = self._pdf[index]
            try:
                w, h = page.get_size()
                if (w * scale) * (h * scale) > MAX_BITMAP_PIXELS:
                    raise RasterError(f"Seite {index} bei {dpi:g} DPI zu groß "
                                      f"({w * scale:.0f}x{h * scale:.0f} px)")
                bitmap = page.render(scale=scale, rotation=0, grayscale=False,
                                     fill_color=(255, 255, 255, 255),
                                     may_draw_forms=True, draw_annots=True)
                img = bitmap.to_pil()
                img.load()
            finally:
                page.close()
        except RasterError:
            raise
        except Exception as e:
            raise RasterError(f"Seite {index} nicht renderbar: {e}") from e
        finally:
            PDFIUM_LOCK.release()
        return img.convert("L" if gray else "RGB")

    def close(self) -> None:
        if self._pdf is None:
            return
        PDFIUM_LOCK.acquire(self._bg)
        try:
            self._close_locked()
        finally:
            PDFIUM_LOCK.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class PdfiumBackend:
    """Production backend: pypdfium2 (BSD-3/Apache-2.0) under the process-wide ``PDFIUM_LOCK``."""
    name = "pdfium"

    def open(self, raw: bytes, background: Optional[bool] = None) -> _PdfiumSession:
        return _PdfiumSession(raw, background)


# --------------------------------------------------------------------------- selection

_FACTORIES: Dict[str, Callable[[], object]] = {"pdfium": PdfiumBackend}


def register_backend(name: str, factory: Callable[[], object]) -> None:
    """Make ``BELEG_RASTER=<name>`` selectable (used by the PyMuPDF test oracle; not by production)."""
    _FACTORIES[name.strip().lower()] = factory


def get_backend(name: Optional[str] = None):
    """The backend named by ``name`` / ``BELEG_RASTER`` (default ``pdfium``; unknown names fall back)."""
    wanted = (name or os.environ.get("BELEG_RASTER", "") or "pdfium").strip().lower()
    factory = _FACTORIES.get(wanted)
    if factory is None:
        logger.warning("Unbekanntes Raster-Backend %r - verwende pdfium.", wanted)
        factory = _FACTORIES["pdfium"]
    return factory()


def open_pdf(raw: bytes, background: Optional[bool] = None):
    """Open ``raw`` with the selected backend. Raises ``RasterError`` for unusable input."""
    if not raw:
        raise RasterError("leeres PDF")
    return get_backend().open(raw, background)
