# 07 — Keyboard structuring, multi-delete & language

Covers keyboard tree-structuring, folder collapse, multi-select **delete** with the
parent/child resolver, inline rename, the **language switcher**, and the layout
tweaks (resizable pane, chevrons, one-line names, page indicator).

---

## MT-50: Keyboard navigation, collapse, and the Insert "carry" move

**Preconditions:** A document with folders and several nodes.

**Steps:**
1. Click a node, then use **↑/↓** to move the selection.
2. On a folder, press **→** to expand, **←** to collapse (or click the chevron).
3. Select a node, press **Insert** (the row gets a dashed outline). Press **↑/↓** to
   reorder, **→** to nest into the folder above, **←** to move out a level.
4. Press **Insert** again to drop. Repeat but press **Esc** instead.

**Expected:**
- ↑/↓ move through the **visible** rows (skipping collapsed folders).
- While carried, the node moves **only visually**; **Insert** commits it (a single
  undoable move), **Esc** reverts with no change. *Not obvious:* Ctrl is multi-select,
  so the move key is **Insert**, not Ctrl+Arrow.
- Folder collapse is **remembered in the file** (save, reopen → still collapsed).

---

## MT-51: Multi-select delete — all selected, focus moves on

**Steps:**
1. **Ctrl-click** several independent nodes (leaves in different folders).
2. Press **Entf** (Delete) — or right-click → **Löschen (N)**.
3. After deletion, look at the selection.

**Expected:**
- **All** selected nodes are deleted in **one undo step** (earlier only one was
  removed). The context-menu entry shows the count, e.g. **Löschen (3)**.
- Focus **moves to the next remaining node** automatically — a second delete needs no
  extra click.

---

## MT-52: Delete with a folder in the selection (resolver)

The data layer **rejects** a mixed folder+child selection; the UI resolves it first.

**Steps:**
1. Select **only a folder** that has contents → **Entf**.
2. Select a folder **and one of its children** (Ctrl-click) → **Entf**.
3. Repeat (2) but answer differently.

**Expected:**
- (1) Folder + none of its children selected → a **warning**: its unselected contents
  will be deleted too — **OK** deletes the folder, **Abbrechen** keeps everything.
- (2) Folder + some children selected → you are asked per problematic folder:
  **OK = alle Elemente löschen** (delete the whole folder), next **OK = nur die
  ausgewählten Elemente, Ordner behalten** (delete only the selected children), or
  **Abbrechen** = nothing. *Not obvious:* if a folder's **all** children are selected,
  there is **no prompt** — the folder simply covers them.

---

## MT-53: Inline rename (Explorer-style)

**Steps:**
1. Click a node to select it. Click its name **again** (not a double-click).
2. Type a new name; press **Enter** (or **Esc** to cancel).
3. Also try right-click → **Umbenennen**.

**Expected:**
- A second click on the already-selected name turns it into an **editable field**.
  Enter saves, Esc cancels, clicking away saves. Dragging is disabled while editing.

---

## MT-54: Language switcher (Deutsch / English)

**Steps:**
1. In the toolbar, use the **🌐** dropdown → **English**.
2. Open a context menu, the compression dropdown, and the status bar.
3. Switch back to **Deutsch**. Restart the app.

**Expected:**
- All UI text switches language **immediately** (toolbar, menus, status bar, prompts,
  status labels). The choice **persists** across restarts. *Not obvious:* the document
  content and node names are **not** translated — only the app's own labels.

---

## MT-55: Layout — resizable tree, chevrons, one-line names, page indicator

**Steps:**
1. Drag the **splitter** between the tree and the preview; restart the app.
2. Look at folder **chevrons** and long node names.
3. Select a multi-page node and scroll; watch the zoom bar.

**Expected:**
- The tree pane resizes by dragging and the width is **remembered** next launch.
- Chevrons are large and clickable; long names stay on **one line** (the tree scrolls
  horizontally rather than wrapping).
- The zoom bar shows **"Seite n / m"** for the page you're viewing (falls back to the
  total page count).
