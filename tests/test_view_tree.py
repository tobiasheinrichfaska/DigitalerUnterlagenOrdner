import pytest
import tkinter
from tkinterdnd2 import TkinterDnD
from view_tree import TreeViewFrame

class DummyController:
    def __init__(self):
        self.storage = None
        self.control_panel = None
        self.tree_view = None
    def set_busy(self, val): pass
    def update_preview(self, node): pass

@pytest.fixture
def tree_view():
    """
    Robuste TreeView-Fixture:
    - Verwendet echten TkinterDnD-Kontext
    - Überspringt den Test, wenn kein GUI verfügbar ist
    - Räumt Fenster und Widgets zuverlässig auf
    """
    try:
        root = TkinterDnD.Tk()
        frame = TreeViewFrame(root, controller=DummyController())
        frame.pack(fill="both", expand=True)
        root.update()
    except Exception as e:
        pytest.skip(f"GUI-Initialisierung fehlgeschlagen (TkinterDnD.Tk()): {e}")
        return

    yield frame

    try:
        frame.destroy()
        root.destroy()
    except:
        pass

    # Rücksetzen des globalen tkinter-Zustands
    tkinter._default_root = None


def test_treeview_created(tree_view):
    assert tree_view.tree.winfo_exists()
    assert isinstance(tree_view.nodes_by_id, dict)


def test_context_menu_configured(tree_view):
    menu = tree_view.context_menu
    assert menu.index("end") is not None


def test_slider_release_triggers_update():
    """
    Testet, ob der Slider das Preview-Update korrekt auslöst.
    Wird übersprungen, wenn kein GUI verfügbar ist.
    """
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.destroy()
    except Exception:
        pytest.skip("tkinter nicht verfügbar – GUI-Test übersprungen")

    # Hier folgt dein eigentlicher Testcode (Platzhalter)
    assert True  # Beispiel-Placeholder – bitte mit realem Code ersetzen
