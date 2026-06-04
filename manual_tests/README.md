# Manual Tests — DigitalerUnterlagenOrdner (BelegTool)

Step-by-step instructions for a **human tester** (no coding needed) to validate
the app by hand. This complements the automated `pytest` suite — it checks the
things only a person at the screen can confirm (visual previews, drag-and-drop,
dialogs, export results).

> **One front end (v3.6.0).** The legacy Tk app was removed; the only UI is the
> **React/pywebview desktop app** (`python host.py`). File
> [05_react_ui.md](05_react_ui.md) covers the React-UI-specific flows (drag-drop
> import, slide-to-level drop, working-preview compression, multi-window). Files
> 01–04 cover the underlying features (import, tree ops, preview/compression,
> export/persistence); ⚠ their step wording predates the React UI and is being
> re-verified against it — perform the equivalent action in the React UI.

## Before you start

1. **Run the app:** `cd webui && npm run build` then `python host.py` (or
   the built `dist\BelegTool\BelegTool.exe`).
2. **Have a few sample files ready** on disk:
   - a multi-page **PDF**, a **JPG/PNG** image, optionally a **.zip**, an
     **.eml** or **.msg** e-mail with an attachment, and a Word/Excel file.
   - You can reuse the fixtures in `tests/data/input/` (e.g. `sample.pdf`,
     `split_sample.pdf`).
3. The app window has three areas: the **toolbar** (top: `[Import] [Speichern]
   [Speichern als]`), the **tree** (left), and the **preview** (right).

## How to use these files

- Work through each file in order. Each **test case** has an ID (e.g. `MT-03`),
  **Preconditions**, numbered **Steps**, and an **Expected** result.
- Pay attention to the *Expected* notes — they call out non-obvious behaviour
  (e.g. a placeholder image may flash before the real preview appears).
- If an Expected result does not happen, note the test ID, what you saw, and the
  steps to reproduce.

## Index

| File | Area |
|---|---|
| [01_import.md](01_import.md) | Importing PDFs, images, e-mails, archives; import-safety |
| [02_tree_operations.md](02_tree_operations.md) | Split, merge, folders, rename, delete, drag-and-drop |
| [03_preview_and_compression.md](03_preview_and_compression.md) | Preview, DPI slider, compression, commit/reset, status colours |
| [04_export_persistence_and_testmode.md](04_export_persistence_and_testmode.md) | Export (TOC), save/reload `.belegtool`, committed-compression drop |
| [05_react_ui.md](05_react_ui.md) | **React UI** (`host.py`): import/drop, tree edit, compression preview, multi-window, guards, export, shortcuts |
| [06_status_cache_compression.md](06_status_cache_compression.md) | **Status bar**, render-cache gauge & ＋/− buttons, prefetch warming, default-to-smallest compression, apply, split-carries-compression, cancel-on-remove |
| [07_keyboard_delete_language.md](07_keyboard_delete_language.md) | **Keyboard** structuring (Insert carry), collapse, **multi-delete + parent/child resolver**, inline rename, **language switcher**, layout (resizable pane, page indicator) |

> Keep these files current: whenever a user-facing flow changes, update the
> matching test case. (Workspace convention — see the global CLAUDE.md.)
