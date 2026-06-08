// How-to-use Help content. DE + EN are authoritative (the 🇩🇪/🇬🇧 flags in the modal
// switch to them). Help is ALSO authored for fr, es, ca, ru, uk, hr, ko, la, the
// dialects bar/nds/vie, Celtic cy/ga/gd, yi and the playful tlh/mnn — the modal opens
// in the current UI language when it has its own text here, otherwise falls back to EN.
// So en-US/en-GB and the Elvish novelties qya/sjn show the English help. Non-DE/EN
// texts are best-effort; corrections welcome via the modal footer. Add a language by
// adding a key here + to the HELP map. Keep sections short; this is a quick reference.

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

// --- best-effort translations (corrections welcome via the modal footer) ----------
// Natural languages first, then German dialects, then constructed/rare (weakest —
// please correct). All mirror the de/en section order.

const ca = [
  { t: 'Resum', items: ['BelegTool reuneix PDF, escanejos, fotos, fitxers Office, correus i arxius en un arbre de carpetes, els comprimeix i ho exporta tot com un sol PDF amb índex.', "L'arbre és a l'esquerra; la previsualització del node seleccionat, a la dreta."] },
  { t: 'Obrir i Desar', items: ['📂 Obrir carrega un fitxer .belegtool; els oberts per línia d\'ordres o doble clic s\'obren directament.', '💾 Desar reescriu el mateix fitxer; 💾… desa amb un nom nou.', 'Si hi ha alternatives de compressió, en desar es pregunta si incrustar-les (més gran) o no (més petit).'] },
  { t: 'Importar', items: ['📥 Importar o arrossegar fitxers a l\'arbre.', 'Compatible: PDF, imatges (JPG/PNG/WEBP/HEIC), Office (cal Office instal·lat), correu (EML/MSG), arxius (ZIP/TAR).'] },
  { t: 'Arbre i arrossegar', items: ['Clic selecciona; Ctrl-clic en selecciona diversos, Maj-clic un interval.', 'Arrossega una fila sobre una altra: quart superior = abans, inferior = després, centre d\'una carpeta = a dins.'] },
  { t: 'Teclat', items: ['↑/↓ navegar, ←/→ plegar/desplegar una carpeta.', 'Insert «agafa» el node; mou-lo amb les fletxes, Insert el deixa anar, Esc cancel·la.', 'F2 reanomena; Ctrl+S desar, Ctrl+O obrir, Ctrl+E exportar, Ctrl+Z/Y desfer/refer, Supr esborrar.'] },
  { t: 'Punts d\'estat', items: ['Els nodes nous no tenen estat (sense punt). Clic dret → Estat: groc = Per registrar, verd = Registrat, vermell = Any anterior, o Cap estat.', 'Posar un estat a una carpeta l\'aplica a tot el contingut. Les carpetes mostren punts agregats; un punt negre = uns amb estat i uns sense.'] },
  { t: 'Compressió', items: ['Un punt vermell al davant = compressió encara no decidida.', 'A la previsualització, tria un mètode i aplica «Lesbarkeit geprüft». Si no hi ha res més petit, queda decidit. Atenció: després de desar un node comprimit, l\'original es perd.'] },
  { t: 'Etiquetes', items: ['🏷️ activa les etiquetes; filtra o agrupa per etiqueta; una vista per etiqueta es pot obrir en una finestra nova.'] },
  { t: 'Exportar', items: ['⬇ Export PDF genera un PDF amb índex, enllaços i marcadors; amb una selecció, només aquests.'] },
]

const ru = [
  { t: 'Обзор', items: ['BelegTool собирает PDF, сканы, фото, файлы Office, письма и архивы в одно дерево папок, сжимает и экспортирует всё в один PDF с оглавлением.', 'Дерево слева; предпросмотр выбранного узла справа.'] },
  { t: 'Открыть и Сохранить', items: ['📂 Открыть загружает файл .belegtool; открытые из командной строки/двойным щелчком открываются сразу.', '💾 Сохранить пишет в тот же файл; 💾… — под новым именем.', 'Если есть варианты сжатия, при сохранении спросят, встроить ли их (больше) или нет (меньше).'] },
  { t: 'Импорт', items: ['📥 Импорт или перетаскивание файлов в дерево.', 'Поддержка: PDF, изображения (JPG/PNG/WEBP/HEIC), Office (нужен установленный Office), почта (EML/MSG), архивы (ZIP/TAR).'] },
  { t: 'Дерево и перетаскивание', items: ['Клик выбирает узел; Ctrl-клик — несколько, Shift-клик — диапазон.', 'Перетащите строку на другую: верхняя четверть = до, нижняя = после, середина папки = внутрь.'] },
  { t: 'Клавиатура', items: ['↑/↓ навигация, ←/→ свернуть/развернуть папку.', 'Insert «берёт» узел; двигайте стрелками, Insert опускает, Esc отменяет.', 'F2 переименовать; Ctrl+S сохранить, Ctrl+O открыть, Ctrl+E экспорт, Ctrl+Z/Y отменить/повторить, Del удалить.'] },
  { t: 'Точки статуса', items: ['Новые узлы без статуса (нет точки). ПКМ → Статус: жёлтый = К обработке, зелёный = Обработано, красный = Прошлый год, или Без статуса.', 'Статус на папке применяется ко всему содержимому. У папок — сводные точки; чёрная точка = часть со статусом, часть без.'] },
  { t: 'Сжатие', items: ['Красная точка спереди = решение о сжатии ещё не принято.', 'В предпросмотре выберите метод и примените «Lesbarkeit geprüft». Если меньше не найдено — считается решённым. Внимание: после сохранения сжатого узла оригинал теряется.'] },
  { t: 'Метки', items: ['🏷️ включает метки; фильтр или группировка по метке; вид по метке можно открыть в новом окне.'] },
  { t: 'Экспорт', items: ['⬇ Export PDF создаёт PDF с оглавлением, ссылками и закладками; при выделении — только его.'] },
]

