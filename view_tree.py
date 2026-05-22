# view_tree.py
import tkinter as tk
from tkinterdnd2 import DND_FILES
from pdf_storage import PDFStorage
from pdf_node import PDFNode
from universal_importer import UniversalImporter
from tkinter import Menu, ttk, messagebox
import io
from typing import Union, List, Dict, Optional, Any
from pdf_storage import PDFStorage, create_wrapper_node
import traceback
import os
from universal_importer import UniversalImporter


class TreeViewFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.tree = ttk.Treeview(self, show="tree")


        self.tree_frame = ttk.Frame(self)
        self.tree_frame.pack(side="top", fill="both", expand=True)

        self.tree = ttk.Treeview(self.tree_frame, show="tree")
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
            print("[INFO] DnD nicht verfügbar – Tree läuft trotzdem.")

        # Kontextmenü mit rechter Maustaste
        self.tree.bind("<Button-3>", self._on_right_click)

        # Drag
        self.tree.bind("<ButtonPress-3>", self._on_mouse_down_context)
        self.tree.bind("<B3-Motion>", self._on_mouse_drag_context)
        self.tree.bind("<ButtonRelease-3>", self._on_mouse_up_context)
        self._drag_in_progress = False


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
        # self.context_menu.add_command(label="Komprimieren", command=self._ctx_compress)
        self.context_menu.add_command(label="Splitten", command=self._ctx_split)
        self.context_menu.add_command(label="Zusammenführen", command=self._ctx_merge)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Vorjahreswert", command=lambda: self._ctx_set_status("vorjahreswert"))
        self.context_menu.add_command(label="Zu erfassen", command=lambda: self._ctx_set_status("zu erfassen"))
        self.context_menu.add_command(label="Erfasst", command=lambda: self._ctx_set_status("erfasst"))
        self.context_menu.add_separator()
        # self.context_menu.add_command(label="Original zerstören", command=self._ctx_commit)
        # self.context_menu.add_command(label="Kompression zerstören", command=self._ctx_reset_compression)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Ordner innerhalb", command=self._ctx_add_inside)
        self.context_menu.add_command(label="Ordner unterhalb", command=self._ctx_add_below)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Löschen", command=self._ctx_delete)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Umbenennen", command=self._ctx_rename)


        self.tree.tag_configure("status_erfasst_light", foreground="green")
        self.tree.tag_configure("status_erfasst_dark", foreground="green")

        self.tree.tag_configure("status_zu_erfassen_light", foreground="blue", background="#ddeeff")
        self.tree.tag_configure("status_zu_erfassen_dark", foreground="blue", background="#99aacc")

        self.tree.tag_configure("status_vorjahreswert_light", foreground="red", background="#ffdada")
        self.tree.tag_configure("status_vorjahreswert_dark", foreground="red", background="#dd8888")


        self.nodes_by_id = {}

    def _on_delete_key(self, event):
        self.controller.control_panel.delete_selected()


    def _on_mouse_down_context(self, event):
        self._drag_start_items = self.tree.selection()
        self._drag_motion_triggered = False

        if self._drag_start_items:
            for iid in self._drag_start_items:
                node = self.nodes_by_id.get(iid)
                # if node:
                    # print(f" - {node.name} | uid={node.uid} | id={id(node)}")

    def _on_mouse_drag_context(self, event):
        self._drag_motion_triggered = True

    def _on_mouse_up_context(self, event):
        if self._drag_in_progress:
            print("[WARN] Dragloop erkannt – wird abgebrochen")
            return
        self._drag_in_progress = True

        target_iid = self.tree.identify_row(event.y)

        # Wenn kein Drag oder keine Startselektion → evtl. Kontextmenü
        if not self._drag_motion_triggered or not self._drag_start_items:
            if target_iid and target_iid in self.tree.selection():
                self.tree.focus(target_iid)
                self.tree.focus_set()
                self.context_menu.tk_popup(event.x_root, event.y_root)
                self.context_menu.grab_release()
                self._drag_in_progress = False
            return

        target_node = self.nodes_by_id.get(target_iid) if target_iid else None

        selected_nodes = [
            self.nodes_by_id[iid]
            for iid in self._drag_start_items
            if iid in self.nodes_by_id
        ]

        if not target_node:
            print("[WARN] Kein gültiges Ziel zum Kopieren.")
            self._drag_in_progress = False
            return


        if event.state & 0x4:  # STRG gedrückt
            # STRG gedrückt → Kopieren
            copies = [n.copy() for n in selected_nodes]
            for copy in copies:
                self.controller.storage.root.add_child(copy)
            for copy in copies:
                self.controller.tree_view._populate(copy, parent="")

            move_plan = self.controller.storage.perform_move(copies, target_node)
            self._apply_gui_move_plan(move_plan)
        else:
            if target_node:

                # Zyklische Verschiebung verhindern (z. B. Ordner in sich selbst oder Kind)
                if any(target_node._is_descendant_of(n) or target_node == n for n in selected_nodes):
                    messagebox.showwarning(
                        "Ungültiges Ziel",
                        "Ein Knoten darf nicht in sich selbst oder seine Nachfahren verschoben werden."
                    )
                    self._drag_in_progress = False
                    return

                move_plan = self.controller.storage.perform_move(selected_nodes, target_node)
                self._apply_gui_move_plan(move_plan)

        self._drag_motion_triggered = False
        self.controller.storage.mark_dirty()
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


    def _on_drop_node(self, event):
        target_item_id = self.tree.identify_row(event.y)
        if not target_item_id:
            return

        target_node = self.nodes_by_id.get(target_item_id)
        if not target_node:
            return

        selected_ids = sorted(
            getattr(self, "_drag_selection", self.tree.selection()),
            key=lambda iid: self.tree.index(iid)
        )

        if not selected_ids:
            return

        try:
            if target_node.is_folder:
                new_parent = target_node
                insert_index = len(new_parent.children)
            else:
                new_parent = target_node.parent
                if not new_parent:
                    raise ValueError("Zielknoten hat keinen Elternknoten")
                insert_index = new_parent.children.index(target_node) + 1

            for item_id in selected_ids:
                node = self.nodes_by_id.get(item_id)
                if not node or node == target_node:
                    continue

                node.move(new_parent)
                if node in new_parent.children:
                    new_parent.children.remove(node)
                new_parent.children.insert(insert_index, node)
                insert_index += 1

            self.controller.storage.mark_dirty()
            self.rebuild_tree()

        except Exception as e:
            messagebox.showerror("Fehler beim Drop", str(e))

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

                    if file_path.lower().endswith((".pdf", ".belegtool", ".zip", ".eml", ".msg")):
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

            node_text = node.name
            tag = self._get_node_tag(node)
            item_id = self.tree.insert(parent, "end", text=node_text, open=True, tags=(tag,))


            print(f"[DBG] Insert: {node.name} | Status: {node.status} | is_compressed: {node.is_compressed}")



            self.nodes_by_id[item_id] = node

            # ✅ Farben direkt nach dem Einfügen anwenden
            self._apply_colors_recursive(node, item_id)

            # GUI stabilisieren
            self.tree.update_idletasks()

            # 🔧 Reihenfolge absichern
            sortable_children = sorted(
                node.children,
                key=lambda c: (c.position if c.position is not None else float("inf"), c.name)
            )

            # 🧪 Prüfe auf Duplikate oder fehlende Positionen
            positions_seen = set()
            positions_valid = all(
                c.position is not None and c.position not in positions_seen and not positions_seen.add(c.position)
                for c in sortable_children
            )

            # 🔁 Wenn ungültig: neue Positionen nach sortierter Reihenfolge vergeben
            if not positions_valid:
                for i, child in enumerate(sortable_children):
                    child.position = i

            # 📋 Einfügen in stabiler Reihenfolge
            for child in sorted(node.children, key=lambda c: c.position):
                self._populate(child, item_id)

        except Exception as e:
            messagebox.showerror(
                "FEHLER in TreeView",
                f"Knoten: {node.name}\nParent-ID: {parent}\nFehler: {e}"
            )
            traceback.print_exc()

    def _apply_colors_recursive(self, node: PDFNode, item_id: str):
        tag = self._get_node_tag(node)

        print(f"[DBG] apply_color: {node.name} → {tag} (item_id={item_id})")

        self.tree.item(item_id, tags=(tag,))
        for cid in self.tree.get_children(item_id):
            child_node = self.nodes_by_id.get(cid)
            if child_node:
                self._apply_colors_recursive(child_node, cid)


    def _get_node_tag(self, node: PDFNode) -> str:
        base = f"status_{node.status.replace(' ', '_')}"
        suffix = "dark" if node.is_compressed else "light"

        tag = f"{base}_{suffix}"
        try:
            print(f"[DBG] Tag-Berechnung: {node.name} → {tag}")
        except Exception:
            pass
        return tag


    def refresh_colors(self):
        def apply_colors_recursive(node: PDFNode, item_id: str):
            tag = self._get_node_tag(node)
            self.tree.item(item_id, tags=(tag,))
            for cid in self.tree.get_children(item_id):
                child_node = self.nodes_by_id.get(cid)
                if child_node:
                    apply_colors_recursive(child_node, cid)

        for item_id in self.tree.get_children(""):
            node = self.nodes_by_id.get(item_id)
            if node:
                apply_colors_recursive(node, item_id)


    def _apply_gui_move_plan(self, move_plan: List[Dict[str, Any]]):
        """
        Verschiebt Knoten im TreeView gemäß übergebenem Move-Plan.
        """
        for entry in move_plan:
            node = next(
                (n for n in self.nodes_by_id.values() if n.uid == entry["uid"]),
                None
            )
            parent = next(
                (n for n in self.nodes_by_id.values() if n.uid == entry["parent_uid"]),
                None
            )

            node_iid = self._get_iid_for_node(node)
            parent_iid = self._get_iid_for_node(parent) if parent else ""


            # DEBUG
            # node_name = node.name
            # parent_name = parent.name if parent else "Wurzel"
            # position = entry["index"]
            # messagebox.showinfo(
            #     "Verschiebe Knoten",
            #     f"Verschiebe '{node_name}' → Zielordner '{parent_name}' an Position {position}"
            # )

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


    def import_pdf(self, source: Union[str, io.BytesIO], name: Optional[str] = None):
        try:
            if isinstance(source, io.BytesIO):
                name = name or "importiert.pdf"
                converted = UniversalImporter.convert(source, name=name)
                node = PDFNode.from_pdf(name=converted.name, source=converted.data.getvalue())

                if not self.controller.storage:
                    self.controller.storage = PDFStorage()
                    self.rebuild_tree()
                self.controller.storage.mark_dirty()
                self.controller.storage.root.add_child(node)
                self.rebuild_tree()
                return

            elif isinstance(source, str):
                with open(source, "rb") as f:
                    data = f.read()
                converted = UniversalImporter.convert(data, name=os.path.basename(source))
                node = PDFNode.from_pdf(name=converted.name, source=converted.data.getvalue())

                if not self.controller.storage:
                    self.controller.storage = PDFStorage()
                    self.controller.storage.root.add_child(node)

                    print(f"[DEBUG] import_pdf aufgerufen für: {name}")
                    self.controller.storage.debug_print_structure()

                    self.rebuild_tree()
                    return
                else:
                    temp = PDFStorage()
                    temp.root.add_child(node)
                    for new_node in temp.root.children:
                        self.controller.storage.root.add_child(new_node)

                    print(f"[DEBUG] import_pdf aufgerufen für: {name}")
                    self.controller.storage.debug_print_structure()

                    self.rebuild_tree()
                    self.controller.storage.mark_dirty()
                    return

            else:
                raise TypeError("Ungültiger Typ für import_pdf(): erwartet str oder BytesIO")

        except Exception as e:
            messagebox.showerror("Fehler beim Import", str(e))

    def rebuild_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.nodes_by_id.clear()
        self._populate(self.controller.storage.root, parent="")
        self.tree.update_idletasks()  # GUI-Sicherheit
        self.refresh_colors()   

    def _reselect_node_by_uid(self, uid: str):
        # print(f"[DEBUG] Suche UID: {uid}")
        dupe_check = {}

        for iid, node in self.nodes_by_id.items():
            print(f"  Tree-ID: {iid}, Name: {node.name}, UID: {node.uid}")
            if node.uid in dupe_check:
                print(f"  ❗ Doppelte UID erkannt: {node.uid} bei {node.name}")
            dupe_check[node.uid] = iid

        new_id = next(
            (iid for iid, n in self.nodes_by_id.items()
             if getattr(n, "uid", None) == uid),
            None
        )

        if not new_id:
            print(f"[WARNUNG] Kein passender TreeView-Knoten für UID {uid} gefunden.")
            return

        print(f"[OK] Selektiere Tree-ID: {new_id}")
        self.tree.selection_set(new_id)
        self.tree.focus(new_id)
        self.tree.see(new_id)
        self.controller.update_preview(self.nodes_by_id[new_id])

    def _get_iid_for_node(self, node):
        for iid, n in self.nodes_by_id.items():
            if n == node:
                return iid
        return None



    def _reorder_children(self, parent_node):
        for i, child in enumerate(parent_node.children):
            child.position = i


    def _get_selected_node(self):
        selected = self.tree.selection()
        if not selected:
            return None
        iid = selected[0]
        return self.nodes_by_id.get(iid)



    def _move_node(self, direction):
        # print(f"[DEBUG] move_node aufgerufen: direction={direction}")
        # print(f"[DEBUG] Auswahl: {self.tree.selection()}")

        if len(self.tree.selection()) > 1:
            print("[INFO] Mehrfachauswahl erkannt – Bewegung wird unterdrückt.")
            return

        node = self._get_selected_node()
        if not node or not node.parent:
            return

        # print(f"[DEBUG] ausgewählter Node: {node.name if node else 'None'}")


        uid = node.uid
        siblings = node.parent.children
        index = siblings.index(node)
        new_index = None
        parent_id = None

        # print(f"[DEBUG] direction {direction} und Länge siblings von {len(siblings)}")


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
            new_index = grandparent.children.index(node.parent) + 1
            node.change_parent(grandparent)
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


