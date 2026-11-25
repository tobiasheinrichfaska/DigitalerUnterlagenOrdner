"""belegtool-archives: bomb-guarded extraction of ZIP / TAR / TGZ / EML / MSG containers
into a nested structure (``{"name", "content"|"children"}``). No host-application imports.

Member conversion (image/Office/HTML -> PDF) is injected via ``convert_member``.
"""

from .archives import (
    ConvertMember,
    extract_email_to_structure,
    extract_tar_to_structure,
    extract_zip_to_structure,
)
from .limits import BOMB_CAP_BYTES, BOMB_CAP_ENTRIES, unsupported_zip_member

__all__ = [
    "ConvertMember",
    "extract_zip_to_structure",
    "extract_tar_to_structure",
    "extract_email_to_structure",
    "BOMB_CAP_BYTES",
    "BOMB_CAP_ENTRIES",
    "unsupported_zip_member",
]
__version__ = "0.1.0"
