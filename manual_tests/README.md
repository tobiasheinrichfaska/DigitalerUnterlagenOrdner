# Manual Tests — DigitalerUnterlagenOrdner (BelegTool)

Step-by-step instructions for a **human tester** (no coding needed) to validate
the app by hand. This complements the automated `pytest` suite — it checks the
things only a person at the screen can confirm (visual previews, drag-and-drop,
dialogs, export results).

> **One front end (v3.6.0).** The legacy Tk app was removed; the only UI is the
> **React/pywebview desktop app** (`python host.py`). All files **01–08 describe the
> current React UI** (toolbar + right-click context menu; there is no menu bar).
> [05_react_ui.md](05_react_ui.md) goes deepest on the React-specific flows (drag-drop
> import positioning, slide-to-level drop, working-preview compression, multi-window).

## Before you start

1. **Run the app:** `cd webui && npm run build` then `python host.py` (or
   the built `dist\BelegTool\BelegTool.exe`).
2. **Have a few sample files ready** on disk:
   - a multi-page **PDF**, a **JPG/PNG** image, optionally a **.zip**, an
     **.eml** or **.msg** e-mail with an attachment, and a Word/Excel file.
   - You can reuse the fixtures in `tests/data/input/` (e.g. `sample.pdf`,
     `split_sample.pdf`).
3. The app window has three areas: the **toolbar** (top: 📂 Öffnen · 📥 Importieren ·
   💾 Speichern · ⬇ Export PDF · ＋ Ordner · 🗗 Neues Fenster · ↶/↷ · 🏷️ Tags · ❓ Hilfe),
   the **tree** (left), and the **preview** (right). Tree operations are on the
   **right-click context menu**.

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
| [03_preview_and_compression.md](03_preview_and_compression.md) | Preview, zoom, DPI slider, compression, commit/reset, status dots |
| [04_export_persistence.md](04_export_persistence.md) | Export (TOC + options dialog), save/reload `.belegtool`, committed-compression drop, save-alternatives dialog |
| [05_react_ui.md](05_react_ui.md) | **React UI** (`host.py`): import/drop, tree edit, compression preview, multi-window, guards, export, shortcuts |
| [06_status_cache_compression.md](06_status_cache_compression.md) | **Status bar**, render-cache gauge & ＋/− buttons, prefetch warming, default-to-smallest compression, apply, split-carries-compression, cancel-on-remove |
| [07_keyboard_delete_language.md](07_keyboard_delete_language.md) | **Keyboard** structuring (Insert carry), collapse, **multi-delete + parent/child resolver**, inline rename, **language switcher**, layout (resizable pane, page indicator) |
| [08_status_dots_help.md](08_status_dots_help.md) | **Status dots** aggregation (leaf/folder, mixed black dot, cascade), compression "undecided" red dot, **❓ Hilfe** modal |
| [09_pdf_tool.md](09_pdf_tool.md) | **PDF-Tool** surface: open a leaf (folders can't), add text / fill forms, save back into the node, re-edit across sessions, compression-flatten caveat |
| [10_datev.md](10_datev.md) | **DATEV mode** (v3.10.0): toggle on/off, „from DATEV" badge on a checked-out file, guarded write-back (incl. conflict/locked fallbacks), file-to-DATEV, export-to-DATEV (same client, every split part) — **requires a DATEVconnect box; skip where none is reachable** |

> Keep these files current: whenever a user-facing flow changes, update the
> matching test case. (Workspace convention — see the global CLAUDE.md.)