const uk = [
  { t: 'Огляд', items: ['BelegTool збирає PDF, скани, фото, файли Office, листи й архіви в одне дерево тек, стискає та експортує все в один PDF зі змістом.', 'Дерево ліворуч; перегляд вибраного вузла праворуч.'] },
  { t: 'Відкрити і Зберегти', items: ['📂 Відкрити завантажує файл .belegtool; відкриті з командного рядка/подвійним клацанням відкриваються одразу.', '💾 Зберегти пише в той самий файл; 💾… — під новою назвою.', 'Якщо є варіанти стиснення, під час збереження запитають, чи вбудувати їх (більше) чи ні (менше).'] },
  { t: 'Імпорт', items: ['📥 Імпорт або перетягування файлів у дерево.', 'Підтримка: PDF, зображення (JPG/PNG/WEBP/HEIC), Office (потрібен встановлений Office), пошта (EML/MSG), архіви (ZIP/TAR).'] },
  { t: 'Дерево і перетягування', items: ['Клік вибирає вузол; Ctrl-клік — кілька, Shift-клік — діапазон.', 'Перетягніть рядок на інший: верхня чверть = перед, нижня = після, середина теки = всередину.'] },
  { t: 'Клавіатура', items: ['↑/↓ навігація, ←/→ згорнути/розгорнути теку.', 'Insert «бере» вузол; рухайте стрілками, Insert опускає, Esc скасовує.', 'F2 перейменувати; Ctrl+S зберегти, Ctrl+O відкрити, Ctrl+E експорт, Ctrl+Z/Y скасувати/повторити, Del видалити.'] },
  { t: 'Точки статусу', items: ['Нові вузли без статусу (немає точки). ПКМ → Статус: жовтий = До обробки, зелений = Оброблено, червоний = Минулий рік, або Без статусу.', 'Статус на теці застосовується до всього вмісту. У тек — зведені точки; чорна = частина зі статусом, частина без.'] },
  { t: 'Стиснення', items: ['Червона точка спереду = рішення про стиснення ще не ухвалене.', 'У перегляді виберіть метод і застосуйте «Lesbarkeit geprüft». Якщо меншого не знайдено — вважається вирішеним. Увага: після збереження стисненого вузла оригінал втрачається.'] },
  { t: 'Мітки', items: ['🏷️ вмикає мітки; фільтр або групування за міткою; вигляд за міткою можна відкрити в новому вікні.'] },
  { t: 'Експорт', items: ['⬇ Export PDF створює PDF зі змістом, посиланнями та закладками; за вибору — лише його.'] },
]

const hr = [
  { t: 'Pregled', items: ['BelegTool skuplja PDF-ove, skenove, fotografije, Office datoteke, e-poštu i arhive u jedno stablo mapa, sažima ih i izvozi sve kao jedan PDF sa sadržajem.', 'Stablo je lijevo; pregled odabranog čvora desno.'] },
  { t: 'Otvori i Spremi', items: ['📂 Otvori učitava .belegtool; otvoreni iz naredbenog retka/dvoklikom otvaraju se izravno.', '💾 Spremi piše u istu datoteku; 💾… pod novim imenom.', 'Ako postoje alternative sažimanja, pri spremanju se pita ugraditi li ih (veće) ili ne (manje).'] },
  { t: 'Uvoz', items: ['📥 Uvoz ili povlačenje datoteka u stablo.', 'Podržano: PDF, slike (JPG/PNG/WEBP/HEIC), Office (treba instaliran Office), e-pošta (EML/MSG), arhive (ZIP/TAR).'] },
  { t: 'Stablo i povlačenje', items: ['Klik odabire čvor; Ctrl-klik više njih, Shift-klik raspon.', 'Povucite redak na drugi: gornja četvrtina = prije, donja = poslije, sredina mape = unutra.'] },
  { t: 'Tipkovnica', items: ['↑/↓ navigacija, ←/→ sklopi/rasklopi mapu.', 'Insert „uhvati" čvor; pomičite strelicama, Insert spušta, Esc odustaje.', 'F2 preimenuj; Ctrl+S spremi, Ctrl+O otvori, Ctrl+E izvoz, Ctrl+Z/Y poništi/ponovi, Del izbriši.'] },
  { t: 'Točke statusa', items: ['Novi čvorovi nemaju status (nema točke). Desni klik → Status: žuto = Za obradu, zeleno = Obrađeno, crveno = Prošla godina, ili Bez statusa.', 'Status na mapi primjenjuje se na sav sadržaj. Mape pokazuju skupne točke; crna = dio sa statusom, dio bez.'] },
  { t: 'Sažimanje', items: ['Crvena točka sprijeda = odluka o sažimanju još nije donesena.', 'U pregledu odaberite metodu i primijenite „Lesbarkeit geprüft". Ako nema ništa manje, smatra se odlučenim. Pažnja: nakon spremanja sažetog čvora original je izgubljen.'] },
  { t: 'Oznake', items: ['🏷️ uključuje oznake; filtriraj ili grupiraj po oznaci; prikaz po oznaci može se otvoriti u novom prozoru.'] },
  { t: 'Izvoz', items: ['⬇ Export PDF stvara PDF sa sadržajem, poveznicama i knjižnim oznakama; uz odabir, samo njih.'] },
]

