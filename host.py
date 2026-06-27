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
import json
import os
import sys

import webview

from core.api import CoreApi
from infra.log_config import logger
from version_info import APP_NAME, get_full_title
from infra.window_geometry import geometry_visible


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
        import tempfile
        from core.api import sweep_stale_view_dirs
        sweep_stale_view_dirs()  # clean up beleg_view_* temp dirs stranded by a crash
        from pypdf import PdfWriter
        from formats import pdf_storage  # noqa: F401  (the big one: universal_importer/COM/pikepdf)
        from core.bridge import save_belegtool, load_belegtool
        from core.model import Document, Node
        from services.render import render_pdf_to_pngs   # PyMuPDF/fitz
        from formats.compress_pdf_bytes import compress_all_methods  # PIL/pikepdf

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
# BELEG_DEV mode loads the Vite dev server. webui runs bare `vite` (no --port), so
# this MUST track Vite's default 5173 — NOT the workspace-wide 5178 web-server port
# (that rule targets standalone servers; this is an embedded-SPA dev convenience).
# If webui's dev script ever pins a port, update this in the same change.
DEV_URL = "http://localhost:5173"
PROD_INDEX = os.path.join(HERE, "webui", "dist", "index.html")
PROD_PDFTOOL = os.path.join(HERE, "webui", "dist", "pdf-tool.html")  # the PDF-Tool surface
FILE_TYPES = ("BelegTool (*.belegtool)", "PDF (*.pdf)", "Alle Dateien (*.*)")


def _import_file_types():
    """Import-dialog filter, derived from the importer's ACTUAL supported set so newly
    supported formats (e.g. ODF .odt/.ods/.odp, legacy .doc/.xls/.ppt, .tif/.txt/.html)
    appear without hand-editing — the old hardcoded tuple silently omitted several.
    Imported lazily: universal_importer pulls in the heavy COM/Office/HEIC stack, which
    must stay off the startup path (see _prewarm)."""
    try:
        from universal_importer import UniversalImporter
        all_pattern = ";".join(f"*{e}" for e in UniversalImporter.get_supported_extensions())
        return (f"Unterstützte Dateien ({all_pattern})", "Alle Dateien (*.*)")
    except Exception:
        return ("Alle Dateien (*.*)",)


def _entry():
    return DEV_URL if os.environ.get("BELEG_DEV") else PROD_INDEX


def _entry_for_kind(kind):
    """Front-end surface for a launch target: 'pdf' (file) or 'node' → the PDF-Tool
    surface, anything else → the organizer. Dev serves both HTML entries off one Vite
    server; prod loads the built files (see docs/pdf-tool.md)."""
    if kind not in ("pdf", "node"):
        return _entry()
    return f"{DEV_URL}/pdf-tool.html" if os.environ.get("BELEG_DEV") else PROD_PDFTOOL


def _bind_close(win, api):
    """Per-window close guard: confirm before discarding unsaved changes. Uses the
    Python-side dirty flag the React app pushes via set_dirty — NOT evaluate_js,
    which hangs during window teardown (windows then wouldn't close). Return False
    cancels the close."""
    def _on_closing():
        try:
            if api._dirty and not win.create_confirmation_dialog(
                    "Ungespeicherte Änderungen",
                    "Das Fenster schließen und die ungespeicherten Änderungen verwerfen?"):
                return False  # user cancelled → keep the window open AND keep the lock
        except Exception:
            pass
        try:
            if api._pdftool_session:
                # node-bound PDF-Tool window: release the node lock + free the bound
                # session. (Save-back-on-close prompt is a deferred GUI item — see
                # docs/pdf-tool.md; closing currently discards unsaved pdf-tool edits.)
                api._core.close_pdftool(api._pdftool_session)
            if api._session:
                api._core.release(api._session)  # free the file lock for this window
                # free the session itself (document bytes, undo log, caches, temp view)
                api._core.close_session(api._session)
        except Exception:
            # still swallow — never block the window close — but TRACE it: a failed
            # release/close_session silently leaks the whole session otherwise.
            logger.exception("window close: release/close_session failed (session leaked)")
        return True
    win.events.closing += _on_closing


