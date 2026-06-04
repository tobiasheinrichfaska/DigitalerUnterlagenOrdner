"""RenderCache + RenderService — deterministic, with a fake renderer and fake CPU."""

from services.render_service import RenderCache, RenderService


class FakeRenderer:
    """Returns fixed-size bytes and records calls (data, page, dpi)."""

    def __init__(self, size: int = 1000):
        self.size = size
        self.calls = []

    def __call__(self, data, page, dpi):
        self.calls.append((data, page, dpi))
        return bytes(self.size)


# --- RenderCache -----------------------------------------------------------

def test_cache_get_put_roundtrip():
    c = RenderCache(budget_bytes=10_000)
    assert c.get(("a", 1, 0, 100)) is None
    c.put(("a", 1, 0, 100), b"xxx")
    assert c.get(("a", 1, 0, 100)) == b"xxx"
    assert len(c) == 1 and c.size == 3


def test_cache_lru_eviction_order():
    c = RenderCache(budget_bytes=2500)  # 2 x 1000-byte pages fit
    c.put(("n", 1, 0, 100), bytes(1000))
    c.put(("n", 1, 1, 100), bytes(1000))
    c.get(("n", 1, 0, 100))                 # touch page 0 → page 1 is now LRU
    c.put(("n", 1, 2, 100), bytes(1000))    # evicts the LRU (page 1)
    assert ("n", 1, 0, 100) in c
    assert ("n", 1, 2, 100) in c
    assert ("n", 1, 1, 100) not in c


def test_cache_rejects_item_larger_than_budget():
    c = RenderCache(budget_bytes=500)
    assert c.put(("a", 1, 0, 100), bytes(1000)) is False
    assert len(c) == 0


def test_cache_no_evict_refuses_when_full():
    c = RenderCache(budget_bytes=1000)
    assert c.put(("a", 1, 0, 100), bytes(1000)) is True
    # prefetch (evict=False) must NOT evict the warm page to fit
    assert c.put(("a", 1, 1, 100), bytes(1000), evict=False) is False
    assert ("a", 1, 0, 100) in c and ("a", 1, 1, 100) not in c


def test_cache_invalidate_node():
    c = RenderCache(budget_bytes=10_000)
    c.put(("a", 1, 0, 100), bytes(1000))
    c.put(("a", 1, 1, 100), bytes(1000))
    c.put(("b", 1, 0, 100), bytes(1000))
    c.invalidate_node("a")
    assert ("a", 1, 0, 100) not in c and ("a", 1, 1, 100) not in c
    assert ("b", 1, 0, 100) in c
    assert c.size == 1000


# --- RenderService foreground ---------------------------------------------

def test_render_window_caches_pages():
    fake = FakeRenderer()
    svc = RenderService(fake, budget_bytes=10**7)
    out = svc.render_window("a", 1, b"data", first=0, count=3, dpi=100)
    assert len(out) == 3 and all(len(p) == 1000 for p in out)
    assert len(fake.calls) == 3
    svc.render_window("a", 1, b"data", first=0, count=3, dpi=100)  # all cached
    assert len(fake.calls) == 3                                    # no new renders


def test_render_window_version_bump_rerenders():
    fake = FakeRenderer()
    svc = RenderService(fake, budget_bytes=10**7)
    svc.render_window("a", 1, b"v1", 0, 2, 100)
    svc.render_window("a", 2, b"v2", 0, 2, 100)  # new version → fresh renders
    assert len(fake.calls) == 4


def test_note_access_bumps_generation_and_history():
    svc = RenderService(FakeRenderer(), budget_bytes=10**7)
    g0 = svc.generation
    svc.note_access("a", 5)
    assert svc.generation == g0 + 1
    svc.note_access("a", 6)
    assert svc.predicted("a", total=100)[0] == 6  # focus follows last access


def test_invalidate_clears_node_pages():
    fake = FakeRenderer()
    svc = RenderService(fake, budget_bytes=10**7)
    svc.render_window("a", 1, b"data", 0, 2, 100)
    svc.invalidate("a")
    svc.render_window("a", 1, b"data", 0, 2, 100)  # must re-render
    assert len(fake.calls) == 4


# --- RenderService background filler ---------------------------------------

SPECS = [("a", 1, 3), ("b", 1, 2)]  # (node_id, version, page_count), display order


def test_warm_step_throttles_on_high_cpu():
    fake = FakeRenderer()
    svc = RenderService(fake, budget_bytes=10**7, cpu_load=lambda: 0.95, cpu_ceiling=0.85)
    assert svc.warm_step(SPECS, "a", 0, lambda nid: nid.encode(), 100) is False
    assert fake.calls == []  # nothing rendered while CPU is busy


