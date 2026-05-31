import gc
import os
import time
import pytest
import tkinter
import tkinter as tk
from view_preview import PreviewFrame
from pdf_node import PDFNode
from PIL import Image
from helpers import create_valid_pdf, wait_for_ready

pytestmark = pytest.mark.skipif(
    "DISPLAY" not in os.environ and os.name != "nt",
    reason="Kein X-Server (Linux) oder GUI-Umgebung verfügbar"
)


class DummyController:
    def __init__(self):
        self.last_updated = None
        self.storage = None

    def update_preview(self, node):
        self.last_updated = node


@pytest.fixture
def preview():
    # A fresh root per test (destroyed in teardown) is deliberate: it cancels any
    # leaked `after`-poll timers with the interpreter. A shared module/session
    # root instead lets a poll scheduled in one test fire against the next test's
    # destroyed frame (TclError). The occasional tk.tcl init flakiness when this
    # file is run alone in a tight loop is the lesser evil.
    root = tk.Tk()
    ctrl = DummyController()
    frame = PreviewFrame(root, controller=ctrl)
    frame.pack()
    root.update()
    yield frame
    if frame._poll_after_id:
        try:
            frame.after_cancel(frame._poll_after_id)
        except Exception:
            pass
    frame.destroy()
    root.update_idletasks()
    root.destroy()
    del frame, root, ctrl
    gc.collect()
    tkinter._default_root = None


def idle_node(name="idle"):
    img = Image.new("RGB", (100, 100), color="white")
    node = PDFNode(name, pdf_data=b"%PDF-1.4\n%EOF")
    node._preview_task_running = False
    node._compression_task_running = False
    node._original_preview_pages = []
    node._current_preview_pages = []
    node.original_pdf_data = b"%PDF-1.4\n%EOF"
    node.current_pdf_data = b"%PDF-1.4\n%EOF"
    return node


def busy_node(name="busy"):
    node = idle_node(name)
    node._preview_task_running = True
    return node


# --- _set_controls_enabled ---

def test_controls_disabled(preview):
    preview._set_controls_enabled(False)
    assert str(preview.rotate_button["state"]) in ("disabled", "disable")
    assert str(preview.commit_button["state"]) in ("disabled", "disable")


def test_controls_enabled(preview):
    preview._set_controls_enabled(False)
    preview._set_controls_enabled(True)
    assert str(preview.rotate_button["state"]) in ("normal", "active")
    assert str(preview.commit_button["state"]) in ("normal", "active")


# --- show_previews busy/idle behaviour ---

def test_show_previews_idle_node_enables_controls(preview):
    node = idle_node()
    preview.show_previews(node)
    assert str(preview.commit_button["state"]) in ("normal", "active")


def test_show_previews_busy_node_disables_controls(preview):
    node = busy_node()
    preview.show_previews(node)
    assert str(preview.commit_button["state"]) in ("disabled", "disable")


def test_show_previews_busy_schedules_poll(preview):
    node = busy_node()
    preview.show_previews(node)
    assert preview._poll_after_id is not None


def test_show_previews_idle_does_not_schedule_poll(preview):
    node = idle_node()
    # A genuinely settled node: already compressed, so show_previews must NOT
    # auto-start compression (and therefore must not schedule a poll). A node
    # with empty _compression_results would legitimately trigger the
    # auto-compress-on-show feature instead.
    node.is_compressed = True
    node._compression_results = {"jpg": node.current_pdf_data}
    preview.show_previews(node)
    assert preview._poll_after_id is None


# --- _poll_node_ready ---

def test_poll_re_enables_controls_when_task_done(preview):
    node = busy_node("poll_test")
    preview.current_node = node
    preview.show_previews(node)
    assert str(preview.commit_button["state"]) in ("disabled", "disable")

    # Simulate task finishing
    node._preview_task_running = False
    node._compression_task_running = False

    # Let the poll timer fire (150 ms + headroom)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        preview.update()
        if str(preview.commit_button["state"]) in ("normal", "active"):
            break
        time.sleep(0.05)

    assert str(preview.commit_button["state"]) in ("normal", "active")


def test_poll_ignores_stale_node(preview):
    node_old = busy_node("old")
    preview.show_previews(node_old)

    # Replace current_node before poll fires
    node_new = idle_node("new")
    preview.show_previews(node_new)

    # Poll should not re-run show_previews for old node
    time.sleep(0.3)
    preview.update()
    assert preview.current_node is node_new
