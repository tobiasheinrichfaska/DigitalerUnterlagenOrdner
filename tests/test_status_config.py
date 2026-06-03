"""The status vocabulary has ONE source — core.model.STATUSES — and config()
exposes exactly it (so the UI never re-defines the vocabulary)."""

from core.api import CoreApi
from core.model import STATUSES


def test_config_statuses_match_core():
    cfg = CoreApi().config()
    assert cfg["statuses"] == list(STATUSES)
