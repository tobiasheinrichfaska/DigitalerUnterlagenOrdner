# Microsoft Store listing & submission content

Copy these into Partner Center. Two listing languages: **de-DE** (primary) and **en-US**.

---

## Listing — Deutsch (de-DE)

**Name:** BelegTool

**Kurzbeschreibung** (≤ ~250 Zeichen):
> PDFs, Scans, Fotos, Office-Dateien und E-Mails in einem Ordnerbaum sammeln, ordnen,
> komprimieren und als ein PDF mit Inhaltsverzeichnis exportieren – schnell, lokal, ohne Cloud.

**Beschreibung:**
> BelegTool bündelt Ihre Unterlagen zu einem aufgeräumten, durchsuchbaren PDF.
>
> Importieren Sie PDFs, Scans, Fotos (JPG/PNG/WEBP/HEIC), Office-Dokumente
> (Word/Excel/PowerPoint – Office erforderlich), E-Mails (EML/MSG) und Archive (ZIP/TAR)
> per Knopfdruck oder Drag-and-drop in einen Ordnerbaum. Ordnen Sie alles per Maus oder
> Tastatur, komprimieren Sie Seiten bei Bedarf und exportieren Sie das Ganze als **ein
> PDF mit Inhaltsverzeichnis, anklickbaren Links und Lesezeichen** – optional mit einem
> **Stichwortverzeichnis nach Tags**.
>
> Funktionen:
> • Ordnerbaum mit Drag-and-drop, Zusammenführen, Splitten, Umbenennen (F2)
> • Status-Punkte (Vorjahr / Zu erfassen / Erfasst) zum Abarbeiten
> • Komprimierung mit Lesbarkeitsprüfung; nur die kleinste sinnvolle Fassung wird behalten
> • Export als ein PDF mit Inhalts- und Stichwortverzeichnis (Tags), Links, Lesezeichen
> • Tags, Tag-Filter und -Gruppierung
> • Mehrsprachige Oberfläche
> • Alles läuft **lokal** – keine Cloud, keine Konten, keine Telemetrie
>
> Open Source (AGPLv3). Für Steuerberatung, Buchhaltung und alle, die Belege ordentlich
> ablegen wollen.

**Was ist neu (v3.11.4):**
> Sicherheitsupdate: aktualisierte Bild- und PDF-Bibliotheken (Pillow, pypdf, PDF.js) –
> schließt unter anderem eine Lücke, über die ein präpariertes PDF Code ausführen konnte.
> Außerdem neu: kompakte Symbolleiste, Speichern-Knopf mit „Speichern unter…",
> PDF-Werkzeug zum Ergänzen von Text und Ausfüllen von Formularen, Schlagworte für mehrere
> Einträge auf einmal, verschachtelte Archive und E-Mails werden bis zu 10 Ebenen tief
> ausgepackt, einstellbares Aufteilen beim Export, und das Fenster merkt sich Größe und Position.

**Suchbegriffe:** Belege, PDF zusammenfügen, Dokumente, Scannen, Steuer, Buchhaltung,
Inhaltsverzeichnis

---

## Listing — English (en-US)

**Name:** BelegTool

**Short description:**
> Collect PDFs, scans, photos, Office files and e-mails into one folder tree, organise,
> compress, and export a single bookmarked PDF with a table of contents — fast, local, no cloud.

**Description:**
> BelegTool turns your scattered documents into one tidy, searchable PDF.
>
> Import PDFs, scans, photos (JPG/PNG/WEBP/HEIC), Office documents (Word/Excel/PowerPoint —
> Office required), e-mails (EML/MSG) and archives (ZIP/TAR) by button or drag-and-drop into
> a folder tree. Organise with mouse or keyboard, compress pages where it helps, and export
> everything as **one PDF with a table of contents, clickable links and bookmarks** —
> optionally with a **tag index**.
>
> Features:
> • Folder tree with drag-and-drop, merge, split, rename (F2)
> • Status dots (Prior year / To record / Recorded) to work through a stack
> • Compression with a readability check; only the smallest worthwhile version is kept
> • Export one PDF with a table of contents + tag index, links, bookmarks
> • Tags, tag filtering and grouping
> • Multilingual UI
> • Everything runs **locally** — no cloud, no accounts, no telemetry
>
> Open source (AGPLv3). For tax advisors, bookkeeping, and anyone who wants receipts filed neatly.

**What's new (v3.11.4):**
> Security update: updated image and PDF libraries (Pillow, pypdf, PDF.js) — among other
> things this closes a hole through which a crafted PDF could run code.
> Also new: a compact toolbar, a Save button with "Save as…", a PDF tool to add text and
> fill in forms, tagging several entries at once, nested archives and e-mails unpacked up to
> 10 levels deep, configurable splitting on export, and the window remembers its size and position.

**Search terms:** receipts, merge PDF, documents, scan, tax, bookkeeping, table of contents

---

## Screenshots to capture (≥1 required; 3–5 recommended)

Window the app to a clean **1366×768** and capture:
1. **Main view** — folder tree (with a few status dots) + a PDF page preview on the right.
2. **Export dialog** — the TOC / tag-index / bookmarks options.
3. **Compression** — the method dropdown + "Lesbarkeit geprüft".
4. **Tags** — a tag view / tag chips on rows.
5. **Help** — the ❓ Hilfe modal with the 🇩🇪/🇬🇧 flags.

Use real-looking but **non-personal** sample documents (the `tests/data/input/*.pdf` fixtures).

---

## Submission checklist (Partner Center)

- [ ] New submission for app **BelegTool** (Store ID `9PL4D25N00XD`).
- [ ] **Packages:** upload the current `packaging/out/BelegTool-<version>-x64.msix` (unsigned; MS re-signs) —
      replaces the earlier package (live in the Store: 3.9.5.0; current build: 3.11.4.0 — submit THIS one, not the superseded 3.11.3.0).
- [ ] **Properties:** category **Productivity**; paste the **broadFileSystemAccess
      justification** (see `packaging/README.md`) into restricted-capability / "Notes for
      certification".
- [ ] **Age ratings:** complete the IARC questionnaire (no objectionable content → 3+).
- [ ] **Store listings:** de-DE + en-US text above; ≥1 screenshot (1366×768); StoreLogo.
- [ ] **Pricing & availability:** Free; choose markets.
- [ ] **Privacy policy URL:** link to `PRIVACY.md` (GitHub URL, or a GitHub Pages URL).
- [ ] Submit → certification (broadFileSystemAccess → manual review; the justification carries it).
- [ ] After publish: the Store link is **https://apps.microsoft.com/detail/9PL4D25N00XD**.
      It is already documented in `README.md` (marked "listing pending"). **Once the listing
      actually resolves**, append it to `BETA_TESTING.md` §1 and the homepage (kept out of the
      beta onboarding doc until then so testers aren't sent to a dead link). Uninstall any
      sideloaded test build before installing the Store version.
