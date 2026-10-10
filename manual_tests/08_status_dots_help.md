# 08 — Status-Punkte, F2, Hilfe, Exportoptionen, Dateisperre

Die Regeln der Status-Punkte, der rote Punkt „Komprimierung noch nicht entschieden“, Umbenennen mit F2, das Hilfe-Fenster, die Optionen beim Export und die Dateisperre für gemeinsam genutzte Ablagen.

---

## MT-50: Neue Einträge haben keinen Status

**Beispieldateien:** `Rechnung_5_Seiten.pdf`, `Teil_A_1_Seite.pdf`

**Voraussetzungen:** BelegTool ist gestartet.

**Schritte:**
1. Beide Dateien importieren und die neuen Zeilen im Baum ansehen.

**Erwartet:**
- Am **Zeilenende** steht **kein** Status-Punkt – neue Einträge beginnen **ohne Status**.

---

## MT-51: Status an einem einzelnen Dokument setzen

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Rechtsklick auf ein Dokument → unter **Status** auf **Zu erfassen** klicken.
2. Erneut rechtsklicken → **Erfasst**; dann **Vorjahr**; dann **Kein Status**.

**Erwartet:**
- Am Zeilenende erscheint ein Punkt, der die Farbe wechselt: **gelb** (Zu erfassen) → **grün** (Erfasst) → **rot** (Vorjahr).
- **Kein Status** entfernt den Punkt vollständig.

---

## MT-52: Status am Ordner gilt für den ganzen Inhalt

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet. Der Ordner **02 Bank** enthält Dokumente und den Unterordner **Darlehen** mit weiteren Dokumenten.

**Schritte:**
1. Rechtsklick auf den Ordner **02 Bank** → unter **Status (gesamter Inhalt)** auf **Erfasst** klicken.
2. Den Unterordner **Darlehen** aufklappen und die Zeilen ansehen.
3. Einmal **↶ Rückgängig** klicken.

**Erwartet:**
- **Jedes** Dokument darin wird grün – in **02 Bank** selbst **und** im Unterordner **Darlehen**.
- Der Ordner hat keinen eigenen Status; er zeigt die Punkte seines Inhalts.
- **Ein** Rückgängig-Schritt nimmt die ganze Übertragung zurück.

---

## MT-53: Sammelpunkte am Ordner und der schwarze Punkt

**Beispieldateien:** `Beispielmappe_mit_Status.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe_mit_Status.belegtool` ist geöffnet. Der Ordner **04 Statusmix** enthält ein Dokument mit Status **Erfasst** (grün), eines mit **Vorjahr** (rot) und eines **ohne Status**.

**Schritte:**
1. Den Ordner **04 Statusmix** zuklappen und seine Zeile ansehen.
2. Den Ordner aufklappen, `Beleg_ohne_Status.pdf` rechtsklicken und einen Status setzen.

**Erwartet:**
- Schritt 1: Der Ordner zeigt einen **roten** und einen **grünen** Punkt – je enthaltenem Status einen, in der Reihenfolge rot → gelb → grün – **und zusätzlich einen schwarzen Punkt**.
- Der schwarze Punkt bedeutet: „Ein Teil des Inhalts hat einen Status, ein Teil nicht.“
- Schritt 2: Sobald auch das dritte Dokument einen Status hat, **verschwindet der schwarze Punkt**.

---

## MT-54: Statusregeln beim Zusammenführen und Splitten

**Beispieldateien:** `Beispielmappe_mit_Status.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe_mit_Status.belegtool` ist geöffnet, der Ordner **01 Eingangsrechnungen** ist aufgeklappt. Darin sind `Telefon_2025-01.pdf` und `Strom_Abschlag_2025-01.pdf` grün (Erfasst), `Buerobedarf_Quittung.pdf` ist rot (Vorjahr) und `Sammelrechnung_Wartung.pdf` (4 Seiten) ist gelb (Zu erfassen).

