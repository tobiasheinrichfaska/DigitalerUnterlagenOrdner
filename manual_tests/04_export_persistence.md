# 04 — Export, Speichern und Öffnen

PDF-Export (**⬇ Export PDF**), Speichern und erneutes Öffnen im Format `.belegtool` (**💾 Speichern**, **📂 Öffnen**).

---

## MT-14: Export als PDF mit Inhaltsverzeichnis

**Beispieldateien:** `Beispielmappe_mit_Tags.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe_mit_Tags.belegtool` ist geöffnet.

**Schritte:**
1. Auf **⬇ Export PDF** klicken (oder **Strg+E**).
2. Im Dialog „PDF exportieren“ **Inhaltsverzeichnis**, **Stichwortverzeichnis (nach Tags)** und **PDF-Lesezeichen (Seitenleiste)** angehakt lassen und auf **Exportieren** klicken.
3. Einen Speicherort wählen – der vorgeschlagene Dateiname ist der **Dokumentname + .pdf** – und speichern.
4. Das exportierte PDF in einem PDF-Betrachter öffnen.
5. Zurück in BelegTool: einige Einträge mit Strg+Klick markieren → Rechtsklick auf einen davon → **Auswahl als PDF exportieren (N)**. (Bei einem einzelnen Eintrag heißt der Menüpunkt **Als PDF exportieren**.)

**Erwartet:**
- Das PDF enthält die Seiten **aller** Dokumente der Mappe (18 Seiten Inhalt).
- Davor stehen ein gedrucktes **Inhaltsverzeichnis** und ein **Stichwortverzeichnis**; die Einträge sind **anklickbar** und springen zur richtigen Seite. Die Seitenleiste des Betrachters zeigt passende **Lesezeichen**.
- In BelegTool erscheint eine grüne Meldung **„✓ PDF exportiert (N Einträge)“**.
- Schritt 5: Das PDF enthält nur die markierten Einträge. Solange etwas markiert ist, zeigt **⬇** die Anzahl als kleine Zahl am Symbol.

**Schritte (Aufteilen in mehrere Dateien – ab Version 3.10.0):**
6. Erneut exportieren. Im Dialog **In mehrere Dateien aufteilen** anhaken, bei **max. Seiten pro Datei** `6` eintragen, bei **Trennen bei:** eine Stufe wählen und exportieren. Mit jeder der drei Stufen wiederholen:
   - **oberste Ordner** – ein Ordner der obersten Ebene bleibt zusammen, auch wenn er die Grenze überschreitet;
   - **jeder Ordnergrenze** – ein großer Ordner wird auf mehrere Dateien verteilt, jedes Dokument bleibt aber ganz;
   - **mitten im Dokument** – auch ein einzelnes Dokument darf an der Seitengrenze geteilt werden.

**Erwartet (Aufteilen):**
- Neben dem gewählten Namen entstehen mehrere Dateien (`…_Teil_1.pdf`, `…_Teil_2.pdf`, …); die Meldung lautet **„… — N Dateien“**. Mit der Beispielmappe und 6 Seiten sind es 3 Dateien (**oberste Ordner**), 4 Dateien (**jeder Ordnergrenze**) bzw. 3 Dateien (**mitten im Dokument**).
- Jede Teildatei ist ein gültiges PDF mit **eigenem Inhaltsverzeichnis**, das auf die anderen Teile **verweist** (graue Einträge).
- *Nicht offensichtlich:* Bei **mitten im Dokument** trägt ein geteiltes Dokument den **Seitenbereich** im Namen – hier `Sammelrechnung_Wartung.pdf (S. 1–3)` in der ersten und `Sammelrechnung_Wartung.pdf (S. 4–4)` in der zweiten Datei.
- *Nicht offensichtlich:* Beim Aufteilen sind Stichwortverzeichnis und Lesezeichen im Dialog ausgegraut – die Teildateien bekommen immer ihr eigenes Inhaltsverzeichnis.

---

