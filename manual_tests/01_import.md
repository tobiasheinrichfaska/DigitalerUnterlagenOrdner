# 01 — Import

Covers bringing files into the document tree and the import-safety guard, in the
**React/pywebview UI** (`python host.py` — the only UI since v3.6.0). All actions
are on the **toolbar** and **drag-and-drop**; there is no menu bar. (Drag-drop import
positioning is exercised in detail in `05_react_ui.md` MT-31.)

---

## MT-01: Import a single PDF

**Preconditions:** App open (a fresh "Dokument N" or a document already loaded).

**Steps:**
1. Click **📥 Importieren** in the toolbar.
2. In the file dialog, choose a multi-page PDF (e.g. `tests/data/input/sample.pdf`).
   The dialog allows multiple selection.
3. Confirm the dialog.
   - *Alternative:* drag the PDF from Explorer **onto the window** (background → into
     the selected folder/top level; onto a folder row → into it; between rows → at
     that position). The drop shows the same indicators as an internal move.

**Expected:**
- A new node with the file name appears in the **tree** (left).
- Selecting it shows the page images in the **preview** (right). *Not obvious:* a
  light **striped placeholder** of the correct page size may appear for a moment
  before the real page renders — this is the windowed preview filling in lazily.
- The window now has unsaved changes: **💾 Speichern** shows a **"•"** marker; each
  import is **one undo step** (↶ removes it).
- *Not obvious:* the render cache **starts warming on its own** — you don't need to
  click the node for neighbouring pages to begin caching.

---

## MT-02: Import an image (JPG / PNG / WEBP / HEIC)

**Preconditions:** App open.

**Steps:**
1. **📥 Importieren** → choose a `.jpg`, `.png`, `.webp` or `.heic` file.

**Expected:**
- The image is converted to a **single-page PDF** node and added to the tree.
- The preview shows the image as one page.

---

## MT-03: Import an e-mail with attachments (.eml / .msg)

**Preconditions:** An `.eml` or `.msg` file that has at least one attachment.

**Steps:**
1. **📥 Importieren** → choose the e-mail file.

**Expected:**
- A **folder** node is created for the e-mail; the body and each attachment appear
  as child nodes.
- Attachments that are convertible (PDF, image, Office) become preview-able nodes.
- *Not obvious:* an attachment that cannot be converted appears as a node named
  `… – nicht importierbar (<reason>)`. The **reason in parentheses** is expected —
  it tells you why (e.g. unexpected type), instead of failing silently.
- *Not obvious:* the first Office import in a session may pause a couple of seconds
  (the Office/COM libraries load on first use only, not at startup). Dragging an item
  straight out of **Outlook** does **not** work (OLE virtual files) — import the saved
  `.msg`/`.eml` instead.

---

## MT-04: Import an archive (.zip / .tar)

**Preconditions:** A `.zip` containing a few PDFs/images, ideally in subfolders.

**Steps:**
1. **📥 Importieren** → choose the `.zip`.

**Expected:**
- The archive's **folder structure is preserved** as nested folder nodes; files
  inside become nodes with previews.
- *Not obvious:* a hostile archive is bounded — too many members or a combined
  unpacked size over the limit is refused (zip-bomb guard) rather than exhausting memory.

---

## MT-05: Import-safety — a disguised executable is refused

This verifies the content check runs on **both** the import dialog and a drag-drop
(not just the file extension).

**Preconditions:** Create a harmless fake: copy any `.exe` (or any file that starts
with the bytes `MZ`) and rename it to `rechnung.pdf`. Have it ready as a loose file
**and** as an attachment in a test `.eml`/`.msg`.

**Steps:**
1. Try to **📥 Importieren** the loose `rechnung.pdf` directly.
2. Import the e-mail containing `rechnung.pdf`.

**Expected:**
- The disguised file is **not** imported as a PDF. Directly it is refused with a
  visible reason; inside the e-mail it shows as
  `rechnung.pdf – nicht importierbar (… sieht aus wie Windows-Programm …)`.
- *Not obvious:* this is the intended safety behaviour — content is checked by its
  real signature, so an EXE/script renamed to `.pdf` is rejected with a visible
  reason rather than silently degrading. The same gate refuses OOXML Office files
  that point at an external template/source (security refusal).
