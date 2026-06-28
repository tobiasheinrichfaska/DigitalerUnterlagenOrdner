# 02 — Tree operations

Covers editing the document tree: split, merge, folders, rename, delete, and
drag-and-drop, in the **React/pywebview UI**. Most actions are on the **right-click
context menu**; the toolbar carries **＋ Ordner** and undo/redo (↶ / ↷). There is no
menu bar. (Keyboard restructuring — Insert-grab move + folder collapse — has its own
deep test in `05_react_ui.md` MT-40.)

---

## MT-06: Split a multi-page document

**Preconditions:** A multi-page PDF node in the tree (e.g. imported `split_sample.pdf`,
3 pages). Right-click it.

**Steps:**
1. Right-click the node → hover **Splitten ▸** to open the flyout, then choose one:
   **pro Seite**, **N Seiten pro Knoten…**, **pro Seite → neuer Ordner**, or
   **N Seiten → neuer Ordner…** (the "N Seiten" entries prompt for the page count).

**Expected:**
- **pro Seite** replaces the node with **one node per page** (e.g. 3 nodes); each new
  node's preview shows exactly **one page**. The **→ neuer Ordner** variants put the
  parts inside a new folder.
- *Not obvious:* **Splitten** is only offered on a **leaf with more than one page**
  (`pdf_length > 1`); it is hidden on folders and single-page leaves.
- *Not obvious:* split parts carry the **uncompressed source** pages, so they remain
  compressible (this changed in v3.9.x — parts are no longer flagged "do not compress").

---

## MT-07: Merge two sibling documents

**Preconditions:** Two leaf nodes at the **same level** (same parent). Select both
(Ctrl-click the second).

**Steps:**
1. Right-click **one of the selected nodes** → **Zusammenführen → 1 PDF (2)**.

**Expected:**
- The two nodes become **one** node whose preview contains **all pages of both**, in order.
- *Not obvious:* **Zusammenführen** only appears for **2+ selected sibling leaves**, and
  only when you right-click a node **inside the selection** — right-clicking a node
  outside the selection hides it (same membership rule as Export / Status / Löschen).
- *Not obvious:* if the inputs were compressed at **different DPI**, the merged node drops
  its compressed version (falls back to the originals). Status: all inputs same status →
  kept; any difference → no status.

---

## MT-08: Create folders, rename, delete

**Preconditions:** A document with at least one node.

**Steps:**
1. Click **＋ Ordner** in the toolbar → a name dialog appears (default **Neuer Ordner**);
   confirm. The new folder is placed **relative to the current selection**:
   - **nothing selected** → at the top level (root);
   - a **folder** selected → **inside** that folder;
   - a **leaf** (document) selected → as a **sibling right after** that node.
   Right-click a **folder** → **Ordner anlegen** also creates a new folder **inside** it.
2. Select a node, press **F2** (inline) — or right-click → **Umbenennen** — type a new
   name, confirm.
3. Select a node, press **Entf** (or right-click → **Löschen**). For a multi-selection the
   item reads **Löschen (N)** and deletes the whole selection in one undo step.

**Expected:**
- *Not obvious:* the toolbar **＋ Ordner** is **selection-aware** — it lands the folder
  inside a selected folder, or directly after a selected document, not always at the end.
  Cancelling the name dialog (Esc / empty name) creates nothing.
- Folders appear at the stated positions; the renamed node shows the new name.
- After delete, the node is gone and the **selection moves** to a neighbour (left sibling,
  else the parent) so you can keep working; the deleted nodes' cached renders are freed.
- *Not obvious:* a multi-selection that mixes a folder with items **inside** it is resolved
  in the UI first (include all / exclude folder / abort) — the data layer rejects a mixed set.

---

## MT-09: Drag-and-drop move + slide-to-level

**Preconditions:** A tree with at least two folders and some leaf nodes.

**Steps:**
1. **Drag** a node onto a folder → drop → it **moves into** that folder.
2. **Drag** a node **between two rows** → it lands before/after at that level.
3. At the **bottom** of a level, **slide left/right** before dropping and watch the ghost.

**Expected:**
- Moved nodes appear under the drop target in the expected order; the tree re-renders from
  the returned model — **no duplicate or "ghost" entries**, and selecting any moved node
  still shows its correct preview.
- The **slide ghost** names the destination ("in &lt;folder&gt;" / "oberste Ebene") as you
  slide levels at the bottom.
- *Not obvious:* internal drag is **move only** — there is no Ctrl-to-copy within a window
  (cross-window copy is a planned feature, not yet built). To restructure with the keyboard,
  use **Insert** to grab a node and the arrows to move it optically, then **Insert** to drop
  (one undo) or **Esc** to cancel — see MT-40.
