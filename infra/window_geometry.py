"""Pure helpers for persisting the main window's geometry (remember size / position /
monitor across launches). The file I/O and the OS virtual-screen query live in
``host.py``; this module holds the validation that a saved geometry is still usable —
so a window saved on a now-disconnected monitor falls back to the default instead of
opening off-screen.
"""

_MIN_W, _MIN_H = 400, 300
_MAX_W, _MAX_H = 20000, 20000


def valid_geometry(g) -> bool:
    """True if ``g`` is a dict with sane integer ``x``/``y``/``width``/``height``."""
    if not isinstance(g, dict):
        return False
    try:
        w, h = int(g["width"]), int(g["height"])
        int(g["x"])
        int(g["y"])
    except (KeyError, TypeError, ValueError):
        return False
    return _MIN_W <= w <= _MAX_W and _MIN_H <= h <= _MAX_H


def geometry_visible(g, virtual_screen, margin: int = 120, top_bar: int = 40) -> bool:
    """True if a usable slice of the window's title bar lands inside the virtual desktop.

    ``virtual_screen`` is ``(x, y, w, h)`` spanning all monitors, or ``None`` when it
    can't be queried (then a valid geometry is trusted). ``margin`` px of the title bar
    must be horizontally on-screen and its top within the desktop — this rejects a
    geometry whose monitor is gone (the saved x/y would be off the current desktop).
    """
    if not valid_geometry(g):
        return False
    if virtual_screen is None:
        return True
    vx, vy, vw, vh = virtual_screen
    x, y, w = int(g["x"]), int(g["y"]), int(g["width"])
    horizontal = (x + w) >= (vx + margin) and x <= (vx + vw - margin)
    vertical = vy <= y <= (vy + vh - top_bar)
    return horizontal and vertical