const ko = [
  { t: '개요', items: ['BelegTool은 PDF, 스캔, 사진, Office 파일, 이메일, 압축 파일을 하나의 폴더 트리로 모아 압축하고 목차가 있는 단일 PDF로 내보냅니다.', '왼쪽은 트리, 오른쪽은 선택한 노드의 미리보기입니다.'] },
  { t: '열기 및 저장', items: ['📂 열기는 .belegtool 파일을 불러옵니다. 명령줄/더블클릭으로 연 파일은 바로 열립니다.', '💾 저장은 같은 파일에 다시 쓰고, 💾…는 새 이름으로 저장합니다.', '압축 대안이 있으면 저장 시 파일에 포함할지(용량↑) 여부를 묻습니다.'] },
  { t: '가져오기', items: ['📥 가져오기 또는 파일을 트리로 끌어다 놓기.', '지원: PDF, 이미지(JPG/PNG/WEBP/HEIC), Office(설치 필요), 이메일(EML/MSG), 압축(ZIP/TAR).'] },
  { t: '트리와 드래그', items: ['클릭으로 노드 선택, Ctrl-클릭 다중 선택, Shift-클릭 범위 선택.', '행을 다른 행 위로 끌기: 위쪽 1/4 = 앞, 아래 = 뒤, 폴더 가운데 = 안으로.'] },
  { t: '키보드', items: ['↑/↓ 이동, ←/→ 폴더 접기/펼치기.', 'Insert로 노드를 "잡고" 화살표로 이동, Insert로 놓기, Esc로 취소.', 'F2 이름 변경; Ctrl+S 저장, Ctrl+O 열기, Ctrl+E 내보내기, Ctrl+Z/Y 실행취소/다시, Del 삭제.'] },
  { t: '상태 점', items: ['새 노드는 상태 없음(점 없음). 우클릭 → 상태: 노랑 = 처리 예정, 초록 = 처리됨, 빨강 = 전년도, 또는 상태 없음.', '폴더에 상태를 지정하면 모든 내용에 적용됩니다. 폴더는 집계 점을 표시하고, 검은 점은 일부만 상태가 있음을 뜻합니다.'] },
  { t: '압축', items: ['앞쪽의 빨간 점 = 아직 압축이 결정되지 않음.', '미리보기에서 방법을 고르고 "Lesbarkeit geprüft"를 적용하세요. 더 작은 것이 없으면 결정된 것으로 간주됩니다. 주의: 압축된 노드를 저장하면 원본이 사라집니다.'] },
  { t: '태그', items: ['🏷️ 태그 켜기; 태그로 필터/그룹화; 태그 보기를 새 창에서 별도 문서로 열 수 있습니다.'] },
  { t: '내보내기', items: ['⬇ Export PDF는 목차, 링크, 북마크가 있는 PDF를 만듭니다. 선택 시 해당 항목만.'] },
]

const la = [
  { t: 'Conspectus', items: ['BelegTool PDF, imagines scanned, photographemata, tabellas Office, epistulas et archiva in unum arborem directoriorum colligit, comprimit et omnia ut unum PDF cum indice exportat.', 'Arbor sinistra est; praevisio nodi electi dextra.'] },
  { t: 'Aperire et Servare', items: ['📂 Aperire tabellam .belegtool legit; per lineam mandatorum apertae statim aperiuntur.', '💾 Servare in eandem tabellam scribit; 💾… sub novo nomine.', 'Si compressionis alternativae sunt, in servando rogatur num eas includere (maius) necne (minus).'] },
  { t: 'Importare', items: ['📥 Importare aut tabellas in arborem trahere.', 'Sustinentur: PDF, imagines (JPG/PNG/WEBP/HEIC), Office (Office requiritur), epistulae (EML/MSG), archiva (ZIP/TAR).'] },
  { t: 'Arbor et tractus', items: ['Ictus nodum eligit; Ctrl-ictus plures, Shift-ictus intervallum.', 'Ordinem in alium trahe: quadrans superior = ante, inferior = post, medium plicae = intus.'] },
  { t: 'Clavis', items: ['↑/↓ navigare, ←/→ plicam claudere/aperire.', 'Insert nodum "capit"; sagittis move, Insert deponit, Esc revocat.', 'F2 renominat; Ctrl+S servare, Ctrl+O aperire, Ctrl+E exportare, Ctrl+Z/Y revocare/iterare, Del delere.'] },
  { t: 'Puncta status', items: ['Novi nodi sine statu sunt (nullum punctum). Dextrum-ictus → Status: flavum = Notandum, viride = Notatum, rubrum = Annus prior, vel Nullus status.', 'Status in plica omnibus contentis applicatur. Plicae puncta summaria monstrant; punctum nigrum = quaedam cum statu, quaedam sine.'] },
  { t: 'Compressio', items: ['Punctum rubrum ante = de compressione nondum decretum est.', 'In praevisione modum elige et "Lesbarkeit geprüft" applica. Si nihil minus invenitur, decretum habetur. Cave: post nodum compressum servatum, originale perit.'] },
  { t: 'Notae', items: ['🏷️ notas accendit; per notam filtra aut congrega; visus per notam in nova fenestra aperiri potest.'] },
  { t: 'Exportare', items: ['⬇ Export PDF PDF cum indice, nexibus et signaculis creat; cum selectione, ea sola.'] },
]

