"""PyMuPDF as a raster backend - TEST ORACLE ONLY (never imported by production code; PyMuPDF is AGPL/Artifex
and lives in requirements-dev). Importing this module registers it as ``BELEG_RASTER=pymupdf``."""

import io
import warnings

warnings.filterwarnings("ignore", message=".*fitz.*deprecated.*", category=FutureWarning)
import fitz  # noqa: E402
from PIL import Image  # noqa: E402

from belegtool_compress import raster  # noqa: E402


class _FitzSession:
    def __init__(self, raw):
        try:
            self._doc = fitz.open(stream=raw, filetype="pdf")
        except Exception as e:
            raise raster.RasterError(str(e)) from e

    @property
    def page_count(self):
        return self._doc.page_count

    def page_size(self, index):
        r = self._doc[index].rect
        return (r.width, r.height)

    def render(self, index, dpi, gray=False):
        if not 0 <= index < self._doc.page_count:
            raise IndexError(index)
        pix = self._doc[index].get_pixmap(dpi=int(dpi), colorspace=fitz.csRGB)
        img = Image.open(io.BytesIO(pix.tobytes("ppm"))).convert("RGB")
        # luminance oracle: MuPDF's own csGRAY brightens saturated colours (docs/pdfium-spike.md)
        return img.convert("L") if gray else img

    def close(self):
        self._doc.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class FitzBackend:
    name = "pymupdf"

    def open(self, raw, background=None):
        return _FitzSession(raw)


raster.register_backend("pymupdf", FitzBackend)
