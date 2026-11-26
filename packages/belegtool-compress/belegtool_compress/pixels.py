# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Per-page pixel budget for rasterization (pure; no host imports).

A hostile/oversized MediaBox (up to 200x200 in) would otherwise make the rasterizer allocate GBs.
~64 MP = ~192 MB RGB - far above any legitimate page at compression DPI, so normal renders are
never affected. (The host's preview renderer keeps its own copy of this tiny function.)
"""

import logging
import math

logger = logging.getLogger("belegtool_compress")

MAX_RENDER_PIXELS = 64_000_000


def capped_dpi_for_size(width_pt: float, height_pt: float, dpi: int) -> int:
    """Clamp ``dpi`` down so a ``width_pt`` x ``height_pt`` page renders within MAX_RENDER_PIXELS."""
    px = (width_pt * dpi / 72.0) * (height_pt * dpi / 72.0)
    if px <= MAX_RENDER_PIXELS or px <= 0:
        return dpi
    capped = max(1, int(dpi * math.sqrt(MAX_RENDER_PIXELS / px)))
    logger.warning("Übergroße Seite (%.0f×%.0f pt) – DPI von %d auf %d begrenzt.",
                   width_pt, height_pt, dpi, capped)
    return capped


def capped_dpi(page, dpi: int) -> int:
    """Same for an object with ``.rect.width/.height`` (kept for existing callers)."""
    return capped_dpi_for_size(page.rect.width, page.rect.height, dpi)