// German dialects — approximations of the German text (please correct).
const bar = [
  { t: 'Überblick', items: ['BelegTool sammlt PDFs, Scans, Fotos, Office-Dateien, E-Mails und Archive in oan Ordnerbaam, druckt s zam und exportiert ois ois oa PDF mit Inhaltsverzeichnis.', 'Links der Baam, rechts d Vorschau vom gwöhltn Knotn.'] },
  { t: 'Aufmacha & Speichern', items: ['📂 Aufmacha laadt a .belegtool-Datei; übern Kommandozeil/Doppelklick gehngs glei auf.', '💾 Speichern schreibt in de gleiche Datei zruck; 💾… untan neichn Nama.', 'Gibts berechnete Komprimierungs-Alternativn, frogt s Speichern, obs eibaut werdn (gresser) oder ned (kloana).'] },
  { t: 'Importiern', items: ['📥 Importiern oder Dateien in Baam ziagn.', 'Geht: PDF, Buidl (JPG/PNG/WEBP/HEIC), Office (braucht Office), E-Mail (EML/MSG), Archive (ZIP/TAR).'] },
  { t: 'Baam & Ziang', items: ['Klick wöhlt an Knotn; Strg-Klick mehrere, Umschoit-Klick an Beroach.', 'A Zeil auf a andane ziang: obn = davor, untn = danoch, Mittn vo am Ordner = eini.'] },
  { t: 'Tastatur', items: ['↑/↓ navigiern, ←/→ Ordner zua/auf.', 'Einfg greift an Knotn; mit Pfeil verschiebn, Einfg lasst foin, Esc bricht o.', 'F2 umbenenna; Strg+S speichern, Strg+O aufmacha, Strg+E exportiern, Strg+Z/Y zruck/vor, Entf löschn.'] },
  { t: 'Status-Punkt', items: ['Neie Knotn ham koan Status (koa Punkt). Rechtsklick → Status: gööb = Z erfassn, gria = Erfasst, rot = Vorjahr, oder Koa Status.', 'Status afm Ordner güit fia ois drin. Ordner zoagn zammgfasste Punkt; a schwoaza Punkt = teils mit, teils ohne Status.'] },
  { t: 'Komprimierung', items: ['A rota Punkt vorn = üba d Komprimierung is no ned entschiedn.', 'In da Vorschau a Methode wöhln und "Lesbarkeit geprüft" anwendn. Findt si nix Kloanas, güits ois entschiedn. Achtung: nochm Speichern vo am komprimiertn Knotn is s Original weg.'] },
  { t: 'Tags', items: ['🏷️ schoit Tags ei; nach Tags fütern oder gruppiern; a Tag-Ansicht ko ma in am neichn Fenster aufmacha.'] },
  { t: 'Exportiern', items: ['⬇ Export PDF macht a PDF mit Inhaltsverzeichnis, Links und Lesezeichn; bei ana Auswoi grod de.'] },
]

const nds = [
  { t: 'Översicht', items: ['BelegTool sammelt PDFs, Scans, Fotos, Office-Dateien, Mails un Archive in een Ordnerboom, drückt dat tosamen un exporteert allns as een PDF mit Inhoolt.', 'Links de Boom, rechts de Vörschau vun den utwählten Knütt.'] },
  { t: 'Opmaken & Sekern', items: ['📂 Opmaken laadt een .belegtool-Datei; över de Kommandoreeg/Dubbelklick gaht se direkt op.', '💾 Sekern schrifft in densülven Datei torüch; 💾… ünner nieg Naam.', 'Gifft dat Komprimeer-Alternativen, fraagt dat Sekern, of se inbuut warrt (grötter) oder nich (lütter).'] },
  { t: 'Importeren', items: ['📥 Importeren oder Dateien in den Boom trecken.', 'Geiht: PDF, Biller (JPG/PNG/WEBP/HEIC), Office (bruukt Office), Mail (EML/MSG), Archive (ZIP/TAR).'] },
  { t: 'Boom & Trecken', items: ['Klick wählt een Knütt; Strg-Klick mehr, Ümschalt-Klick een Rebeet.', 'Een Reeg op een annere trecken: baven = vörher, nerrn = naher, Midd vun en Ordner = rin.'] },
  { t: 'Tastatuur', items: ['↑/↓ navigeren, ←/→ Ordner to/op.', 'Insert gript den Knütt; mit Pielen schuven, Insert lett fallen, Esc brickt af.', 'F2 ümnömen; Strg+S sekern, Strg+O opmaken, Strg+E exporteren, Strg+Z/Y torüch/wedder, Entf wegdoon.'] },
  { t: 'Status-Pünkt', items: ['Niege Knütten hebbt keen Status (keen Pünkt). Rechtsklick → Status: geel = To erfaten, gröön = Erfaat, root = Vörjohr, oder Keen Status.', 'Status op en Ordner gellt för allns dorin. Ordner wiest tosamenfaat Pünkt; en swatt Pünkt = deels mit, deels ahn Status.'] },
  { t: 'Komprimeren', items: ['En root Pünkt vörn = över de Komprimeren is noch nich beslaten.', 'In de Vörschau en Methood utwählen un "Lesbarkeit geprüft" bruken. Find sik nix Lütteres, gellt dat as beslaten. Acht: na dat Sekern vun en komprimeert Knütt is dat Original weg.'] },
  { t: 'Tags', items: ['🏷️ maakt Tags an; na Tags filtern oder gruppeern; en Tag-Ansicht kann in en nieg Finster opmaakt warrn.'] },
  { t: 'Exporteren', items: ['⬇ Export PDF maakt en PDF mit Inhoolt, Links un Leestekens; bi en Utwahl bloots de.'] },
]