def _geom_file():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME, "window.json")


def _virtual_screen():
    """Windows virtual-desktop bounds (x, y, w, h) spanning all monitors; None elsewhere."""
    try:
        import ctypes
        gsm = ctypes.windll.user32.GetSystemMetrics
        return (gsm(76), gsm(77), gsm(78), gsm(79))  # SM_*VIRTUALSCREEN
    except Exception:
        return None


def _load_geometry():
    """The last saved geometry if it is still on-screen, else None (→ default)."""
    try:
        with open(_geom_file(), encoding="utf-8") as f:
            g = json.load(f)
        if geometry_visible(g, _virtual_screen()):
            return g
    except Exception:
        pass
    return None


def _save_geometry(win):
    """Persist the window's size + position so the next launch restores it (incl. monitor)."""
    try:
        g = {"x": int(win.x), "y": int(win.y),
             "width": int(win.width), "height": int(win.height)}
        path = _geom_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(g, f)
    except Exception:
        logger.debug("window geometry save skipped", exc_info=True)


def _open_window(core, startup_path=None, restore=False,
                 startup_kind="belegtool", startup_session=None):
    """Open a document window with its own HostApi (sharing one CoreApi — sessions
    are independent per window). Used for the first window and every 'new window'.
    ``startup_path`` (or ``startup_session`` for a node binding) is opened by the
    surface on load. ``startup_kind`` selects the surface: 'pdf'/'node' → the PDF-Tool,
    else the organizer. ``restore`` (first window only) re-applies the last saved
    geometry and saves it again on close, so the app remembers its size / position /
    monitor across launches."""
    api = HostApi(core)
    api._startup_path = startup_path
    api._startup_kind = startup_kind
    api._startup_session = startup_session
    api._pdftool_session = startup_session if startup_kind == "node" else None
    kwargs = dict(width=1280, height=820, min_size=(900, 600))
    geom = _load_geometry() if restore else None
    if geom:
        kwargs.update(width=int(geom["width"]), height=int(geom["height"]),
                      x=int(geom["x"]), y=int(geom["y"]))
    win = webview.create_window(
        get_full_title(), _entry_for_kind(startup_kind), js_api=api, **kwargs)  # title: "… 3.10.0"
    api._uid = win.uid  # bind after creation (storing the window object recurses)
    if restore:
        win.events.closing += lambda: _save_geometry(win)   # remember geometry on close
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
        self._startup_path = None  # file to open on load (first window only)
        self._startup_kind = "belegtool"  # 'belegtool' → organizer, 'pdf'/'node' → PDF-Tool
        self._startup_session = None  # a pre-bound session (node binding) the surface fetches
        self._pdftool_session = None  # a node-bound pdf-tool session to release on close
        self._session = None  # this window's session id (for the close-time lock release)

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

    def open_view_in_new_window(self, session, node_ids, name=None):
        """Materialise the currently displayed tag view (``node_ids``) as a temp
        .belegtool and open it in a fresh window — a real, editable copy of just the
        shown nodes, in normal tree order (grouping not applied). ``name`` becomes the
        new document's title (the used tag prefixed onto the old name)."""
        try:
            res = self._core.materialize_subset(session, node_ids, name)
            if not res.get("ok"):
                return res
            return _open_window(self._core, startup_path=res["path"])
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # core ops (delegate)
    def config(self):
        cfg = dict(self._core.config())
        if self._startup_path:
            cfg["startup_path"] = self._startup_path  # the surface opens this on load
            cfg["startup_kind"] = self._startup_kind  # 'belegtool' | 'pdf'
        if self._startup_session:
            cfg["startup_session"] = self._startup_session  # node binding: fetch its bytes
            cfg["startup_kind"] = self._startup_kind  # 'node'
        cfg["dev"] = bool(os.environ.get("BELEG_DEV"))  # gate dev-only UI (Testmodus)
        return cfg

    def get_pdf_bytes(self, session):
        """PDF bytes of a PDF-bound session (base64) for the PDF-Tool surface."""
        return self._core.get_pdf_bytes(session)

    # PDF-Tool node binding (docs/pdf-tool.md)
    def open_node_in_pdftool(self, session, node_id):
        """Lock a node and open it in a new PDF-Tool window bound to it."""
        try:
            res = self._core.open_node_in_pdftool(session, node_id)
            if not res.get("ok"):
                return res
            return _open_window(self._core, startup_kind="node", startup_session=res["session"])
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_node_back(self, pdftool_session, data_b64=None):
        return self._core.save_node_back(pdftool_session, data_b64)

    def break_node_binding(self, session, node_id):
        return self._core.break_node_binding(session, node_id)

    def open(self, session=None, path=None):
        resp = self._core.open(session, path)
        if resp.get("ok"):
            self._session = resp.get("session")  # remember for the close-time lock release
        return resp

    def dispatch(self, session, command):
        return self._core.dispatch(session, command)

    def undo(self, session):
        return self._core.undo(session)

    def redo(self, session):
        return self._core.redo(session)

    # (render/render_compressed bridge wrappers removed 2026-06-12 — the React UI
    # only uses the windowed variants below; CoreApi.render stays for the IPC
    # server, CoreApi.render_compressed for tests.)

    def compress_options(self, session, node_id, dpi=150):
        return self._core.compress_options(session, node_id, dpi)

    # windowed render cache
    def render_stats(self):
        return self._core.render_stats()

    def set_render_budget(self, mb):
        return self._core.set_render_budget(mb)

    def page_count(self, session, node_id):
        return self._core.page_count(session, node_id)

    def page_dims(self, session, node_id):
        return self._core.page_dims(session, node_id)

    def render_window(self, session, node_id, first=0, count=10, dpi=100):
        return self._core.render_window(session, node_id, first, count, dpi)

    def render_compressed_window(self, session, node_id, dpi=150, method=None, first=0, count=10):
        return self._core.render_compressed_window(session, node_id, dpi, method, first, count)

    # import (drop path uses bytes; the button uses the native dialog → real paths)
    def import_bytes(self, session, name, data, parent_id=None, index=None):
        return self._core.import_bytes(session, name, data, parent_id, index)

    def export_dialog(self, session, node_ids=None, options=None):
        win = self._win()
        if win is None:
            return {"ok": False, "error": "Fenster nicht gefunden"}
        name = (self._core.document_name(session) or "Export").strip() or "Export"
        path = win.create_file_dialog(
            webview.FileDialog.SAVE, save_filename=f"{name}.pdf", file_types=("PDF (*.pdf)",))
        if not path:
            return {"ok": False, "error": "cancelled"}
        if isinstance(path, (tuple, list)):
            path = path[0]
        result = self._core.export(session, path, node_ids, options)
        # #13: a split would overwrite existing "_Teil_N" files (the native Save dialog
        # only confirmed the base name) — confirm the ACTUAL part files before clobbering.
        if not result.get("ok") and result.get("code") == "exists":
            names = "\n".join(os.path.basename(p) for p in result.get("existing", []))
            if not win.create_confirmation_dialog(
                    "Dateien überschreiben?",
                    "Diese Dateien existieren bereits und werden überschrieben:\n" + names):
                return {"ok": False, "error": "cancelled"}
            opts = dict(options or {})
            opts["overwrite"] = True
            result = self._core.export(session, path, node_ids, opts)
        return result

    def import_dialog(self, session, parent_id=None):
        win = self._win()
        if win is None:
            return {"ok": False, "error": "Fenster nicht gefunden"}
        result = win.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True, file_types=_import_file_types())
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

    def save_info(self, session):
        return self._core.save_info(session)

    def save_file(self, session, store_alternatives=True):
        """Save in place if this document already has a path; otherwise prompt once.
        ``store_alternatives`` False → 'Original speichern' (don't embed variants)."""
        path = self._core.document_path(session)
        if path:
            return self._core.save(session, path, store_alternatives)
        return self.save_file_as(session, store_alternatives)

    def save_file_as(self, session, store_alternatives=True):
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
        return self._core.save(session, path, store_alternatives)

    # --- DATEV mode (lazy; ops delegate to CoreApi, dialogs run on this window) ---
    def datev_status(self):
        return self._core.datev_status()

    def set_datev_mode(self, on):
        return self._core.set_datev_mode(on)

    def save_to_datev(self, session):
        """Ask „nach DATEV zurückschreiben?" then perform the guarded write-back. Returns
        the verdict so the React app can explain a non-ok result and offer a local save.
        Cancelling the prompt is reported as ``declined`` (→ the UI does a normal save)."""
        win = self._win()
        if win is None:
            return {"ok": False, "error": "Fenster nicht gefunden"}
        if not win.create_confirmation_dialog(
                "Nach DATEV zurückschreiben?",
                "Die Änderungen in das verknüpfte DATEV-Dokument zurückschreiben?\n"
                "(DATEV Dokumentenablage behält keine Revision — der alte Stand wird "
                "überschrieben; eine lokale Sicherung wird vorher angelegt.)"):
            return {"ok": False, "verdict": "declined"}
        return self._core.datev_save_back(session, confirmed=True)

    def datev_file(self, session, client_guid=None, mandant_number=None, description=None,
                   domain_id=1, folder_id=None, register_id=None):
        return self._core.datev_file(session, client_guid=client_guid,
                                     mandant_number=mandant_number, description=description,
                                     domain_id=domain_id, folder_id=folder_id,
                                     register_id=register_id)

    def datev_export(self, session, node_ids=None, options=None, client_guid=None,
                     mandant_number=None, description=None, domain_id=1, folder_id=None,
                     register_id=None):
        return self._core.datev_export(session, node_ids=node_ids, options=options,
                                       client_guid=client_guid, mandant_number=mandant_number,
                                       description=description, domain_id=domain_id,
                                       folder_id=folder_id, register_id=register_id)


