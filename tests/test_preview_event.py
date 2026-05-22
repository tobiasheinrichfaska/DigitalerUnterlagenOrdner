import threading
import time
import pytest
from pdf_node import PDFNode
from helpers import create_valid_pdf, wait_for_ready


def make_node(name="evt_node"):
    return PDFNode(name=name, pdf_data=create_valid_pdf(pages=1))


def test_event_set_on_init():
    node = make_node()
    assert node._preview_done.is_set(), "_preview_done must be set initially (no task running)"


def test_event_cleared_while_task_runs():
    node = make_node()
    # Start a preview task
    node._preview_done.clear()
    assert not node._preview_done.is_set()


def test_event_set_after_task_completes():
    node = make_node()
    # Trigger a real preview task via update_preview
    node.update_preview()
    # Wait for the background thread to finish
    set_in_time = node._preview_done.wait(timeout=15)
    assert set_in_time, "_preview_done should be set after preview task finishes"


def test_wait_returns_quickly_when_no_task_running():
    node = make_node()
    start = time.monotonic()
    result = node._preview_done.wait(timeout=5)
    elapsed = time.monotonic() - start
    assert result is True
    assert elapsed < 0.5, "wait() should return immediately when no task is running"


def test_event_set_after_preview_lazy():
    node = make_node()
    node.preview_lazy()
    # The event should be set again once the background task completes
    set_in_time = node._preview_done.wait(timeout=15)
    assert set_in_time, "_preview_done should be set after preview_lazy completes"


def test_two_nodes_events_independent():
    node1 = make_node("n1")
    node2 = make_node("n2")
    node1._preview_done.clear()
    assert not node1._preview_done.is_set()
    assert node2._preview_done.is_set(), "n2 event must not be affected by n1"
