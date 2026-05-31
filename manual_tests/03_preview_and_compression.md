# 03 — Preview & compression, status

Covers the preview panel (right side), the DPI/compression controls, and the
status colour system.

---

## MT-10: Preview, zoom, original toggle

**Preconditions:** A leaf node with a real PDF/image. Select it.

**Steps:**
1. Look at the preview panel on the right.
2. Use **Strg + +** / **Strg + −** to zoom, **Strg + 0** to reset (also under
   menu **Ansicht**).
3. Toggle **Ansicht → Original anzeigen** on and off.

**Expected:**
- Pages render in the preview; zoom changes the size, reset returns to fit.
- "Original anzeigen" switches between the compressed view and the untouched
  original. *Not obvious:* for a not-yet-compressed node the two look the same.

---

## MT-11: Compress with the DPI slider and pick a method

**Preconditions:** A leaf node with a reasonably detailed page (e.g. a scanned
receipt or `compress_sample.pdf`). Select it.

**Steps:**
1. In the preview panel, drag the **DPI** slider (range 50–300).
2. Open the **Kompression** method dropdown and try the offered methods.

**Expected:**
- After a moment the page re-renders at the chosen DPI; the size labels update.
- *Not obvious:* the dropdown only lists methods that produced a file **smaller
  than the original** — methods that made it larger are hidden. A brief
  placeholder/spinner is normal while compression runs in the background.

---

## MT-12: Commit ("Lesbarkeit geprüft") and reset

**Preconditions:** A leaf node you have just compressed (MT-11).

**Steps:**
1. Click **✓ Lesbarkeit geprüft** (commit) in the preview panel.
2. Re-select the node and confirm the change stuck.
3. Now use the tree context menu: right-click the node →
   **Kompression zurücksetzen** and confirm the dialog.

**Expected:**
- **Commit** replaces the stored original with the compressed version (the node
  is now "done"); the status colour may change.
- **Kompression zurücksetzen** restores the original (uncompressed) data after a
  confirmation dialog.
- *Not obvious:* **Komprimieren**, **Lesbarkeit geprüft** and **Kompression
  zurücksetzen** are now also available directly on the **right-click menu**, not
  only via the preview panel. They are greyed out when nothing is selected.

---

## MT-13: Status colours

**Preconditions:** Any node selected.

**Steps:**
1. Right-click → **Status →** and pick, in turn, **Zu erfassen**, **Erfasst**,
   **Vorjahreswert**.

**Expected:**
- The node's row colour changes to match:
  - **Erfasst** → green
  - **Zu erfassen** → blue, highlighted
  - **Vorjahreswert** → red, highlighted
