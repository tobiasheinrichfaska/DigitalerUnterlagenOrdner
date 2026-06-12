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


def sweep_stale_view_dirs(root=None, max_age_s=24 * 3600, now=None):
    """Best-effort startup cleanup of leftover ``beleg_view_*`` temp dirs.
    Materialized tag views are deleted when their window closes (close_session),
    but a crash can strand them. Only dirs older than ``max_age_s`` are removed,
    so a concurrently running instance's live view is never touched. Returns the
    removed paths."""
    import glob
    import shutil
    import tempfile
    import time
    root = root or tempfile.gettempdir()
    now = now if now is not None else time.time()
    removed = []
    for d in glob.glob(os.path.join(root, "beleg_view_*")):
        try:
            if os.path.isdir(d) and now - os.path.getmtime(d) > max_age_s:
                shutil.rmtree(d, ignore_errors=True)
                removed.append(d)
        except OSError:
            continue
    return removed


# NOTE on i18n: the German messages below (and the static error strings in CoreApi)
# are translation KEYS — the React UI localizes them via t()/localizeMessage
# (webui/src/lib/messages.js mirrors the dynamic templates). Changing the wording
# here requires updating en.js + every full-coverage language file.
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
    if "externe vorlage/quelle" in low:  # OOXML .rels pre-scan refusal (converters.py)
        return f"{name}: Dokument verweist auf eine externe Vorlage/Quelle und wird aus Sicherheitsgründen nicht importiert"
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
        # Single-writer file lock (off by default; opt-in via BELEG_FILE_LOCK). When on,
        # opening a .belegtool holds an exclusive handle for the session's lifetime.
        self._file_lock_enabled = os.environ.get("BELEG_FILE_LOCK", "").lower() not in ("", "0", "false", "no")
        self._locks = {}  # session -> FileLock (only while file-lock is enabled)
        self._view_dirs = {}  # session -> temp beleg_view_* dir of its materialized view (deleted on close)
        self._pending_view_dirs = set()  # materialized view dirs not yet bound to their (new) session
        self._view_touched = {}  # view_dir -> last os.utime, to rate-limit the keep-alive touch
        self._renderer_lock = threading.Lock()  # guards the lazy RenderService build

    def _renderer(self):
        if self._render_service is None:
            with self._renderer_lock:  # js threads race here → never build the service twice
                if self._render_service is None:
                    from services.render import render_page
                    from services.render_service import RenderService
                    from services.cpu import default_budget_for_ram, total_physical_ram
                    budget = default_budget_for_ram(total_physical_ram())
                    self._render_service = RenderService(render_page, budget_bytes=budget)
        return self._render_service

    def _count_for(self, node_id, version, data):
        # _pcount is iterated by close_session under self._lock (js threads), so the
        # read/insert here must hold it too — an unlocked insert mid-iteration raises
        # inside close_session and silently leaks the whole session.
        key = (node_id, version)
        with self._lock:
            c = self._pcount.get(key)
        if c is None:
            from services.render import page_count
            c = page_count(data)
            with self._lock:
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
        # unlocked write is deliberate: a single atomic tuple swap, readers only
        # ever see a complete old or new value (audit 2026-06-12: benign)
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

    def _should_lock(self, path) -> bool:
        return bool(self._file_lock_enabled and path)

    def _acquire_lock(self, path):
        """Acquire the single-writer lock for ``path`` (after restoring from a leftover
        .bak if the file was left truncated by an interrupted locked save). Returns a
        FileLock, or raises FileInUseError. Non-Windows / unexpected errors → None
        (best-effort: open without a lock rather than block the user)."""
        from infra.file_lock import FileLock, FileInUseError
        self._restore_from_bak(path)
        try:
            return FileLock(path).acquire()
        except FileInUseError:
            raise
        except Exception:
            logger.warning("[lock] acquire failed; opening without a lock", exc_info=True)
            return None

    def _restore_from_bak(self, path):
        """If a locked save was interrupted, the file may be truncated/invalid while a
        sibling .bak holds the previous good bytes — restore it before opening."""
        bak = path + ".bak"
        if not os.path.exists(bak):
            return
        try:
            ok = os.path.getsize(path) > 0 and b"%PDF" in open(path, "rb").read(1024)
        except Exception:
            ok = False
        if not ok:
            try:
                import shutil
                shutil.copyfile(bak, path)
                logger.warning("[lock] restored %s from .bak after an interrupted save", path)
            except Exception:
                logger.exception("[lock] .bak restore failed")
        try:
            os.remove(bak)
        except OSError:
            pass

    def _release_lock(self, session):
        with self._lock:  # pywebview dispatches JS calls on separate threads
            lock = self._locks.pop(session, None)
        if lock is not None:
            lock.release()

    def open(self, session: str = None, path: str = None) -> dict:
        import dataclasses
        lock = None
        if self._should_lock(path):
            from infra.file_lock import FileInUseError
            try:
                lock = self._acquire_lock(path)
            except FileInUseError:
                return {"ok": False, "code": "in_use",
                        "error": "Diese Datei wird bereits bearbeitet und kann nur von "
                                 "einer Person gleichzeitig geöffnet werden."}
        try:
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
        except Exception:
            if lock is not None:
                lock.release()  # never leak the handle if the load fails
            raise
        with self._lock:
            if session and session in self._sessions:
                sid = session
                self._sessions[sid] = DocumentSession(document, engine=self._engine)
            else:
                sid = self._new_locked(document)
            prev_lock = self._locks.pop(sid, None)  # reopening in the same session → drop old lock
            self._paths[sid] = path if path else None  # remember where it came from
            if lock is not None:
                self._locks[sid] = lock
            # a materialized tag view opened in its new window → bind the temp dir to
            # this session so close_session can delete it with the window.
            view_dir = os.path.dirname(path) if path else None
            if view_dir and view_dir in self._pending_view_dirs:
                self._pending_view_dirs.discard(view_dir)
                self._view_dirs[sid] = view_dir
                self._touch_view_dir(view_dir)  # live dir must never look stale to a sweep
            resp = self._doc_response_locked(sid)
        if prev_lock is not None:
            prev_lock.release()
        # uids persist in .belegtool: a node deleted (set token) in another window
        # must be compressible in this fresh session of the same file.
        self._revive_cancel_tokens(sid)
        self._prewarm_cache(sid)  # start warming the cache immediately (no click needed)
        return resp

    def document_path(self, session: str):
        """The on-disk path this session is bound to (None if never saved/opened)."""
        return self._paths.get(session)

    @staticmethod
    def _touch_view_dir(view_dir):
        """Refresh a live view dir's mtime so a SECOND running instance's startup
        sweep (sweep_stale_view_dirs, >24 h) never deletes a dir that is still in
        use — its mtime would otherwise stay at creation time for the window's life."""
        try:
            os.utime(view_dir, None)
        except OSError:
            pass

    def _maybe_touch_view_dir(self, view_dir, min_interval_s=3600):
        """Rate-limited keep-alive touch, piggybacked on render traffic — so a view
        window open >24 h WITHOUT ever saving still never looks stale to a sweep."""
        import time
        now = time.time()
        if now - self._view_touched.get(view_dir, 0) >= min_interval_s:
            self._view_touched[view_dir] = now
            self._touch_view_dir(view_dir)

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
        if removed:
            with self._lock:
                # node uids persist in .belegtool, so the same file open twice shares
                # ids — only cancel what no OTHER session still uses (same guard as
                # close_session), or deleting in one window kills the other's compression.
                live_elsewhere = set()
                for sid, other in self._sessions.items():
                    if sid != session:
                        live_elsewhere.update(n.id for n in other.document.root.iter())
                for nid in removed:  # abort in-flight compressions of nodes about to vanish
                    ev = self._cancel_tokens.get(nid)
                    if ev is not None and nid not in live_elsewhere:
                        ev.set()
        return self._after_mutate(session, self._mutate(session, lambda s: s.dispatch(cmd)))

    def _after_mutate(self, session, resp) -> dict:
        """Shared post-mutation hygiene for dispatch/undo/redo: revive cancel tokens
        of ids back in the document, drop vanished nodes' renders from the cache,
        and keep the background prefetch warming around the new state. Tokens are
        revived on the FAILURE path too — dispatch sets them before the mutate, so
        a failed command (which removed nothing) must not leave still-present
        nodes' tokens set (their compress_options would return [] until the next
        successful edit)."""
        self._revive_cancel_tokens(session)
        if resp.get("ok"):
            self._renderer().prune(self._all_live_node_ids())  # free vanished nodes' renders
            self._kick_prewarm(session)  # keep the cache warming around the new state
        return resp

    def _revive_cancel_tokens(self, session):
        """Drop SET cancel tokens of ids that are (back) in the document — a
        delete→undo revives the node, and a stale set token would make every later
        compression abort instantly (compress_options == [] forever). The next
        compress call recreates a fresh, unset Event on demand."""
        with self._lock:
            s = self._sessions.get(session)
            if s is None:
                return
            for n in s.document.root.iter():
                ev = self._cancel_tokens.get(n.id)
                if ev is not None and ev.is_set():
                    del self._cancel_tokens[n.id]

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
        return self._after_mutate(session, self._mutate(session, lambda s: s.undo()))

    def redo(self, session: str) -> dict:
        return self._after_mutate(session, self._mutate(session, lambda s: s.redo()))

    def render(self, session: str, node_id: str, dpi: int = 100) -> dict:
        """Render a leaf node's effective pages to base64 PNG data-URLs.

        IPC/test-only: the named-pipe server still dispatches ``op == "render"``
        here, but the React UI renders exclusively through ``render_window`` (the
        JS-bridge wrapper was removed)."""
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
        mutating the document. Falls back to the original bytes if the method
        yields no gain / no_compression.

        Test-only: not on the JS bridge and not an IPC op — the working-preview UI
        uses the windowed ``render_compressed_window`` exclusively."""
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
            view_dir = self._view_dirs.get(session)
        if view_dir:
            self._maybe_touch_view_dir(view_dir)  # a rendering view window is alive
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
        lock = self._locks.get(session)
        in_place_locked = lock is not None and path == self._paths.get(session)
        try:
            if in_place_locked:
                self._save_through_lock(lock, path, document, store_alternatives)
            else:
                from core.bridge import save_belegtool
                save_belegtool(document, path)
                if store_alternatives:
                    from services.variant_store import embed_variants
                    embed_variants(path, document, self._engine)  # persist computed variants
                self._relock_after_save_as(session, path)  # save-as under lock → lock the new file
        except Exception as e:
            logger.exception("save failed")
            return {"ok": False, "error": str(e)}
        with self._lock:
            s = self._sessions.get(session)
            if s is not None:
                s.mark_saved()
            self._paths[session] = path  # bind the session to this file for in-place saves
            view_dir = self._view_dirs.get(session)
        if view_dir:
            self._touch_view_dir(view_dir)  # saving through a view keeps it sweep-safe
        return {"ok": True, "session": session, "path": path}

    def _save_through_lock(self, lock, path, document, store_alternatives) -> None:
        """Single-write save through the held handle (the lock denies our own open('wb')).
        Guards the non-atomic in-place overwrite with a sibling .bak of the previous bytes,
        removed only after a successful flush."""
        from core.bridge import document_to_storage
        data = document_to_storage(document).to_bytes()
        if store_alternatives:
            from services.variant_store import embed_variants_bytes
            data, _ = embed_variants_bytes(data, document, self._engine)
        bak = path + ".bak"
        try:
            prev = lock.read_all()
        except Exception:
            prev = b""
        if prev:
            with open(bak, "wb") as f:
                f.write(prev)
        lock.overwrite(data)
        try:
            os.remove(bak)
        except OSError:
            pass

    def _relock_after_save_as(self, session, new_path) -> None:
        """After a normal (unlocked) save to a NEW path while file-lock is on: release the
        old lock and lock the just-written file so the session keeps its single-writer hold."""
        if not self._file_lock_enabled:
            return
        with self._lock:
            if new_path == self._paths.get(session):
                return
        self._release_lock(session)
        try:
            lock = self._acquire_lock(new_path)
            if lock is not None:
                with self._lock:
                    self._locks[session] = lock
        except Exception:
            logger.warning("[lock] could not lock the new file after save-as", exc_info=True)

    def release(self, session: str) -> dict:
        """Release the session's file lock — called when its window closes so another
        person/window can open the file without quitting the app. Idempotent."""
        self._release_lock(session)
        return {"ok": True}

    def close_session(self, session: str) -> dict:
        """Free everything a closed window held: its DocumentSession (full bytes +
        undo log), path binding, page-count entries, cancel tokens, file lock and —
        for a materialized tag view — its temp beleg_view_* dir. Then prune the
        shared render cache so the gone nodes' renders can be evicted. Idempotent."""
        with self._lock:
            s = self._sessions.pop(session, None)
            self._paths.pop(session, None)
            lock = self._locks.pop(session, None)
            view_dir = self._view_dirs.pop(session, None)
            if view_dir is not None:
                self._view_touched.pop(view_dir, None)  # drop its keep-alive timestamp too
            if s is not None:
                live = set()
                for other in self._sessions.values():
                    live.update(n.id for n in other.document.root.iter())
                # node uids persist in .belegtool, so the same file open twice shares
                # ids — only drop what no remaining session still uses.
                gone = {n.id for n in s.document.root.iter()} - live
                for key in [k for k in self._pcount if k[0] in gone]:
                    del self._pcount[key]
                for nid in gone:
                    ev = self._cancel_tokens.pop(nid, None)
                    if ev is not None:
                        ev.set()  # abort any in-flight compression of a vanished node
            if self._last_seed and self._last_seed[0] == session:
                self._last_seed = None  # never resume prefetch for a closed session
        if lock is not None:
            lock.release()
        if view_dir is not None:
            import shutil
            shutil.rmtree(view_dir, ignore_errors=True)
        if self._render_service is not None:
            self._render_service.prune(self._all_live_node_ids())
        return {"ok": True}

    def export(self, session: str, path: str, node_ids=None, options=None) -> dict:
        """Export to a single PDF. ``node_ids`` exports only those subtrees; otherwise
        the whole document. ``options`` (see toc_export.DEFAULT_EXPORT_OPTIONS) toggles
        the printed TOC (+links), the tag index (+links), and the PDF bookmarks."""
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
        from formats.toc_export import export_pdf, empty_leaf_names

        # Leaves with no pages are silently dropped from the export/TOC; collect
        # their names so the UI can tell the user what was left out.
        skipped = empty_leaf_names(nodes)
        try:
            export_pdf(nodes, path, options)
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
        with self._lock:  # remember the temp dir until its new window opens (then per-session)
            self._pending_view_dirs.add(os.path.dirname(path))
        return {"ok": True, "path": path, "count": sum(1 for _ in new_root.iter()) - 1}

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
        # re-importing a persisted uid that was deleted elsewhere (set token) must
        # leave the node compressible — same revive as dispatch/undo/redo.
        self._revive_cancel_tokens(session)
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
