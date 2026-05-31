"""The core server: accepts multiple pipe clients and dispatches requests.

Step 0a scope — plumbing only:
  - ``hello``                  -> new session id
  - ``open`` {path?}           -> session id + tree JSON (or null tree if no path)
Each connection is independent and gets its own session; the server handles many
connections at once (one per UI window / CLI client) on one process.

Request/response are JSON objects framed by core.protocol. Every response carries
``ok: bool``; on failure also ``error: str``.
"""

import threading
import uuid

import win32file
import pywintypes

from core import CORE_VERSION
from core.pipe import PipeConnection, connect, create_server_instance, default_pipe_name
from pdf_storage import PDFStorage
from log_config import logger


class SessionManager:
    """Tracks per-connection sessions (one open document each, for now)."""

    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        sid = uuid.uuid4().hex
        with self._lock:
            self._sessions[sid] = {"storage": None}
        return sid

    def ensure(self, sid):
        if sid and sid in self._sessions:
            return sid
        return self.create()

    def open(self, sid: str, path):
        """Open a .belegtool/PDF into the session; return its tree dict (or None)."""
        sid = self.ensure(sid)
        if not path:
            return sid, None
        storage = PDFStorage(path)
        with self._lock:
            self._sessions[sid]["storage"] = storage
        return sid, storage.root.to_dict()

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)


class CoreServer:
    def __init__(self, pipe_name: str = None):
        self.pipe_name = pipe_name or default_pipe_name()
        self.sessions = SessionManager()
        self._running = False
        self._accept_thread = None

    # --- lifecycle ---------------------------------------------------------
    def start(self):
        self._running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        logger.info("CoreServer listening on %s", self.pipe_name)

    def stop(self):
        self._running = False
        # Unblock the accept loop's ConnectNamedPipe by connecting once.
        try:
            connect(self.pipe_name, timeout=1.0).close()
        except Exception:
            pass
        if self._accept_thread:
            self._accept_thread.join(timeout=2.0)

    # --- accept / serve ----------------------------------------------------
    def _accept_loop(self):
        while self._running:
            try:
                handle = create_server_instance(self.pipe_name)
            except pywintypes.error as e:
                logger.error("CreateNamedPipe failed: %s", e)
                break
            try:
                win32pipe_connect(handle)
            except pywintypes.error:
                _close(handle)
                continue
            if not self._running:
                _close(handle)
                break
            conn = PipeConnection(handle)
            threading.Thread(target=self._serve_connection, args=(conn,), daemon=True).start()

    def _serve_connection(self, conn: PipeConnection):
        try:
            while self._running:
                req = conn.recv()
                if req is None:
                    break  # client disconnected
                conn.send(self._dispatch(req))
        except Exception as e:
            logger.warning("Verbindung beendet: %s", e)
        finally:
            conn.close()

    # --- dispatch ----------------------------------------------------------
    def _dispatch(self, req: dict) -> dict:
        op = req.get("op")
        try:
            if op == "hello":
                return {"ok": True, "session": self.sessions.create(),
                        "core_version": CORE_VERSION}
            if op == "open":
                sid, tree = self.sessions.open(req.get("session"), req.get("path"))
                return {"ok": True, "session": sid, "tree": tree}
            return {"ok": False, "error": f"unknown op: {op!r}"}
        except Exception as e:
            logger.exception("Dispatch-Fehler bei op=%r", op)
            return {"ok": False, "error": str(e)}


def win32pipe_connect(handle):
    import win32pipe
    win32pipe.ConnectNamedPipe(handle, None)


def _close(handle):
    try:
        win32file.CloseHandle(handle)
    except Exception:
        pass
