"""Per-page pixel budget for rasterization (pure; no host imports).

A hostile/oversized MediaBox (up to 200x200 in) would otherwise make ``get_pixmap`` allocate GBs.
~64 MP = ~192 MB RGB - far above any legitimate page at compression DPI, so normal renders are
never affected. (The host's preview renderer keeps its own copy of this tiny function.)
"""

import logging
import math

logger = logging.getLogger("belegtool_compress")

MAX_RENDER_PIXELS = 64_000_000


def capped_dpi(page, dpi: int) -> int:
    """Clamp ``dpi`` down so the page renders within MAX_RENDER_PIXELS."""
    rect = page.rect
    px = (rect.width * dpi / 72.0) * (rect.height * dpi / 72.0)
    if px <= MAX_RENDER_PIXELS or px <= 0:
        return dpi
    capped = max(1, int(dpi * math.sqrt(MAX_RENDER_PIXELS / px)))
    logger.warning("Übergroße Seite (%.0f×%.0f pt) – DPI von %d auf %d begrenzt.",
                   rect.width, rect.height, dpi, capped)
    return capped