def _safe_http_port():
    """An OS-assigned free ephemeral port (>=49152) for pywebview's internal file
    server. Chromium/WebView2 hard-blocks a set of "unsafe" ports (1719, 1720, …);
    if pywebview's random pick lands on one the page fails with ERR_UNSAFE_PORT.
    Ephemeral ports are never on that block list, so we hand one in explicitly."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


_WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
# Evergreen WebView2 Runtime registration GUID (also where the Win11 in-box runtime registers).
_WEBVIEW2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def _webview2_installed() -> bool:
    """True if the Edge WebView2 Runtime is present. Without it the React UI renders
    blank (pywebview can't use the Chromium backend). Non-Windows: assume present."""
    if sys.platform != "win32":
        return True
    import winreg
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_GUID}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_GUID}"),
        (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_GUID}"),
    ]
    for root, path in keys:
        try:
            with winreg.OpenKey(root, path) as k:
                pv = winreg.QueryValueEx(k, "pv")[0]
                if pv and pv != "0.0.0.0":
                    return True
        except OSError:
            continue
    return False


def _warn_missing_webview2():
    """Tell the user plainly (native dialog + open the download page) instead of showing
    a blank window when the WebView2 Runtime is missing."""
    msg = ("Microsoft Edge WebView2 Runtime fehlt.\n\n"
           "BelegTool benötigt die WebView2-Runtime — sonst bleibt das Fenster leer.\n"
           "Bitte installieren und BelegTool neu starten:\n" + _WEBVIEW2_URL)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "BelegTool – WebView2 erforderlich", 0x10)
    except Exception:
        print(msg)
    try:
        import webbrowser
        webbrowser.open(_WEBVIEW2_URL)
    except Exception:
        pass


