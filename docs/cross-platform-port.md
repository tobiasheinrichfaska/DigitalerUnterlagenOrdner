# Draft — Help wanted: macOS & Linux port

> **Status: DRAFT / not maintainer-planned.** BelegTool ships as a Windows desktop app.
> A macOS/Linux port is *feasible* but is **not on the maintainer's roadmap** — this is an
> open call for community contributions. PRs welcome (AGPLv3 + CLA, see
> [`CONTRIBUTING.md`](../CONTRIBUTING.md)). Treat everything below as a starting point to
> refine, not a finished spec.

## Why it's Windows-only today

The PDF/processing core is already cross-platform; the app shell isn't. The hard
Windows bindings:

| Component | Today (Windows) | What a port needs |
|---|---|---|
| GUI host | `pywebview` on **Edge WebView2** (via `pythonnet`) | `pywebview` Cocoa/WebKit (macOS) and GTK/Qt-WebKit (Linux) backends; verify native file dialogs + drag-drop |
| `pywin32` | hard dependency (won't `pip install` off Windows); used by the file lock and Office/COM import | make it an **optional / platform-marked** dependency |
| Office import | Word/Excel/PowerPoint via **COM** (`win32com`, `universal_importer`) | abstract behind an interface; on macOS/Linux use LibreOffice headless (`soffice --convert-to pdf`) or disable with a clear message |
| File lock | Win32 `CreateFile` share-mode handle (`infra/file_lock.py`) | already Windows-gated; add a POSIX `fcntl`/`flock` implementation **or** keep it Windows-only |
| Build | PyInstaller `win64` onedir + `build.ps1` | `.app`/`dmg` (macOS) and an AppImage/binary (Linux) build scripts |

Cross-platform already: PyMuPDF, Pillow/pillow-heif, pikepdf, pypdf, reportlab,
xhtml2pdf, extract-msg — so import (minus COM Office), compression, preview, TOC/index
export and the `.belegtool` format should work as-is.

## Suggested approach

1. **Dependency split** — move `pywin32`/`pythonnet` to Windows-only markers in
   `requirements.txt` (e.g. `pywin32==311; sys_platform == "win32"`); guard every Windows
   import behind `sys.platform` (the lock already does — extend to `universal_importer`).
2. **Office import behind a port** — a small `OfficeConverter` interface: COM on Windows,
   LibreOffice-headless elsewhere, else a clear "Office import unavailable on this platform".
3. **GUI backend** — confirm the app runs under pywebview's macOS/Linux backends; fix any
   WebView2-specific assumptions (e.g. the `_safe_http_port` workaround, file-drop).
4. **Build** — add macOS/Linux build scripts mirroring `build.ps1`.
5. **CI** — run `pytest` on macOS/Linux; the Windows-only suites (`test_file_lock*`) already
   `skipif`, so they'll skip cleanly.

## Definition of done (per the project's conventions)

- Logic stays UI-free and headless-testable; `pytest` green on the target OS.
- New cross-platform code ships with tests; Windows behaviour unchanged.
- `manual_tests/` gains an OS-specific run note; `CLAUDE.md` platform section updated.
- No regression to the Windows build.

## Non-goals / keep in mind

- **Windows parity is the baseline** — the port must not degrade the Windows app.
- The single-writer **file lock** semantics differ across OSes (Windows mandatory vs POSIX
  advisory) — a POSIX version is "best-effort"; document it or keep the feature Windows-only.

## How to help

Comment on the tracking issue
[#3 "Help wanted: macOS & Linux port"](https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner/issues/3)
or open a PR against a `feature/…` branch. Small, reviewable slices welcome — e.g.
"dependency split + Linux launch" as a first PR, Office conversion as a second. See
[`CONTRIBUTING.md`](../CONTRIBUTING.md).
