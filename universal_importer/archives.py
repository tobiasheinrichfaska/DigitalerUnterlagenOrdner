"""Compatibility shim: container extraction lives in the separable package
``belegtool_archives`` (packages/belegtool-archives). This module re-exports its public
and test-visible surface and injects :class:`UniversalImporter` as the member converter,
so all former import paths keep working unchanged.
"""

import functools

import belegtool_archives.archives as _impl
from belegtool_archives.archives import (  # noqa: F401  (re-exports)
    _ARCHIVE_MAX_DEPTH,
    _ARCHIVE_MAX_MEMBERS,
    _ARCHIVE_MAX_UNCOMPRESSED_BYTES,
    _MAX_PATH_DEPTH,
    _MAX_TOTAL_FOLDER_DEPTH,
    _Budget,
    _new_budget,
    _not_importable,
    _split_member_path,
)

from .importer import UniversalImporter


def _convert_member(content: bytes, name: str):
    """The injected converter: image / Office / HTML / ... -> PDF (BytesIO)."""
    return UniversalImporter.convert(content, name=name).data


def _with_converter(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        kwargs.setdefault("convert_member", _convert_member)
        return fn(*args, **kwargs)
    return wrapper


extract_zip_to_structure = _with_converter(_impl.extract_zip_to_structure)
extract_tar_to_structure = _with_converter(_impl.extract_tar_to_structure)
extract_email_to_structure = _with_converter(_impl.extract_email_to_structure)
