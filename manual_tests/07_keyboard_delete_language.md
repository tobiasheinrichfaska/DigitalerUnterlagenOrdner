# 07 — Tastatur, Löschen mehrerer Einträge, Sprache

Umbauen des Baums mit der Tastatur, Löschen einer Mehrfachauswahl mit Rückfrage bei Ordnern, Umbenennen direkt in der Zeile, die **Sprachauswahl** und die Darstellung (verschiebbare Trennlinie, Seitenanzeige).

---

## MT-50: Mit der Tastatur bewegen, zuklappen und Einträge „tragen“

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Einen Eintrag anklicken und mit **↑ / ↓** die Markierung bewegen.
2. Auf einem Ordner **→** zum Aufklappen und **←** zum Zuklappen drücken (oder den Pfeil vor dem Ordner anklicken).
3. Einen Eintrag markieren und **Einfg** drücken. Mit **↑ / ↓** umsortieren, mit **→** in den Ordner darüber schieben, mit **←** eine Ebene herausholen.
4. **Einfg** erneut drücken, um abzulegen. Den Vorgang wiederholen, aber mit **Esc** beenden.

**Erwartet:**
- **↑ / ↓** bewegen sich durch die **sichtbaren** Zeilen und überspringen zugeklappte Ordner.
- Nach **Einfg** hat die Zeile einen gestrichelten Rahmen. Solange getragen wird, wandert der Eintrag **nur optisch**.
- **Einfg** legt ab (eine rückgängig machbare Verschiebung), **Esc** stellt den Ausgangszustand ohne Änderung wieder her.
- *Nicht offensichtlich:* Die Verschiebe-Taste ist **Einfg** und nicht Strg+Pfeil, weil Strg für die Mehrfachauswahl gebraucht wird.
- Zugeklappte Ordner werden **in der Datei gemerkt** (speichern, neu öffnen → weiterhin zugeklappt).

---

## MT-50b: Mehrere Einträge auf einmal tragen

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet, alle Ordner sind aufgeklappt.

**Schritte:**
1. Mit **Strg+Klick** zwei oder mehr Einträge markieren. Merken, welcher der **Haupteintrag** ist – der mit der Vorschau und der kräftigsten Hervorhebung, in der Regel der zuletzt angeklickte.
2. **Einfg** drücken.
3. Mit **↑ / ↓** (und bei Bedarf **→ / ←**) an eine neue Stelle bewegen und mit **Einfg** ablegen.
4. **Strg+Z** drücken.

**Erwartet:**
- Schritt 2: Der Haupteintrag bekommt den gestrichelten Rahmen.
- Schritt 3: Während des Tragens bewegt sich **nur der Haupteintrag**; die übrigen markierten Zeilen **bleiben stehen, sind aber weiter markiert**.
- *Nicht offensichtlich:* Die übrigen Einträge wandern nicht sichtbar mit – sie springen erst **beim Ablegen** zum Haupteintrag.
- Beim Ablegen ziehen **alle markierten Einträge gemeinsam** an die neue Stelle, in ihrer bisherigen Reihenfolge und als **ein** Schritt. Schritt 4 nimmt die ganze Verschiebung auf einmal zurück.
- Ablegen, ohne den Haupteintrag bewegt zu haben, verändert nichts.

---

## MT-51: Mehrere Einträge löschen – alle auf einmal, Markierung rückt nach

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet, alle Ordner sind aufgeklappt.

**Schritte:**
1. Mit **Strg+Klick** drei voneinander unabhängige Dokumente in verschiedenen Ordnern markieren.
2. **Entf** drücken – oder Rechtsklick auf einen davon → **Löschen (3)**.
3. Auf die Markierung nach dem Löschen achten und einmal **↶ Rückgängig** klicken.

**Erwartet:**
- **Alle** markierten Einträge werden in **einem** Rückgängig-Schritt gelöscht. Der Menüpunkt nennt die Anzahl, z. B. **Löschen (3)**.
- Die Markierung **rückt von selbst** auf einen verbleibenden Eintrag – ein weiteres Löschen braucht keinen zusätzlichen Klick.
- **↶** holt alle drei auf einmal zurück.

---

## MT-52: Löschen, wenn ein Ordner in der Markierung ist (Rückfragen)

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet, alle Ordner sind aufgeklappt.

