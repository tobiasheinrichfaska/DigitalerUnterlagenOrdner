"""Thin re-export of the separable package ``belegtool_compress`` (packages/belegtool-compress).

Kept so every existing import path (``core.engine`` lazy-imports ``compress_all_methods`` /
``CompressionCancelled``, ``host._prewarm``, tests) keeps working unchanged.
"""

from belegtool_compress.compress import (  # noqa: F401
    DEFAULT_CONFIG,
    CompressionCancelled,
    CompressionConfig,
    compress_all_methods,
    compress_pdf_bytes,
    recompress_with_pikepdf,
    reencode_pdf_structure,
)
