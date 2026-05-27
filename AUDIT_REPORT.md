# Audit Report — DigitalerUnterlagenOrdner (BelegTool) v3.5.3

> **Note on naming.** The request referenced "DigitalerBelegOrdner". No project exists under that name in `c:\skripte\`. The matching project is `c:\skripte\private\DigitalerUnterlagenOrdner` (a.k.a. BelegTool, entry point `belegtool_main.py`). This audit covers that codebase.

Audit date: 2026-05-27
Scope: all Python modules at the repo root plus the `tests/` tree. Focus areas: compression infrastructure, split/merge file handling, `no_compression` tag, code quality, security.

---

## 1. Current compression infrastructure

### 1.1 Methods

All compression flows funnel through `compress_pdf_bytes.py`. There are three "methods", but only two are user-selectable in the UI dropdown today:

| Key | Pipeline | Lossy? | Color | Where it lives |
|-----|----------|--------|-------|----------------|
| `"jpg"` | fitz render → PIL grayscale → JPEG quality=60 → embed in new pikepdf-like page → pypdf re-encode | yes | grayscale only (`fitz.csGRAY`) | `compress_pdf_bytes.py:42-84` |
| `"png"` | fitz render → PIL grayscale → PNG `compress_level=6` → embed → pypdf re-encode | no (re-quantized to 8-bit gray) | grayscale only | `compress_pdf_bytes.py:42-84` |
| `"pikepdf"` | `pikepdf.save(compress_streams=True, recompress_flate=True)` — pure structural | no | preserved | `compress_pdf_bytes.py:101-110` |

Public entry points:

- `compress_pdf_bytes(input_bytes, dpi=150, method="jpg")` — single-method (`compress_pdf_bytes.py:9-13`). Note: the docstring says "Returns the smaller result" but the function does **not** compare against the input; it always returns the re-encoded render.
- `compress_all_methods(input_bytes, dpi=150)` — runs `jpg`, `png`, and `pikepdf`, filters out any larger-than-input result, and returns a dict sorted smallest-first (`compress_pdf_bytes.py:16-39`).
- `recompress_with_pikepdf(input_bytes)` — direct call to the structural path.
- `reencode_pdf_structure(pdf_bytes)` — pypdf rewrite, no compression options.

A second silent compression path lives in `pdf_storage.py:253-269`: when saving a `.belegtool` file, the writer-built PDF is re-saved through pikepdf with `compress_streams=True, recompress_flate=True, linearize=True`. This is keep-the-smaller logic and applies to the *envelope* PDF (not individual nodes).

### 1.2 Configuration knobs (what the user / dev can actually tune)

| Knob | Default | Range | Location |
|------|---------|-------|----------|
| DPI (UI slider) | `dpi_current` or 150 | 50 – `dpi_original`, else 350 | `view_preview.py:40, 355` |
| Lazy compress DPI on import | 150 | hard-coded | `pdf_storage.py:128` |
| Auto-compress on creation | 120 | hard-coded `_compression_task_dpi` default | `pdf_node.py:35, 268, 297, 356` |
| JPEG quality | 60 | hard-coded | `compress_pdf_bytes.py:67` |
| PNG `compress_level` | 6 | hard-coded | `compress_pdf_bytes.py:69` |
| A4 downscale threshold | 595 pt (A4 width) | hard-coded | `compress_pdf_bytes.py:44, 52` |
| Preview render DPI | 100 | hard-coded | `pdf_node.py:153` |
| Colorspace | `fitz.csGRAY` | hard-coded | `compress_pdf_bytes.py:62` |
| `pikepdf` save options | streams+flate (+ linearize on save) | hard-coded | `compress_pdf_bytes.py:106`, `pdf_storage.py:257-262` |

**There is no central config object, no `config.txt` for runtime knobs, no env-var overrides.** The lone `config.txt` at repo root is an InnoSetup installer stub, unrelated.

### 1.3 Flow / orchestration

- `PDFNode.compress(dpi)` — synchronous single-method (JPG path), used by the toolbar "compress" action (`panel_controls.py:454-459`) and by `_on_slider_changed` (`view_preview.py:342`). Always picks JPG; no method comparison.
- `PDFNode.compress_lazy(dpi)` — async wrapper around `compress` (still JPG-only).
- `PDFNode.compress_multi_lazy(dpi)` — async wrapper around `compress_all_methods`; populates `_compression_results`, sets `current_pdf_data` to the smallest result. **This is the only place all three methods are tried.**
- `PDFNode.select_compression_method(method)` — switches `current_pdf_data` to a previously computed result, without re-rendering.

The UI uses `compress_multi_lazy` from the DPI slider release (`view_preview.py:467`), the reset-compression button (`view_preview.py:384`), the auto-kick-off path (`view_preview.py:308`), and the data-load path (`pdf_node.py:819`). But `panel_controls.compress_selected()` (`panel_controls.py:454-459`) and `pdf_storage.compress()` (`pdf_storage.py:135-142`) call **`compress()`** — JPG-only, single-method, no comparison.

### 1.4 Documentation coverage

- `CLAUDE.md` documents the existence of three methods and the "pick best" behavior at a high level.
- `Briefing UI Design Update.md` §4 documents the UI strings and dropdown format.
- Method-level docstrings exist but are sparse: `compress_pdf_bytes` doesn't document its method choices, doesn't list valid `method` values, and contradicts itself ("Returns the smaller result" vs actual behavior).
- The pikepdf branch in `_render_pdf_as_images` raising `ValueError("Unbekannte Komprimierungsmethode")` (line 71) means a future caller passing `method="pikepdf"` would crash here even though `"pikepdf"` is a legitimate method key elsewhere.
- No documentation on **why** grayscale-only, **why** JPEG q=60, or how to add a new method.

---

## 2. Issues with split/merge file handling

### 2.1 Split correctly marks nodes as uncompressed — but only via `no_compression=True`

`_split_pdf` at `pdf_node.py:887-957` sets `no_compression=True` on every produced page node (lines 929, 951). It then copies `dpi_original` / `dpi_current` over to each split. The intent is "do not lazily re-compress page slices, they came out of an already-compressed document".

The constructor `set_original_and_current_data` (`pdf_node.py:778-828`) has a guard:

```python
should_lazy_compress = (
    original_data and
    current_data is None and
    dpi_original is None and
    dpi_current is None and
    not no_compression       # ← this is what split relies on
)
```

So `no_compression=True` correctly suppresses the lazy compression task. **However**:

- `is_compressed` on a split node is left at its initial `False` (see `PDFNode.__init__`, `pdf_node.py:55`). Yet `test_split_preserves_previews.py:43` asserts `split_node.is_compressed is True`. That test passes only because `set_original_and_current_data` flips `is_compressed = True` *when current_data is set* (`pdf_node.py:826`). If the original was uncompressed and `current_data` is None (a node was never compressed), the split would produce `is_compressed=False`, even though `no_compression=True` is set. That's correct, but the test only covers the compressed-input case.
- `is_compressed` and `no_compression` model **two different facts** but the code sometimes treats them as proxies. A split node carries `no_compression=True` regardless of whether the source was ever compressed — losing the "was once an original" information.

### 2.2 Split: the first node mutates `self` in-place (lines 944-955)

After producing all page nodes, the first one is *replaced into self* by calling `set_original_and_current_data` on `self` with values pulled from the freshly-built `first` node, then `self._original_preview_pages = first._original_preview_pages`. This means:

- The original `self.children` (if any — not possible for a leaf, but the abstraction is muddy) and any external references that distinguished `self` from a fresh page-1 node are silently merged.
- `no_compression=True` is force-set on `self` as part of the swap (line 951). **This is correct for the split contract but undocumented** — anyone reading the public `split()` docstring wouldn't expect the source node to flip its own `no_compression` flag.

### 2.3 Merge: `_merge_pdf` DPI-conflict handling is asymmetric (lines 496-528)

```python
dpi_orig_set = {self.dpi_original, other.dpi_original} - {None}
dpi_curr_set = {self.dpi_current, other.dpi_current} - {None}
dpi_conflict = len(dpi_orig_set) > 1 or len(dpi_curr_set) > 1

