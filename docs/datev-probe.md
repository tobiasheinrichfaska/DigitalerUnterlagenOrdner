# DATEV-Probe — standalone read/(later)write probe for DATEVconnect DMS v2

A small **standalone one-file exe** to check, against the *real* DATEV install, what the
DATEVconnect Dokumentenablage API actually does — so we know what to build into BelegTool.
It is **not** part of the BelegTool app; its results drive that work.

## Why
The OpenAPI spec (`document management 2.3.1`) defines the *interface*, but install-specific
facts decide the design and only the live box reveals them:
- **`GET /info → feature`** = `DokAB` / `DokAbRev` / `DMS`. **DokAB has no revision
  management**, so a file *exchange* is a destructive overwrite; `DokAbRev`/`DMS` keep a
  revision. (Confirmed target here: **DokAB**.)
- Is the API **licensed/reachable**? (BroCheck hit a missing-license wall; this box reports
  `info`/`documents`/`domains` available.)
- The exact runtime behaviour of create + exchange.

## Rounds
1. **Read (done, live-verified).** Govern each retrieval from the GUI: connect → `info`
   (feature) → `domains` → `documents` (filter + max) → one document's structure-items → its
   file. Read-only; safe. **Confirmed on the live box: `feature = "DokAb"`** (no revisions →
   exchange overwrites), `environment = "Kanzlei"`, rich domain/folder/register taxonomy, and
   the `Mandanten` domain links to `master-data/v1/clients` for the client GUID.
2a. **Create only (this build).** Resolve a **Mandant number → GUID** via
   `master-data/v1/clients` (the create's required `correspondence_partner_guid`), upload a
   **synthetic** one-page PDF (`POST /document-files` → `document_file_id`), then `POST
   /documents` with the chosen domain/folder/register and **save the returned document id +
   `change_date_time`**. Reads the structure back so we see what DokAb stored. Confirm-gated.
2b. **Exchange + delete (next).** Upload new bytes, `PUT /documents/{savedId}` with the
   structure item pointing at the new file id — **only on the id created in 2a** — to observe
   overwrite-vs-revision; then `DELETE /documents/{savedId}` to clean up. Re-GET and compare
   `change_date_time` first (the conflict token; DokAb has no ETag).

## Safety
- Round 1 is read-only.
- Round 2a **creates** one document from **synthetic PDF bytes** (`datev/synthetic_pdf.py` —
  never a real document), under a **client and folder/register you choose in the GUI**,
  auto-labelled `ZZZ TEST – DATEV-Probe – bitte löschen`, behind an explicit confirm dialog.
  No existing document is read, modified, or deleted. The Mandant number is entered at runtime
  (never hard-coded — this is a public repo).
- Round 2b will only ever modify/delete the document **created in the same run** (the saved
  id); every write stays confirm-gated.

## Architecture (BelegTool, Python)
| File | Role |
|---|---|
| `datev/types.py` | `DatevConfig`, injected `Transport`, errors, `program_keeps_revisions` (DokAB ⇒ overwrite) |
| `datev/endpoints.py` | data-driven DMS v2 endpoint catalog (read) + `build_url` |
| `datev/transport.py` | stdlib `urllib` transport (Basic auth header from the client; self-signed-TLS tolerant). SSO/Negotiate later. |
| `datev/client.py` | `DatevConnectClient` — read: `get_info` / `list_domains` / `list_documents` / `get_document` / `list_structure_items` / `get_document_file`; create (2a): `resolve_client_guid` / `list_clients` / `upload_document_file` / `create_document`; maps 401 → `DatevAuthError`, license envelope → `DatevLicenseError` |
| `datev/synthetic_pdf.py` | `make_test_pdf` — a tiny hand-built one-page PDF (stdlib only), the throwaway bytes for 2a |
| `datev/probe_gui.py` | Tkinter governing GUI — every retrieval/write is an explicit, logged button; 2a create is confirm-gated |
| `datev_probe.py` | one-file exe entry point |
| `tests/test_datev_client.py` | unit tests with a fake transport (no live DATEV): feature, reads, query/path building, Basic auth, error mapping |

## Connection (mirrors OPOS)
The connector matches OPOS's proven `src/io/datev_api.py`:
- **Windows SSO** via `curl.exe --negotiate -u :` (current user, nothing stored), hardened the
  same way: **`--http1.1`** (avoids `http_code 000` on the big documents list), bounded
  `--connect-timeout`/`--max-time`, one `--retry`, `--compressed`, and **`CREATE_NO_WINDOW`** so the
  windowed exe never flashes a console. Basic (UPN) stays available via stdlib `urllib`.
- **`datev.config.json`** next to the exe ({`base_url`, `auth`, `user`, `password`, `verify_tls`})
  prefills the GUI; self-signed TLS is trusted only for a loopback host unless `verify_tls` says
  otherwise (same rule as OPOS). So an existing OPOS `datev.config.json` works here too.

## Build & run
```powershell
scripts\build_datev_probe.ps1        # → dist\DATEV-Probe.exe  (stdlib-only; no deps install)
```
Or from source: `.build_venv\Scripts\python.exe datev_probe.py`

In the GUI: enter the Base-URL (default `https://localhost:58452/datev/api/dms/v2`), keep
**Windows-Anmeldung (SSO)** selected (the default — authenticates as the current Windows user
via `curl.exe --negotiate`, exactly like DATEV's own programs; **no username/password needed**),
keep *self-signed TLS* on for localhost → **Verbinden / Info abrufen**. The program type
(DokAB/DokAbRev/DMS) and whether exchanges keep revisions are shown. Then load domains /
documents and inspect one document's file. Everything pulled is printed in the log.

> Runs on the DATEV workstation, where DATEVconnect listens on `localhost:58452`. SSO uses the
> bundled `curl.exe` (Windows 10+); switch to **Basic (Benutzer/Passwort)** (UPN form
> `user@domain.local`) only if SSO is unavailable.

## App integration (deferred — DATEV mode only): how a document finds itself
When BelegTool later gains the DATEV mode (a settings flag + a DATEV menu toggle; lazy-loaded so
a normal launch stays lean), the **provenance** for "update itself back to DATEV" does **not** need
a separate DATEV import API: when a document is opened from DATEV, **DATEV prefixes the temp file
name with the document id** (first characters). BelegTool captures that id when the file is handed
over → stores it on the node → on save it knows exactly which DATEV document to replace. This whole
path exists **only when DATEV mode is enabled**. (Conflict-safety on write still applies: DokAB has
no revisions, so an exchange overwrites — re-read `change_date_time` before writing; see the
concurrency notes.)
