# Data Contract — DigitalerUnterlagenOrdner (BelegTool)

The stable shapes that decouple the **data** from any UI. Today the Tkinter app
uses them in-process; the future core service (see
[`REACT_MIGRATION_PLAN.md`](REACT_MIGRATION_PLAN.md), on `react-migration`) sends
the same shapes over IPC to the React UI. Treat changes here as
**data-format changes** (semantic-versioning MAJOR if a `.belegtool` written by
an old build would no longer load).

---

## 1. Node tree (JSON) — `PDFNode.to_dict()` / `PDFStorage._parse_node()`

Each node serialises to this object (see `pdf_node.py::to_dict`):

| Field | Type | Meaning |
|---|---|---|
| `name` | string | display name |
| `is_folder` | bool | folder vs. leaf (document) |
| `status` | string | one of `"erfasst"`, `"zu erfassen"`, `"vorjahreswert"` |
| `position` | int \| null | sibling order within the parent |
| `vz_start` | int \| null | accounting period start (Verzeichniszeitraum) |
| `vz_end` | int \| null | accounting period end |
| `pdf_length` | int | page count of this node's own pages (0 for folders) |
| `is_compressed` | bool | a smaller compressed version is the current data |
| `dpi_original` | int \| null | DPI the original was captured at, if known |
| `dpi_current` | int \| null | DPI of the current (compressed) data; null if uncompressed / conflict |
| `no_compression` | bool | node must not be (re-)compressed (e.g. split parts) |
| `compression_method` | string \| null | method that produced `current_data` (`"jpg"`, `"png"`, `"pikepdf"`); null if uncompressed / merge conflict |
| `children` | array of node | nested nodes (folders and leaves) |

Invariants worth preserving (already enforced / tested):
- A folder's **effective data** is the concatenation of its children's effective
  data (current → original fallback, recursing into sub-folders); folders carry
  no page bytes of their own.
- DPI-conflict on merge ⇒ `no_compression = true`, `dpi_current = null`,
  `is_compressed = false` (no contradictory "compressed + no_compression").
- `uid` is **not** serialised — it is a fresh per-instance runtime id
  (`uuid4`), unique per displayed node; it must not be relied on across saves.

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

This "PDF + embedded JSON" design means a `.belegtool` also opens as an ordinary
PDF in any viewer (you just see the concatenated pages + bookmarks).

---

## 3. Operation surface (what the core service will expose)

The IPC API the React UI calls — each maps to existing, UI-agnostic logic:

| Operation | Backed by |
|---|---|
| `open(path)` → tree JSON | `PDFStorage(path)` |
| `save(path)` / `save()` | `PDFStorage.save` |
| `import_file(bytes, name)` → node(s) | `UniversalImporter.convert` + `create_wrapper_node` |
| `split` / `merge` / `add_folder` / `rename` / `delete` / `move` | `PDFNode` tree ops |
| `compress(node, dpi)` / `commit` / `reset` | `PDFNode.compress*` / `compress_pdf_bytes` |
| `export(nodes, path)` | `toc_export` / `PDFStorage.export_selection` |
| `render_preview(node|pageRef, dpi)` → **PNG bytes** | `services/render.render_pdf_to_pngs` |
| `render_compressed(node, dpi, method)` → **PNG bytes** | `engine.compress` + `render_pdf_to_pngs`, **read-only** |
| progress / busy signals | `progress` port |

Long-running ops (compress/render/export) run on the executor (`tasks`) and the
worker pool; results/progress are pushed back to the UI.

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
