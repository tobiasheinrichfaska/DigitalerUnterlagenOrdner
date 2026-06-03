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

## MT-17: Committed compression drops the source (irreversible)

Verifies the v3.6.0 save policy: once a node is compressed ("Lesbarkeit geprüft"),
the saved file keeps only the compressed result — the uncompressed original is
dropped, and a reloaded committed node can no longer be re-compressed or reset.

**Preconditions:** the app running (`python host.py`); a multi-page color PDF imported as a node.

**Steps:**
1. Select the imported node. In the compression controls, pick a method (e.g.
   **JPEG (Farbe)** or **JPEG (Graustufen)**) and click **❓ Lesbarkeit geprüft**.
2. **Save** the document as a `.belegtool` file.
3. Close the window, then **open** that saved `.belegtool` again.
4. Select the same node and open the compression dropdown.

**Expected:**
- After saving, the file is noticeably smaller than the original import (only the
  compressed result is stored, not the source).
- On reload the node still previews correctly (rendered from the compressed bytes).
- *Not obvious / important:* the compression dropdown for that node now shows
  **"bereits komprimiert (keine Quelle)"** and is **disabled** — you cannot
  re-compress or reset it, because the original was intentionally discarded on
  save. This is by design and **irreversible**: the only copy is the compressed one.
- A node you did **not** compress before saving keeps its source and remains fully
  compressible after reload.


---

## MT-18: Testmodus (React UI) — input vs live vs expected

Re-introduced in the React UI (v3.6.0+). A developer/QA view that runs the
golden-master operations and shows the results side by side. Needs the fixtures.

**Preconditions:** the app is running (`python host.py`); `tests/data/input/`
exists (if not, a developer runs `python tests/make_fixtures.py`).

**Steps:**
1. In the toolbar, click **🧪 Testmodus**.
2. Wait a moment ("Operationen laufen …" shows while the operations run).
3. Scroll through the overlay.
4. Click **Schließen**.

**Expected:**
- A full-window overlay appears with sections **Kompression**, **Splitten**,
  **Zusammenführen**.
- Each item shows three columns — **Eingabe**, **Live** (the operation run right
  now), **Referenz** — as page thumbnails (up to ~12 pages per item, so multi-page
  results are visible in full).
- **Splitten:** each row is one page of the source — **Eingabe** shows the
  *original* page *i*, **Live** the split piece *i*, **Referenz** the golden piece.
  You can verify by eye that piece *i* really is page *i* of the source.
- **Zusammenführen:** the two **Quelle** rows show `merge1_a`/`merge1_b` and their
  pages; the **Ergebnis** row shows the full merged document (a's page, then b's
  pages) in **Live** and **Referenz**, so you can confirm the concatenation order.
- Each item carries a badge: **✓ stimmt mit Referenz überein** (live matches the
  golden master), **✗ weicht ab**, or **⚠ keine Referenz** / **⚠ kein Ergebnis**.
- *Not obvious:* with unchanged code every item that has a reference should be
  green (✓). A red ✗ means a live operation drifted from its golden master.
- *Not obvious:* if the fixtures are missing, the overlay shows a clear message
  telling you to run `python tests/make_fixtures.py` instead of empty columns.
- **Schließen** restores the normal editor; the open document is untouched
  (Testmodus is read-only).
