"""Exclusive single-writer lock on a file (Windows), used optionally for the
client-server / SMB store so only one person edits a ``.belegtool`` at a time.

Holds a Win32 handle open with share mode = FILE_SHARE_READ for the file's whole
edit lifetime — i.e. others may open it read-only, but **no one else can write,
rename or delete it** (bit-for-bit the share mode Adobe Acrobat uses). The OS frees
the handle when the process dies, so there is no stale lock to clean up.

Because the handle denies write-sharing, the app cannot reopen the file with
``open(path, 'wb')`` while it holds the lock — saving must go through ``overwrite``.
Reading is fine (FILE_SHARE_READ allows other read opens, incl. our own).

Windows-only (pywin32). The lock is off by default; only enabled via settings.
"""

from __future__ import annotations

import sys


class FileInUseError(Exception):
    """The file is already open (write-locked) by someone else."""


class FileLock:
    def __init__(self, path: str, share_read: bool = True):
        self.path = path
        self._share_read = share_read
        self._handle = None

    # -- lifecycle ----------------------------------------------------------
    def acquire(self) -> "FileLock":
        if sys.platform != "win32":
            raise RuntimeError("FileLock is only supported on Windows")
        import win32con
        import win32file
        import pywintypes

        share = win32con.FILE_SHARE_READ if self._share_read else 0  # never WRITE/DELETE
        try:
            self._handle = win32file.CreateFile(
                self.path,
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                share,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None,
            )
        except pywintypes.error as e:
            if e.winerror == 32:  # ERROR_SHARING_VIOLATION
                raise FileInUseError(self.path) from e
            if e.winerror in (2, 3):  # FILE/PATH_NOT_FOUND
                raise FileNotFoundError(self.path) from e
            raise
        return self

    def release(self) -> None:
        if self._handle is not None:
            try:
                import win32file
                win32file.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None

    @property
    def held(self) -> bool:
        return self._handle is not None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *_exc):
        self.release()

    # -- io through the held handle ----------------------------------------
    def read_all(self) -> bytes:
        """Current file bytes. A normal read open works under FILE_SHARE_READ, so this
        does not need the handle — but it's offered for symmetry/tests."""
        with open(self.path, "rb") as f:
            return f.read()

    def overwrite(self, data: bytes) -> None:
        """Replace the file's contents **through the held handle** (the only way to write
        while the lock denies write-sharing): seek 0, write, truncate, flush to disk."""
        if self._handle is None:
            raise RuntimeError("overwrite called without an acquired lock")
        import win32con
        import win32file

        win32file.SetFilePointer(self._handle, 0, win32con.FILE_BEGIN)
        mv = memoryview(data)
        written = 0
        while written < len(mv):
            _hr, n = win32file.WriteFile(self._handle, bytes(mv[written:]))
            if n <= 0:
                break
            written += n
        win32file.SetEndOfFile(self._handle)
        win32file.FlushFileBuffers(self._handle)