**Schritte:**
1. **Nur** den Ordner **03 Vorjahr 2024** markieren (er hat Inhalt) → **Entf**. Die Rückfrage mit **Abbrechen** beantworten, dann wiederholen und mit **OK** bestätigen. Danach **↶ Rückgängig**.
2. Den Ordner **01 Eingangsrechnungen** **und** ein Dokument daraus (mit Strg+Klick) markieren → **Entf**. Die erste Rückfrage mit **OK** beantworten. Danach **↶ Rückgängig**.
3. Schritt 2 wiederholen, die erste Rückfrage mit **Abbrechen** und die zweite mit **OK** beantworten.
4. Einen Ordner und **alle** seine Inhalte markieren → **Entf**.

**Erwartet:**
- Schritt 1: Es erscheint die Warnung „Der Ordner „03 Vorjahr 2024“ enthält nicht ausgewählte Elemente, die mit einbezogen werden. Fortfahren?“. **OK** löscht den Ordner samt Inhalt, **Abbrechen** behält alles.
- Schritt 2: Die Frage lautet „„01 Eingangsrechnungen“: den ganzen Ordner einbeziehen? (Abbrechen = nur die ausgewählten Elemente, Ordner ausschließen)“. **OK** löscht den **ganzen Ordner**.
- Schritt 3: Nach **Abbrechen** folgt die zweite Frage „Nur die ausgewählten Elemente verwenden und „01 Eingangsrechnungen“ ausschließen? (Abbrechen = Vorgang abbrechen)“. **OK** löscht **nur das markierte Dokument**; der Ordner bleibt. **Abbrechen** an dieser Stelle löscht nichts.
- Schritt 4: *Nicht offensichtlich:* Sind **alle** Inhalte eines Ordners mitmarkiert, kommt **keine** Rückfrage – der Ordner deckt sie ohnehin ab.

---

## MT-53: Umbenennen direkt in der Zeile (wie im Explorer)

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Einen Eintrag anklicken. Nach kurzer Pause **noch einmal auf seinen Namen** klicken (kein Doppelklick).
2. Einen neuen Namen tippen und **Enter** drücken. Bei einem zweiten Versuch mit **Esc** abbrechen, bei einem dritten daneben klicken.
3. Zusätzlich Rechtsklick → **Umbenennen** ausprobieren.

**Erwartet:**
- Der zweite Klick auf den bereits markierten Namen macht ihn zum **Eingabefeld**.
- **Enter** speichert, **Esc** bricht ab, ein Klick daneben speichert ebenfalls.
- Solange das Eingabefeld offen ist, lässt sich die Zeile nicht ziehen.

---

## MT-54: Sprache umschalten (Deutsch / English)

**Voraussetzungen:** BelegTool ist gestartet.

**Schritte:**
1. In der Symbolleiste in der Auswahlliste **🌐** den Eintrag **English (US)** wählen.
2. Ein Kontextmenü öffnen, die Auswahlliste der Komprimierungsverfahren ansehen und einen Blick auf die Statusleiste werfen.
3. Zurück auf **Deutsch** stellen, zwischendurch eine weitere Sprache ausprobieren, dann BelegTool neu starten.

**Erwartet:**
- Alle Beschriftungen wechseln **sofort** die Sprache: Hinweistexte der Symbolleiste, Menüs, Statusleiste, Rückfragen und Statusbezeichnungen.
- Die gewählte Sprache **bleibt** nach dem Neustart erhalten.
- *Nicht offensichtlich:* Übersetzt werden nur die Beschriftungen des Programms – **nicht** der Inhalt Ihrer Dokumente und nicht die Namen der Einträge.

---

## MT-55: Darstellung – Breite des Baums, Pfeile, einzeilige Namen, Seitenanzeige

**Beispieldateien:** `Beispielmappe.belegtool`, `Kontoauszug_8_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet und `Kontoauszug_8_Seiten.pdf` importiert.

**Schritte:**
1. Die **Trennlinie** zwischen Baum und Vorschau mit der Maus ziehen. BelegTool neu starten.
2. Die **Pfeile** vor den Ordnern und lange Namen ansehen; den Baum dafür schmal ziehen.
3. Den Kontoauszug anklicken und scrollen; die Zoom-Leiste beobachten.

**Erwartet:**
- Die Breite des Baums lässt sich durch Ziehen ändern und ist beim nächsten Start **gemerkt**.
- Die Pfeile sind groß genug, um sie gut zu treffen. Lange Namen bleiben **einzeilig** – der Baum scrollt waagerecht, statt umzubrechen.
- Die Zoom-Leiste zeigt **„Seite n / m“** für die gerade sichtbare Seite.
