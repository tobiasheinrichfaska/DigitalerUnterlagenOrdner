"""Tests for the headless progress port (progress.py)."""

import progress


class _Recorder:
    def __init__(self):
        self.started = []
        self.finished = []

    def task_started(self, name):
        self.started.append(name)

    def task_finished(self, name):
        self.finished.append(name)


def test_noop_without_reporter():
    progress.set_reporter(None)
    # Must not raise when nothing is wired up.
    progress.task_started("x")
    progress.task_finished("x")


def test_reporter_receives_signals():
    rec = _Recorder()
    progress.set_reporter(rec)
    try:
        progress.task_started("Kompression: a")
        progress.task_finished("Kompression: a")
        assert "Kompression: a" in rec.started
        assert "Kompression: a" in rec.finished
    finally:
        progress.set_reporter(None)


def test_reporter_exceptions_are_swallowed():
    class _Boom:
        def task_started(self, name):
            raise RuntimeError("boom")

        def task_finished(self, name):
            raise RuntimeError("boom")

    progress.set_reporter(_Boom())
    try:
        progress.task_started("x")   # swallowed, no raise
        progress.task_finished("x")
    finally:
        progress.set_reporter(None)
