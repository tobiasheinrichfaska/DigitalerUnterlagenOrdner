"""Embed/read per-node compression variants in a .belegtool, as PDF attachments
keyed by node id (``variant_<id>``). Attachments are not pages and not tree nodes —
invisible in the document, ignored by plain PDF viewers and older app versions.

On save we attach each node's computed variants (from the engine); on open we read
them back and seed the engine so re-selecting the node is instant (no recompute).
Only nodes that still have a source are stored — a committed ("Lesbarkeit geprüft")
node dropped its source on save and IS its compressed result, so it needs none.
"""

from __future__ import annotations

import pikepdf
from infra.log_config import logger
from services import variant_blobs

_PREFIX = "variant_"
DEFAULT_BUDGET = 300 * 1024 * 1024  # cap embedded-variant bytes per file


def embed_variants(path, doc, engine, budget_bytes: int = DEFAULT_BUDGET) -> int:
    """Attach every node's variants to the .belegtool at ``path``. Returns the count
    of nodes whose variants were embedded."""
    if not hasattr(engine, "variants_for"):
        return 0
    blobs, total = {}, 0
    for n in doc.root.iter():
        if n.is_folder or not n.original_data:
            continue
        variants = engine.variants_for(n.original_data)
        if not variants:
            continue
        blob = variant_blobs.pack(variants)
        if total + len(blob) > budget_bytes:
            continue  # stay within the per-file budget
        blobs[_PREFIX + n.id] = blob
        total += len(blob)
    if not blobs:
        return 0
    try:
        with pikepdf.open(path, allow_overwriting_input=True) as pdf:
            for name, blob in blobs.items():
                pdf.attachments[name] = pikepdf.AttachedFileSpec(
                    pdf, blob, filename=name, mime_type="application/zip")
            pdf.save(path)
    except Exception as e:  # never let variant persistence break a save
        logger.warning("[variants] embed failed: %s", e)
        return 0
    return len(blobs)


def seed_variants_from_file(path, doc, engine) -> int:
    """Read embedded variants from ``path`` and seed ``engine`` for the matching nodes.
    Returns the count seeded."""
    if not hasattr(engine, "seed_variants"):
        return 0
    data_by_id = {}
    try:
        with pikepdf.open(path) as pdf:
            for name in list(pdf.attachments):
                if not name.startswith(_PREFIX):
                    continue
                try:
                    data_by_id[name[len(_PREFIX):]] = pdf.attachments[name].get_file().read_bytes()
                except Exception:
                    continue
    except Exception as e:
        logger.warning("[variants] read failed: %s", e)
        return 0
    by_id = {n.id: n for n in doc.root.iter() if not n.is_folder and n.original_data}
    seeded = 0
    for nid, blob in data_by_id.items():
        node = by_id.get(nid)
        if node is None:
            continue
        variants = variant_blobs.unpack(blob)
        if variants:
            engine.seed_variants(node.original_data, variants)
            seeded += 1
    return seeded
