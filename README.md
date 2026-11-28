# Digitaler Unterlagen-Ordner

*A filing cabinet for your PDFs — collect every document into one structured, bookmarked PDF.*

**Digitaler Unterlagen-Ordner** (internally *BelegTool*) is a Windows desktop app for anyone who keeps a lot of documents and receipts and wants them in one place instead of scattered across folders. Import PDFs, scans, photos, Office files, e-mails, and archives into a single structured tree, preview and compress them, and export the whole thing as one PDF with a clickable table of contents and sidebar bookmarks.

The interface is available in 22 languages (German and English fully native; see [BETA_TESTING.md](BETA_TESTING.md)).

> **Status: active beta.** It's solid enough for real use, but see [Known limitations](#known-limitations) and [BETA_TESTING.md](BETA_TESTING.md) before you rely on it. Bug reports and feedback are very welcome — see [Feedback & contributing](#feedback--contributing).

## Features

**Bring in anything**
- PDF and `.belegtool` files load directly as document trees.
- Images (JPG, PNG, BMP, TIFF, WebP, HEIC) are converted to PDF automatically, one A4 page each; text and HTML files too.
- Microsoft Office files (Word, Excel, PowerPoint), converted via the installed Office apps.
- E-mail — `.eml` and Outlook `.msg` — with attachments extracted into a subtree.
- Archives — ZIP and TAR/TGZ — with their folder structure preserved (and a zip-bomb guard).
- An import safety screen rejects executables and files masquerading as PDFs or images.

**Organize**
- Arrange documents in a foldered tree: create folders, rename, delete.
- Drag-and-drop to move, nest, and reorder — or drop OS files straight in to import them.
- Keyboard-driven restructuring (grab, move, commit) with full undo/redo.
- Split a multi-page document into one node per page; merge siblings back together.
- Per-node status tracking (recorded / to record / prior year), which round-trips when you save.

**Preview & compress**
- Fast, cached, page-by-page preview with a DPI slider (50–300).
- Multiple compression methods computed in parallel — grayscale/color JPG, PNG, and structural — with the smallest result picked automatically and original sizes shown for comparison.

**Export & save**
- Export your selection or the whole tree to one PDF (or several, split by page count) with a printed, clickable table of contents and sidebar bookmarks.
- Save as `.belegtool`: a real PDF that any viewer can open, with your tree structure stored inside so it re-imports losslessly.
- Open multiple documents at once, each in its own window.

## Requirements

- Windows 10 or 11.
- For importing **Office** files, Microsoft Word/Excel/PowerPoint must be installed. Everything else (PDF, image, archive, and email import) works without Office.

## Installation

### Microsoft Store

BelegTool is available in the Microsoft Store:

**https://apps.microsoft.com/detail/9PL4D25N00XD**

The Store install is the easiest path: automatic updates and no SmartScreen/antivirus
warnings. A step-by-step guide (German) is in
[docs/Installation_Microsoft_Store.pdf](docs/Installation_Microsoft_Store.pdf). The Store
build can lag behind the latest GitHub release — the window title shows the installed version.

### Option A — Prebuilt

Download the latest build from the [Releases](../../releases) page, unzip it, and run `BelegTool.exe`. No Python or Node.js required. You can also open a file directly:

```
BelegTool.exe yourfile.belegtool
```

### Option B — From source

Requires Python 3.12 or newer and Node.js.

```bash
pip install -r requirements.txt
cd webui && npm install && npm run build && cd ..
python host.py
```

Open a file on launch with `python host.py yourfile.belegtool`.

## Known limitations

- **Split export has its own table of contents.** When an export is split into several files, each file gets its own TOC with cross-references; the tag-index/bookmark options apply to single-file export only.
- **Compression is irreversible once saved.** When you commit compression on a document and save, the original bytes are dropped to keep the file small — that node can't be reset afterward.
- See [BETA_TESTING.md](BETA_TESTING.md) for the full current list and what to expect while testing.

## Feedback & contributing

This project is in active testing, and feedback is the most useful thing you can give. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to report bugs, request features, and share first impressions.

Translations are welcome too: the UI strings are externalized (German source + one map per language under `webui/src/i18n/`), so adding a language is just a translation file. Open an issue if you'd like to help.

## License

Licensed under the **GNU Affero General Public License v3.0** (AGPLv3 or any later version, `AGPL-3.0-or-later`) — free to use, modify, and distribute, and free for personal use. If you use it to provide a network service, you must make your modified source code available to that service's users.

A **commercial license** is available for closed-source or proprietary use. Contact: tobias.a.w.heinrich@gmail.com

See [LICENSE](LICENSE) for the license notice, [COPYING](COPYING) for the full AGPLv3 text and [LICENSE_COMMERCIAL.md](LICENSE_COMMERCIAL.md) for commercial terms.

Source code: <https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner>. Licenses of the bundled third-party components: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) (generated by `scripts/gen_third_party_notices.py`; the full license texts ship in the `licenses/` folder of the program directory).

### Trademarks

Dieses Projekt steht in keiner Verbindung zur DATEV eG; DATEV ist eine eingetragene Marke der DATEV eG.
This project is not affiliated with DATEV eG; DATEV is a registered trademark of DATEV eG.
