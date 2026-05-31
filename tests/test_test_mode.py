"""Headless tests for the test-mode data layer (no Tk / display needed)."""

import test_mode
from test_mode import (
    build_all_datasets,
    build_compression_dataset,
    build_merge_dataset,
    build_split_dataset,
    render_thumbnails,
    fixtures_available,
    STATUS_MATCH,
)


def test_fixtures_are_available():
    assert fixtures_available() is True


def test_compression_live_matches_expected():
    ds = build_compression_dataset()
    assert ds.error is None
    assert len(ds.items) == 1
    item = ds.items[0]
    assert item.live_pdf is not None
    assert item.expected_pdf is not None
    assert item.status == STATUS_MATCH


def test_split_live_matches_expected():
    ds = build_split_dataset()
    assert ds.error is None
    assert len(ds.items) == 3  # split_sample.pdf has 3 pages
    for item in ds.items:
        assert item.status == STATUS_MATCH, f"{item.label}: {item.status}"


def test_merge_result_matches_expected():
    ds = build_merge_dataset()
    assert ds.error is None
    result = ds.items[-1]  # last item is the merged result
    assert result.live_pdf is not None
    assert result.status == STATUS_MATCH


def test_build_all_returns_three_datasets():
    datasets = build_all_datasets()
    assert [d.name for d in datasets] == ["Kompression", "Splitten", "Zusammenführen"]


def test_render_thumbnails_handles_empty_and_real():
    assert render_thumbnails(None) == []
    assert render_thumbnails(b"not a pdf") == []
    data = (test_mode.INPUT_DIR / "compress_sample.pdf").read_bytes()
    imgs = render_thumbnails(data, max_pages=2)
    assert 1 <= len(imgs) <= 2
    assert imgs[0].width <= 230
