"""Tkinter governing GUI for the DATEVconnect read probe (round 1). Every retrieval is an
explicit button — you decide what is pulled and see the raw result in the log. Nothing is
fetched automatically. Logic lives in the (tested) client; this is only the shell.

Run standalone (or as the one-file exe built by scripts/build_datev_probe.ps1):
    .build_venv/Scripts/python.exe datev_probe.py
"""
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .client import DatevConnectClient
from .transport import make_urllib_transport
from .types import DatevConfig, program_keeps_revisions

DEFAULT_BASE = "https://localhost:58452/datev/api/dms/v2"


def _short(obj, n=160):
    s = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    return s if len(s) <= n else s[: n - 1] + "…"


class ProbeApp:
    def __init__(self, root):
        self.root = root
        self.client = None
        self.docs = []          # last documents list
        self.structure_items = []
        root.title("DATEV-Probe — DMS v2 (Lesen)")
        root.geometry("960x720")
        self._build()

    # --- layout ------------------------------------------------------------
    def _build(self):
        pad = dict(padx=6, pady=3)
        conn = ttk.LabelFrame(self.root, text="Verbindung")
        conn.pack(fill="x", **pad)
        self.base = tk.StringVar(value=DEFAULT_BASE)
        self.user = tk.StringVar()
        self.pw = tk.StringVar()
        self.self_signed = tk.BooleanVar(value=True)
        ttk.Label(conn, text="Base-URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(conn, textvariable=self.base, width=60).grid(row=0, column=1, columnspan=3, sticky="we", **pad)
        ttk.Label(conn, text="Benutzer (UPN)").grid(row=1, column=0, sticky="w")
        ttk.Entry(conn, textvariable=self.user, width=28).grid(row=1, column=1, sticky="we", **pad)
        ttk.Label(conn, text="Passwort").grid(row=1, column=2, sticky="w")
        ttk.Entry(conn, textvariable=self.pw, show="•", width=20).grid(row=1, column=3, sticky="we", **pad)
        ttk.Checkbutton(conn, text="Self-signed TLS zulassen (localhost)",
                        variable=self.self_signed).grid(row=2, column=1, columnspan=2, sticky="w", **pad)
        ttk.Button(conn, text="Verbinden / Info abrufen", command=self.connect).grid(row=2, column=3, sticky="e", **pad)
        conn.columnconfigure(1, weight=1)

        self.feature = tk.StringVar(value="Programmtyp: —")
        ttk.Label(self.root, textvariable=self.feature, font=("", 10, "bold")).pack(anchor="w", padx=8)

        # Read actions
        act = ttk.LabelFrame(self.root, text="Lesen (Sie steuern, was geholt wird)")
        act.pack(fill="x", **pad)
        ttk.Button(act, text="Domains", command=self.load_domains).grid(row=0, column=0, **pad)
        ttk.Label(act, text="Filter").grid(row=0, column=1, sticky="e")
        self.filter = tk.StringVar()
        ttk.Entry(act, textvariable=self.filter, width=30).grid(row=0, column=2, sticky="we", **pad)
        ttk.Label(act, text="max.").grid(row=0, column=3, sticky="e")
        self.top = tk.IntVar(value=20)
        ttk.Spinbox(act, from_=1, to=1000, textvariable=self.top, width=6).grid(row=0, column=4, **pad)
        ttk.Button(act, text="Dokumente laden", command=self.load_documents).grid(row=0, column=5, **pad)
        act.columnconfigure(2, weight=1)

        # Documents list + detail buttons
        mid = ttk.Frame(self.root)
        mid.pack(fill="both", expand=True, **pad)
        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Dokumente (auswählen)").pack(anchor="w")
        self.doclist = tk.Listbox(left, height=10)
        self.doclist.pack(fill="both", expand=True)
        self.doclist.bind("<<ListboxSelect>>", lambda e: self._on_doc_select())
        btns = ttk.Frame(left)
        btns.pack(fill="x")
        ttk.Button(btns, text="Details + Struktur", command=self.load_detail).pack(side="left", **pad)
        ttk.Button(btns, text="Datei speichern…", command=self.save_file).pack(side="left", **pad)

        # Log
        right = ttk.LabelFrame(mid, text="Ergebnis / Protokoll")
        right.pack(side="left", fill="both", expand=True)
        self.log = tk.Text(right, wrap="word", height=10)
        self.log.pack(fill="both", expand=True)

        self.status = tk.StringVar(value="Bereit.")
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    # --- helpers -----------------------------------------------------------
    def _make_client(self):
        cfg = DatevConfig(base_url=self.base.get().strip(),
                          username=self.user.get().strip() or None,
                          password=self.pw.get() or None,
                          allow_self_signed=self.self_signed.get())
        return DatevConnectClient(cfg, make_urllib_transport(cfg.allow_self_signed))

    def _log_line(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def _run(self, label, fn, on_ok=None):
        self.status.set(f"{label} …")
        self._log_line(f"→ {label}")

        def worker():
            try:
                res = fn()
                self.root.after(0, lambda: self._ok(label, res, on_ok))
            except Exception as e:  # surface every DATEV error in the log + status
                self.root.after(0, lambda: self._err(label, e))

        threading.Thread(target=worker, daemon=True).start()

    def _ok(self, label, res, on_ok):
        self.status.set(f"{label}: ok")
        if isinstance(res, (dict, list)):
            self._log_line(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            self._log_line(f"{label}: {len(res)} Bytes" if isinstance(res, (bytes, bytearray)) else str(res))
        if on_ok:
            on_ok(res)

    def _err(self, label, exc):
        self.status.set(f"{label}: FEHLER")
        self._log_line(f"✗ {type(exc).__name__}: {exc}")

    def _need_client(self):
        if self.client is None:
            messagebox.showwarning("DATEV-Probe", "Bitte zuerst „Verbinden / Info abrufen“.")
            return False
        return True

    # --- actions -----------------------------------------------------------
    def connect(self):
        self.client = self._make_client()

        def on_ok(info):
            feat = (info or {}).get("feature", "?")
            rev = "mit Revisionen" if program_keeps_revisions(feat) else "OHNE Revisionen (Austausch überschreibt)"
            self.feature.set(f"Programmtyp: {feat}  —  {rev}")

        self._run("Info abrufen", self.client.get_info, on_ok)

    def load_domains(self):
        if not self._need_client():
            return
        self._run("Domains laden", lambda: self.client.list_domains(self.filter.get().strip() or None))

    def load_documents(self):
        if not self._need_client():
            return

        def on_ok(docs):
            self.docs = docs if isinstance(docs, list) else []
            self.doclist.delete(0, "end")
            for d in self.docs:
                self.doclist.insert("end", _short(
                    f"{d.get('description', '(ohne Titel)')}  ·  {d.get('extension', '')}  ·  "
                    f"{d.get('change_date_time', '')}  ·  {d.get('id', '')}"))

        self._run("Dokumente laden",
                  lambda: self.client.list_documents(self.filter.get().strip() or None, self.top.get()),
                  on_ok)

    def _on_doc_select(self):
        sel = self.doclist.curselection()
        # selection only; detail/file actions read the current selection on click

    def _selected_doc(self):
        sel = self.doclist.curselection()
        if not sel or sel[0] >= len(self.docs):
            messagebox.showinfo("DATEV-Probe", "Bitte ein Dokument auswählen.")
            return None
        return self.docs[sel[0]]

    def load_detail(self):
        if not self._need_client():
            return
        doc = self._selected_doc()
        if not doc:
            return
        doc_id = doc.get("id")

        def on_ok(items):
            self.structure_items = items if isinstance(items, list) else []

        self._run(f"Details {doc_id}", lambda: self.client.get_document(doc_id))
        self._run(f"Struktur {doc_id}", lambda: self.client.list_structure_items(doc_id), on_ok)

    def save_file(self):
        if not self._need_client():
            return
        if not self.structure_items:
            messagebox.showinfo("DATEV-Probe", "Erst „Details + Struktur“ laden (liefert die document_file_id).")
            return
        file_id = next((it.get("document_file_id") for it in self.structure_items if it.get("document_file_id")), None)
        if not file_id:
            messagebox.showinfo("DATEV-Probe", "Kein document_file_id in der Struktur gefunden.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                            filetypes=[("PDF", "*.pdf"), ("Alle", "*.*")])
        if not path:
            return

        def on_ok(data):
            with open(path, "wb") as f:
                f.write(data)
            self._log_line(f"gespeichert: {path} ({len(data)} Bytes)")

        self._run(f"Datei {file_id}", lambda: self.client.get_document_file(file_id), on_ok)


def main():
    root = tk.Tk()
    ProbeApp(root)
    root.mainloop()
