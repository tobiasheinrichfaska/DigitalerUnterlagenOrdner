# FEATURES_REQUIRED — DigitalerUnterlagenOrdner (BelegTool)

Critical user paths the app must support (React/pywebview front end, `host.py`).
Each lists the observable acceptance an audit or manual smoke test can check.
Keep in sync with `CLAUDE.md` and the `manual_tests/` files.

---

## 1. Import → tree
- **PDF / .belegtool**: a PDF becomes a leaf under the drop target / selected folder;
  a `.belegtool` restores its full tree. **Images / Office / Archives / Email** convert
  as before (image→PDF, COM→PDF, archive→nested folders with a zip-bomb guard,
  email→body+attachments subtree). A container **nested inside another** (a zip in a zip,
  a `.msg`/`.eml` in a zip, a zip attached to a mail) is **recursed** into a sub-folder,
  depth-bounded (`_ARCHIVE_MAX_DEPTH`) with a **shared** bomb budget across levels (#12).
- Acceptance: new nodes appear; the document is **dirty** (Save offered); the render
  cache **starts warming on its own** (no node click needed).

## 2. Tree editing
- **Split** (per page / N pages / into a folder), **Merge** (sibling leaves, DPI-conflict
  handled), **Create folder**, **inline Rename** (click a selected name again), **deep copy**,
  **drag-and-drop** move.
- **Keyboard structuring**: ↑/↓ navigate visible rows, ←/→ collapse/expand, **Insert**
  grabs a node and arrows move it *optically* until **Insert** drops it (one undo) or **Esc**
  reverts. Folder **collapse is persisted** in the file.
- **Multi-delete (Entf / context menu)**: deletes the *whole selection* in one undo, then
  focuses the next node. A selection mixing a folder with items inside it is **resolved in
  the UI first** (include all / exclude folder / abort); the data layer **rejects** a mixed
  set. The same resolver applies to **move / group / export**.
- Acceptance: model and tree stay consistent; deleted nodes' cached renders are freed.

## 3. Preview & compression
- Virtualized windowed preview; the middleware warms the cache (current node, then
  neighbours, until full) and yields to compression. First page loads on select (no scroll).
- Compression: DPI 50–300; methods JPG/JPG-color/PNG/pikepdf, smallest offered, larger
  hidden; the source size is shown. Nodes **≤ 5 pages default to the smallest variant** on
  display; the chosen method is **remembered** per node. **Lesbarkeit geprüft** applies it.
- **Split carries** an applied compression into the parts (verbatim, no recompute; pikepdf
  recomputes). **Splitting/deleting/merging** a node **cancels** its in-flight compression.
- **Variants persist**: computed-but-unapplied variants are embedded in the `.belegtool`
  (hidden per-node attachments) and rehydrated on reopen → **no recompute**.
- Acceptance: `is_compressed`/`dpi_current` are coherent; a committed node has no source
  ("bereits komprimiert (keine Quelle)") and re-compress/reset are blocked.

## 4. Status system
Each node has a status — `erfasst` / `zu erfassen` / `vorjahreswert` — set from the context
menu; the vocabulary comes from the core (`config().statuses`), labels via i18n.

## 5. Export
Export the selection (resolved) to a single PDF with a printed TOC, clickable links and
sidebar bookmarks. Acceptance: the PDF opens and the TOC links hit the right pages.
**Known gap:** exports over 100 pages stay a single PDF — the auto-split-with-
cross-references path (`toc_export.export_pdf_split_with_toc`) exists but is **not yet wired
into the UI export** (consistent with CLAUDE.md / BETA_TESTING §4).

## 6. Persistence
- **Speichern saves in place** once the document has a path (no dialog), clearing the dirty
  "•"; **Speichern unter…** prompts. Node **ids round-trip** (persisted in `/JSONStructure`).
- Re-opening a `.belegtool` restores the schema losslessly; a committed node returns
  coherently (`current_data` set, `original_data` None) and drop-source-on-save is unchanged.

## 7. Language, status bar & windows
- **Language switcher** (22 entries incl. Deutsch and English (US)/(UK); the others fall
  back to German for any untranslated string) translates all UI text live and persists the
  choice; document content/names are not translated.
- **Status bar**: background activity (Komprimiere N by node / Vorschau lädt / Cache füllt) and
  the render-cache gauge (used/budget MB · cached/total pages) with **＋ / −** to grow/shrink
  the budget (shrink evicts immediately).
- **Multiple windows**: a second window opens and starts cleanly (the bridge waits for each
  method to be callable, not just for the API object to exist).