def _is_clr_load_error(exc) -> bool:
    """A pythonnet/.NET assembly that failed to load — almost always because Windows
    flagged the downloaded files with the 'Mark of the Web' and .NET refuses to load
    the (signed) Python.Runtime.dll. Not antivirus, and the DLL is present."""
    s = str(exc).lower()
    return ("python.runtime" in s or "pythonnet" in s
            or "loader.initialize" in s or "clr_loader" in s)


def _warn_clr_load_failed(exc):
    """Explain the Mark-of-the-Web block + how to unblock, instead of a raw traceback."""
    msg = (".NET-Komponente konnte nicht geladen werden.\n\n"
           "Das passiert meist, weil Windows die heruntergeladenen Dateien als "
           "'aus dem Internet' markiert hat (Mark of the Web) und .NET das Laden "
           "blockiert — das ist NICHT der Virenscanner.\n\n"
           "Lösung – die Dateien entsperren:\n"
           "• Am besten VOR dem Entpacken: Rechtsklick auf die ZIP → Eigenschaften → "
           "unten 'Zulassen' (bzw. 'Blockierung aufheben') anhaken → OK → dann entpacken.\n"
           "• Schon entpackt (PowerShell im BelegTool-Ordner):\n"
           "    Get-ChildItem -Recurse . | Unblock-File\n\n"
           f"Technische Meldung: {exc}")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "BelegTool – Dateien entsperren", 0x10)
    except Exception:
        print(msg)