const vie = [
  { t: 'Überblick', items: ['BelegTool sammöt PDFs, Scans, Fotos, Office-Dateien, E-Mails und Archive in an Ordnerbaam, druckts zsamm und exportierts ois oa PDF mitm Inhoitsverzeichnis.', 'Links da Baam, rechts d Voschau vom auswöhtn Knotn.'] },
  { t: 'Aufmochn & Speichern', items: ['📂 Aufmochn ladt a .belegtool-Datei; üba d Kommandozeun/Doppööklick gengas glei auf.', '💾 Speichern schreibt in de söbe Datei zruck; 💾… untam neichn Nomm.', 'Gibts berechnete Komprimierungs-Oitanativn, frogt s Speichern, obs eibaut wean (gressa) oda ned (kloana).'] },
  { t: 'Importiern', items: ['📥 Importiern oda Dateien in Baam ziagn.', 'Geht: PDF, Buidln (JPG/PNG/WEBP/HEIC), Office (brauchts Office), E-Mail (EML/MSG), Archive (ZIP/TAR).'] },
  { t: 'Baam & Ziang', items: ['Klick wöht an Knotn; Strg-Klick mehrane, Umschoit-Klick an Beraich.', 'A Zeun auf a aundane ziang: obm = davoa, untn = danoch, Mittn vo am Ordna = eine.'] },
  { t: 'Tastatua', items: ['↑/↓ navigian, ←/→ Ordna zua/auf.', 'Einfg greift an Knotn; mit Pfeu vaschiabn, Einfg losst foin, Esc bricht o.', 'F2 umbenenna; Strg+S speichern, Strg+O aufmochn, Strg+E exportiern, Strg+Z/Y zruck/vua, Entf löschn.'] },
  { t: 'Status-Punkt', items: ['Neiche Knotn haum kan Status (kan Punkt). Rechtsklick → Status: göb = Z erfossn, grea = Erfosst, rot = Voajoa, oda Kan Status.', 'Status aufm Ordna güit fia ois drin. Ordna zagn zaummgfosste Punkt; a schwoaza Punkt = teus mit, teus ohne Status.'] },
  { t: 'Komprimierung', items: ['A rota Punkt voa = üba d Komprimierung is no ned entschiedn.', 'In da Voschau a Methode auswöhn und "Lesbarkeit geprüft" auwendn. Findt si nix Kloanas, güits ois entschiedn. Ochtung: nochm Speichern vo am komprimiatn Knotn is s Original weg.'] },
  { t: 'Tags', items: ['🏷️ schoit Tags ei; noch Tags füten oda gruppian; a Tag-Ansicht ko ma in am neichn Fensta aufmochn.'] },
  { t: 'Exportiern', items: ['⬇ Export PDF mocht a PDF mitm Inhoitsverzeichnis, Links und Lesezeichn; bei ana Auswoi grod de.'] },
]

// Celtic + Yiddish — rough best-effort, please correct.
const cy = [
  { t: 'Trosolwg', items: ['Mae BelegTool yn casglu PDFs, sganiau, lluniau, ffeiliau Office, e-byst ac archifau mewn un goeden ffolderi, eu cywasgu a\'u hallforio i gyd fel un PDF gyda thabl cynnwys.', 'Mae\'r goeden ar y chwith; rhagolwg y nod a ddewiswyd ar y dde.'] },
  { t: 'Agor a Chadw', items: ['📂 Agor yn llwytho ffeil .belegtool; mae rhai a agorwyd o\'r llinell orchymyn yn agor yn syth.', '💾 Cadw yn ailysgrifennu\'r un ffeil; 💾… o dan enw newydd.', 'Os oes dewisiadau cywasgu, mae cadw\'n gofyn a ddylid eu mewnosod (mwy) ai peidio (llai).'] },
  { t: 'Mewnforio', items: ['📥 Mewnforio neu lusgo ffeiliau i\'r goeden.', 'Cefnogir: PDF, delweddau (JPG/PNG/WEBP/HEIC), Office (angen Office), e-bost (EML/MSG), archifau (ZIP/TAR).'] },
  { t: 'Coeden a llusgo', items: ['Clic yn dewis nod; Ctrl-glic sawl un, Shift-glic ystod.', 'Llusgwch res ar un arall: chwarter uchaf = o flaen, gwaelod = ar ôl, canol ffolder = i mewn.'] },
  { t: 'Bysellfwrdd', items: ['↑/↓ llywio, ←/→ cau/agor ffolder.', 'Insert yn "gafael" nod; symudwch â\'r saethau, Insert i\'w ollwng, Esc i ganslo.', 'F2 ailenwi; Ctrl+S cadw, Ctrl+O agor, Ctrl+E allforio, Ctrl+Z/Y dadwneud/ailwneud, Del dileu.'] },
  { t: 'Dotiau statws', items: ['Nid oes statws gan nodau newydd (dim dot). Clic dde → Statws: melyn = I\'w gofnodi, gwyrdd = Wedi\'i gofnodi, coch = Blwyddyn flaenorol, neu Dim statws.', 'Mae gosod statws ar ffolder yn berthnasol i\'r cynnwys i gyd. Mae ffolderi\'n dangos dotiau cyfun; mae dot du = rhai â statws, rhai heb.'] },
  { t: 'Cywasgu', items: ['Dot coch ar y blaen = heb benderfynu ar gywasgu eto.', 'Yn y rhagolwg, dewiswch ddull a chymhwyso "Lesbarkeit geprüft". Os na cheir dim llai, fe\'i hystyrir wedi\'i benderfynu. Sylwer: ar ôl cadw nod wedi\'i gywasgu, mae\'r gwreiddiol wedi mynd.'] },
  { t: 'Tagiau', items: ['🏷️ yn troi tagiau ymlaen; hidlo neu grwpio yn ôl tag; gellir agor golwg tag mewn ffenestr newydd.'] },
  { t: 'Allforio', items: ['⬇ Export PDF yn creu PDF gyda thabl cynnwys, dolenni a nodau tudalen; gyda dewis, dim ond y rheini.'] },
]

