# 09 — PDF-Tool (text + forms, save-back)

The PDF-Tool is the second surface: it renders a single PDF richly (selectable text,
fillable AcroForm) and lets you **add text** and **fill forms**, saved back into the node.
It opens in its own window. These cases need a person — jsdom/unit tests can't drive the
PDF.js editor.

Preconditions: a `.belegtool` open in the organizer with at least one **leaf** (a PDF
document, not a folder) and one folder.

---

## MT-50: Open a leaf in the PDF-Tool — and a folder cannot
**Steps**
1. Right-click a **leaf** (document) node → context menu.
2. Click **„Im PDF-Tool öffnen"**.
3. Close that window. Right-click a **folder** node.

**Expected**
- Step 2 opens a **new window** showing the PDF with a top toolbar („✎ Text", „💾 Speichern").
  The document is readable; you can select text with the mouse.
- Step 3: the folder's context menu **has no „Im PDF-Tool öffnen"** entry — a folder has no
  PDF, so it can't be opened (the entry is simply absent, not greyed).
- While a node is open in the PDF-Tool it is **locked** in the organizer: content ops on it
  (rotate/split/merge/compress/delete) are refused there until the tool window is closed.

## MT-51: Add text and save it back
**Steps**
1. Open a leaf in the PDF-Tool (MT-50).
2. Click **„✎ Text"** (it highlights). Click on the page and type a note (e.g. „Geprüft 27.06.").
3. Click **„💾 Speichern"**. Watch the status text on the right of the toolbar.
4. Close the PDF-Tool window. Back in the organizer, look at that node.

**Expected**
- Step 2: the „✎ Text" button shows an active/pressed state; clicking the page places an
  editable text box you can type into and reposition.
- Step 3: the status shows **„Speichern…" → „Gespeichert ✓"**. (If it shows a German error,
  note it — e.g. an unbound sample document can't save.)
- Step 4: the organizer is now marked **unsaved** (the node took the edited bytes as its new
  source; **Undo** reverts it). Saving the `.belegtool` persists the change.

## MT-52: Re-edit text across sessions (round-trip)
**Steps**
1. After MT-51 (text added + saved), reopen the **same** node in the PDF-Tool.
2. Click **„✎ Text"** and click your earlier note.

**Expected**
- Your previously added text is **still on the page** and is **selectable/re-editable** — you
  can change its wording, move it, or delete it. (It was saved as a real FreeText annotation,
  which the PDF-Tool reloads as an editable object — not flattened into the image.)

> ⚠ Note: if you **compress** the node in the organizer afterwards, the page is rasterised and
> your added text becomes part of the picture — no longer editable. Compression is a deliberate
> flatten; add/finalise text before compressing.

## MT-53: Fill a form field and save
**Preconditions:** a leaf that is a PDF **form** (AcroForm) — e.g. a fillable Antrag.
**Steps**
1. Open it in the PDF-Tool. Click a form field and type a value.
2. Click **„💾 Speichern"**; close; reopen the node.

**Expected**
- The field accepts input; after save+reopen the value is **still in the field** (live form
  field, re-editable). Status showed „Gespeichert ✓".
