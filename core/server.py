"""The core server: accepts multiple pipe clients and dispatches requests.

Each connection gets its own editing session (an immutable Document + undo/redo).
The server handles many connections at once (one per UI window / CLI client).

Ops:
  - ``hello``                       -> new session id
  - ``open`` {path?}                -> document JSON (empty doc if no path)
  - ``dispatch`` {session, command} -> new document JSON (+ undo/redo flags)
  - ``undo`` / ``redo`` {session}   -> document JSON

Request/response are JSON objects framed by core.protocol. Every response carries
``ok: bool``; on failure also ``error: str``.
"""

import threading
import uuid

import win32file
import pywintypes

from core import CORE_VERSION
from core.bridge import load_belegtool
from core.commands import CommandError, command_from_dict
from core.engine import RealEngine
from core.model import Document
from core.pipe import PipeConnection, connect, create_server_instance, default_pipe_name
from core.session import DocumentSession
from log_config import logger


class SessionManager:
    """Tracks per-connection editing sessions (one DocumentSession each)."""

    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()
        self._engine = RealEngine()

    def create(self) -> str:
        sid = uuid.uuid4().hex
        with self._lock:
            self._sessions[sid] = DocumentSession(Document.empty(), engine=self._engine)
        return sid

    def ensure(self, sid: str) -> str:
        with self._lock:
            if sid and sid in self._sessions:
                return sid
        return self.create()

    def get(self, sid: str):
        with self._lock:
            return self._sessions.get(sid)

    def open(self, sid: str, path):
        """Load a .belegtool/PDF (or an empty doc) into the session."""
        sid = self.ensure(sid)
        document = load_belegtool(path) if path else Document.empty()
        session = DocumentSession(document, engine=self._engine)
        with self._lock:
            self._sessions[sid] = session
        return sid, session

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
                sid, session = self.sessions.open(req.get("session"), req.get("path"))
                return self._doc_response(sid, session)

            if op in ("dispatch", "undo", "redo"):
                sid = req.get("session")
                session = self.sessions.get(sid)
                if session is None:
                    return {"ok": False, "error": "unknown session"}
                if op == "dispatch":
                    session.dispatch(command_from_dict(req["command"]))
                elif op == "undo":
                    session.undo()
                else:
                    session.redo()
                return self._doc_response(sid, session)

            return {"ok": False, "error": f"unknown op: {op!r}"}
        except CommandError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            logger.exception("Dispatch-Fehler bei op=%r", op)
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _doc_response(sid: str, session) -> dict:
        return {
            "ok": True,
            "session": sid,
            "tree": session.document.to_dict(),
            "can_undo": session.can_undo(),
            "can_redo": session.can_redo(),
        }


def win32pipe_connect(handle):
    import win32pipe
    win32pipe.ConnectNamedPipe(handle, None)


def _close(handle):
    try:
        win32file.CloseHandle(handle)
    except Exception:
        pass
