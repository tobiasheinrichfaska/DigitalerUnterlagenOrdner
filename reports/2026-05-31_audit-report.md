# Audit Report — DigitalerUnterlagenOrdner (BelegTool) v3.5.3

Audit date: 2026-05-31
Auditor: Claude Opus (audit skill)
Scope: All Python modules at repo root + `tests/` tree. Project: Python/Tkinter desktop PDF manager (Windows). Entry point `belegtool_main.py`.

> **Note:** A prior `AUDIT_REPORT.md` (2026-05-27) exists at the repo root. The majority of its bug findings have since been fixed in the current code (see "Previously-flagged, now fixed" below). That stale file should be archived or deleted to avoid confusion. This report reflects the **current** state of the codebase.

---

## Pre-flight checks

| Check | Result |
|---|---|
| FEATURES_REQUIRED.md present | **No** — file absent at root and `docs/`. Critical user paths are not formally defined. |
| Test framework | pytest (33 test files, `pytest.ini` present) |
| Test run | `python -m pytest -q` (rogue script excluded): **21 failed, 80 passed, 8 skipped** in ~250 s. Root cause identified — see Finding 0. |
| Lint config | None (no flake8/ruff/black config in repo) |
| Build | `build.ps1` → PyInstaller onedir; not executed in this audit (no behavioural change made) |
| Secrets scan | No hardcoded credentials/API keys found. License email is intentional public contact. |

---

## Findings