**Schritte:**
1. Die beiden grünen Dokumente mit Strg+Klick markieren → Rechtsklick auf eines davon → **Zusammenführen → 1 PDF (2)**.
2. Das eben entstandene grüne Dokument und das rote `Buerobedarf_Quittung.pdf` markieren → **Zusammenführen → 1 PDF (2)**.
3. Rechtsklick auf `Sammelrechnung_Wartung.pdf` → **Splitten ▸** → **pro Seite**.

**Erwartet:**
- Schritt 1: Das zusammengeführte Dokument bleibt **grün** (alle Teile hatten denselben Status).
- Schritt 2: Das Ergebnis hat **keinen Status** (unterschiedliche Status der Teile).
- Schritt 3: **Jeder** der vier Teile trägt den Status des Originals (gelb).

---

## MT-55: Roter Punkt vorn – „Komprimierung noch nicht entschieden“

**Beispieldateien:** `Farbscan_Rechnung_3_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die Datei ist frisch importiert.

**Schritte:**
1. Den **Anfang** der Zeile ansehen, bevor der Eintrag angeklickt wird.
2. Den Eintrag anklicken, in der Auswahlliste ein Verfahren wählen und auf **❓ Lesbarkeit geprüft** klicken.

**Erwartet:**
- Schritt 1: Ein **roter Punkt vorn** in der Zeile bedeutet „Komprimierung noch nicht entschieden“ (so lautet auch der Hinweistext).
- Schritt 2: Nach dem Übernehmen **verschwindet** der rote Punkt vorn.
- *Nicht offensichtlich:* Lässt sich ein Dokument gar nicht verkleinern, verschwindet der Punkt ebenfalls (automatisch entschieden) – und **bleibt nach Speichern und erneutem Öffnen weg**.
- Nicht verwechseln: Der Punkt **vorn** betrifft die Komprimierung, die Punkte am **Zeilenende** den Status.

---

## MT-55b: Punkte verschwinden von selbst, wenn nichts einzusparen ist

**Beispieldateien:** `Viele_kleine_Belege.belegtool`

**Voraussetzungen:** BelegTool ist gestartet.

**Schritte:**
1. Die Datei öffnen, alle Ordner aufklappen und die roten Punkte vorn beobachten, **ohne** einen Eintrag anzuklicken.

**Erwartet:**
- Innerhalb weniger Sekunden verschwinden die roten Punkte bei den 24 Text-Belegen in **Eingang** und **Ausgang** von selbst – ein Hintergrundlauf prüft die kleinen Dokumente (bis 5 Seiten).
- Die beiden Dokumente im Ordner **Scans** **behalten** ihren roten Punkt, bis eine Komprimierung übernommen wird – sie lassen sich verkleinern.
- Die Statusleiste kann währenddessen kurz **⚙ Komprimiere …** anzeigen.
- *Nicht offensichtlich:* **Große** Dokumente (mehr als 5 Seiten) behalten den Punkt, bis sie angeklickt werden – sie vorab zu prüfen wäre zu aufwendig.

---

## MT-56: Umbenennen mit F2

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Einen Eintrag markieren und **F2** drücken.
2. Einen neuen Namen tippen und mit **Enter** bestätigen; bei einem zweiten Versuch mit **Esc** abbrechen.

**Erwartet:**
- Der Name wird zum Eingabefeld direkt in der Zeile (wie beim Klick auf einen bereits markierten Namen).
- **Enter** übernimmt, **Esc** verwirft.
- Das funktioniert auch in einer gefilterten Tag-Ansicht – Umbenennen ist eine inhaltliche Änderung.

---

## MT-57: Hilfe-Fenster, Sprachflaggen, Meldelinks

**Voraussetzungen:** BelegTool ist gestartet.

**Schritte:**
1. In der Symbolleiste auf **❓ Hilfe** klicken.
2. Auf die Flagge **🇬🇧** klicken, danach auf **🇩🇪**.
3. In der Fußzeile auf **▸ GitHub** und auf **✉ E-Mail** klicken.
4. Das Fenster mit **Esc** oder **✕** schließen.

**Erwartet:**
- Es öffnet sich ein Fenster mit Anleitungen in der aktuellen Sprache der Oberfläche (Englisch, falls diese Sprache noch nicht übersetzt ist).
- Die Flaggen schalten auf den maßgeblichen **englischen** bzw. **deutschen** Text um.
- **▸ GitHub** öffnet im Browser eine vorausgefüllte Seite für eine neue Meldung; **✉ E-Mail** öffnet einen vorausgefüllten E-Mail-Entwurf.

---

## MT-58: Exportoptionen (Inhaltsverzeichnis / Stichwortverzeichnis / Lesezeichen)

**Beispieldateien:** `Beispielmappe_mit_Tags.belegtool`, `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe_mit_Tags.belegtool` ist geöffnet.

**Schritte:**
1. Auf **⬇ Export PDF** klicken.
2. Die Kontrollkästchen im Dialog ansehen: **Inhaltsverzeichnis** (darunter **mit anklickbaren Links**), **Stichwortverzeichnis (nach Tags)** (darunter **mit anklickbaren Links**), **PDF-Lesezeichen (Seitenleiste)**.
3. Alles angehakt lassen → **Exportieren** → speichern → das PDF öffnen.
4. Erneut exportieren, diesmal ohne **Stichwortverzeichnis** und ohne **mit anklickbaren Links** beim Inhaltsverzeichnis; die beiden PDFs vergleichen.
5. `Beispielmappe.belegtool` (ohne Tags) öffnen und den Exportdialog ansehen.

**Erwartet:**
- Der vorgeschlagene Dateiname ist der **Dokumentname + `.pdf`** (nicht „Export.pdf“).
- Das erste PDF hat ein Inhaltsverzeichnis **und** eine Seite „Stichwortverzeichnis“, die zu jedem Tag die Dokumente mit Seitenzahl nennt. Die Einträge sind anklickbar; die Seitenleiste zeigt Lesezeichen.
- Im zweiten PDF fehlt das Stichwortverzeichnis und die Einträge des Inhaltsverzeichnisses sind nicht anklickbar. Ohne den Haken bei den Lesezeichen fehlt die Gliederung in der Seitenleiste.
- Schritt 5: *Nicht offensichtlich:* Enthält das Dokument **keine Tags**, ist das Stichwortverzeichnis **ausgegraut** (Hinweistext „Keine Tags im Dokument“).

---

## MT-59: Dateisperre – nur eine Person bearbeitet (muss eingeschaltet werden)

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** Die Dateisperre ist **standardmäßig aus**. Zum Einschalten vor dem Start von BelegTool die Umgebungsvariable `BELEG_FILE_LOCK` auf `1` setzen: Windows-Suche → „Umgebungsvariablen für dieses Konto bearbeiten“ → **Neu…** → Name `BELEG_FILE_LOCK`, Wert `1` → OK. Danach BelegTool neu starten. Die Beispielmappe liegt idealerweise auf einem gemeinsam genutzten Netzlaufwerk.

**Schritte:**
1. Die Datei in BelegTool öffnen.
2. BelegTool **ein zweites Mal starten** (oder an einem zweiten PC, dort ebenfalls mit gesetzter Variable) und **dieselbe** Datei öffnen.
3. Während die Datei im ersten BelegTool offen ist: im Windows-Explorer versuchen, sie **umzubenennen oder zu löschen**.
4. Im ersten BelegTool einen Eintrag umbenennen und mit **Strg+S** speichern. Danach das Fenster schließen.
5. Die Datei jetzt im zweiten BelegTool öffnen.

**Erwartet:**
- Schritt 2: Das zweite BelegTool lehnt ab: „Diese Datei wird bereits bearbeitet und kann nur von einer Person gleichzeitig geöffnet werden.“
- Schritt 3: Der Explorer verweigert Umbenennen und Löschen (Datei in Verwendung).
- Schritt 4: Das Speichern gelingt an Ort und Stelle; im Ordner bleibt danach **keine** `.bak`-Datei zurück.
- Schritt 5: Nach dem Schließen des ersten Fensters ist die Datei frei und lässt sich öffnen.
- *Nicht offensichtlich:* Ohne die Variable gilt nichts davon – die Datei wird dann gar nicht gesperrt.

**Hinweis:** Nach dem Test die Umgebungsvariable wieder **löschen**, sonst bleibt die Sperre für alle weiteren Tests eingeschaltet.
