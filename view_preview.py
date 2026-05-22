import tkinter as tk
from tkinter import ttk
from PIL import ImageTk, ImageDraw, ImageFont, Image
from typing import Optional
from tkinter import messagebox

class PreviewFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        self.image_refs = []
        self.zoom_level = 1.0
        self.zoom_auto = True
        self.show_original = False
        self.current_node = None
        self._poll_after_id = None

        # === Canvas (nimmt den gesamten verbleibenden Platz oben ein) ===
        self.canvas_frame = ttk.Frame(self)
        self.canvas = tk.Canvas(self.canvas_frame, bg="white")
        self.v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)
        self.v_scrollbar.pack(side="right", fill="y")
        self.h_scrollbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # === Commit-Zeile (ganz unten) ===
        self.commit_frame = ttk.Frame(self)
        self.commit_button = ttk.Button(self.commit_frame, text="✓ Lesbarkeit geprüft",
                                        command=self._on_destroy_original)
        self.commit_button.pack(pady=2)

        # === DPI / Kompression-Zeile ===
        self.compression_frame = ttk.Frame(self)
        ttk.Label(self.compression_frame, text="DPI:").pack(side="left", padx=(5, 2))
        self.slider_label_min = ttk.Label(self.compression_frame, text="50")
        self.slider_label_min.pack(side="left")
        self.slider = ttk.Scale(self.compression_frame, from_=50, to=300, orient="horizontal")
        self.slider.pack(side="left", fill="x", expand=True, padx=5)
        self.slider_label_max = ttk.Label(self.compression_frame, text="∞")
        self.slider_label_max.pack(side="left", padx=(0, 5))
        self.slider.bind("<Motion>", self._on_slider_hover)
        self.slider.bind("<Leave>", lambda e: self.slider_tooltip.place_forget())
        self.slider.bind("<ButtonRelease-1>", self._on_slider_released)
        self.reset_button = ttk.Button(self.compression_frame, text="Kompression wieder erlauben",
                                       command=self._on_reset_compression)
        self.reset_button.pack(side="left", padx=5)
        self.reset_button.pack_forget()

        self.slider_tooltip = tk.Label(self, text="", background="#ffffe0",
                                       relief="solid", borderwidth=1, font=("Arial", 9))
        self.slider_tooltip.place_forget()

        # === Methoden-Auswahl (konditional, zwischen DPI und Commit) ===
        self.method_frame = ttk.Frame(self)
        ttk.Label(self.method_frame, text="Kompression:").pack(side="left", padx=5)
        self.method_var = tk.StringVar()
        self.method_combo = ttk.Combobox(self.method_frame, textvariable=self.method_var,
                                         state="readonly", width=35)
        self.method_combo.pack(side="left", padx=5)
        self.method_combo.bind("<<ComboboxSelected>>", self._on_method_selected)

        # === Ansicht / Zoom-Zeile (direkt unterhalb des Canvas) ===
        self.view_frame = ttk.Frame(self)
        ttk.Label(self.view_frame, text="Ansicht:").pack(side="left", padx=(5, 2))
        self.zoom_label = ttk.Label(self.view_frame, text="100%")
        self.zoom_label.pack(side="left", padx=5)
        self.zoom_slider = ttk.Scale(self.view_frame, from_=100, to=400,
                                     orient="horizontal", command=self._on_zoom_changed)
        self.zoom_slider.set(100)
        self.zoom_slider.pack(side="left", fill="x", expand=True, padx=5)
        self.rotate_button = ttk.Menubutton(self.view_frame, text="⟳ Drehen")
        self.rotate_menu = tk.Menu(self.rotate_button, tearoff=0)
        self.rotate_menu.add_command(label="⟲ 90° links",  command=lambda: self._rotate_selected("left"))
        self.rotate_menu.add_command(label="⟳ 90° rechts", command=lambda: self._rotate_selected("right"))
        self.rotate_menu.add_command(label="⟲⟳ 180°",      command=lambda: self._rotate_selected("180"))
        self.rotate_button["menu"] = self.rotate_menu
        self.rotate_button.pack(side="left", padx=5)

        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
        self.canvas.bind("<MouseWheel>", self._on_ctrl_mousewheel)

        # === Pack-Reihenfolge: side="bottom" stapelt von unten nach oben ===
        self.commit_frame.pack(side="bottom", pady=4)                    # → ganz unten
        self.compression_frame.pack(side="bottom", pady=4, fill="x")    # → darüber
        # method_frame: konditional mit after=commit_frame
        self.view_frame.pack(side="bottom", pady=4, fill="x")            # → direkt unter Canvas
        self.canvas_frame.pack(side="top", fill="both", expand=True)

    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel_windows)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel_windows(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        direction = -1 if event.num == 4 else 1
        self.canvas.yview_scroll(direction, "units")

    def _on_ctrl_mousewheel(self, event):
        if event.state & 0x0004:
            factor = 1.1 if event.delta > 0 else 0.9
            self.zoom_level *= factor
            self.zoom_auto = False
            if self.current_node:
                self.show_previews(self.current_node)

    def _on_destroy_original(self):
        if not self.current_node:
            return
        try:
            self.current_node.commit_changes()
            self.show_previews(self.current_node)
            # Kompression dauerhaft deaktivieren
            self.current_node.no_compression = True
            self.current_node.current_pdf_data = None

            # Simuliere Slider am rechten Anschlag
            dpi_max = self.current_node.dpi_original or 350
            self.slider.set(dpi_max)
            self._update_slider_visibility()
        except Exception as e:
            messagebox.showerror("Fehler", f"Original konnte nicht ersetzt werden:\n{e}")


    def _zoom_in(self):
        self.zoom_level *= 1.1
        self.zoom_auto = False
        if self.current_node:
            self.show_previews(self.current_node)

    def _zoom_out(self):
        self.zoom_level /= 1.1
        self.zoom_auto = False
        if self.current_node:
            self.show_previews(self.current_node)

    def _enable_autozoom(self):
        self.zoom_auto = True
        self.zoom_level = 1.0
        if self.current_node:
            self.show_previews(self.current_node)

    def _draw_image_with_optional_border(self, img: Image.Image, draw_red: bool, label_text: Optional[str] = None) -> Image.Image:
        from PIL import ImageDraw, ImageFont

        resized = img.resize((int(img.width * self.zoom_level), int(img.height * self.zoom_level)))
        if draw_red:
            draw = ImageDraw.Draw(resized)
            draw.rectangle((0, 0, resized.width - 1, resized.height - 1), outline="red", width=5)
        if label_text:
            draw = ImageDraw.Draw(resized)
            font = ImageFont.load_default()
            try:
                bbox = draw.textbbox((0, 0), label_text, font=font)
                textwidth = bbox[2] - bbox[0]
                textheight = bbox[3] - bbox[1]
            except AttributeError:
                textwidth, textheight = draw.textsize(label_text, font=font)
            position = (10, resized.height - textheight - 10)
            draw.text(position, label_text, fill=(255, 0, 0), font=font)
        return resized

    def _render_node_images(self, node: 'PDFNode', y_offset: int, show_title: bool) -> int:
        from PIL import ImageDraw

        images = node.original_preview_images if self.show_original else node.current_preview_images

        if self.zoom_auto and images:
            canvas_width = self.canvas.winfo_width()
            if canvas_width <= 1:
                self.update_idletasks()
                canvas_width = self.canvas.winfo_width()
            page_width = images[0].width
            if page_width > 0:
                self.zoom_level = canvas_width / page_width * 0.95

        # ✅ Eindeutige zentrale Logik
        is_true_original = (
            self.show_original
            and node.dpi_original is None
            and not node.no_compression
        )

        if show_title:
            self.canvas.create_text(
                10, y_offset,
                anchor="nw",
                text=node.name,
                font=("Arial", 12, "bold"),
                fill="red" if is_true_original else "#006400"

            )
            y_offset += 20

        for i, img in enumerate(images):
            resized = img.resize((int(img.width * self.zoom_level), int(img.height * self.zoom_level)))
            draw = ImageDraw.Draw(resized)

            # 🔴 Roter Streifen oben, wenn wirklich Original
            if is_true_original:
                draw.line((0, 0, resized.width, 0), fill="red", width=4)

            tk_img = ImageTk.PhotoImage(resized)
            self.image_refs.append(tk_img)
            self.canvas.create_image(10, y_offset, anchor="nw", image=tk_img)
            y_offset += resized.height + 10

            # ➖ Trennlinie zwischen Seiten
            if i < len(images) - 1:
                self.canvas.create_line(
                    10, y_offset, resized.width + 10, y_offset,
                    fill="#bbbbbb", width=1
                )
                y_offset += 10

        return y_offset

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.rotate_button.config(state=state)
        self.commit_button.config(state=state)
        self.zoom_slider.config(state=state)
        try:
            self.slider.config(state=state)
        except Exception:
            pass

    def _schedule_poll(self, node):
        self._poll_after_id = self.after(150, lambda: self._poll_node_ready(node))

    def _poll_node_ready(self, node):
        self._poll_after_id = None
        if node is not self.current_node:
            return
        if node._preview_task_running or node._compression_task_running:
            self._schedule_poll(node)
        else:
            self.show_previews(node)

    def show_previews(self, node):
        self.current_node = node

        if self._poll_after_id is not None:
            self.after_cancel(self._poll_after_id)
            self._poll_after_id = None

        busy = node._preview_task_running or node._compression_task_running
        self._set_controls_enabled(not busy)

        # while a background task runs, show the stable original instead of a placeholder
        was_show_original = self.show_original
        if busy:
            self.show_original = True

        self.canvas.delete("all")
        self.image_refs.clear()
        y_offset = 10

        if node.is_folder:
            leaf_nodes = self._get_all_leaf_nodes(node)
            for i, leaf in enumerate(leaf_nodes):
                y_offset = self._render_node_images(leaf, y_offset, show_title=True)
                if i < len(leaf_nodes) - 1:
                    self.canvas.create_rectangle(
                        0, y_offset, self.canvas.winfo_width(), y_offset + 15,
                        fill="#cccccc", outline=""
                    )
                    y_offset += 20
        else:
            y_offset = self._render_node_images(node, y_offset, show_title=False)

        self.canvas.config(scrollregion=self.canvas.bbox("all"))

        if self.zoom_label:
            percent = int(self.zoom_level * 100)
            self.zoom_label.config(text=f"{percent}%")

        self.show_original = was_show_original
        self._update_slider_visibility()
        self._update_method_selector()

        if busy:
            self._schedule_poll(node)



    def _get_all_leaf_nodes(self, node: 'PDFNode') -> list:
        result = []
        if node.is_folder:
            for child in node.children:
                result.extend(self._get_all_leaf_nodes(child))
        else:
            result.append(node)
        return result


    def _on_slider_changed(self, value):
        if not self.current_node or self.current_node.is_folder:
            return

        dpi = int(float(value))
        dpi_max = self.current_node.dpi_original or 300

        if dpi >= dpi_max:
            # Benutzer will „∞“ – keine Kompression
            self.current_node.no_compression = True
            self.current_node.current_pdf_data = None
            self._update_slider_visibility()
            self.controller.update_preview(self.current_node)
            return

        self.current_node.no_compression = False
        self.current_node.dpi_current = dpi
        self.current_node.compress(dpi)
        self.controller.update_preview(self.current_node)

    def _update_slider_visibility(self):
        node = self.current_node
        if not node or node.is_folder:
            self.slider.pack_forget()
            self.slider_label_min.pack_forget()
            self.slider_label_max.pack_forget()
            self.reset_button.pack_forget()
            return

        dpi_original = node.dpi_original
        dpi_max = dpi_original if dpi_original else 350
        self.slider.config(from_=50, to=dpi_max)

        if node.no_compression:
            self.slider.pack_forget()
            self.slider_label_min.pack_forget()
            self.slider_label_max.pack_forget()
            self.reset_button.pack(side="left", padx=5)
            return

        self.reset_button.pack_forget()
        self.slider.set(node.dpi_current or dpi_max)
        self.slider_label_min.config(text="50")
        self.slider_label_max.config(text="∞" if not dpi_original else str(dpi_original))
        self.slider_label_min.pack(side="left")
        self.slider.pack(side="left", fill="x", expand=True, padx=5)
        self.slider_label_max.pack(side="left", padx=(0, 5))

    def _on_reset_compression(self):
        if not self.current_node:
            return
        self.current_node.no_compression = False
        self._update_slider_visibility()

    def _update_method_selector(self):
        node = self.current_node
        results = getattr(node, "_compression_results", {}) if node else {}
        if not node or node.is_folder or len(results) < 2:
            self.method_frame.pack_forget()
            return

        best_method = min(results, key=lambda m: len(results[m]))
        labels = []
        for method, data in results.items():
            kb = round(len(data) / 1024)
            if method == best_method:
                labels.append(f"✓ {method} · {kb} KB · bestes Ergebnis")
            else:
                labels.append(f"{method} · {kb} KB")

        self.method_combo["values"] = labels
        for i, (method, data) in enumerate(results.items()):
            if data == node.current_pdf_data:
                self.method_combo.current(i)
                break
        else:
            self.method_combo.current(0)

        self.method_frame.pack(side="bottom", fill="x", pady=2, after=self.commit_frame)

    def _on_method_selected(self, event=None):
        node = self.current_node
        if not node:
            return
        idx = self.method_combo.current()
        results = getattr(node, "_compression_results", {})
        method = list(results.keys())[idx]
        try:
            node.select_compression_method(method)
            self.controller.update_preview(node)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Fehler", str(e))





    def _on_slider_hover(self, event):
        if not self.current_node or self.current_node.no_compression:
            self.slider_tooltip.place_forget()
            return

        value = int(float(self.slider.get()))
        self.slider_tooltip.config(text=f"{value} DPI")
        self.slider_tooltip.place(x=event.x_root - self.winfo_rootx() + 10,
                                  y=event.y_root - self.winfo_rooty() - 20)




    def _on_slider_released(self, event):
        if not self.current_node or self.current_node.is_folder:
            return

        dpi = int(float(self.slider.get()))
        dpi_max = self.current_node.dpi_original or 300

        if dpi >= dpi_max:
            self.current_node.no_compression = True
            self.current_node.current_pdf_data = None
            self._update_slider_visibility()
            self.controller.update_preview(self.current_node)
            return

        self.current_node.no_compression = False
        self.current_node.dpi_current = dpi
        self.current_node._compression_results = {}
        self.current_node.compress_multi_lazy(dpi=dpi)
        self.controller.update_preview(self.current_node)


    def _on_zoom_changed(self, value):
        self.zoom_auto = False
        self.zoom_level = float(value) / 100.0
        self.zoom_label.config(text=f"{int(float(value))}%")
        if self.current_node:
            self.show_previews(self.current_node)



    def _rotate_selected(self, direction):
        if not self.current_node:
            return
        try:
            self.current_node.rotate(direction)
            self.controller.update_preview(self.current_node)
            self.controller.storage.mark_dirty()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Fehler bei Rotation", str(e))
