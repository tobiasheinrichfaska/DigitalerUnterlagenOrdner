# Final Fix + Verification Report — DigitalerUnterlagenOrdner (BelegTool)

**Date:** 2026-06-16
**Scope:** Apply all findings from `2026-06-16_00-05-00_audit-report.md` (readability/structure),
one by one, tests before+after each, commit each — plus a test-integrity issue surfaced mid-work.
**Mode:** read→edit→verify; every layer run to completion this session (per the new
**Test-result integrity** workspace rule).

---

## Final full-suite gate (all five layers, captured)

| Layer | Command | Result |
|---|---|---|
| Python | `.build_venv/Scripts/python.exe -m pytest` | ✅ **514 passed** in 70 s (incl. office golden) |
| Frontend unit/component | `npm test` (vitest, vmThreads) | ✅ **287 passed / 31 files** |
| Frontend e2e | `npm run test:e2e` (Playwright, real Chromium) | ✅ **3 passed** |
| Lint | `npm run lint` (eslint) | ✅ **0 problems** |
| Web build | `npm run build` (vite) | ✅ built (index 412.6 kB / gzip 115.4 kB) |

Baseline was 498 Python / 281 frontend "passed" — but the frontend figure was **false**
(see I-1). Real frontend baseline was 274 passed / **7 failed**.

---

## Findings resolved

| # | Finding | Resolution | Commit |
|---|---|---|---|
| **C-1** | `archives.py` 58 % coverage | Added `tests/test_archive_extract_more.py` (12 tests) covering the TAR loop, eml html-body + extensionless-attachment inference + inline-image, and the full `.msg` path (stubbed `extract_msg.Message`). **58 % → 84 %**; suite 498 → 508. | `test(C-1)…` |
| **S-2** | `App.jsx` 25 `useState` in one orchestrator | Extracted `useSelection` / `useDialogs` / `useTagView` hooks (return the same names → behaviour-preserving); `useTagView` derived flags unit-tested. eslint clean. | `refactor(S-2)…` |
| **S-1** | `CoreApi` 58-method god-façade | Moved the **stateless** single-writer disk-I/O policy (`restore_from_bak`, `acquire_lock`, `write_through_lock`) to `infra/file_lock.py`; CoreApi delegates (−2 methods, smaller `_save_through_lock`). Now independently unit-tested (`test_lock_io.py`, 6 tests). **Deliberately did NOT move** the `_locks`/`_view_dirs` dict coordination — it runs inside `self._lock` critical sections shared with `_sessions`/`_paths`, so relocating it would change atomicity (concurrency risk > readability gain). | `refactor(S-1)+docs(D-1)…` |
| **D-1** | `core/api.py` flat 56-method list | Added `# --- section banners ---` grouping methods by responsibility (render/prefetch, config, file lock, open/lifecycle, mutations, rendering, save, export, compression+import, internals). Comments only, no reordering. | same commit |

---

## I-1 — Test-integrity finding (surfaced mid-work, highest priority)

**Symptom:** running `npm test` showed **7 failing** frontend tests (`StatusBar.test.jsx` 4,
`PreviewPane.test.jsx` 3), yet the prior audit and the initial audit this session reported the
frontend "281 passed".

**Root cause (confirmed):** those two files are the **only** ones using `vi.mock()`, and
`vi.mock()` does **not** take effect under the `vmThreads` Vitest pool. The project is forced
onto `vmThreads` because the `forks`/`threads` pools crash on this toolchain (vitest 4.1.8 +
Node 24 + Vite 8 → *"failed to find the current suite"*, 0 tests; verified — even vitest 4.1.9
and `singleFork`/`--no-isolate` don't fix it). Git history: the `vmThreads` workaround landed
2026-06-13; both `vi.mock` test files were added 2026-06-15 — so **they never passed once**.
The audits reported green by **inheriting the pass count instead of running the suite** (the
initial audit this session did the same — it stated the frontend was green "as of 2026-06-15,
source unchanged").

**Fix:**
1. **Workspace-wide rule** — new **"Test-result integrity"** section in
   `general stuff/CLAUDE.md` (git-tracked master) **and** the root mirror `c:\skripte\CLAUDE.md`:
   a layer is green only if its command ran to completion this session with a real pass/fail
   summary + zero exit; never inherit numbers; "collected ≠ passed"; a test that can't execute
   is a gap, not a pass; **run the whole suite after each fix, not subsets**; capture the
   summary. Memory saved.
2. **The 7 tests rewritten `vi.mock`-free** — `StatusBar` now drives the real `./lib/core` via a
   stubbed `window.pywebview.api` (a genuine integration test of activity tracking + stats
   polling); `PreviewPane` renders the real children and asserts on their root elements. The
   "no `vi.mock` here" constraint is documented in the project CLAUDE.md.

---

## Convention compliance (unchanged, still green)

`manual_tests/` (01–08, React UI) · `docs/data-model.html` · Known Limitations · logic/UI
separation · `.gitattributes` LF · `FEATURES_REQUIRED.md` · CLAUDE.md back-link + listing —
all present. Version `version_info.VERSION = 3.9.3`.

---

## Commits (branch `fix/2026-06-16-audit-readability-structure`)

1. `docs:` add 2026-06-16 readability/structure audit report
2. `test(C-1):` cover archives.py tar/eml/msg extraction paths
3. `refactor(S-2):` extract useSelection/useDialogs/useTagView hooks from App.jsx
4. `test(webui):` make StatusBar/PreviewPane tests vi.mock-free (were silently red)
5. `refactor(S-1)+docs(D-1):` extract file-lock disk-I/O from CoreApi; section-banner the façade
6. (workspace repo `general stuff`) `docs:` add Test-result integrity rule

No Critical/High code findings remained open. All five test layers green with captured summaries.