if dpi_conflict:
    self.current_pdf_data = None
    self.dpi_current = None
    self.no_compression = True
```

When two nodes with different compressed DPIs are merged, `self.no_compression = True` is set — but **only on conflict**. In the non-conflict path:

```python
self.no_compression = self.no_compression or other.no_compression   # line 524
```

So `no_compression` propagates as OR. That means merging a "never compress" node with a normal node *will* keep `no_compression=True`. **However**, lines 525-526 then re-compute DPI as the max of both nodes — leaving a node with `no_compression=True` *and* non-None `dpi_current` set. That combination is semantically inconsistent ("I'm not to be compressed" + "but I have an active compression DPI"). The UI partially copes (`view_preview.py:358` hides the slider when `no_compression`) but `is_compressed` may stay `True` from `self.is_compressed and other.is_compressed` (line 523).

### 2.4 Merge: `is_compressed` and DPI propagation are duplicated and inconsistent

Lines 510-526 are reached even *after* a DPI conflict has wiped `current_pdf_data` and `dpi_current` (lines 510-512). Then line 526 sets `dpi_current` back to the max of `self.dpi_current` (now None) and `other.dpi_current` — which is non-None. So a DPI-conflict merge ends with `current_pdf_data=None`, `no_compression=True`, but `dpi_current` rebuilt from the other side. Net result: the "wipe the compressed side" is partially undone three lines later.

### 2.5 `_concat_two_pdfs` re-uses pypdf and silently drops outline/annotations (lines 473-482)

`PdfWriter.add_page` doesn't carry over named destinations, link annotations between pages, or outline entries. This is fine for image-only PDFs but loses information for text-PDFs from upstream tools. No warning is logged.

### 2.6 Merge: no compression-method preservation

When a merge happens, `_compression_results` from each side is lost; only the concatenated `current_pdf_data` is kept. After a merge, the dropdown in the preview panel won't show alternatives until the user re-triggers compression. (The compress-on-merge fallback at `panel_controls.py:330-331` uses `compress_lazy` — JPG-only — not `compress_multi_lazy`, so the multi-method dropdown stays empty.)

### 2.7 `commit_changes` always forces `no_compression = True` (pdf_node.py:562)

Once a user clicks "Lesbarkeit geprüft", the node is permanently flagged "do not compress again". This is intentional (the user told us this is the final size). But the side-effect: a subsequent merge of two committed nodes carries `no_compression=True` forward via the OR-rule, propagating the flag to the merged result even when one side might still be compressible. This compounds rather than letting the merged document re-evaluate.

### 2.8 Folder merge calls `preview_lazy` on the parent (line 494) but does not propagate `no_compression`

`_merge_folder` only re-parents children. It does not reconcile `no_compression` flags on the folder itself (folders ignore `no_compression` for their own data, but a tooltip/UI that surfaced it for folders would mislead).

---

## 3. `no_compression` tag — usage and gaps

### 3.1 Where it is set to `True`

| Location | Trigger | Rationale |
|---|---|---|
| `pdf_node.py:512` | DPI conflict during PDF merge | Source dpi_current sets differ → can't pick one. |
| `pdf_node.py:524` | OR propagation in PDF merge | If either side had no_compression. |
| `pdf_node.py:562` | `commit_changes()` | User accepted current as final original. |
| `pdf_node.py:929, 951` | `_split_pdf` (every produced node + self) | Split slices inherit "do not re-compress". |
| `view_preview.py:125, 334, 458` | UI: commit button / slider at max / slider release at max | User asked for "∞ DPI" → keep original. |

### 3.2 Where it is set to `False`

| Location | Trigger |
|---|---|
| `view_preview.py:340, 377, 464` | User dragged slider below max OR clicked "Kompression wieder erlauben" reset button |

### 3.3 Where it is *read*

| Location | Effect when True |
|---|---|
| `pdf_node.py:414` | `rotate()` skips automatic `compress_lazy` after rotation. |
| `pdf_node.py:814` | `set_original_and_current_data` skips lazy compression. |
| `pdf_storage.py:126` | `_load_pdf` single-file branch skips `compress_lazy(150)`. |
| `panel_controls.py:268` | Merge warns the user before merging a `no_compression` node. |
| `panel_controls.py:330` | Post-merge auto-compress is skipped. |
| `view_preview.py:196` | "True original" marker (red border + red title) is shown only when `dpi_original is None AND not no_compression`. |
| `view_preview.py:303` | Auto-kickoff of multi-method compression is gated on this. |
| `view_preview.py:358` | Slider hidden, "Kompression wieder erlauben" button shown. |
| `view_preview.py:438` | Hover-tooltip on slider suppressed. |
| `tests/helpers.py:53` | Test wait loop ignores compression state for no_compression nodes. |

### 3.4 Gaps and inconsistencies

1. **Persistence works in both directions but the schema isn't symmetric.** `to_dict` writes `no_compression` (line 444), and `_parse_node` reads it back (line 367). Good. But `_parse_node` then unconditionally sets `node.is_compressed = False` two lines later (line 369), regardless of what the JSON said about `is_compressed` (which *is* persisted, line 441, but ignored on load). So a saved-then-reloaded compressed node loses its `is_compressed` flag, which means the TreeView (`view_tree.py:339`) renders it as "light" (uncompressed) after reload.
2. **No `no_compression` flag on folder merge bubble-up.** `_merge_folder` (line 484) doesn't touch `no_compression`. Whether that's correct depends on interpretation — folders have no own PDF data — but a folder containing a `no_compression` child still allows `panel_controls.compress_selected()` (line 454) to *compress* sibling leaves under it without warning. The merge precondition warning (line 268) only fires at merge time, not at "compress" time.
3. **`commit_changes()` recursively no-ops on folders** (lines 536-539). A folder with mixed children may have its leaf children flipped to `no_compression=True` via recursion. This is documented in the controller dialog ("Dies betrifft ggf. alle enthaltenen Unterknoten.") but not in the docstring.
4. **`reset_compression()` does not touch `no_compression`** (lines 570-581). So if a node is `no_compression=True` (from commit or from split), `reset_compression()` clears `current_pdf_data` and `is_compressed` but leaves the "no compression" gate intact. The user-visible difference: the slider stays hidden, the reset button stays visible. This is probably the intended behavior, but it's not in any docstring or test.
5. **Split sets `no_compression=True` even when the source had `no_compression=False`.** This is a deliberate over-cautious choice (split slices come from an already-compressed parent), but it means a split-then-reset cycle can't recover the parent's compression because the slices were pre-flagged.
6. **The `compress` (synchronous) path does not check `no_compression`.** `panel_controls.compress_selected()` walks `get_all_nodes()` and calls `subnode.compress()` if `not subnode.is_compressed` (line 454). It does **not** check `subnode.no_compression`. A user who explicitly opted out via "Lesbarkeit geprüft" or slider=∞ will still get compressed by the menu-driven "compress" action. **This is a bug.**
7. **`pdf_storage.compress()` has the same flaw** (line 138): `if not node.is_folder and not node.is_compressed:` — no `no_compression` guard.
8. **No `no_compression` flag exists for archives or imports.** `extract_zip_to_structure` / `extract_email_to_structure` / etc. produce nodes via `PDFNode.from_recursive_array`, which constructs nodes with default `no_compression=False`. They go through auto-compression. There's no "this came from a ZIP, don't re-render" hint, even though many ZIP-extracted PDFs are already optimally compressed.

---

## 4. Code quality concerns

### 4.1 Bugs

- **`pdf_storage._parse_node` discards persisted `is_compressed`** (`pdf_storage.py:369`): unconditional reset to `False` after `set_original_and_current_data`. Either drop the persisted field or honor it on load.
- **`compress_selected` and `pdf_storage.compress` ignore `no_compression`** (see §3.4-6/7).
- **`_split_pdf` `_preview_done.wait(timeout=30)`** (`pdf_node.py:901`) — silent timeout. If preview never completes, the split runs against possibly-stale preview state, and the user gets no warning.
- **Race in `compress_lazy`** (`pdf_node.py:268-293`): unlike `compress_multi_lazy`, this version checks `_compression_task_running` *without* its lock (`pdf_node.py:277`). Two simultaneous calls can both pass the check and start.
- **`pdf_node.py:813`**: `dpi_current is None` is in the `should_lazy_compress` predicate, but the predicate above (line 791) sets `self.dpi_current = dpi_current if current_data else None` *before* the check. If `current_data` was None and `dpi_current` was non-None, the predicate uses the parameter `dpi_current` (still non-None), not the just-assigned `self.dpi_current` (now None). Cosmetic — same outcome — but confusing.
- **`view_preview.py:44`**: `self.slider.bind("<Leave>", lambda e: self.slider_tooltip.place_forget())` references `self.slider_tooltip` before it is created (line 52). Tk lazily evaluates the lambda, so it works at runtime, but a re-order makes the intent clearer.
- **`view_preview.py:308`**: `node.compress_multi_lazy(dpi=node.dpi_current or 150)` after the busy check sets the DPI to the *current* value or 150. But `_compression_task_dpi` is the field actually consumed inside the run() closure (`pdf_node.py:318`) — the multi-lazy method copies the parameter into the field under the lock. OK, but worth noting that "first call after slider drag" can race the slider-released path that also calls `compress_multi_lazy(dpi=dpi)`.
- **`pdf_node.py:44`**: `pdf_data = pdf_data.getvalue()` — `BytesIO.getvalue()` on a `BytesIO` is fine, but `pdf_data` could be `None` already, and the `isinstance` check guards that case. Good. But `from_pdf` (line 86) accepts `bytes`/`str`/`BytesIO` and then passes through `sanitize_pdf` (line 99). The constructor path on lines 61-78 does *not* sanitize. So importing via `from_pdf` repairs broken PDFs; importing via `PDFNode(name=..., pdf_data=...)` does not.

### 4.2 Anti-patterns / smells

- **Mutable default-arg pattern avoided ✓**, but **wide bare `except Exception`** appears 76 times across the codebase. Highlights:
  - `pdf_node.py:170-173`, `pdf_node.py:898-899` (split swallows reader-construction errors silently), `pdf_node.py:920-921` (per-page silent skip), `pdf_node.py:939-940` (preview-copy fallthrough).
  - `compress_pdf_bytes.py:97`, `108`: log + return original. Means "compression failed" is indistinguishable from "compression didn't help" in the result dict.
  - `pdf_storage.py:88-89` falls back to plain PDF import on any error during structured import — could hide ZIP/TAR/EML corruption.
  - `view_preview.py:238-241`: `try: self.slider.config(state=state); except Exception: pass` — silently swallows tk errors during busy-state changes.
- **Module-level side effects in `tools.py:38-44`**: `PLACEHOLDER_PREVIEW` is built at import time and mutated with `_is_placeholder = True`. It's also returned (not copied) from `current_preview_images` (line 711). If any caller mutates it (e.g., resizes for display), the *singleton* mutates — and the `_is_placeholder` check in `commit_changes` (line 553) is the only thing keeping it from being stored as a real preview. The defensive check exists, but copy-on-return would be safer.
- **Circular/inline imports**: `pdf_node.py:710`, `:722`, `:739`, `:747` re-import `PLACEHOLDER_PREVIEW`/`PreviewPage`. `view_preview.py` re-imports `ImageDraw`/`ImageFont`/`messagebox`/`PreviewPage` repeatedly inside methods. Looks like remnants of a circular-import workaround; if so, the canonical pattern would be a one-time import at the top guarded by `TYPE_CHECKING`.
- **Duplicated import blocks in `tests/test_pdf_node_merge_files.py:1-49`**: the same imports + path setup are pasted three times.
- **Inconsistent threading-task locking**:
  - `compress_lazy` uses `_compression_task_running` as a plain bool with no lock (`pdf_node.py:277-281`).
  - `compress_multi_lazy` uses `_compression_task_lock`.
  - `preview_lazy` uses `_preview_task_lock`.
  - All three share state on the same node — they don't coordinate with each other.
- **Magic numbers** in `compress_pdf_bytes.py`: `A4_WIDTH_PT = 595.0` (only A4 — A3, Letter, Legal pages are silently re-scaled to A4 width), `quality=60`, `compress_level=6`, default `dpi=150`. None of these are tunable without code edits.
- **`tools.py:7-15` "no compression" sanitize**: silently rewrites the PDF only if it was *unreadable*. Most PDFs from import pass through unchanged, but the `except PdfReadError` path swallows the reason in a `logger.warning` and then *re-reads the same broken data* on line 25 — guaranteed to fail. The repair only ever produces output if `pypdf` is *non-deterministic* about the same input, which it isn't. Net effect: `sanitize_pdf` is essentially a no-op for any broken PDF. This is documented as "Reparatur" but doesn't actually repair anything.
- **`belegtool_main.py:223`**: `self.focus_force()` inside `set_busy()` — focus-stealing during background-task state changes can be jarring for users.
- **`belegtool_main.py:270`**: `os.startfile(LOGFILE)` after `mainloop()` returns — auto-opens the log file in the user's default editor at every exit when logging is enabled. Surprising but documented; not a bug.

### 4.3 Documentation gaps

- `compress_pdf_bytes.compress_pdf_bytes` — docstring contradicts implementation ("Returns the smaller result" — it doesn't compare).
- `compress_pdf_bytes._render_pdf_as_images` — docstring says "Renders every page as a greyscale image" but doesn't note A4-scaling, JPG quality, or the fact that landscape/A3 pages are silently squeezed.
- `PDFNode.split` — doesn't mention the silent `no_compression=True` side effect on `self` and all returned nodes.
- `PDFNode._merge_pdf` — doesn't mention DPI-conflict semantics or the `no_compression` OR rule.
- `PDFNode.commit_changes` — docstring says "Speichert den aktuellen Zustand als neuen Originalzustand", doesn't mention `no_compression=True` is set.
- No top-level architecture doc for the compression subsystem (CLAUDE.md is high-level only).
- `Briefing UI Design Update.md` references `Briefing Performance und Kompression.txt` (table §9) — that file does not exist in the repo.

### 4.4 Tests

- 31 test files; broad coverage of merge/split/copy/rotate plus a multi-method compression suite.
- `test_compress_pdf_bytes.py` is a no-op smoke test that accepts `None` as a valid result — provides essentially zero verification value.
- No tests for the `no_compression`-bypass bug in `compress_selected` / `pdf_storage.compress`.
- No tests for the persisted-but-discarded `is_compressed` field in `_parse_node`.
- No tests assert the post-merge `no_compression` OR rule.
- `test_pdf_node_merge_dpi_conflict_lazy.py` is a script with module-level side effects (writes to `Path("merge_dpi_conflict_a.pdf")` in CWD) — not a pytest function, and the file does collect because pytest picks up `test_*` modules even without `def test_*`. The hard-coded PDF literal at lines 6-23 is brittle.

---

## 5. Security findings

The application is a local desktop tool, not a server, so the threat model is mostly "untrusted file dropped onto the UI". Findings ranked from highest to lowest concern.

### 5.1 ZIP/TAR import — no member-size or count limits (universal_importer.py:382-398, 412-433)

`extract_zip_to_structure` and `extract_tar_to_structure` iterate every member of an archive and call `UniversalImporter.convert` on each. There is:

- **No limit on uncompressed size** — a zip-bomb (small `.zip` file expanding to GB) is opened entirely in memory via `zf.open(name).read()` / `tf.extractfile(member).read()`.
- **No limit on member count.**
- **No path-traversal check.** TAR entries with `../../` paths are not used to write files (good — we never extract to disk), but `os.path.basename(member.name)` (line 417) is the only sanitization; if `basename` returns empty, the original `member.name` is reused as a node name (line 417 `or member.name`). For TAR specifically, member names like `/etc/passwd` would just become node display names — low risk, but symlinks (`member.issym()`/`member.islnk()`) are silently skipped via `if not member.isfile()` (line 415), so the absence of explicit symlink handling is acceptable.

**Risk:** Local DoS via a maliciously crafted archive. Practical impact: a user drag-dropping an attacker-supplied `.zip` could lock up or crash the app.

### 5.2 Temp-file lifecycle in Office conversion (universal_importer.py:285-320)

`_convert_office_via_com` writes to `os.path.join(tempfile.gettempdir(), base_name + ".pdf")` — predictable filename based on the input base name. Concerns:

- **No `tempfile.NamedTemporaryFile`** — predictable path in shared TEMP allows another local user (or process) to pre-create / replace the file between Excel/Word save and the subsequent `open(out_path, "rb")`. Mitigation: on Windows this is usually a per-user TEMP, so cross-user attack is rare.
- **The temp PDF is never deleted.** Repeated imports leak files into `%TEMP%`.

### 5.3 Office COM injection via filename (universal_importer.py:291-309)

`win32com.client.Dispatch("Word.Application").Documents.Open(path)` — the path is normalized but not sanitized for things like `\\server\share` UNC paths. Opening a malicious doc/xls/ppt over SMB could be abused via macros or DDE — although Office's own protected-view should block. Recommend setting `word.AutomationSecurity = 3` (msoAutomationSecurityForceDisable) before Open.

### 5.4 No PDF content validation beyond `%PDF` header (universal_importer.py:143, 178, 317)

After conversion, the only check is `pdf_bytes.strip().startswith(b"%PDF")`. A malformed PDF can still crash pikepdf/pypdf later. Not a security issue per se, just a robustness issue (already covered by `try/except` walls, but causes silent compression failures).

### 5.5 Email parsing (universal_importer.py:436-572)

- `extract_email_to_structure` uses `email.parser.BytesParser(policy=policy.default)` — modern policy, OK.
- Attachments are decoded via `part.get_payload(decode=True)` and passed straight to `UniversalImporter.convert`. The eventual converter is determined by *filename extension only* (line 127). A file named `.pdf` containing arbitrary bytes is fed straight into pikepdf/pypdf — which is fine, those libraries are designed to handle untrusted PDFs, but EXE/JS/HTML attachments masquerading as PDF would silently fail rather than warn the user.
- HTML body is converted via `xhtml2pdf.pisa.CreatePDF` (line 245). xhtml2pdf has had a history of CVEs around URL fetching for images and CSS. The current invocation passes raw HTML straight in — no `link_callback` to block remote URL fetches. **This means a malicious .eml/.msg with an HTML body containing `<img src="http://attacker/track">` will be fetched at import time and leak the user's IP / track that the email was opened.** This is the most concrete security finding in the report.

### 5.6 PDF metadata injection (pdf_storage.py:249, 96-114)

`writer.add_metadata({"/JSONStructure": structure_json})` embeds the full tree structure as a PDF metadata string. On load (`pdf_storage.py:96-114`), the metadata is read and `json.loads`-ed. `json.loads` itself is safe, but the parsed structure drives `_parse_node` which calls `extract_pages(data, start, end)` with `start`/`end` from the untrusted JSON (lines 343-355). Bounds are checked (line 347, 351), so worst case is an empty result. Acceptable.

### 5.7 No code signing / no integrity check on `.belegtool` files

A `.belegtool` is just a PDF with embedded JSON. There's no signature, no checksum. An attacker who can modify a saved file can change `pdf_length` values to confuse the tree-structure parser. Bounds-checked, so no crash, but data integrity is on the host filesystem.

### 5.8 Log file behavior (log_config.py:46-60, belegtool_main.py:268-271)

- LOGFILE is deleted at every startup if logging is enabled (line 50). User runs are not preserved across sessions.
- `os.startfile(LOGFILE)` is called *after* mainloop returns if `LOGGING_ENABLED` and `getsize > 0`. The file is opened in the user's default `.log` handler. Mostly benign.

### 5.9 No checks on `tkinterdnd2` drop sources (view_tree.py:262-286)

DnD-dropped files are processed without confirmation. A malicious drop chain (e.g., browser tab dragging a UNC path) feeds straight into the importer.

---

## 6. Recommendations — improving compression capabilities and configurability

Numbered roughly by impact / cost. **R1, R3, R5, R8 are the highest-leverage.**

### R1. Introduce a central compression-config dataclass

```python
# compress_pdf_bytes.py
from dataclasses import dataclass

