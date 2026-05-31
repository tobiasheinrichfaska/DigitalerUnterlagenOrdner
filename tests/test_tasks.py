"""Tests for the headless task-execution port (tasks.py)."""

import threading

import tasks


def test_default_executor_runs_the_fn():
    done = threading.Event()
    tasks.submit(done.set)
    assert done.wait(timeout=5), "default executor did not run the task"


def test_custom_synchronous_executor_runs_inline():
    class _Sync:
        def submit(self, fn):
            fn()

    tasks.set_executor(_Sync())
    try:
        calls = []
        tasks.submit(lambda: calls.append(1))
        assert calls == [1]  # ran synchronously, in-line
    finally:
        tasks.set_executor(None)


def test_set_executor_none_resets_to_default():
    tasks.set_executor(None)
    done = threading.Event()
    tasks.submit(done.set)
    assert done.wait(timeout=5)
