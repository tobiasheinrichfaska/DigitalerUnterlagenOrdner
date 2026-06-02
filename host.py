"""pywebview host — the single warm process for the React UI.

Embeds the data-driven core (core.api.CoreApi) and exposes it to the React app as
``window.pywebview.api.*``. HostApi adds the methods that need the native window
(open/save file dialogs); everything else delegates to CoreApi. One Python
process; the React build is just static assets.

Run:
  - dev:  cd webui && npm run dev ; then  set BELEG_DEV=1 ; python host.py
  - prod: cd webui && npm run build ; then  python host.py
"""

import io
import os
import sys

import webview

from core.api import CoreApi
from log_config import logger
from version_info import APP_NAME


def _prewarm():
    """Warm the load/render/compress path in the background so the first real
    open/render doesn't pay the cold-import cost. Runs on a daemon thread at
    startup, concurrent with the user looking at the window / picking a file.

    Deliberately does NOT touch universal_importer (win32com/COM, extract-msg,
    pillow-heif): that ~2.6 s cost is only needed to *import* Office/email/archive/
    HEIC files, so it stays lazy and loads on first such import, not at startup.
    Best-effort; never blocks startup.
    """
    try:
        import os
        import tempfile
        from pypdf import PdfWriter
        import pdf_storage  # noqa: F401  (the big one: universal_importer/COM/pikepdf)
        from core.bridge import save_belegtool, load_belegtool
        from core.model import Document, Node
        from services.render import render_pdf_to_pngs   # PyMuPDF/fitz
        from compress_pdf_bytes import compress_all_methods  # PIL/pikepdf

        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        buf = io.BytesIO()
        writer.write(buf)
        tiny = buf.getvalue()

        doc = Document(Node(name="root", is_folder=True, children=(
            Node(name="w", pdf_length=1, original_data=tiny),)))
        path = os.path.join(tempfile.gettempdir(), "_belegtool_warm.belegtool")
        save_belegtool(doc, path)           # warm the save path
        load_belegtool(path)                # warm the parse/slice load path
        render_pdf_to_pngs(tiny)            # warm the fitz render path
        compress_all_methods(tiny, dpi=72)  # warm the PIL/pikepdf compress path
        try:
            os.remove(path)
        except Exception:
            pass
    except Exception:
        # best-effort; never block startup — but log so a broken import path
        # (missing DLL, library drift) is diagnosable instead of silently slow.
        logger.exception("prewarm failed")

# Frozen (PyInstaller onedir): data files live under sys._MEIPASS, not next to
# this module (which is packed into the archive). Dev: resolve from the source.
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
DEV_URL = "http://localhost:5173"
PROD_INDEX = os.path.join(HERE, "webui", "dist", "index.html")
FILE_TYPES = ("BelegTool (*.belegtool)", "PDF (*.pdf)", "Alle Dateien (*.*)")
IMPORT_FILE_TYPES = (
    "Unterstützte Dateien (*.pdf;*.belegtool;*.jpg;*.jpeg;*.png;*.webp;*.heic;"
    "*.docx;*.xlsx;*.pptx;*.zip;*.tar;*.eml;*.msg)",
    "Alle Dateien (*.*)",
)


def _entry():
    return DEV_URL if os.environ.get("BELEG_DEV") else PROD_INDEX


def _bind_close(win, api):
    """Per-window close guard: confirm before discarding unsaved changes. Uses the
    Python-side dirty flag the React app pushes via set_dirty — NOT evaluate_js,
    which hangs during window teardown (windows then wouldn't close). Return False
    cancels the close."""
    def _on_closing():
        try:
            if api._dirty:
                return bool(win.create_confirmation_dialog(
                    "Ungespeicherte Änderungen",
                    "Es gibt ungespeicherte Änderungen. Trotzdem schließen und verwerfen?"))
        except Exception:
            pass
        return True
    win.events.closing += _on_closing


def _open_window(core, startup_path=None):
    """Open a document window with its own HostApi (sharing one CoreApi — sessions
    are independent per window). Used for the first window and every 'new window'.
    ``startup_path`` (only the first window) is a .belegtool the React app opens on
    load — used when the legacy GUI hands a document over via 'open in new GUI'."""
    api = HostApi(core)
    api._startup_path = startup_path
    win = webview.create_window(
        APP_NAME, _entry(), js_api=api,
        width=1280, height=820, min_size=(900, 600))
    api._uid = win.uid  # bind after creation (storing the window object recurses)
    _bind_close(win, api)
    return {"ok": True}


