# 04 — Export & persistence

Covers exporting to PDF and saving/reloading the `.belegtool` format.

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
