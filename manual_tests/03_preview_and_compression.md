# 03 — Preview & compression, status

Covers the preview panel (right side), the DPI/compression controls
(`PreviewControls.jsx`), and the status-dot system, in the **React/pywebview UI**.
The status **dots** have a dedicated deep test in `08_status_dots_help.md`; this file
covers the basics.

---

## MT-10: Preview & zoom

**Preconditions:** A leaf node with a real PDF/image. Select it.

**Steps:**
1. Look at the preview panel on the right; scroll through the pages.
2. Zoom with **Strg + Mausrad** (Ctrl + wheel) over the preview, and use the zoom bar
   **− / ＋ / 100 %** at the bottom of the preview.

**Expected:**
- Pages render in the preview (windowed — only visible pages render, placeholders fill
  in as you scroll; see MT-39). Ctrl+wheel and the zoom bar change the page size.
- The zoom bar also shows the viewport position as **"Seite n / m"**.
- *Not obvious:* there is **no separate "Original anzeigen" toggle** — the preview shows
  the node's effective bytes; the compression **working-preview** (MT-11) is where you
  compare a method against the original.

---

## MT-11: Compress with the DPI slider and pick a method

**Preconditions:** A leaf node with a reasonably detailed page (e.g. a scanned receipt or
`compress_sample.pdf`). Select it.

**Steps:**
1. In the preview panel, open the **Kompression** method dropdown.
2. Pick a method; drag the **DPI** slider (range 50–300); also try **unkomprimierte Fassung**.

**Expected:**
- *Not obvious:* selecting a leaf runs **no** compression (the undo arrow stays disabled).
  Opening the dropdown shows **"Kompression läuft …"**, then the methods.
- The dropdown only lists methods that produced a file **smaller than the original** —
  methods that made it larger are hidden. Methods include **JPG (Graustufen)**,
  **JPG (Farbe)** (keeps colour), **PNG**, and **pikepdf** (structural). The original size
  is shown for comparison.
- Browsing methods/DPI only **previews** — the document is not changed yet (windowed, so a
  big document doesn't freeze; switching back to an already-viewed method is instant).

---

## MT-12: Commit ("Lesbarkeit geprüft") and reset

**Preconditions:** A leaf node you have just been previewing a method on (MT-11).

**Steps:**
1. Click **✓ Lesbarkeit geprüft** (commit) in the preview panel.
2. Re-select the node and confirm the chosen method stuck (the button now reads **✓ übernommen**).
3. On an **uncommitted** node, use the **reset** button in the preview controls.

**Expected:**
- **Commit** applies the compressed version as the node's current data (one undo step); the
  front red "undecided" dot clears.
- **Reset** (on an uncommitted node) returns to the original bytes.
- *Not obvious / important:* once a committed node has been **saved**, its source is dropped
  — on reload the compression dropdown shows **"bereits komprimiert (keine Quelle)"** and is
  **disabled** (re-compress and reset are blocked). This is by design and irreversible — see
  `04_export_persistence.md` MT-17. (Compression controls live only in the preview panel, not
  on the right-click menu.)

---

## MT-13: Status dots

**Preconditions:** A document with a folder containing several leaves.

**Steps:**
1. Right-click a leaf → **Status →** and pick, in turn, **Zu erfassen**, **Erfasst**,
   **Vorjahr**, then **Kein Status**.
2. Right-click the **folder** → **Status (gesamter Inhalt) →** pick a value.

**Expected:**
- A leaf shows a single **trailing dot**: **zu erfassen → yellow**, **erfasst → green**,
  **vorjahreswert → red**, **Kein Status → no dot**.
- A **folder** shows one dot per distinct descendant status (red → yellow → green) **plus a
  black dot** when descendants are mixed with/without status; an all-no-status or empty
  folder shows no dots. Setting a status on a folder **cascades to every descendant document**.
- *Not obvious:* this replaced the old row-colour scheme — status is shown as dots, not by
  tinting the row. The full aggregation rules are tested in `08_status_dots_help.md`.
