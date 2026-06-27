# Beta Testing BelegTool 🧪

Thanks for helping test **BelegTool** (DigitalerUnterlagenOrdner) **v3.9.5** — a
Windows desktop app that collects PDFs, scans, photos, Office files, e-mails and
archives into one foldered tree, then compresses, previews and exports the whole
thing as a single bookmarked PDF with a table of contents.

> 🌍 **Many languages — and you can help polish them!** The language switcher
> (top-right) offers 22 entries. **Fully translated:** German (default),
> English (US) / English (UK), Français, Español, Català, Русский, Українська,
> Hrvatski, 한국어, Latina, the dialects **Boarisch, Plattdüütsch, Weanerisch**, and the
> best-effort **ייִדיש (Yiddish), Gàidhlig (Scottish Gaelic), Gaeilge (Irish),
> Cymraeg (Welsh)** — these last four are complete but **would genuinely benefit from
> a native eye**. A few are partial just for fun (**Quenya** & **Sindarin** Elvish and
> **tlhIngan Hol** / Klingon — these fall back to German — plus **Minionese** 🍌). If
> you speak one of the best-effort ones, please send corrections (see *Translations*
> below). Feedback in German is always welcome. 🇩🇪

**Requirements:** Windows **10 or 11**. For Word/Excel/PowerPoint import you also
need **Microsoft Office installed** — without it, importing PDFs, images, archives
and e-mails still works fine.

---

## 1. Get & run the app

### Path A — Prebuilt download (easiest, no Python/Node)
1. Download **`BelegTool-v3.9.5-win64.zip`** from the
   [**latest release**](https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner/releases/latest).
2. Unzip it anywhere.
3. Double-click **`BelegTool\BelegTool.exe`**. That's it — no installation.
   - To open a saved file directly: `BelegTool.exe yourfile.belegtool`.
   - *Windows SmartScreen* may warn on first run (unsigned app) → **More info → Run anyway**.

#### ⚠️ App errors with a ".NET / Python.Runtime / clr" message — unblock the files
If you see *"Failed to resolve Python.Runtime.Loader.Initialize …"* (or a similar
pythonnet/.NET error), the usual cause is **Windows' "Mark of the Web"**: downloaded files
are flagged *"from the internet"*, and **.NET then refuses to load the bundled
`Python.Runtime.dll`**. This happens **even if you have no antivirus** — the file is present
and not infected. Fix by **unblocking the files**:
1. **Best — before extracting:** right-click the downloaded `.zip` → **Properties** → tick
   **Unblock** (de: *Zulassen* / *Blockierung aufheben*) → **OK** → then unzip.
2. **Already extracted** — in PowerShell, inside the BelegTool folder:
   ```powershell
   Get-ChildItem -Recurse . | Unblock-File
   ```
3. Extract to a normal local folder like `C:\Users\<you>\BelegTool` — **not** under
   `C:\Program Files` or a network/removable drive (those cause "cannot access / permissions").

(From v3.9.4 the app detects this and shows the unblock hint instead of a raw traceback.)

#### ⚠️ Antivirus quarantines it (Norton, etc.)
The beta is **not code-signed yet**, so some antivirus tools (e.g. **Norton CyberCapture**)
may sandbox or quarantine files (often `Python.Runtime.dll`). It's a **false alarm**, not
malware: restore the quarantined files and add an **exclusion** for the BelegTool folder
(Norton → *Security History/Quarantine* → restore; *Settings → Antivirus → Exclusions*).

A signed Microsoft Store version is planned, which removes these warnings. **Please don't
file these as bugs** — they're known limitations of the unsigned beta.

### Path B — From source
1. Install **Python 3.12 or newer** (on PATH) and **Node.js**. *(3.13 and 3.14 work for
   running from source; the official prebuilt `.exe` is currently built with 3.12.)*
2. In the project folder:
   ```powershell
   pip install -r requirements.txt
   cd webui
   npm install
   npm run build
   cd ..
   python host.py
   ```

---

## 2. Sample files to test with

The repo ships ready-made PDFs in **`tests/data/input/`**:
`sample.pdf`, `split_sample.pdf`, `compress_sample.pdf`, `merge1_a.pdf`,
`merge1_b.pdf`. If they're missing, regenerate with
`python tests/make_fixtures.py`. Bring your own files too — a JPG/PNG/HEIC image,
a `.zip`, an `.eml`/`.msg` e-mail with an attachment, and (if you have Office) a
Word/Excel file.

---

## 3. Recommended test path

Walk through the manual-test guides in [`manual_tests/`](manual_tests/README.md).
Use these three — they match the current app:

- **[`05_react_ui.md`](manual_tests/05_react_ui.md)** — import & drag-drop, tree
  editing, compression preview, multi-window, export, shortcuts.
- **[`06_status_cache_compression.md`](manual_tests/06_status_cache_compression.md)**
  — status bar, render-cache gauge, compression default-to-smallest, apply.
- **[`07_keyboard_delete_language.md`](manual_tests/07_keyboard_delete_language.md)**
  — keyboard structuring, multi-delete, inline rename, language switcher.

> All files **`01`–`08` describe the current React/pywebview UI** (toolbar +
> right-click menu; no menu bar).

Core workflows to make sure you exercise: **import** (several formats),
**tree view** (folders, move, rename), **split / merge / compress**,
**TOC export** (export a multi-folder tree, open the PDF, check the table of
contents and bookmarks), and **save & reload** a `.belegtool` file.

---

## 4. One known gap — please DON'T report this as a bug

1. **Compression is irreversible after saving.** Once you apply compression to a
   node and save, the original source is dropped — you can't undo it later, and
   the option shows *"bereits komprimiert (keine Quelle)"*. This is by design.

> Large exports now offer a split: the export dialog lets you split into multiple
> PDFs by page count and break level (top node / any folder / mid-document), so a
> big tree no longer has to be one giant file.

---

## 5. What feedback we want, and where it goes

| What | How | Template |
|---|---|---|
| 🐞 **Bugs** — something broken/wrong | New issue | *Bug report* |
| 🧪 **Impressions & UX** — confusion, gut feel, "would you use it?" | New issue | *Beta feedback* |
| 💡 **Feature ideas** | New issue | *Feature request* |
| 🌐 **Translations** — wrong/missing UI text in a language (esp. the partial ones above) | New issue or Discussions | *Beta feedback* |
| 💬 **Questions / not-sure-if-a-bug / general chat** | [Discussions](https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner/discussions) | — |

Open an issue at the project's **Issues** tab and pick the matching form, or start
a thread under **Discussions**. The forms ask for your app version, install method
(prebuilt vs. source), Windows version, and whether Office is installed — having
those up front saves a round-trip.

**Thank you — every report genuinely helps.** 🙏
