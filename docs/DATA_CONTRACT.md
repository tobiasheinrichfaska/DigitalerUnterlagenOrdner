# Data Contract — DigitalerUnterlagenOrdner (BelegTool)

The stable shapes that decouple the **data** from any UI. The React/pywebview host
uses them in-process (the legacy Tk GUI was removed in v3.6.0); the core service can
send the same shapes over IPC to the React UI. Treat changes here as
**data-format changes** (semantic-versioning MAJOR if a `.belegtool` written by
an old build would no longer load).

---

## 1. Node tree (JSON) — `PDFNode.to_dict()` / `PDFStorage._parse_node()`

Each node serialises to this object (see `pdf_node.py::to_dict`):

| Field | Type | Meaning |
|---|---|---|
| `uid` | string | **persisted node id** (uuid4 hex) — written to `/JSONStructure` and restored on load, so ids survive save/reopen (tag views, variant keys, DATEV bindings rely on it) |
| `name` | string | display name |
| `is_folder` | bool | folder vs. leaf (document) |
| `status` | string | `""` (no status) or one of `"erfasst"`, `"zu erfassen"`, `"vorjahreswert"` |
| `position` | int \| null | sibling order within the parent |
| `vz_start` | int \| null | accounting period start (Verzeichniszeitraum) |
| `vz_end` | int \| null | accounting period end |
| `pdf_length` | int | page count of this node's own pages (0 for folders) |
| `is_compressed` | bool | a smaller compressed version is the current data |
| `dpi_original` | int \| null | DPI the original was captured at, if known |
| `dpi_current` | int \| null | DPI of the current (compressed) data; null if uncompressed / conflict |
| `no_compression` | bool | node must not be (re-)compressed (e.g. split parts) |
| `compression_method` | string \| null | method that produced `current_data` (`"jpg"`, `"png"`, `"pikepdf"`); null if uncompressed / merge conflict |
| `compression_no_gain` | bool | evaluated, nothing smaller found → the "undecided" dot stays resolved across moves/reopen (set silently, no undo/dirty) |
| `collapsed` | bool | folder collapsed in the tree view (persisted) |
| `tags` | array of string | free-form labels (folders & leaves); set via `SetTags`. Stored per-node (own tags only). For search/group, *effective* tags = own ∪ ancestor-folder tags (computed in the view, never duplicated into children). |
| `datev` | object \| null | DATEV provenance on the ROOT node only (`doc_guid`, `file_id`, `structure_item_id`, …); null everywhere else |
| `children` | array of node | nested nodes (folders and leaves) |

Invariants worth preserving (already enforced / tested):
- A folder's **effective data** is the concatenation of its children's effective
  data (current → original fallback, recursing into sub-folders); folders carry
  no page bytes of their own.
- DPI-conflict on merge ⇒ `no_compression = true`, `dpi_current = null`,
  `is_compressed = false` (no contradictory "compressed + no_compression").
- **Split/Merge carry metadata (QS 2026-11-04, M-2):** split parts inherit
  `tags`, `vz_start`/`vz_end` and `dpi_original` (never the id or compression
  flags); the SplitInto folder variant puts the tags on the NEW FOLDER (tag views
  inherit them — per-part tags would list every part in the tag index), the parts
  keep the vz. Merge unions the tags (ordered, deduped) and spans the vz
  (min start … max end over the inputs that carry one). `SetNodeBytes` recomputes
  `pdf_length` from the new bytes (stale counts corrupt the reload slicing).
- `uid` **is serialised and restored** (corrected 2026-11-04 — the old claim
  here contradicted the code): `pdf_node.to_dict` writes it, `pdf_storage`
  restores it, so the same file open twice shares node ids and tag views /
  variant keys / DATEV bindings survive a reopen.

**Page bytes are not in this JSON.** The JSON is the *structure*; the bytes live
alongside it (in the `.belegtool` PDF today; as separate blobs over IPC later).

---

## 2. `.belegtool` file format

A `.belegtool` is a **single PDF** that carries both the page content and the
structure (see `PDFStorage.save` / `_load_pdf` / `_parse_json_structure`):

1. **Pages:** every node's pages, appended depth-first via
   `_append_pages_with_outline`, with PDF **outline/bookmarks** mirroring the tree.
2. **Structure:** the full `to_dict()` tree, JSON-encoded, stored in PDF metadata
   under the key **`/JSONStructure`**.
3. Optionally re-compressed losslessly with pikepdf on save.

