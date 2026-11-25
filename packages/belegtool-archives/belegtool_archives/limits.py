"""Shared bomb-guard caps for untrusted-container decoding.

Single source of truth for the decoded-size / entry-count limits applied
wherever bytes from untrusted input are inflated (archive members, embedded
compression-variant blobs, PDF repair output). Defined once so the mirrored
caps in ``belegtool_archives/archives.py`` and (in the host app)
``services/variant_blobs.py`` / ``infra/tools.py`` cannot silently drift apart.
"""

BOMB_CAP_BYTES = 500 * 1024 * 1024  # 500 MB decoded
BOMB_CAP_ENTRIES = 500

# Zip members are only read with these compression methods. For ZIP_BZIP2/ZIP_LZMA,
# CPython's zipfile decompresses each chunk WITHOUT a max_length and truncates only
# afterwards (zipfile ZipExtFile._read1), so the usual read(remaining+1) caps the
# RESULT but not the memory allocated while inflating — a few-KB member with a
# forged small size can allocate GBs. Refuse those methods up front, everywhere an
# untrusted zip is opened (archive import, variant blobs, OOXML .rels scan).
_SAFE_ZIP_COMPRESS_TYPES = (0, 8)  # ZIP_STORED, ZIP_DEFLATED


def unsupported_zip_member(info) -> str:
    """Reason (German, user-facing) when a zip member's compression method is unsafe
    to decompress from untrusted input; empty string when it is fine."""
    if info.compress_type not in _SAFE_ZIP_COMPRESS_TYPES:
        return f"nicht unterstütztes Komprimierverfahren ({info.compress_type})"
    return ""
