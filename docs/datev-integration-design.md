# In-app DATEV integration — design (deferred; DATEV-mode only)

Everything here happens **only when DATEV mode is activated** (a settings flag + a „DATEV"
menu toggle; the DATEV code is lazy-loaded so a normal launch stays lean). In normal mode none
of this runs and BelegTool behaves exactly as today.

Mechanics it builds on: [`datev-dokumentenablage-recipe.md`](datev-dokumentenablage-recipe.md)
(connect/CRUD) and [`datev-provenance.md`](datev-provenance.md) (checkout path
`…\<doc-guid>\<document-file-id>`). DokAb keeps **no revision** → a write is a permanent
overwrite, so the save-back is guarded.

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
- **To validate before building:** confirm on the box that `change_date_time` advances after a
  `PUT …/structure-items/{sid}` (then the cheap guard is trustworthy and the hash is the confirm).
