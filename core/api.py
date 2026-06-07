"""In-process façade over the data-driven core.

JSON-able request/response, managing one ``DocumentSession`` per open document
(window). Used **directly** by the pywebview host (the single warm process) and,
via a thin transport, by the named-pipe server — so both share one implementation.

Every method returns a dict with ``ok: bool``; success carries ``session``,
``tree`` (Document JSON), ``can_undo``, ``can_redo``; failure carries ``error``.
"""

from __future__ import annotations

import os
import threading
import uuid
import zlib
from collections import OrderedDict
from contextlib import contextmanager

from core import CORE_VERSION
from core.bridge import load_belegtool
from core.commands import (
    DEFAULT_COMPRESSION_DPI,
    CommandError,
    command_from_dict,
)
from core.engine import RealEngine
from core.model import Document, STATUSES
from core.session import DocumentSession
from infra.log_config import logger
from version_info import APP_NAME


def _friendly_import_error(path: str, exc: Exception) -> str:
    """Map a raw import exception to a clear, per-file German message."""
    name = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower() or "?"
    msg = str(exc)
    low = msg.lower()
    if type(exc).__name__ == "com_error" or "dispatch" in low or "klasse" in low or "class not registered" in low:
        return f"{name}: Office-Programm zum Konvertieren nicht verfügbar (Word/Excel/PowerPoint erforderlich)"
    if "nicht unterstützt" in low or "unsupported" in low:
        return f"{name}: Dateityp {ext} wird nicht unterstützt"
    if "passwort" in low or "password" in low or "encrypted" in low:
        return f"{name}: Datei ist passwortgeschützt"
    if name.lower().endswith((".zip", ".tar", ".tgz", ".tar.gz", ".eml", ".msg")):
        return f"{name}: Archiv/E-Mail konnte nicht gelesen werden ({msg[:80]})"
    if "kein gültiges pdf" in low or "not a pdf" in low or "eof marker" in low or "startxref" in low:
        return f"{name}: beschädigte oder ungültige Datei"
    return f"{name}: {msg}"


