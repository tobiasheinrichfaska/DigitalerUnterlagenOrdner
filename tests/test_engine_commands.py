"""Unit tests for engine-backed single-node commands (D3a) with a FakeEngine."""

import pytest

from core.model import Document, Node
from core.commands import (
    DEFAULT_COMPRESSION_DPI,
    Commit,
    CommandError,
    Compress,
    Reset,
    Rotate,
    apply,
    command_from_dict,
    command_to_dict,
)


class FakeEngine:
    """Deterministic, no real PDF work — lets us assert exact bytes."""

    def page_count(self, b: bytes) -> int:
        return b.count(b"\n") + 1

    def compress(self, b: bytes, dpi: int, method=None):
        if len(b) <= 4:
            return None  # "no method beat the original"
        out = (b"c%d:" % dpi) + b[:2]
        return out if len(out) < len(b) else None

    def rotate(self, b: bytes, angle: int) -> bytes:
        return (b"r%d:" % angle) + b


ENGINE = FakeEngine()
DATA = b"ORIGINAL-DATA-1234567890"


def leaf_doc(data=DATA, **leaf_kw) -> Document:
    leaf = Node(name="a", id="a", pdf_length=1, original_data=data, **leaf_kw)
    return Document(Node(name="root", id="root", is_folder=True, children=(leaf,)))


# --- Compress --------------------------------------------------------------

def test_compress_sets_current_and_flags():
    d0 = leaf_doc()
    d1 = apply(d0, Compress("a", dpi=150), ENGINE)
    a = d1.find("a")
    assert a.current_data == b"c150:OR"
    assert a.is_compressed is True and a.dpi_current == 150
    assert d0.find("a").current_data is None  # original untouched (pure)


def test_compress_records_chosen_method():
    d0 = leaf_doc()
    a = apply(d0, Compress("a", dpi=150, method="png"), ENGINE).find("a")
    assert a.compression_method == "png"
    # auto/best leaves it unset (None = "auto")
    b = apply(d0, Compress("a", dpi=150), ENGINE).find("a")
    assert b.compression_method is None


def test_compress_no_gain_returns_unchanged():
    d0 = leaf_doc(data=b"ab")  # too small → FakeEngine returns None
    assert apply(d0, Compress("a"), ENGINE) is d0


def test_compress_requires_engine():
    with pytest.raises(CommandError):
        apply(leaf_doc(), Compress("a"))  # no engine


def test_compress_rejects_no_compression_and_missing_data_and_folder():
    with pytest.raises(CommandError):
        apply(leaf_doc(no_compression=True), Compress("a"), ENGINE)
    with pytest.raises(CommandError):
        apply(leaf_doc(data=None), Compress("a"), ENGINE)
    with pytest.raises(CommandError):
        apply(leaf_doc(), Compress("root"), ENGINE)  # folder, not a leaf


# --- Commit ----------------------------------------------------------------

def test_commit_promotes_current_to_original():
    d0 = leaf_doc(current_data=b"COMPRESSED", is_compressed=True, dpi_current=120, dpi_original=300)
    d1 = apply(d0, Commit("a"))  # no engine needed
    a = d1.find("a")
    assert a.original_data == b"COMPRESSED"
    assert a.current_data is None
    assert a.is_compressed is False
    assert a.dpi_original == 120 and a.dpi_current is None


def test_commit_without_current_raises():
    with pytest.raises(CommandError):
        apply(leaf_doc(), Commit("a"))


# --- Reset -----------------------------------------------------------------

def test_reset_clears_compression():
    d0 = leaf_doc(current_data=b"X", is_compressed=True, dpi_current=120, compression_method="jpg")
    a = apply(d0, Reset("a")).find("a")
    assert a.current_data is None and a.is_compressed is False and a.dpi_current is None
    assert a.compression_method is None
    assert a.original_data == DATA  # original kept


def test_reset_rejects_folders():
    # a folder has nothing to reset — Reset requires a leaf like the other engine ops
    with pytest.raises(CommandError, match="not a leaf"):
        apply(leaf_doc(), Reset("root"))


# --- Rotate ----------------------------------------------------------------

def test_rotate_invalidates_compression():
    # rotating a compressed node drops the compressed variant (original is kept)
    d0 = leaf_doc(current_data=b"OLD", is_compressed=True, dpi_current=120)
    a = apply(d0, Rotate("a", "right"), ENGINE).find("a")
    assert a.original_data == b"r90:" + DATA
    assert a.current_data is None and a.is_compressed is False and a.dpi_current is None


def test_compress_uses_core_default_dpi():
    assert Compress("a").dpi == DEFAULT_COMPRESSION_DPI


def test_rotate_directions():
    assert apply(leaf_doc(), Rotate("a", "left"), ENGINE).find("a").original_data == b"r-90:" + DATA
    assert apply(leaf_doc(), Rotate("a", "180"), ENGINE).find("a").original_data == b"r180:" + DATA


def test_rotate_invalid_direction_and_no_engine():
    with pytest.raises(CommandError):
        apply(leaf_doc(), Rotate("a", "sideways"), ENGINE)
    with pytest.raises(CommandError):
        apply(leaf_doc(), Rotate("a", "right"))  # no engine


# --- serialisation ---------------------------------------------------------

@pytest.mark.parametrize("cmd", [
    Compress(node_id="a", dpi=120),
    Commit(node_id="a"),
    Reset(node_id="a"),
    Rotate(node_id="a", direction="180"),
])
def test_engine_command_serialisation_roundtrip(cmd):
    assert command_from_dict(command_to_dict(cmd)) == cmd