def test_fill_until_idle_warms_whole_document():
    fake = FakeRenderer()
    svc = RenderService(fake, budget_bytes=10**7, cpu_load=lambda: 0.0)
    warmed = svc.fill_until_idle(SPECS, "a", 0, lambda nid: nid.encode(), 100)
    assert warmed == 5                      # 3 (a) + 2 (b)
    assert len(svc.cache) == 5


def test_fill_until_idle_respects_budget():
    fake = FakeRenderer(size=1000)
    svc = RenderService(fake, budget_bytes=2500, cpu_load=lambda: 0.0)  # only 2 fit
    warmed = svc.fill_until_idle(SPECS, "a", 0, lambda nid: nid.encode(), 100)
    assert warmed == 2
    assert len(svc.cache) == 2


def test_stats_reports_cache_occupancy():
    fake = FakeRenderer(size=1000)
    svc = RenderService(fake, budget_bytes=4000, cpu_load=lambda: 0.0)
    s0 = svc.stats()
    assert s0["cache_used"] == 0 and s0["cache_budget"] == 4000 and s0["cache_free"] == 4000
    assert s0["prefetch_active"] is False and s0["cache_pages"] == 0
    svc.render_window("a", 1, b"data", first=0, count=2, dpi=100)  # caches 2 pages
    s1 = svc.stats()
    assert s1["cache_pages"] == 2 and s1["cache_used"] == 2000 and s1["cache_free"] == 2000


def test_fill_pauses_when_pause_if_true():
    fake = FakeRenderer()
    svc = RenderService(fake, budget_bytes=10**7, cpu_load=lambda: 0.0)
    warmed = svc.fill_until_idle([("a", 1, 50)], "a", 0, lambda nid: nid.encode(), 100,
                                 pause_if=lambda: True)  # e.g. a compression wants the CPU
    assert warmed == 0 and fake.calls == []  # warmed nothing while paused


def test_set_budget_changes_free_space():
    svc = RenderService(FakeRenderer(), budget_bytes=1000, cpu_load=lambda: 0.0)
    assert svc.stats()["cache_budget"] == 1000
    svc.set_budget(50_000)
    s = svc.stats()
    assert s["cache_budget"] == 50_000 and s["cache_free"] == 50_000


def test_seed_warms_around_focus_in_background():
    fake = FakeRenderer()
    svc = RenderService(fake, budget_bytes=10**7, cpu_load=lambda: 0.0, seed_steps=8)
    svc.seed([("a", 1, 100)], "a", 50, lambda nid: nid.encode(), 100)
    svc._exec().shutdown(wait=True)  # wait for the background seed job to finish
    assert len(svc.cache) == 8                 # seed_steps pages warmed
    assert ("a", 1, 50, 100) in svc.cache      # incl. the focus page


def test_fill_until_idle_renders_in_parallel_bounded_by_workers():
    """The background filler must actually use multiple cores (concurrent renders)
    yet never exceed max_workers in flight at once."""
    import threading
    import time

    svc = RenderService(FakeRenderer(), budget_bytes=10**7, cpu_load=lambda: 0.0,
                        max_workers=4)
    lock = threading.Lock()
    peak = {"cur": 0, "max": 0}

    def renderer(data, page, dpi):
        with lock:
            peak["cur"] += 1
            peak["max"] = max(peak["max"], peak["cur"])
        time.sleep(0.02)  # hold the "core" so overlap is observable
        with lock:
            peak["cur"] -= 1
        return bytes(100)

    svc._render_page = renderer
    warmed = svc.fill_until_idle([("a", 1, 20)], "a", 0, lambda nid: nid.encode(), 100)
    assert warmed == 20
    assert peak["max"] >= 2          # genuinely concurrent (would be 1 if serial)
    assert peak["max"] <= 4          # never more than the worker cap


def test_fill_until_idle_aborts_on_new_request():
    svc = RenderService(FakeRenderer(), budget_bytes=10**9, cpu_load=lambda: 0.0)
    specs = [("a", 1, 50)]
    state = {"n": 0}

    def renderer(data, page, dpi):
        state["n"] += 1
        if state["n"] == 2:
            svc.note_access("a", 40)  # a concurrent foreground request lands
        return bytes(1000)

    svc._render_page = renderer
    warmed = svc.fill_until_idle(specs, "a", 0, lambda nid: nid.encode(), 100)
    assert warmed < 50  # aborted early, did not warm all 50 pages
