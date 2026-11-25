"""Cheap, non-rasterizing PDF facts (page count, page sizes) via pikepdf.

Replaces the former PyMuPDF (``fitz``) uses that never rendered anything. Pure: no host
imports, no rendering. ``page_dims`` reproduces how a viewer sizes a page — inherited
page-tree attributes, CropBox∩MediaBox, /Rotate (snapped to 0/90/180/270) and /UserUnit —
including the defaults a tolerant reader (MuPDF) falls back to for a missing or empty box
(US Letter, 612x792 pt), so callers see the same numbers as before the swap.
"""

import io
from typing import List, Optional, Tuple, Union

import pikepdf

_DEFAULT_BOX = (0.0, 0.0, 612.0, 792.0)  # US Letter, what MuPDF assumes without a usable box
_MAX_PARENT_DEPTH = 64                   # page-tree depth guard against /Parent cycles
_MAX_BOX = 1e9                           # sanity bound: absurd/non-finite boxes are "unusable"


def _raw(data) -> Optional[bytes]:
    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if hasattr(data, "getvalue"):
        return data.getvalue()
    return None


def _open(raw: bytes):
    return pikepdf.open(io.BytesIO(raw), suppress_warnings=True)


def page_count(data: Union[bytes, io.BytesIO, None]) -> int:
    """Number of pages; 0 for empty/unreadable input."""
    raw = _raw(data)
    if not raw:
        return 0
    try:
        with _open(raw) as pdf:
            return len(pdf.pages)
    except Exception:
        return 0


def _inherited(page_obj, key: str):
    obj = page_obj
    for _ in range(_MAX_PARENT_DEPTH):
        if obj is None:
            return None
        try:
            if key in obj:
                return obj[key]
            obj = obj.get("/Parent")
        except Exception:
            return None
    return None


def _num(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _box(arr) -> Optional[Tuple[float, float, float, float]]:
    """Normalised (x0, y0, x1, y1) of a PDF rectangle array, ``None`` if not an array."""
    if arr is None:
        return None
    try:
        vals = [_num(arr[i]) for i in range(4)]
    except Exception:
        return None
    x0, y0, x1, y1 = vals
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _usable(b) -> bool:
    return (b is not None and b[0] < b[2] and b[1] < b[3]
            and all(abs(v) <= _MAX_BOX for v in b))


def _page_size(page_obj) -> Tuple[float, float]:
    media = _box(_inherited(page_obj, "/MediaBox"))
    if not _usable(media):
        media = _DEFAULT_BOX
    crop_obj = _inherited(page_obj, "/CropBox")
    if crop_obj is not None:
        crop = _box(crop_obj)
        if crop is not None:
            crop = (max(media[0], crop[0]), max(media[1], crop[1]),
                    min(media[2], crop[2]), min(media[3], crop[3]))
    else:
        crop = media
    if not _usable(crop):
        crop = _DEFAULT_BOX
    w, h = crop[2] - crop[0], crop[3] - crop[1]

    try:
        unit = _num(page_obj.get("/UserUnit"))
    except Exception:
        unit = 0.0
    if unit > 0:
        w, h = w * unit, h * unit

    try:
        rot = int(_num(_inherited(page_obj, "/Rotate")))
    except Exception:
        rot = 0
    if rot < 0:
        rot = 360 - ((-rot) % 360)
    if rot >= 360:
        rot %= 360
    rot = 90 * ((rot + 45) // 90)
    if rot >= 360:
        rot = 0
    if rot in (90, 270):
        w, h = h, w
    return (w, h)


def page_dims(data: Union[bytes, io.BytesIO, None]) -> List[Tuple[float, float]]:
    """``(width, height)`` in points for every page (as displayed: rotation applied)."""
    raw = _raw(data)
    if not raw:
        return []
    try:
        with _open(raw) as pdf:
            return [_page_size(p.obj) for p in pdf.pages]
    except Exception:
        return []
