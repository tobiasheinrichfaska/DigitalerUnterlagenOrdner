"""Embed/read per-node compression variants in a .belegtool, as PDF attachments
keyed by node id (``variant_<id>``). Attachments are not pages and not tree nodes —
invisible in the document, ignored by plain PDF viewers and older app versions.

On save we attach each node's computed variants (from the engine); on open we read
them back and seed the engine so re-selecting the node is instant (no recompute).
Only nodes that still have a source are stored — a committed ("Lesbarkeit geprüft")
node dropped its source on save and IS its compressed result, so it needs none.
"""

from __future__ import annotations

import io
import zlib

import pikepdf
from infra.log_config import logger
from services import variant_blobs

_PREFIX = "variant_"
DEFAULT_BUDGET = 300 * 1024 * 1024  # cap embedded-variant bytes per file
MAX_ATTACHMENTS = 500  # bomb guard: cap variant_* attachments read from an untrusted file
# Bomb guards at THIS layer too (2026-06-12): pikepdf's read_bytes() inflates the
# embedded-file's /FlateDecode stream uncapped, so the caps in variant_blobs.unpack
# alone sit BELOW where a deflate bomb would detonate. Mirror unpack's magnitudes.
MAX_ATTACHMENT_BYTES = variant_blobs.MAX_TOTAL_BYTES  # decoded cap per attachment
MAX_TOTAL_ATTACHMENT_BYTES = variant_blobs.MAX_TOTAL_BYTES  # decoded cap across all attachments


def _read_attachment_capped(filespec, max_bytes: int):
    """Decoded bytes of an embedded-file attachment, bounded against deflate bombs.

    Reads the RAW (stored) stream first — cheap, bounded by the file on disk — and
    inflates it incrementally with a hard decoded-size cap, instead of pikepdf's
    uncapped ``read_bytes()``. Legit blobs are stored ZIPs of already-compressed
    PDFs (raw ≈ decoded), so the cap never bites them. Returns ``None`` when over
    cap or not safely decodable (fail-safe: skip → the variants just recompute)."""
    stream = filespec.get_file().obj
    raw = stream.read_raw_bytes()
    if len(raw) > max_bytes:
        return None
    filters = stream.get("/Filter", None)
    if filters is None:
        return bytes(raw)
    names = [str(f) for f in filters] if isinstance(filters, pikepdf.Array) else [str(filters)]
    if names != ["/FlateDecode"] or stream.get("/DecodeParms", None) is not None:
        return None  # never inflate an unexpected encoding blind
    d = zlib.decompressobj()
    try:
        out = d.decompress(bytes(raw), max_bytes + 1)
    except zlib.error:
        return None
    if len(out) > max_bytes or d.unconsumed_tail:
        return None  # decoded size exceeds the cap — a bomb reveals itself at cap+1 bytes
    out += d.flush()
    return out if len(out) <= max_bytes else None


def pending_variant_count(doc, engine) -> int:
    """How many nodes have computed compression alternatives a save *would* embed
    (dry run — no write). Mirrors embed_variants' node predicate: a non-folder,
    NOT-yet-compressed node with a source whose engine memo holds variants. A node
    that already has a compression applied (``is_compressed``, "Lesbarkeit geprüft")
    has chosen its one version — its other alternatives are dead (the source is
    dropped on save, re-compress is blocked), so they're never offered or embedded.
    """
    if not hasattr(engine, "variants_for"):
        return 0
    count = 0
    for n in doc.root.iter():
        if n.is_folder or n.is_compressed or not n.original_data:
            continue
        if engine.variants_for(n.original_data):
            count += 1
    return count


def _collect_variant_blobs(doc, engine, budget_bytes: int) -> dict:
    """Per-node variant ZIP blobs to embed (keyed ``variant_<id>``), within the budget.
    Applied-compression nodes drop their source on save → no live alternatives → skipped."""
    if not hasattr(engine, "variants_for"):
        return {}
    blobs, total = {}, 0
    for n in doc.root.iter():
        if n.is_folder or n.is_compressed or not n.original_data:
            continue
        variants = engine.variants_for(n.original_data)
        if not variants:
            continue
        blob = variant_blobs.pack(variants)
        if total + len(blob) > budget_bytes:
            continue  # stay within the per-file budget
        blobs[_PREFIX + n.id] = blob
        total += len(blob)
    return blobs


def _attach_blobs(pdf, blobs: dict) -> None:
    for name, blob in blobs.items():
        pdf.attachments[name] = pikepdf.AttachedFileSpec(
            pdf, blob, filename=name, mime_type="application/zip")


def embed_variants(path, doc, engine, budget_bytes: int = DEFAULT_BUDGET) -> int:
    """Attach every node's variants to the .belegtool at ``path`` (in place). Returns the
    count embedded."""
    blobs = _collect_variant_blobs(doc, engine, budget_bytes)
    if not blobs:
        return 0
    try:
        with pikepdf.open(path, allow_overwriting_input=True) as pdf:
            _attach_blobs(pdf, blobs)
            pdf.save(path)
    except Exception as e:  # never let variant persistence break a save
        logger.warning("[variants] embed failed: %s", e)
        return 0
    return len(blobs)


def embed_variants_bytes(pdf_bytes: bytes, doc, engine,
                         budget_bytes: int = DEFAULT_BUDGET):
    """In-memory variant embed: return ``(new_bytes, count)`` — ``pdf_bytes`` with each
    node's variants attached. Used by the single-write/locked save path. On failure
    returns the input bytes unchanged (variant persistence never breaks a save)."""
    blobs = _collect_variant_blobs(doc, engine, budget_bytes)
    if not blobs:
        return pdf_bytes, 0
    try:
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            _attach_blobs(pdf, blobs)
            out = io.BytesIO()
            pdf.save(out)
            return out.getvalue(), len(blobs)
    except Exception as e:
        logger.warning("[variants] embed (bytes) failed: %s", e)
        return pdf_bytes, 0


def seed_variants_from_file(path, doc, engine) -> int:
    """Read embedded variants from ``path`` and seed ``engine`` for the matching nodes.
    Returns the count seeded."""
    if not hasattr(engine, "seed_variants"):
        return 0
    data_by_id = {}
    total = 0
    try:
        with pikepdf.open(path) as pdf:
            for name in list(pdf.attachments):
                if not name.startswith(_PREFIX):
                    continue
                if len(data_by_id) >= MAX_ATTACHMENTS:
                    logger.warning("[variants] attachment cap reached (%d); rest ignored",
                                   MAX_ATTACHMENTS)
                    break
                # Clamp the in-flight decode to the REMAINING total budget so a single
                # attachment can't transiently allocate the full per-attachment cap on
                # top of already-retained bytes (no ~2x peak). The per-attachment cap
                # still bounds an isolated decode; the post-decode total check stays.
                remaining = MAX_TOTAL_ATTACHMENT_BYTES - total
                if remaining <= 0:
                    logger.warning("[variants] total attachment budget reached; rest ignored")
                    break
                try:
                    blob = _read_attachment_capped(
                        pdf.attachments[name], min(MAX_ATTACHMENT_BYTES, remaining))
                except Exception:
                    continue
                if blob is None:
                    logger.warning("[variants] attachment %s over the size cap; skipped", name)
                    continue
                if total + len(blob) > MAX_TOTAL_ATTACHMENT_BYTES:
                    logger.warning("[variants] total attachment budget reached; rest ignored")
                    break
                total += len(blob)
                data_by_id[name[len(_PREFIX):]] = blob
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
