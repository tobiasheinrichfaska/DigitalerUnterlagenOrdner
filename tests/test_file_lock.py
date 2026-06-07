"""Intensive tests for the exclusive single-writer FileLock (Windows share-mode lock).

These are real-filesystem integration tests — OS locking can't be faked. Skipped off
Windows (the lock is Windows-only)."""

import os
import sys
import threading

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="FileLock is Windows-only")

from infra.file_lock import FileLock, FileInUseError


def _file(tmp_path, name="doc.belegtool", data=b"hello"):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


# --- acquire / release ------------------------------------------------------

def test_acquire_release_then_reacquire(tmp_path):
    p = _file(tmp_path)
    lock = FileLock(p).acquire()
    assert lock.held
    lock.release()
    assert not lock.held
    FileLock(p).acquire().release()  # free again


def test_missing_file_is_not_in_use(tmp_path):
    with pytest.raises(FileNotFoundError):
        FileLock(str(tmp_path / "nope.belegtool")).acquire()


def test_second_acquire_raises_in_use(tmp_path):
    p = _file(tmp_path)
    first = FileLock(p).acquire()
    try:
        with pytest.raises(FileInUseError):
            FileLock(p).acquire()
    finally:
        first.release()
    FileLock(p).acquire().release()  # released → free


def test_release_is_idempotent(tmp_path):
    lock = FileLock(_file(tmp_path)).acquire()
    lock.release()
    lock.release()  # no raise


def test_context_manager_releases_on_exception(tmp_path):
    p = _file(tmp_path)
    with pytest.raises(ValueError):
        with FileLock(p):
            raise ValueError("boom")
    FileLock(p).acquire().release()  # was released despite the exception


# --- share-mode enforcement -------------------------------------------------

def test_while_locked_others_cannot_write(tmp_path):
    p = _file(tmp_path)
    lock = FileLock(p).acquire()
    try:
        with pytest.raises(PermissionError):
            open(p, "wb").close()
    finally:
        lock.release()


def test_while_locked_others_can_read(tmp_path):
    p = _file(tmp_path, data=b"READABLE")
    lock = FileLock(p).acquire()
    try:
        with open(p, "rb") as f:
            assert f.read() == b"READABLE"  # FILE_SHARE_READ
    finally:
        lock.release()


def test_while_locked_rename_is_blocked(tmp_path):
    p = _file(tmp_path)
    lock = FileLock(p).acquire()
    try:
        with pytest.raises(OSError):
            os.rename(p, p + ".renamed")  # no FILE_SHARE_DELETE
    finally:
        lock.release()


# --- io through the handle --------------------------------------------------

def test_overwrite_roundtrips_and_truncates(tmp_path):
    p = _file(tmp_path, data=b"original-long-content")
    lock = FileLock(p).acquire()
    try:
        lock.overwrite(b"short")          # shrink
        assert lock.read_all() == b"short"
        assert os.path.getsize(p) == len(b"short")  # truncated, no trailing garbage
        lock.overwrite(b"a-much-longer-content-again")  # grow
        assert lock.read_all() == b"a-much-longer-content-again"
        lock.overwrite(b"")               # empty
        assert lock.read_all() == b""
    finally:
        lock.release()


def test_many_overwrite_cycles_keep_handle_valid(tmp_path):
    p = _file(tmp_path)
    lock = FileLock(p).acquire()
    try:
        for i in range(500):
            lock.overwrite(f"v{i}".encode())
        assert lock.read_all() == b"v499"
    finally:
        lock.release()


def test_overwrite_without_acquire_raises(tmp_path):
    with pytest.raises(RuntimeError):
        FileLock(_file(tmp_path)).overwrite(b"x")


def test_unicode_path(tmp_path):
    p = _file(tmp_path, name="Beleg_äöü_2024.belegtool")
    lock = FileLock(p).acquire()
    try:
        lock.overwrite("Inhalt mit Ümläüten".encode("utf-8"))
        assert lock.read_all().decode("utf-8") == "Inhalt mit Ümläüten"
    finally:
        lock.release()


# --- concurrency ------------------------------------------------------------

def test_thread_race_exactly_one_winner(tmp_path):
    p = _file(tmp_path)
    winners, errors = [], []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            lock = FileLock(p).acquire()
            winners.append(lock)
        except FileInUseError:
            errors.append(1)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    try:
        assert len(winners) == 1            # exactly one holds it
        assert len(errors) == 7             # the rest see in-use, no deadlock
    finally:
        for w in winners:
            w.release()


def test_os_releases_lock_when_holder_process_dies(tmp_path):
    """Proves there is no stale lock: a child process holds the lock; when it is killed
    the OS frees the handle and the parent can acquire. Uses a readiness marker so it
    isn't timing-dependent."""
    import subprocess
    import textwrap
    import time

    p = _file(tmp_path)
    ready = str(tmp_path / "ready.flag")
    errfile = str(tmp_path / "child.err")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    child = subprocess.Popen([sys.executable, "-c", textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {root!r})
        from infra.file_lock import FileLock
        lock = FileLock({p!r}).acquire()   # keep a reference (pywin32 closes the handle on GC)
        open({ready!r}, "w").close()
        time.sleep(30)
    """)], stderr=open(errfile, "w"))
    try:
        for _ in range(100):                # wait until the child holds the lock
            if os.path.exists(ready):
                break
            time.sleep(0.1)
        if not os.path.exists(ready):
            with open(errfile) as f:
                pytest.fail("child never acquired the lock; stderr:\n" + f.read())

        with pytest.raises(FileInUseError):  # it's genuinely locked by the child
            FileLock(p).acquire()

        child.terminate()                    # simulate the holder dying
        child.wait(timeout=10)

        for _ in range(50):                  # OS releases the dead process's handle
            try:
                FileLock(p).acquire().release()
                break
            except FileInUseError:
                time.sleep(0.1)
        else:
            raise AssertionError("lock not released after the holder died")
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
