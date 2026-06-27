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
1. **Read (this build).** Govern each retrieval from the GUI: connect → `info` (feature) →
   `domains` → `documents` (filter + max) → one document's structure-items → its file.
   Read-only; safe.
2. **Write (next).** *Create* a NEW throwaway test document (single file) and **save its id**;
   then *exchange* that file — **only on the self-created id**, behind an explicit confirm —
   to observe overwrite-vs-revision on this install. Never touches a real client document.

## Safety
- Round 1 is read-only.
- Round 2 will only ever create and then modify a document **it created in the same run** (the
  saved id); a real client document is never written. The exchange step is confirm-gated.

## Architecture (BelegTool, Python)
| File | Role |
|---|---|
| `datev/types.py` | `DatevConfig`, injected `Transport`, errors, `program_keeps_revisions` (DokAB ⇒ overwrite) |
| `datev/endpoints.py` | data-driven DMS v2 endpoint catalog (read) + `build_url` |
| `datev/transport.py` | stdlib `urllib` transport (Basic auth header from the client; self-signed-TLS tolerant). SSO/Negotiate later. |
| `datev/client.py` | `DatevConnectClient` — `get_info` / `list_domains` / `list_documents` / `get_document` / `list_structure_items` / `get_document_file`; maps 401 → `DatevAuthError`, license envelope → `DatevLicenseError` |
| `datev/probe_gui.py` | Tkinter governing GUI — every retrieval is an explicit, logged button |
| `datev_probe.py` | one-file exe entry point |
| `tests/test_datev_client.py` | unit tests with a fake transport (no live DATEV): feature, reads, query/path building, Basic auth, error mapping |

## Build & run
```powershell
scripts\build_datev_probe.ps1        # → dist\DATEV-Probe.exe  (stdlib-only; no deps install)
```
Or from source: `.build_venv\Scripts\python.exe datev_probe.py`

In the GUI: enter the Base-URL (default `https://localhost:58452/datev/api/dms/v2`), the UPN
user + password (Basic; UPN form `user@domain.local`), keep *self-signed TLS* on for
localhost → **Verbinden / Info abrufen**. The program type (DokAB/DokAbRev/DMS) and whether
exchanges keep revisions are shown. Then load domains / documents and inspect one document's
file. Everything pulled is printed in the log.

> Runs on (or with line-of-sight to) the DATEV workstation, where DATEVconnect listens on
> `localhost:58452`. SSO is not yet implemented — use Basic (UPN) for now.
