"""Lock the bomb-guard caps to the single source of truth in infra.limits, so
the mirrored module-level names can't silently drift apart (audit 2026-06-15)."""

from infra.limits import BOMB_CAP_BYTES, BOMB_CAP_ENTRIES


def test_caps_have_expected_values():
    assert BOMB_CAP_BYTES == 500 * 1024 * 1024
    assert BOMB_CAP_ENTRIES == 500


def test_archives_caps_reference_shared_constant():
    from universal_importer import archives

    assert archives._ARCHIVE_MAX_UNCOMPRESSED_BYTES == BOMB_CAP_BYTES
    assert archives._ARCHIVE_MAX_MEMBERS == BOMB_CAP_ENTRIES


def test_variant_blobs_caps_reference_shared_constant():
    from services import variant_blobs

    assert variant_blobs.MAX_TOTAL_BYTES == BOMB_CAP_BYTES
    assert variant_blobs.MAX_ENTRIES == BOMB_CAP_ENTRIES


def test_repair_cap_references_shared_constant():
    from infra import tools

    assert tools._REPAIR_ABS_CAP == BOMB_CAP_BYTES