class HostApi:
    """JS-facing API for one window: shared CoreApi ops + native dialogs on *this*
    window. One HostApi per window; it stores only the window's uid (storing the
    window object makes pywebview recurse when it serialises js_api)."""

    def __init__(self, core, uid=None):
        self._core = core
        self._uid = uid
        self._dirty = False  # pushed from the React app for the close guard
        self._startup_path = None  # .belegtool to open on load (first window only)

    def set_dirty(self, value):
        self._dirty = bool(value)
        return {"ok": True}

    def _win(self):
        # this window only — never fall back to windows[0], or a dialog could open
        # against the wrong document if this window was closed mid-call.
        for w in webview.windows:
            if w.uid == self._uid:
                return w
        return None

    # window management
    def new_window(self):
        try:
            return _open_window(self._core)
        except Exception as e:  # never crash the caller
            return {"ok": False, "error": str(e)}

    # core ops (delegate)
    def config(self):
        cfg = dict(self._core.config())
        if self._startup_path:
            cfg["startup_path"] = self._startup_path  # React opens this on load
        return cfg

    def open(self, session=None, path=None):
        return self._core.open(session, path)

    def dispatch(self, session, command):
        return self._core.dispatch(session, command)

    def undo(self, session):
        return self._core.undo(session)

    def redo(self, session):
        return self._core.redo(session)

    def render(self, session, node_id, dpi=100):
        return self._core.render(session, node_id, dpi)

    def render_compressed(self, session, node_id, dpi=150, method=None):
        return self._core.render_compressed(session, node_id, dpi, method)

    def compress_options(self, session, node_id, dpi=150):
        return self._core.compress_options(session, node_id, dpi)

    def test_mode(self, dpi=60, max_pages=3):
        return self._core.test_mode(dpi, max_pages)

    # windowed render cache
    def page_count(self, session, node_id):
        return self._core.page_count(session, node_id)

    def page_dims(self, session, node_id):
        return self._core.page_dims(session, node_id)

    def render_window(self, session, node_id, first=0, count=10, dpi=100):
        return self._core.render_window(session, node_id, first, count, dpi)

    # import (drop path uses bytes; the button uses the native dialog → real paths)
    def import_bytes(self, session, name, data, parent_id=None, index=None):
        return self._core.import_bytes(session, name, data, parent_id, index)

    def export_dialog(self, session, node_ids=None):
        win = self._win()
        if win is None:
            return {"ok": False, "error": "Fenster nicht gefunden"}
        path = win.create_file_dialog(
            webview.FileDialog.SAVE, save_filename="Export.pdf", file_types=("PDF (*.pdf)",))
        if not path:
            return {"ok": False, "error": "cancelled"}
        if isinstance(path, (tuple, list)):
            path = path[0]
        return self._core.export(session, path, node_ids)

    def import_dialog(self, session, parent_id=None):
        win = self._win()
        if win is None:
            return {"ok": False, "error": "Fenster nicht gefunden"}
        result = win.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True, file_types=IMPORT_FILE_TYPES)
        if not result:
            return {"ok": False, "error": "cancelled"}
        return self._core.import_paths(session, list(result), parent_id)

    # host-only ops (native dialogs)
    def open_file(self, session=None):
        win = self._win()
        if win is None:
            return {"ok": False, "error": "Fenster nicht gefunden"}
        result = win.create_file_dialog(webview.FileDialog.OPEN, file_types=FILE_TYPES)
        if not result:
            return {"ok": False, "error": "cancelled"}
        return self._core.open(session, result[0])

    def save_file(self, session):
        win = self._win()
        if win is None:
            return {"ok": False, "error": "Fenster nicht gefunden"}
        name = self._core.document_name(session) or "unbenannt"
        path = win.create_file_dialog(
            webview.FileDialog.SAVE, save_filename=f"{name}.belegtool",
            file_types=("BelegTool (*.belegtool)",))
        if not path:
            return {"ok": False, "error": "cancelled"}
        if isinstance(path, (tuple, list)):
            path = path[0]
        return self._core.save(session, path)


def main(startup_path=None):
    core = CoreApi()  # shared across all windows; sessions are per window
    _open_window(core, startup_path)
    # Warm up only AFTER the window is up (start's func runs on its own thread once
    # the GUI loop is live), so warming doesn't compete with window creation.
    webview.start(_prewarm)


if __name__ == "__main__":
    main()
