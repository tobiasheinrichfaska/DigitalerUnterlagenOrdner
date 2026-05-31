# 01 — Import

Covers bringing files into the storage tree and the import-safety guard.

---

## MT-01: Import a single PDF

**Preconditions:** App open, no file loaded (or a storage already open).

**Steps:**
1. Click **[Import]** in the toolbar (or menu **Datei → Importieren…**, or `Strg+O`).
2. In the file dialog, choose a multi-page PDF (e.g. `tests/data/input/sample.pdf`).
3. Confirm the dialog.

**Expected:**
- A new node with the file name appears in the **tree** (left).
- Selecting it shows the page images in the **preview** (right). *Not obvious:* a
  grey **placeholder** image may appear for a moment before the real preview is
  rendered — this is normal (previews are generated lazily).
- The window now has unsaved changes: **Datei → Speichern** is available.

---

## MT-02: Import an image (JPG / PNG)

**Preconditions:** App open.

**Steps:**
1. **[Import]** → choose a `.jpg` or `.png` file.

**Expected:**
- The image is converted to a **single-page PDF** node and added to the tree.
- The preview shows the image as one page.

---

## MT-03: Import an e-mail with attachments (.eml / .msg)

**Preconditions:** An `.eml` or `.msg` file that has at least one attachment.

**Steps:**
1. **[Import]** → choose the e-mail file.

**Expected:**
- A **folder** node is created for the e-mail; the body and each attachment
  appear as child nodes.
- Attachments that are convertible (PDF, image, Office) become preview-able nodes.
- *Not obvious:* an attachment that cannot be converted appears as a node named
  `… – nicht importierbar (<reason>)`. The **reason in parentheses** is expected
  — it tells you why (e.g. unexpected type), instead of failing silently.

---

## MT-04: Import an archive (.zip)

**Preconditions:** A `.zip` containing a few PDFs/images, ideally in subfolders.

**Steps:**
1. **[Import]** → choose the `.zip`.

**Expected:**
- The archive's **folder structure is preserved** as nested folder nodes.
- Files inside become nodes with previews.

---

## MT-05: Import-safety — a disguised executable is refused

This verifies the content check (not just the file extension).

**Preconditions:** Create a harmless fake: copy any `.exe` (or any file that
starts with the bytes `MZ`) and rename it to `rechnung.pdf`. Put it as an
attachment in a test `.eml`/`.msg`, **or** import it directly if the dialog lets
you pick it.

**Steps:**
1. Import the e-mail containing `rechnung.pdf` (the disguised file).

**Expected:**
- The disguised file is **not** imported as a PDF. It shows up as
  `rechnung.pdf – nicht importierbar (… sieht aus wie Windows-Programm …)`.
- *Not obvious:* this is the intended safety behaviour — content is checked by
  its real signature, so an EXE renamed to `.pdf` is rejected with a visible
  reason rather than silently degrading.