@dataclass(frozen=True)
class CompressionConfig:
    dpi: int = 150
    jpeg_quality: int = 60
    png_compress_level: int = 6
    colorspace: str = "gray"    # "gray" | "rgb"
    max_width_pt: float = 595.0 # A4; None disables downscaling
    methods: tuple = ("jpg", "png", "pikepdf")
```

Plumb a single `CompressionConfig` through `compress_pdf_bytes`, `compress_all_methods`, `PDFNode.compress*`. Default values match today's behavior — no regression. Opens the door to a real UI for power-users (a "Compression settings" dialog) and a real `config.txt` (or a `pdf_tool.toml`) for per-machine defaults.

### R2. Add a `quality_low / quality_medium / quality_high` preset enum

Most users don't know what JPEG q=60 means. Expose three presets:
- Low (q=40, gray, 100 DPI, downscale to A4)
- Medium (q=60, gray, 150 DPI, downscale to A4) — current default
- High (q=85, RGB, 200 DPI, no downscale)

This is a small UI change (radio buttons next to the DPI slider) but lets users trade size for fidelity without learning DPI semantics.

### R3. Add color-preserving methods

Today's `jpg`/`png` paths force grayscale (`fitz.csGRAY`, `.convert("L")`). For receipts (the project's actual name implies receipts), color matters — stamps, highlighter, signatures. Add two new methods:

- `"jpg_color"` — RGB JPEG, q=75.
- `"jpg_mixed"` — per-page detection: if `Image.getcolors(maxcolors=64)` returns None or shows >32 distinct colors → RGB JPEG, else grayscale. Best size/fidelity tradeoff for scanned receipts that mix BW and color pages.

Each method becomes another entry in `compress_all_methods`; the dropdown automatically lists them.

### R4. Add a `"webp"` method

WebP is now well-supported in PDF viewers via Pillow (`format="WEBP"`). WebP at quality 75 typically beats JPEG q=75 by 20-30% at the same visual quality. Pillow already ships WebP support — zero new dependency.

### R5. Honor `no_compression` in *all* compression entry points

Fix the bugs identified in §3.4-6/7:

```python
# panel_controls.py compress_selected
if not subnode.is_compressed and not subnode.no_compression and subnode._is_descendant_of(node):
# ...
elif not node.is_compressed and not node.no_compression:

# pdf_storage.py compress
if not node.is_folder and not node.is_compressed and not node.no_compression:
```

### R6. Restore `is_compressed` from disk

In `_parse_node`, delete line 369 (`node.is_compressed = False`) and instead let `set_original_and_current_data` reconstruct it, or pass the persisted value through the constructor signature.

### R7. Split should preserve, not overwrite, source `no_compression`

```python
no_compression=self.no_compression  # was: True
```

…with the caveat that splits from an *already compressed* parent should still inherit `True` because the slice's "original" is actually the parent's compressed output. Best fix: track `no_compression` and a new `slice_of_compressed` flag separately.

### R8. Cache compressed bytes on disk between runs

Today `_compression_results` lives in RAM only. Re-opening a `.belegtool` file re-runs all three methods on every leaf. For a 100-page document this is 30+ seconds of CPU per open. Persist `_compression_results` (or at least the best result + its method name + DPI) in the `.belegtool` JSON metadata. Recompute only when DPI changes.

### R9. Disable remote URL fetching in xhtml2pdf

```python
def _block_remote(uri, rel):
    if uri.startswith(("http://", "https://")):
        return None    # do not fetch
    return uri

pisa_status = pisa.CreatePDF(src=html, dest=buffer, link_callback=_block_remote)
```

Addresses §5.5.

### R10. Add archive-size guards

```python
MAX_UNCOMPRESSED = 500 * 1024 * 1024  # 500 MB
MAX_MEMBERS = 500