## MT-15: Speichern und wieder öffnen (.belegtool)

**Beispieldateien:** `Beispielmappe_mit_Status.belegtool`, `Farbscan_Rechnung_3_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe_mit_Status.belegtool` ist geöffnet. Zur Vorbereitung:
- `Farbscan_Rechnung_3_Seiten.pdf` importieren, ein Verfahren wählen und mit **❓ Lesbarkeit geprüft** übernehmen;
- einen Ordner über den Pfeil **▾** zuklappen;
- einen Eintrag umbenennen.

**Schritte:**
1. Auf **💾 Speichern** klicken (oder **Strg+S**).
2. Auf den kleinen Pfeil **▾** rechts neben **💾** klicken → **Speichern unter…** wählen und einen neuen Speicherort angeben.
3. Das Fenster schließen.
4. BelegTool starten und die eben gespeicherte Datei mit **📂 Öffnen** laden.

**Erwartet:**
- Der Baum kommt **genau so** zurück: dieselben Ordner, Namen, Reihenfolge, Status-Punkte, **zugeklappte** Ordner, Tags und derselbe Komprimierungsstand.
- Die Vorschau zeigt die Seiten wieder (ein gestreifter Platzhalter kann kurz aufblitzen).
- *Nicht offensichtlich:* **💾** speichert eine bereits gespeicherte Datei **an Ort und Stelle** ohne Rückfrage; das **„•“** verschwindet und es erscheint **„✓ Gespeichert“**. Ein Dokument ohne Speicherort fragt beim ersten Speichern nach dem Ziel.
- *Ab Version 3.10.0:* Speichern ist eine **geteilte Schaltfläche** – der Hauptteil speichert, der Pfeil **▾** öffnet das Menü mit **Speichern unter…** (fragt immer nach einem neuen Ziel). Das Menü schließt mit **Esc**, bei einem Klick daneben oder nach der Auswahl. In älteren Versionen stehen dafür zwei getrennte Schaltflächen in der Symbolleiste.

---

## MT-15b: Datei per Doppelklick öffnen (Dateizuordnung)

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist **aus dem Microsoft Store** installiert und im Moment **nicht** gestartet. (Die ZIP-Version registriert keine Dateizuordnung – dort ist dieser Test nicht durchführbar.)

**Schritte:**
1. Im Windows-Explorer das Symbol und den Dateityp von `Beispielmappe.belegtool` ansehen.
2. Die Datei **doppelklicken**.
3. BelegTool schließen. Rechtsklick auf die Datei → **Öffnen mit**.

**Erwartet:**
- Schritt 1: Der Explorer zeigt als Typ **„BelegTool-Dokument“** und das BelegTool-Symbol.
- Schritt 2: BelegTool startet und zeigt die Beispielmappe direkt an – ohne den Umweg über **📂 Öffnen**.
- Schritt 3: **BelegTool** wird in der Liste „Öffnen mit“ angeboten.
- *Nicht offensichtlich:* Sind mehrere BelegTool-Varianten installiert (z. B. Store und eine ältere Testversion), kann Windows beim ersten Doppelklick fragen, welche App die Datei öffnen soll.

---

## MT-15c: Ein einzelnes PDF mit „Öffnen“ laden

