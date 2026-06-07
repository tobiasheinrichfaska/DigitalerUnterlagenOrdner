// How-to-use Help content. DE + EN are authoritative; FR + ES are best-effort
// machine translations; every other UI language falls back to EN (the 🇩🇪/🇬🇧 flags
// in the modal always switch to the authoritative German / English text). Corrections
// are welcome via the report links in the modal footer — add a language by adding a
// key here. Keep sections short; this is a quick reference, not a manual.

export const HELP_FLAG_LANGS = ['de', 'en'] // the two authoritative versions (flag buttons)

const de = [
  { t: 'Überblick', items: [
    'BelegTool sammelt PDFs, Scans, Fotos, Office-Dateien, E-Mails und Archive in einem Ordnerbaum, komprimiert und exportiert alles als ein PDF mit Inhaltsverzeichnis.',
    'Links der Baum, rechts die Seitenvorschau des gewählten Knotens.',
  ] },
  { t: 'Öffnen & Speichern', items: [
    '📂 Öffnen lädt eine .belegtool-Datei. Per Kommandozeile / Doppelklick geöffnete Dateien werden direkt geöffnet.',
    '💾 Speichern sichert in dieselbe Datei zurück; 💾… speichert unter neuem Namen.',
    'Gibt es berechnete Komprimierungs-Alternativen, fragt das Speichern, ob sie in die Datei eingebettet werden (größer, sofort beim Öffnen da) oder nicht (kleiner).',
  ] },
  { t: 'Importieren', items: [
    '📥 Importieren oder Dateien per Drag-and-drop in den Baum ziehen.',
    'Unterstützt: PDF, Bilder (JPG/PNG/WEBP/HEIC), Office (Word/Excel/PowerPoint – benötigt installiertes Office), E-Mail (EML/MSG), Archive (ZIP/TAR).',
  ] },
  { t: 'Baum & Drag-and-drop', items: [
    'Klick wählt einen Knoten; Strg-Klick wählt mehrere, Umschalt-Klick einen Bereich.',
    'Eine Zeile auf eine andere ziehen: oberes Viertel = davor, unteres = danach, Mitte eines Ordners = hinein.',
    'Am unteren Ende einer Ebene zeigt ein Geist die Position – links/rechts wählt die Verschachtelungs-Ebene.',
  ] },
  { t: 'Tastatur', items: [
    '↑/↓ navigieren, ←/→ Ordner zu-/aufklappen (oder eine Ebene rein/raus).',
    'Einfg „greift" den Knoten; mit Pfeilen optisch verschieben, Einfg lässt fallen (ein Schritt), Esc bricht ab.',
    'F2 benennt den gewählten Knoten um.',
    'Strg+S speichern, Strg+O öffnen, Strg+E exportieren, Strg+N neues Fenster, Strg+Z/Y rückgängig/wiederholen, Entf löschen.',
  ] },
  { t: 'Status-Punkte', items: [
    'Neue Knoten haben keinen Status (kein Punkt). Rechtsklick → Status setzt: Gelb = Zu erfassen, Grün = Erfasst, Rot = Vorjahr, oder Kein Status.',
    'Status auf einem Ordner setzt alle enthaltenen Dokumente (Kinder und Enkel).',
    'Ordner zeigen die enthaltenen Status als kleine Punkte; ein schwarzer Punkt heißt: teils mit, teils ohne Status.',
  ] },
  { t: 'Komprimierung', items: [
    'Ein roter Punkt vorne heißt: über die Komprimierung dieses Knotens ist noch nicht entschieden.',
    'Im Vorschaubereich eine Methode wählen und „Lesbarkeit geprüft" anwenden – der rote Punkt verschwindet.',
    'Findet sich nichts Kleineres, gilt das als entschieden (kein roter Punkt) und wird nicht erneut berechnet.',
    'Achtung: Nach dem Speichern eines komprimierten Knotens ist das Original weg – die Komprimierung ist endgültig.',
  ] },
  { t: 'Tags', items: [
    '🏷️ schaltet Tags ein. Knoten lassen sich frei beschriften.',
    'Damit nach Tags filtern oder gruppieren; eine Tag-Ansicht lässt sich in einem neuen Fenster als eigenes Dokument öffnen.',
  ] },
  { t: 'Exportieren', items: [
    '⬇ Export PDF erzeugt ein PDF mit Inhaltsverzeichnis, klickbaren Links und Lesezeichen; bei einer Auswahl nur diese.',
  ] },
]