| # | Category | Severity | Finding | Location | Suggestion |
|---|---|---|---|---|---|
| 0 | Test Suite / Runtime | **Critical** | **21 of 109 tests fail.** Missing fixture `tests/data/input/sample.pdf` (referenced by `create_valid_pdf`) forces the blank-page fallback. Blank PDFs never compress smaller than the original, so `compress_all_methods` returns `{}` → `is_compressed` stays `False` and `dpi_current` stays `None`. This breaks (a) all `assert node.is_compressed` tests and (b) every `wait_for_real_preview`/`wait_for_ready` helper, which then raise `TimeoutError: Vorschau...` after 20 s. The suite is effectively red and slow. | `tests/helpers.py:11-35, 42-86`; failing: `test_pdf_storage_additional.py::test_compress_all`, `test_pdf_node_compression.py::test_pdf_compression_loop`, `test_pdf_node_split.py`, `test_pdf_node_merge_files.py`, `test_lazy_preview.py`, `test_view_preview.py::test_reset_compression`, +others | Commit a real multi-page `tests/data/input/sample.pdf` (scanned content that actually compresses), OR change the fallback to produce a compressible PDF, OR relax assertions/waits to tolerate "compression yielded no smaller result". Pick one and make the suite green. |
| 1 | Test Coverage / Hygiene | High | `test_pdf_node_merge_dpi_conflict_lazy.py` is a **module-level script**, not a pytest test. It runs at collection time: renders/compresses PDFs, `time.sleep` up to 2 s, and **writes two PDF files into the CWD** (`merge_dpi_conflict_a.pdf`, `_compressed.pdf`). No assertions → zero verification value, pollutes the repo root and slows every test run. | `tests/test_pdf_node_merge_dpi_conflict_lazy.py:26-62` | Convert to a real `def test_*()` using a tmp_path fixture and assertions, or delete it. |
| 2 | Test Coverage | Medium | `test_compress_pdf_bytes.py` is a no-op smoke test: it accepts `None` as a valid result and wraps the call in bare `try/except`. Provides essentially no regression protection for the core compression entry point. | `tests/test_compress_pdf_bytes.py:3-9` | Assert on a real multi-page PDF: result is `bytes`, starts with `%PDF`, and `len(result) <= len(input)`. |
| 3 | Dead Code | Medium | `_ctx_compress`, `_ctx_commit`, `_ctx_reset_compression` are defined but **never wired** into the tree context menu. The corresponding user actions (Komprimieren / Lesbarkeit geprüft / Kompression zurücksetzen) are therefore unreachable from the TreeView — only available via the preview-panel slider/buttons. | `view_tree.py:231-244` (context menu built at `:70-87`) | Either add the menu entries or remove the dead handler methods. Confirm the intended UX. |
| 4 | Security (privacy) | Medium | Email attachments are dispatched to a converter **by filename extension only** (`get_supported_extensions`), with content validated solely by `%PDF` header after conversion. An EXE/JS/HTML masquerading as a benign type silently degrades to "nicht importierbar" rather than warning the user. Low exploitability (libs handle untrusted input) but worth a user-facing note. | `universal_importer.py:127-129, 519-524` | Surface "could not import / unexpected type" more visibly; consider magic-byte sniffing for the common cases. |
| 5 | Error Handling | Medium | 74 broad `except Exception` blocks across the codebase. Several swallow the cause silently (e.g. `view_preview.py:238-241` slider state, `_split_pdf` per-page `:949-950`, `compress_all_methods` conflates "failed" vs "didn't help"). Makes field debugging hard, especially with logging off by default. | repo-wide; hotspots `pdf_node.py`, `compress_pdf_bytes.py:82-83`, `view_preview.py` | Narrow except clauses where the failure mode is known; always `logger.warning`/`debug` the exception. |
| 6 | Performance | Low | `_get_iid_for_node` and `_apply_gui_move_plan` do O(n) linear scans of `nodes_by_id` for every reverse lookup (node→iid and uid→node). For large trees and bulk moves this is O(n²). | `view_tree.py:350-368, 428-432` | Maintain a reverse `node→iid` / `uid→iid` dict updated on insert/delete. |
| 7 | Data Integrity | Low | `_concat_two_pdfs` / `_export_nodes_to_bytes` use `PdfWriter.add_page`, which drops named destinations, inter-page link annotations and outlines from source PDFs. Fine for image-only receipts, lossy for text PDFs from upstream tools. No warning logged. | `pdf_node.py:489-497`, `toc_export.py:88-110` | Document the limitation; or use pikepdf page copy when source has annotations. |
| 8 | Consistency / Semantics | Low | DPI-conflict merge path: after wiping `current_pdf_data`/`dpi_current` and setting `no_compression=True`, the code re-concatenates and recomputes flags. The guard at `:546` correctly keeps `dpi_current=None` on conflict, but `is_compressed` can still end up `True` via `self.is_compressed and other.is_compressed` while `no_compression=True` — a "not to be compressed" + "is compressed" combo. | `pdf_node.py:524-549` | Force `is_compressed=False` whenever `no_compression` is set in the conflict branch; add a test asserting the post-merge flag combination. |
| 9 | Repo Hygiene | Low | Build/dev artifacts sit in the (now public) repo root: `pdf_tool.log`, `debug_invalid_preview.pdf`, `merge_dpi_conflict_a*.pdf`, `.coverage`, `__pycache__/`, `.pytest_cache/`. `.gitignore` covers their patterns, but the working tree is cluttered and `diagnose_msg.py` (a stray dev script) ships at root. | repo root | Delete generated artifacts; move `diagnose_msg.py` into a `tools/`/`scripts/` dir or exclude it. Verify none are git-tracked. |
| 10 | Documentation / Process | Low | No `FEATURES_REQUIRED.md` defining critical user paths (import → tree edit → compress → save/export). The audit cannot mechanically validate feature completeness without it. | repo root | Add `FEATURES_REQUIRED.md` listing the critical flows so future audits can verify them. |
| 11 | UX | Low | `set_busy()` calls `self.focus_force()` on every busy-state toggle (incl. background task start/stop), which can steal focus mid-interaction. | `belegtool_main.py:223` | Only force focus on explicit user-initiated transitions, not background task churn. |
| 12 | Robustness | Low | `_split_pdf` waits on the preview event with `self._preview_done.wait(timeout=30)` and proceeds silently on timeout against possibly-stale preview state. | `pdf_node.py:930` | Log a warning on timeout; consider surfacing it to the user. |

---

## Previously-flagged, now FIXED (verification of prior 2026-05-27 audit)

The current code already resolves the most serious items from the older report:

- **`no_compression` honored in all compress entry points** — `compress_selected` (`panel_controls.py:454,458`) and `pdf_storage.compress` (`pdf_storage.py:141`) now both guard on `not node.no_compression`. ✓
- **`is_compressed` restored from disk** — `_parse_node` now reads it back (`pdf_storage.py:376`) instead of hard-resetting to False. ✓
- **xhtml2pdf remote-fetch / tracking-pixel hole closed** — `_block_remote_link` callback blocks `http(s)://` and `//` URIs (`universal_importer.py:240-261`). ✓
- **Archive zip-bomb guards added** — member-count (500) and uncompressed-size (500 MB) limits for ZIP and TAR (`universal_importer.py:404-434, 468-478`). ✓
- **Office COM hardening** — `AutomationSecurity = 3` set before opening Word/Excel/PPT; temp output now uses `tempfile.mkdtemp` with guaranteed cleanup, not a predictable `%TEMP%` path (`universal_importer.py:307-349`). ✓
- **Central `CompressionConfig` dataclass** — magic numbers (DPI, JPEG quality, PNG level, A4 width, colorspace, methods) centralized (`compress_pdf_bytes.py:11-39`). ✓
- **`compress()` now multi-method** — uses `compress_all_methods` and picks the smallest result, instead of JPG-only (`pdf_node.py:360-386`). ✓
- **`sanitize_pdf` is a real pikepdf repair** — opens with `suppress_warnings` and round-trips, no longer a no-op (`tools.py:7-37`). ✓
- **`compress_lazy` race fixed** — `_compression_task_running` now set under `_compression_task_lock` (`pdf_node.py:280-284`). ✓
- **`compress_pdf_bytes` docstring/behavior aligned** — now genuinely returns the smaller of re-encoded vs. original (`compress_pdf_bytes.py:42-55`). ✓

---

## Summary

### Findings by severity
- Critical: 1 (test suite is red — 21/109 failing due to a missing fixture)
- High: 1 (collection-time script masquerading as a test)
- Medium: 4 (no-op test, dead context-menu handlers, ext-only import dispatch, broad excepts)
- Low: 7

### Top 3 high/medium-priority fixes
1. **Restore the test suite to green (Finding 0)** — add `tests/data/input/sample.pdf` (or fix the fallback / waits). Right now 21 tests fail and each timeout burns 20 s, making the suite both red and ~4 min long.
2. **Fix the fake test** `test_pdf_node_merge_dpi_conflict_lazy.py` (Finding 1) — it writes files to CWD at collection time and has zero assertions.
3. **Wire up or remove the dead context-menu handlers** (Finding 3) — Komprimieren/Commit/Reset are unreachable from the tree; a real UX gap, not just dead code.

### Top 2 architectural improvements
1. **Reverse-index the TreeView node↔iid mapping** (Finding 6) to remove O(n²) lookups during bulk moves and GUI plan application.
2. **Unify the three per-node threading state machines** (preview vs. `compress_lazy` vs. `compress_multi_lazy`) under coordinated locking — they currently share node state without cross-coordination, a latent race source.

### Quick wins
- Delete/archive the stale root `AUDIT_REPORT.md` and the generated artifact files (`*.log`, `debug_*.pdf`, `merge_dpi_conflict_*.pdf`, `.coverage`).
- Add `FEATURES_REQUIRED.md` to enable future feature-completeness validation.
- Add a `logger.warning` to the `_split_pdf` 30 s timeout path.
- Move `diagnose_msg.py` out of the package root.

### Pre-flight status
- Build: not run (no code changes made).
- Lint: no linter configured.
- Tests: **21 failed, 80 passed, 8 skipped** (rogue script excluded). Dominant root cause is the missing `tests/data/input/sample.pdf` fixture (Finding 0), not a product-logic regression — but the suite is red as-is.
- Data model: `PDFNode` serialization (`to_dict`/`_parse_node`) round-trips `name, is_folder, status, vz_start/end, pdf_length, is_compressed, dpi_original, dpi_current, no_compression, children` — schema is internally consistent.
