# DATEV Dokumentenablage (DokAb) via DATEVconnect — working recipe

Authoritative, **live-verified** (2026-06-27, on the practice DATEVconnect host, `feature = DokAb`)
notes for talking to the DATEV Dokumentenablage from BelegTool. Everything below was proven
end-to-end with the standalone `DATEV-Probe.exe` (package `datev/`). The spec source is
`import/document management-2.3.1.json` (vendor IP — **gitignored, never commit**).

## 1. Connection

- **One local gateway, port `58452` (HTTPS) / `58454` (HTTP).** Every DATEV API hangs off it:
  `…/datev/api/dms/v2` (Dokumentenablage), `…/master-data/v1` (Mandanten), `…/iam/v1` (users),
  `…/accounting/v1` (Rechnungswesen, OPOS), `…/law/v1` (Akten). Same host:port, different path.
- **Auth = Windows SSO (Negotiate)** as the logged-in user — no username/password. The probe
  shells out to `curl.exe --negotiate -u :` (the OPOS pattern). HTTP Basic (UPN) is a fallback.
- **TLS:** self-signed locally; trust it for loopback, otherwise rely on the machine trust store.
- **curl hardening that matters** (all learned the hard way):
  - `--http1.1` — avoids `http_code 000` on large list bodies.
  - request body from a **file** (`--data-binary @file`), never stdin (`@-`): Negotiate replays
    the body on the authenticated retry and can't rewind a stream → POST/PUT hangs.
  - `-H "Expect:"` — disable 100-continue; DATEVconnect may never answer it → POST stalls.
  - run via `Popen` with stdout/stderr to **files** (no pipes) + a hard `kill` on timeout, so a
    wedged call always surfaces instead of blocking on pipe drain.
  - `CREATE_NO_WINDOW` so the windowed exe doesn't flash a console per call.

## 2. Reading (safe)

| Call | Endpoint | Notes |
|---|---|---|
| Program type | `GET /dms/v2/info` | `feature` = `DokAb` \| `DokAbRev` \| `DMS`. **DokAb = no revisions.** |
| Folder tree | `GET /dms/v2/domains` | domain → folder → register; ids reused below |
| List documents | `GET /dms/v2/documents?filter=…&top=…` | filter keys: `number, domain.id, folder.id, register.id, state.id, correspondence_partner_guid, change_date_time` (eq/gt/lt). **No description/size filter.** |
| One document | `GET /dms/v2/documents/{guid}` | **id is a GUID**; a number → `400 id must be a guid` |
| Its files | `GET /dms/v2/documents/{guid}/structure-items` | each item: `name, type(1=file/2=folder), document_file_id, size, id` |
| File bytes | `GET /dms/v2/document-files/{file_id}` | `file_id` is the **numeric** id (a different namespace from the doc GUID) |

**Two id namespaces — do not mix:** a **document** is a GUID; a **document-file** is an integer
(`document_file_id`). `GET /documents/<number>` never works.

## 3. The lookups a create needs

- **Mandant number → `correspondence_partner_guid`:** `GET /master-data/v1/clients`, match on
  `number`, take `id` (GUID).
- **User GUID (mandatory `user`):** `GET /iam/v1/users` returns **SCIM** (`resources[]`, with
  `id`, `display_name`, `active`, `linked_windows_identity.value` = Windows SID). Pick the user
  whose SID matches the connection (the probe matches `whoami /user` automatically).
- **State:** `GET /dms/v2/documentstates`. On this box all states are `valid_document_classes:[3]`
  (Beleg). **A class-1 „Dokument" has no applicable state → omit `state` entirely.**

## 4. Insert (create a document) — round 2a

1. **Upload the file first:** `POST /dms/v2/document-files`, body = raw PDF bytes,
   `Content-Type: application/octet-stream` → returns `{ "id": "<number>" }`. **DATEV returns the
   id as a STRING; coerce to int** before using it — `document_file_id` is typed integer and a
   string leaves the file unbound (→ structure-less doc → discarded).
2. **Create the document:** `POST /dms/v2/documents`, JSON. **Mandatory elements** (spec
   "Required Elements", confirmed by `400 Not all mandatory properties are set`):
   ```jsonc
   {
     "class": { "id": 1 },                         // 1 = Dokument
     "correspondence_partner_guid": "<client GUID>",
     "description": "…",                           // the title
     "domain": { "id": 1 },                        // Mandanten
     "user":  { "id": "<user GUID>" },             // mandatory
     "structure_items": [{
       "name": "beleg.pdf", "type": 1,             // 1 = file
       "counter": 1, "parent_counter": 0,          // tree position
       "creation_date": "2026-06-27T18:28:00",     // mandatory
       "last_modification_date": "2026-06-27T18:28:00",
       "document_file_id": 1085410                 // INT, from step 1
     }],
     "folder":   { "id": 177 },                    // optional placement
     "register": { "id": 461 }                     // optional placement
     // NO "state" for class 1
   }
   ```
   → `200`/`201` with the created `Document` (its `id` is the new GUID). On a permission-less
   user the response may carry **only** a valid `id` with the rest defaulted; an empty body may
   carry the id in the **`Location`** header — read both.
   - A document left **without a valid structure is auto-deleted by DATEV (~24 h)**; always send
     the structure item with `counter`/`parent_counter` + the dates.

## 5. Edit (replace the file in place) — round 2b

To **change a file** of an existing document (the spec points here explicitly):
`PUT /dms/v2/documents/{guid}/structure-items/{structure_item_id}` — body `StructureItemUpdate`,
**requires `id` + `document_file_id`**:
```jsonc
{ "id": 1085409, "document_file_id": 1085411, "revision_comment": "…" }
```
1. Upload the new bytes (`POST /document-files`) → new `document_file_id`.
2. PUT the structure item with the new file id. **Returns `204 No Content` on success** (no body).
- **On DokAb this OVERWRITES — no revision kept** (`DokAbRev`/`DMS` keep a revision via
  `revision_comment`). Verified: after PUT the item's `document_file_id` changes and the **old
  file id returns `not found`**.
- **`structure_item.id` is STABLE across exchanges** (e.g. stays `1085411`); only
  `document_file_id` changes per version (1085414 → 1085415 → …). So the structure-item id is the
  durable PUT handle; the checkout path's file id is the *current* version pointer — map it to the
  structure item via `GET …/structure-items` (find the item whose `document_file_id` matches).
- **`change_date_time` advances on every PUT** (verified: a swap moved it ~15 s) → it is a
  **trustworthy concurrency guard**; a full content hash is then only the optional final confirm.
- The PUT is **rejected if the document is checked out by another user** (the conflict guard).
- The "composition can only be manipulated in the offline product" note refers to **re-arranging
  the structure tree**, not swapping a file — file swap via this endpoint works.

## 6. Delete

`DELETE /dms/v2/documents/{guid}`. Deleted documents are still readable via `GET /documents/{id}`
and findable with the „Gelöscht" filter.

## 7. Implications for BelegTool "update itself back into DATEV"

- **Feasible on DokAb via the API:** upload new bytes → `PUT …/structure-items/{sid}`. It is a
  destructive overwrite (no revision) — re-read `change_date_time` / honour `checked_out` before
  writing as the conflict check (there is no ETag/If-Match).
- Provenance (which DATEV document a BelegTool file is): see
  [`datev-provenance.md`](datev-provenance.md).

> Connection details mirror OPOS (`src/io/datev_api.py`). The probe and these findings are the
> input for the in-app DATEV integration (settings flag + lazy-loaded DATEV mode).
