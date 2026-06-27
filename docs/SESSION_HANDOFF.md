# Session handoff — v3.10.0 (quick-wins shipped + in-app DATEV gate)

**Repo:** `c:\skripte\public\DigitalerUnterlagenOrdner` · **Branch:** `feat/v3.10-quickwins`
**Version:** bumped to **3.10.0** (was 3.9.5) · **Remote:**
github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner

## Goal
Ship **v3.10.0** = the quick-wins (done) + the **in-app DATEV integration** (the main
remaining build), then release. **Austausch-Pad #5A is cut** from v3.10 (not built,
doesn't block; #5B/#5C remain logged for later).

## Quick-wins — DONE on this branch
#1 Office golden test · #2 toolbar icon-only redesign · #3 Save split-button · #4 rotate
order · #7 multi-select tagging · #8 „Neuer Ordner" at selection + dialog · #9 zoom keeps
document position · #10 reusable accessible menu hook · #12 nested archive/mail extraction +
subfolders · #13 configurable export split. Plus the PDF-Tool text editor (FreeText/typewriter
+ AcroForm fill, round-trips editable) — covers #6.
**Cut/deferred:** #5A Austausch-Pad (cut from v3.10); #11 error-code contract (deferred,
`lib/messages.js` covers it).

## The main build: in-app DATEV mode
Research is **complete and live-verified** (Kanzlei box `DatevHeinrich`, `feature = DokAb`)
via the standalone probe (`datev/` package + `dist/DATEV-Probe.exe`). The `datev/` package is
reusable, pure-ish, and unit-tested — the in-app feature **imports from it; do not rewrite the
client**. The probe exe is research tooling and is **not shipped** in the BelegTool release.

**Proven on the live box (feature=DokAb):** SSO connect (port-58452 gateway), read, create,
in-place exchange (`PUT …/structure-items/{sid}` → 204, overwrite, no revision), delete,
provenance via checkout path `…\<doc-guid>\<file-id>`, `change_date_time` advances on every
write (trustworthy guard), `structure_item.id` stable across exchanges (cache it;
`document_file_id` changes per version).

### Reusable building blocks already in the repo (all tested)
- `datev/client.py` — `DatevConnectClient`: info/domains/documents/files/structure,
  `resolve_client_guid`, `list_users` (SCIM), `list_document_states`, `upload_document_file`
  (coerces id→int), `create_document`, `update_structure_item`, `delete_document`,
  `get_document_raw`.
- `datev/transport.py` — hardened curl SSO (file-body Negotiate replay, `Expect:` off,
  pipe-free `Popen` + kill, header/Location capture).
- `datev/config.py` — `dms_base_url` / `master_data_base_url` / `iam_base_url` / auth.
- `datev/provenance.py` — `parse_checkout_path` (exact), `provenance_stats`/`match_entries`.
- `datev/writeback.py` — pure guard, 8 tests: `decide_save_back(...)` →
  `ok|declined|locked|conflict_changed|conflict_content`; `is_connected`/`can_write_back`/
  `can_file_to_datev`.

### Authoritative design docs
- `docs/datev-integration-design.md` — open/save/Save-As/file-anew flow + state model.
- `docs/datev-dokumentenablage-recipe.md` — connect/CRUD.
- `docs/datev-provenance.md` — provenance.
- `import/` = vendor OpenAPI specs, **gitignored, never commit**.

## Build plan for the in-app gate (DATEV-mode only, lazy-loaded)
- **Setting + toggle:** persisted app flag `datev_mode` in `%APPDATA%\…\settings.json`
  (sibling of `window.json`) + a „DATEV" menu button that flips it. When off, never import
  `datev` → normal launch stays lean. Optionally store the DMS base URL (default
  `https://localhost:58452/datev/api/dms/v2`).
- **Lazy load:** import the `datev` package only when `datev_mode` is on (in host/CoreApi);
  expose DATEV ops on HostApi.
- **On open (DATEV mode):** `parse_checkout_path(path)`; if `{doc_guid, file_id}` → store
  provenance on the node (+ cache opened bytes' SHA-256, GET `change_date_time` + `checked_out`);
  if checked out, tell the user now. Show a "from DATEV" badge. Persist provenance on the node
  (round-trips in `.belegtool`).
- **On save:** if `can_write_back` → ask „nach DATEV zurückschreiben? Ja/Nein" → on Ja, re-read
  server now and `decide_save_back` (not checked out, `change_date_time` unchanged vs baseline,
  server-bytes == opened-original); `ok` → back up fetched server bytes locally, then
  `upload_document_file` → `update_structure_item`; any non-ok → message + filesystem save.
- **Save As** → clear provenance (`is_connected` → false). Not-connected file → offer „nach
  DATEV ablegen" = the create flow (Mandant via `resolve_client_guid` + domain/folder/register
  + user via SID match, no state for class 1), then adopt the new provenance.
- **Tests:** pure logic is covered; add host/integration tests for the open-path capture + the
  save dispatch (mock the datev client). Manual test: new `manual_tests/10_datev.md`.

## Release checklist for v3.10.0
1. Build & wire the DATEV gate (above).
2. Run **ALL FIVE** test layers (workspace gate, no inherited numbers): `pytest` (incl. office
   golden + datev tests) · `npm run lint` · `npm run test:all` (vitest + Playwright Chromium
   e2e) · `npm run build`. Paste real tails.
3. CLAUDE.md: mark v3.10 items shipped (+ DATEV section), cut #5A, refresh Known Limitations &
   Current tag.
4. Bump `version_info.py` → 3.10.0; update version in `BETA_TESTING.md` + bug-report form.
5. `manual_tests/` current (PDF-Tool `09_…` exists; add `10_datev.md`).
6. Merge `feat/v3.10-quickwins` → `master`; `build.ps1` (clean onedir); smoke-launch
   `dist\BelegTool\BelegTool.exe`.
7. Tag `v3.10.0`, push `--tags`, publish Release (`gh release … --latest`).

## Housekeeping
- Delete productive DATEV test docs (real Sperlingweg data):
  `fa89ad42-8cd4-4828-8234-143161d41985`, `6025044c-2b39-4fd3-92e3-42d9a87854fc`
  (+ check the DATEV desktop for earlier „ZZZ TEST" strays) via the probe's
  „Dokument löschen (DELETE)".
- Optional: embed the Windows version resource in `BelegTool.exe` (noted in CLAUDE.md
  build-hygiene).
