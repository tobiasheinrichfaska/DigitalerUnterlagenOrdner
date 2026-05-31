# webui — React UI for DigitalerBelegeOrdner

The React front end that runs inside the pywebview host (`../host.py`), which
embeds the data-driven core (`core.api.CoreApi`) and exposes it as
`window.pywebview.api.*` (open / dispatch / undo / redo).

`npm`/Node are **build-time only** — the shipped app contains just the built
static files in `dist/` (bundled into the PyInstaller exe); end users need no Node.

## Develop (hot reload)

```bash
cd webui
npm install          # once
npm run dev          # Vite dev server on http://localhost:5173
```
then in another shell, from the project root:
```powershell
$env:BELEG_DEV = "1"     # tells host.py to load the dev server
python host.py
```
Edit `src/*` → the window hot-reloads.

## Build + run (production form)

```bash
cd webui && npm run build      # -> webui/dist (relative paths, file://-ready)
```
then from the project root:
```powershell
python host.py                 # loads webui/dist/index.html in the window
```

## Layout

| File | Role |
|---|---|
| `src/core.js` | thin wrapper over `window.pywebview.api` (awaits `pywebviewready`) |
| `src/App.jsx` | loads the document, toolbar (add-folder / undo / redo) |
| `src/Tree.jsx` | recursive tree; node actions dispatch real core commands |

`vite.config.js` sets `base: './'` so the build loads from `file://` in the host.
