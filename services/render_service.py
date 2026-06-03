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
from typing import Callable, Deque, Dict, List, Optional, Sequence, Tuple

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
    ):
        self._render_page = render_page_fn
        self.cache = RenderCache(budget_bytes)
        self._cpu_load = cpu_load or (lambda: 0.0)
        self.cpu_ceiling = cpu_ceiling
        self._hist: Dict[str, Deque[int]] = defaultdict(lambda: deque(maxlen=history_len))
        self._gen = 0
        self._lock = threading.RLock()
        self.ahead, self.behind, self.head = ahead, behind, head
        self.seed_steps = seed_steps    # pages to warm per background seed
        self._executor = None           # lazy single background worker

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

    def fill_until_idle(self, node_specs: Sequence[NodeSpec], focus_node: str,
                        focus_page: int, data_for: Callable[[str], bytes], dpi: int,
                        *, max_steps: int = 1_000_000, since_gen: Optional[int] = None) -> int:
        """Warm pages in priority order (current node from the focus outward, then
        neighbours) into FREE budget, until ``max_steps`` are warmed, the budget is
        full, the CPU is busy, or a newer foreground request bumps the generation.
        One ``fill_order`` pass (skipping already-cached pages), so it's O(pages),
        not O(pages²). Returns the number of pages warmed."""
        gen = self.generation if since_gen is None else since_gen
        nodes = [(nid, cnt) for nid, _v, cnt in node_specs]
        vmap = {nid: v for nid, v, _c in node_specs}
        warmed = 0
        for nid, page in fill_order(nodes, focus_node, focus_page,
                                    ahead=self.ahead, behind=self.behind, head=self.head):
            if warmed >= max_steps:
                break
            if self.generation != gen:        # superseded by a newer request → abandon
                break
            if self.cache.free() <= 0:
                break
            if self._cpu_load() >= self.cpu_ceiling:
                break
            key = (nid, vmap[nid], page, dpi)
            if key in self.cache:             # already warm (e.g. the foreground page)
                continue
            rendered = self._render_page(data_for(nid), page, dpi)
            if not self.cache.put(key, rendered, evict=False):  # prefetch into free space only
                break
            warmed += 1
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
            try:
                self.fill_until_idle(specs, focus_node, focus_page, data_for, dpi,
                                     max_steps=self.seed_steps, since_gen=gen)
            except Exception:  # background; never crash the worker
                pass

        self._exec().submit(job)
