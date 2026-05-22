# gui_main.py
import logging
from tkinterdnd2 import TkinterDnD
from view_tree import TreeViewFrame
from view_preview import PreviewFrame
from pdf_storage import PDFStorage
from panel_controls import ControlPanel
import tkinter as tk
from tkinter import ttk, messagebox
from universal_importer import UniversalImporter
from typing import Optional
import os
import extract_msg
import status_display
from version_info import get_full_title

class DigitalerBelegGUI(TkinterDnD.Tk):
    def __init__(self, filepath: Optional[str] = None):
        super().__init__()

        # Titel setzen
        self.base_title = get_full_title()
        self.title(self.base_title)

        # Fenstergröße
        self.geometry("1600x900")

        # Zentrale Speicherobjekte
        self.storage = None
        self.selected_node = None

        # GUI-Komponenten aufbauen
        self.control_panel = ControlPanel(self)
        self.control_panel.pack(fill="x")

        self.pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.pane.pack(fill=tk.BOTH, expand=True)

        self.tree_view = TreeViewFrame(self, controller=self)
        self.preview_frame = PreviewFrame(self, controller=self)


        self.pane.add(self.tree_view, weight=1)
        self.pane.add(self.preview_frame, weight=3)

        # Fenster-Schließen abfangen
        self.protocol("WM_DELETE_WINDOW", self._exit_app)

        # Titel-Loop aktivieren
        status_display.set_base_title(self.base_title)
        self.after_idle(lambda: status_display.start_title_loop(self))

        # Falls Datei mitgegeben wurde → direkt laden
        if filepath:
            self._load_file_on_start(filepath)


    def update_preview(self, node):
        self.selected_node = node
        self.preview_frame.show_previews(node)
        self.control_panel.update_buttons(node)
        self.tree_view.refresh_colors()



    def confirm_close_storage(self) -> bool:
        if not self.storage:
            return True

        if self.storage.is_dirty:
            confirm = messagebox.askyesno(
                "Ungespeicherte Änderungen",
                "Es liegen ungespeicherte Änderungen vor. Trotzdem schließen?",
                icon="warning", default="no"
            )
            if not confirm:
                return False

        # Alles löschen
        self.storage = None
        self.selected_node = None
        self.tree_view.tree.delete(*self.tree_view.tree.get_children())
        self.tree_view.nodes_by_id.clear()
        self.preview_frame.canvas.delete("all")
        self.preview_frame.image_refs.clear()
        return True


    def _exit_app(self):
        if self.confirm_close_storage():
            self.destroy()

    def set_busy(self, busy=True):
        # Globaler Cursor für alle Widgets
        cursor = "watch" if busy else ""
        self.config(cursor=cursor)
        self.tree_view.config(cursor=cursor)
        self.tree_view.tree.config(cursor=cursor)
        self.preview_frame.config(cursor=cursor)
        self.preview_frame.canvas.config(cursor=cursor)

        # Titel-Task setzen oder entfernen
        if busy:
            status_display.register_task("Busy")
        else:
            status_display.unregister_task("Busy")

        # Anzeige sofort erzwingen
        self.update_idletasks()

        # Fokus hart setzen (damit Cursor greift)
        try:
            self.focus_force()
        except Exception:
            pass

        # Rekursiv auf alle Child-Widgets anwenden
        def apply_cursor_recursively(widget):
            try:
                widget.config(cursor=cursor)
            except Exception:
                pass
            for child in widget.winfo_children():
                apply_cursor_recursively(child)

        apply_cursor_recursively(self)

    def set_busy(self, busy=True):
        # Globaler Cursor für alle Widgets
        cursor = "watch" if busy else ""
        self.config(cursor=cursor)
        self.tree_view.config(cursor=cursor)
        self.tree_view.tree.config(cursor=cursor)
        self.preview_frame.config(cursor=cursor)
        self.preview_frame.canvas.config(cursor=cursor)

        if busy:
            status_display.register_task("Busy")
        else:
            status_display.unregister_task("Busy")

        self.update_idletasks()

        try:
            self.focus_force()
        except Exception:
            pass

        def apply_cursor_recursively(widget):
            try:
                widget.config(cursor=cursor)
            except Exception:
                pass
            for child in widget.winfo_children():
                apply_cursor_recursively(child)

        apply_cursor_recursively(self)

    def _load_file_on_start(self, filepath: str):
        try:
            self.set_busy(True)

            ext = os.path.splitext(filepath)[1].lower()
            if ext != ".belegtool":
                messagebox.showwarning(
                    "Nur BelegTool-Dateien erlaubt",
                    "Beim Start können nur .belegtool-Dateien direkt geöffnet werden.\n"
                    "Andere Formate bitte über den Import-Dialog laden."
                )
                return

            self.storage = PDFStorage(filepath)
            self.storage.filename = filepath
            self.storage.save_path = filepath

            self.tree_view.rebuild_tree()

        except Exception as e:
            messagebox.showerror("Fehler beim Laden", str(e))
        finally:
            self.set_busy(False)

def start_gui():
    import sys
    logging.basicConfig(level=logging.INFO)
    filepath = sys.argv[1] if len(sys.argv) > 1 else None
    app = DigitalerBelegGUI(filepath=filepath)
    UniversalImporter.initialize_async()
    app.mainloop()
    if LOGLEVEL < logging.CRITICAL and os.path.exists(LOGFILE) and os.path.getsize(LOGFILE) > 0:
        os.startfile(LOGFILE)




if __name__ == "__main__":
    start_gui()