const en = [
  { t: 'Overview', items: [
    'BelegTool collects PDFs, scans, photos, Office files, e-mails and archives into one folder tree, compresses them and exports everything as a single PDF with a table of contents.',
    'The tree is on the left; the page preview of the selected node is on the right.',
  ] },
  { t: 'Open & Save', items: [
    '📂 Open loads a .belegtool file. Files opened via the command line / double-click open directly.',
    '💾 Save writes back to the same file; 💾… saves under a new name.',
    'If computed compression alternatives exist, saving asks whether to embed them in the file (larger, instantly available on reopen) or not (smaller).',
  ] },
  { t: 'Import', items: [
    '📥 Import, or drag and drop files onto the tree.',
    'Supported: PDF, images (JPG/PNG/WEBP/HEIC), Office (Word/Excel/PowerPoint – needs Office installed), e-mail (EML/MSG), archives (ZIP/TAR).',
  ] },
  { t: 'Tree & drag-and-drop', items: [
    'Click selects a node; Ctrl-click selects several, Shift-click a range.',
    'Drag a row onto another: top quarter = before, bottom = after, middle of a folder = inside.',
    'At the bottom of a level a ghost shows the drop spot – move left/right to choose the nesting level.',
  ] },
  { t: 'Keyboard', items: [
    '↑/↓ navigate, ←/→ collapse/expand a folder (or step out/in).',
    'Insert "grabs" the node; move it optically with the arrows, Insert drops it (one step), Esc cancels.',
    'F2 renames the selected node.',
    'Ctrl+S save, Ctrl+O open, Ctrl+E export, Ctrl+N new window, Ctrl+Z/Y undo/redo, Del delete.',
  ] },
  { t: 'Status dots', items: [
    'New nodes have no status (no dot). Right-click → Status sets: yellow = To record, green = Recorded, red = Prior year, or No status.',
    'Setting a status on a folder applies it to every document inside (children and grandchildren).',
    'Folders show their contained statuses as small dots; a black dot means: some with, some without a status.',
  ] },
  { t: 'Compression', items: [
    'A red dot at the front means: no compression decision has been made for this node yet.',
    'In the preview, pick a method and apply "Lesbarkeit geprüft" (readability checked) – the red dot disappears.',
    'If nothing smaller is found, that counts as decided (no red dot) and is not recomputed.',
    'Note: after saving a compressed node the original is gone – compression is final.',
  ] },
  { t: 'Tags', items: [
    '🏷️ turns tags on. Nodes can be freely labelled.',
    'Filter or group by tag; a tag view can be opened in a new window as its own document.',
  ] },
  { t: 'Export', items: [
    '⬇ Export PDF produces a PDF with a table of contents, clickable links and bookmarks; with a selection, only those.',
  ] },
]

const fr = [
  { t: 'Aperçu', items: [
    'BelegTool rassemble des PDF, scans, photos, fichiers Office, e-mails et archives dans une arborescence de dossiers, les compresse et exporte le tout en un seul PDF avec table des matières.',
    "L'arborescence est à gauche ; l'aperçu des pages du nœud sélectionné est à droite.",
  ] },
  { t: 'Ouvrir & Enregistrer', items: [
    '📂 Ouvrir charge un fichier .belegtool. Les fichiers ouverts via la ligne de commande / double-clic s’ouvrent directement.',
    '💾 Enregistrer réécrit dans le même fichier ; 💾… enregistre sous un nouveau nom.',
    "Si des alternatives de compression existent, l'enregistrement demande s'il faut les intégrer (fichier plus gros, disponibles à la réouverture) ou non (plus petit).",
  ] },
  { t: 'Importer', items: [
    '📥 Importer, ou glisser-déposer des fichiers sur l’arborescence.',
    'Pris en charge : PDF, images (JPG/PNG/WEBP/HEIC), Office (Word/Excel/PowerPoint – nécessite Office installé), e-mail (EML/MSG), archives (ZIP/TAR).',
  ] },
  { t: 'Arborescence & glisser-déposer', items: [
    'Un clic sélectionne un nœud ; Ctrl-clic en sélectionne plusieurs, Maj-clic une plage.',
    "Glisser une ligne sur une autre : quart supérieur = avant, bas = après, milieu d'un dossier = à l'intérieur.",
    "En bas d'un niveau, un fantôme indique l'emplacement – gauche/droite choisit le niveau d'imbrication.",
  ] },
  { t: 'Clavier', items: [
    '↑/↓ naviguer, ←/→ replier/déplier un dossier (ou sortir/entrer d’un niveau).',
    'Inser « saisit » le nœud ; déplacez-le visuellement avec les flèches, Inser le dépose (une étape), Échap annule.',
    'F2 renomme le nœud sélectionné.',
    'Ctrl+S enregistrer, Ctrl+O ouvrir, Ctrl+E exporter, Ctrl+N nouvelle fenêtre, Ctrl+Z/Y annuler/rétablir, Suppr supprimer.',
  ] },
  { t: 'Pastilles de statut', items: [
    'Les nouveaux nœuds n’ont pas de statut (pas de pastille). Clic droit → Statut : jaune = À saisir, vert = Saisi, rouge = Année précédente, ou Aucun statut.',
    'Définir un statut sur un dossier l’applique à tous les documents qu’il contient (enfants et petits-enfants).',
    'Les dossiers affichent les statuts contenus sous forme de petites pastilles ; une pastille noire signifie : certains avec, d’autres sans statut.',
  ] },
  { t: 'Compression', items: [
    'Une pastille rouge à l’avant signifie : aucune décision de compression n’a encore été prise pour ce nœud.',
    'Dans l’aperçu, choisissez une méthode et appliquez « Lesbarkeit geprüft » (lisibilité vérifiée) – la pastille rouge disparaît.',
    'Si rien de plus petit n’est trouvé, cela compte comme décidé (pas de pastille rouge) et n’est pas recalculé.',
    'Attention : après l’enregistrement d’un nœud compressé, l’original est perdu – la compression est définitive.',
  ] },
  { t: 'Tags', items: [
    '🏷️ active les tags. Les nœuds peuvent être librement étiquetés.',
    'Filtrer ou grouper par tag ; une vue par tag peut être ouverte dans une nouvelle fenêtre comme document à part.',
  ] },
  { t: 'Exporter', items: [
    '⬇ Export PDF produit un PDF avec table des matières, liens cliquables et signets ; avec une sélection, uniquement ceux-ci.',
  ] },
]

