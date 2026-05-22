import pytest
from belegtool_main import DigitalerBelegGUI
from unittest.mock import MagicMock, patch
import tkinter

def has_tkdnd():
    try:
        root = tkinter.Tk()
        root.tk.call("package", "require", "tkdnd")
        root.destroy()
        return True
    except:
        return False

@pytest.fixture
def app():
    if not has_tkdnd():
        pytest.skip("tkdnd nicht verfügbar – GUI-Test übersprungen")
    gui = DigitalerBelegGUI()
    gui.update()
    yield gui
    gui.destroy()
    gui.update_idletasks()
    tkinter._default_root = None

def test_window_title(app):
    assert app.title() == app.base_title

def test_gui_components_exist(app):
    assert hasattr(app, "control_panel")
    assert hasattr(app, "tree_view")
    assert hasattr(app, "preview_frame")

def test_set_busy_on(app):
    app.set_busy(True)
    assert app["cursor"] == "watch"
    app.set_busy(False)

def test_set_busy_off(app):
    app.set_busy(False)
    assert app["cursor"] == ""

def test_update_preview_assigns_node(app):
    dummy_node = object()
    app.preview_frame.show_previews = MagicMock()
    app.control_panel.update_buttons = MagicMock()
    app.tree_view.refresh_colors = MagicMock()
    app.update_preview(dummy_node)
    assert app.selected_node is dummy_node
    app.preview_frame.show_previews.assert_called_once_with(dummy_node)
    app.control_panel.update_buttons.assert_called_once_with(dummy_node)
    app.tree_view.refresh_colors.assert_called_once()

def test_confirm_close_storage_without_changes(app):
    app.storage = None
    assert app.confirm_close_storage() is True

def test_confirm_close_storage_with_unsaved_changes_yes(app):
    app.storage = MagicMock(is_dirty=True)
    with patch("tkinter.messagebox.askyesno", return_value=True):
        assert app.confirm_close_storage() is True

def test_confirm_close_storage_with_unsaved_changes_no(app):
    app.storage = MagicMock(is_dirty=True)
    with patch("tkinter.messagebox.askyesno", return_value=False):
        assert app.confirm_close_storage() is False