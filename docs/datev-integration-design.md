# In-app DATEV integration — design (SHIPPED v3.10.0; DATEV-mode only)

> **Status: built in v3.10.0.** This design is now implemented — settings gate
> ([`infra/settings.py`](../infra/settings.py)), lazy service
> ([`datev/inapp.py`](../datev/inapp.py)), provenance round-trip (`Node.datev` + `SetDatev`),
> and the `CoreApi.datev_*` / `HostApi` ops wired to [`DatevBar.jsx`](../webui/src/DatevBar.jsx)
> and the export dialog. See the **In-app DATEV integration** section of the project
> [`CLAUDE.md`](../CLAUDE.md). The text below is the authoritative spec it was built to.

Everything here happens **only when DATEV mode is activated** (a settings flag + a „DATEV"
menu toggle; the DATEV code is lazy-loaded so a normal launch stays lean). In normal mode none
of this runs and BelegTool behaves exactly as today.

Mechanics it builds on: [`datev-dokumentenablage-recipe.md`](datev-dokumentenablage-recipe.md)
(connect/CRUD) and [`datev-provenance.md`](datev-provenance.md) (checkout path
`…\<doc-guid>\<document-file-id>`). DokAb keeps **no revision** → a write is a permanent
overwrite, so the save-back is guarded.

## Document state: connected vs. not connected

A working document is in exactly one of two states (DATEV mode):

- **DATEV-connected** — carries provenance `{doc_guid, file_id, structure_item_id}` + the
  open-time baseline. Established when a file is opened from a DATEV checkout path. Save offers
  **"nach DATEV zurückschreiben"** (the guarded update below).
- **Not connected** — a new/imported/locally-opened file, or one whose link was broken. Save goes
  to the **filesystem**; additionally it offers **"nach DATEV ablegen"** (file as a *new* document).

**Transitions:**

| Action | Effect on the connection |
|---|---|
| Open from a DATEV checkout path | → **connected** (capture provenance + baseline) |
| **Save As (to a filesystem path)** | **breaks the connection** → becomes **not connected** (the working doc is now that local file; the DATEV document is untouched and was *not* written). No write-back is possible afterwards until it is filed anew. |
| Write-back succeeds | stays **connected** (refresh baseline: new `file_id`/`change_date_time`) |
| **File a not-connected file to DATEV** (create) | → **connected** to the newly created document (optional; see below) |

> **Save As must clear the DATEV binding.** Choosing a filesystem target is an explicit "this is
> now a local copy" — keeping the binding would risk overwriting the DATEV document with a file the
> user deliberately diverted. After Save As, only filesystem save / file-anew are offered.

## Filing a not-connected file to DATEV (create)

A document with **no** provenance can be filed into DATEV as a **new** document — the round-2a
create flow (proven in the probe), in-app:

1. Pick **Mandant** (→ `correspondence_partner_guid`), **domain/folder/register**, class.
2. `POST /document-files` (the file bytes) → `document_file_id` (coerce to int).
3. `POST /documents` with the mandatory set (`class · correspondence_partner_guid · description ·
   domain · user · structure_items[counter,type,creation_date,last_modification_date]`; user =
   the connection user; **no `state` for class 1**).
4. On success, **optionally adopt the new `{doc_guid, file_id, structure_item.id}` as provenance**
   so the node becomes **connected** and later edits write back to it.

This is the counterpart to write-back: write-back **updates** an existing document, file-to-DATEV
**creates** one. Both are DATEV-mode only and never run in normal mode.

## On open (DATEV mode)

When a file is opened and its path is recognised as a DATEV checkout
(`parse_checkout_path` → `{doc_guid, file_id}`):

1. **Cache the opened bytes as the `original`** (the baseline) and hash them (SHA-256). The
   opened file *is* the DATEV checkout, so `original` == the server's file at open — we do **not**
   need a separate fetch at open.
2. `GET /documents/{doc_guid}` → store **`open_change_dt`** (`change_date_time`) and
   **`was_checked_out_at_open`** (`checked_out`).
3. **If it is already checked out at open, tell the user now**: "this document is checked out in
   DATEV — you'll be able to edit, but not save back; only a local save will be offered."

So the user learns the constraint up front, not only when they try to save.

## On save (DATEV mode)

The user triggers save → **ask: „Änderungen nach DATEV zurückschreiben?" (Ja/Nein)**.

- **Nein** → save to the **filesystem** (local fallback). Done.
- **Ja** → re-read the server **now** and verify against the **open-time baseline**:
  1. **Not checked out** by another (re-`GET /documents/{doc_guid}` → `checked_out` false), and
     it wasn't checked out at open either;
  2. **`change_date_time` unchanged** — `remote_change_dt == open_change_dt`;
  3. **Same bytes** — fetch the current server file
     (`GET /document-files/{current file_id}`) and compare its SHA-256 to the **cached `original`
     opened bytes**.

> ⚠️ The comparison at save is **server-now vs. the opened file** (the bytes we cached at open) —
> **not** vs. a snapshot fetched at open time. The opened file *is* the baseline.

- **All three pass** → write back: first persist the just-fetched server bytes as a **local
  backup** (the only undo on revision-less DokAb), then upload the edited bytes
  (`POST /document-files`) → `PUT /documents/{doc_guid}/structure-items/{structure_item.id}`
  (the structure item whose `document_file_id` matches the path's `file_id`).
- **Any check fails** (declined, checked out at open, now checked out, `change_date_time`
  advanced, or bytes differ) → **explain why** and **offer a filesystem save** instead. Never
  overwrite on a failed guard.

## Decision logic (pure)

`datev/writeback.py::decide_save_back(...) → verdict` encodes the above, UI-free and unit-tested:

| verdict | cause | UI action |
|---|---|---|
| `ok` | confirmed + not locked + same change_dt + same bytes | write back to DATEV |
| `declined` | user chose Nein | local save |
| `locked` | checked out at open or now | message + local save |
| `conflict_changed` | `change_date_time` advanced | message + local save |
| `conflict_content` | server bytes ≠ opened original | message + local save |

The UI maps every non-`ok` verdict to a clear message + the filesystem-save fallback.

## Security / performance notes
- Guard order is cheap→strong: confirm → `checked_out`/`change_date_time` (metadata, ~1 KB) →
  full-file SHA-256 (one download at save, reused as the backup). No polling, no per-keystroke
  fetches.
- The integrity guard is a **content hash**, not size/title (those are provenance-discovery only).
- Productive client bytes stay local (memory/`.tmp/` backup); never sent externally; logs carry
  only `{doc_guid, file_id, size, sha256-prefix, change_date_time}`, never content.
- Server also rejects the PUT if another user has it checked out — belt and suspenders.
- **Validated on the box (2026-06-27):** `change_date_time` **advances on every**
  `PUT …/structure-items/{sid}` (a swap moved it ~15 s), so the cheap metadata guard is
  trustworthy and the full hash is the optional final confirm. Also confirmed: `structure_item.id`
  is **stable** across exchanges (cache it at open) while `document_file_id` changes per version,
  and the PUT returns `204`.