const es = [
  { t: 'Resumen', items: [
    'BelegTool reúne PDF, escaneos, fotos, archivos de Office, correos y archivos comprimidos en un árbol de carpetas, los comprime y exporta todo como un único PDF con índice.',
    'El árbol está a la izquierda; la vista previa de páginas del nodo seleccionado, a la derecha.',
  ] },
  { t: 'Abrir y Guardar', items: [
    '📂 Abrir carga un archivo .belegtool. Los archivos abiertos por línea de comandos / doble clic se abren directamente.',
    '💾 Guardar reescribe el mismo archivo; 💾… guarda con un nombre nuevo.',
    'Si existen alternativas de compresión calculadas, al guardar se pregunta si incrustarlas (archivo mayor, disponibles al reabrir) o no (menor).',
  ] },
  { t: 'Importar', items: [
    '📥 Importar, o arrastrar y soltar archivos en el árbol.',
    'Compatible: PDF, imágenes (JPG/PNG/WEBP/HEIC), Office (Word/Excel/PowerPoint – requiere Office instalado), correo (EML/MSG), archivos (ZIP/TAR).',
  ] },
  { t: 'Árbol y arrastrar y soltar', items: [
    'Un clic selecciona un nodo; Ctrl-clic selecciona varios, Mayús-clic un rango.',
    'Arrastra una fila sobre otra: cuarto superior = antes, inferior = después, centro de una carpeta = dentro.',
    'Al final de un nivel, un fantasma muestra el destino – izquierda/derecha elige el nivel de anidación.',
  ] },
  { t: 'Teclado', items: [
    '↑/↓ navegar, ←/→ plegar/desplegar una carpeta (o salir/entrar un nivel).',
    'Insert «agarra» el nodo; muévelo visualmente con las flechas, Insert lo suelta (un paso), Esc cancela.',
    'F2 renombra el nodo seleccionado.',
    'Ctrl+S guardar, Ctrl+O abrir, Ctrl+E exportar, Ctrl+N ventana nueva, Ctrl+Z/Y deshacer/rehacer, Supr eliminar.',
  ] },
  { t: 'Puntos de estado', items: [
    'Los nodos nuevos no tienen estado (sin punto). Clic derecho → Estado: amarillo = Por registrar, verde = Registrado, rojo = Año anterior, o Sin estado.',
    'Asignar un estado a una carpeta lo aplica a todos los documentos que contiene (hijos y nietos).',
    'Las carpetas muestran los estados contenidos como puntos pequeños; un punto negro significa: unos con estado y otros sin él.',
  ] },
  { t: 'Compresión', items: [
    'Un punto rojo al inicio significa: aún no se ha decidido la compresión de este nodo.',
    'En la vista previa, elige un método y aplica «Lesbarkeit geprüft» (legibilidad comprobada) – el punto rojo desaparece.',
    'Si no se encuentra nada más pequeño, cuenta como decidido (sin punto rojo) y no se recalcula.',
    'Atención: tras guardar un nodo comprimido, el original se pierde – la compresión es definitiva.',
  ] },
  { t: 'Etiquetas', items: [
    '🏷️ activa las etiquetas. Los nodos se pueden etiquetar libremente.',
    'Filtra o agrupa por etiqueta; una vista por etiqueta puede abrirse en una ventana nueva como documento propio.',
  ] },
  { t: 'Exportar', items: [
    '⬇ Export PDF genera un PDF con índice, enlaces y marcadores; con una selección, solo esos.',
  ] },
]

export const HELP = { de, en, fr, es }

// Pick the help for a UI language, falling back to English when not authored yet.
export function helpFor(lang) {
  return HELP[lang] || HELP.en
}
