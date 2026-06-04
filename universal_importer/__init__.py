"""Universal file → PDF import.

Public surface (unchanged after the package split):
- ``UniversalImporter`` — detect a file's type and dispatch to a converter.
- ``ConvertedPDF`` — the converter result (name + PDF BytesIO).
- ``extract_zip_to_structure`` / ``extract_tar_to_structure`` /
  ``extract_email_to_structure`` — container extraction into nested structures.
- ``_not_importable`` — placeholder folder node for an unconvertible member.

Internals split by responsibility: `converters` (per-format conversion),
`importer` (detect + dispatch), `archives` (container extraction).
"""

from .converters import ConvertedPDF
from .importer import UniversalImporter
from .archives import (
    extract_zip_to_structure,
    extract_tar_to_structure,
    extract_email_to_structure,
    _not_importable,
)

__all__ = [
    "UniversalImporter",
    "ConvertedPDF",
    "extract_zip_to_structure",
    "extract_tar_to_structure",
    "extract_email_to_structure",
    "_not_importable",
]
