# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
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

import os
import sys

from infra.log_config import logger


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
                # N-2 (QS 2026-11-04): an incomplete write must be an ERROR — the old
                # silent `break` continued into SetEndOfFile/Flush, the save counted as
                # success and write_through_lock removed the .bak safety copy.
                raise OSError(f"Unvollständig geschrieben: {written} von {len(mv)} Bytes")
            written += n
        win32file.SetEndOfFile(self._handle)
        win32file.FlushFileBuffers(self._handle)


# -- single-writer disk-I/O policy (stateless; extracted from CoreApi, audit S-1) ----
# These wrap FileLock with the .bak crash-recovery policy. They hold no application
# state, so they live here next to the primitive they build on rather than on CoreApi.

def restore_from_bak(path: str) -> None:
    """If a locked save was interrupted, ``path`` may be truncated/invalid while a sibling
    ``.bak`` holds the previous good bytes — restore it before opening. A save interrupted
    AFTER the %PDF header but before the trailer leaves a truncated file a header-only check
    would wrongly accept (→ silent data loss), so require BOTH a %PDF header and a %%EOF
    trailer; otherwise restore from .bak. The .bak is removed either way."""
    bak = path + ".bak"
    wip = path + ".wip"
    pending = os.path.exists(wip)  # a locked save started but never finished
    if not os.path.exists(bak):
        if pending:
            try:
                os.remove(wip)  # stale marker without a .bak — nothing to restore from
            except OSError:
                pass
        return
    try:
        # Nebenbefund 1 (QS 2026-11-04): the head/tail heuristic alone also accepts a
        # file whose beginning is new and whose end is from the previous version (both
        # markers present). The .wip marker is authoritative: it only exists while a
        # locked save is in flight, so its presence means the write did not complete.
        ok = False
        if not pending:
            size = os.path.getsize(path)
            if size > 0:
                with open(path, "rb") as f:
                    head = f.read(1024)
                    f.seek(max(0, size - 1024))
                    tail = f.read()
                ok = b"%PDF" in head and b"%%EOF" in tail
    except Exception:
        ok = False
    if not ok:
        try:
            import shutil
            shutil.copyfile(bak, path)
            logger.warning("[lock] restored %s from .bak after an interrupted save", path)
        except Exception:
            logger.exception("[lock] .bak restore failed")
    try:
        os.remove(bak)
    except OSError:
        pass
    if pending:
        try:
            os.remove(wip)
        except OSError:
            pass


def acquire_lock(path: str):
    """Restore from a leftover ``.bak`` (truncated interrupted save), then acquire the
    single-writer lock. Returns a held ``FileLock``; re-raises ``FileInUseError`` if the
    file is already locked; returns ``None`` on non-Windows / unexpected errors (best-effort:
    open without a lock rather than block the user)."""
    restore_from_bak(path)
    try:
        return FileLock(path).acquire()
    except FileInUseError:
        raise
    except Exception:
        logger.warning("[lock] acquire failed; opening without a lock", exc_info=True)
        return None


def write_through_lock(lock: "FileLock", path: str, data: bytes) -> None:
    """Overwrite ``path`` **through the held handle** (the lock denies our own ``open('wb')``),
    guarding the non-atomic in-place write with a sibling ``.bak`` of the previous bytes,
    removed only after a successful flush. If the current bytes can't be read AND the on-disk
    file is non-empty, abort rather than risk an unrecoverable truncated write."""
    bak = path + ".bak"
    wip = path + ".wip"
    # A leftover marker means the PREVIOUS locked save failed mid-write: the existing
    # .bak still holds the last good bytes — never refresh it from the current on-disk
    # state (Nebenbefund 1, QS 2026-11-04).
    retry_after_failure = os.path.exists(wip) and os.path.exists(bak)
    if not retry_after_failure:
        read_ok = True
        try:
            prev = lock.read_all()
        except Exception:
            prev = b""
            read_ok = False
        if not read_ok:
            try:
                on_disk = os.path.getsize(path)
            except OSError:
                on_disk = 0
            if on_disk:
                raise OSError(
                    f"Konnte die vorhandene Datei vor dem Speichern nicht sichern: {path}")
        if prev:
            with open(bak, "wb") as f:
                f.write(prev)
    with open(wip, "wb") as f:
        f.write(b"wip")  # in-flight marker; restore_from_bak treats it as authoritative
    lock.overwrite(data)
    # The write completed — clear the safety files. Order matters: remove the .bak
    # FIRST, then the marker. If we crash between the two, a leftover marker WITHOUT
    # a .bak is harmless (restore_from_bak just drops it); the reverse order could
    # leave marker+bak behind a failed remove and the next open would restore the
    # OLD bytes over this successful save (QS-Bewertung 2026-11-04). A vanished
    # marker (another process's restore_from_bak raced us) is not an error either.
    try:
        os.remove(bak)
    except OSError:
        pass
    try:
        os.remove(wip)
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("[lock] .wip marker could not be removed: %s", wip)