const ga = [
  { t: 'Forbhreathnú', items: ['Bailíonn BelegTool PDFanna, scananna, grianghraif, comhaid Office, ríomhphoist agus cartlanna i gcrann fillteán amháin, déanann iad a chomhbhrú agus easpórtálann gach rud mar PDF amháin le clár ábhair.', 'Tá an crann ar chlé; réamhamharc an nóid roghnaithe ar dheis.'] },
  { t: 'Oscail agus Sábháil', items: ['📂 Osclaíonn comhad .belegtool; osclaíonn cinn ón líne ordaithe go díreach.', '💾 Sábháil scríobhann sa chomhad céanna; 💾… faoi ainm nua.', 'Má tá roghanna comhbhrú ann, fiafraítear agus tú ag sábháil ar cheart iad a leabú (níos mó) nó nár cheart (níos lú).'] },
  { t: 'Iompórtáil', items: ['📥 Iompórtáil nó comhaid a tharraingt isteach sa chrann.', 'Tacaithe: PDF, íomhánna (JPG/PNG/WEBP/HEIC), Office (Office de dhíth), ríomhphost (EML/MSG), cartlanna (ZIP/TAR).'] },
  { t: 'Crann agus tarraingt', items: ['Roghnaíonn cliceáil nód; Ctrl-chliceáil roinnt, Shift-chliceáil raon.', 'Tarraing ró ar cheann eile: ceathrú uachtarach = roimh, bun = tar éis, lár fillteáin = isteach.'] },
  { t: 'Méarchlár', items: ['↑/↓ nascleanúint, ←/→ fillteán a laghdú/leathnú.', 'Beireann Insert ar an nód; bog le saigheada, Insert chun é a scaoileadh, Esc chun cealú.', 'F2 athainmnigh; Ctrl+S sábháil, Ctrl+O oscail, Ctrl+E easpórtáil, Ctrl+Z/Y cealaigh/athdhéan, Del scrios.'] },
  { t: 'Poncanna stádais', items: ['Níl stádas ag nóid nua (gan ponc). Deaschliceáil → Stádas: buí = Le taifeadadh, glas = Taifeadta, dearg = Bliain roimhe, nó Gan stádas.', 'Baineann stádas ar fhillteán leis an ábhar ar fad. Taispeánann fillteáin poncanna comhiomlána; ciallaíonn ponc dubh = cuid le stádas, cuid gan.'] },
  { t: 'Comhbhrú', items: ['Ponc dearg chun tosaigh = níor socraíodh an comhbhrú fós.', 'San réamhamharc, roghnaigh modh agus cuir "Lesbarkeit geprüft" i bhfeidhm. Mura bhfaightear aon rud níos lú, meastar é socraithe. Aire: tar éis nód comhbhrúite a shábháil, tá an bunleagan imithe.'] },
  { t: 'Clibeanna', items: ['🏷️ cuireann clibeanna ar siúl; scag nó grúpáil de réir clibe; is féidir amharc clibe a oscailt i bhfuinneog nua.'] },
  { t: 'Easpórtáil', items: ['⬇ Export PDF cruthaíonn PDF le clár ábhair, naisc agus leabharmharcanna; le roghnúchán, iadsan amháin.'] },
]

const gd = [
  { t: 'Foir-shealladh', items: ['Bidh BelegTool a\' cruinneachadh PDFan, sganaidhean, dealbhan, faidhlichean Office, puist-d agus tasglannan ann an aon chraobh phasgan, gan teannachadh agus a\' às-phortadh a h-uile càil mar aon PDF le clàr-innse.', 'Tha a\' chraobh air an taobh chlì; ro-shealladh an nòd a thagh thu air an taobh dheas.'] },
  { t: 'Fosgail is Sàbhail', items: ['📂 Fosgail a\' luchdadh faidhle .belegtool; bidh feadhainn on loidhne-àithne a\' fosgladh sa bhad.', '💾 Sàbhail a\' sgrìobhadh dhan aon fhaidhle; 💾… fo ainm ùr.', 'Ma tha roghainnean teannachaidh ann, faighnichear nuair a shàbhalas tu am bu chòir an leabachadh (nas motha) no nach bu chòir (nas lugha).'] },
  { t: 'Ion-phortadh', items: ['📥 Ion-phortadh no faidhlichean a shlaodadh dhan chraoibh.', 'Le taic: PDF, dealbhan (JPG/PNG/WEBP/HEIC), Office (feumar Office), post-d (EML/MSG), tasglannan (ZIP/TAR).'] },
  { t: 'Craobh is slaodadh', items: ['Taghaidh briogadh nòd; Ctrl-bhriogadh grunn, Shift-bhriogadh raon.', 'Slaod sreath air fear eile: cairteal àrd = ron, bonn = às dèidh, meadhan pasgain = a-steach.'] },
  { t: 'Meur-chlàr', items: ['↑/↓ seòladh, ←/→ pasgan a dhùnadh/fhosgladh.', 'Glacaidh Insert an nòd; gluais le saighdean, Insert ga leigeil, Esc gus sgur.', 'F2 ath-ainmich; Ctrl+S sàbhail, Ctrl+O fosgail, Ctrl+E às-phortadh, Ctrl+Z/Y neo-dhèan/ath-dhèan, Del sguab às.'] },
  { t: 'Dotagan inbhe', items: ['Chan eil inbhe aig nòdan ùra (gun dotag). Briogadh deas → Inbhe: buidhe = Ri chlàradh, uaine = Clàraichte, dearg = Bliadhna roimhe, no Gun inbhe.', 'Tha inbhe air pasgan a\' buntainn ris an t-susbaint gu lèir. Seallaidh pasganan dotagan iomlan; tha dotag dhubh = cuid le inbhe, cuid gun.'] },
  { t: 'Teannachadh', items: ['Dotag dhearg air thoiseach = cha do cho-dhùnadh an teannachadh fhathast.', 'San ro-shealladh, tagh dòigh is cuir "Lesbarkeit geprüft" an sàs. Mura lorgar dad nas lugha, thathar ga mheas air a cho-dhùnadh. An aire: às dèidh nòd teannaichte a shàbhaladh, tha an tùs air falbh.'] },
  { t: 'Tagaichean', items: ['🏷️ a\' cur tagaichean air; sìolaich no buidhnich a rèir taga; gabhaidh sealladh taga fhosgladh ann an uinneag ùr.'] },
  { t: 'Às-phortadh', items: ['⬇ Export PDF a\' cruthachadh PDF le clàr-innse, ceanglaichean is comharran-leabhair; le taghadh, iadsan a-mhàin.'] },
]

