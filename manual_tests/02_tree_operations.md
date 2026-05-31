# 02 — Tree operations

Covers editing the document tree: split, merge, folders, rename, delete, and
drag-and-drop. Most actions are on the **right-click context menu** and the
**Bearbeiten** menu.

---

## MT-06: Split a multi-page document into one node per page

**Preconditions:** A multi-page PDF node in the tree (e.g. imported `split_sample.pdf`, 3 pages). Select it.

**Steps:**
1. Right-click the node → **Splitten** (or **Bearbeiten → Splitten**).

**Expected:**
- The node is replaced/expanded into **one node per page** (e.g. 3 nodes).
- Each new node's preview shows exactly **one page**.
- *Not obvious:* the split pages are marked "do not compress" (they came from an
  already-processed parent), so the compression slider may be hidden for them.

---

## MT-07: Merge two sibling documents

**Preconditions:** Two leaf nodes at the **same level** (same parent). Select both
(Ctrl-click the second).

**Steps:**
1. Right-click → **Zusammenführen** (or **Bearbeiten → Zusammenführen**).

**Expected:**
- The two nodes become **one** node whose preview contains **all pages of both**,
  in order.
- *Not obvious:* if the two were compressed at **different DPI**, the merged node
  drops its compressed version (it falls back to the originals) and is no longer
  marked "compressed" — this avoids mixing resolutions.

---

## MT-08: Create folders, rename, delete

**Preconditions:** At least one node selected.

**Steps:**
1. Right-click a folder → **Ordner innerhalb** → a new folder appears *inside* it.
2. Right-click any node → **Ordner unterhalb** → a new folder appears *below* it
   (same level, just after).
3. Select a node, press **F2** (or right-click → **Umbenennen**), type a new name,
   confirm.
4. Select a node, press **Entf** (or right-click → **Löschen**), confirm the prompt.

**Expected:**
- Folders appear at the stated positions; renamed node shows the new name.
- After delete, the node is gone and the **selection moves** to a neighbour
  (left sibling, else the parent) so you can keep working.

---

## MT-09: Drag-and-drop move and copy

**Preconditions:** A tree with at least two folders and some leaf nodes.

**Steps:**
1. **Drag** a node onto a folder and drop it → the node **moves** into that folder.
2. Hold **Ctrl** while dragging a node onto a folder → a **copy** is placed there
   (the original stays).
3. Select a node and press **Ctrl + ↑ / ↓** to move it among its siblings.

**Expected:**
- Moved nodes appear under the drop target in the expected order; copies are
  independent (editing one does not change the other).
- The tree stays consistent — no duplicate or "ghost" entries, and selecting any
  moved/copied node still shows its correct preview.
