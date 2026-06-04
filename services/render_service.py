"""Stateful windowed render cache — application layer (no UI, no model imports).

Holds a global LRU of rendered PNG pages keyed by ``(node_id, version, page, dpi)``,
serves windowed render requests cache-first, and runs a budget-bounded,
CPU-throttled background filler driven by the pure ``core.render_policy``.

Everything stateful/threaded lives here; the rendering itself and the CPU reading
are **injected** (``render_page_fn``, ``cpu_load``) so the whole thing is
deterministically unit-testable with fakes — no real rendering, threads, or CPU.
"""

from __future__ import annotations

import threading
from collections import OrderedDict, defaultdict, deque
from concurrent.futures import as_completed
from typing import Callable, Deque, Dict, List, Optional, Sequence, Tuple

from services import cpu
from core.render_policy import (
    DEFAULT_AHEAD,
    DEFAULT_BEHIND,
    DEFAULT_HEAD,
    fill_order,
    next_fill_target,
    predict_window,
)

Key = Tuple[str, int, int, int]          # (node_id, version, page, dpi)
NodeSpec = Tuple[str, int, int]          # (node_id, version, page_count)

DEFAULT_BUDGET = 200 * 1024 * 1024       # 200 MiB


class RenderCache:
    """Thread-safe LRU of rendered page bytes with a byte budget.

    ``put(evict=True)`` evicts least-recently-used entries to fit (foreground
    requests); ``put(evict=False)`` stores only into free space and otherwise
    refuses (the background filler — it never evicts warm pages to prefetch).
    """

    def __init__(self, budget_bytes: int = DEFAULT_BUDGET):
        self.budget = budget_bytes
        self._store: "OrderedDict[Key, bytes]" = OrderedDict()
        self._size = 0
        self._lock = threading.RLock()

    @property
    def size(self) -> int:
        with self._lock:
            return self._size

    def free(self) -> int:
        with self._lock:
            return self.budget - self._size

    def __contains__(self, key: Key) -> bool:
        with self._lock:
            return key in self._store

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def get(self, key: Key) -> Optional[bytes]:
        with self._lock:
            data = self._store.get(key)
            if data is not None:
                self._store.move_to_end(key)  # mark most-recently-used
            return data

    def put(self, key: Key, data: bytes, *, evict: bool = True) -> bool:
        with self._lock:
            n = len(data)
            if n > self.budget:
                return False  # a single page bigger than the whole budget — never store
            if key in self._store:
                self._size -= len(self._store.pop(key))
            if evict:
                while self._size + n > self.budget and self._store:
                    _, old = self._store.popitem(last=False)  # drop LRU
                    self._size -= len(old)
            elif self._size + n > self.budget:
                return False  # prefetch into free space only
            self._store[key] = data
            self._size += n
            return True

    def invalidate_node(self, node_id: str) -> None:
        """Drop every cached page of ``node_id`` (all versions/dpis) — call when a
        node's bytes change so stale renders are never served."""
        with self._lock:
            for k in [k for k in self._store if k[0] == node_id]:
                self._size -= len(self._store.pop(k))

    def set_budget(self, budget_bytes: int) -> None:
        """Change the byte budget, evicting LRU entries to fit if it shrank."""
        with self._lock:
            self.budget = max(0, int(budget_bytes))
            while self._size > self.budget and self._store:
                _, old = self._store.popitem(last=False)  # drop LRU until within budget
                self._size -= len(old)


