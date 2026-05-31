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
import status_display
from version_info import get_full_title
from log_config import LOGLEVEL, LOGFILE, LOGGING_ENABLED, logger

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
        self._test_view = None  # Testmodus-Vergleichsansicht (lazy)

        # GUI-Komponenten aufbauen
        self.control_panel = ControlPanel(self)
        self.control_panel.pack(fill="x")

        self.pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.pane.pack(fill=tk.BOTH, expand=True)

        self.tree_view = TreeViewFrame(self, controller=self)
        self.preview_frame = PreviewFrame(self, controller=self)


        self.pane.add(self.tree_view, weight=1)
        self.pane.add(self.preview_frame, weight=3)

        # Menüleiste (nach allen Komponenten aufbauen, da Referenzen benötigt werden)
        self._build_menu()

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
        self.tree_view.clear_node_index()
        self.preview_frame.canvas.delete("all")
        self.preview_frame.image_refs.clear()
        return True


    def _exit_app(self):
        if self.confirm_close_storage():
            self.destroy()

    def _build_menu(self):
        menubar = tk.Menu(self)

        # ── Datei ──────────────────────────────────────────────────────────────
        datei_menu = tk.Menu(menubar, tearoff=0)
        datei_menu.add_command(label="Importieren…",    accelerator="Strg+O",        command=self.control_panel.import_pdf)
        datei_menu.add_command(label="Speichern",       accelerator="Strg+S",        command=self.control_panel.save_automatic)
        datei_menu.add_command(label="Speichern als…",  accelerator="Strg+Umsch+S",  command=self.control_panel.save_as)
        datei_menu.add_command(label="Exportieren…",                                 command=self.control_panel.export_selected)
        datei_menu.add_separator()
        datei_menu.add_command(label="Schließen",                                    command=self.control_panel.close_storage)
        datei_menu.add_separator()
        datei_menu.add_command(label="Beenden",         accelerator="Alt+F4",        command=self._exit_app)
        menubar.add_cascade(label="Datei", menu=datei_menu)
        self.datei_menu = datei_menu

        # ── Bearbeiten ─────────────────────────────────────────────────────────
        self.edit_menu = tk.Menu(menubar, tearoff=0)
        self.edit_menu.add_command(label="Splitten",         command=self.control_panel.split_selected)
        self.edit_menu.add_command(label="Zusammenführen",   command=self.control_panel.merge_selected)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Ordner innerhalb", command=self.control_panel.add_folder_inside)
        self.edit_menu.add_command(label="Ordner unterhalb", command=self.control_panel.add_folder_below)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Umbenennen",  accelerator="F2",   command=self.control_panel.rename_selected)
        self.edit_menu.add_command(label="Löschen",     accelerator="Entf", command=self.control_panel.delete_selected)
        self.edit_menu.add_separator()
        _edit_status = tk.Menu(self.edit_menu, tearoff=0)
        _edit_status.add_command(label="Vorjahreswert", command=lambda: self.control_panel.set_status_for_selection("vorjahreswert"))
        _edit_status.add_command(label="Zu erfassen",   command=lambda: self.control_panel.set_status_for_selection("zu erfassen"))
        _edit_status.add_command(label="Erfasst",       command=lambda: self.control_panel.set_status_for_selection("erfasst"))
        self.edit_menu.add_cascade(label="Status", menu=_edit_status)
        menubar.add_cascade(label="Bearbeiten", menu=self.edit_menu)

        # ── Ansicht ────────────────────────────────────────────────────────────
        ansicht_menu = tk.Menu(menubar, tearoff=0)
        ansicht_menu.add_command(label="Zoom +",            accelerator="Strg++", command=self.preview_frame._zoom_in)
        ansicht_menu.add_command(label="Zoom −",            accelerator="Strg+−", command=self.preview_frame._zoom_out)
        ansicht_menu.add_command(label="Zoom zurücksetzen", accelerator="Strg+0", command=self.preview_frame._enable_autozoom)
        ansicht_menu.add_separator()
        self._show_original_var = tk.BooleanVar(value=False)
        ansicht_menu.add_checkbutton(label="Original anzeigen", variable=self._show_original_var,
                                     command=self._toggle_show_original)
        ansicht_menu.add_separator()
        self._test_mode_var = tk.BooleanVar(value=False)
        ansicht_menu.add_checkbutton(label="Testmodus", variable=self._test_mode_var,
                                     command=self._toggle_test_mode)
        menubar.add_cascade(label="Ansicht", menu=ansicht_menu)

        # ── ? ──────────────────────────────────────────────────────────────────
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Info", command=self._show_info)
        menubar.add_cascade(label="?", menu=help_menu)

        self.config(menu=menubar)

        # Keyboard-Shortcuts
        self.bind_all("<Control-o>", lambda e: self.control_panel.import_pdf())
        self.bind_all("<Control-s>", lambda e: self.control_panel.save_automatic())
        self.bind_all("<Control-S>", lambda e: self.control_panel.save_as())
        self.bind_all("<Control-plus>",  lambda e: self.preview_frame._zoom_in())
        self.bind_all("<Control-minus>", lambda e: self.preview_frame._zoom_out())
        self.bind_all("<Control-0>",     lambda e: self.preview_frame._enable_autozoom())

    def _update_menu_states(self):
        selection = self.tree_view.tree.selection()
        nodes = [self.tree_view.nodes_by_id.get(i) for i in selection]
        nodes = [n for n in nodes if n]

        n          = len(nodes)
        one        = n == 1
        multi      = n >= 2
        one_leaf   = one and not nodes[0].is_folder
        one_folder = one and nodes[0].is_folder
        same_level = multi and len({nd.parent for nd in nodes}) == 1

        def s(cond): return "normal" if cond else "disabled"

        # Bearbeiten-Menü
        em = self.edit_menu
        em.entryconfig("Splitten",         state=s(one_leaf))
        em.entryconfig("Zusammenführen",   state=s(same_level))
        em.entryconfig("Ordner innerhalb", state=s(one_folder))
        em.entryconfig("Ordner unterhalb", state=s(one))
        em.entryconfig("Umbenennen",       state=s(one))
        em.entryconfig("Löschen",          state=s(n >= 1))
        em.entryconfig("Status",           state=s(n >= 1))

        # Datei-Menü
        self.datei_menu.entryconfig("Exportieren…", state=s(n >= 1))

        # Kontextmenü
        ctx = self.tree_view.context_menu
        ctx.entryconfig("Splitten",         state=s(one_leaf))
        ctx.entryconfig("Zusammenführen",   state=s(same_level))
        ctx.entryconfig("Komprimieren",                state=s(n >= 1))
        ctx.entryconfig("Lesbarkeit geprüft",          state=s(n >= 1))
        ctx.entryconfig("Kompression zurücksetzen",    state=s(n >= 1))
        ctx.entryconfig("Ordner innerhalb", state=s(one_folder))
        ctx.entryconfig("Ordner unterhalb", state=s(one))
        ctx.entryconfig("Umbenennen",       state=s(one))
        ctx.entryconfig("Löschen",          state=s(n >= 1))
        ctx.entryconfig("Exportieren…",     state=s(n >= 1))
        ctx.entryconfig("Status",           state=s(n >= 1))

    def _toggle_show_original(self):
        self.preview_frame.show_original = self._show_original_var.get()
        if self.preview_frame.current_node:
            self.preview_frame.show_previews(self.preview_frame.current_node)

    def _toggle_test_mode(self):
        """Swap the editor pane for the input/live/expected comparison view.

        Test mode runs the golden-master operations (compression, split, merge)
        on the committed test fixtures and shows each input next to its live
        result and its expected reference. It expects tests/data/input/ to be
        present (see test_mode.fixtures_available).
        """
        if self._test_mode_var.get():
            from test_mode import TestModeView
            self.pane.pack_forget()
            if getattr(self, "_test_view", None) is None:
                self._test_view = TestModeView(self)
            self._test_view.frame.pack(fill=tk.BOTH, expand=True)
            # Building the datasets runs live compression/split/merge synchronously.
            self.set_busy(True)
            try:
                self._test_view.refresh()
            finally:
                self.set_busy(False)
        else:
            if getattr(self, "_test_view", None) is not None:
                self._test_view.frame.pack_forget()
            self.pane.pack(fill=tk.BOTH, expand=True)

    def _show_info(self):
        from version_info import get_full_title
        msg = (
            f"{get_full_title()}\n\n"
            f"Autor: Tobias Heinrich\n"
            f"Co-Autor: Claude (Anthropic)"
        )
        messagebox.showinfo("Info", msg)

    def set_busy(self, busy=True):
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

        # Only grab focus when entering the busy state (an operation is starting,
        # typically right after a user action / dialog). Forcing focus on release
        # would yank it back when a background task finishes while the user has
        # moved to another window. (Audit finding 11.)
        if busy:
            try:
                self.focus_force()
            except Exception as e:
                logger.debug("focus_force fehlgeschlagen: %s", e)

        def apply_cursor_recursively(widget):
            try:
                widget.config(cursor=cursor)
            except Exception as e:
                logger.debug("Cursor konnte für %r nicht gesetzt werden: %s", widget, e)
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
    # Nur öffnen, wenn der Nutzer Logging via PDF_TOOL_LOG_LEVEL aktiviert hat
    # UND tatsächlich etwas in die Datei geschrieben wurde.
    if LOGGING_ENABLED and os.path.exists(LOGFILE) and os.path.getsize(LOGFILE) > 0:
        os.startfile(LOGFILE)




if __name__ == "__main__":
    start_gui()