**Load:** open the PDF → read `/JSONStructure` → walk it, assigning each node its
pages by `pdf_length` (a running page cursor). No JSON ⇒ the PDF is imported as a
single leaf node.

**Load integrity (QS 2026-11-04, H-1/M-3/N-4 + Bewertungsrunde).** Loading stays
tolerant, but every degradation is COLLECTED in `PDFStorage.load_warnings` instead of
only logged: an unreadable page tree (after one REAL repair attempt — a full pikepdf
rewrite, also triggered when pypdf tolerantly reports 0 pages although the structure
has leaves; a successful repair still warns, because the repaired bytes are not the
on-disk file), an unparseable or MISSING structure in a `.belegtool` (→ single-node
fallback; for the app's own extension the metadata is read even when the raw
`/JSONStructure` marker is hidden in a compressed object stream — a rewritten file
keeps its tree), a node starting past the page end (skipped), a node reaching past it
(truncated), pages beyond what the structure describes (externally appended), and a
negative/non-int `pdf_length` (treated as 0 — the cursor never moves backwards; a
legitimate `0` stays warning-free). `vz_start`/`vz_end` coerce to int-or-None on load
(mixed types would crash Merge's span). `CoreApi.open` surfaces the warnings as
`warning` and **does not bind the path** of a degraded load, so Ctrl+S becomes
Save-As (the host suggests `<name> (wiederhergestellt)` so Enter+Ersetzen cannot hit
the original) and the still-rescuable original is never overwritten; `_import_path`
**refuses** a degraded `.belegtool`/PDF with the reason.

**Save (unlocked) is atomic** (M-1): `PDFStorage.save` writes a sibling temp file
and `os.replace`s it over the target (in-place fallback only when the target is
held open elsewhere). The locked path keeps its `.bak` scheme, now with a `.wip`
in-flight marker so an interrupted locked save is restored reliably on next open.

This "PDF + embedded JSON" design means a `.belegtool` also opens as an ordinary
PDF in any viewer (you just see the concatenated pages + bookmarks).

---

## 3. Operation surface (what the core service will expose)

The IPC API the React UI calls — each maps to existing, UI-agnostic logic:

| Operation | Backed by |
|---|---|
| `open(path)` → tree JSON | `PDFStorage(path)` |
| `save(path)` / `save()` | `PDFStorage.save` |
| `import_paths(paths)` / `import_bytes(name, b64)` → tree | `_import_path` (PDFStorage / `UniversalImporter.convert`) + `InsertNodes` |
| `split` / `merge` / `add_folder` / `rename` / `delete` / `move` | `PDFNode` tree ops |
| `compress(node, dpi)` / `commit` / `reset` | `PDFNode.compress*` / `compress_pdf_bytes` |
| `export(nodes, path)` | `toc_export` (ausschließlich; `export_selection` entfernt 2026-11-04) |
| `render_preview(node|pageRef, dpi)` → **PNG bytes** | `services/render.render_pdf_to_pngs` |
| `render_compressed(node, dpi, method)` → **PNG bytes** | `engine.compress` + `render_pdf_to_pngs`, **read-only** |
| progress / busy signals | status-bar polling (`render_stats`, compressing count) |

Long-running ops (compress/render/export) run on background daemon threads and the
CPU-fair worker pools (`services/cpu`); the UI polls their state. (A dedicated
`tasks`/`progress` port never got a consumer and was removed 2026-11-04.)

**Working preview (compression).** Selecting a leaf does **not** compress the
document. The UI browses methods/DPI through `render_compressed` (read-only — it
compresses the original bytes and rasterises the result without storing anything),
so there is no undo entry and the node never becomes pending while browsing. The
document changes only on a deliberate apply: `Compress` (“❓ Lesbarkeit geprüft”)
or `Reset` (“Original”). This keeps undo meaningful and the preflight quiet until
a real compression exists.

**Defaults.** The default compression DPI is a fixed core constant
(`DEFAULT_COMPRESSION_DPI = 150`, surfaced via `CoreApi.config()` → `default_dpi`),
and the default method is "best" (smallest of `compress_methods`). The UI reads
these from the core rather than hardcoding them.

---

## 4. Stability

- Adding an **optional** node field with a sensible default = backwards-compatible
  (MINOR). Loaders must ignore unknown fields.
- Renaming/removing a field, or changing `.belegtool`'s `/JSONStructure` key or
  page-mapping rule = **breaking** (MAJOR) — provide a migration/loader fallback.
- Round-trip is covered by `tests/test_pdf_storage_structure.py`,
  `tests/test_import_belegtool_root.py`, and the split/merge golden masters.
