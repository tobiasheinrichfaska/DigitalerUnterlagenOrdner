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
  handled), **Create folder**, **inline Rename** (click a selected name again),
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
**Configurable split (#13):** the dialog can split the export into several files above a page
threshold, at a chosen break level — **top folders**, **any folder boundary**, or **mid-document**
(a per-page cut that may split one document across files). Acceptance: above the threshold the
export writes multiple part files, each a valid PDF with a per-file TOC + cross-references; the
notice reports the file count. (Split mode uses its own TOC, not the index/bookmarks toggles.)

## 6. Persistence
- **Speichern saves in place** once the document has a path (no dialog), clearing the dirty
  "•"; **Speichern unter…** prompts. Node **ids round-trip** (persisted in `/JSONStructure`).
- Re-opening a `.belegtool` restores the schema losslessly; a committed node returns
  coherently (`current_data` set, `original_data` None) and drop-source-on-save is unchanged.

## 7. DATEV mode (v3.10.0 / v3.11.x — off by default, opt-in per user)
Only when the per-user **DATEV mode** is on (header „DATEV" toggle); when off, the `datev`
package is never imported and none of this is reachable.
- **Status + toggle**: the bar reflects `datev_status` (mode on/off, connected/not); toggling
  persists per-user (`%APPDATA%`, terminal-server safe) via `set_datev_mode`.
- **Connected document** (opened from a DATEV checkout path): shows the „Mit DATEV verknüpft"
  badge; **„Nach DATEV zurückschreiben"** runs the guarded write-back (`save_to_datev` →
  `datev_save_back`). On `ok` the linked DATEV document is overwritten (a backup is written
  first) **and the bound `.belegtool` is saved locally in parallel** (no Save-As prompt); a
  non-ok verdict (`declined`/`locked`/`conflict_changed`/`conflict_content`/`no_structure_item`)
  writes **nothing** to DATEV and offers a local save instead.
- **Not-connected document**: **„Nach DATEV ablegen"** files it as a NEW DATEV document under a
  prompted Mandant (`datev_file`), then shows „verknüpft".
- **Export → DATEV (same client)**: with a connected document, the export dialog offers „Nach
  DATEV ablegen (gleicher Mandant)"; `datev_export` files **every produced PDF** (single or each
  split part) as its own new document; a partial failure reports „Nur X von Y …".
- **PDF opening (PDF-Tool surface)**: a DATEV checkout `.pdf` opens in the PDF-Tool, which must
  also offer DATEV — **„🔗 Nach DATEV zurückschreiben"** for a connected checkout (bakes the edit
  into the node, then the guarded write-back) and **„📤 Nach DATEV ablegen"** for a not-connected
  PDF. The first write-back of an unedited checkout must **not** false-conflict (baseline hashes
  the raw checkout file). DATEV mode off → no button.
- **Format-clarity on local save**: the parallel local save writes the bound path's own format —
  a `.belegtool` (organizer) keeps structure + provenance; a checkout `.pdf` (PDF-Tool) is
  overwritten with clean effective PDF bytes — and the success notice **names the saved file** so
  the user can tell which format landed (`local_kind`).
- **Filing dialog (v3.11.0)**: „Nach DATEV ablegen" and the export-to-DATEV action open a filing
  dialog (searchable Mandant, folder/register, Belegdatum, Veranlagungsjahr/-monat). A **Bezeichnung**
  (the DATEV document name, prefilled) is required; filing without one is refused.
- **No connection or no client list → no DATEV write**: with no live connection, or when the
  master data (client list) cannot be read, filing and write-back are refused with a message and
  nothing is sent.
- **Checked-out document**: the „Nach DATEV zurückschreiben" button is hidden for a document that
  is checked out; **💾 Speichern** writes the local working copy instead (check it in via DATEV). A
  write-back that is invoked anyway reports `checked_out_self` and saves locally.
- **Node binding in the PDF-Tool**: a node opened in the PDF-Tool always offers file-anew; filing it
  creates a new DATEV document and pushes the baked bytes back to the owner node so the organizer
  shows the edit.
- **Non-blocking connect**: opening a checkout never waits on the SSO handshake; while the connect is
  still running the UI reports `connecting`, and the write-back completes the baseline when it runs.
- Acceptance: with mode **off**, a normal launch never touches DATEV and the badge/actions are
  absent. With mode **on** + a fake/real service, the verdicts above are honoured and a refused
  write-back never overwrites the server. (Live end-to-end = `manual_tests/10_datev.md`.)

## 8. Language, status bar & windows
- **Language switcher** (22 entries incl. Deutsch and English (US)/(UK); the others fall
  back to German for any untranslated string) translates all UI text live and persists the
  choice; document content/names are not translated.
- **Status bar**: background activity (Komprimiere N by node / Vorschau lädt / Cache füllt) and
  the render-cache gauge (used/budget MB · cached/total pages) with **＋ / −** to grow/shrink
  the budget (shrink evicts immediately).
- **Multiple windows**: a second window opens and starts cleanly (the bridge waits for each
  method to be callable, not just for the API object to exist).

## 9. Tags & tag views (v3.8.0 / v3.9.0)
- Tagging is **off by default** (toolbar 🏷️) and auto-enables when a loaded file already has tags.
  Tags are persisted per node; multi-select applies or removes one tag across all selected nodes
  as one undo step.
- **Search** filters by tag only (never by name); a matching tag keeps the whole subtree.
  **Group by tag** shows one synthetic folder per tag; nodes may appear under several tags.
- Acceptance: while a search or group view is active, reorder, import, add-folder, delete, group,
  merge and split are disabled; content edits stay available. „In neuem Fenster öffnen" on a tag
  search writes a temp document with just the displayed nodes in normal tree order.

## 10. PDF-Tool surface (v3.11.x)
- A `.pdf` (or a node opened „in PDF-Tool") opens with a selectable text layer and interactive
  AcroForm fields; „✎ Text" adds FreeText, and added text reopens as editable FreeText.
- **💾 Speichern** on a node binding writes the bytes back to the owner node (undoable in the
  organizer); external links open in the system browser, never in the app window.
- Acceptance: a scanned PDF renders its pages (not blank); compression from this surface is not
  wired (see `CLAUDE.md`, Known Limitations).

## 11. Compression marker & no-gain verdict (v3.9.0)
- A **red dot at the front** of a leaf row marks compression as **undecided** (not applied, not
  marked „no compression", no persisted no-gain verdict). Folder rows show it if any descendant
  leaf is undecided.
- When evaluation finds nothing smaller, the verdict is **persisted** in the document
  (`compression_no_gain`, silent, no undo) and survives save/reopen and moves; it is cleared on rotate.
- Acceptance: a no-gain node shows no red dot after reopen; a cancelled evaluation is not flagged;
  the cheap (≤5-page) undecided leaves resolve in the background after a load.

## 12. File lock — single writer (v3.9.0, off by default)
- Enabled only with the environment variable `BELEG_FILE_LOCK=1`. Opening a `.belegtool` takes an
  exclusive lock for the window's lifetime; a second user gets an „in use" message instead.
- Locked saves go through the lock handle with a `.bak` and a `.wip` marker; an interrupted save is
  restored from `.bak` on the next open.
- Acceptance: a second open of the same file reports „in use"; save-as re-locks the new file; closing
  the window releases the lock. Not yet: a graphical toggle, autosave/recover, read-only fallback.