def main(startup_target=None):
    # Fail loudly, not blank: without the WebView2 Runtime the window renders empty.
    # (BELEG_SKIP_WEBVIEW2_CHECK=1 bypasses, in case detection ever false-negatives.)
    skip = os.environ.get("BELEG_SKIP_WEBVIEW2_CHECK", "").lower() not in ("", "0", "false", "no")
    if not skip and not _webview2_installed():
        _warn_missing_webview2()
        return
    core = CoreApi()  # shared across all windows; sessions are per window
    # The first window remembers its geometry (size / position / monitor across launches).
    if startup_target:
        _open_window(core, startup_target["path"], restore=True,
                     startup_kind=startup_target["kind"])
    else:
        _open_window(core, restore=True)
    # Warm up only AFTER the window is up (start's func runs on its own thread once
    # the GUI loop is live), so warming doesn't compete with window creation.
    # Pin a safe http port so the file server never lands on a Chromium-blocked one.
    try:
        webview.start(_prewarm, http_port=_safe_http_port())
    except Exception as e:
        # pythonnet/.NET failing to load is almost always Mark-of-the-Web on a
        # downloaded build — give a clear unblock hint, not a cryptic traceback.
        if sys.platform == "win32" and _is_clr_load_error(e):
            # log the real exception too — the dialog may be the user's only view of it
            logger.exception("pythonnet/.NET load failed (likely Mark-of-the-Web)")
            _warn_clr_load_failed(e)
            return
        raise


def _startup_target_from_argv(argv):
    """A document handed on the command line (file association / 'open with' /
    BelegTool.exe <file>): a .belegtool opens the organizer; a .pdf opens the
    PDF-Tool bound to that file (see docs/pdf-tool.md). Returns
    ``{'path': str, 'kind': 'belegtool'|'pdf'}`` or None when there is nothing
    valid to open."""
    if len(argv) < 2:
        return None
    path = argv[1]
    if not os.path.isfile(path):
        return None
    low = path.lower()
    if low.endswith(".belegtool"):
        return {"path": path, "kind": "belegtool"}
    if low.endswith(".pdf"):
        return {"path": path, "kind": "pdf"}
    return None


if __name__ == "__main__":
    main(_startup_target_from_argv(sys.argv))
