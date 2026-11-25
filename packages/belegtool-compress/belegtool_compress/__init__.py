"""belegtool_compress - render-based and structural PDF compression with CPU-fairness primitives.

Public surface: ``compress_all_methods``, ``compress_pdf_bytes``, ``CompressionCancelled``,
``CompressionConfig``, ``DEFAULT_CONFIG``; helpers live in ``compress``, ``cpu`` and ``pixels``.
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

__version__ = "0.1.0"