class CoreApi:
    def __init__(self, engine=None):
        self._engine = engine or RealEngine()
        self._sessions = {}
        self._paths = {}  # session -> on-disk path (so Speichern saves in place, not Save-As)
        self._lock = threading.Lock()
        self._untitled = 0  # counter for "Dokument N" names (process-wide)
        self._render_service = None  # lazy windowed render cache (shared across windows)
        self._pcount = {}  # (node_id, version) -> page count, to avoid re-opening the PDF
        self._vcache = OrderedDict()  # id(bytes) -> (bytes, crc32), memoised versions (LRU)
        self._compress_active = 0  # >0 while a compression runs → background prefetch yields the CPU
        self._last_seed = None  # (session, focus_id, focus_page, dpi) of the last prefetch, to resume
        self._cancel_tokens = {}  # node_id -> threading.Event, to abort an in-flight compression

    def _renderer(self):
        if self._render_service is None:
            from services.render import render_page
            from services.render_service import RenderService
            from services.cpu import default_budget_for_ram, total_physical_ram
            budget = default_budget_for_ram(total_physical_ram())
            self._render_service = RenderService(render_page, budget_bytes=budget)
        return self._render_service

    def _count_for(self, node_id, version, data):
        key = (node_id, version)
        c = self._pcount.get(key)
        if c is None:
            from services.render import page_count
            c = page_count(data)
            self._pcount[key] = c
        return c

    def _cancel_token(self, node_id):
        """The cancellation Event for compressions of ``node_id`` (created on demand,
        reused across that node's compress calls). Node ids are unique, so a token set
        when a node is removed never wrongly cancels a different node."""
        with self._lock:
            ev = self._cancel_tokens.get(node_id)
            if ev is None:
                ev = threading.Event()
                self._cancel_tokens[node_id] = ev
            return ev

    def _removed_node_ids(self, session, cmd):
        """All node ids a command removes (incl. descendants of a deleted folder),
        computed against the CURRENT document (before the command is applied)."""
        name = type(cmd).__name__
        if name in ("Split", "SplitInto", "Delete"):
            roots = [cmd.node_id]
        elif name in ("DeleteMany", "Merge"):
            roots = list(cmd.node_ids)
        else:
            return []
        with self._lock:
            s = self._sessions.get(session)
            doc = s.document if s else None
        if doc is None:
            return []
        ids = []
        for rid in roots:
            n = doc.find(rid)
            if n is not None:
                ids.extend(d.id for d in n.iter())  # self + descendants
        return ids

    def _kick_prewarm(self, session):
        """(Re)start the background warming around the last focus (if it still exists)
        else the first leaf — used after any change so the cache keeps filling."""
        seed = self._last_seed
        if seed and seed[0] == session:
            _, fid, fpage, dpi = seed
            with self._lock:
                s = self._sessions.get(session)
                doc = s.document if s else None
            if doc is not None and doc.find(fid) is not None:
                self._seed_around(session, fid, fpage, dpi)
                return
        self._prewarm_cache(session)

    @contextmanager
    def _compressing(self):
        """Mark a compression in progress so the background prefetch pauses and
        leaves the CPU to the (user-visible) compression."""
        with self._lock:
            self._compress_active += 1
        try:
            yield
        finally:
            with self._lock:
                self._compress_active -= 1
                resume = self._last_seed if self._compress_active == 0 else None
            if resume is not None:
                self._seed_around(*resume)  # the prefetch paused for us → resume warming

    def _version_of(self, data):
        """Memoised crc32 of bytes, keyed by object identity (the model is immutable,
        so a given bytes object is stable). The bytes are held in the cache value, so
        its id can't be reused for different bytes while cached. LRU-bounded."""
        key = id(data)
        ent = self._vcache.get(key)
        if ent is not None and ent[0] is data:
            self._vcache.move_to_end(key)
            return ent[1]
        v = zlib.crc32(data)
        self._vcache[key] = (data, v)
        if len(self._vcache) > 64:
            self._vcache.popitem(last=False)
        return v

    def _seed_single(self, node_id, version, data, focus_page, dpi):
        """Warm just this node's window (used for transient compressed variants,
        which have no neighbours to warm)."""
        count = self._count_for(node_id, version, data)
        if count > 0:
            self._renderer().seed([(node_id, version, count)], node_id, focus_page,
                                  lambda _nid: data, dpi)

    def _seed_around(self, session, focus_id, focus_page, dpi):
        """Warm the focus node from the viewport outward, then the nearest
        neighbouring leaves (tree order), filling the cache until it's full. The
        whole enumeration/hashing runs on the background worker (via prefetch)."""
        self._last_seed = (session, focus_id, focus_page, dpi)  # to resume after a pause

        def build():
            with self._lock:
                s = self._sessions.get(session)
                root = s.document.root if s else None
            if root is None:
                return [], (lambda _i: b""), focus_id, focus_page
            leaves = [n for n in root.iter()
                      if not n.is_folder and (n.current_data or n.original_data)]
            ids = [n.id for n in leaves]
            if focus_id not in ids:
                return [], (lambda _i: b""), focus_id, focus_page
            fi = ids.index(focus_id)
            # ALL leaves, ordered by distance from the focus (closest first) — so the
            # prefetch keeps warming the whole document (the fill stops at cache-full).
            order = sorted(range(len(leaves)), key=lambda j: (abs(j - fi), j))
            specs, data_map = [], {}
            for idx in order:
                n = leaves[idx]
                data = n.current_data or n.original_data
                ver = self._version_of(data)
                cnt = self._count_for(n.id, ver, data)
                if cnt > 0:
                    specs.append((n.id, ver, cnt))
                    data_map[n.id] = data
            return specs, data_map.get, focus_id, focus_page

        # pause warming while a compression runs, so it gets the CPU
        self._renderer().prefetch(build, dpi, pause_if=lambda: self._compress_active > 0)

    def _next_untitled_name(self) -> str:
        with self._lock:
            self._untitled += 1
            return f"Dokument {self._untitled}"

    # --- ops ---------------------------------------------------------------
    def config(self) -> dict:
        """Fixed core defaults the UI should use instead of hardcoding its own."""
        return {"ok": True, "default_dpi": DEFAULT_COMPRESSION_DPI, "app_name": APP_NAME,
                "statuses": list(STATUSES)}  # status vocabulary lives in the core

    def hello(self) -> dict:
        with self._lock:
            sid = self._new_locked(Document.empty())
        return {"ok": True, "session": sid, "core_version": CORE_VERSION}

    def open(self, session: str = None, path: str = None) -> dict:
        import dataclasses
        if path:
            document = load_belegtool(path)
            name = os.path.splitext(os.path.basename(path))[0] or "Dokument"
            document = Document(dataclasses.replace(document.root, name=name))
            try:  # rehydrate persisted compression variants (instant, no recompute)
                from services.variant_store import seed_variants_from_file
                seed_variants_from_file(path, document, self._engine)
            except Exception:
                logger.warning("[variants] seed on open failed", exc_info=True)
        else:
            document = Document.empty(self._next_untitled_name())  # "Dokument N"
        with self._lock:
            if session and session in self._sessions:
                sid = session
                self._sessions[sid] = DocumentSession(document, engine=self._engine)
            else:
                sid = self._new_locked(document)
            self._paths[sid] = path if path else None  # remember where it came from
            resp = self._doc_response_locked(sid)
        self._prewarm_cache(sid)  # start warming the cache immediately (no click needed)
        return resp

    def document_path(self, session: str):
        """The on-disk path this session is bound to (None if never saved/opened)."""
        return self._paths.get(session)

    def _prewarm_cache(self, session):
        """Kick off the background prefetch around the first leaf, so the render cache
        starts warming as soon as a document is open (before any node is selected)."""
        with self._lock:
            s = self._sessions.get(session)
            root = s.document.root if s else None
        if root is None:
            return
        leaf = next((n for n in root.iter()
                     if not n.is_folder and (n.current_data or n.original_data)), None)
        if leaf is not None:
            self._seed_around(session, leaf.id, 0, 100)

    def document_name(self, session: str) -> str:
        with self._lock:
            s = self._sessions.get(session)
            return s.document.root.name if s else None

    def dispatch(self, session: str, command: dict) -> dict:
        cmd = command_from_dict(command)
        removed = self._removed_node_ids(session, cmd)
        for nid in removed:  # abort in-flight compressions of nodes about to vanish
            ev = self._cancel_tokens.get(nid)
            if ev is not None:
                ev.set()
        resp = self._mutate(session, lambda s: s.dispatch(cmd))
        if resp.get("ok"):
            self._renderer().prune(self._all_live_node_ids())  # free vanished nodes' renders
            self._kick_prewarm(session)  # keep the cache warming around the new state
        return resp

    def _all_live_node_ids(self):
        """Every node id across all open documents (the cache is shared) — anything not
        in this set is stale and can be dropped from the render cache."""
        ids = set()
        with self._lock:
            for s in self._sessions.values():
                for n in s.document.root.iter():
                    ids.add(n.id)
        return ids

    def undo(self, session: str) -> dict:
        return self._mutate(session, lambda s: s.undo())

    def redo(self, session: str) -> dict:
        return self._mutate(session, lambda s: s.redo())

    def render(self, session: str, node_id: str, dpi: int = 100) -> dict:
        """Render a leaf node's effective pages to base64 PNG data-URLs."""
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            node = s.document.find(node_id)
            if node is None:
                return {"ok": False, "error": f"node not found: {node_id}"}
            data = node.current_data or node.original_data
        # render outside the lock (CPU-bound); folders carry no bytes -> []
        from base64 import b64encode
        from services.render import render_pdf_to_pngs
        pages = [
            "data:image/png;base64," + b64encode(p).decode("ascii")
            for p in render_pdf_to_pngs(data, dpi=dpi)
        ]
        return {"ok": True, "session": session, "node": node_id, "pages": pages}

    def render_compressed(self, session: str, node_id: str,
                          dpi: int = DEFAULT_COMPRESSION_DPI, method: str = None) -> dict:
        """Render a *transient* compressed preview of a leaf — compress its
        original bytes with ``method`` at ``dpi`` and rasterise the result, WITHOUT
        mutating the document. Powers the working-preview UI: browse methods/DPI
        with no undo entry; the document only changes on an explicit Compress.
        Falls back to the original bytes if the method yields no gain / no_compression.
        """
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            node = s.document.find(node_id)
            if node is None:
                return {"ok": False, "error": f"node not found: {node_id}"}
            data = node.original_data
            no_comp = node.no_compression
        if not data:
            return {"ok": True, "session": session, "node": node_id, "pages": [], "compressed": False}
        # compress + render outside the lock (CPU-bound); never stored back.
        # "original"/None → render the original bytes directly (no compression run).
        if no_comp or not method or method == "original":
            compressed = None
        else:
            compressed = self._engine.compress(data, dpi, method)
        effective = compressed if compressed is not None else data
        from base64 import b64encode
        from services.render import render_pdf_to_pngs
        pages = [
            "data:image/png;base64," + b64encode(p).decode("ascii")
            for p in render_pdf_to_pngs(effective)
        ]
        return {"ok": True, "session": session, "node": node_id,
                "pages": pages, "compressed": compressed is not None}

    # --- windowed render cache --------------------------------------------
    def _effective(self, node):
        """Effective bytes + a content-derived version (so a compress/rotate/edit
        changes the version and the cache auto-invalidates)."""
        import zlib
        data = node.current_data or node.original_data
        return (data, zlib.crc32(data)) if data else (None, 0)

    def _leaf_data(self, session, node_id):
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return None, None, {"ok": False, "error": "unknown session"}
            node = s.document.find(node_id)
            if node is None:
                return None, None, {"ok": False, "error": f"node not found: {node_id}"}
            return node, (node.current_data or node.original_data), None

    def render_stats(self) -> dict:
        """Render-cache occupancy + background prefetch state, for the UI status bar.
        Cheap; safe to poll. The render service is shared across windows/sessions."""
        stats = self._renderer().stats()
        return {"ok": True, **stats}

    def set_render_budget(self, mb: int) -> dict:
        """Set the render-cache budget (MB). Returns the refreshed stats."""
        self._renderer().set_budget(max(0, int(mb)) * 1024 * 1024)
        if self._last_seed:  # fill the new headroom right away
            self._kick_prewarm(self._last_seed[0])
        return {"ok": True, **self._renderer().stats()}

    def page_count(self, session: str, node_id: str) -> dict:
        node, data, err = self._leaf_data(session, node_id)
        if err:
            return err
        from services.render import page_count
        return {"ok": True, "session": session, "node": node_id, "count": page_count(data)}

    def page_dims(self, session: str, node_id: str) -> dict:
        """(width, height) per page in points — for stable placeholder boxes."""
        node, data, err = self._leaf_data(session, node_id)
        if err:
            return err
        from services.render import page_dims
        return {"ok": True, "session": session, "node": node_id,
                "dims": [[w, h] for (w, h) in page_dims(data)]}

    def render_window(self, session: str, node_id: str, first: int = 0,
                      count: int = 10, dpi: int = 100) -> dict:
        """Render only pages ``[first, first+count)`` of a leaf, cache-first via the
        shared RenderService. The windowed replacement for ``render`` (all pages)."""
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            node = s.document.find(node_id)
            if node is None:
                return {"ok": False, "error": f"node not found: {node_id}"}
            data, version = self._effective(node)
        if not data:
            return {"ok": True, "session": session, "node": node_id, "first": first, "pages": []}
        from base64 import b64encode
        # render the requested (small) window now — foreground priority — then ask
        # the middleware to warm the cache around it in the background.
        pages = self._renderer().render_window(node_id, version, data, first, count, dpi)
        self._seed_around(session, node_id, first, dpi)  # warm this node + neighbours
        urls = ["data:image/png;base64," + b64encode(p).decode("ascii") if p else None
                for p in pages]
        return {"ok": True, "session": session, "node": node_id, "first": first, "pages": urls}

    def render_compressed_window(self, session: str, node_id: str,
                                 dpi: int = DEFAULT_COMPRESSION_DPI, method: str = None,
                                 first: int = 0, count: int = 10) -> dict:
        """Windowed render of a **transient** compressed variant: compress the node's
        original bytes with ``method``@``dpi`` (engine-memoised), then render pages
        ``[first, first+count)`` of the result through the same RenderService —
        keyed by the *variant's* content hash, so re-browsing a method/DPI is
        instant and only the visible window renders. Never mutates the document.
        ``method`` None/"original" (or ``no_compression``) renders the original
        bytes, reusing the plain preview's cache."""
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            node = s.document.find(node_id)
            if node is None:
                return {"ok": False, "error": f"node not found: {node_id}"}
            data = node.original_data
            no_comp = node.no_compression
        if not data:
            return {"ok": True, "session": session, "node": node_id, "first": first,
                    "pages": [], "compressed": False}
        # compress + render outside the lock (CPU-bound); never stored back.
        if no_comp or not method or method == "original":
            variant = data
        else:
            with self._compressing():
                variant = self._engine.compress(data, dpi, method,
                                                cancel=self._cancel_token(node_id).is_set) or data
        import zlib
        version = zlib.crc32(variant)  # variant bytes → its own cache identity
        from base64 import b64encode
        pages = self._renderer().render_window(node_id, version, variant, first, count, 100)
        self._seed_single(node_id, version, variant, first, 100)  # warm this variant's pages
        self._seed_around(session, node_id, first, 100)  # keep warming the whole document
        urls = ["data:image/png;base64," + b64encode(p).decode("ascii") if p else None
                for p in pages]
        return {"ok": True, "session": session, "node": node_id, "first": first,
                "pages": urls, "compressed": variant is not data}

    def save_info(self, session: str) -> dict:
        """Preflight for the save dialog: are there computed compression
        alternatives this save would embed? Lets the UI decide whether to ask
        'store alternatives' vs 'save original' before committing to a path."""
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            document = s.document
        from services.variant_store import pending_variant_count
        count = pending_variant_count(document, self._engine)
        return {"ok": True, "has_alternatives": count > 0, "count": count}

    def save(self, session: str, path: str, store_alternatives: bool = True) -> dict:
        """Save the document to ``path``. When ``store_alternatives`` is False the
        computed compression variants are NOT embedded (smaller file; the options
        recompute on reopen) — the 'Original speichern' choice in the save dialog."""
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            document = s.document
        document = self._bake_no_gain(document)  # persist auto-confirmed no-gain leaves
        from core.bridge import save_belegtool
        try:
            save_belegtool(document, path)
            if store_alternatives:
                from services.variant_store import embed_variants
                embed_variants(path, document, self._engine)  # persist computed variants
        except Exception as e:
            logger.exception("save failed")
            return {"ok": False, "error": str(e)}
        with self._lock:
            s = self._sessions.get(session)
            if s is not None:
                s.mark_saved()
            self._paths[session] = path  # bind the session to this file for in-place saves
        return {"ok": True, "session": session, "path": path}

    def export(self, session: str, path: str, node_ids=None) -> dict:
        """Export to a single PDF with a table of contents, clickable links and
        bookmarks (toc_export). ``node_ids`` exports only those subtrees; otherwise
        the whole document."""
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            doc = s.document
        from core.bridge import document_to_storage
        storage = document_to_storage(doc)  # immutable → PDFNode tree (bytes, no preview)
        if node_ids:
            wanted = set(node_ids)
            nodes = []

            def walk(pn):
                if getattr(pn, "uid", None) in wanted:
                    nodes.append(pn)  # whole subtree (export dedupes ancestors)
                    return
                for c in pn.children:
                    walk(c)

            for child in storage.root.children:
                walk(child)
        else:
            nodes = list(storage.root.children)
        if not nodes:
            return {"ok": False, "error": "nichts zu exportieren"}
        from formats.toc_export import export_pdf_with_toc, empty_leaf_names

        # Leaves with no pages are silently dropped from the export/TOC; collect
        # their names so the UI can tell the user what was left out.
        skipped = empty_leaf_names(nodes)
        try:
            export_pdf_with_toc(nodes, path)
        except Exception as e:
            logger.exception("export failed")
            return {"ok": False, "error": str(e)}
        result = {"ok": True, "session": session, "path": path, "count": len(nodes)}
        if skipped:
            result["warning"] = "Ohne Seiten übersprungen: " + ", ".join(skipped)
        return result

    def materialize_subset(self, session: str, node_ids, name=None) -> dict:
        """Write a NEW .belegtool containing only ``node_ids`` — the nodes a tag view
        is currently displaying — kept in the document's **normal order and structure**
        (an ancestor of a kept node is itself kept). The view's grouping is NOT applied:
        the copy mirrors the real tree, just without the hidden nodes. ``name`` renames
        the new document's root (the used tag prefixed onto the old name). Returns the
        temp file path so the host can open it in a fresh, fully-editable window."""
        from dataclasses import replace
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            document = s.document
        ids = set(node_ids or [])
        if not ids:
            return {"ok": False, "error": "nichts angezeigt"}

        # keep a child only if it is displayed; ancestors of a displayed node are
        # themselves displayed (the view always shows the path), so a node absent from
        # ``ids`` has no displayed descendants and is dropped whole.
        def prune(n):
            return replace(n, children=tuple(prune(c) for c in n.children if c.id in ids))

        new_root = prune(document.root)
        if not new_root.children:
            return {"ok": False, "error": "nichts angezeigt"}
        import re
        import tempfile
        from core.bridge import save_belegtool
        # open() titles a document from its FILE NAME (stem), so encode the wanted name
        # there — in its own temp dir to avoid mkstemp's random suffix in the title.
        safe = re.sub(r'[<>:"/\\|?*]', "_", (name or "Ansicht")).strip() or "Ansicht"
        path = os.path.join(tempfile.mkdtemp(prefix="beleg_view_"), f"{safe}.belegtool")
        try:
            save_belegtool(Document(new_root), path)
        except Exception as e:
            logger.exception("materialize_subset failed")
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": path, "count": sum(1 for _ in new_root.iter()) - 1}

    def any_dirty(self) -> bool:
        """True if any open session has unsaved changes (for the close prompt)."""
        with self._lock:
            return any(s.dirty for s in self._sessions.values())

    def compress_options(self, session: str, node_id: str, dpi: int = 150) -> dict:
        """Available compression methods for a leaf at ``dpi`` (smallest first)."""
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            node = s.document.find(node_id)
            if node is None:
                return {"ok": False, "error": f"node not found: {node_id}"}
            data = node.original_data
        if not data:
            return {"ok": True, "session": session, "node": node_id, "dpi": dpi,
                    "original_size": 0, "options": []}
        with self._compressing():
            sizes = self._engine.compress_methods(data, dpi, cancel=self._cancel_token(node_id).is_set)
        options = sorted(
            ({"method": m, "size": sz} for m, sz in sizes.items()),
            key=lambda o: o["size"],
        )
        return {"ok": True, "session": session, "node": node_id, "dpi": dpi,
                "original_size": len(data), "options": options}

    # --- import ------------------------------------------------------------
    def _import_path(self, path: str) -> list:
        """Import one file from disk into immutable Node(s) — mirrors the Tk import:
        .belegtool/PDF/zip/tar/email via PDFStorage, everything else (images,
        Office, …) via UniversalImporter. Heavy; call outside the lock."""
        from core.bridge import node_from_pdfnode
        low = path.lower()
        if low.endswith(".belegtool"):
            return list(load_belegtool(path).root.children)
        if low.endswith((".pdf", ".zip", ".tar", ".tgz", ".tar.gz", ".eml", ".msg")):
            from formats.pdf_storage import PDFStorage, create_wrapper_node
            storage = PDFStorage(path)
            return [node_from_pdfnode(create_wrapper_node(storage, path))]
        from formats.pdf_node import PDFNode
        from universal_importer import UniversalImporter
        result = UniversalImporter.convert(path)  # images / Office / …
        data = result.data.getvalue() if hasattr(result.data, "getvalue") else result.data
        pn = PDFNode(name=result.name)
        pn.set_original_and_current_data(data, None, None, None, False)
        return [node_from_pdfnode(pn)]

    def import_paths(self, session: str, paths, parent_id: str = None, index: int = None) -> dict:
        """Import real file paths (from the native dialog) under a folder (or root),
        optionally at a position (index) within that folder."""
        from core.commands import InsertNodes
        nodes, errors = [], []
        for path in paths:
            try:
                nodes.extend(self._import_path(path))
            except Exception as e:
                logger.exception("import failed: %s", path)
                errors.append(_friendly_import_error(path, e))
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            if not nodes:
                return {"ok": False, "error": "; ".join(errors) or "nichts importiert"}
            node = s.document.find(parent_id) if parent_id else None
            target = parent_id if (node is not None and node.is_folder) else s.document.root.id
            try:
                s.dispatch(InsertNodes(parent_id=target, nodes=tuple(nodes), index=index))
            except CommandError as e:
                return {"ok": False, "error": str(e)}
            resp = self._doc_response_locked(session)
        self._kick_prewarm(session)  # warm the freshly imported pages without a click
        if errors:
            resp["warning"] = "; ".join(errors)
        return resp

    def import_bytes(self, session: str, name: str, data_b64: str, parent_id: str = None, index: int = None) -> dict:
        """Import a single dropped file given as base64 / data-URL — written to a
        temp file (keeping its name) so the path pipeline (and COM) handle it."""
        import base64
        import shutil
        import tempfile
        try:
            data = base64.b64decode((data_b64 or "").split(",")[-1])
        except Exception as e:
            return {"ok": False, "error": f"ungültige Daten: {e}"}
        tmpdir = tempfile.mkdtemp(prefix="beleg_import_")
        path = os.path.join(tmpdir, os.path.basename(name) or "import.bin")
        try:
            with open(path, "wb") as f:
                f.write(data)
            return self.import_paths(session, [path], parent_id, index)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    # --- internals ---------------------------------------------------------
    def _new_locked(self, document: Document) -> str:
        sid = uuid.uuid4().hex
        self._sessions[sid] = DocumentSession(document, engine=self._engine)
        return sid

    def _mutate(self, session: str, action) -> dict:
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return {"ok": False, "error": "unknown session"}
            try:
                action(s)
            except CommandError as e:
                return {"ok": False, "error": str(e)}
            except Exception as e:  # defensive — never crash the host
                logger.exception("CoreApi op failed")
                return {"ok": False, "error": str(e)}
            return self._doc_response_locked(session)

    def _compression_undecided(self, node) -> bool:
        """Red-dot signal: a leaf whose compression has NOT been confirmed — neither
        applied ('Lesbarkeit geprüft' = is_compressed) nor auto-confirmed (evaluated and
        nothing smaller found) nor marked no_compression. A leaf with a smaller variant
        available but not applied, or one never evaluated, is undecided."""
        if node.is_folder or node.original_data is None:
            return False
        if node.is_compressed or node.no_compression or node.compression_no_gain:
            return False  # applied, can't-compress, or auto-confirmed no-gain → decided
        eng = self._engine
        if bool(getattr(eng, "variants_for", lambda b: {})(node.original_data)):
            return True  # smaller version available, not applied
        return not getattr(eng, "evaluated", lambda b: False)(node.original_data)

    def _bake_no_gain(self, document):
        """Persist the auto-confirmed 'nothing smaller found' decision: any leaf the
        engine evaluated with no smaller variant gets ``compression_no_gain=True`` so it
        is neither re-evaluated nor shown as undecided after reload. Runs at save time
        from current engine state (mirrors embed_variants). Returns a new Document."""
        eng = self._engine
        if not hasattr(eng, "evaluated"):
            return document
        for n in document.root.iter():
            if (not n.is_folder and n.original_data is not None
                    and not n.is_compressed and not n.no_compression
                    and not n.compression_no_gain
                    and eng.evaluated(n.original_data)
                    and not eng.variants_for(n.original_data)):
                document = document.update_node(n.id, compression_no_gain=True)
        return document

    def _doc_response_locked(self, sid: str) -> dict:
        s = self._sessions[sid]
        tree = s.document.to_dict()
        undecided = {n.id: self._compression_undecided(n) for n in s.document.root.iter()}

        def _mark(d):
            d["compression_undecided"] = undecided.get(d["id"], False)
            for c in d["children"]:
                _mark(c)
        _mark(tree)
        return {
            "ok": True,
            "session": sid,
            "tree": tree,
            "can_undo": s.can_undo(),
            "can_redo": s.can_redo(),
        }
