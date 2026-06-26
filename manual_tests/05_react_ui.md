# 05 — React desktop UI (pywebview)

Covers the React/pywebview front end (`python host.py`) — the only UI since
v3.6.0. Launch with `cd webui && npm run build` then `python host.py`.

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
  It is offered only when you right-click **one of the selected nodes** — right-
  clicking a node outside the selection hides it (like Export/Status/Löschen).
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

---

## MT-39: Windowed preview — big PDF scrolls without the long load

Validates the virtualized preview (v3.6.0+). A large PDF should open its preview
**immediately** (first pages only) and render more as you scroll, instead of
freezing while every page renders.

**Preconditions:** the app is running (`python host.py`); import a **large**
PDF (ideally 100+ pages; a colour scan is a good stress test).

**Steps:**
1. Select the large PDF node in the tree.
2. Watch the preview pane appear.
3. Scroll down slowly through the document.
4. Scroll quickly (flick) far down, then back up.
5. Select a different node, then select the large PDF again.

**Expected:**
- The preview appears **right away**: the first page(s) show within ~1–2 s, not
  after a long freeze. Pages not yet rendered show a light **striped placeholder**
  box of the correct size (the layout does not jump when the real page arrives).
- *Not obvious:* scrolling at a normal/reading pace stays smooth — pages fill in
  just ahead of the viewport (a few pages are prefetched in each direction).
- A fast flick may briefly show placeholders that fill in within a moment; the
  scrollbar position stays stable (no jumping).
- *Not obvious:* returning to the large PDF restores **the same scroll position**
  you left it at, and already-seen pages reappear instantly (cached).
