"""Thin client for the core service (used by the CLI and tests)."""

from core.pipe import connect, default_pipe_name


class CoreClient:
    def __init__(self, pipe_name: str = None, timeout: float = 5.0):
        self._conn = connect(pipe_name or default_pipe_name(), timeout=timeout)

    def request(self, obj: dict) -> dict:
        self._conn.send(obj)
        return self._conn.recv()

    def hello(self) -> dict:
        return self.request({"op": "hello"})

    def open(self, path: str = None, session: str = None) -> dict:
        req = {"op": "open"}
        if path:
            req["path"] = path
        if session:
            req["session"] = session
        return self.request(req)

    def dispatch(self, command: dict, session: str) -> dict:
        return self.request({"op": "dispatch", "session": session, "command": command})

    def undo(self, session: str) -> dict:
        return self.request({"op": "undo", "session": session})

    def redo(self, session: str) -> dict:
        return self.request({"op": "redo", "session": session})

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