class RenderService:
    def __init__(
        self,
        render_page_fn: Callable[[bytes, int, int], bytes],
        *,
        budget_bytes: int = DEFAULT_BUDGET,
        cpu_load: Optional[Callable[[], float]] = None,
        cpu_ceiling: float = 0.85,
        history_len: int = 16,
        ahead: int = DEFAULT_AHEAD,
        behind: int = DEFAULT_BEHIND,
        head: int = DEFAULT_HEAD,
        seed_steps: int = 32,
        max_workers: Optional[int] = None,
    ):
        self._render_page = render_page_fn
        self.cache = RenderCache(budget_bytes)
        # default to the real whole-system CPU sampler so background prefetch backs
        # off when the box is loaded (by us OR other users on a terminal server).
        self._cpu_load = cpu_load or cpu.default_sampler.load
        self.cpu_ceiling = cpu_ceiling
        self._hist: Dict[str, Deque[int]] = defaultdict(lambda: deque(maxlen=history_len))
        self._gen = 0
        self._lock = threading.RLock()
        self.ahead, self.behind, self.head = ahead, behind, head
        self.seed_steps = seed_steps    # pages to warm per background seed
        # session-aware, capped pool size; background render threads run at
        # below-normal priority so the OS preempts them for any interactive work.
        self.max_workers = max_workers if max_workers is not None else cpu.worker_count()
        self._executor = None           # lazy single seed-dispatcher worker
        self._pool = None               # lazy N-worker render pool
        self._prefetch = {"prefetch_active": False, "prefetch_warmed": 0}

    # --- stats / config (for the UI status bar) ---------------------------
    def set_budget(self, budget_bytes: int) -> None:
        """Grow/shrink the cache byte budget at runtime (evicts down when shrunk)."""
        self.cache.set_budget(budget_bytes)

    def stats(self) -> dict:
        """Cache occupancy + whether a background prefetch is currently running."""
        with self._lock:
            pf = dict(self._prefetch)
        return {
            "cache_used": self.cache.size,
            "cache_budget": self.cache.budget,
            "cache_free": self.cache.free(),
            "cache_pages": len(self.cache),
            "workers": self.max_workers,
            **pf,  # prefetch_active, prefetch_warmed
        }

    # --- generation / access history --------------------------------------
    @property
    def generation(self) -> int:
        with self._lock:
            return self._gen

    def note_access(self, node_id: str, page: int) -> int:
        """Record a foreground page request and bump the generation (so any
        in-flight background fill abandons its now-stale work)."""
        with self._lock:
            self._gen += 1
            self._hist[node_id].append(page)
            return self._gen

    def predicted(self, node_id: str, total: int) -> List[int]:
        with self._lock:
            hist = list(self._hist[node_id])
        return predict_window(hist, total, ahead=self.ahead, behind=self.behind)

    # --- foreground render ------------------------------------------------
    def render_window(self, node_id: str, version: int, data: bytes,
                      first: int, count: int, dpi: int) -> List[bytes]:
        """Render pages ``[first, first+count)`` cache-first and return their PNG
        bytes. Records the access (focus = ``first``) for direction inference."""
        self.note_access(node_id, first)
        return [self._get_or_render(node_id, version, data, p, dpi)
                for p in range(first, first + count)]

    def _get_or_render(self, node_id: str, version: int, data: bytes,
                       page: int, dpi: int) -> bytes:
        key = (node_id, version, page, dpi)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        rendered = self._render_page(data, page, dpi)
        self.cache.put(key, rendered, evict=True)  # foreground may evict to fit
        return rendered

    def invalidate(self, node_id: str) -> None:
        self.cache.invalidate_node(node_id)

    # --- background filler ------------------------------------------------
    def _cached_pairs(self, node_specs: Sequence[NodeSpec], dpi: int) -> "set[Tuple[str, int]]":
        cached = set()
        for nid, ver, cnt in node_specs:
            for p in range(cnt):
                if (nid, ver, p, dpi) in self.cache:
                    cached.add((nid, p))
        return cached

    def warm_step(self, node_specs: Sequence[NodeSpec], focus_node: str,
                  focus_page: int, data_for: Callable[[str], bytes], dpi: int) -> bool:
        """Render the single highest-priority not-yet-cached page into FREE budget.

        Returns False (does nothing) when throttled by CPU, when the budget is
        full, or when everything reachable is already warm — so a caller can loop
        on the return value.
        """
        if self._cpu_load() >= self.cpu_ceiling:
            return False  # leave headroom for foreground work / fans / battery
        if self.cache.free() <= 0:
            return False
        nodes = [(nid, cnt) for nid, _ver, cnt in node_specs]
        cached = self._cached_pairs(node_specs, dpi)
        target = next_fill_target(nodes, focus_node, focus_page, cached,
                                  ahead=self.ahead, behind=self.behind, head=self.head)
        if target is None:
            return False
        nid, page = target
        version = next(ver for n, ver, _cnt in node_specs if n == nid)
        rendered = self._render_page(data_for(nid), page, dpi)
        return self.cache.put((nid, version, page, dpi), rendered, evict=False)

    def _pool_exec(self):
        """Lazy N-worker render pool. Workers run at below-normal priority so the OS
        preempts them for foreground / other sessions' work (terminal-server fair)."""
        if self._pool is None:
            from concurrent.futures import ThreadPoolExecutor
            self._pool = ThreadPoolExecutor(
                max_workers=self.max_workers,
                initializer=cpu.set_current_thread_below_normal,
                thread_name_prefix="render-pool",
            )
        return self._pool

    def fill_until_idle(self, node_specs: Sequence[NodeSpec], focus_node: str,
                        focus_page: int, data_for: Callable[[str], bytes], dpi: int,
                        *, max_steps: int = 1_000_000, since_gen: Optional[int] = None,
                        pause_if: Optional[Callable[[], bool]] = None) -> int:
        """Warm pages in priority order (current node from the focus outward, then
        neighbours) into FREE budget, **rendering up to ``max_workers`` pages at once**,
        until ``max_steps`` are warmed, the budget is full, the CPU is busy, or a newer
        foreground request bumps the generation. One ``fill_order`` pass (skipping
        already-cached pages). Returns the number of pages warmed."""
        gen = self.generation if since_gen is None else since_gen
        nodes = [(nid, cnt) for nid, _v, cnt in node_specs]
        vmap = {nid: v for nid, v, _c in node_specs}
        order = list(fill_order(nodes, focus_node, focus_page,
                                ahead=self.ahead, behind=self.behind, head=self.head))
        pool = self._pool_exec()
        warmed, i, n = 0, 0, len(order)
        while i < n and warmed < max_steps:
            if self.generation != gen:        # superseded by a newer request → abandon
                break
            if pause_if is not None and pause_if():  # e.g. a compression wants the CPU
                break
            if self.cache.free() <= 0:
                break
            if self._cpu_load() >= self.cpu_ceiling:
                break
            # collect the next batch of not-yet-cached pages (one per worker)
            batch = []
            while i < n and len(batch) < self.max_workers:
                nid, page = order[i]
                i += 1
                key = (nid, vmap[nid], page, dpi)
                if key not in self.cache:     # already warm (e.g. the foreground page)
                    batch.append((key, nid, page))
            if not batch:
                continue
            futures = {pool.submit(self._render_page, data_for(nid), page, dpi): key
                       for key, nid, page in batch}
            stop = False
            for fut in as_completed(futures):
                key = futures[fut]
                try:
                    rendered = fut.result()
                except Exception:             # background; a bad page never crashes the fill
                    continue
                if self.generation != gen:    # a foreground request landed mid-batch
                    stop = True
                    break
                if not self.cache.put(key, rendered, evict=False):  # free space only
                    stop = True
                    break
                warmed += 1
                if warmed >= max_steps:
                    stop = True
                    break
            if stop:
                break
        return warmed

    # --- background seeding (fire-and-forget) -----------------------------
    def _exec(self):
        if self._executor is None:
            from concurrent.futures import ThreadPoolExecutor
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="render-seed")
        return self._executor

    def seed(self, node_specs: Sequence[NodeSpec], focus_node: str, focus_page: int,
             data_for: Callable[[str], bytes], dpi: int) -> None:
        """Warm ``seed_steps`` pages around ``focus_page`` on the background worker,
        superseding any previous seed (it abandons as soon as the next foreground
        request bumps the generation). Returns immediately — the foreground render
        is never blocked by it."""
        gen = self.generation
        specs = list(node_specs)

        def job():
            with self._lock:
                self._prefetch = {"prefetch_active": True, "prefetch_warmed": 0}
            warmed = 0
            try:
                warmed = self.fill_until_idle(specs, focus_node, focus_page, data_for, dpi,
                                              max_steps=self.seed_steps, since_gen=gen)
            except Exception:  # background; never crash the worker
                pass
            finally:
                with self._lock:
                    self._prefetch = {"prefetch_active": False, "prefetch_warmed": warmed}

        self._exec().submit(job)

    def prefetch(self, build: Callable[[], tuple], dpi: int,
                 pause_if: Optional[Callable[[], bool]] = None) -> None:
        """Like ``seed``, but ``build()`` (run on the background worker, so its
        possibly-heavy enumeration/hashing never blocks the foreground) returns
        ``(node_specs, data_for, focus_node, focus_page)``, and we then warm the
        cache **until it is full** (not a fixed step count) — current node from the
        focus outward, then neighbouring nodes — yielding to the CPU, pausing while
        ``pause_if()`` is true (e.g. a compression is running), and abandoning as
        soon as a newer foreground request bumps the generation."""
        gen = self.generation

        def job():
            with self._lock:
                self._prefetch = {"prefetch_active": True, "prefetch_warmed": 0}
            warmed = 0
            try:
                specs, data_for, fnode, fpage = build()
                if specs:
                    warmed = self.fill_until_idle(specs, fnode, fpage, data_for, dpi,
                                                  max_steps=10 ** 9, since_gen=gen,
                                                  pause_if=pause_if)
            except Exception:  # background; never crash the worker
                pass
            finally:
                with self._lock:
                    self._prefetch = {"prefetch_active": False, "prefetch_warmed": warmed}

        self._exec().submit(job)
