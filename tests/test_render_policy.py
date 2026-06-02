"""Pure render-prefetch policy: predict_window + next_fill_target.

No rendering, no UI, no threads — just asserting the page arithmetic and
priority order that the RenderService will rely on.
"""

from core.render_policy import (
    DEFAULT_AHEAD,
    DEFAULT_BEHIND,
    fill_order,
    next_fill_target,
    predict_window,
)


# --- predict_window --------------------------------------------------------

def test_focus_is_first():
    order = predict_window([20], total=100)
    assert order[0] == 20


def test_small_document_returns_all_pages():
    order = predict_window([0], total=4)
    assert sorted(order) == [0, 1, 2, 3]


def test_band_is_contiguous_and_clamped_to_bounds():
    order = predict_window([2], total=100, ahead=10, behind=5)
    assert min(order) == 0                       # clamped at top, no negatives
    assert max(order) == 2 + 10                  # forward/neutral keeps `ahead` after focus
    assert sorted(order) == list(range(0, 13))   # contiguous


def test_forward_scroll_biases_ahead():
    # history trending forward → more pages after focus than before
    order = predict_window([8, 9, 10], total=100, ahead=10, behind=5)
    after = [p for p in order if p > 10]
    before = [p for p in order if p < 10]
    assert len(after) == 10 and len(before) == 5
    # priority: nearest-forward beats nearest-back
    assert order[1] == 11


def test_backward_scroll_biases_behind():
    order = predict_window([12, 11, 10], total=100, ahead=10, behind=5)
    after = [p for p in order if p > 10]
    before = [p for p in order if p < 10]
    assert len(before) == 10 and len(after) == 5
    assert order[1] == 9                          # nearest-backward first


def test_jump_does_not_fill_the_gap():
    # 10 -> 800 is a jump, not a scroll: band only around 800, nothing near 10
    order = predict_window([10, 800], total=1000, ahead=10, behind=5)
    assert 800 in order
    assert all(p > 780 for p in order)            # no in-between pages
    assert len(order) <= DEFAULT_AHEAD + DEFAULT_BEHIND + 1


def test_empty_history_starts_at_top():
    order = predict_window([], total=100)
    assert order[0] == 0
    assert min(order) == 0


def test_total_zero_returns_empty():
    assert predict_window([5], total=0) == []


# --- fill_order / next_fill_target ----------------------------------------

NODES = [("a", 3), ("b", 30), ("c", 2)]  # leaf list in display order


def test_fill_order_starts_with_focus_node_window():
    order = fill_order(NODES, focus_node="b", focus_page=15)
    # everything from the focus node comes before any neighbour page
    first_other = next(i for i, (nid, _) in enumerate(order) if nid != "b")
    assert all(nid == "b" for nid, _ in order[:first_other])
    assert order[0] == ("b", 15)                  # focus first


def test_fill_order_neighbour_heads_before_deepening():
    # Focus the small node 'a' (filled fast); neighbours are b(30) and c(2).
    # Heads-before-deepening applies across NEIGHBOURS: c's head must precede
    # b's deep (post-head) pages, and b's own head precedes its deep pages.
    order = fill_order(NODES, focus_node="a", focus_page=0, head=10)
    assert order.index(("c", 1)) < order.index(("b", 10))
    assert order.index(("b", 9)) < order.index(("b", 10))
    # the focus node is fully filled before any neighbour page
    last_a = max(order.index(("a", p)) for p in range(3))
    first_neighbour = min(order.index(("b", 0)), order.index(("c", 0)))
    assert last_a < first_neighbour


def test_fill_order_covers_every_page_once():
    order = fill_order(NODES, focus_node="a", focus_page=0)
    total = sum(c for _, c in NODES)
    assert len(order) == total
    assert len(set(order)) == total               # no duplicates


def test_next_fill_target_skips_cached():
    cached = {("b", p) for p in range(30)} | {("a", 0), ("a", 1), ("a", 2)}
    # only node c is uncached
    t = next_fill_target(NODES, focus_node="b", focus_page=15, cached=cached)
    assert t is not None and t[0] == "c"


def test_next_fill_target_none_when_all_cached():
    cached = {(nid, p) for nid, cnt in NODES for p in range(cnt)}
    assert next_fill_target(NODES, focus_node="b", focus_page=0, cached=cached) is None


def test_next_fill_target_unknown_focus_node():
    assert next_fill_target(NODES, focus_node="zzz", focus_page=0, cached=set()) is None
