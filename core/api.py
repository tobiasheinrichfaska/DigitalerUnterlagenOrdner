"""In-process façade over the data-driven core.

JSON-able request/response, managing one ``DocumentSession`` per open document
(window). Used **directly** by the pywebview host (the single warm process) and,
via a thin transport, by the named-pipe server — so both share one implementation.

Every method returns a dict with ``ok: bool``; success carries ``session``,
``tree`` (Document JSON), ``can_undo``, ``can_redo``; failure carries ``error``.
"""

from __future__ import annotations

import os
import threading
import uuid

from core import CORE_VERSION
from core.bridge import load_belegtool
from core.commands import (
    DEFAULT_COMPRESSION_DPI,
    CommandError,
    command_from_dict,
)
from core.engine import RealEngine
from core.model import Document
from core.session import DocumentSession
from log_config import logger


class CoreApi:
    def __init__(self, engine=None):
        self._engine = engine or RealEngine()
        self._sessions = {}
        self._lock = threading.Lock()

    # --- ops ---------------------------------------------------------------
    def config(self) -> dict:
        """Fixed core defaults the UI should use instead of hardcoding its own."""
        return {"ok": True, "default_dpi": DEFAULT_COMPRESSION_DPI}

    def hello(self) -> dict:
        with self._lock:
            sid = self._new_locked(Document.empty())
        return {"ok": True, "session": sid, "core_version": CORE_VERSION}

    def open(self, session: str = None, path: str = None) -> dict:
        document = load_belegtool(path) if path else Document.empty()
        with self._lock:
            if session and session in self._sessions:
                sid = session
                self._sessions[sid] = DocumentSession(document, engine=self._engine)
            else:
                sid = self._new_locked(document)
            return self._doc_response_locked(sid)

    def dispatch(self, session: str, command: dict) -> dict:
        return self._mutate(session, lambda s: s.dispatch(command_from_dict(command)))

    def undo(self, session: str) -> dict:
        return self._mutate(session, lambda s: s.undo())

    def redo(self, session: str) -> dict:
        return self._mutate(session, lambda s: s.redo())

    def render(self, session: str, node_id: str, dpi: int = 100) -> dict:
        """Render a leaf node's effective pages to base64 PNG data-URLs."""
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            node = s.document.find(node_id)
            if node is None:
                return {"ok": False, "error": f"node not found: {node_id}"}
            data = node.current_data or node.original_data
        # render outside the lock (CPU-bound); folders carry no bytes -> []
        from base64 import b64encode
        from services.render import render_pdf_to_pngs
        pages = [
            "data:image/png;base64," + b64encode(p).decode("ascii")
            for p in render_pdf_to_pngs(data, dpi=dpi)
        ]
        return {"ok": True, "session": session, "node": node_id, "pages": pages}

    def render_compressed(self, session: str, node_id: str,
                          dpi: int = DEFAULT_COMPRESSION_DPI, method: str = None) -> dict:
        """Render a *transient* compressed preview of a leaf — compress its
        original bytes with ``method`` at ``dpi`` and rasterise the result, WITHOUT
        mutating the document. Powers the working-preview UI: browse methods/DPI
        with no undo entry; the document only changes on an explicit Compress.
        Falls back to the original bytes if the method yields no gain / no_compression.
        """
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            node = s.document.find(node_id)
            if node is None:
                return {"ok": False, "error": f"node not found: {node_id}"}
            data = node.original_data
            no_comp = node.no_compression
        if not data:
            return {"ok": True, "session": session, "node": node_id, "pages": [], "compressed": False}
        # compress + render outside the lock (CPU-bound); never stored back.
        # "original"/None → render the original bytes directly (no compression run).
        if no_comp or not method or method == "original":
            compressed = None
        else:
            compressed = self._engine.compress(data, dpi, method)
        effective = compressed if compressed is not None else data
        from base64 import b64encode
        from services.render import render_pdf_to_pngs
        pages = [
            "data:image/png;base64," + b64encode(p).decode("ascii")
            for p in render_pdf_to_pngs(effective)
        ]
        return {"ok": True, "session": session, "node": node_id,
                "pages": pages, "compressed": compressed is not None}

    def save(self, session: str, path: str) -> dict:
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            document = s.document
        from core.bridge import save_belegtool
        try:
            save_belegtool(document, path)
        except Exception as e:
            logger.exception("save failed")
            return {"ok": False, "error": str(e)}
        with self._lock:
            s = self._sessions.get(session)
            if s is not None:
                s.mark_saved()
        return {"ok": True, "session": session, "path": path}

    def any_dirty(self) -> bool:
        """True if any open session has unsaved changes (for the close prompt)."""
        with self._lock:
            return any(s.dirty for s in self._sessions.values())

    def compress_options(self, session: str, node_id: str, dpi: int = 150) -> dict:
        """Available compression methods for a leaf at ``dpi`` (smallest first)."""
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            node = s.document.find(node_id)
            if node is None:
                return {"ok": False, "error": f"node not found: {node_id}"}
            data = node.original_data
        if not data:
            return {"ok": True, "session": session, "node": node_id, "dpi": dpi,
                    "original_size": 0, "options": []}
        sizes = self._engine.compress_methods(data, dpi)
        options = sorted(
            ({"method": m, "size": sz} for m, sz in sizes.items()),
            key=lambda o: o["size"],
        )
        return {"ok": True, "session": session, "node": node_id, "dpi": dpi,
                "original_size": len(data), "options": options}

    # --- import ------------------------------------------------------------
    def _import_path(self, path: str) -> list:
        """Import one file from disk into immutable Node(s) — mirrors the Tk import:
        .belegtool/PDF/zip/tar/email via PDFStorage, everything else (images,
        Office, …) via UniversalImporter. Heavy; call outside the lock."""
        from core.bridge import node_from_pdfnode
        low = path.lower()
        if low.endswith(".belegtool"):
            return list(load_belegtool(path).root.children)
        if low.endswith((".pdf", ".zip", ".tar", ".tgz", ".tar.gz", ".eml", ".msg")):
            from pdf_storage import PDFStorage, create_wrapper_node
            storage = PDFStorage(path, generate_previews=False)
            return [node_from_pdfnode(create_wrapper_node(storage, path))]
        from pdf_node import PDFNode
        from universal_importer import UniversalImporter
        result = UniversalImporter.convert(path)  # images / Office / …
        data = result.data.getvalue() if hasattr(result.data, "getvalue") else result.data
        pn = PDFNode(name=result.name)
        pn.set_original_and_current_data(data, None, None, None, False, generate_preview=False)
        return [node_from_pdfnode(pn)]

    def import_paths(self, session: str, paths, parent_id: str = None, index: int = None) -> dict:
        """Import real file paths (from the native dialog) under a folder (or root),
        optionally at a position (index) within that folder."""
        from core.commands import InsertNodes
        nodes, errors = [], []
        for path in paths:
            try:
                nodes.extend(self._import_path(path))
            except Exception as e:
                logger.exception("import failed: %s", path)
                errors.append(f"{os.path.basename(path)}: {e}")
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            if not nodes:
                return {"ok": False, "error": "; ".join(errors) or "nichts importiert"}
            node = s.document.find(parent_id) if parent_id else None
            target = parent_id if (node is not None and node.is_folder) else s.document.root.id
            try:
                s.dispatch(InsertNodes(parent_id=target, nodes=tuple(nodes), index=index))
            except CommandError as e:
                return {"ok": False, "error": str(e)}
            resp = self._doc_response_locked(session)
        if errors:
            resp["warning"] = "; ".join(errors)
        return resp

    def import_bytes(self, session: str, name: str, data_b64: str, parent_id: str = None, index: int = None) -> dict:
        """Import a single dropped file given as base64 / data-URL — written to a
        temp file (keeping its name) so the path pipeline (and COM) handle it."""
        import base64
        import shutil
        import tempfile
        try:
            data = base64.b64decode((data_b64 or "").split(",")[-1])
        except Exception as e:
            return {"ok": False, "error": f"ungültige Daten: {e}"}
        tmpdir = tempfile.mkdtemp(prefix="beleg_import_")
        path = os.path.join(tmpdir, os.path.basename(name) or "import.bin")
        try:
            with open(path, "wb") as f:
                f.write(data)
            return self.import_paths(session, [path], parent_id, index)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    # --- internals ---------------------------------------------------------
    def _new_locked(self, document: Document) -> str:
        sid = uuid.uuid4().hex
        self._sessions[sid] = DocumentSession(document, engine=self._engine)
        return sid

    def _mutate(self, session: str, action) -> dict:
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            try:
                action(s)
            except CommandError as e:
                return {"ok": False, "error": str(e)}
            except Exception as e:  # defensive — never crash the host
                logger.exception("CoreApi op failed")
                return {"ok": False, "error": str(e)}
            return self._doc_response_locked(session)

    def _doc_response_locked(self, sid: str) -> dict:
        s = self._sessions[sid]
        return {
            "ok": True,
            "session": sid,
            "tree": s.document.to_dict(),
            "can_undo": s.can_undo(),
            "can_redo": s.can_redo(),
        }