- *Not obvious:* the compression working-preview (method dropdown / DPI) is now
  **also windowed** — browsing methods on a big document no longer freezes; only the
  visible pages render, and switching back to a method (or to the original) you
  already viewed is instant. (The first browse at a new DPI still pauses while the
  compressed variant is computed — that's compression, not rendering.)


---

## MT-40: Keyboard tree-structuring + folder collapse

Covers the keyboard restructuring + folder collapse (persisted) added for large
trees.

**Preconditions:** dev app running (`python host.py`); a document with a few
folders and nested nodes.

**A — Folder collapse (persisted):**
1. Click the **▾ chevron** on a folder → it collapses to **▸** and its children hide.
2. Right-click a folder → **Zuklappen/Aufklappen**; right-click anywhere → **Alle
   zuklappen** / **Alle aufklappen**.
3. **Speichern**, close, **reopen** the file.

**Expected (A):**
- Collapsing hides children and cuts scrolling; the chevron reflects the state.
- *Not obvious:* collapsing marks the document **dirty (•)** — it's a saved model
  change, so it **survives reload**: the folders you left collapsed come back
  collapsed. (Undo/Ctrl+Z reverses a collapse, like a status change.)

**B — Keyboard navigation + collapse:**
4. Click a node, then use **↑/↓** to move the selection (collapsed folders' children
   are skipped). On a folder, **→** expands / steps in, **←** collapses / steps out.

**Expected (B):** selection follows the visible rows; ←/→ fold/unfold folders.

**C — Carry-move (Insert grab → arrows → Insert drop):**
5. Select a node, press **Insert** — it gets a **dashed outline** (grabbed).
6. Press **↑/↓** (reorder among siblings), **→** (nest into the folder directly
   above), **←** (move out one level). The node moves **visually only**.
7. Press **Insert** again to **drop**.
8. Repeat, but press **Esc** instead of the final Insert.

**Expected (C):**
- While grabbed, the tree shows fully expanded and the node slides as you arrow,
  but **nothing is committed yet**. **Insert** drops it — a single **undoable** move
  (Ctrl+Z reverts it in one step). **Esc** cancels and the node snaps back with **no
  change** to the document.

---

## MT-41: Tags — on/off, editing, and the filtered view

Covers the tag toggle (default off, auto-on for tagged files), tag editing, and the
view-only tag/name filter with its structural-edit lock.

**Preconditions:** dev app running; a document with several leaves in a couple of
folders.

**A — Toggle + auto-on:**
1. Note the toolbar **🏷️ Tags** button is **off** on a fresh/empty document — no tag
   chips and no tag editor are shown.
2. Click **🏷️ Tags** → it highlights (on); the tag editor appears above the preview
   and a **search bar** appears above the tree.
3. Add a tag (e.g. `Spende`) to one leaf, **Speichern**, close, **reopen** the file.

**Expected (A):**
- *Not obvious:* a file that **already has tags** opens with tagging **on
  automatically** — you don't have to flip the switch to see existing tags. Turning
  tagging **off** hides all chips and every tag function, but the tags **stay stored**
  (reopen / toggle on shows them again).

**B — Filter view + inheritance:**
4. Tag a **folder** with `Steuer`; tag one leaf inside another folder with `Spende`.
5. In the search bar type `steuer`.
6. Clear it, then type `spende`.
7. Clear it again, then type a **node name** (e.g. part of a document's filename).

**Expected (B):**
- `steuer` → the tagged folder shows with its **whole subtree** (a folder tag applies
  downward to everything inside).
- `spende` → only the **path** to the matching leaf shows: its parent folder appears
  as a container but its **non-matching siblings are hidden** (not the whole folder).
- Search matches **tags only** (case-insensitive) — typing a **node/file name** finds
  **nothing** (names are deliberately *not* searched).

**B2 — Group by tag:**
8. Tick **Nach Tag gruppieren** (no search).

**Expected (B2):**
- The tree is replaced by one folder **per tag** (sorted). Inside each tag's folder is
  the **path** to every node that carries it: a tagged **folder** is kept **whole**
  (all its children come with it); a tagged **leaf** keeps its **parent folders** as
  context. A node with several tags appears under **each**, and an item tagged
  differently from its tagged parent shows **both** inside the parent and under its own
  tag (nodes may appear more than once — that's intended). Fully-untagged paths fall
  into a final **„Ohne Tags"** group.
- *Not obvious:* the per-tag group **headers** are a view only (synthetic) — clicking/
  right-clicking a header does nothing; but the **real** folders/leaves inside are still
  selectable and previewable. Structure stays locked (same as filtering). Untick the box
  (or **Ansicht zurücksetzen**) to return.

**B3 — Open the view in a new window:**
9. With a **tag search** active, click **In neuem Fenster öffnen** in the view bar.

**Expected (B3):**
- A **new window** opens containing a **real, editable copy** of just the **displayed**
  nodes — in the **normal tree order/structure** (any grouping is *not* carried over;
  hidden nodes are absent). The original window is unchanged.
- The new document is **named after the searched tag**, prefixed onto the old name
  (e.g. `Spende - <old name>`); that title is also the suggested filename on **Speichern**.
- *Not obvious:* the button appears **only when a tag search is active** — turning
  **Nach Tag gruppieren** on/off does **not** show or hide it (grouping alone reshapes
  the whole tree, so there's no subset to extract). Editing the copy does **not** touch
  the source document.

**C — Structural edit-lock while filtered:**
7. With a search active, note the **⚠ "Ansicht gefiltert — Umsortieren aus"** hint and
   try: drag a row, press **Insert**, press **Delete**, click **📥 Importieren** / **＋
   Ordner**, drag a file from Explorer onto the tree, right-click a node.

**Expected (C):**
- While filtered, the view is **read-only for structure**: rows **don't drag**, Insert/
  Delete do nothing, **Importieren** and **＋ Ordner** are **disabled** (greyed), an OS
  file-drop is ignored, and the right-click menu hides **Löschen / Zusammenführen / In
  neuen Ordner / Splitten / Ordner anlegen**.
- *Why (call out):* a filtered folder can hide non-matching children, so deleting or
  moving it would silently affect rows you can't see — so structure is locked until you
  **Ansicht zurücksetzen** (clear the search). **Content edits stay available**: rename,
  status, and compression still work on the rows you can see.

**D — Multi-select tagging (#7):**
10. With tagging **on**, give two leaves a shared tag (e.g. `Steuer` on both) and one of
    them a second tag (e.g. `2024` on leaf A only).
11. **Ctrl+click** (or Shift-range) to select **both** leaves at once.
12. In the tag editor above the preview, **add** a tag (e.g. `Wichtig`), then **remove**
    the shared `Steuer` chip.

**Expected (D):**
- The editor shows a small **„2 markiert"** badge and the **union** of the two leaves'
  tags. *Not obvious:* a tag on **only one** of them (`2024`) is drawn as a **hollow /
  dashed** „partial" chip, while a tag on **both** (`Steuer`) is a solid chip.
- Adding `Wichtig` puts it on **both** leaves; removing `Steuer` takes it off **both** —
  each is **one undo step** (a single ↶ reverts the whole bulk change).
- *Not obvious:* re-adding the partial `2024` from the input **completes** it onto the
  other leaf too. A node that already has the tag is left unchanged (no duplicates), and
  **Backspace** does **not** bulk-remove in multi-select (only single-select).
