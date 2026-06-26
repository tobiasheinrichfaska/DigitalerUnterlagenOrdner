# 04 — Export & persistence

Covers exporting to PDF and saving/reloading the `.belegtool` format, in the
**React/pywebview UI**. Toolbar: **⬇ Export PDF** and **💾 Speichern**; opening is
**📂 Öffnen**. There is no menu bar.

---

## MT-14: Export to a PDF with table of contents

**Preconditions:** A document with several nodes/folders.

**Steps:**
1. Click **⬇ Export PDF** (or **Strg+E**) — or Ctrl-select some nodes first and right-click
   → **Auswahl als PDF exportieren (N)** (a single node → **Als PDF exportieren**).
2. In the **export-options dialog**, leave **TOC**, **Stichwortverzeichnis** (only offered
   when the document has tags) and **PDF-Lesezeichen** as desired, then confirm.
3. Choose a target `.pdf` path (the default filename is the **document name + .pdf**) and save.
4. Open the exported PDF in a normal PDF viewer.

**Expected:**
- The PDF opens and contains **every exported node's pages**.
- With TOC on, the first page(s) are a printed **table of contents** whose entries are
  **clickable** and jump to the right page; the viewer's sidebar shows matching **bookmarks**;
  a tag index appears when enabled.
- A green **"✓ PDF exportiert (N …)"** notice appears on success.
- *Not obvious (known gap):* an export over **100 pages** stays a **single PDF** — the
  auto-split-with-cross-references path exists in code but is **not yet wired into the UI**
  (consistent with `CLAUDE.md` / `BETA_TESTING.md` §4).

---

## MT-15: Save and reload a `.belegtool` file (round-trip)

**Preconditions:** A document with folders, several nodes, mixed statuses, some collapsed
folders, and at least one compressed node.

**Steps:**
1. Press **💾 Speichern** (or **Strg+S**). On a document that has **no path yet**, this
   prompts for a location (Save-as); afterwards it saves **in place** without asking.
2. Click the small **caret (▾)** on the right of the Save button → a dropdown with
   **„Speichern unter…"** appears; choose it and pick a new location.
3. Close the window.
4. **📂 Öffnen** the `.belegtool` file you just saved.

**Expected:**
- The tree comes back **exactly as before**: same folder structure, names, order, **node
  ids**, statuses (dots), **collapsed** folders, tags, and compression state.
- Previews render again (a striped placeholder may flash first).
- *Not obvious:* the Save control is a **split-button** — the main part saves in place
  (and clears the **"•"** dirty marker, showing a green **"✓ Gespeichert"** notice), the
  **caret** opens the dropdown with **„Speichern unter…"** (always prompts for a new path).
  The dropdown closes on **Esc**, on a click outside, or after you pick the entry.

---

## MT-17: Committed compression drops the source (irreversible)

Verifies the v3.6.0 save policy: once a node is compressed ("Lesbarkeit geprüft"), the saved
file keeps only the compressed result — the uncompressed original is dropped, and a reloaded
committed node can no longer be re-compressed or reset.

**Preconditions:** the app running (`python host.py`); a multi-page colour PDF imported as a node.

**Steps:**
1. Select the imported node. In the compression controls, pick a method (e.g.
   **JPG (Farbe)** or **JPG (Graustufen)**) and click **✓ Lesbarkeit geprüft**.
2. **💾 Speichern** the document as a `.belegtool` file.
3. Close the window, then **📂 Öffnen** that saved `.belegtool` again.
4. Select the same node and open the compression dropdown.

**Expected:**
- After saving, the file is noticeably smaller than the original import (only the compressed
  result is stored, not the source). On reload the node still previews correctly (rendered
  from the compressed bytes).
- *Not obvious / important:* the compression dropdown for that node now shows
  **"bereits komprimiert (keine Quelle)"** and is **disabled** — you cannot re-compress or
  reset it, because the original was intentionally discarded on save. This is by design and
  **irreversible**.
- A node you did **not** compress before saving keeps its source and remains fully
  compressible after reload.

---

## MT-19: Save dialog — store compression alternatives or not

Verifies the save-time choice that appears only when there are **computed-but-unapplied**
compression alternatives to embed.

**Preconditions:** the app running; a multi-page colour PDF imported as a node.

**Steps:**
1. Import the node but **do not** click "Lesbarkeit geprüft". Select it and open the
   **compression dropdown** so the methods compute (you'll see method sizes appear).
2. Press **💾 Speichern** (Ctrl+S) and choose a path.
3. Observe the dialog, then click **Wie geplant speichern**. Note the file size.
4. Repeat the save to a second file, this time clicking **Original speichern**. Compare sizes.

**Expected:**
- A dialog **„Komprimierungs-Alternativen speichern?"** appears with three buttons:
  **Wie geplant speichern · Original speichern · Abbrechen**.
- *Not obvious:* the dialog appears **only** when alternatives exist. If you never opened the
  compression dropdown (nothing computed), or every node is committed, Save proceeds **without**
  the dialog.
- **Wie geplant** → larger file; reopening shows the compression options instantly (no
  "Kompression läuft …"). **Original speichern** → smaller file; reopening recomputes the
  options on demand. **Abbrechen** → nothing is saved; the title bar still shows unsaved
  changes (•).
