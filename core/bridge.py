"""Bridge between the immutable Document model and the existing PDFStorage/.belegtool.

Lets the data-driven core read/write the real on-disk format and interoperate
with the current (mutable) PDFNode/PDFStorage app objects.

- ``document_from_storage`` / ``document_to_storage`` — in-memory, full fidelity
  (every field + page bytes; folders hold no bytes; node ids preserved via uid).
- ``load_belegtool`` / ``save_belegtool`` — go through a real ``.belegtool`` file.
  The file format does not store node ids, so a freshly loaded document gets new
  ids (ids are session-scoped anyway).
"""

from __future__ import annotations

from core.model import Document, Node


def _node_from_pdfnode(pn) -> Node:
    return Node(
        name=pn.name,
        is_folder=pn.is_folder,
        id=pn.uid,
        status=pn.status,
        vz_start=pn.vz_start,
        vz_end=pn.vz_end,
        pdf_length=pn.pdf_length,
        is_compressed=pn.is_compressed,
        dpi_original=pn.dpi_original,
        dpi_current=pn.dpi_current,
        no_compression=pn.no_compression,
        collapsed=getattr(pn, "collapsed", False),
        compression_method=getattr(pn, "compression_method", None),
        tags=tuple(getattr(pn, "tags", ()) or ()),
        children=tuple(_node_from_pdfnode(c) for c in pn.children),
        # raw per-node bytes (folders have none — never the aggregated property)
        original_data=getattr(pn, "_original_pdf_data", None),
        current_data=getattr(pn, "_current_pdf_data", None),
    )


def document_from_storage(storage) -> Document:
    return Document(_node_from_pdfnode(storage.root))


def node_from_pdfnode(pn) -> Node:
    """Public: convert a single (imported) PDFNode subtree into an immutable Node."""
    return _node_from_pdfnode(pn)


def _pdfnode_from_node(node: Node):
    from formats.pdf_node import PDFNode
    pn = PDFNode(name=node.name, is_folder=node.is_folder, pdf_data=None)
    pn.uid = node.id
    pn.status = node.status
    pn.vz_start = node.vz_start
    pn.vz_end = node.vz_end
    pn.pdf_length = node.pdf_length
    pn.is_compressed = node.is_compressed
    pn.dpi_original = node.dpi_original
    pn.dpi_current = node.dpi_current
    pn.no_compression = node.no_compression
    pn.collapsed = node.collapsed
    pn.compression_method = node.compression_method
    pn.tags = list(node.tags)
    if not node.is_folder:
        # property setters store the bytes without triggering lazy compression
        pn.original_pdf_data = node.original_data
        pn.current_pdf_data = node.current_data
    for child in node.children:
        pn.add_child(_pdfnode_from_node(child))
    return pn


def document_to_storage(doc: Document):
    from formats.pdf_storage import PDFStorage
    storage = PDFStorage()
    storage.root = _pdfnode_from_node(doc.root)
    return storage


def load_belegtool(path) -> Document:
    from formats.pdf_storage import PDFStorage
    return document_from_storage(PDFStorage(str(path)))


def save_belegtool(doc: Document, path) -> None:
    document_to_storage(doc).save(str(path))
