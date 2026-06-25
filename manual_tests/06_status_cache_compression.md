# 06 — Status bar, render cache & compression UX

Covers the bottom **status bar**, the **render-cache** behaviour, and the
compression workflow (default-to-smallest, remembered choice, carry-on-split,
cancel-on-remove). Launch with `python host.py` and open a document with several
multi-page nodes (a real scanned `.belegtool` is ideal).

---

## MT-40: Status bar — background activity & cache gauge

**Preconditions:** A document with a few multi-page nodes is open.

**Steps:**
1. Look at the **bottom bar**. Note the right-hand readout `📦 Cache x/y MB · n/m Seiten`.
2. Click through several nodes quickly and watch the left side of the bar.
3. Hover the cache readout.

**Expected:**
- Left side shows live background work: **Komprimiere N**, **Vorschau lädt N**,
  **Cache füllt** — or **Bereit** when idle. *Not obvious:* **Komprimiere** counts
  **distinct nodes**, not operations.
- The cache readout climbs as pages render: **used / budget MB** and
  **cached / total pages**. *Not obvious:* cached pages can **exceed** the document's
  page count — a node caches its plain render *and* its compressed variant separately.
- The tooltip shows the free MB.

---

## MT-41: Cache grow / shrink buttons (＋ / −)

**Steps:**
1. Browse a large document until the cache MB rises.
2. Click **＋** (next to the cache readout) a few times.
3. Click **−** several times, below the current usage.

**Expected:**
- **＋** raises the budget by 50 MB each click; the prefetch immediately starts
  **filling the new headroom** (watch "Cache füllt" and the MB climb).
- **−** lowers the budget by 50 MB (floor 50 MB) and, if usage was above the new
  budget, **frees memory right away** (the used-MB drops to fit).

---

## MT-42: Background prefetch warms the whole document

**Preconditions:** A document larger than a couple of nodes; let it sit idle.

**Steps:**
1. Open a document (or import files) and **don't click anything**.
2. Watch the cache `n/m Seiten` for ~10–30 s.
3. Select a node, then jump to a far-away node and scroll.

**Expected:**
- Warming **starts on its own after opening/importing** (no node click needed) and
  keeps climbing toward the budget across the **whole** document, nearest nodes first.
- Pages you scroll to are usually **already rendered** (little or no "Seite N"
  placeholder). *Not obvious:* warming **pauses while a compression runs** (so it gets
  the CPU) and **resumes automatically** when the compression finishes.

---

## MT-43: Compression defaults to the smallest variant (≤ 5 pages)

**Preconditions:** A node with **2–5 pages** that compresses well (a scan).

**Steps:**
1. Select the node. Wait a moment.
2. Open the compression dropdown (top of the preview).
3. Select a different method, then re-select the node later.

**Expected:**
- On display, the preview **switches to the smallest variant by default** (the
  dropdown shows that method selected, with sizes). *Not obvious:* this only happens
  automatically for nodes **≤ 5 pages**; larger nodes stay on the original until you
  open the dropdown.
- The **"unkomprimierte Fassung"** entry shows the source size.
- Your last chosen method is **remembered** for that node when you come back.
- *Low-res files:* if nothing is smaller than the original, only **"unkomprimierte
  Fassung"** is offered — that is correct.

---

## MT-44: Apply compression — "Lesbarkeit geprüft"

**Steps:**
1. On a node, pick a method, check the preview is readable.
2. Click **❓ Lesbarkeit geprüft**.
3. Save, close, reopen the file; select the node.

**Expected:**
- The preview updates to the committed result **immediately** (no manual scroll
  needed). The button shows **✓ übernommen**.
- *Not obvious:* an **un-applied** variant is **not saved** — only after "Lesbarkeit
  geprüft" is the compressed result stored. After reopening, a committed node shows
  **"bereits komprimiert (keine Quelle)"** and can't be re-compressed/reset.

---

## MT-45: Split carries the compression; cancel on split

**Preconditions:** A multi-page node with an **applied** compression (MT-44), source
still present (not yet saved+reopened).

**Steps:**
1. Right-click the node → **Splitten ▸ pro Seite**.
2. Inspect the resulting one-page parts (open the compression dropdown on one).
3. Separately: select a large node so it starts compressing (watch **Komprimiere 1**),
   then immediately split or delete it.

**Expected:**
- The split parts arrive **already compressed** (same quality — verbatim slice) **and**
  still editable; no recompute needed. *Not obvious:* if the winning method was the
  structural **pikepdf** one, parts recompute from source instead.
- Splitting/deleting a node that is **currently compressing** **stops** that
  compression — the **Komprimiere N** count drops (it doesn't run to completion on a
  node that's gone).

---

## MT-46: Compression variants persist across reload

**Preconditions:** A node that compresses well, **not** yet applied.

**Steps:**
1. Select the node; open the compression dropdown and let the method **sizes** load
   (the variants are now computed for this session). Do **not** click "Lesbarkeit
   geprüft".
2. **Save** the file (💾). Close the app. Reopen it and open the same file.
3. Select that node and open the compression dropdown again.

**Expected:**
- The method list and previews come back **instantly** — no "Kompression läuft …",
  no multi-second wait. The variants were embedded in the `.belegtool` (as hidden
  per-node attachments) and reloaded. *Not obvious:* the file still opens normally in
  any PDF viewer (the variants are attachments, not pages); a committed node has no
  source and stores no variants.

---

## MT-47: Red "undecided" dot stays gone for incompressible docs (move + reopen)

**Preconditions:** A document with **many (≥ 20) low-resolution / already-small leaf
documents** that have **no worthwhile compression** — e.g. a folder full of small,
mostly-text single-page PDFs. (Each shows a **red dot at the front of its row** until
its compression has been evaluated.)

**Steps:**
1. Open the document and **wait a few seconds** without clicking — the background sweep
   evaluates the small leaves. Watch the red front dots disappear as each resolves.
2. Once the red dots are gone, **drag one of those leaves** to a different folder /
   position (or use Insert to move it).
3. **Save** (💾), close the app, and **reopen** the same file.

**Expected:**
- After the sweep, the incompressible leaves show **no red front dot** (nothing smaller
  was found → the decision is made).
- **Moving** a leaf does **not** bring its red dot back — and crucially, moving one does
  not make *other* already-resolved leaves light up again. *(This was the bug fixed in
  v3.9.5: with more than ~16 such documents the verdict used to be forgotten, so the red
  dots reappeared on move or reopen.)*
- After **reopen**, the incompressible leaves are **still dot-free** without any new wait
  — the "nothing smaller found" verdict was saved in the file.
- *Contrast:* a leaf that **does** have a smaller variant available but not yet applied
  **keeps** its red dot (a decision is still pending) — that is correct, not a bug.

