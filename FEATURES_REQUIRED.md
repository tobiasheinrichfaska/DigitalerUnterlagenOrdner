# FEATURES_REQUIRED — DigitalerUnterlagenOrdner (BelegTool)

Critical user paths the application must support. Each flow lists the steps and
the observable acceptance criteria an audit (or a manual smoke test) can check.
Keep this in sync with the feature set in `CLAUDE.md`.

---

## 1. Import → tree

- **PDF / .belegtool**: importing a PDF adds it as a leaf node under the current
  storage root; a `.belegtool` file restores its full tree.
- **Images** (jpg, png, webp, heic): converted to a single-page PDF node.
- **Office** (Word, Excel, PPT): converted to PDF via COM, added as a node.
- **Archives** (ZIP, TAR): folder structure preserved as nested folder nodes;
  member-count and uncompressed-size limits enforced (zip-bomb guard).
- **Email** (eml, msg): body + attachments extracted into a folder subtree.

Acceptance: after import the new node(s) appear in the TreeView and a preview is
generated (lazily); the file is marked dirty so Save is offered.

## 2. Tree editing

- **Split** a multi-page leaf into one node per page.
- **Merge** sibling nodes / folders (with DPI-conflict handling — see §3).
- **Create folder** inside / below the selection.
- **Rename** (F2), **Delete** (Entf), **deep copy**.
- **Drag-and-drop** move (Ctrl = copy), **keyboard move** (Ctrl+arrows).

Acceptance: the model and the TreeView stay consistent after every operation;
node↔tree-item lookups remain valid (see `register_node`/`unregister_node`).

## 3. Preview & compression

- Preview is lazy-generated and cached; a placeholder shows until ready.
- DPI slider 50–300; multi-method compression (JPG / PNG / pikepdf) picks the
  smallest result; methods larger than the original are hidden.
- **Commit** replaces the original with the compressed version; **Reset**
  restores the original.
- A node flagged `no_compression` is never re-compressed.
- **DPI conflict on merge**: if two nodes were compressed at different DPI, the
  compressed data is discarded, `dpi_current` is cleared, `no_compression`
  becomes True and `is_compressed` becomes False (no contradictory state).

Acceptance: `is_compressed` / `dpi_current` reflect the actual state; a folder's
data aggregates every child's effective data (uncompressed leaves,
`no_compression` nodes and sub-folders included).

## 4. Status system

Each node carries a status — `erfasst` (green), `zu erfassen` (blue,
highlighted), `vorjahreswert` (red, highlighted) — settable from the menu /
context menu and reflected in the TreeView colours.

## 5. Export

- Export selection to a **single PDF with a printed table of contents**,
  clickable TOC links and sidebar bookmarks; auto-split above 100 pages with
  cross-references.
- Export / save in the **.belegtool** format (metadata + ZIP) and reload it
  losslessly.

Acceptance: the exported PDF opens, contains every selected node's pages, and
the TOC entries link to the correct pages.

## 6. Persistence

- **Save** / **Save as** write the current tree to `.belegtool`.
- Re-opening a `.belegtool` round-trips the node schema (name, is_folder,
  status, vz_start/end, pdf_length, is_compressed, dpi_original, dpi_current,
  no_compression, children).

---

## Test / QA mode

`Ansicht → Testmodus` shows, per golden-master operation (compression, split,
merge), the input fixture next to the live result and the committed expected
reference. It expects `tests/data/input/` to be present (regenerate with
`python tests/make_fixtures.py`).
