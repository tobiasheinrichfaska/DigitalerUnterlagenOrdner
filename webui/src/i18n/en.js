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
  'Vorschau-Cache · {free} MB frei': 'Preview cache · {free} MB free',
  'Cache {used}/{total} MB · {pages}/{doc} Seiten': 'Cache {used}/{total} MB · {pages}/{doc} pages',
  'Cache vergrößern (+50 MB)': 'Enlarge cache (+50 MB)',
  'Cache verkleinern (−50 MB)': 'Shrink cache (−50 MB)',

  // toolbar
  'Öffnen': 'Open',
  'Neues Fenster': 'New window',
  'Weiteres Dokument in neuem Fenster': 'Another document in a new window',
  'Importieren': 'Import',
  'Speichern': 'Save',
  'Speichern unter…': 'Save as…',
  'Export PDF': 'Export PDF',
  // save dialog (compression alternatives)
  'Komprimierungs-Alternativen speichern?': 'Save compression alternatives?',
  '{n} Dokument(e) haben berechnete Komprimierungs-Alternativen.':
    '{n} document(s) have computed compression alternatives.',
  '„Wie geplant" behält die Alternativen in der Datei (größer, beim Öffnen sofort verfügbar). „Original" speichert nur die Basis-Fassung (kleiner; Alternativen werden beim Öffnen neu berechnet).':
    '"As planned" keeps the alternatives in the file (larger, instantly available on reopen). "Original" saves only the base version (smaller; alternatives are recomputed on reopen).',
  'Wie geplant speichern': 'Save as planned',
  'Original speichern': 'Save original',
  'Abbrechen': 'Cancel',
  'Als PDF mit Inhaltsverzeichnis exportieren (Auswahl, sonst das ganze Dokument)':
    'Export as a PDF with table of contents (selection, otherwise the whole document)',
  'Auswahl': 'Selection',
  'Ordner': 'Folder',
  'Rückgängig': 'Undo',
  'Wiederholen': 'Redo',

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
  'Der Ordner „{name}“ enthält nicht ausgewählte Elemente, die mit einbezogen werden. Fortfahren?':
    'Folder “{name}” contains unselected items that will be included. Continue?',
  '„{name}“: den ganzen Ordner einbeziehen? (Abbrechen = nur die ausgewählten Elemente, Ordner ausschließen)':
    '“{name}”: include the whole folder? (Cancel = only the selected items, exclude the folder)',
  'Nur die ausgewählten Elemente verwenden und „{name}“ ausschließen? (Abbrechen = Vorgang abbrechen)':
    'Use only the selected items and exclude “{name}”? (Cancel = cancel the operation)',
  'Zusammenführen → 1 PDF ({count})': 'Merge → 1 PDF ({count})',
  'In neuen Ordner ({count})': 'Into a new folder ({count})',
  'Name des neuen Ordners': 'Name of the new folder',
  'Neue Gruppe': 'New group',

  // tags
  'Tags': 'Tags',
  'Tags ein-/ausschalten': 'Toggle tags on/off',
  '+ Tag': '+ Tag',
  'Tag entfernen': 'Remove tag',
  'Zu Favoriten': 'Add to favourites',
  'Aus Favoriten entfernen': 'Remove from favourites',
  'Favorit hinzufügen': 'Add favourite',

  // tag view bar (search / filtered view / group by tag)
  'Tags suchen…': 'Search tags…',
  'Suche löschen': 'Clear search',
  'Ansicht gefiltert — Umsortieren aus': 'View filtered — restructuring off',
  'Nach Tag gruppieren': 'Group by tag',
  'Nach Tag gruppiert — Umsortieren aus': 'Grouped by tag — restructuring off',
  'Belege nach Tag gruppieren (nur Ansicht)': 'Group documents by tag (view only)',
  'Ohne Tags': 'Untagged',
  'In neuem Fenster öffnen': 'Open in new window',
  'Ansicht in neuem Fenster geöffnet ({count})': 'View opened in a new window ({count})',
  'Ansicht zurücksetzen': 'Reset view',
  'In der gefilterten Ansicht nicht verfügbar': 'Not available in the filtered view',

  // status labels (German display → English; the data keys stay erfasst/…)
  'Erfasst': 'Recorded',
  'Zu erfassen': 'To record',
  'Vorjahr': 'Prior year',
  'Kein Status': 'No status',
  'Status (gesamter Inhalt)': 'Status (entire contents)',
  'Komprimierung noch nicht entschieden': 'Compression not yet decided',
  'Teils ohne Status': 'Some without status',

  // export dialog
  'PDF exportieren': 'Export PDF',
  'Inhaltsverzeichnis': 'Table of contents',
  'mit anklickbaren Links': 'with clickable links',
  'Stichwortverzeichnis (nach Tags)': 'Tag index',
  'PDF-Lesezeichen (Seitenleiste)': 'PDF bookmarks (sidebar)',
  'Exportieren': 'Export',
  'Keine Tags im Dokument': 'No tags in the document',

  // help
  'Hilfe': 'Help',
  'Schließen': 'Close',
  'Übersetzungsfehler melden:': 'Report a translation error:',

  // compression controls + method labels
  'JPEG (Graustufen)': 'JPEG (grayscale)',
  'JPEG (Farbe)': 'JPEG (color)',
  'PNG (Graustufen)': 'PNG (grayscale)',
  'Struktur (Farbe erhalten)': 'Structural (color preserved)',
  'Kompressions-DPI': 'Compression DPI',
  'Größe der aktuellen Auswahl bei diesem DPI': 'Size of the current choice at this DPI',
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
