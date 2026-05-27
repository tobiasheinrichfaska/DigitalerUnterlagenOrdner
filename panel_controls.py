from tkinter import ttk, filedialog, messagebox, simpledialog
import tkinter as tk
from log_config import logger
from universal_importer import UniversalImporter
from pdf_storage import PDFStorage
from pdf_node import PDFNode
from typing import Optional
import os

class ControlPanel(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.controller = master

        self.import_button = ttk.Button(self, text="Importieren", command=self.import_pdf)
        self.import_button.pack(side="left", padx=5, pady=5)

        self.save_button_auto = ttk.Button(self, text="Speichern", command=self.save_automatic)
        self.save_button_auto.pack(side="left", padx=5, pady=5)

        self.save_as_button = ttk.Button(self, text="Speichern als", command=self.save_as)
        self.save_as_button.pack(side="left", padx=5, pady=5)


    def update_buttons(self, node):
        """
        Aktualisiert die Toolbar-/Aktionszustände basierend auf dem aktuell
        ausgewählten Knoten. Delegiert an die Menü-Statuslogik im Hauptfenster,
        damit Toolbar und Menüs konsistent bleiben.
        """
        update_menu_states = getattr(self.controller, "_update_menu_states", None)
        if callable(update_menu_states):
            update_menu_states()


    def rename_selected(self):
        selected_ids = self.controller.tree_view.tree.selection()
        if not selected_ids:
            return
        item_id = selected_ids[0]
        node = self.controller.tree_view.nodes_by_id.get(item_id)
        if not node:
            return

        from tkinter.simpledialog import askstring
        new_name = askstring("Umbenennen", "Neuer Name für den Knoten:", initialvalue=node.name)
        if new_name:
            node.name = new_name
            self.controller.storage.mark_dirty()
            self.controller.tree_view.tree.item(item_id, text=new_name)


    def add_folder_inside(self):
        selected_ids = self.controller.tree_view.tree.selection()
        if not selected_ids:
            return

        try:
            self.controller.set_busy(True)
            self.controller.storage.mark_dirty()
            for item_id in selected_ids:
                parent_node = self.controller.tree_view.nodes_by_id.get(item_id)
                if not parent_node or not parent_node.is_folder:
                    messagebox.showerror("Ungültiger Zielknoten", "Ein Ordner kann nur innerhalb eines anderen Ordners erstellt werden.")
                    continue
                new_node = self._create_folder_node("Neuer Ordner")
                parent_node.add_child(new_node)
                new_id = self.controller.tree_view.tree.insert(item_id, "end", text=new_node.name)
                self.controller.tree_view.nodes_by_id[new_id] = new_node
        finally:
            self.controller.set_busy(False)

    def add_folder_below(self):
        selected_ids = self.controller.tree_view.tree.selection()
        if not selected_ids:
            return

        try:
            self.controller.set_busy(True)
            self.controller.storage.mark_dirty()
            for item_id in selected_ids:
                current_node = self.controller.tree_view.nodes_by_id.get(item_id)
                if not current_node or not current_node.parent:
                    continue
                parent_node = current_node.parent
                new_node = self._create_folder_node("Neuer Ordner")

                # insert directly after current node in the sibling list
                siblings = current_node.parent.children
                index = siblings.index(current_node)
                siblings.insert(index + 1, new_node)
                new_node.parent = current_node.parent

                # TreeView: visuell direkt unterhalb einfügen
                parent_id = self.controller.tree_view.tree.parent(item_id)
                tree_index = self.controller.tree_view.tree.index(item_id)
                new_id = self.controller.tree_view.tree.insert(parent_id, tree_index + 1, text=new_node.name)
                self.controller.tree_view.nodes_by_id[new_id] = new_node
        finally:
            self.controller.set_busy(False)


    def delete_selected(self):
        selected_ids = self.controller.tree_view.tree.selection()
        if not selected_ids:
            return

        if not messagebox.askyesno("Löschen bestätigen", "Ausgewählte Knoten wirklich löschen?", icon="warning", default="no"):
            return

        try:
            self.controller.set_busy(True)
            self.controller.storage.mark_dirty()

            # Fokusziel vor dem Löschen ermitteln
            fallback_node = None
            first_id = selected_ids[0]
            first_node = self.controller.tree_view.nodes_by_id.get(first_id)

            if first_node and first_node.parent:
                siblings = first_node.parent.children
                idx = siblings.index(first_node) if first_node in siblings else -1
                if idx > 0:
                    fallback_node = siblings[idx - 1]  # linker Sibling
                else:
                    fallback_node = first_node.parent  # sonst Parent
            if not fallback_node:
                fallback_node = self.controller.storage.root



            for item_id in selected_ids:
                node = self.controller.tree_view.nodes_by_id.get(item_id)
                if node:
                    node.delete()
                    self.controller.tree_view.tree.delete(item_id)
                    del self.controller.tree_view.nodes_by_id[item_id]

                fallback_id = self.controller.tree_view._get_iid_for_node(fallback_node)
                if fallback_id:
                    self.controller.tree_view.tree.selection_set(fallback_id)
                    self.controller.tree_view.tree.focus(fallback_id)
                    self.controller.tree_view.tree.focus_set()  # Bringt Fokus ins TreeView-Feld zurück
                    self.controller.update_preview(fallback_node)



        finally:
            self.controller.set_busy(False)
            # Direkt dem Treeview den Eingabefokus geben
            self.controller.tree_view.tree.focus_set()

            # Alternativ (robust gegen Canvas-"Übergriff"):
            self.after_idle(lambda: self.controller.tree_view.tree.focus_force())

    def _create_folder_node(self, name: str):
        from pdf_node import PDFNode
        return PDFNode(name=name, is_folder=True)


    def close_storage(self):
        try:
            self.controller.set_busy(True)
            if self.controller.confirm_close_storage():
                messagebox.showinfo("Info", "PDF-Daten wurden geschlossen.")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
        finally:
            self.controller.set_busy(False)


    def set_status_for_selection(self, status_text: str):
        selected_ids = self.controller.tree_view.tree.selection()
        if not selected_ids:
            return

        try:
            self.controller.set_busy(True)
            self.controller.storage.mark_dirty()
            for item_id in selected_ids:
                node = self.controller.tree_view.nodes_by_id.get(item_id)
                if not node:
                    continue
                if node.is_folder:
                    for subnode in self.controller.storage.get_all_nodes():
                        if not subnode.is_folder and subnode._is_descendant_of(node):
                            subnode.status = status_text
                else:
                    node.status = status_text
            self.controller.update_preview(self.controller.selected_node)
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
        finally:
            self.controller.tree_view.refresh_colors()
            self.controller.set_busy(False)


    def commit_changes_for_selection(self):
        selected_ids = self.controller.tree_view.tree.selection()
        if not selected_ids:
            messagebox.showinfo("Hinweis", "Bitte einen Knoten auswählen.")
            return

        try:
            self.controller.set_busy(True)
            self.controller.storage.mark_dirty()

            for item_id in selected_ids:
                root_node = self.controller.tree_view.nodes_by_id.get(item_id)
                if not root_node:
                    continue

                messagebox.showinfo("Original ersetzen",
                    f'Der ausgewählte Knoten ("{root_node.name}") wird auf den aktuellen Stand gesetzt.\n'
                    f'Dies betrifft ggf. alle enthaltenen Unterknoten.')
                root_node.commit_changes()

            self.controller.update_preview(self.controller.selected_node)
        except Exception as e:
            messagebox.showerror("Fehler", f"Original konnte nicht ersetzt werden:\n{e}")
        finally:
            self.controller.tree_view.refresh_colors()
            self.controller.set_busy(False)

    def _group_as_folder(self, selected_ids) -> bool:
        """Groups selected nodes into a new folder. Returns True if handled."""
        if not messagebox.askyesno(
            "Als Ordner gruppieren?",
            "Sollen die markierten Knoten in einem gemeinsamen Ordner zusammengefasst werden?",
            default="no", icon="question"
        ):
            return False

        folder_name = simpledialog.askstring("Ordnername", "Name für den neuen Ordner:", initialvalue="Neuer Ordner") or "Neuer Ordner"
        first_id = selected_ids[0]
        first_node = self.controller.tree_view.nodes_by_id[first_id]
        parent = first_node.parent

        new_folder = self._create_folder_node(folder_name)
        new_folder.parent = parent

        if parent:
            siblings = parent.children
            insert_index = siblings.index(first_node)
            siblings.insert(insert_index, new_folder)
            new_folder.position = first_node.position
        else:
            self.controller.storage.root.children.insert(0, new_folder)

        parent_id = self.controller.tree_view.tree.parent(first_id)
        tree_index = self.controller.tree_view.tree.index(first_id)
        folder_id = self.controller.tree_view.tree.insert(parent_id, tree_index, text=new_folder.name)
        self.controller.tree_view.nodes_by_id[folder_id] = new_folder

        for item_id in selected_ids:
            node = self.controller.tree_view.nodes_by_id.get(item_id)
            if node and node != new_folder:
                node.move(new_folder)

        self.controller.tree_view.rebuild_tree()
        self.controller.storage.mark_dirty()
        self.controller.update_preview(new_folder)
        return True

    def _check_merge_preconditions(self, selected_ids) -> bool:
        """Returns True if merge can proceed, False if the user cancelled."""
        if any(
            getattr(self.controller.tree_view.nodes_by_id.get(iid), "no_compression", False)
            for iid in selected_ids
        ):
            if not messagebox.askyesno(
                "Merge verhindert künftige Kompression",
                "Mindestens ein ausgewählter Knoten ist dauerhaft von Kompression ausgeschlossen.\n"
                "Wird der Merge durchgeführt, betrifft dies alle zusammengeführten Inhalte.\n\n"
                "Möchten Sie den Merge trotzdem durchführen?",
                icon="warning", default="no"
            ):
                return False

        try:
            dpi_originals, dpi_currents = set(), set()
            for iid in selected_ids:
                node = self.controller.tree_view.nodes_by_id.get(iid)
                if not node or node.is_folder:
                    continue
                if node.dpi_original is not None:
                    dpi_originals.add(node.dpi_original)
                if node.dpi_current is not None:
                    dpi_currents.add(node.dpi_current)

            if len(dpi_originals) > 1 or len(dpi_currents) > 1:
                if not messagebox.askyesno(
                    "Komprimierungen verwerfen?",
                    "Die markierten Knoten haben unterschiedliche Komprimierungen oder Auflösungen.\n"
                    "Soll der Merge trotzdem durchgeführt werden?\n\n"
                    "Dabei werden alle aktuellen Komprimierungen gelöscht.",
                    icon="warning", default="no"
                ):
                    return False
        except Exception as e:
            messagebox.showerror("Fehler bei DPI-Prüfung", str(e))
            return False

        return True

    def merge_selected(self):
        selected_ids = self.controller.tree_view.tree.selection()
        try:
            self.controller.set_busy(True)

            if self._group_as_folder(selected_ids):
                return

            if not self._check_merge_preconditions(selected_ids):
                return

            base = self.controller.tree_view.nodes_by_id[selected_ids[0]]
            for item_id in selected_ids[1:]:
                other = self.controller.tree_view.nodes_by_id.get(item_id)
                if not other or other == base:
                    continue
                if base.is_folder != other.is_folder:
                    raise ValueError("Nur gleichartige Knoten (Ordner oder PDF) können zusammengeführt werden.")
                base.merge(other, nopreview=True)
                other.delete()
                self.controller.tree_view.tree.delete(item_id)
                del self.controller.tree_view.nodes_by_id[item_id]

            base.update_preview()
            if not base.no_compression and base.current_pdf_data is None:
                base.compress_lazy()

            self.controller.tree_view.rebuild_tree()
            self.controller.storage.mark_dirty()
            self.controller.update_preview(base)

        except Exception as e:
            messagebox.showerror("Fehler beim Zusammenführen", str(e))
        finally:
            self.controller.set_busy(False)

    def reset_compression_for_selection(self):
        selected_ids = self.controller.tree_view.tree.selection()
        if not selected_ids:
            messagebox.showinfo("Hinweis", "Bitte einen Knoten auswählen.")
            return

        try:
            self.controller.set_busy(True)
            self.controller.storage.mark_dirty()

            for item_id in selected_ids:
                root_node = self.controller.tree_view.nodes_by_id.get(item_id)
                if not root_node:
                    continue

                messagebox.showinfo("Kompression zerstören",
                    f'Die Kompression des Knotens "{root_node.name}" wird zurückgesetzt.\n'
                    f'Dies betrifft ggf. alle enthaltenen Unterknoten.')
                root_node.reset_compression()

            self.controller.update_preview(self.controller.selected_node)
        except Exception as e:
            messagebox.showerror("Fehler", f"Kompression konnte nicht zurückgesetzt werden:\n{e}")
        finally:
            self.controller.tree_view.refresh_colors()
            self.controller.set_busy(False)


    def import_pdf(self):
        from pdf_storage import create_wrapper_node

        filetypes = UniversalImporter.get_filetypes_for_dialog()
        paths = filedialog.askopenfilenames(filetypes=filetypes)

        new_nodes_imported = False  # Flag für spätere Farbanpassung

        self.controller.set_busy(True)
        for path in paths:
            try:

                if (
                    path.lower().endswith(".belegtool")
                    and (
                        self.controller.storage is None
                        or not self.controller.storage.root.children
                    )
                ):
                    self.controller.storage = PDFStorage(path)
                    self.controller.storage.filename = path
                    self.controller.storage.save_path = path

                    self.controller.tree_view.rebuild_tree()
                    new_nodes_imported = True
                    continue


                if path.lower().endswith((".pdf", ".belegtool", ".zip", ".tar", ".tgz", ".tar.gz", ".eml", ".msg")):
                    temp_storage = PDFStorage(path)
                    wrapper_node = create_wrapper_node(temp_storage, path)

                    if not self.controller.storage:
                        self.controller.storage = PDFStorage()

                    root_id = None
                    for item_id, node in self.controller.tree_view.nodes_by_id.items():
                        if node == self.controller.storage.root:
                            root_id = item_id
                            break

                    if root_id is None:
                        root_id = self.controller.tree_view._populate(self.controller.storage.root, parent="")
                        self.controller.tree_view.tree.update_idletasks()

                    self.controller.storage.root.add_child(wrapper_node)
                    self.controller.tree_view._populate(wrapper_node, parent=root_id)
                    self.controller.tree_view.tree.update_idletasks()

                    self.controller.storage.mark_dirty()
                    new_nodes_imported = True
                    continue

                # Andere Formate (Word, Bilder etc.)
                result = UniversalImporter.convert(path)
                self.controller.tree_view.import_pdf(result.data, name=result.name)
                self.controller.tree_view.tree.update_idletasks()
                new_nodes_imported = True

            except Exception as e:
                messagebox.showerror("Fehler beim Import", f"{path}\n{e}")

        if new_nodes_imported:
            self.controller.tree_view.refresh_colors()
        self.controller.set_busy(False)


    def compress_selected(self):
        selected_ids = self.controller.tree_view.tree.selection()
        if not selected_ids:
            return
        try:
            self.controller.set_busy(True)
            self.controller.storage.mark_dirty()
            total = 0
            updated_node = None
            for item_id in selected_ids:
                node = self.controller.tree_view.nodes_by_id.get(item_id)
                if not node:
                    continue
                if node.is_folder:
                    for subnode in self.controller.storage.get_all_nodes():
                        if subnode.is_folder:
                            continue
                        if not subnode.is_compressed and not subnode.no_compression and subnode._is_descendant_of(node):
                            subnode.compress()
                            subnode.update_preview()
                            total += 1
                elif not node.is_compressed and not node.no_compression:
                    node.compress()
                    node.update_preview()
                    total += 1
                updated_node = node

            if updated_node:
                self.controller.update_preview(updated_node)

            messagebox.showinfo("Erfolg", f"{total} PDFs wurden komprimiert.")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
        finally:
            self.controller.set_busy(False)

    def split_selected(self):
        selected_ids = self.controller.tree_view.tree.selection()
        if not selected_ids:
            return
        try:
            self.controller.set_busy(True)
            self.controller.storage.mark_dirty()
            total_new = 0
            last_updated = None
            for item_id in selected_ids:
                node = self.controller.tree_view.nodes_by_id.get(item_id)
                if not node or node.is_folder:
                    continue
                new_nodes = node.split()
                if not new_nodes:
                    continue
                parent_id = self.controller.tree_view.tree.parent(item_id)
                for new_node in new_nodes:
                    new_id = self.controller.tree_view.tree.insert(parent_id, "end", text=new_node.name)
                    self.controller.tree_view.nodes_by_id[new_id] = new_node
                    if node.parent:
                        node.parent.add_child(new_node)
                    total_new += 1
                move_plan = self.controller.storage.perform_move(new_nodes, node)
                self.controller.tree_view._apply_gui_move_plan(move_plan)

                node.update_preview()
                last_updated = node
            if last_updated:
                self.controller.update_preview(last_updated)
        except Exception as e:
            messagebox.showerror("Fehler beim Splitten", str(e))
        finally:
            self.controller.set_busy(False)

    def _do_save(self, path: str = None):
        try:
            self.controller.set_busy(True)
            self.controller.storage.save(path)
            messagebox.showinfo("Erfolg", "Datei gespeichert.")
        except Exception as e:
            messagebox.showerror("Fehler beim Speichern", str(e))
        finally:
            self.controller.set_busy(False)

    def save_automatic(self):
        if not self.controller.storage:
            return
        if not self.controller.storage.save_path:
            self.save_as()
            return
        self._do_save()

    def save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".belegtool",
            filetypes=[("BelegTool-Dateien", "*.belegtool"), ("Alle Dateien", "*.*")]
        )
        if path:
            self._do_save(path)


    def export_selected(self):
        if not self.controller.storage:
            return
        selected_ids = self.controller.tree_view.tree.selection()
        if not selected_ids:
            messagebox.showinfo("Hinweis", "Bitte mindestens einen Knoten auswählen.")
            return

        nodes = [
            self.controller.tree_view.nodes_by_id[iid]
            for iid in selected_ids
            if iid in self.controller.tree_view.nodes_by_id
        ]
        if not nodes:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".belegtool",
            filetypes=[
                ("BelegTool-Dateien", "*.belegtool"),
                ("PDF-Dateien", "*.pdf"),
                ("Alle Dateien", "*.*"),
            ]
        )
        if not path:
            return

        try:
            self.controller.set_busy(True)

            if path.lower().endswith(".pdf"):
                from toc_export import export_pdf_with_toc, export_pdf_split_with_toc, count_total_pages
                total = count_total_pages(nodes)

                if total > 100:
                    max_per_file = self._ask_split_options(total)
                    if max_per_file is None:
                        return  # abgebrochen
                    if max_per_file == 0:
                        export_pdf_with_toc(nodes, path)
                        messagebox.showinfo("Exportiert", f"Exportiert nach:\n{path}")
                    else:
                        created = export_pdf_split_with_toc(nodes, path, max_per_file)
                        files_str = "\n".join(os.path.basename(p) for p in created)
                        messagebox.showinfo("Exportiert",
                                            f"{len(created)} Datei(en) erstellt:\n{files_str}")
                else:
                    export_pdf_with_toc(nodes, path)
                    messagebox.showinfo("Exportiert", f"Exportiert nach:\n{path}")
            else:
                self.controller.storage.export_selection(nodes, path)
                messagebox.showinfo("Exportiert", f"Auswahl exportiert nach:\n{path}")

        except Exception as e:
            messagebox.showerror("Fehler beim Exportieren", str(e))
        finally:
            self.controller.set_busy(False)

    def _ask_split_options(self, total_pages: int) -> Optional[int]:
        """
        Zeigt Dialog zur Aufteilungsoption.
        Gibt None bei Abbruch zurück, 0 für keine Aufteilung, sonst max Seiten pro Datei.
        """
        result = [None]

        dialog = tk.Toplevel(self.controller)
        dialog.title("Exportoptionen")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.focus_set()

        tk.Label(
            dialog,
            text=f"Die Auswahl umfasst {total_pages} Seiten.\n"
                 "In mehrere Dateien aufteilen?",
            justify="left", padx=15, pady=10
        ).pack()

        split_var = tk.BooleanVar(value=True)
        pages_var = tk.IntVar(value=100)

        opt_frame = tk.Frame(dialog)
        opt_frame.pack(padx=15, pady=5)

        tk.Radiobutton(
            opt_frame, text="Nein — als eine Datei exportieren",
            variable=split_var, value=False
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=2)

        tk.Radiobutton(
            opt_frame, text="Ja — maximal",
            variable=split_var, value=True
        ).grid(row=1, column=0, sticky="w")

        ttk.Spinbox(opt_frame, from_=10, to=2000, textvariable=pages_var, width=7)\
            .grid(row=1, column=1, padx=5)

        tk.Label(opt_frame, text="Seiten pro Datei")\
            .grid(row=1, column=2, sticky="w")

        def on_ok():
            result[0] = pages_var.get() if split_var.get() else 0
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=(5, 15))
        tk.Button(btn_frame, text="Exportieren", width=14, command=on_ok).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Abbrechen",   width=14, command=on_cancel).pack(side="left", padx=5)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.wait_window()
        return result[0]

    def debug_output(self):
        storage = self.controller.storage
        tree = self.controller.tree_view

        logger.debug("=== Sichtbare TreeView-Knoten ===")
        for item_id in tree.tree.get_children(""):
            self._print_recursive_tree_nodes(item_id, tree, level=0)

        logger.debug("=== Alle PDF-Knoten (rekursiv aus Speicherbaum) ===")
        for node in storage.get_all_nodes():
            if not node.is_folder:
                uid = getattr(node, "uid", "–")
                logger.debug("- %s | UID: %s | Seiten: %d", node.name, uid, node.pdf_length)

    def _print_recursive_tree_nodes(self, item_id, tree, level):
        node = tree.nodes_by_id.get(item_id)
        indent = "  " * level
        uid = getattr(node, "uid", "–")
        num_images = len(node.current_preview_images) if node else 0
        logger.debug("%s- %s | UID: %s | Images: %d", indent, node.name, uid, num_images)

        for child_id in tree.tree.get_children(item_id):
            self._print_recursive_tree_nodes(child_id, tree, level + 1)


