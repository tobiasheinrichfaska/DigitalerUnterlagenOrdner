# 05 — React desktop UI (pywebview)

Covers the **new** React front end (`python host.py`), separate from the Tk app
tested in 01–04. Launch with `cd webui && npm run build` then `python host.py`.

---

## MT-30: Launch, open, save

**Preconditions:** A built `webui/dist` (run `npm run build` once).

**Steps:**
1. Run `python host.py`. Wait for the window.
2. Click **📂 Öffnen**, pick a `.belegtool` file.
3. Make any change (e.g. right-click a node → **Umbenennen**).
4. Click **💾 Speichern** (or press **Strg+S**).

**Expected:**
- The window appears quickly; the first **Öffnen** is near-instant (libraries are
  pre-warmed in the background — *not obvious:* the very first action right after
  launch may pause ~1 s if you beat the warm-up).
- After an edit, **💾 Speichern** shows a **"•"** marker; saving clears it and shows
  a green **"✓ Gespeichert"** notice.

---

## MT-31: Import — button, drag-drop, and drop position

**Preconditions:** App open. Have a few files ready: a PDF, an image, and (optional)
a Word/Excel/`.md` file.

**Steps:**
1. Click **📥 Importieren**, select several files at once.
2. Drag a file from Explorer **onto the window** (not on a row) → drop.
3. Drag a file **onto a folder row** → drop. Watch the indicator.
4. Drag a file **between two rows**, and at the very bottom **slide left/right**.

**Expected:**
- Imported files appear as nodes; multiple keep their order; each import is **one
  undo step** (↶ removes it).
- *Not obvious:* the first Office/`.md` import may pause a couple seconds the first
  time (the Office/COM libraries load on first use only).
- Drop **shows the same indicators as moving**: a folder highlights for "into", a
  line for before/after, and at the bottom a **ghost "📥 importieren"** with a
  destination pill that follows the cursor as you slide levels.
- Drop **on the window background** imports into the selected folder (or top level);
  the dashed border + badge is just a hint.

---

## MT-32: Tree editing — move, slide-to-level, merge, group, split

**Preconditions:** A document with folders and several leaves at different depths.

**Steps:**
1. **Drag** a node onto a folder (into), between rows (before/after), and at the
   bottom **slide left** to drop it at a shallower level (watch the ghost).
2. **Ctrl-click** two sibling leaves → right-click → **Zusammenführen → 1 PDF**.
3. **Ctrl-click** two nodes in *different* folders → right-click → **In neuen Ordner**.
4. Right-click a multi-page leaf → **Splitten**.

**Expected:**
- Move re-renders from the returned tree (no flicker/duplication); the slide ghost
  names the destination ("in <folder>" / "oberste Ebene").
- **Zusammenführen** only appears for 2+ **sibling** leaves and makes one PDF node.
- **In neuen Ordner** works across depths (folder lands in the common parent, else
  the root) and keeps the items separate.
- **Splitten** replaces the leaf with one node per page.

---

## MT-33: Compression working-preview

**Preconditions:** Select a leaf with a detailed page.

**Steps:**
1. Open the **method dropdown** in the preview panel.
2. Pick a method; drag the **DPI** slider; pick **unkomprimierte Fassung**.
3. Click **❓ Lesbarkeit geprüft**. Re-select the node.

**Expected:**
- *Not obvious:* selecting a leaf runs **no** compression — the undo arrow stays
  disabled. Opening the dropdown shows **"Kompression läuft …"** then the methods.
- Browsing methods/DPI only previews; the document changes (one undo step) **only**
  on **Lesbarkeit geprüft** (button then reads **✓ übernommen**). Re-selecting shows
  the saved method.

---

## MT-34: Multi-window

**Steps:**
1. Click **🗗 Neues Fenster** (or **Strg+N**).
2. In the new window, **📂 Öffnen** a different file and edit it.
3. Use **📥 Importieren** / **💾 Speichern** in each window.

**Expected:**
- A second independent window opens; the two documents are unrelated.
- *Not obvious:* file dialogs and the save target belong to the window you clicked
  in (not always the first window).

---

## MT-35: Unsaved-changes guards

**Steps:**
1. Make an edit (see the **"•"** on Speichern).
2. Click **📂 Öffnen** → cancel the confirm.
3. Try to **close the window** → cancel the confirm. Then save, and close again.

**Expected:**
- Opening another file with unsaved changes asks first; cancelling keeps the doc.
- Closing the window with unsaved changes asks first; after saving, it closes
  without asking. Each window warns about **its own** changes.

---

## MT-36: Export to TOC PDF

**Steps:**
1. With a document open, click **⬇ Export PDF** → choose a path.
2. Optionally Ctrl-select some nodes first → the button reads **(Auswahl)**.
3. Open the exported PDF.

**Expected:**
- A single PDF with a **table-of-contents page**, clickable links and sidebar
  **bookmarks**; selection export includes only the chosen subtrees.
- A green **"✓ PDF exportiert (N …)"** notice on success.

---

## MT-37: Keyboard shortcuts & zoom

**Steps:**
1. **Strg+Z / Strg+Y** (undo/redo), **Strg+S** (save), **Strg+O** (open),
   **Strg+E** (export), **Strg+N** (new window), **Entf** (delete selected node).
2. In the preview, **Strg + Mausrad** to zoom; the zoom bar −/＋/100%.

**Expected:**
- Shortcuts work, but are **ignored while typing** in a text field/dialog.
- **Entf** deletes the selected node (undoable). Ctrl+wheel zooms the preview only.
