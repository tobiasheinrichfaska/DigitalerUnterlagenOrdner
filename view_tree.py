import tkinter as tk
from tkinterdnd2 import DND_FILES
from pdf_storage import PDFStorage, create_wrapper_node
from tkinter import simpledialog
from pdf_node import PDFNode
from universal_importer import UniversalImporter
from tkinter import Menu, ttk, messagebox
import io
from typing import Union, List, Dict, Optional, Any
import os
from log_config import logger


class TreeViewFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        self.tree_frame = ttk.Frame(self)
        self.tree_frame.pack(side="top", fill="both", expand=True)

        self.tree = ttk.Treeview(self.tree_frame, show="tree", selectmode="extended")
        self.v_scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.h_scrollbar = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)

        self.tree.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)

        self.v_scrollbar.pack(side="right", fill="y")
        self.h_scrollbar.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)


        try:
            self.tree.drop_target_register(DND_FILES)
            self.tree.dnd_bind('<<Drop>>', self._on_drop_pdf)
        except tk.TclError:
            logger.info("DnD nicht verfügbar – Tree läuft trotzdem.")

        # Kontextmenü mit rechter Maustaste
        self.tree.bind("<Button-3>", self._on_right_click)

        # Left-button drag-and-drop (move = plain drag, copy = Ctrl+drag)
        # Binding WITHOUT add=True runs BEFORE the class binding → returning "break"
        # prevents the class-level range-selection only when we are in drag mode.
        self.tree.bind("<ButtonPress-1>",   self._on_left_press)
        self.tree.bind("<B1-Motion>",       self._on_left_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_left_release, add=True)

        self._drag_in_progress  = False
        self._left_press_item   = None
        self._left_press_pos    = None
        self._left_drag_active  = False
        self._left_sel_at_press = []
        self._defer_single_sel  = False
        self._drag_highlight    = None


        # F2 = Umbenennen
        self.tree.bind("<F2>", self._on_rename_key)
        self.tree.bind("<Delete>", self._on_delete_key)
        self.tree.bind("<Control-Up>", lambda e: self._move_node("up") or "break")
        self.tree.bind("<Control-Down>", lambda e: self._move_node("down") or "break")
        self.tree.bind("<Control-Left>", lambda e: self._move_node("left") or "break")
        self.tree.bind("<Control-Right>", lambda e: self._move_node("right") or "break")


        # Auswahlwechsel
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Umbenennen",     accelerator="F2",   command=self._ctx_rename)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Exportieren…",                       command=self._ctx_export)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Splitten",                           command=self._ctx_split)
        self.context_menu.add_command(label="Zusammenführen",                     command=self._ctx_merge)
        self.context_menu.add_separator()
        _status_submenu = tk.Menu(self.context_menu, tearoff=0)
        _status_submenu.add_command(label="Vorjahreswert", command=lambda: self._ctx_set_status("vorjahreswert"))
        _status_submenu.add_command(label="Zu erfassen",   command=lambda: self._ctx_set_status("zu erfassen"))
        _status_submenu.add_command(label="Erfasst",       command=lambda: self._ctx_set_status("erfasst"))
        self.context_menu.add_cascade(label="Status", menu=_status_submenu)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Ordner innerhalb",                   command=self._ctx_add_inside)
        self.context_menu.add_command(label="Ordner unterhalb",                   command=self._ctx_add_below)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Löschen",       accelerator="Entf",  command=self._ctx_delete)


        self.tree.tag_configure("status_erfasst_light", foreground="green")
        self.tree.tag_configure("status_erfasst_dark", foreground="green")

        self.tree.tag_configure("status_zu_erfassen_light", foreground="blue", background="#ddeeff")
        self.tree.tag_configure("status_zu_erfassen_dark", foreground="blue", background="#99aacc")

        self.tree.tag_configure("status_vorjahreswert_light", foreground="red", background="#ffdada")
        self.tree.tag_configure("status_vorjahreswert_dark", foreground="red", background="#dd8888")

        self.tree.tag_configure("drag_target", background="#cce8ff")

        self.nodes_by_id = {}          # iid -> PDFNode
        self._iid_by_uid = {}          # PDFNode.uid -> iid (reverse index, O(1) lookups)

    def clear_node_index(self):
        """Clear both the iid->node map and the uid->iid reverse index together."""
        self.nodes_by_id.clear()
        self._iid_by_uid.clear()

    def register_node(self, iid: str, node) -> None:
        """Record an iid<->node mapping in both the forward and reverse index."""
        self.nodes_by_id[iid] = node
        self._iid_by_uid[node.uid] = iid

    def unregister_node(self, iid: str) -> None:
        """Remove an iid from both indices (keeps the reverse index consistent)."""
        node = self.nodes_by_id.pop(iid, None)
        if node is not None and self._iid_by_uid.get(node.uid) == iid:
            del self._iid_by_uid[node.uid]

    def _on_delete_key(self, event):
        self.controller.control_panel.delete_selected()


    def _on_left_press(self, event):
        item = self.tree.identify_row(event.y)
        is_shift = bool(event.state & 0x1)
        is_ctrl  = bool(event.state & 0x4)

        self._left_press_item   = item
        self._left_press_pos    = (event.x, event.y)
        self._left_drag_active  = False
        self._defer_single_sel  = False
        self._left_sel_at_press = list(self.tree.selection())

        # Clicking an already-selected item without modifiers: hold the multi-
        # selection so the user can start a drag. Defer single-select to release.
        if item and item in self.tree.selection() and not is_shift and not is_ctrl:
            self.tree.focus(item)
            self.tree.focus_set()
            self._defer_single_sel = True
            return "break"   # prevent class binding from clearing multi-selection

    def _on_left_motion(self, event):
        if not self._left_press_item:
            return   # no "break" -> class binding handles range selection

        dx = abs(event.x - self._left_press_pos[0])
        dy = abs(event.y - self._left_press_pos[1])
        if dx <= 5 and dy <= 5:
            return   # below threshold -> class binding handles range selection

        # Threshold crossed: commit to drag mode
        if not self._left_drag_active:
            self._left_drag_active = True
            self._defer_single_sel = False
            sel = self._left_sel_at_press or ([self._left_press_item] if self._left_press_item else [])
            self.tree.selection_set(sel)   # restore selection (undo any partial range-select)

        # Highlight the row under the cursor (but not one of the dragged items)
        target = self.tree.identify_row(event.y)
        if target != self._drag_highlight:
            if self._drag_highlight:
                self.tree.tag_remove("drag_target", self._drag_highlight)
            if target and target not in self._left_sel_at_press:
                self.tree.tag_add("drag_target", target)
                self._drag_highlight = target
            else:
                self._drag_highlight = None

        return "break"   # prevent class binding from doing range selection

    def _on_left_release(self, event):
        if self._drag_highlight:
            self.tree.tag_remove("drag_target", self._drag_highlight)
            self._drag_highlight = None

        if self._left_drag_active:
            self._execute_left_drop(event)
        elif self._defer_single_sel and self._left_press_item:
            # No drag happened -- apply the deferred single-select
            self.tree.selection_set(self._left_press_item)
            self.tree.focus(self._left_press_item)

        self._left_drag_active = False
        self._defer_single_sel = False
        self._left_press_item  = None

    def _execute_left_drop(self, event):
        if self._drag_in_progress:
            return
        self._drag_in_progress = True
        try:
            target_iid  = self.tree.identify_row(event.y)
            target_node = self.nodes_by_id.get(target_iid) if target_iid else None
            selected_nodes = [
                self.nodes_by_id[iid]
                for iid in self._left_sel_at_press
                if iid in self.nodes_by_id
            ]

            if not selected_nodes or not target_node:
                return

            is_ctrl = bool(event.state & 0x4)

            if is_ctrl:
                filtered = self._resolve_conflict(selected_nodes)
                if filtered is None:
                    return
                copies = [n.copy() for n in filtered]
                for c in copies:
                    self.controller.storage.root.add_child(c)
                    self._populate(c, parent="")
                move_plan = self.controller.storage.perform_move(copies, target_node)
            else:
                if any(target_node._is_descendant_of(n) or target_node == n for n in selected_nodes):
                    messagebox.showwarning(
                        "Invalid target",
                        "A node cannot be moved into itself or its descendants."
                    )
                    return
                filtered = self._resolve_conflict(selected_nodes)
                if filtered is None:
                    return
                move_plan = self.controller.storage.perform_move(filtered, target_node)

            self._apply_gui_move_plan(move_plan)
            self.controller.storage.mark_dirty()
            self.controller._update_menu_states()
        finally:
            self._drag_in_progress = False

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        if item not in self.tree.selection():
            self.tree.selection_set(item)
        self.context_menu.post(event.x_root, event.y_root)

    def _on_rename_key(self, event):
        self._ctx_rename()


    def _ctx_export(self):
        self.controller.control_panel.export_selected()

    def _ctx_compress(self):
        self.controller.control_panel.compress_selected()

    def _ctx_split(self):
        self.controller.control_panel.split_selected()

    def _ctx_merge(self):
        self.controller.control_panel.merge_selected()

    def _ctx_commit(self):
        self.controller.control_panel.commit_changes_for_selection()

    def _ctx_reset_compression(self):
        self.controller.control_panel.reset_compression_for_selection()

    def _ctx_set_status(self, status):
        self.controller.control_panel.set_status_for_selection(status)

    def _ctx_add_inside(self):
        self.controller.control_panel.add_folder_inside()

    def _ctx_add_below(self):
        self.controller.control_panel.add_folder_below()

    def _ctx_delete(self):
        self.controller.control_panel.delete_selected()

    def _ctx_rename(self):
        self.controller.control_panel.rename_selected()

    def _on_drop_pdf(self, event):
        self.controller.set_busy(True)
        try:
            files = self.master.tk.splitlist(event.data)
            for file_path in files:
                try:
                    ext = file_path.lower().split(".")[-1]

                    if file_path.lower().endswith((".pdf", ".belegtool", ".zip", ".tar", ".tgz", ".tar.gz", ".eml", ".msg")):
                        temp_storage = PDFStorage(file_path)

                        if not self.controller.storage:
                            self.controller.storage = PDFStorage()

                        wrapper_node = create_wrapper_node(temp_storage, file_path)
                        self.controller.storage.root.add_child(wrapper_node)
                        self.rebuild_tree()
                        self.controller.storage.mark_dirty()
                    else:
                        result = UniversalImporter.convert(file_path)
                        self.import_pdf(result.data, name=result.name)

                except Exception as inner:
                    messagebox.showerror("Fehler beim Import", f"{file_path}\n{inner}")
        finally:
            self.controller.set_busy(False)

    def _populate(self, node: PDFNode, parent=""):
        try:
            parent = parent or ""

            # Schutz: Parent muss im TreeView existieren
            if parent and not self.tree.exists(parent):
                raise RuntimeError(f"Ungültiger TreeView-Parent: {parent}")

            tag = self._get_node_tag(node)
            item_id = self.tree.insert(parent, "end", text=node.name, open=True, tags=(tag,))

            self.register_node(item_id, node)
            self._apply_colors_recursive(node, item_id)
            self.tree.update_idletasks()

            sortable_children = sorted(
                node.children,
                key=lambda c: (c.position if c.position is not None else float("inf"), c.name)
            )

            positions_seen = set()
            positions_valid = all(
                c.position is not None and c.position not in positions_seen and not positions_seen.add(c.position)
                for c in sortable_children
            )

            if not positions_valid:
                for i, child in enumerate(sortable_children):
                    child.position = i

            for child in sorted(node.children, key=lambda c: c.position):
                self._populate(child, item_id)

        except Exception as e:
            logger.exception("FEHLER in TreeView – Knoten: %s, Parent-ID: %s", node.name, parent)
            messagebox.showerror(
                "FEHLER in TreeView",
                f"Knoten: {node.name}\nParent-ID: {parent}\nFehler: {e}"
            )

    def _apply_colors_recursive(self, node: PDFNode, item_id: str):
        tag = self._get_node_tag(node)
        self.tree.item(item_id, tags=(tag,))
        for cid in self.tree.get_children(item_id):
            child_node = self.nodes_by_id.get(cid)
            if child_node:
                self._apply_colors_recursive(child_node, cid)


    def _get_node_tag(self, node: PDFNode) -> str:
        base = f"status_{node.status.replace(' ', '_')}"
        suffix = "dark" if node.is_compressed else "light"
        return f"{base}_{suffix}"


    def refresh_colors(self):
        for item_id in self.tree.get_children(""):
            node = self.nodes_by_id.get(item_id)
            if node:
                self._apply_colors_recursive(node, item_id)


    def _apply_gui_move_plan(self, move_plan: List[Dict[str, Any]]):
        """
        Verschiebt Knoten im TreeView gemäß übergebenem Move-Plan.
        """
        for entry in move_plan:
            node_iid = self._iid_by_uid.get(entry["uid"])
            parent_iid = self._iid_by_uid.get(entry["parent_uid"], "")

            if node_iid is None:
                continue

            self.tree.move(node_iid, parent_iid, entry["index"])
            self.tree.update_idletasks()

    def _on_tree_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        item_id = selection[0]
        node = self.nodes_by_id.get(item_id)
        if node:
            self.controller.update_preview(node)
        self.controller._update_menu_states()


    def import_pdf(self, source: Union[str, io.BytesIO], name: Optional[str] = None):
        try:
            if isinstance(source, io.BytesIO):
                # Caller already ran UniversalImporter.convert — source is already PDF bytes.
                name = name or "importiert.pdf"
                node = PDFNode.from_pdf(name=name, source=source.getvalue())

            elif isinstance(source, str):
                with open(source, "rb") as f:
                    data = f.read()
                converted = UniversalImporter.convert(data, name=os.path.basename(source))
                node = PDFNode.from_pdf(name=converted.name, source=converted.data.getvalue())

            else:
                raise TypeError("Ungültiger Typ für import_pdf(): erwartet str oder BytesIO")

            if not self.controller.storage:
                self.controller.storage = PDFStorage()
            self.controller.storage.root.add_child(node)
            self.controller.storage.mark_dirty()
            self.rebuild_tree()

        except Exception as e:
            messagebox.showerror("Fehler beim Import", str(e))

    def rebuild_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.clear_node_index()
        self._populate(self.controller.storage.root, parent="")
        self.tree.update_idletasks()  # GUI-Sicherheit
        self.refresh_colors()   

    def _reselect_node_by_uid(self, uid: str):
        new_id = self._iid_by_uid.get(uid)

        if not new_id:
            return

        self.tree.selection_set(new_id)
        self.tree.focus(new_id)
        self.tree.see(new_id)
        self.controller.update_preview(self.nodes_by_id[new_id])

    def _get_iid_for_node(self, node):
        if node is None:
            return None
        return self._iid_by_uid.get(node.uid)



    def _reorder_children(self, parent_node):
        for i, child in enumerate(parent_node.children):
            child.position = i


    def _get_selected_node(self):
        selected = self.tree.selection()
        if not selected:
            return None
        iid = selected[0]
        return self.nodes_by_id.get(iid)

    def _resolve_conflict(self, nodes: List['PDFNode']) -> Optional[List['PDFNode']]:
        """
        Prüft, ob die Selektion Eltern-Kind-Konflikte enthält (Ordner + enthaltene Knoten
        gleichzeitig markiert). Zeigt bei Konflikt einen Dialog mit drei Optionen:
          - 'Ordner verschieben' → Nachfahren aus Selektion entfernen
          - 'Nur markierte Elemente' → Vorfahren aus Selektion entfernen
          - 'Abbrechen' → None zurückgeben
        Ohne Konflikt wird die Originalliste unverändert zurückgegeben.
        """
        if not PDFStorage.has_parent_child_conflict(nodes):
            return nodes

        dialog = tk.Toplevel(self)
        dialog.title("Konflikt in Auswahl")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.focus_set()

        tk.Label(
            dialog,
            text=(
                "Die Auswahl enthält sowohl einen Ordner als auch darin enthaltene Elemente.\n"
                "Wie soll verschoben werden?"
            ),
            justify="left",
            padx=15, pady=10
        ).pack()

        result = [None]

        def choose(value):
            result[0] = value
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(padx=15, pady=(0, 15))

        tk.Button(
            btn_frame, text="Ganzen Ordner verschieben",
            width=28,
            command=lambda: choose("folder")
        ).grid(row=0, column=0, padx=5, pady=3)

        tk.Button(
            btn_frame, text="Nur markierte Elemente",
            width=28,
            command=lambda: choose("items")
        ).grid(row=1, column=0, padx=5, pady=3)

        tk.Button(
            btn_frame, text="Abbrechen",
            width=28,
            command=lambda: choose(None)
        ).grid(row=2, column=0, padx=5, pady=3)

        dialog.protocol("WM_DELETE_WINDOW", lambda: choose(None))
        self.wait_window(dialog)

        if result[0] == "folder":
            return PDFStorage.filter_keep_ancestors(nodes)
        elif result[0] == "items":
            return PDFStorage.filter_keep_descendants(nodes)
        else:
            return None



    def _move_node(self, direction):
        if len(self.tree.selection()) > 1:
            logger.debug("Mehrfachauswahl erkannt – Bewegung wird unterdrückt.")
            return

        node = self._get_selected_node()
        if not node or not node.parent:
            return

        uid = node.uid
        siblings = node.parent.children
        index = siblings.index(node)
        new_index = None
        parent_id = None


        if direction == "down" and index < len(siblings) - 1:
            new_index = index + 1
            # print(f"[DEBUG] verschiebe {node.name} von {index} nach {index + 1}")
            siblings[index], siblings[new_index] = siblings[new_index], siblings[index]
            self._reorder_children(node.parent)
            parent_id = self.tree.parent(self._get_iid_for_node(node))

        elif direction == "up" and index > 0:
            new_index = index - 1
            siblings[index], siblings[new_index] = siblings[new_index], siblings[index]
            self._reorder_children(node.parent)
            parent_id = self.tree.parent(self._get_iid_for_node(node))

        elif direction == "left" and node.parent.parent:
            grandparent = node.parent.parent
            old_parent = node.parent
            new_index = grandparent.children.index(old_parent) + 1
            node.change_parent(grandparent, index=new_index)
            self._reorder_children(old_parent)
            self._reorder_children(grandparent)
            parent_id = self._get_iid_for_node(grandparent)

        elif direction == "right" and index > 0 and getattr(siblings[index - 1], "is_folder", False):
            left_sibling = siblings[index - 1]
            new_index = "end"
            node.change_parent(left_sibling)
            self._reorder_children(left_sibling)
            parent_id = self._get_iid_for_node(left_sibling)
            new_index = left_sibling.children.index(node)
        else:
            return  # Keine gültige Bewegung möglich

        gui_id = self._get_iid_for_node(node)
        if new_index is None:
            parent_id = self.tree.parent(gui_id)
        else:
            self.tree.move(gui_id, parent_id, new_index)
            self.controller.storage.mark_dirty()


        self.after_idle(lambda uid=uid: self._reselect_node_by_uid(uid))


