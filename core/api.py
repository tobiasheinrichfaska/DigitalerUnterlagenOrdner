"""In-process façade over the data-driven core.

JSON-able request/response, managing one ``DocumentSession`` per open document
(window). Used **directly** by the pywebview host (the single warm process) and,
via a thin transport, by the named-pipe server — so both share one implementation.

Every method returns a dict with ``ok: bool``; success carries ``session``,
``tree`` (Document JSON), ``can_undo``, ``can_redo``; failure carries ``error``.
"""

from __future__ import annotations

import threading
import uuid

from core import CORE_VERSION
from core.bridge import load_belegtool
from core.commands import CommandError, command_from_dict
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
        return {"ok": True, "session": session, "path": path}

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
