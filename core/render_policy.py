"""Pure render-prefetch policy — the 'brain' of the windowed render cache.

No rendering, no threads, no UI, no model imports: just page arithmetic over an
access history. Fully unit-testable. The stateful RenderService (application
layer) calls these to decide what to render now and what to warm in the
background; the immutable Document model is never touched.

Two functions:
  * ``predict_window`` — given a node's recent page accesses, which pages to keep
    cached and in what render-priority order (focus first, biased to the scroll
    direction; jumps band around the new focus without filling the gap).
  * ``next_fill_target`` — the background filler's priority order across a whole
    document: current node outward, then neighbor heads, then deepen.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

# Defaults (tunable knobs; the three numbers from the design discussion).
DEFAULT_AHEAD = 10   # pages to keep in the direction of travel
DEFAULT_BEHIND = 5   # pages to keep in the already-passed direction
DEFAULT_HEAD = 10    # pages of each neighbouring node to warm first


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(v, hi))


def _direction(history: Sequence[int], jump_threshold: int) -> int:
    """+1 forward, -1 backward, 0 unknown. A delta larger than the window is a
    *jump* (scrollbar/goto), not a scroll, so it yields 0 (neutral) — the band
    re-centres on the new focus instead of biasing wildly."""
    if len(history) < 2:
        return 0
    delta = history[-1] - history[-2]
    if abs(delta) > jump_threshold:
        return 0
    return 1 if delta > 0 else (-1 if delta < 0 else 0)


def predict_window(
    history: Sequence[int],
    total: int,
    *,
    ahead: int = DEFAULT_AHEAD,
    behind: int = DEFAULT_BEHIND,
) -> List[int]:
    """Pages to keep cached around the current focus, in render-priority order.

    ``history`` is the node's recent page requests, most-recent **last** (its last
    element is the current focus). ``total`` is the node's page count. ``ahead`` /
    ``behind`` are relative to the inferred scroll direction (forward/neutral keeps
    ``ahead`` pages after focus and ``behind`` before; backward mirrors it).

    Order: focus first, then outward by distance, ties broken toward the travel
    direction. Small documents return all their pages. Jumps band around the new
    focus only (no gap fill). Empty history ⇒ focus at page 0 (top-of-document).
    """
    if total <= 0:
        return []

    focus = history[-1] if history else 0
    focus = _clamp(focus, 0, total - 1)
    direction = _direction(history, jump_threshold=max(ahead, behind))
    forward = direction >= 0  # neutral biases like forward (top-to-bottom reading)

    if forward:
        lo, hi = focus - behind, focus + ahead
    else:
        lo, hi = focus - ahead, focus + behind
    lo = max(0, lo)
    hi = min(total - 1, hi)

    order: List[int] = [focus]
    seen = {focus}
    for d in range(1, (hi - lo) + 1):
        candidates = (focus + d, focus - d) if forward else (focus - d, focus + d)
        for c in candidates:
            if lo <= c <= hi and c not in seen:
                order.append(c)
                seen.add(c)
    return order


def _ring(idx: int, n: int) -> List[int]:
    """Indices of other nodes by distance from ``idx`` (forward-first):
    idx+1, idx-1, idx+2, idx-2, …  — an expanding ring."""
    out: List[int] = []
    for d in range(1, n):
        for j in (idx + d, idx - d):
            if 0 <= j < n and j != idx:
                out.append(j)
    return out


def fill_order(
    nodes: Sequence[Tuple[str, int]],
    focus_node: str,
    focus_page: int,
    *,
    ahead: int = DEFAULT_AHEAD,
    behind: int = DEFAULT_BEHIND,
    head: int = DEFAULT_HEAD,
) -> List[Tuple[str, int]]:
    """The full background-fill priority order as (node_id, page) pairs.

    ``nodes`` is the leaf list in display order as (node_id, page_count). Priority:
      1. current node — the predicted window first, then the rest of that node,
      2. the *heads* (first ``head`` pages) of neighbouring nodes, expanding ring,
      3. deepen those neighbours (pages beyond their head).
    Pages past a node's count are skipped. The list is the order in which the
    filler should warm the cache; the caller renders the first not-yet-cached one.
    """
    counts = {nid: cnt for nid, cnt in nodes}
    try:
        idx = next(i for i, (nid, _) in enumerate(nodes) if nid == focus_node)
    except StopIteration:
        return []

    out: List[Tuple[str, int]] = []
    seen = set()

    def push(nid: str, p: int) -> None:
        if 0 <= p < counts[nid] and (nid, p) not in seen:
            out.append((nid, p))
            seen.add((nid, p))

    # 1. current node: predicted window, then the remainder
    fcount = counts[focus_node]
    for p in predict_window([focus_page], fcount, ahead=ahead, behind=behind):
        push(focus_node, p)
    for p in range(fcount):
        push(focus_node, p)

    ring = _ring(idx, len(nodes))
    # 2. neighbour heads
    for j in ring:
        nid, cnt = nodes[j]
        for p in range(min(head, cnt)):
            push(nid, p)
    # 3. deepen neighbours
    for j in ring:
        nid, cnt = nodes[j]
        for p in range(head, cnt):
            push(nid, p)
    return out


def next_fill_target(
    nodes: Sequence[Tuple[str, int]],
    focus_node: str,
    focus_page: int,
    cached: "set[Tuple[str, int]]",
    *,
    ahead: int = DEFAULT_AHEAD,
    behind: int = DEFAULT_BEHIND,
    head: int = DEFAULT_HEAD,
) -> Optional[Tuple[str, int]]:
    """The single highest-priority (node_id, page) not yet in ``cached`` — or
    ``None`` when everything reachable is warm. Pure; the filler loop calls this
    repeatedly, rendering each result into the cache, until it returns None."""
    for target in fill_order(nodes, focus_node, focus_page,
                             ahead=ahead, behind=behind, head=head):
        if target not in cached:
            return target
    return None
