// English translations: German source text → English. Keys are the exact German
// strings passed to t(...) in the components. Entries whose value equals the key
// (e.g. 'Status', 'Export PDF') are listed on purpose so coverage is explicit.
export const en = {
  // app shell
  'Verbinde mit Core…': 'Connecting to core…',
  'Arbeite…': 'Working…',
  'Sprache': 'Language',

  // status bar (background activity + cache)
  'Bereit': 'Ready',
  'Komprimiere {n}': 'Compressing {n}',
  'Vorschau lädt {n}': 'Loading preview {n}',
  'Cache füllt': 'Filling cache',
  'Vorschau-Cache': 'Preview cache',
  'Cache {used} / {total} MB ({free} frei)': 'Cache {used} / {total} MB ({free} free)',

  // toolbar
  'Öffnen': 'Open',
  'Neues Fenster': 'New window',
  'Weiteres Dokument in neuem Fenster': 'Another document in a new window',
  'Importieren': 'Import',
  'Speichern': 'Save',
  'Export PDF': 'Export PDF',
  'Als PDF mit Inhaltsverzeichnis exportieren (Auswahl, sonst das ganze Dokument)':
    'Export as a PDF with table of contents (selection, otherwise the whole document)',
  'Auswahl': 'Selection',
  'Ordner': 'Folder',
  'Rückgängig': 'Undo',
  'Wiederholen': 'Redo',
  'Testmodus': 'Test mode',
  'Testmodus: Golden-Master-Vergleich (Entwickler/QA)': 'Test mode: golden-master comparison (developer/QA)',

  // dialogs / notices (frontend)
  'Eine andere Datei öffnen und die ungespeicherten Änderungen verwerfen?':
    'Open another file and discard the unsaved changes?',
  'Gespeichert': 'Saved',
  'PDF exportiert ({count} {entries})': 'PDF exported ({count} {entries})',
  'Eintrag': 'entry',
  'Einträge': 'entries',

  // tree / resize
  'Breite der Baumansicht ziehen': 'Drag to resize the tree pane',

  // preview + zoom
  'Knoten auswählen für die Vorschau': 'Select a node to preview',
  'Keine Vorschau (Ordner oder leer)': 'No preview (folder or empty)',
  'Seite {page} / {total}': 'Page {page} / {total}',
  '{total} Seiten': '{total} pages',
  'Seite {n}': 'Page {n}',
  'kleiner': 'smaller',
  'größer': 'larger',
  'zurücksetzen': 'reset',

  // OS file-drop overlay
  'Dateien ablegen — auf eine Position im Baum (rein/zwischen) für ein genaues Ziel, sonst in {target}':
    'Drop files — onto a position in the tree (into/between) for a precise target, otherwise into {target}',
  'oberste Ebene': 'top level',

  // context menu
  'Neuer Ordner': 'New folder',
  'Umbenennen': 'Rename',
  'Neuer Name': 'New name',
  'Splitten': 'Split',
  'pro Seite': 'per page',
  'N Seiten pro Knoten…': 'N pages per node…',
  'pro Seite → neuer Ordner': 'per page → new folder',
  'N Seiten → neuer Ordner…': 'N pages → new folder…',
  'Seiten pro Knoten:': 'Pages per node:',
  'Ordner anlegen': 'New folder',
  'Aufklappen': 'Expand',
  'Zuklappen': 'Collapse',
  'Alle aufklappen': 'Expand all',
  'Alle zuklappen': 'Collapse all',
  'Status': 'Status',
  'Als PDF exportieren': 'Export as PDF',
  'Auswahl als PDF exportieren ({count})': 'Export selection as PDF ({count})',
  'Löschen': 'Delete',
  'Zusammenführen → 1 PDF ({count})': 'Merge → 1 PDF ({count})',
  'In neuen Ordner ({count})': 'Into a new folder ({count})',
  'Name des neuen Ordners': 'Name of the new folder',
  'Neue Gruppe': 'New group',

  // status labels (German display → English; the data keys stay erfasst/…)
  'Erfasst': 'Recorded',
  'Zu erfassen': 'To record',
  'Vorjahr': 'Prior year',

  // compression controls + method labels
  'JPEG (Graustufen)': 'JPEG (grayscale)',
  'JPEG (Farbe)': 'JPEG (color)',
  'PNG (Graustufen)': 'PNG (grayscale)',
  'Struktur (Farbe erhalten)': 'Structural (color preserved)',
  'Kompressions-DPI': 'Compression DPI',
  'unkomprimierte Fassung': 'uncompressed version',
  'Kompression läuft …': 'Compressing …',
  'bereits komprimiert (keine Quelle)': 'already compressed (no source)',
  'beste': 'best',
  'Lesbarkeit geprüft': 'Readability checked',
  'übernommen': 'applied',
  'Die aktuell angezeigte Komprimierung übernehmen': 'Apply the currently shown compression',
  'rechts drehen': 'rotate right',
  'links drehen': 'rotate left',
}