**Beispieldateien:** `Rechnung_5_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet (leeres Dokument, keine ungespeicherten Änderungen).

**Schritte:**
1. Auf **📂 Öffnen** klicken. Im Dateidialog den Dateityp auf **„PDF (*.pdf)“** stellen und `Rechnung_5_Seiten.pdf` wählen.
2. Den Eintrag im Baum anklicken.
3. Über **▾ → Speichern unter…** als `.belegtool` an einem neuen Ort speichern.

**Erwartet:**
- Schritt 1: Das PDF wird als **neues Dokument** geöffnet. Der Dokumenttitel ist der Dateiname („Rechnung_5_Seiten“); im Baum steht ein Eintrag mit 5 Seiten.
- Schritt 3: Es entsteht eine `.belegtool`-Datei; die ursprüngliche PDF-Datei bleibt unverändert.
- *Unterschied zu Importieren:* **📂 Öffnen** ersetzt das angezeigte Dokument, **📥 Importieren** fügt die Datei dem geöffneten Dokument hinzu.

**Hinweis:** **💾 Speichern** (ohne „unter…“) schreibt bei einem so geöffneten PDF **direkt in die PDF-Datei zurück**. Sie bleibt ein normales PDF, das jeder Betrachter öffnet, wird dabei aber überschrieben. Wer das Original behalten will, nimmt **Speichern unter…**.

---

## MT-17: Übernommene Komprimierung verwirft die Quelle (nicht umkehrbar)

Sobald ein Dokument komprimiert übernommen („Lesbarkeit geprüft“) und gespeichert ist, enthält die Datei nur noch das komprimierte Ergebnis. Das unkomprimierte Original wird verworfen.

**Beispieldateien:** `Farbscan_Rechnung_3_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die Datei ist importiert.

**Schritte:**
1. Den Eintrag anklicken, ein Verfahren wählen (z. B. **JPEG (Farbe)** oder **JPEG (Graustufen)**) und auf **❓ Lesbarkeit geprüft** klicken.
2. Mit **💾 Speichern** als `.belegtool` speichern.
3. Das Fenster schließen, BelegTool starten und die gespeicherte Datei mit **📂 Öffnen** laden.
4. Denselben Eintrag anklicken und die Auswahlliste der Verfahren ansehen.

**Erwartet:**
- Die gespeicherte Datei ist deutlich **kleiner** als die importierte PDF-Datei (im Explorer vergleichen). Nach dem Öffnen wird das Dokument weiterhin korrekt angezeigt.
- *Wichtig:* Die Auswahlliste zeigt **„bereits komprimiert (keine Quelle)“** und ist **gesperrt**. Erneutes Komprimieren und Zurücksetzen sind nicht mehr möglich, weil das Original beim Speichern absichtlich verworfen wurde. Das ist gewollt und **nicht umkehrbar**.
- Ein Dokument, das vor dem Speichern **nicht** übernommen wurde, behält seine Quelle und bleibt nach dem Öffnen voll komprimierbar.

---

## MT-19: Speichern-Dialog – Komprimierungs-Alternativen mitspeichern oder nicht

Die Rückfrage erscheint nur, wenn es **berechnete, aber noch nicht übernommene** Komprimierungs-Alternativen gibt.

**Beispieldateien:** `Farbscan_Rechnung_3_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die Datei ist importiert. **Nicht** auf „Lesbarkeit geprüft“ klicken.

**Schritte:**
1. Den Eintrag anklicken und warten, bis in der Auswahlliste die Verfahren mit Größen stehen.
2. **💾 Speichern** (Strg+S) und einen Speicherort wählen.
3. Den erscheinenden Dialog lesen und auf **Wie geplant speichern** klicken. Die Dateigröße im Explorer notieren.
4. Über **▾ → Speichern unter…** in eine zweite Datei speichern, diesmal mit **Original speichern**. Größen vergleichen.

**Erwartet:**
- Es erscheint der Dialog **„Komprimierungs-Alternativen speichern?“** mit drei Schaltflächen: **Wie geplant speichern**, **Original speichern**, **Abbrechen**.
- **Wie geplant speichern** → größere Datei; nach dem Öffnen stehen die Verfahren sofort bereit (kein „Kompression läuft …“).
- **Original speichern** → kleinere Datei; nach dem Öffnen werden die Verfahren bei Bedarf neu berechnet.
- **Abbrechen** → es wird nichts gespeichert; das **„•“** bleibt stehen.
- *Nicht offensichtlich:* Der Dialog erscheint **nur**, wenn Alternativen vorhanden sind. Wurde nichts berechnet oder ist jedes Dokument bereits übernommen, speichert BelegTool ohne Rückfrage.
