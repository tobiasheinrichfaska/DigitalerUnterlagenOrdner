# Contributing to DigitalerUnterlagenOrdner (BelegTool)

Thank you for your interest! This covers both **code contributions** and
**beta-tester feedback**. The project is dual-licensed under AGPLv3 (open source)
and a commercial license.

> 🇩🇪 Beiträge und Rückmeldungen auf **Deutsch** sind ebenfalls willkommen.

---

## Giving feedback (beta testers)

You don't need to write code to help. New testers should start with
[`BETA_TESTING.md`](BETA_TESTING.md). There are four kinds of feedback, each with
its own issue form (**New issue** → pick a template):

| Kind | Where | Use it for |
|---|---|---|
| 🐞 Bug report | Issue → *Bug report* | Something broken or wrong |
| 💡 Feature request | Issue → *Feature request* | A capability you'd like |
| 🧪 Beta feedback | Issue → *Beta feedback* | First impressions / UX / "would you use it?" |
| 💬 Question | [Discussions](https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner/discussions) | Not sure if it's a bug, or general chat |

**Two things that are NOT bugs** (please don't report them):
1. Exporting more than 100 pages produces a **single** PDF — auto-split is not
   wired into the UI yet.
2. Compression is **irreversible after saving** — the source is dropped and the
   option shows *"bereits komprimiert (keine Quelle)"*.

---

## Building & running from source

BelegTool is **Windows 10/11 only** (it uses Edge WebView2 and, for Office import,
MS Office via COM).

**Prerequisites:** Python **3.12** on PATH, **Node.js**, and — for Word/Excel/
PowerPoint import — **Microsoft Office installed locally**.

```powershell
pip install -r requirements.txt
cd webui
npm install
npm run build      # build the React SPA once
cd ..
python host.py             # launch the app
python host.py file.belegtool   # ...opening a file
```

Dev mode (live React reload + the 🧪 Testmodus button):
`cd webui ; npm run dev` then `set BELEG_DEV=1 ; python host.py`.

Build the prebuilt exe: `powershell -ExecutionPolicy Bypass -File build.ps1`
→ `dist\BelegTool\BelegTool.exe`.

---

## Tests & fixtures

```powershell
pytest               # Python logic/core tests
cd webui ; npm test  # React/Vitest tests
```

PDF test fixtures live in **`tests/data/input/`** (e.g. `sample.pdf`,
`split_sample.pdf`, `compress_sample.pdf`, `merge1_a.pdf`, `merge1_b.pdf`).
Regenerate them with `python tests/make_fixtures.py`.

**Manual tests** (human tester, no coding): see
[`manual_tests/`](manual_tests/README.md). The current, accurate files are
**`05_react_ui.md`, `06_status_cache_compression.md`, `07_keyboard_delete_language.md`**.
Files `01`–`04` are **stale** (they describe the removed Tk GUI) — perform the
equivalent action in the React UI.

---

## Contributor License Agreement

By submitting a pull request or contribution to this project, you agree that:

1. **Grant of Rights:** You grant the project maintainer (Tobias Heinrich) a
   perpetual, worldwide, non-exclusive, royalty-free, irrevocable right to use,
   reproduce, modify, and redistribute your contributions under any license
   (including commercial licenses) without restriction.
2. **Original Work:** You represent that your contributions are original works or
   properly licensed/attributed third-party work.
3. **No Warranty:** Your contributions are provided "as-is" without warranty of any kind.

By contributing, you accept these terms.

## How to contribute code

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Add tests (logic ships with its tests; a bug fix ships with a regression test)
5. Commit with clear messages
6. Push to your fork and open a pull request

## Help wanted

- **macOS / Linux port** — BelegTool is Windows-only today; a port is feasible but not on
  the maintainer's roadmap. See the draft RFC [`docs/cross-platform-port.md`](docs/cross-platform-port.md)
  for the blockers, a suggested approach, and a definition of done. Contributions welcome.

## Code standards

- Follow PEP 8 for Python code
- Keep the logic/UI split: the `core/` model has no UI imports and is unit-testable headless
- Write tests for new features
- Update `CLAUDE.md` if you change architecture

Thank you!
