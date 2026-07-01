# 10 — DATEV mode (v3.11.0)

The in-app DATEV integration files / writes documents back into the local **DATEV
Dokumentenablage** via DATEVconnect. It is **off by default** and **lazy-loaded** — when
DATEV mode is off, none of this runs and BelegTool behaves exactly as before.

> ⚠️ **Environment:** these cases need a machine with **DATEVconnect** running (the local
> gateway on port `58452`) and Windows SSO as a DATEV user — typically the Kanzlei box. On
> any machine **without** a reachable DATEVconnect, only **MT-DATEV-01** (the toggle) and the
> "no crash when offline" checks apply; mark the rest **N/A — no DATEV box**.
>
> ⚠️ **Productive data:** the write-back **overwrites** the DATEV document (DokAb keeps no
> revision). Use a **test client / test document** ("ZZZ TEST"), never real client data, when
> exercising write-back and delete. A local backup of the previous bytes is written to
> `%APPDATA%\DigitalerUnterlagenOrdner\datev_backups\` before every overwrite.

---

## MT-DATEV-01: Toggle DATEV mode on and off (no DATEV box needed)

**Preconditions:** App open (any document).

**Steps:**
1. Find the **„DATEV"** button in the header (to the right of the toolbar).
2. Click it.
3. Close and reopen the app.
4. Click **„DATEV"** again to turn it off.

**Expected:**
- The button shows a filled green state with a **●** dot when on.
- The setting is **persisted per user**: after reopening, DATEV mode is **still on** (it is
  stored in `%APPDATA%\DigitalerUnterlagenOrdner\settings.json`, your own profile — on a
  terminal server every user has their own).
- With **no DATEV box reachable**, toggling on must **not** freeze or crash the app; no
  document badge or actions appear (there is nothing connected). Turning it off returns the
  header to the plain state.

---

## MT-DATEV-02: „from DATEV" badge on a checked-out document

**Preconditions:** DATEV mode **on**; a DATEVconnect box reachable. In DATEV, **check out** a
test document — DATEV materialises its file at `…\<doc-guid>\<file-id>.pdf`.

**Steps:**
1. In BelegTool, **open** that checked-out PDF (drag it in / „Öffnen", or `BelegTool.exe <path>`).
2. Look at the header bar.

**Expected:**
- A **🔗 „Mit DATEV verknüpft"** badge appears, showing the source file name.
- If the document was **already checked out by someone else** at the moment you opened it, a
  **„· in DATEV ausgecheckt"** hint is shown **immediately** (you learn the constraint up
  front, not only when you try to save).
- A **„Nach DATEV zurückschreiben"** button is offered next to the badge.

---

## MT-DATEV-03: Guarded write-back (happy path)

**Preconditions:** MT-DATEV-02 done (a connected test document open, not checked out by anyone
else). Make a small edit (e.g. add a FreeText note via the PDF-Tool, or any change).

**Steps:**
1. Click **„Nach DATEV zurückschreiben"**.
2. Confirm the **„Nach DATEV zurückschreiben?"** dialog with **Ja**.

**Expected:**
- A success notice **„Nach DATEV zurückgeschrieben"** appears.
- In DATEV, the document's file now reflects your edit; its **change date advances**.
- **The bound `.belegtool` is also saved on disk in the same step** — there is always a local
  path, so write-back and the local copy stay in sync **without any „Speichern unter…" prompt**.
  The unsaved-changes **„•"** clears (the title no longer shows pending changes).
- A backup of the **previous** server file was written to
  `%APPDATA%\DigitalerUnterlagenOrdner\datev_backups\` **before** the overwrite.
- Choosing **Nein** (cancel the dialog) writes **nothing** to DATEV — you can then use the
  normal **💾 Speichern** for a local file instead.

**Edge — DATEV succeeds but the local save fails** (e.g. the `.belegtool` sits on a removed
USB / read-only network share): provoke it by making the local file unwritable, then write back.
*Expected:* the **„Nach DATEV zurückgeschrieben"** notice still appears (DATEV **did** get the
edit), **and** a separate error names the failed local save — your edit is not silently lost,
and you can re-save locally to a writable location.

---

## MT-DATEV-04: Write-back conflict guards (fallbacks)

**Preconditions:** A connected test document open (as MT-DATEV-03).

**Try each and confirm the write is REFUSED with a clear message (never a silent overwrite):**

| Provoke | Expected message (then: save locally) |
|---|---|
| In DATEV, **check out** the document by another user, then write back | „DATEV: Das Dokument ist ausgecheckt — nur lokal speichern möglich." |
| In DATEV, **change** the document (new file) after you opened it, then write back | „DATEV: Das Dokument wurde zwischenzeitlich geändert …" |
| Open a **saved `.belegtool`** that remembers a DATEV origin but whose content no longer matches the server file, then write back | „DATEV: Der Serverstand weicht vom geöffneten Stand ab …" |

**Expected:** In every case the DATEV document is **left untouched**, the message explains why,
and you can fall back to a normal local **Speichern**.

---

## MT-DATEV-05: File a not-connected document into DATEV

**Preconditions:** DATEV mode **on**; open a **normal** document (NOT from a checkout path) —
so it is **not** connected.

**Steps:**
1. In the header, click **„Nach DATEV ablegen"**. A **filing dialog** opens (no longer a bare
   number prompt) and loads the client list.
2. In the dialog: type in the **Mandant** search box (filters by number OR name) and pick the
   client from the list. Check the **Bezeichnung** field — it is **prefilled with the document
   name** and becomes the document's **name in DATEV**; edit it if you like. Optionally choose a
   **Ordner** + **Register**, a **Belegdatum**, and a **Veranlagungsjahr**/**-monat**. Click **„Ablegen"**.

**Expected:**
- **„Ablegen" is disabled until BOTH a Mandant is chosen AND a Bezeichnung is present** — clearing
  the Bezeichnung disables it, so a filed document is **never nameless**. (No client → no safe
  target.) Choosing a month without a year shows a hint and keeps it disabled.
- A success notice **„In DATEV abgelegt"** appears.
- In DATEV (Dokumentenablage of that Mandant), a **new** document holds the exported file, **its
  name = the Bezeichnung you entered**, in the chosen folder/register, with the Belegdatum as
  `receipt_date` and the Veranlagungszeitraum as the document's **Jahr/Monat** (verify these fields
  in DATEV — they are mapped per the DMS spec but should be confirmed on first real use).
- The header badge flips to **„Mit DATEV verknüpft"** (the document is now connected, so a
  later edit offers write-back).
- **If the client list cannot be loaded** (master-data unreachable), the dialog shows the reason
  and **„Ablegen" stays disabled** — filing is refused rather than guessed.

---

## MT-DATEV-06: Export → DATEV (same client), including split

**Preconditions:** A **connected** test document open (so the same-client Mandant is known);
DATEV mode on.

**Steps:**
1. Click **⬇ Export PDF**.
2. In the export dialog, tick **„Nach DATEV ablegen (gleicher Mandant)"**.
3. (Optional) also tick **„In mehrere Dateien aufteilen"** with a small page threshold.
4. Click **Exportieren**.

**Expected:**
- **No file save dialog** appears — the export goes to DATEV instead of disk.
- A notice reports **„In DATEV abgelegt (N Dokumente)"**.
- In DATEV, **N new documents** appear under the **same client** as the source — when split is
  on, **each part PDF is its own document** (N = the number of parts); when off, exactly one.

---

## MT-DATEV-07: Mode-off is truly inert (regression)

**Preconditions:** DATEV mode **off**.

**Steps:**
1. Open, edit, save, and export documents as usual.

**Expected:**
- No DATEV badge, no DATEV actions, no DATEV option in the export dialog.
- Behaviour is identical to a build without the DATEV feature (the `datev` package is not even
  imported). Nothing about DATEV should appear anywhere.

---

## MT-DATEV-08: Write back a checkout opened in the PDF-Tool (PDF opening)

**Preconditions:** DATEV mode **on**; a DATEVconnect box reachable. In DATEV, **check out** a
test document. DATEV materialises it in one of two shapes — both must be recognised:
- **DMS:** `…\<doc-guid>\<file-id>.pdf` (the file is named `<file-id>`);
- **DokOrg Pro:** `…\<doc-guid>\<file-id>\<name>.pdf` (`<file-id>` is a **folder**, the real name follows).

⚠️ **Key behaviour (confirmed live 2026-06-30): DATEV refuses an API write-back to a *checked-out*
document** ("The document can't be changed because it is checked out"). So a checked-out doc is
saved the **native** way — edit the working copy, **check it in via DATEV** — and the PDF-Tool does
**not** offer „🔗 Nach DATEV zurückschreiben" for it. In-place API write-back applies only to a
connected doc that is **not** checked out.

**Steps (checked-out document — the normal DokOrg flow):**
1. Open the checked-out **`.pdf`** directly (double-click / file association / `BelegTool.exe <path>`).
   It opens in the **PDF-Tool** surface (single-PDF editor), **not** the organizer.
   ⚠️ **The window must appear and render the PDF immediately** — it must **not** hang for 10-20 s
   waiting for the DATEV connection (the connect runs in the background).
   ⚠️ **The page content must be VISIBLE, not a blank white page.** DATEV documents are scans
   (JBIG2 / JPEG2000); the PDF-Tool bundles the PDF.js wasm decoders (`/pdfjs/wasm/`) so these
   render. A blank page with a correct page count = the decoder assets aren't being served (regression).
2. Confirm the toolbar shows the badge **„🔗 Mit DATEV verknüpft · <file> · ausgecheckt
   (💾 Speichern → in DATEV einchecken)"** and that there is **NO „🔗 Nach DATEV zurückschreiben"**
   button (it is hidden for a checked-out doc).
3. Add a small note (✎ Text), then click **💾 Speichern**.
4. In DATEV, **check the document back in**.

**Expected:**
- After **💾 Speichern**: status **„Gespeichert ✓"**; the edit is written to the local **working
  copy** (the checked-out `.pdf` in your profile's DokOrg checkout folder).
  - If the working copy is **locked / read-only**, Speichern reports the error (`[Errno 13]…`) —
    nothing was saved; close whatever holds the file and retry.
- After the **DATEV check-in**: the document's new version in DATEV reflects your edit (DokOrg uploads
  the working copy as the new version).
- **Diagnostics** (`belegtool_diag.log`, next to the exe) for this doc show
  `checked_out=True`, `resolved: file_id=… structure_item_id=…` (the **server** ids, not the path
  number), and — *only if you somehow trigger a write-back* — `verdict=checked_out_self` followed by a
  local-working-copy save (the safety net), **never** a raw "can't be changed because it is checked out".

**Steps (connected doc that is NOT checked out — in-place write-back still works):**
1. Open a connected `.pdf` that is **not** checked out.
2. Confirm the **„🔗 Nach DATEV zurückschreiben"** button **is** shown; add a note; click it; confirm **Ja**.

**Expected:** status **„Nach DATEV zurückgeschrieben ✓ · <file>.pdf"**; the DATEV file reflects the
edit; a backup of the previous server bytes is in `%APPDATA%\DigitalerUnterlagenOrdner\datev_backups\`.
The local copy is also overwritten when writable; a locked local copy after a *successful* server
write-back is **silently** tolerated (no `[Errno 13]` on a ✓).

**Other surfaces:**
- A **not-connected** PDF shows **„📤 Nach DATEV ablegen"** → the filing dialog (searchable Mandant +
  folder/register + Belegdatum + Veranlagungsjahr/-monat) files it as a new DATEV document.
- The DATEV write-back button is **disabled with a hint** while the connection is still establishing.
- With DATEV mode **off**, the PDF-Tool shows **no** DATEV button at all.

---

## MT-DATEV-09: File a node opened „in PDF-Tool" into DATEV

**Preconditions:** DATEV mode **on**; a DATEVconnect box reachable. Open a **normal `.belegtool`**
in the organizer (not from a checkout), with at least one document (leaf) node.

**Steps:**
1. Right-click a document node → **„Im PDF-Tool öffnen"**. It opens in the **PDF-Tool** surface,
   **bound to that node** (a node binding, not a file).
2. Confirm a **„📤 Nach DATEV ablegen"** button is shown (NOT a blank toolbar — this used to be
   missing entirely for a node opened in the PDF-Tool).
3. Add a small note (✎ Text). Click **„📤 Nach DATEV ablegen"** → the **same filing dialog**
   opens (searchable Mandant + **Bezeichnung** + folder/register + Belegdatum + Veranlagung).
   Pick a test Mandant, keep/edit the Bezeichnung, click **„Ablegen"**.

**Expected:**
- A success notice **„In DATEV abgelegt ✓"** appears.
- In DATEV, a **new** document holds the (edited) PDF under the chosen Mandant, named after the
  Bezeichnung.
- Back in the **organizer**, the node now reflects your edit (the baked bytes were pushed back to
  the owner node) — there is **no** „lokal nicht gespeichert" error, because the node binding's
  local target is the organizer node itself (no separate file path).
- A node binding only ever offers **file-anew** (📤), never write-back (🔗) — the organizer owns
  any DATEV link, so write-back of a connected `.belegtool` is done there (MT-DATEV-03).