const yi = [
  { t: 'איבערבליק', items: ['BelegTool זאמלט PDFs, סקאנס, בילדער, Office־טעקעס, אי־מעילס און ארכיוון אין איין בוים פון פּאַפּקעס, קאָמפּרעסירט זיי און עקספּאָרטירט אַלץ ווי איין PDF מיט אַן אינהאַלט.', 'דער בוים איז לינקס; די פאָרויסיקע אָנבליק פונעם אויסגעקליבענעם קנופּ איז רעכטס.'] },
  { t: 'עפענען און אויפהיטן', items: ['📂 עפענען לאָדט אַ .belegtool־טעקע; די וואָס מע עפנט פון דער קאָמאַנדאָ־ליניע עפנען זיך גלייך.', '💾 אויפהיטן שרייבט אין דער זעלביקער טעקע; 💾… אונטער אַ נייעם נאָמען.', 'אויב ס\'זענען דאָ קאָמפּרעס־אַלטערנאַטיוון, פרעגט מען ביים אויפהיטן צי אַריינצולייגן זיי (גרעסער) צי נישט (קלענער).'] },
  { t: 'אימפּאָרטירן', items: ['📥 אימפּאָרטירן אָדער שלעפּן טעקעס אין בוים.', 'געשטיצט: PDF, בילדער (JPG/PNG/WEBP/HEIC), Office (דאַרף Office), אי־מעיל (EML/MSG), ארכיוון (ZIP/TAR).'] },
  { t: 'בוים און שלעפּן', items: ['אַ קליק קלייבט אויס אַ קנופּ; Ctrl־קליק עטלעכע, Shift־קליק אַ באַרייך.', 'שלעפּ אַ רייע אויף אַן אַנדערער: אויבן = פאַר, אונטן = נאָך, מיטן פון אַ פּאַפּקע = אַריין.'] },
  { t: 'קלאַוויאַטור', items: ['↑/↓ נאַוויגירן, ←/→ פאַרמאַכן/עפענען אַ פּאַפּקע.', 'Insert "כאַפּט" דעם קנופּ; באַוועג מיט פיילן, Insert לאָזט עס פאַלן, Esc אַנולירט.', 'F2 איבערנעמען; Ctrl+S אויפהיטן, Ctrl+O עפענען, Ctrl+E עקספּאָרטירן, Ctrl+Z/Y צוריק/ווידער, Del אויסמעקן.'] },
  { t: 'סטאַטוס־פּינטלעך', items: ['נייע קנעפּ האָבן נישט קיין סטאַטוס (קיין פּינטל). רעכטס־קליק → סטאַטוס: געל = צו פאַרצייכענען, גרין = פאַרצייכנט, רויט = פאַראַיאָר, אָדער קיין סטאַטוס.', 'אַ סטאַטוס אויף אַ פּאַפּקע גילט פאַר אַלץ אינעווייניק. פּאַפּקעס ווייזן צונויפגענומענע פּינטלעך; אַ שוואַרץ פּינטל = טייל מיט, טייל אָן סטאַטוס.'] },
  { t: 'קאָמפּרעסיע', items: ['אַ רויט פּינטל פאָרנט = די קאָמפּרעסיע איז נאָך נישט באַשלאָסן.', 'אין דער פאָרויסיקער אָנבליק, קלייב אַ מעטאָד און נוץ "Lesbarkeit geprüft". געפינט מען נישט קיין קלענערס, רעכנט מען עס פאַר באַשלאָסן. אַכטונג: נאָכן אויפהיטן אַ קאָמפּרעסירטן קנופּ איז דער אָריגינאַל אַוועק.'] },
  { t: 'טאַגן', items: ['🏷️ שאַלט אָן טאַגן; פילטער אָדער גרופּיר לויט טאַג; אַ טאַג־אָנבליק קען מען עפענען אין אַ נייעם פֿענצטער.'] },
  { t: 'עקספּאָרטירן', items: ['⬇ Export PDF שאַפט אַ PDF מיט אַן אינהאַלט, לינקען און צייכנס; מיט אַן אויסקלייב, נאָר זיי.'] },
]

// Constructed / fun (matching the app's existing playful UI translations).
const tlh = [
  { t: 'qen', items: ['BelegTool: PDFmey, nguvmey, mIllogh, Office De\', QInmey, ngaSwI\' je wa\' raSDaq boqHa\'moH, ghochmoH, \'ej wa\' PDFDaq HIjmeH (chovnatlh tu\'lu\').', 'poS: raS. nIH: Sov chovnatlh.'] },
  { t: 'poSmoH \'ej choqmoH', items: ['📂 poSmoH: .belegtool De\' laD. ra\'ghomvo\' poSlu\'bogh teywI\' poSchoH.', '💾 choqmoH: teywI\' rurDaq ghIt; 💾… chu\' pong.', 'boqHa\'ghach DopHommey tu\'lu\'chugh, choqmeH yu\'lu\': chel (tIn) pagh chel (machHa\').'] },
  { t: 'HIj', items: ['📥 HIj pagh raSDaq teywI\' DIn.', 'lo\'laH: PDF, mIllogh (JPG/PNG/WEBP/HEIC), Office (Office poQ), QIn (EML/MSG), ngaS (ZIP/TAR).'] },
  { t: 'raS \'ej DIn', items: ['wIv: pe\'. Ctrl-pe\': law\'. Shift-pe\': \'ay\'.', 'latlhDaq raS DIn: Dung = nungbogh, bIng = veb, botlh = qoD.'] },
  { t: 'naQHom', items: ['↑/↓ leng, ←/→ ngaSwI\' SoQmoH/poSmoH.', 'Insert: raS jon. naQHommey lo\': vIH. Insert: pum. Esc: qIl.', 'F2 pong choH; Ctrl+S choq, Ctrl+O poS, Ctrl+E HIj, Ctrl+Z/Y chID/ghItlh, Del Qaw\'.'] },
  { t: 'Dotmey Dotlh', items: ['raS chu\': Dotlh Hutlh (Dot Hutlh). nIH-pe\' → Dotlh: SuD = qonmeH, SuDqu\' = qonta\', Doq = ben, pagh Dotlh Hutlh.', 'ngaSwI\'Daq Dotlh: Hoch qoD lo\'. ngaSwI\'mey: Dotmey boq; qIj Dot = \'op Dotlh, \'op Hutlh.'] },
  { t: 'boqHa\'ghach', items: ['nung Doq Dot: boqHa\'ghach wIvbe\'lu\'.', 'chovnatlhDaq mIw wIv, "Lesbarkeit geprüft" lo\'. machHa\' tu\'be\'lu\'chugh, wIvlu\'. yep: boqHa\' raS choqlu\'pa\', Hutlh tlhol.'] },
  { t: 'per', items: ['🏷️ per chu\'moH; per pIqmey pagh boqmoH; latlh QorwaghDaq per legh poSlaH.'] },
  { t: 'HIj PDF', items: ['⬇ Export PDF: PDF chenmoH (chovnatlh, rar, pormey); wIvlu\'chugh, chaH neH.'] },
]

