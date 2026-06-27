# 10 — DATEV mode (v3.10.0)

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
1. In the header, click **„Nach DATEV ablegen"**.
2. Enter a **test Mandant number** at the prompt.

**Expected:**
- A success notice **„In DATEV abgelegt"** appears.
- In DATEV (Dokumentenablage of that Mandant), a **new** document holds the exported file.
- The header badge flips to **„Mit DATEV verknüpft"** (the document is now connected, so a
  later edit offers write-back).

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
test document (DATEV materialises `…\<doc-guid>\<file-id>.pdf`).

**Steps:**
1. Open the checked-out **`.pdf`** directly (double-click / file association / `BelegTool.exe <path>`).
   It opens in the **PDF-Tool** surface (single-PDF editor), **not** the organizer.
2. In the PDF-Tool toolbar, confirm a **„🔗 Nach DATEV zurückschreiben"** button is shown.
3. Add a small note (✎ Text), then click **„🔗 Nach DATEV zurückschreiben"** and confirm **Ja**.

**Expected:**
- The write-back **succeeds** — status shows **„Nach DATEV zurückgeschrieben ✓ · <file>.pdf"**.
  ⚠️ It must **not** report a conflict on the very first, otherwise-unedited write-back (the
  content baseline hashes the raw checkout file, so an unchanged checkout is never a false
  conflict).
- The status line **names the saved file** so you can see it saved a **`.pdf`** (the on-disk
  checkout file is overwritten with the edited PDF — still a valid PDF, no `.belegtool` structure).
- In DATEV the document's file reflects the edit; a backup of the previous server bytes is in
  `%APPDATA%\DigitalerUnterlagenOrdner\datev_backups\`.
- A **not-connected** PDF (opened from a non-checkout path) instead shows **„📤 Nach DATEV
  ablegen"**, which prompts a Mandant and files it as a new DATEV document.
- With DATEV mode **off**, the PDF-Tool shows **no** DATEV button at all.
