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

import win32file
import pywintypes

from core.api import CoreApi
from core.pipe import PipeConnection, connect, create_server_instance, default_pipe_name
from log_config import logger


class CoreServer:
    """Named-pipe transport over a shared :class:`core.api.CoreApi`."""

    def __init__(self, pipe_name: str = None):
        self.pipe_name = pipe_name or default_pipe_name()
        self.api = CoreApi()
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

    # --- dispatch (maps pipe ops onto the shared CoreApi) ------------------
    def _dispatch(self, req: dict) -> dict:
        op = req.get("op")
        if op == "hello":
            return self.api.hello()
        if op == "open":
            return self.api.open(req.get("session"), req.get("path"))
        if op == "dispatch":
            return self.api.dispatch(req.get("session"), req.get("command"))
        if op == "undo":
            return self.api.undo(req.get("session"))
        if op == "redo":
            return self.api.redo(req.get("session"))
        return {"ok": False, "error": f"unknown op: {op!r}"}


def win32pipe_connect(handle):
    import win32pipe
    win32pipe.ConnectNamedPipe(handle, None)


def _close(handle):
    try:
        win32file.CloseHandle(handle)
    except Exception:
        pass
