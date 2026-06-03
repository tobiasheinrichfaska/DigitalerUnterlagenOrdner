"""Testmodus golden-master data layer + the CoreApi.test_mode report."""

import testmode
from core.api import CoreApi
from testmode import (
    STATUS_MATCH,
    STATUS_NO_EXPECTED,
    build_all_datasets,
    fixtures_available,
)


def test_fixtures_available():
    assert fixtures_available()  # tests/data/input present in the repo


def test_build_all_datasets_shape():
    datasets = build_all_datasets()
    names = [d.name for d in datasets]
    assert names == ["Kompression", "Splitten", "Zusammenführen"]
    for d in datasets:
        assert d.error is None, f"{d.name}: {d.error}"
        assert d.items


def test_live_matches_golden_master():
    # With unchanged code, every item that HAS an expected reference must match.
    for d in build_all_datasets():
        for it in d.items:
            if it.expected_pdf is not None and it.live_pdf is not None:
                assert it.status == STATUS_MATCH, f"{d.name}/{it.label} drifted from golden master"


def test_comparison_status_values():
    item_statuses = {
        it.status
        for d in build_all_datasets()
        for it in d.items
    }
    # only the defined status vocabulary appears
    assert item_statuses <= {STATUS_MATCH, STATUS_NO_EXPECTED, "differ", "no-live"}


def test_split_shows_original_page_as_input():
    from services.render import page_count
    from testmode import build_split_dataset

    ds = build_split_dataset()
    assert ds.items
    for it in ds.items:
        # input column is now the corresponding ORIGINAL page (one page), next to
        # the split piece (live) — so a tester can verify the split kept page i.
        assert it.input_pdf and page_count(it.input_pdf) == 1
        assert it.live_pdf and page_count(it.live_pdf) == 1


def test_merge_result_has_no_redundant_input():
    from testmode import build_merge_dataset

    ds = build_merge_dataset()
    result = ds.items[-1]
    assert result.input_pdf is None and result.live_pdf is not None  # Live | Referenz only


def test_core_api_test_mode_report():
    api = CoreApi()
    r = api.test_mode(dpi=50, max_pages=2)
    assert r["ok"], r.get("error")
    assert [d["name"] for d in r["datasets"]] == ["Kompression", "Splitten", "Zusammenführen"]
    # thumbnails are base64 PNG data-URLs
    comp = r["datasets"][0]["items"][0]
    assert comp["input"] and comp["input"][0].startswith("data:image/png;base64,")
    assert comp["status"] in {"match", "differ", "no-expected", "no-live"}