total = sum(zi.file_size for zi in zf.infolist())
if total > MAX_UNCOMPRESSED or len(zf.infolist()) > MAX_MEMBERS:
    raise ValueError("Archive too large or has too many members.")
```

Addresses §5.1.

### R11. Unify the locking in `PDFNode`

A single `_node_lock` covering preview + compression state changes is simpler than the three current state machines. The cost is briefly serializing preview generation behind compression on the same node, which is fine — the UI shows a placeholder either way.

### R12. Replace `sanitize_pdf` with a real repair pass

Either delete it (it doesn't repair anything, see §4.2) or replace with a pikepdf-based round-trip (`pikepdf.open(... fix_pdf=True).save(...)`) which actually handles many real-world corruptions.

### R13. Per-page method choice

The current model: one method per node. Real receipts often have one scanned cover (best as JPEG) + several text pages (best as pikepdf structural). Per-page method selection could shave another 30-50% on heterogeneous documents. Implementation: in `_render_pdf_as_images`, allow `method="auto"` that decides per page based on `len(page.get_images())` or text-coverage heuristics.

### R14. Expose `linearize=True` as a method/save option

`pdf_storage.save` already linearizes on save, but the compression methods don't. Linearization (Fast Web View) is free at compress-time and helps when files are uploaded to web viewers.

### R15. Document each compression method

Add a `METHODS_DOC = {...}` dict mapping method-key → user-facing description ("JPEG, grayscale, lossy. Best for scanned receipts."). Surface in the dropdown tooltip.

---

## 7. Quick wins

These are the lowest-effort, highest-reward changes — most are one-liners or small refactors that can land independently.

| # | Change | File:line | Effort | Impact |
|---|---|---|---|---|
| QW1 | Add `not node.no_compression` to `compress_selected` and `pdf_storage.compress` | `panel_controls.py:454,458`, `pdf_storage.py:138` | 5 min | Fixes user-visible bug: "I clicked Lesbarkeit-geprüft, why did it re-compress?" |
| QW2 | Stop discarding `is_compressed` on load | `pdf_storage.py:369` | 2 min | Reload preserves tree colors. |
| QW3 | Fix docstring contradiction in `compress_pdf_bytes` | `compress_pdf_bytes.py:9-13` | 2 min | Removes misleading "Returns the smaller result". |
| QW4 | Add `link_callback` to xhtml2pdf to block remote fetches | `universal_importer.py:245` | 5 min | Closes tracking-pixel privacy hole. |
| QW5 | Delete the no-op `test_compress_pdf_bytes.py` and write one real test | `tests/test_compress_pdf_bytes.py` | 15 min | Real regression protection. |
| QW6 | Extract magic numbers (`q=60`, `compress_level=6`, `A4_WIDTH_PT`, default DPI) into module-level constants | `compress_pdf_bytes.py:44,67,69` | 10 min | Easier future tuning. |
| QW7 | Add archive size + member-count guards | `universal_importer.py:382,412` | 15 min | Closes zip-bomb DoS. |
| QW8 | Add the `dpi_current` reset alongside `no_compression` reset in `reset_compression` | `pdf_node.py:570-581` | 5 min | Avoids stale `dpi_current` after reset. |
| QW9 | Add an explicit `webp` method to `compress_all_methods` | `compress_pdf_bytes.py:24` | 30 min | Often 20-30% better than JPG, zero new deps. |
| QW10 | Set `word.AutomationSecurity = 3` before opening docs | `universal_importer.py:291` | 5 min | Defense-in-depth for macro/DDE. |
| QW11 | Make `compress_selected` use `compress_multi_lazy` instead of synchronous JPG-only `compress` | `panel_controls.py:455,459` | 5 min | Toolbar/menu compression matches what slider does — best method wins, dropdown gets populated. |
| QW12 | Add a docstring note on `_split_pdf` about the `no_compression=True` and self-mutation side effects | `pdf_node.py:887-957` | 5 min | Future-maintainer clarity. |
| QW13 | Replace `tools.sanitize_pdf` with a pikepdf-based round-trip OR remove it | `tools.py:6-36` | 20 min | Either real repair or honest no-op. |
| QW14 | Persist best-compression result in the `.belegtool` metadata to avoid recompute on every open | `pdf_node.to_dict`, `pdf_storage._parse_node` | 60 min | Massive UX win for repeat-edit workflows. |
| QW15 | Add `linearize=True` to the in-memory pikepdf save in `recompress_with_pikepdf` | `compress_pdf_bytes.py:106` | 1 min | Fast Web View on every result. |

---

## Appendix A — Files cited

Source files (absolute paths):

- `c:\skripte\private\DigitalerUnterlagenOrdner\compress_pdf_bytes.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\pdf_node.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\pdf_storage.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\panel_controls.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\view_preview.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\view_tree.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\belegtool_main.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\universal_importer.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\toc_export.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tools.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\log_config.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\status_display.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\preview_page.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\version_info.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\requirements.txt`

Briefings reviewed:

- `c:\skripte\private\DigitalerUnterlagenOrdner\Briefing UI Design.txt`
- `c:\skripte\private\DigitalerUnterlagenOrdner\Briefing UI Design Update.md`
- `c:\skripte\private\DigitalerUnterlagenOrdner\Briefing Erweiterungen Zammad.txt`
- `c:\skripte\private\DigitalerUnterlagenOrdner\CLAUDE.md`

Tests reviewed:

- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\helpers.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\test_compress_pdf_bytes.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\test_compression_multi.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\test_pdf_node_merge.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\test_pdf_node_merge_dpi_conflict_lazy.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\test_pdf_node_merge_files.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\test_pdf_node_foldermerge.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\test_pdf_node_split.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\test_split_folder.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\test_split_preserves_previews.py`
- `c:\skripte\private\DigitalerUnterlagenOrdner\tests\test_pdf_node_rotate.py`