const mnn = [
  { t: 'Bello!', items: ['BelegTool poopaye PDF, scan, photo, Office, email, archive banana tree-la, squeeze-a, tutti one PDF poulet (table-la).', 'Tree la left; preview la right. Tank yu!'] },
  { t: 'Open & Save', items: ['📂 Open la .belegtool. Command-line/double-click → open bello directo.', '💾 Save la same file; 💾… new nombre.', 'Compression banana-options → save ask: put inside (gros) o no (petit).'] },
  { t: 'Import', items: ['📥 Import o drag file la tree.', 'OK: PDF, image (JPG/PNG/WEBP/HEIC), Office (need Office), email (EML/MSG), archive (ZIP/TAR).'] },
  { t: 'Tree & drag', items: ['Click = pick uno; Ctrl-click = mucho; Shift-click = range.', 'Drag row la otra: top = before, bottom = after, middle folder = inside-a.'] },
  { t: 'Keyboard', items: ['↑/↓ move, ←/→ folder close/open.', 'Insert grab node; arrow move; Insert drop; Esc no-no.', 'F2 rename; Ctrl+S save, Ctrl+O open, Ctrl+E export, Ctrl+Z/Y undo/redo, Del bye-bye.'] },
  { t: 'Status banana-dots', items: ['New node = no status (no dot). Right-click → Status: yellow = to do, green = done, red = last year, o no status.', 'Status la folder → tutti inside. Folder show dots; black dot = some yes some no.'] },
  { t: 'Compression', items: ['Red dot front = compression no decide yet.', 'Preview: pick method, "Lesbarkeit geprüft" tatata. No smaller → decide. Careful: save compressed → original poopaye gone.'] },
  { t: 'Tags', items: ['🏷️ tags on; filter o group by tag; tag-view open new window. Banana!'] },
  { t: 'Export', items: ['⬇ Export PDF → PDF (table, links, marks); selection → only those. Poulet tiki!'] },
]

// Elvish (Tolkien) — rough best-effort, telegraphic, using attested vocabulary where
// it exists and loanwords (PDF, Office, Status, Tags, index, links…) for modern terms.
// Grammar/mutations are NOT guaranteed — a fluent Quenya/Sindarin speaker should review;
// corrections welcome via the modal footer.
const qya = [
  { t: 'Cenë', items: [
    'BelegTool: PDF, emmar, Office, e-mail, archë → er PDF (index as).',
    'Alda hyarya; cenë forya.',
  ] },
  { t: 'Panta & Hepa', items: [
    '📂 Panta: parma .belegtool. 💾 Hepa; 💾… essë vinya.',
  ] },
  { t: 'Tulta', items: [
    '📥 Tulta aldanna: PDF, emmar, Office (Office mauya), e-mail (EML/MSG), archë (ZIP/TAR).',
  ] },
  { t: 'Alda', items: [
    'Cilë; rimbë: Ctrl. ←/→: colca panta/holta. F2: essë vinya. Del: nancara.',
  ] },
  { t: 'Status', items: [
    'Malina = „zu erfassen", laica = „erfasst", carnë = „Vorjahr", hya munta.',
    'Status colcassë → ilyë hínar.',
  ] },
  { t: 'Compressië', items: [
    'Carnë: compressië lá cestaina. Cenë → cilë → „Lesbarkeit geprüft".',
  ] },
  { t: 'Tags', items: [
    '🏷️ Tags. Tags-nen: hosta hya cilë.',
  ] },
  { t: 'Menta', items: [
    '⬇ Menta PDF: index, links, bookmarks as.',
  ] },
]

const sjn = [
  { t: 'BelegTool', items: [
    'PDF, eml, Office, post, archive → er PDF.',
    'Galadh: hair. Tiro: forn.',
  ] },
  { t: 'Edro & Hebo', items: [
    '📂 Edro: .belegtool. 💾 Hebo; 💾… eneth gwain.',
  ] },
  { t: 'Tolo / Meno', items: [
    '📥 Tolo (import): PDF, eml, Office (Office baur), EML/MSG, ZIP/TAR.',
    '⬇ Meno (export): PDF — index, links, bookmarks.',
  ] },
  { t: 'Galadh', items: [
    'Cilo nod; Ctrl: laew. ←/→: edro galadh. F2: eneth gwain. Risto: rist.',
  ] },
  { t: 'Status', items: [
    'Malen = „zu erfassen", calen = „erfasst", caran = „Vorjahr", egor pen-status.',
  ] },
]

export const HELP = { de, en, 'en-US': en, 'en-GB': en, fr, es, ca, ru, uk, hr, ko, la, bar, nds, vie, cy, ga, gd, yi, tlh, mnn, qya, sjn }

// Pick the help for a UI language, falling back to English when not authored yet.
export function helpFor(lang) {
  return HELP[lang] || HELP.en
}
