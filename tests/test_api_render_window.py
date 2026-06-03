"""CoreApi windowed render integration: page_count/dims + render_window cache."""

from helpers import create_valid_pdf
from core.api import CoreApi
from core.model import Document, Node
from core.session import DocumentSession


def _session_with_pdf(pages=3):
    api = CoreApi()
    node = Node(name="doc", is_folder=False,
                original_data=create_valid_pdf(pages=pages), pdf_length=pages)
    doc = Document(Node(name="root", is_folder=True, children=(node,)))
    api._sessions["s"] = DocumentSession(doc, engine=api._engine)
    return api, node.id


def test_page_count_and_dims():
    api, nid = _session_with_pdf(pages=3)
    assert api.page_count("s", nid) == {"ok": True, "session": "s", "node": nid, "count": 3}
    dims = api.page_dims("s", nid)
    assert dims["ok"] and len(dims["dims"]) == 3
    assert all(w > 0 and h > 0 for w, h in dims["dims"])


def test_render_window_returns_only_the_window():
    api, nid = _session_with_pdf(pages=5)
    r = api.render_window("s", nid, first=1, count=2, dpi=72)
    assert r["ok"] and r["first"] == 1
    assert len(r["pages"]) == 2
    assert all(p.startswith("data:image/png;base64,") for p in r["pages"])


def test_render_window_uses_cache_on_repeat():
    api, nid = _session_with_pdf(pages=3)
    api.render_window("s", nid, 0, 3, 72)
    cache_len = len(api._renderer().cache)
    assert cache_len == 3
    api.render_window("s", nid, 0, 3, 72)        # served from cache
    assert len(api._renderer().cache) == 3       # no growth / no re-render


def test_effective_version_tracks_bytes():
    # content-derived version: same bytes → same version; different bytes → different.
    api = CoreApi()
    data = create_valid_pdf(pages=1)
    _, v1 = api._effective(Node(name="x", original_data=data))
    _, v1b = api._effective(Node(name="x", original_data=bytes(data)))
    _, v2 = api._effective(Node(name="x", original_data=data + b"%%x"))
    assert v1 == v1b and v1 != v2
    # current_data takes precedence over original_data for the effective version
    _, vc = api._effective(Node(name="x", original_data=data, current_data=data + b"#"))
    assert vc != v1


def test_render_window_unknown_node():
    api, _ = _session_with_pdf(pages=1)
    assert api.render_window("s", "nope", 0, 1)["ok"] is False


# --- compressed-variant presentation routed through the same cache ---------

def test_render_compressed_window_returns_window():
    api, nid = _session_with_pdf(pages=4)
    r = api.render_compressed_window("s", nid, dpi=150, method="jpg", first=1, count=2)
    assert r["ok"] and r["first"] == 1 and len(r["pages"]) == 2
    assert all(p.startswith("data:image/png;base64,") for p in r["pages"])


def test_render_compressed_window_original_reuses_plain_cache():
    api, nid = _session_with_pdf(pages=3)
    api.render_window("s", nid, 0, 3, 100)               # plain preview @ dpi 100
    n = len(api._renderer().cache)
    r = api.render_compressed_window("s", nid, dpi=150, method="original", first=0, count=3)
    assert r["ok"] and r["compressed"] is False
    # "original" renders the same bytes @ dpi 100 → identical keys → no new entries
    assert len(api._renderer().cache) == n


def test_render_compressed_window_caches_on_repeat():
    api, nid = _session_with_pdf(pages=3)
    api.render_compressed_window("s", nid, 150, "jpg", 0, 3)
    n = len(api._renderer().cache)
    api.render_compressed_window("s", nid, 150, "jpg", 0, 3)  # same variant → cache hit
    assert len(api._renderer().cache) == n
