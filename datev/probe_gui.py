"""Tkinter governing GUI for the DATEVconnect read probe (round 1). Every retrieval is an
explicit button — you decide what is pulled and see the raw result in the log. Nothing is
fetched automatically. Logic lives in the (tested) client; this is only the shell.

Run standalone (or as the one-file exe built by scripts/build_datev_probe.ps1):
    .build_venv/Scripts/python.exe datev_probe.py
"""
import datetime
import json
import os
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .client import DatevConnectClient
from .config import dms_base_url, load_config, resolve_auth_mode, self_signed_allowed
from .synthetic_pdf import make_test_pdf
from .transport import make_curl_sso_transport, make_urllib_transport
from .types import DatevConfig, program_keeps_revisions

DEFAULT_BASE = "https://localhost:58452/datev/api/dms/v2"
TEST_DESC = "ZZZ TEST – DATEV-Probe – bitte löschen"


def _exe_dir():
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
        else os.path.dirname(os.path.abspath(__file__))


def _build_stamp():
    """The build/modification time of the running program — so the title proves which exe
    is live (stale-copy is the classic 'my fix didn't take' cause)."""
    try:
        target = sys.executable if getattr(sys, "frozen", False) else __file__
        return datetime.datetime.fromtimestamp(os.path.getmtime(target)).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return "?"


def _short(obj, n=160):
    s = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    return s if len(s) <= n else s[: n - 1] + "…"


