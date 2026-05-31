# 04 — Export, persistence, Test mode

Covers exporting to PDF, saving/reloading the `.belegtool` format, and the
built-in Test mode.

---

## MT-14: Export selection to a PDF with table of contents

**Preconditions:** A storage with several nodes/folders. Select one or more nodes.

**Steps:**
1. Right-click → **Exportieren…** (or **Datei → Exportieren…**).
2. Choose a target `.pdf` path and confirm.
3. Open the exported PDF in a normal PDF viewer.

**Expected:**
- The PDF opens and contains **every selected node's pages**.
- The first page(s) are a printed **table of contents**; the TOC entries are
  **clickable** and jump to the right page. The viewer's sidebar shows matching
  **bookmarks**.
- *Not obvious:* a very large export (>100 pages) is **auto-split** into multiple
  PDFs with cross-references between them.

---

## MT-15: Save and reload a `.belegtool` file (round-trip)

**Preconditions:** A storage with folders, several nodes, mixed statuses, and at
least one compressed node.

**Steps:**
1. **Datei → Speichern als…** (`Strg+Umsch+S`), choose a path, save.
2. **Datei → Schließen** (close the storage).
3. **[Import]** / **Datei → Importieren…** the `.belegtool` file you just saved.

**Expected:**
- The tree comes back **exactly as before**: same folder structure, names, order,
  statuses (colours), and compression state.
- Previews render again (a placeholder may flash first).
- *Not obvious:* **Speichern** (`Strg+S`) saves back to the already-known file
  without asking for a path; **Speichern als…** always asks.

---

## MT-16: Test mode — input vs live vs expected

This is a developer/QA view that runs the golden-master operations and shows the
results side by side. It needs the test fixtures present.

**Preconditions:** `tests/data/input/` exists (if not, a developer runs
`python tests/make_fixtures.py`).

**Steps:**
1. Menu **Ansicht → Testmodus** (toggle it on).
2. Wait a few seconds (a busy cursor shows while the operations run).
3. Scroll through the view.
4. Toggle **Ansicht → Testmodus** off again.

**Expected:**
- The normal editor is replaced by a comparison view with three columns per item:
  **Input**, **Live** (the operation run right now), **Erwartet (Referenz)**.
- Each row shows a badge: **✓ stimmt mit Referenz überein** (live matches the
  golden master), **✗ weicht ab**, or **⚠ keine Referenz**.
- Sections appear for **Kompression**, **Splitten**, **Zusammenführen**.
- Turning the toggle off restores the normal editor.
- *Not obvious:* if the fixtures are missing you get a message telling you to run
  `python tests/make_fixtures.py` instead of an empty view.
