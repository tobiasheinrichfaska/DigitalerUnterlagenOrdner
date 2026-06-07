# 08 — Status dots, F2 rename, Help (v3.9.0)

Covers the new status-dot model, the persisted compression "undecided" dot, F2 rename,
and the Help modal. Run the app (`python host.py`, or the prebuilt exe).

---

## MT-50: New nodes have no status
**Preconditions:** App open, a few documents imported.
**Steps:**
1. Look at the freshly imported documents in the tree.
**Expected:** No status dot at the **end** of those rows — new nodes start with **no status**
(not "zu erfassen" as before).

## MT-51: Set a status on a single document
**Preconditions:** A document selected.
**Steps:**
1. Right-click it → **Status** → **Zu erfassen**.
2. Right-click again → **Erfasst**, then → **Vorjahr**, then → **Kein Status**.
**Expected:** A trailing dot appears and changes colour: **yellow** (Zu erfassen) → **green**
(Erfasst) → **red** (Vorjahr). **Kein Status** removes the dot entirely.

## MT-52: Folder status cascade
**Preconditions:** A folder with several documents (incl. a sub-folder with documents).
**Steps:**
1. Right-click the **folder** → **Status (gesamter Inhalt)** → **Erfasst**.
**Expected:** **Every** document inside (children *and* grandchildren) turns green. One Undo
reverts the whole cascade in a single step. The folder itself shows no own status.

## MT-53: Folder aggregate dots + black dot
**Preconditions:** A folder containing one **Erfasst** (green) doc, one **Vorjahr** (red) doc,
and one **no-status** doc.
**Steps:**
1. Collapse the folder and look at its row.
**Expected:** The folder shows a **red** and a **green** dot (one per contained status, ordered
red→yellow→green) **plus a black dot** — the black dot means "some contents have a status and
some don't". If you then set the no-status doc to a status, the **black dot disappears**.

## MT-54: Merge / Split status rules
**Steps:**
1. Select two **Erfasst** documents → right-click → **Zusammenführen**.
2. Select one **Erfasst** and one **Vorjahr** document → **Zusammenführen**.
3. Select a multi-page document with a status → **Splitten → pro Seite**.
**Expected:** (1) merged node stays **green**. (2) merged node has **no status** (mixed inputs).
(3) every split part keeps the **original's** status.

## MT-55: Compression "undecided" red dot (front)
**Preconditions:** A freshly imported, uncompressed document (≤5 pages).
**Steps:**
1. Look at the **front** of the row before selecting it (large/unviewed docs).
2. Select it; open the compression method dropdown; pick a method; click **❓ Lesbarkeit geprüft**.
**Expected:** A **red dot at the front** marks "compression not yet decided". After applying
("Lesbarkeit geprüft"), the front red dot **disappears**. *Not obvious:* if the document can't be
made smaller, the dot also disappears (auto-decided) — and **stays gone after save + reopen**
(it is not re-evaluated).

## MT-56: F2 renames
**Steps:**
1. Select a node, press **F2**.
**Expected:** The name turns into an inline edit field (same as clicking an already-selected row).
Enter confirms, Esc cancels. Works in a tag/search view too (rename is a content edit).

## MT-57: Help modal + language flags + report links
**Steps:**
1. Click **❓ Hilfe** in the toolbar.
2. Click the **🇬🇧** flag, then the **🇩🇪** flag.
3. Click **▸ GitHub** and **✉ E-Mail** in the footer.
**Expected:** A modal opens with how-to sections in the current UI language (English if that
language isn't translated yet). The flags switch the text to authoritative **English / German**.
**▸ GitHub** opens a pre-filled new-issue page in the browser; **✉ E-Mail** opens a pre-filled
mail draft. Esc or ✕ closes the modal.