class ProbeApp:
    def __init__(self, root):
        self.root = root
        self.client = None
        self.docs = []          # last documents list
        self.structure_items = []
        self.client_guid = None     # resolved Mandant GUID (round 2)
        self.created_doc_id = None  # the doc this run created — the ONLY id round 2b may exchange
        self.cfg = load_config()  # datev.config.json next to the exe (same as OPOS), if present
        self._logpath = os.path.join(_exe_dir(), "datev-probe.log")
        root.title(f"DATEV-Probe — DMS v2 — Build {_build_stamp()}")
        root.geometry("960x720")
        self._build()
        self._logf(f"=== Start {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · Build {_build_stamp()} ===")

    # --- layout ------------------------------------------------------------
    def _build(self):
        pad = dict(padx=6, pady=3)
        conn = ttk.LabelFrame(self.root, text="Verbindung")
        conn.pack(fill="x", **pad)
        # Pin the DMS path even when the config's base_url points at the accounting API (OPOS reuse).
        base_default = dms_base_url(self.cfg, DEFAULT_BASE)
        self.base = tk.StringVar(value=base_default)
        self.user = tk.StringVar(value=self.cfg.get("user") or "")
        self.pw = tk.StringVar(value=self.cfg.get("password") or "")
        self.self_signed = tk.BooleanVar(value=self_signed_allowed(self.cfg, base_default))
        # SSO default like the other DATEV programs; honours an explicit "auth" in the config.
        self.auth_mode = tk.StringVar(value=resolve_auth_mode(self.cfg))
        ttk.Label(conn, text="Base-URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(conn, textvariable=self.base, width=60).grid(row=0, column=1, columnspan=3, sticky="we", **pad)
        # Auth: Windows SSO (current user, no password — matches DATEV's own programs) or Basic.
        ttk.Radiobutton(conn, text="Windows-Anmeldung (SSO)", value="sso", variable=self.auth_mode,
                        command=self._sync_auth).grid(row=1, column=0, columnspan=2, sticky="w", **pad)
        ttk.Radiobutton(conn, text="Basic (Benutzer/Passwort)", value="basic", variable=self.auth_mode,
                        command=self._sync_auth).grid(row=1, column=2, columnspan=2, sticky="w", **pad)
        ttk.Label(conn, text="Benutzer (UPN)").grid(row=2, column=0, sticky="w")
        self.user_entry = ttk.Entry(conn, textvariable=self.user, width=28)
        self.user_entry.grid(row=2, column=1, sticky="we", **pad)
        ttk.Label(conn, text="Passwort").grid(row=2, column=2, sticky="w")
        self.pw_entry = ttk.Entry(conn, textvariable=self.pw, show="•", width=20)
        self.pw_entry.grid(row=2, column=3, sticky="we", **pad)
        ttk.Checkbutton(conn, text="Self-signed TLS zulassen (localhost)",
                        variable=self.self_signed).grid(row=3, column=1, columnspan=2, sticky="w", **pad)
        ttk.Button(conn, text="Verbinden / Info abrufen", command=self.connect).grid(row=3, column=3, sticky="e", **pad)
        conn.columnconfigure(1, weight=1)
        self._sync_auth()  # disable user/pw under SSO

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

        # Write actions — Round 2a: CREATE ONLY (synthetic PDF, you pick the Mandant; no exchange/delete)
        w = ttk.LabelFrame(self.root, text="Schreiben — Runde 2a: NUR Anlegen (Test-Dokument, synthetisch)")
        w.pack(fill="x", **pad)
        ttk.Label(w, text="Mandant-Nr.").grid(row=0, column=0, sticky="e")
        self.mandant = tk.StringVar()
        ttk.Entry(w, textvariable=self.mandant, width=10).grid(row=0, column=1, sticky="w", **pad)
        ttk.Button(w, text="→ GUID auflösen", command=self.resolve_client).grid(row=0, column=2, **pad)
        self.guid_lbl = tk.StringVar(value="GUID: —")
        ttk.Label(w, textvariable=self.guid_lbl).grid(row=0, column=3, columnspan=3, sticky="w", **pad)
        # placement ids (the user reads these from the Domains dump)
        self.domain_id = tk.StringVar(value="1")    # Mandanten
        self.folder_id = tk.StringVar()
        self.register_id = tk.StringVar()
        self.class_id = tk.StringVar(value="1")     # "Dokument"
        for col, (lbl, var) in enumerate([("Domain-ID", self.domain_id), ("Ordner-ID", self.folder_id),
                                          ("Register-ID", self.register_id), ("Klasse-ID", self.class_id)]):
            ttk.Label(w, text=lbl).grid(row=1, column=col * 2, sticky="e")
            ttk.Entry(w, textvariable=var, width=8).grid(row=1, column=col * 2 + 1, sticky="w", **pad)
        ttk.Label(w, text="Vorh. Datei-ID").grid(row=2, column=6, sticky="e")
        self.reuse_file_id = tk.StringVar()   # bind an existing orphan upload instead of a new one
        ttk.Entry(w, textvariable=self.reuse_file_id, width=12).grid(row=2, column=7, sticky="w", **pad)
        ttk.Button(w, text="Test-Dokument anlegen", command=self.create_test_document).grid(
            row=2, column=0, columnspan=2, sticky="w", **pad)
        self.created_lbl = tk.StringVar(value="Angelegt: —")
        ttk.Label(w, textvariable=self.created_lbl, font=("", 9, "bold")).grid(
            row=2, column=2, columnspan=4, sticky="w", **pad)
        # Fetch a specific document back by id (pre-filled after a create) — Details + Struktur.
        ttk.Label(w, text="Dokument-ID").grid(row=3, column=0, sticky="e")
        self.fetch_id = tk.StringVar()
        ttk.Entry(w, textvariable=self.fetch_id, width=40).grid(
            row=3, column=1, columnspan=3, sticky="we", **pad)
        ttk.Button(w, text="Abrufen (Details + Struktur)", command=self.fetch_by_id).grid(
            row=3, column=4, sticky="w", **pad)
        ttk.Button(w, text="GET /documents/{id} (roh)", command=self.get_doc_raw).grid(
            row=3, column=5, sticky="w", **pad)
        # Confirm the uploaded FILE persists (file-id is an int, distinct from the document GUID).
        ttk.Label(w, text="Datei-ID").grid(row=4, column=0, sticky="e")
        self.file_id = tk.StringVar()
        ttk.Entry(w, textvariable=self.file_id, width=14).grid(row=4, column=1, sticky="w", **pad)
        ttk.Button(w, text="Datei prüfen (Bytes)", command=self.check_file_id).grid(
            row=4, column=2, **pad)

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
    def _sync_auth(self):
        state = "disabled" if self.auth_mode.get() == "sso" else "normal"
        self.user_entry.configure(state=state)
        self.pw_entry.configure(state=state)

    def _make_client(self):
        sso = self.auth_mode.get() == "sso"
        cfg = DatevConfig(base_url=self.base.get().strip(),
                          username=None if sso else (self.user.get().strip() or None),
                          password=None if sso else (self.pw.get() or None),
                          allow_self_signed=self.self_signed.get())
        transport = (make_curl_sso_transport(cfg.allow_self_signed) if sso
                     else make_urllib_transport(cfg.allow_self_signed))
        return DatevConnectClient(cfg, transport)

    def _logf(self, text):
        """Append to datev-probe.log next to the exe — ground truth even if the GUI log
        doesn't render a line (so a hung/odd call is still recorded)."""
        try:
            with open(self._logpath, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass

    def _log_line(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self._logf(text)

    def _post_log(self, text):
        """Thread-safe log: schedule the write on the Tk main thread (never touch widgets
        from a worker thread — that can wedge the event loop so results never render)."""
        self.root.after(0, lambda: self._log_line(text))

    def _run(self, label, fn, on_ok=None):
        self.status.set(f"{label} …")
        self._log_line(f"→ {label}")
        state = {"done": False, "secs": 0}

        def heartbeat():   # visible proof the call is still running (so slow ≠ stuck)
            if state["done"]:
                return
            state["secs"] += 1
            self.status.set(f"{label} … läuft ({state['secs']}s)")
            self.root.after(1000, heartbeat)

        self.root.after(1000, heartbeat)

        def worker():
            try:
                res = fn()
                state["done"] = True
                self.root.after(0, lambda: self._ok(label, res, on_ok))
            except Exception as e:  # surface every DATEV error in the log + status
                state["done"] = True
                self._logf(f"!!! worker exception in {label!r}:\n{traceback.format_exc()}")
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
        status = getattr(exc, "status", None)
        head = f"✗ {type(exc).__name__}" + (f" [HTTP {status}]" if status else "") + f": {exc}"
        self._log_line(head)
        body = getattr(exc, "body", None)  # the raw DATEV response — the real reason
        if body:
            snippet = body if len(body) <= 1000 else body[:999] + "…"
            self._log_line(f"   Rohantwort: {snippet}")

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

    # --- write (round 2a: create only) -------------------------------------
    def resolve_client(self):
        if not self._need_client():
            return
        num = self.mandant.get().strip()
        if not num:
            messagebox.showinfo("DATEV-Probe", "Bitte eine Mandant-Nr. eingeben.")
            return

        def on_ok(res):
            self.client_guid = res.get("guid")
            self.guid_lbl.set(f"GUID: {self.client_guid}  ({res.get('name') or ''})")

        self._run(f"Mandant {num} auflösen", lambda: self.client.resolve_client_guid(num), on_ok)

    def _build_create_payload(self):
        """A DocumentCreate body for ONE synthetic test file under the chosen client/placement."""
        def _int(var, name):
            v = var.get().strip()
            if not v.isdigit():
                raise ValueError(f"{name} muss eine Zahl sein.")
            return int(v)

        payload = {
            "class": {"id": _int(self.class_id, "Klasse-ID")},
            "correspondence_partner_guid": self.client_guid,
            "description": TEST_DESC,
            "domain": {"id": _int(self.domain_id, "Domain-ID")},
            # type 1 = file; counter/parent_counter give it an explicit position in the
            # structure tree (a document left without a valid structure is auto-deleted by
            # DATEV within ~24 h, so we always supply one).
            "structure_items": [{"name": "datev-probe-test.pdf", "type": 1,
                                 "counter": 1, "parent_counter": 0}],
        }
        if self.folder_id.get().strip():
            payload["folder"] = {"id": _int(self.folder_id, "Ordner-ID")}
        if self.register_id.get().strip():
            payload["register"] = {"id": _int(self.register_id, "Register-ID")}
        return payload

    def create_test_document(self):
        if not self._need_client():
            return
        if not self.client_guid:
            messagebox.showinfo("DATEV-Probe", "Erst „→ GUID auflösen“ (Mandant-Nr.).")
            return
        try:
            payload = self._build_create_payload()
        except ValueError as e:
            messagebox.showwarning("DATEV-Probe", str(e))
            return
        if not messagebox.askyesno(
                "Test-Dokument anlegen — schreibt in DATEV",
                f"Es wird EIN synthetisches Test-PDF in der LIVE-Dokumentenablage angelegt:\n\n"
                f"  Mandant-GUID: {self.client_guid}\n"
                f"  Domain {self.domain_id.get()} · Ordner {self.folder_id.get() or '—'} · "
                f"Register {self.register_id.get() or '—'}\n"
                f"  Beschreibung: {TEST_DESC}\n\n"
                f"Es wird KEIN echtes Dokument verändert. Fortfahren?"):
            return

        reuse = self.reuse_file_id.get().strip()

        def do_create():
            if reuse:   # rebind an existing orphan upload instead of creating a new file
                file_id = int(reuse) if reuse.lstrip("-").isdigit() else reuse
                self._post_log(f"vorhandene document_file_id = {file_id} (kein Upload)")
            else:
                file_id = self.client.upload_document_file(make_test_pdf(TEST_DESC))
                self._post_log(f"document_file_id = {file_id}")   # thread-safe (was the wedge bug)
            payload["structure_items"][0]["document_file_id"] = file_id
            self._post_log("→ POST /documents " + json.dumps(payload, ensure_ascii=False))
            doc = self.client.create_document(payload)
            self._post_log("← " + json.dumps(doc, ensure_ascii=False))
            return {"file_id": file_id, "document": doc}

        def on_ok(res):
            doc = res.get("document") or {}
            self.created_doc_id = doc.get("id")
            cdt = doc.get("change_date_time") or doc.get("create_date_time") or "—"
            self.created_lbl.set(f"Angelegt: id={self.created_doc_id}  ·  change_date_time={cdt}")
            if self.created_doc_id:  # pre-fill the fetch field + read the structure back
                self.fetch_id.set(self.created_doc_id)
                self._run(f"Struktur {self.created_doc_id}",
                          lambda: self.client.list_structure_items(self.created_doc_id))

        self._run("Test-Dokument anlegen", do_create, on_ok)

    def fetch_by_id(self):
        """GET a specific document (typed or just-created id) + its structure — proves whether
        the create persisted and how DokAb stored it."""
        if not self._need_client():
            return
        doc_id = self.fetch_id.get().strip()
        if not doc_id:
            messagebox.showinfo("DATEV-Probe", "Bitte eine Dokument-ID eingeben.")
            return
        if not self._guard_doc_guid(doc_id):
            return
        self._run(f"Dokument {doc_id}", lambda: self.client.get_document(doc_id))
        self._run(f"Struktur {doc_id}", lambda: self.client.list_structure_items(doc_id))

    def _guard_doc_guid(self, doc_id):
        """A document id is a GUID; an all-numeric value is a document_file_id (wrong
        namespace). Catch the common mix-up before a pointless GET /documents/<number>."""
        if doc_id.isdigit():
            messagebox.showwarning(
                "DATEV-Probe",
                f"„{doc_id}“ ist eine Datei-ID (Zahl), kein Dokument-GUID.\n\n"
                "GET /documents/{id} braucht den Dokument-GUID (z. B. 5677c4b7-…).\n"
                "Für eine Datei-Nummer „Datei prüfen (Bytes)“ nutzen (= /document-files/{id}).")
            return False
        return True

    def get_doc_raw(self):
        """Single raw GET /documents/{id} — shows HTTP status + full body so existence is
        unambiguous (200 real / 200 default-values / 404 not found)."""
        if not self._need_client():
            return
        doc_id = self.fetch_id.get().strip()
        if not doc_id:
            messagebox.showinfo("DATEV-Probe", "Bitte eine Dokument-ID eingeben.")
            return
        if not self._guard_doc_guid(doc_id):
            return
        self._run(f"GET /documents/{doc_id} (roh)",
                  lambda: self.client.get_document_raw(doc_id))

    def check_file_id(self):
        """GET /document-files/{id} — confirms the uploaded file still exists (an orphan upload
        not bound into a surviving document is what DATEV purges)."""
        if not self._need_client():
            return
        fid = self.file_id.get().strip()
        if not fid:
            messagebox.showinfo("DATEV-Probe", "Bitte eine Datei-ID (Zahl) eingeben.")
            return
        self._run(f"Datei {fid} prüfen", lambda: self.client.get_document_file(fid))


def main():
    root = tk.Tk()
    ProbeApp(root)
    root.mainloop()
