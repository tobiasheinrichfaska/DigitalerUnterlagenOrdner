"""Shared bomb-guard caps for untrusted-container decoding.

Single source of truth for the decoded-size / entry-count limits applied
wherever bytes from untrusted input are inflated (archive members, embedded
compression-variant blobs, PDF repair output). Defined once so the mirrored
caps in ``universal_importer/archives.py``, ``services/variant_blobs.py`` and
``infra/tools.py`` cannot silently drift apart.
"""

BOMB_CAP_BYTES = 500 * 1024 * 1024  # 500 MB decoded
BOMB_CAP_ENTRIES = 500
